from calibre.constants import numeric_version

RECORDS_POSITION_SINCE = (9, 5, 0)
PERCENT = 100
MOST_RECENT = 'epoch'


def records_position():
    return tuple(numeric_version) >= RECORDS_POSITION_SINCE


def viewer_progress(db, book_id):
    position = _latest_position(db, book_id)

    if position is None:
        return None

    try:
        percent = round(float(position.get('pos_frac')) * PERCENT, 2)
    except (TypeError, ValueError):
        return None

    return percent if 0 < percent <= PERCENT else None


def read_in_viewer_since(db, book_ids, since):
    if not records_position():
        return []

    epoch = since.timestamp()

    return [book_id for book_id in book_ids if _read_after(_latest_position(db, book_id), epoch)]


def _read_after(position, epoch):
    if position is None:
        return False

    try:
        return float(position.get('epoch') or 0) >= epoch
    except (TypeError, ValueError):
        return False


def _latest_position(db, book_id):
    if not records_position():
        return None

    from calibre.db.constants import EBOOK_VIEWER_USER

    records = db.get_last_read_positions(book_id, user=EBOOK_VIEWER_USER, order_by=MOST_RECENT, limit=1)

    return records[0] if records else None
