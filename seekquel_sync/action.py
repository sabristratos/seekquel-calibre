from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog, gprefs, info_dialog, open_url, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import SeekquelError, SeekquelUnreachable
from calibre_plugins.seekquel_sync.config import forget_connection, is_connected, prefs
from calibre_plugins.seekquel_sync.log import log_path, read_log
from calibre_plugins.seekquel_sync.sync import pull_library, push_library
from qt.core import QMenu, QToolButton, QUrl

WEB_URL = 'https://seekquel.app'

ICON_PATH = 'images/seekquel.png'

TOOLBAR_KEY = 'action-layout-toolbar'


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

        self.menu.addAction('Send my whole library').triggered.connect(self.push_all)
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
                'Next, open Settings and choose which of your columns Seekquel should read and write.',
                show=True,
            )

    def disconnect(self):
        if not question_dialog(self.gui, 'Disconnect', 'Stop syncing this library with Seekquel?'):
            return

        forget_connection()
        self.rebuild_menu()

    def push_all(self):
        self._push(list(self.gui.current_db.new_api.all_book_ids()))

    def push_selected(self):
        book_ids = self._selected_book_ids()

        if not book_ids:
            error_dialog(self.gui, 'Nothing selected', 'Select one or more books first.', show=True)

            return

        self._push(book_ids)

    def pull(self):
        db = self.gui.current_db.new_api

        job = ThreadedJob(
            'seekquel-pull',
            'Bringing Seekquel up to date in Calibre',
            self._run_pull,
            (db,),
            {},
            self._pull_finished,
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
            self._push_finished,
            max_concurrent_count=1,
            killable=True,
        )
        self.gui.job_manager.run_threaded_job(job)

    def _run_push(self, db, book_ids, notifications=None, abort=None, log=None):
        return push_library(db, book_ids, notifications=notifications, log=log, abort=abort)

    def _run_pull(self, db, notifications=None, abort=None, log=None):
        return pull_library(db, notifications=notifications, log=log, abort=abort)

    def _push_finished(self, job):
        if job.failed:
            self._report_failure(job, 'Could not send your library')

            return

        result = job.result or {}
        message = f"Seekquel took {result.get('accepted', 0)} of {result.get('total', 0)} books."

        if result.get('skipped'):
            message += f"\n\n{result['skipped']} were skipped because Calibre has no id for them yet."

        message += (
            '\n\nMatching happens in the background, so give it a moment, then use '
            '"Bring Seekquel up to date here" to read the results back.'
        )

        info_dialog(self.gui, 'Sent to Seekquel', message, show=True)

    def _pull_finished(self, job):
        if job.failed:
            self._report_failure(job, 'Could not read from Seekquel')

            return

        result = job.result or {}
        message = f"Updated {result.get('updated', 0)} books in Calibre."

        if result.get('unmatched'):
            message += (
                f"\n\n{result['unmatched']} books are waiting for you on Seekquel: it could "
                'not work out which book they are. Open Settings, Integrations, '
                'Calibre on Seekquel to sort them out.'
            )

        if result.get('missing'):
            message += f"\n\n{result['missing']} books Seekquel knows about are not in this library."

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
