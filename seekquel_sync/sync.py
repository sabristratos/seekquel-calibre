from calibre_plugins.seekquel_sync import __version__
from calibre_plugins.seekquel_sync.api import (
    SeekquelApi,
    SeekquelError,
    SeekquelUnreachable,
)
from calibre_plugins.seekquel_sync.columns import (
    column_name,
    describe,
    plan_book,
    read_book,
    write_book,
)
from calibre_plugins.seekquel_sync.config import library_id, prefs, pull_mark, set_pull_mark
from calibre_plugins.seekquel_sync.log import note

CHUNK_SIZE = 100
MAX_COVERS_PER_RUN = 25
PREVIEW_SAMPLE = 40

NEEDS_A_LOOK = ('unmatched', 'unidentified')

STATE_FIELDS = ('status', 'rating', 'review', 'started_at', 'finished_at', 'progress_percent')


def api():
    return SeekquelApi(prefs.get('base_url'), prefs.get('key'))


def push_library(db, book_ids, notifications=None, log=None, abort=None):
    note(f'Push started: {len(book_ids)} books')
    client = api()
    chunk_size = _chunk_size(client, log)

    accepted = 0
    skipped = 0
    total = len(book_ids)

    for index in range(0, total, chunk_size):
        if abort is not None and abort.is_set():
            break

        payload = []

        for book_id in book_ids[index:index + chunk_size]:
            book = read_book(db, book_id)

            if not book.get('uuid'):
                skipped += 1

                continue

            payload.append(book)

        if not payload:
            continue

        result = client.push_library(payload, library_id(db) or None, prefs.get('push_tags'))
        taken = int(result.get('books_accepted') or 0)
        accepted += taken
        _note(log, f'Sent {len(payload)} books, Seekquel took {taken}')

        _report(notifications, min(index + chunk_size, total) / max(total, 1),
                f'Sent {min(index + chunk_size, total)} of {total} books')

    note(f'Push finished: accepted {accepted}, skipped {skipped}, of {total}')

    return {'accepted': accepted, 'skipped': skipped, 'total': total}


def pull_library(db, notifications=None, log=None, abort=None):
    since, since_id = pull_mark(db)
    note(f"Pull started, since {since or 'the beginning'}")
    client = api()

    updated = 0
    unmatched = 0
    missing = 0
    seen = 0
    written = []
    wanted = []
    by_uuid = _uuid_index(db)

    for rows, synced_at, synced_id, has_more in _pages(client, since, since_id, abort):
        for row in rows:
            book_id = by_uuid.get(row.get('uuid'))

            if book_id is None:
                missing += 1

                continue

            if row.get('match_status') in NEEDS_A_LOOK:
                unmatched += 1

            if write_book(db, book_id, row):
                updated += 1
                written.append(book_id)

            if row.get('wants_cover'):
                wanted.append((row.get('uuid'), book_id))

        if synced_at:
            set_pull_mark(db, synced_at, synced_id)

        seen += len(rows)
        _note(log, f'Read {len(rows)} books back from Seekquel')
        _report(notifications, 0.5 if has_more else 1.0, f'Read {seen} books back from Seekquel')

    covers = _send_covers(db, client, wanted, log, abort)

    _note(log, f'Updated {updated}, waiting on you {unmatched}, not in this library {missing}')

    return {
        'updated': updated,
        'unmatched': unmatched,
        'missing': missing,
        'book_ids': written,
        'covers': covers,
    }


def preview_sync(db, book_ids, notifications=None, log=None, abort=None):
    note(f'Preview started: {len(book_ids)} books in scope')
    _report(notifications, 0.2, 'Reading your library')
    sending = _sending_preview(db, book_ids, abort)

    _report(notifications, 0.6, 'Asking Seekquel what would come back')
    receiving = _receiving_preview(db, api(), abort)

    _note(log, 'Preview only. Nothing was sent and nothing was written.')

    return {'sending': sending, 'receiving': receiving}


def report_device(gui, log=None):
    try:
        answer = api().report_device(_device_name(gui), 'calibre', __version__)
    except (SeekquelError, SeekquelUnreachable) as error:
        if log is not None:
            log(f'Could not report this install: {error}')

        return None

    return answer


def _pages(client, since, since_id, abort):
    while True:
        if abort is not None and abort.is_set():
            return

        result = client.pull_library(since, since_id)
        rows = result.get('data') or []
        synced_at = result.get('synced_at')
        synced_id = result.get('synced_id')
        has_more = bool(result.get('has_more')) and bool(rows) and bool(synced_at)

        yield rows, synced_at, synced_id, has_more

        if not has_more:
            return

        since = synced_at
        since_id = synced_id


def _sending_preview(db, book_ids, abort=None):
    fields = {}
    skipped = 0
    unidentified = 0
    sending = 0

    for book_id in book_ids:
        if abort is not None and abort.is_set():
            break

        book = read_book(db, book_id)

        if not book.get('uuid'):
            skipped += 1

            continue

        sending += 1

        if not book.get('isbn') and not book.get('identifiers'):
            unidentified += 1

        state = book.get('state') or {}

        for field in STATE_FIELDS:
            if state.get(field) is not None:
                fields[field] = fields.get(field, 0) + 1

        if book.get('tags'):
            fields['tags'] = fields.get('tags', 0) + 1

    return {
        'sending': sending,
        'skipped': skipped,
        'unidentified': unidentified,
        'fields': fields,
    }


def _receiving_preview(db, client, abort=None):
    since, since_id = pull_mark(db)
    by_uuid = _uuid_index(db)

    seen = 0
    missing = 0
    unmatched = 0
    changed = 0
    covers = 0
    columns = {}
    sample = []

    for rows, _synced_at, _synced_id, _has_more in _pages(client, since, since_id, abort):
        for row in rows:
            book_id = by_uuid.get(row.get('uuid'))

            if book_id is None:
                missing += 1

                continue

            if row.get('match_status') in NEEDS_A_LOOK:
                unmatched += 1

            if row.get('wants_cover') and prefs.get('push_covers'):
                covers += 1

            planned = plan_book(db, book_id, row)

            if not planned:
                continue

            changed += 1

            for column, value in planned.items():
                name = column_name(db, column)
                columns[name] = columns.get(name, 0) + 1

                if len(sample) < PREVIEW_SAMPLE:
                    title = row.get('title') or 'Untitled'
                    sample.append(f'{title}: {describe(db, book_id, column, value)}')

        seen += len(rows)

    return {
        'seen': seen,
        'changed': changed,
        'unmatched': unmatched,
        'missing': missing,
        'covers': min(covers, MAX_COVERS_PER_RUN),
        'columns': columns,
        'sample': sample,
    }


def _send_covers(db, client, wanted, log=None, abort=None):
    if not wanted or not prefs.get('push_covers'):
        return 0

    sent = 0

    for uuid, book_id in wanted[:MAX_COVERS_PER_RUN]:
        if abort is not None and abort.is_set():
            break

        if not uuid:
            continue

        content = _cover_bytes(db, book_id)

        if content is None:
            continue

        try:
            client.upload_cover(uuid, f'{book_id}.jpg', content)
            sent += 1
        except (SeekquelError, SeekquelUnreachable) as error:
            _note(log, f'Could not send a cover: {error}')

            break

    if sent:
        _note(log, f'Sent {sent} covers')

    return sent


def _cover_bytes(db, book_id):
    try:
        return db.cover(book_id) or None
    except Exception:
        return None


def _chunk_size(client, log=None):
    try:
        answer = client.report_device(None, 'calibre', __version__)
        published = int(answer.get('max_books_per_push') or 0)
        _remember_tag_ceiling(answer)
    except Exception as error:
        _note(log, f'Could not ask Seekquel how many books it takes at once: {error}')
        published = 0

    return published if published > 0 else CHUNK_SIZE


def _remember_tag_ceiling(answer):
    published = int(answer.get('max_tags_per_book') or 0)

    if published > 0 and published != prefs.get('max_tags_per_book'):
        prefs['max_tags_per_book'] = published
        prefs.commit()


def _uuid_index(db):
    index = {}

    for book_id in db.all_book_ids():
        uuid = db.field_for('uuid', book_id)

        if uuid:
            index[uuid] = book_id

    return index


def _device_name(gui):
    try:
        return gui.current_db.library_path.rstrip('/\\').rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    except Exception:
        return 'Calibre'


def _note(log, message):
    note(message)

    if log is not None:
        log(message)


def _report(notifications, fraction, message):
    if notifications is None:
        return

    notifications.put((max(0.0, min(1.0, fraction)), message))
