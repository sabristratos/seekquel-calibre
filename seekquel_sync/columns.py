from calibre.utils.date import parse_date, utcnow
from calibre_plugins.seekquel_sync.config import STATUS_VALUES, prefs

CALIBRE_RATING_SCALE = 2.0

STATUS_LABELS = dict(STATUS_VALUES)
STATUS_BY_LABEL = {label.lower(): value for value, label in STATUS_VALUES}
STATUS_ALIASES = {
    'to read': 'want_to_read',
    'tbr': 'want_to_read',
    'currently reading': 'reading',
    'in progress': 'reading',
    'on hold': 'paused',
    'finished': 'read',
    'complete': 'read',
    'completed': 'read',
    'dnf': 'did_not_finish',
    'abandoned': 'did_not_finish',
}


def read_book(db, book_id):
    identifiers = db.field_for('identifiers', book_id) or {}

    return {
        'uuid': db.field_for('uuid', book_id),
        'id': book_id,
        'title': db.field_for('title', book_id),
        'authors': ' & '.join(db.field_for('authors', book_id) or []),
        'isbn': identifiers.get('isbn'),
        'identifiers': {k: v for k, v in identifiers.items() if isinstance(v, str)},
        'series': db.field_for('series', book_id),
        'series_index': db.field_for('series_index', book_id),
        'page_count': None,
        'state': read_state(db, book_id),
    }


def read_state(db, book_id):
    state = {}

    if prefs.get('push_status'):
        status = _normalize_status(_column_value(db, book_id, prefs.get('status_column')))

        if status:
            state['status'] = status

    if prefs.get('push_ratings'):
        rating = _read_rating(db, book_id)

        if rating is not None:
            state['rating'] = rating

    if prefs.get('push_reviews'):
        review = _column_value(db, book_id, prefs.get('review_column'))

        if isinstance(review, str) and review.strip():
            state['review'] = review.strip()

    if prefs.get('push_dates'):
        started = _read_date(db, book_id, prefs.get('started_column'))
        finished = _read_date(db, book_id, prefs.get('finished_column'))

        if started:
            state['started_at'] = started

        if finished:
            state['finished_at'] = finished

    progress = _column_value(db, book_id, prefs.get('progress_column'))

    if isinstance(progress, (int, float)) and 0 < progress <= 100:
        state['progress_percent'] = float(progress)

    return state


def write_book(db, book_id, remote):
    changes = {}

    status = remote.get('status')

    if status and prefs.get('status_column'):
        changes[prefs['status_column']] = STATUS_LABELS.get(status, status)

    rating = remote.get('rating')

    if rating is not None and prefs.get('rating_column'):
        changes[prefs['rating_column']] = round(float(rating) * CALIBRE_RATING_SCALE)

    started = _parse_iso_date(remote.get('started_at'))

    if started and prefs.get('started_column'):
        changes[prefs['started_column']] = started

    finished = _parse_iso_date(remote.get('finished_at'))

    if finished and prefs.get('finished_column'):
        changes[prefs['finished_column']] = finished

    progress = remote.get('progress_percent')

    if progress is not None and prefs.get('progress_column'):
        changes[prefs['progress_column']] = _fit_progress(db, prefs['progress_column'], progress)

    written = set()

    for column, value in changes.items():
        if _write_column(db, book_id, column, value):
            written.add(column)

    if _write_identifier(db, book_id, remote.get('url')):
        written.add('identifiers')

    return written


def _write_column(db, book_id, column, value):
    if _column_value(db, book_id, column) == value:
        return False

    try:
        db.set_field(column, {book_id: value})
    except Exception:
        return False

    return True


def _write_identifier(db, book_id, url):
    if not url:
        return False

    slug = url.rstrip('/').rsplit('/', 1)[-1]

    if not slug:
        return False

    identifiers = dict(db.field_for('identifiers', book_id) or {})

    if identifiers.get('seekquel') == slug:
        return False

    identifiers['seekquel'] = slug

    try:
        db.set_field('identifiers', {book_id: identifiers})
    except Exception:
        return False

    return True


def _column_value(db, book_id, column):
    if not column:
        return None

    try:
        return db.field_for(column, book_id)
    except Exception:
        return None


def _read_rating(db, book_id):
    column = prefs.get('rating_column')
    value = _column_value(db, book_id, column)

    if not isinstance(value, (int, float)) or value <= 0:
        return None

    return round(float(value) / CALIBRE_RATING_SCALE, 1)


def _read_date(db, book_id, column):
    value = _column_value(db, book_id, column)

    if value is None:
        return None

    try:
        if isinstance(value, str):
            value = parse_date(value)

        if value.year <= 1:
            return None

        return value.strftime('%Y-%m-%d')
    except Exception:
        return None


def _parse_iso_date(value):
    if not value:
        return None

    try:
        return parse_date(value + 'T12:00:00+00:00')
    except Exception:
        return None


def _fit_progress(db, column, progress):
    try:
        datatype = db.field_metadata.custom_field_metadata().get(column, {}).get('datatype')
    except Exception:
        datatype = None

    return round(progress) if datatype == 'int' else round(float(progress), 2)


def _normalize_status(value):
    if not isinstance(value, str):
        return None

    candidate = value.strip().lower()

    if not candidate:
        return None

    if candidate in STATUS_LABELS:
        return candidate

    if candidate in STATUS_BY_LABEL:
        return STATUS_BY_LABEL[candidate]

    return STATUS_ALIASES.get(candidate)


def now_iso():
    return utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
