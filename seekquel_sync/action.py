from calibre import prepare_string_for_xml
from calibre.gui2 import Dispatcher, error_dialog, gprefs, info_dialog, open_url, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import SeekquelError, SeekquelUnreachable
from calibre_plugins.seekquel_sync.config import forget_connection, is_connected, prefs
from calibre_plugins.seekquel_sync.log import log_path, read_log
from calibre_plugins.seekquel_sync.scope import ScopeUnavailable, books_in_scope, scope_name
from calibre_plugins.seekquel_sync.sync import preview_sync, pull_library, push_library
from qt.core import QMenu, QToolButton, QUrl

WEB_URL = 'https://seekquel.app'

ICON_PATH = 'images/seekquel.png'

TOOLBAR_KEY = 'action-layout-toolbar'

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


class SeekquelSyncAction(InterfaceAction):
    name = 'Seekquel Sync'
    action_spec = ('Seekquel', None, 'Sync this library with Seekquel', None)
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_type = 'current'

    def genesis(self):
        self.qaction.setIcon(get_icons(ICON_PATH, 'Seekquel Sync'))
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)
        self.menu.aboutToShow.connect(self.rebuild_menu)
        self.rebuild_menu()

    def initialization_complete(self):
        self.place_on_toolbar()

    def place_on_toolbar(self):
        if prefs.get('toolbar_placed'):
            return

        prefs['toolbar_placed'] = True
        prefs.commit()

        layout = list(gprefs.get(TOOLBAR_KEY) or ())

        if self.name in layout:
            return

        gprefs[TOOLBAR_KEY] = (*layout, self.name)

        try:
            self.gui.bars_manager.init_bars()
            self.gui.bars_manager.update_bars()
            self.gui.bars_manager.apply_settings()
        except Exception:
            pass

    def rebuild_menu(self):
        self.menu.clear()

        if not is_connected():
            self.menu.addAction('Connect to Seekquel...').triggered.connect(self.connect)
            self.menu.addSeparator()
            self.menu.addAction('Show the log...').triggered.connect(self.show_log)
            self.menu.addAction('Open Seekquel').triggered.connect(self.open_site)

            return

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

    def library_changed(self, _db):
        self.rebuild_menu()

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
        book_ids = self._books_to_send()

        if book_ids is None:
            return

        self._push(book_ids)

    def push_selected(self):
        book_ids = self._selected_book_ids()

        if not book_ids:
            error_dialog(self.gui, 'Nothing selected', 'Select one or more books first.', show=True)

            return

        self._push(book_ids)

    def preview(self):
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

    def _push(self, book_ids):
        if not book_ids:
            error_dialog(self.gui, 'Nothing to send', 'This library has no books in it.', show=True)

            return

        db = self.gui.current_db.new_api

        job = ThreadedJob(
            'seekquel-push',
            f'Sending {len(book_ids)} books to Seekquel',
            self._run_push,
            (db, book_ids),
            {},
            Dispatcher(self._push_finished),
            max_concurrent_count=1,
            killable=True,
        )
        self.gui.job_manager.run_threaded_job(job)

    def _run_push(self, db, book_ids, notifications=None, abort=None, log=None):
        return push_library(db, book_ids, notifications=notifications, log=log, abort=abort)

    def _run_pull(self, db, notifications=None, abort=None, log=None):
        return pull_library(db, notifications=notifications, log=log, abort=abort)

    def _run_preview(self, db, book_ids, notifications=None, abort=None, log=None):
        return preview_sync(db, book_ids, notifications=notifications, log=log, abort=abort)

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

        if isinstance(error, SeekquelUnreachable):
            message = (
                f'Could not reach Seekquel.\n\n{error}\n\n'
                'Check the address in Settings and that you are online.'
            )
        elif isinstance(error, SeekquelError):
            message = str(error)

            if error.status == 401:
                message += '\n\nReconnect this library from Settings.'
        else:
            message = 'Something went wrong. The job details have the whole story.'

        error_dialog(self.gui, title, message, det_msg=job.details, show=True)

    def _selected_book_ids(self):
        rows = self.gui.library_view.selectionModel().selectedRows()

        if not rows:
            return []

        return [self.gui.library_view.model().id(row) for row in rows]

    def about(self):
        return f'Seekquel Sync {__version__}'
