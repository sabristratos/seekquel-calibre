import contextlib
import time
from dataclasses import dataclass
from threading import Event, Thread

from calibre import prepare_string_for_xml
from calibre.gui2 import Dispatcher, error_dialog, info_dialog, open_url, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import INVALID_KEY_CODE, SeekquelError, SeekquelUnreachable
from calibre_plugins.seekquel_sync.config import (
    ACTION_NAME,
    auto_sync_minutes,
    forget_connection,
    has_been_sent,
    is_connected,
    prefs,
    syncs_automatically,
)
from calibre_plugins.seekquel_sync.diagnostics import LAST_SYNC_AT, LAST_SYNC_OK
from calibre_plugins.seekquel_sync.log import log_path, note, read_log
from calibre_plugins.seekquel_sync.scope import ScopeUnavailable, books_in_scope, scope_name
from calibre_plugins.seekquel_sync.sync import (
    BUSY_MESSAGE,
    SyncBusy,
    automatic_sync,
    exclusive,
    is_syncing,
    prepare_flush,
    preview_sync,
    pull_library,
    push_library,
    push_scope,
    send_flush,
)
from qt.core import QMenu, QTimer, QToolButton, QUrl

WEB_URL = 'https://seekquel.app'

ICON_PATH = 'images/seekquel.png'

AUTO_SYNC_START_DELAY_SECONDS = 30
STAND_DOWN_BUDGET_SECONDS = 3
SECONDS_PER_MINUTE = 60
MILLISECONDS_PER_SECOND = 1000

SENDING_LABELS = (
    ('status', 'status'),
    ('rating', 'a rating'),
    ('review', 'a review'),
    ('started_at', 'a start date'),
    ('finished_at', 'a finish date'),
    ('progress_percent', 'progress'),
    ('tags', 'tags'),
)


def _books(count):
    return f'{count} book' if count == 1 else f'{count} books'


def _when(timestamp):
    moment = time.localtime(timestamp)
    clock = time.strftime('%H:%M', moment)

    if moment[:3] == time.localtime()[:3]:
        return f'today at {clock}'

    return f'on {moment.tm_mday} {time.strftime("%b", moment)} at {clock}'


@dataclass(frozen=True)
class AutomaticRun:
    thread: Thread
    abort: Event


class SeekquelSyncAction(InterfaceAction):
    name = ACTION_NAME
    action_spec = ('Seekquel Sync', None, 'Sync this library with Seekquel', None)
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_type = 'current'

    def genesis(self):
        self.qaction.setIcon(get_icons(ICON_PATH, 'Seekquel Sync'))
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)
        self.menu.aboutToShow.connect(self.rebuild_menu)
        self.automatic_run = None
        self.closing = False
        self.automatic_finished = Dispatcher(self._automatic_finished)
        self.automatic_timer = QTimer(self.gui)
        self.automatic_timer.setSingleShot(True)
        self.automatic_timer.timeout.connect(self.run_automatic_sync)
        self.rebuild_menu()

    def rebuild_menu(self):
        self.menu.clear()

        if not is_connected():
            self.menu.addAction('Connect to Seekquel...').triggered.connect(self.connect)
            self.menu.addSeparator()
            self.menu.addAction('Show the log...').triggered.connect(self.show_log)
            self.menu.addAction('Open Seekquel').triggered.connect(self.open_site)

            return

        self.menu.addAction(self._status_line()).setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction('Preview a sync...').triggered.connect(self.preview)
        self.menu.addSeparator()
        self.menu.addAction(self._send_all_label()).triggered.connect(self.push_all)
        self.menu.addAction('Send the selected books').triggered.connect(self.push_selected)
        self.menu.addSeparator()
        self.menu.addAction('Bring Seekquel up to date here').triggered.connect(self.pull)
        self.menu.addSeparator()
        self.menu.addAction('View this book on Seekquel').triggered.connect(self.open_book)
        self.menu.addSeparator()
        self.menu.addAction('Settings...').triggered.connect(self.show_configuration)
        self.menu.addAction('Show the log...').triggered.connect(self.show_log)
        self.menu.addAction('Disconnect').triggered.connect(self.disconnect)

    def initialization_complete(self):
        self._schedule(AUTO_SYNC_START_DELAY_SECONDS)

    def library_about_to_change(self, olddb, _db):
        self._stand_down(olddb)

    def library_changed(self, _db):
        self.rebuild_menu()
        self._schedule(AUTO_SYNC_START_DELAY_SECONDS)

    def shutting_down(self):
        self.closing = True
        self.automatic_timer.stop()
        self._stand_down(self.gui.current_db)

        return True

    def schedule_automatic_sync(self):
        self._schedule(auto_sync_minutes() * SECONDS_PER_MINUTE)

    def run_automatic_sync(self):
        if self.closing or not syncs_automatically():
            return

        if is_syncing():
            note('Automatic sync skipped: another sync is running')
            self.schedule_automatic_sync()

            return

        db = self._current_db()

        if db is None:
            self.schedule_automatic_sync()

            return

        abort = Event()
        thread = Thread(target=self._automatic_worker, args=(db, abort), daemon=True)
        self.automatic_run = AutomaticRun(thread, abort)
        thread.start()

    def connect(self):
        from calibre_plugins.seekquel_sync.dialogs.pair import PairDialog

        dialog = PairDialog(self.gui)

        if dialog.exec() == dialog.DialogCode.Accepted:
            self.rebuild_menu()
            info_dialog(
                self.gui,
                'Connected',
                'This library is connected to Seekquel.\n\n'
                'Nothing is mapped yet. Choose which of your own columns Seekquel should read '
                'and write, and which books to send. Settings opens next.',
                show=True,
            )
            self.show_configuration()

    def disconnect(self):
        if not question_dialog(self.gui, 'Disconnect', 'Stop syncing this library with Seekquel?'):
            return

        forget_connection()
        self.rebuild_menu()

    def push_all(self):
        if self._already_syncing():
            return

        book_ids = self._books_to_send()

        if book_ids is None:
            return

        self._push(book_ids, whole_scope=True)

    def push_selected(self):
        if self._already_syncing():
            return

        book_ids = self._selected_book_ids()

        if not book_ids:
            error_dialog(self.gui, 'Nothing selected', 'Select one or more books first.', show=True)

            return

        self._push(book_ids)

    def preview(self):
        if self._already_syncing():
            return

        book_ids = self._books_to_send()

        if book_ids is None:
            return

        db = self.gui.current_db.new_api

        job = ThreadedJob(
            'seekquel-preview',
            'Working out what a sync would change',
            self._run_preview,
            (db, book_ids),
            {},
            Dispatcher(self._preview_finished),
            max_concurrent_count=1,
            killable=True,
        )
        self.gui.job_manager.run_threaded_job(job)

    def pull(self):
        if self._already_syncing():
            return

        db = self.gui.current_db.new_api

        job = ThreadedJob(
            'seekquel-pull',
            'Bringing Seekquel up to date in Calibre',
            self._run_pull,
            (db,),
            {},
            Dispatcher(self._pull_finished),
            max_concurrent_count=1,
            killable=True,
        )
        self.gui.job_manager.run_threaded_job(job)

    def open_book(self):
        book_ids = self._selected_book_ids()

        if not book_ids:
            error_dialog(self.gui, 'Nothing selected', 'Select a book first.', show=True)

            return

        identifiers = self.gui.current_db.new_api.field_for('identifiers', book_ids[0]) or {}
        slug = identifiers.get('seekquel')

        if not slug:
            error_dialog(
                self.gui,
                'Not linked yet',
                'Seekquel has not matched this book to a catalogue page yet.\n\n'
                'Send your library, then bring Seekquel up to date here.',
                show=True,
            )

            return

        open_url(QUrl(f'{WEB_URL}/work/{slug}'))

    def open_site(self):
        open_url(QUrl(WEB_URL))

    def show_configuration(self):
        self.interface_action_base_plugin.do_user_config(self.gui)
        self.rebuild_menu()

    def show_log(self):
        from calibre.gui2.dialogs.message_box import ViewLog

        text = read_log()

        if not text.strip():
            info_dialog(
                self.gui,
                'Nothing logged yet',
                f'Seekquel has not recorded anything yet.\n\nThe log lives at {log_path()}.',
                show=True,
            )

            return

        dialog = ViewLog('Seekquel log', f'<pre>{prepare_string_for_xml(text)}</pre>', parent=self.gui)
        dialog.exec()

    def _send_all_label(self):
        name = scope_name()

        if name is None:
            return 'Send my whole library'

        return f'Send the books I sync ({name})'

    def _books_to_send(self):
        try:
            book_ids = books_in_scope(self.gui.current_db.new_api)
        except ScopeUnavailable as error:
            error_dialog(
                self.gui,
                'Nothing was sent',
                f'{error}\n\nOpen Settings, What to send, and choose which books to send.',
                show=True,
            )

            return None

        if book_ids:
            return book_ids

        name = scope_name()

        if name is None:
            error_dialog(self.gui, 'Nothing to send', 'This library has no books in it.', show=True)
        else:
            error_dialog(
                self.gui,
                'Nothing to send',
                f'Nothing in this library matches "{name}".\n\n'
                'Open Settings, What to send, to change which books are sent.',
                show=True,
            )

        return None

    def _push(self, book_ids, whole_scope=False):
        if not book_ids:
            error_dialog(self.gui, 'Nothing to send', 'This library has no books in it.', show=True)

            return

        db = self.gui.current_db.new_api

        job = ThreadedJob(
            'seekquel-push',
            f'Sending {len(book_ids)} books to Seekquel',
            self._run_push_scope if whole_scope else self._run_push,
            (db, book_ids),
            {},
            Dispatcher(self._push_finished),
            max_concurrent_count=1,
            killable=True,
        )
        self.gui.job_manager.run_threaded_job(job)

    def _run_push(self, db, book_ids, notifications=None, abort=None, log=None):
        with exclusive():
            return push_library(db, book_ids, notifications=notifications, log=log, abort=abort)

    def _run_push_scope(self, db, book_ids, notifications=None, abort=None, log=None):
        with exclusive():
            return push_scope(db, book_ids, notifications=notifications, log=log, abort=abort)

    def _run_pull(self, db, notifications=None, abort=None, log=None):
        with exclusive():
            return pull_library(db, notifications=notifications, log=log, abort=abort)

    def _run_preview(self, db, book_ids, notifications=None, abort=None, log=None):
        with exclusive():
            return preview_sync(db, book_ids, notifications=notifications, log=log, abort=abort)

    def _already_syncing(self):
        if not is_syncing():
            return False

        info_dialog(self.gui, 'Already syncing', BUSY_MESSAGE, show=True)

        return True

    def _schedule(self, seconds):
        self.automatic_timer.stop()

        if self.closing or not syncs_automatically():
            return

        self.automatic_timer.start(seconds * MILLISECONDS_PER_SECOND)

    def _automatic_worker(self, db, abort):
        result = None
        failure = None

        try:
            result = automatic_sync(db, abort)
        except Exception as error:
            failure = error
            note(f'Automatic sync did not finish: {error}')

        with contextlib.suppress(RuntimeError):
            self.automatic_finished(db, result, failure)

    def _automatic_finished(self, db, result, failure):
        self.automatic_run = None

        if self.closing or not self._is_current(db):
            return

        if isinstance(failure, SeekquelError) and failure.code == INVALID_KEY_CODE:
            self._drop_dead_connection()

            return

        if result:
            self._refresh_books((result.get('pulled') or {}).get('book_ids') or ())

        self.schedule_automatic_sync()

    def _stand_down(self, database):
        try:
            self._stand_down_on(database.new_api)
        except Exception as error:
            note(f'Could not send the last changes: {error}')

    def _stand_down_on(self, db):
        run = self.automatic_run

        if run is not None and run.thread.is_alive():
            run.abort.set()
            run.thread.join(STAND_DOWN_BUDGET_SECONDS)

            return

        if not syncs_automatically() or is_syncing():
            return

        flush = prepare_flush(db)

        if flush is None:
            return

        thread = Thread(target=self._flush_worker, args=(flush,), daemon=True)
        thread.start()
        thread.join(STAND_DOWN_BUDGET_SECONDS)

        if thread.is_alive():
            note(f'Still sending the last changes after {STAND_DOWN_BUDGET_SECONDS}s, left for next time')

    def _flush_worker(self, flush):
        try:
            send_flush(flush)
        except Exception as error:
            note(f'Could not send the last changes: {error}')

    def _is_current(self, db):
        return db is not None and self._current_db() is db

    def _current_db(self):
        try:
            return self.gui.current_db.new_api
        except Exception:
            return None

    def _status_line(self):
        if is_syncing():
            return 'Syncing with Seekquel now'

        if not syncs_automatically():
            return 'Syncs only when you ask'

        db = self._current_db()

        if db is None or not has_been_sent(db):
            return 'Syncs on its own once you send this library'

        last = prefs.get(LAST_SYNC_AT)

        if not last:
            return f'Syncs every {auto_sync_minutes()} minutes'

        if prefs.get(LAST_SYNC_OK):
            return f'Last synced {_when(last)}'

        return f'Last sync failed {_when(last)}, trying again later'

    def _push_finished(self, job):
        if job.failed:
            self._report_failure(job, 'Could not send your library')

            return

        result = job.result or {}
        skipped = result.get('skipped', 0)
        message = f"Seekquel took {result.get('accepted', 0)} of {_books(result.get('total', 0))}."

        name = scope_name()

        if name is not None:
            message += f'\n\nThose are the books matching "{name}", which is what Settings says to send.'

        if skipped == 1:
            message += '\n\nOne was skipped because Calibre has no id for it yet.'
        elif skipped:
            message += f'\n\n{skipped} were skipped because Calibre has no id for them yet.'

        message += (
            '\n\nMatching happens in the background, so give it a moment, then use '
            '"Bring Seekquel up to date here" to read the results back.'
        )

        info_dialog(self.gui, 'Sent to Seekquel', message, show=True)

    def _preview_finished(self, job):
        if job.failed:
            self._report_failure(job, 'Could not work out what a sync would change')

            return

        result = job.result or {}
        sending = result.get('sending') or {}
        receiving = result.get('receiving') or {}

        lines = ['Nothing has been changed.', '']
        lines.extend(self._sending_lines(sending))
        lines.append('')
        lines.extend(self._receiving_lines(receiving))

        sample = receiving.get('sample') or []
        details = '\n'.join(sample) if sample else None

        if sample and receiving.get('changed', 0) > len(sample):
            details += f'\n\n...and {receiving["changed"] - len(sample)} more.'

        info_dialog(
            self.gui,
            'What a sync would do',
            '\n'.join(lines),
            det_msg=details,
            show=True,
        )

    def _sending_lines(self, sending):
        name = scope_name()
        where = 'your whole library' if name is None else f'"{name}"'
        lines = [f'Sending {_books(sending.get("sending", 0))}, from {where}.']

        carried = [
            f'{label} on {sending["fields"][key]}'
            for key, label in SENDING_LABELS
            if (sending.get('fields') or {}).get(key)
        ]

        if carried:
            lines.append('Carrying ' + ', '.join(carried) + '.')

        unidentified = sending.get('unidentified', 0)

        if unidentified:
            lines.append(
                f'{unidentified} carry no ISBN, so Seekquel has to match them on title and author.'
            )

        skipped = sending.get('skipped', 0)

        if skipped:
            lines.append(f'{skipped} would be skipped because Calibre has no id for them yet.')

        return lines

    def _receiving_lines(self, receiving):
        changed = receiving.get('changed', 0)

        if changed == 0:
            lines = ['Nothing would change in Calibre.']
        else:
            lines = [f'{_books(changed)} would change in Calibre.']
            columns = receiving.get('columns') or {}
            lines.append('Columns touched: ' + ', '.join(
                f'{column} ({count})' for column, count in sorted(columns.items())
            ) + '.')

        unmatched = receiving.get('unmatched', 0)

        if unmatched:
            lines.append(f'{_books(unmatched)} are waiting for you on Seekquel.')

        covers = receiving.get('covers', 0)

        if covers:
            lines.append(f'Up to {covers} covers would be sent, for books Seekquel has none for.')

        return lines

    def _pull_finished(self, job):
        if job.failed:
            self._report_failure(job, 'Could not read from Seekquel')

            return

        result = job.result or {}
        updated = result.get('updated', 0)
        unmatched = result.get('unmatched', 0)
        missing = result.get('missing', 0)
        covers = result.get('covers', 0)

        if updated == 0:
            message = 'Nothing needed changing in Calibre.'
        else:
            message = f'Updated {_books(updated)} in Calibre.'

        if unmatched == 1:
            message += (
                '\n\nOne book is waiting for you on Seekquel: it could not work out which '
                'book it is. Open Settings, Integrations, Calibre on Seekquel to sort it out.'
            )
        elif unmatched:
            message += (
                f'\n\n{unmatched} books are waiting for you on Seekquel: it could not work '
                'out which books they are. Open Settings, Integrations, Calibre on Seekquel '
                'to sort them out.'
            )

        if missing == 1:
            message += '\n\nOne book Seekquel knows about is not in this library.'
        elif missing:
            message += f'\n\n{missing} books Seekquel knows about are not in this library.'

        if covers == 1:
            message += '\n\nSent one cover, for a book Seekquel had none for.'
        elif covers:
            message += f'\n\nSent {covers} covers, for books Seekquel had none for.'

        self._refresh_books(result.get('book_ids') or ())
        info_dialog(self.gui, 'Up to date', message, show=True)

    def _refresh_books(self, book_ids):
        if not book_ids:
            return

        self.gui.library_view.model().refresh_ids(list(book_ids))
        self.gui.tags_view.recount()

    def _report_failure(self, job, title):
        error = getattr(job, 'exception', None)

        if isinstance(error, SyncBusy):
            message = BUSY_MESSAGE
        elif isinstance(error, SeekquelUnreachable):
            message = (
                f'Could not reach Seekquel.\n\n{error}\n\n'
                'Check the address in Settings and that you are online.'
            )
        elif isinstance(error, SeekquelError):
            message = str(error)

            if error.code == INVALID_KEY_CODE:
                self._drop_dead_connection()
                message += (
                    '\n\nThis library has been disconnected here. '
                    'Connect it again from the Seekquel Sync menu.'
                )
            elif error.status == 401:
                message += '\n\nReconnect this library from Settings.'
        else:
            message = 'Something went wrong. The job details have the whole story.'

        error_dialog(self.gui, title, message, det_msg=job.details, show=True)

    def _drop_dead_connection(self):
        if not is_connected():
            return

        note('Seekquel no longer recognises this key, forgetting it')
        forget_connection()
        self.rebuild_menu()

    def _selected_book_ids(self):
        rows = self.gui.library_view.selectionModel().selectedRows()

        if not rows:
            return []

        return [self.gui.library_view.model().id(row) for row in rows]

    def about(self):
        return f'Seekquel Sync {__version__}'
