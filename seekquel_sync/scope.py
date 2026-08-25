from calibre_plugins.seekquel_sync.config import (
    SCOPE_ALL,
    SCOPE_SAVED_SEARCH,
    SCOPE_SEARCH,
    SCOPE_VIRTUAL_LIBRARY,
    prefs,
)

VIRTUAL_LIBRARIES_PREF = 'virtual_libraries'
SAVED_SEARCHES_PREF = 'saved_searches'

OWN_SEARCH_NAME = 'a search of my own'


class ScopeUnavailable(Exception):
    pass


def virtual_libraries(db):
    return _named(db, VIRTUAL_LIBRARIES_PREF)


def saved_searches(db):
    return _named(db, SAVED_SEARCHES_PREF)


def scope_name():
    kind, value = current_scope()

    if kind == SCOPE_ALL or not value:
        return None

    if kind == SCOPE_SEARCH:
        return OWN_SEARCH_NAME

    return value


def current_scope():
    kind = prefs.get('send_scope') or SCOPE_ALL
    value = (prefs.get('send_scope_value') or '').strip()

    return kind, value


def books_in_scope(db):
    kind, value = current_scope()

    if kind == SCOPE_ALL or not value:
        return sorted(db.all_book_ids())

    query = _query(db, kind, value)

    try:
        matched = db.search(query)
    except Exception as error:
        raise ScopeUnavailable(
            f'Calibre could not run the search behind "{scope_name()}": {error}'
        ) from error

    return sorted(matched)


def _query(db, kind, value):
    if kind == SCOPE_VIRTUAL_LIBRARY:
        return _stored(virtual_libraries(db), value, 'virtual library')

    if kind == SCOPE_SAVED_SEARCH:
        return _stored(saved_searches(db), value, 'saved search')

    return value


def _stored(mapping, name, description):
    query = _lookup(mapping, name)

    if query is None:
        raise ScopeUnavailable(
            f'This library no longer has a {description} called "{name}".'
        )

    return query


def _lookup(mapping, name):
    wanted = name.strip().lower()

    for key, value in mapping.items():
        if str(key).strip().lower() == wanted:
            return value

    return None


def _named(db, key):
    try:
        stored = db.pref(key)
    except Exception:
        return {}

    return dict(stored) if isinstance(stored, dict) else {}
