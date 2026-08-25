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
    QTabWidget,
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

SCOPE_ALL = 'all'
SCOPE_VIRTUAL_LIBRARY = 'virtual_library'
SCOPE_SAVED_SEARCH = 'saved_search'
SCOPE_SEARCH = 'search'

SCOPE_SEPARATOR = ':'
LABEL_SEPARATOR = ','
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
    'send_scope': SCOPE_ALL,
    'send_scope_value': '',
    'status_labels': {},
    'status_column': '',
    'rating_column': '',
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
        self.label_edits = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        tabs.addTab(self._connection_tab(), 'Connection')
        tabs.addTab(self._columns_tab(), 'Columns')
        tabs.addTab(self._sending_tab(), 'What to send')
        layout.addWidget(tabs)

    @property
    def widget(self):
        return self

    def save_settings(self):
        prefs['base_url'] = self.base_url.text().strip().rstrip('/')

        for key in self.column_boxes:
            prefs[key] = self.column_boxes[key].currentData() or ''

        kind, _, value = (self.scope_box.currentData() or '').partition(SCOPE_SEPARATOR)

        if kind == SCOPE_SEARCH:
            value = self.scope_search.text().strip()

        prefs['send_scope'] = kind or SCOPE_ALL
        prefs['send_scope_value'] = value

        prefs['status_labels'] = {
            status: self.label_edits[status].text().strip()
            for status in self.label_edits
            if self.label_edits[status].text().strip()
        }

        prefs['push_status'] = self.push_status.isChecked()
        prefs['push_ratings'] = self.push_ratings.isChecked()
        prefs['push_reviews'] = self.push_reviews.isChecked()
        prefs['push_dates'] = self.push_dates.isChecked()
        prefs['push_covers'] = self.push_covers.isChecked()
        prefs['push_tags'] = self.push_tags.isChecked()
        prefs.commit()

    def _connection_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

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
        layout.addStretch(1)

        return page

    def _columns_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

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

        labels = QGroupBox('Status labels')
        labels_form = QFormLayout(labels)
        labels_form.addRow(QLabel(
            'What your own status column calls each one. Leave a row blank to use ours.\n'
            'Separate several with commas; the first is the one Seekquel writes back.'
        ))

        stored = prefs.get('status_labels') or {}

        for status, label in STATUS_VALUES:
            edit = QLineEdit(str(stored.get(status) or ''))
            edit.setPlaceholderText(label)
            self.label_edits[status] = edit
            labels_form.addRow(label, edit)

        layout.addWidget(labels)
        layout.addStretch(1)

        return page

    def _sending_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        books = QGroupBox('Books to send')
        books_form = QFormLayout(books)
        books_form.addRow(QLabel(
            'A library holds manuals and papers as well as books. Point Seekquel at a\n'
            'virtual library or a saved search and it sends only those.\n'
            'Sending books you have selected ignores this and sends exactly those.'
        ))

        self.scope_box = QComboBox()
        self._fill_scope_box()
        self.scope_box.currentIndexChanged.connect(self._scope_changed)
        books_form.addRow('Send', self.scope_box)

        self.scope_search = QLineEdit(self._stored_search())
        self.scope_search.setPlaceholderText('tags:"=fiction" not tags:"=manual"')
        books_form.addRow('Search', self.scope_search)

        layout.addWidget(books)

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

        self._scope_changed()

        return page

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

    def _fill_scope_box(self):
        from calibre_plugins.seekquel_sync.scope import saved_searches, virtual_libraries

        db = self._db()
        self.scope_box.addItem('All the books in this library', SCOPE_ALL + SCOPE_SEPARATOR)

        if db is not None:
            for name in sorted(virtual_libraries(db)):
                self.scope_box.addItem(
                    f'Virtual library: {name}',
                    SCOPE_VIRTUAL_LIBRARY + SCOPE_SEPARATOR + name,
                )

            for name in sorted(saved_searches(db)):
                self.scope_box.addItem(
                    f'Saved search: {name}',
                    SCOPE_SAVED_SEARCH + SCOPE_SEPARATOR + name,
                )

        self.scope_box.addItem('A search of my own', SCOPE_SEARCH + SCOPE_SEPARATOR)
        self._select_stored_scope()

    def _select_stored_scope(self):
        kind = prefs.get('send_scope') or SCOPE_ALL
        value = (prefs.get('send_scope_value') or '').strip()
        stored = kind + SCOPE_SEPARATOR + ('' if kind == SCOPE_SEARCH else value)
        index = self.scope_box.findData(stored)

        if index < 0 and kind not in (SCOPE_ALL, SCOPE_SEARCH) and value:
            self.scope_box.addItem(f'{value} (no longer in this library)', stored)
            index = self.scope_box.count() - 1

        self.scope_box.setCurrentIndex(max(index, 0))

    def _stored_search(self):
        if (prefs.get('send_scope') or SCOPE_ALL) != SCOPE_SEARCH:
            return ''

        return prefs.get('send_scope_value') or ''

    def _scope_changed(self):
        kind, _, _value = (self.scope_box.currentData() or '').partition(SCOPE_SEPARATOR)
        self.scope_search.setEnabled(kind == SCOPE_SEARCH)

    def _db(self):
        gui = _gui()
        database = getattr(gui, 'current_db', None)

        return None if database is None else database.new_api

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
