import contextlib

from calibre.gui2 import error_dialog
from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import (
    SeekquelApi,
    SeekquelError,
    SeekquelUnreachable,
)
from calibre_plugins.seekquel_sync.config import DEFAULT_BASE_URL, prefs
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
PENDING_CODES = ('AUTHORIZATION_PENDING', 'SLOW_DOWN')


class PairDialog(QDialog):
    def __init__(self, gui):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.device_code = None
        self.timer = None

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

        try:
            answer = self._api().start_pairing(self._library_name(), 'calibre')
        except SeekquelUnreachable as error:
            self._fail(f'Could not reach Seekquel.\n\n{error}')

            return
        except SeekquelError as error:
            self._fail(str(error))

            return

        self.device_code = answer.get('device_code')
        self.code.setText(answer.get('user_code') or '')
        self.state.setText('Waiting for you to approve it in Seekquel...')

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(max(POLL_INTERVAL_MS, int(answer.get('interval') or 0) * 1000))

    def poll(self):
        if not self.device_code:
            return

        try:
            answer = self._api().poll_pairing(self.device_code)
        except SeekquelUnreachable:
            return
        except SeekquelError as error:
            if error.code in PENDING_CODES:
                return

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
        prefs['last_pulled_at'] = ''

        if answer.get('api_url'):
            prefs['base_url'] = answer['api_url'].rstrip('/')

        prefs.commit()

        self._report_install()
        self.accept()

    def _report_install(self):
        with contextlib.suppress(SeekquelError, SeekquelUnreachable):
            self._api().report_device(self._library_name(), 'calibre', __version__)

    def _fail(self, message):
        self._stop_timer()
        self.state.setText(message)
        self.code.setText('')
        self.base_url.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText('Try again')

    def _stop_timer(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer = None

    def reject(self):
        self._stop_timer()
        QDialog.reject(self)

    def _api(self):
        return SeekquelApi(prefs.get('base_url'), prefs.get('key'))

    def _library_name(self):
        try:
            path = self.gui.current_db.library_path.rstrip('/\\')

            return path.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] or 'Calibre'
        except Exception:
            return 'Calibre'
