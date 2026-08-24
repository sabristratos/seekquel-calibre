from calibre.utils.config import JSONConfig
from qt.core import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

DEFAULT_BASE_URL = 'https://api.seekquel.app/calibre'

STATUS_VALUES = [
    ('want_to_read', 'Want to read'),
    ('reading', 'Reading'),
    ('paused', 'Paused'),
    ('read', 'Read'),
    ('did_not_finish', 'Did not finish'),
]

COLUMN_FIELDS = [
    ('status_column', 'Status', ('text', 'enumeration')),
    ('rating_column', 'Rating', ('rating',)),
    ('review_column', 'Review', ('comments',)),
    ('started_column', 'Date started', ('datetime',)),
    ('finished_column', 'Date finished', ('datetime',)),
    ('progress_column', 'Progress (%)', ('int', 'float')),
]

MARK_SEPARATOR = '|'

DEFAULTS = {
    'base_url': DEFAULT_BASE_URL,
    'key': '',
    'device_id': '',
    'pull_marks': {},
    'push_ratings': True,
    'push_reviews': True,
    'push_dates': True,
    'push_status': True,
    'push_covers': True,
    'push_tags': False,
    'max_tags_per_book': 0,
    'status_column': '',
    'rating_column': 'rating',
    'review_column': '',
    'started_column': '',
    'finished_column': '',
    'progress_column': '',
}

prefs = JSONConfig('plugins/Seekquel Sync')
prefs.defaults = dict(DEFAULTS)


def is_connected():
    return bool(prefs.get('key') and prefs.get('base_url'))


def forget_connection():
    prefs['key'] = ''
    prefs['device_id'] = ''
    prefs['pull_marks'] = {}
    prefs.commit()


def library_id(db):
    try:
        return db.library_id or ''
    except Exception:
        return ''


def pull_mark(db):
    stored = (prefs.get('pull_marks') or {}).get(library_id(db)) or None

    if not stored:
        return None, None

    at, _, mark_id = stored.partition(MARK_SEPARATOR)

    return at or None, mark_id or None


def set_pull_mark(db, value, mark_id=None):
    marks = dict(prefs.get('pull_marks') or {})
    marks[library_id(db)] = f'{value}{MARK_SEPARATOR}{mark_id}' if mark_id else value
    prefs['pull_marks'] = marks
    prefs.commit()


def _gui():
    from calibre.gui2.ui import get_gui

    return get_gui()


class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.column_boxes = {}

        layout = QVBoxLayout(self)

        connection = QGroupBox('Connection')
        connection_form = QFormLayout(connection)

        self.base_url = QLineEdit(prefs.get('base_url') or DEFAULT_BASE_URL)
        connection_form.addRow('Seekquel address', self.base_url)

        self.connection_state = QLabel(self._connection_label())
        row = QHBoxLayout()
        row.addWidget(self.connection_state, 1)

        self.connect_button = QPushButton('Connect' if not is_connected() else 'Reconnect')
        self.connect_button.clicked.connect(self._connect)
        row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton('Disconnect')
        self.disconnect_button.setEnabled(is_connected())
        self.disconnect_button.clicked.connect(self._disconnect)
        row.addWidget(self.disconnect_button)

        connection_form.addRow('Status', self._wrap(row))
        layout.addWidget(connection)

        columns = QGroupBox('Columns')
        columns_form = QFormLayout(columns)
        columns_form.addRow(QLabel(
            'Choose which of your own columns Seekquel reads from and writes to.\n'
            'A column you leave unset is never read and never written.'
        ))

        for key, label, kinds in COLUMN_FIELDS:
            box = QComboBox()
            self._fill_column_box(box, key, kinds)
            self.column_boxes[key] = box
            columns_form.addRow(label, box)

        layout.addWidget(columns)

        sending = QGroupBox('What to send')
        sending_layout = QVBoxLayout(sending)
        self.push_status = self._checkbox('push_status', 'Reading status', sending_layout)
        self.push_ratings = self._checkbox('push_ratings', 'Ratings', sending_layout)
        self.push_reviews = self._checkbox('push_reviews', 'Reviews', sending_layout)
        self.push_dates = self._checkbox('push_dates', 'Reading dates', sending_layout)
        self.push_covers = self._checkbox(
            'push_covers',
            'Covers, for books Seekquel has none for',
            sending_layout,
        )
        self.push_tags = self._checkbox(
            'push_tags',
            'Tags, as your own tags in Seekquel',
            sending_layout,
        )
        layout.addWidget(sending)

        layout.addStretch(1)

    @property
    def widget(self):
        return self

    def save_settings(self):
        prefs['base_url'] = self.base_url.text().strip().rstrip('/')

        for key in self.column_boxes:
            prefs[key] = self.column_boxes[key].currentData() or ''

        prefs['push_status'] = self.push_status.isChecked()
        prefs['push_ratings'] = self.push_ratings.isChecked()
        prefs['push_reviews'] = self.push_reviews.isChecked()
        prefs['push_dates'] = self.push_dates.isChecked()
        prefs['push_covers'] = self.push_covers.isChecked()
        prefs['push_tags'] = self.push_tags.isChecked()
        prefs.commit()

    def _wrap(self, layout):
        holder = QWidget()
        holder.setLayout(layout)

        return holder

    def _checkbox(self, key, label, layout):
        box = QCheckBox(label)
        box.setChecked(bool(prefs.get(key)))
        layout.addWidget(box)

        return box

    def _connection_label(self):
        if not is_connected():
            return 'Not connected'

        return 'Connected'

    def _fill_column_box(self, box, key, kinds):
        box.addItem('(not used)', '')

        if key == 'rating_column':
            box.addItem("Calibre's own rating", 'rating')

        for lookup, meta in self._custom_columns().items():
            if meta.get('datatype') in kinds:
                box.addItem('{} ({})'.format(meta.get('name') or lookup, lookup), lookup)

        stored = prefs.get(key) or ''
        index = box.findData(stored)
        box.setCurrentIndex(max(index, 0))

    def _custom_columns(self):
        db = getattr(_gui(), 'current_db', None)

        if db is None:
            return {}

        return db.field_metadata.custom_field_metadata()

    def _connect(self):
        from calibre.gui2 import error_dialog

        gui = _gui()

        if gui is None:
            error_dialog(self, 'Seekquel', 'Open this from the Seekquel toolbar button.', show=True)

            return

        prefs['base_url'] = self.base_url.text().strip().rstrip('/')
        prefs.commit()

        from calibre_plugins.seekquel_sync.dialogs.pair import PairDialog

        dialog = PairDialog(gui)

        if dialog.exec() == dialog.DialogCode.Accepted:
            self.connection_state.setText(self._connection_label())
            self.connect_button.setText('Reconnect')
            self.disconnect_button.setEnabled(True)

    def _disconnect(self):
        from calibre.gui2 import question_dialog

        if not question_dialog(self, 'Disconnect', 'Stop syncing this library with Seekquel?'):
            return

        forget_connection()
        self.connection_state.setText(self._connection_label())
        self.connect_button.setText('Connect')
        self.disconnect_button.setEnabled(False)
