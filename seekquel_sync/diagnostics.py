"""What this install last managed, so Seekquel can see it without being told.

Every KOReader device reports its slowest call and whether its last sync worked. Measured
on 2026-09-08, all 17 connected Calibre installs reported nothing at all, so when the two
largest libraries stopped syncing after a single push, and when a stale root store left
whole installs unable to verify the certificate, there was nothing on the server that said
so. Both had to be found by reading raw logs and by a reader saying something.

The last sync outcome is kept in the plugin's own preferences rather than in memory,
because the failure worth reporting is usually the one that made the reader close Calibre.
It is sent on the next attempt: `_chunk_size` asks the server how many books it takes at
once at the start of every push, and that call carries whatever this holds.

The slowest call is per session and deliberately not persisted. It answers "is the server
slow for this reader today", which a week-old number does not.
"""

import time

from calibre_plugins.seekquel_sync.config import prefs

LAST_SYNC_AT = 'last_sync_at'
LAST_SYNC_OK = 'last_sync_ok'
LAST_ERROR = 'last_error'
BOOKS_SENT = 'books_sent'

MAX_ERROR_LENGTH = 200

_slowest_call = None
_slowest_seconds = 0


def record_call(method, path, seconds):
    """Remember the slowest call of this session."""
    global _slowest_call, _slowest_seconds

    if seconds <= _slowest_seconds:
        return

    _slowest_seconds = seconds
    _slowest_call = f'{method} {path}'


def record_sync(ok, books_sent=0, error=None):
    """Remember how the last sync went, across restarts."""
    prefs[LAST_SYNC_AT] = int(time.time())
    prefs[LAST_SYNC_OK] = bool(ok)
    prefs[BOOKS_SENT] = int(books_sent or 0)
    prefs[LAST_ERROR] = _trimmed(error)
    prefs.commit()


def snapshot():
    """What to send with the next device report, or None when there is nothing to say.

    Returns only the fields that carry a value. A key with nothing behind it reads on the
    server as a measurement that came back empty, which is a different claim from one that
    was never taken.
    """
    reported = {}

    if prefs.get(LAST_SYNC_AT):
        reported[LAST_SYNC_AT] = int(prefs.get(LAST_SYNC_AT))
        reported[LAST_SYNC_OK] = bool(prefs.get(LAST_SYNC_OK))
        reported[BOOKS_SENT] = int(prefs.get(BOOKS_SENT) or 0)

    error = prefs.get(LAST_ERROR)

    if error:
        reported[LAST_ERROR] = _trimmed(error)

    if _slowest_call is not None:
        reported['slowest_call'] = _slowest_call
        reported['slowest_seconds'] = int(_slowest_seconds)

    return reported or None


def _trimmed(error):
    if not error:
        return ''

    return str(error)[:MAX_ERROR_LENGTH]
