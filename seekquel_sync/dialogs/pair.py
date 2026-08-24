import contextlib
import queue
from threading import Thread

from calibre.gui2 import error_dialog
from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import (
    SeekquelApi,
    SeekquelError,
    SeekquelUnreachable,
)
from calibre_plugins.seekquel_sync.config import DEFAULT_BASE_URL, prefs
from calibre_plugins.seekquel_sync.log import note
from qt.core import (
    QDialog,
    QDialogButtonBox,
    QFont,
    QLabel,
    QLineEdit,
    Qt,
    QTimer,
    QVBoxLayout,
)

POLL_INTERVAL_MS = 3000
DRAIN_INTERVAL_MS = 150
PENDING_CODES = ('AUTHORIZATION_PENDING', 'SLOW_DOWN')

START = 'start'
POLL = 'poll'


class PairDialog(QDialog):
    def __init__(self, gui):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.device_code = None
        self.timer = None
        self.polling = False
        self.answers = queue.Queue()

        self.setWindowTitle('Connect to Seekquel')
        self.resize(460, 280)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('Seekquel address'))
        self.base_url = QLineEdit(prefs.get('base_url') or DEFAULT_BASE_URL)
        layout.addWidget(self.base_url)

        self.instructions = QLabel(
            'Click Start. Seekquel will show you a code here.\n'
            'Then open Seekquel, go to Settings, Integrations, Calibre, and enter it.'
        )
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)

        self.code = QLabel('')
        code_font = QFont()
        code_font.setPointSize(22)
        code_font.setBold(True)
        self.code.setFont(code_font)
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.code)

        self.state = QLabel('')
        self.state.setWordWrap(True)
        layout.addWidget(self.state)

        layout.addStretch(1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.start_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.start_button.setText('Start')
        self.buttons.accepted.connect(self.start)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.drain = QTimer(self)
        self.drain.timeout.connect(self._drain)
        self.drain.start(DRAIN_INTERVAL_MS)

    def start(self):
        base_url = self.base_url.text().strip().rstrip('/')

        if not base_url:
            error_dialog(self, 'Connect to Seekquel', 'Enter the Seekquel address first.', show=True)

            return

        prefs['base_url'] = base_url
        prefs.commit()

        self.base_url.setEnabled(False)
        self.start_button.setEnabled(False)
        self.state.setText('Asking Seekquel for a code...')

        name = self._library_name()
        client = self._api()

        self._in_background(START, lambda: client.start_pairing(name, 'calibre'))

    def poll(self):
        if not self.device_code or self.polling:
            return

        self.polling = True
        code = self.device_code
        client = self._api()

        self._in_background(POLL, lambda: client.poll_pairing(code))

    def _in_background(self, kind, call):
        answers = self.answers

        def run():
            try:
                answers.put((kind, call(), None))
            except Exception as error:
                answers.put((kind, None, error))

        Thread(target=run, daemon=True).start()

    def _drain(self):
        while True:
            try:
                kind, answer, error = self.answers.get_nowait()
            except queue.Empty:
                return

            if kind == START:
                self._started(answer, error)
            else:
                self.polling = False
                self._polled(answer, error)

    def _started(self, answer, error):
        if isinstance(error, SeekquelUnreachable):
            self._fail(f'Could not reach Seekquel.\n\n{error}')

            return

        if error is not None:
            self._fail(str(error))

            return

        note(f"Pairing started against {prefs.get('base_url')}")
        self.device_code = answer.get('device_code')
        self.code.setText(answer.get('user_code') or '')
        self.state.setText('Waiting for you to approve it in Seekquel...')

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(max(POLL_INTERVAL_MS, int(answer.get('interval') or 0) * 1000))

    def _polled(self, answer, error):
        if isinstance(error, SeekquelUnreachable):
            return

        if isinstance(error, SeekquelError):
            if error.code in PENDING_CODES:
                return

            self._fail(str(error))

            return

        if error is not None:
            self._fail(str(error))

            return

        self._store(answer)

    def _store(self, answer):
        key = answer.get('key')

        if not key:
            self._fail('Seekquel did not hand back a key.')

            return

        self._stop_timer()

        prefs['key'] = key
        prefs['device_id'] = answer.get('device_id') or ''
        prefs['pull_marks'] = {}

        if answer.get('api_url'):
            prefs['base_url'] = answer['api_url'].rstrip('/')

        prefs.commit()

        note('Pairing approved, this library is connected')
        self._report_install()
        self.accept()

    def _report_install(self):
        name = self._library_name()
        client = self._api()

        def run():
            with contextlib.suppress(SeekquelError, SeekquelUnreachable):
                client.report_device(name, 'calibre', __version__)

        Thread(target=run, daemon=True).start()

    def _fail(self, message):
        note(f'Pairing failed: {message}')
        self._stop_timer()
        self.state.setText(message)
        self.code.setText('')
        self.base_url.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText('Try again')

    def _stop_timer(self):
        self.polling = False

        if self.timer is not None:
            self.timer.stop()
            self.timer = None

    def reject(self):
        self._stop_timer()
        self.drain.stop()
        QDialog.reject(self)

    def accept(self):
        self._stop_timer()
        self.drain.stop()
        QDialog.accept(self)

    def _api(self):
        return SeekquelApi(prefs.get('base_url'), prefs.get('key'))

    def _library_name(self):
        try:
            path = self.gui.current_db.library_path.rstrip('/\\')

            return path.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] or 'Calibre'
        except Exception:
            return 'Calibre'
