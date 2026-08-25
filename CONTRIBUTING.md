# Contributing

Bug reports from real libraries are the most valuable thing anyone can send right now.
The plugin has been exercised end to end against a running server, but only against small
test libraries, so anything that goes wrong at a few thousand books is very much worth
reporting.

## Reporting a bug

Open an issue and include:

- Your Calibre version, from **Preferences > About**, and your operating system.
- Roughly how many books are in the library.
- What you expected and what happened instead.
- If a sync failed, the job details. Open Calibre's job list at the bottom right,
  double-click the failed job, and paste what it says.

Redact your device key if it appears anywhere. It is 16 characters and looks like
`K9QPF26MXABDRFWR`.

## Layout

```
seekquel_sync/         the plugin itself
  __init__.py          the class Calibre loads, and the version
  action.py            the toolbar button, its menu, and the background jobs
  api.py               every HTTP call
  columns.py           reading the reader's columns and writing back into them
  config.py            stored settings and the preferences dialog
  scope.py             which books a sync sends
  sync.py              the two directions a library moves in
  dialogs/pair.py      the pairing dialog
build.py               writes dist/Seekquel Sync.zip
scripts/check_imports.py  refuses module-scope imports of Calibre internals
```

## Building and installing

```bash
python build.py
calibre-customize -a "dist/Seekquel Sync.zip"
```

Restart Calibre afterwards. `calibre-customize` is installed alongside Calibre; on Windows
it lives in `C:\Program Files\Calibre2`.

**The zip's root is the contents of `seekquel_sync/`, never the folder itself.** Calibre
resolves a plugin's modules through the import name in
`plugin-import-name-seekquel_sync.txt` at the zip root, so an archive built one level up
installs as a plugin whose every import fails at startup. `build.py` gets this right; a
hand-made zip usually does not.

## Style

- Four spaces, no tabs. LF endings.
- No comments and no docstrings. Names carry the meaning, and anything that genuinely
  needs explaining belongs in the README where a user will find it.
- Calibre and Qt are imported inside the function that needs them wherever a module is
  loaded at startup, so a menu rebuild does not drag in the whole GUI.
- Nothing that touches the network runs on the GUI thread. Long work goes through
  `ThreadedJob` so Calibre stays usable and the reader can stop it.
- A failure is reported to the reader in words they can act on. "Could not reach
  Seekquel" and "that key is no longer valid" are different problems and must never be
  reported as the same one.
- Never clear a value the reader typed. A field the server does not answer with is left
  alone rather than blanked.

Run `ruff check .` and `python scripts/check_imports.py` before opening a pull request.
CI runs both, and byte-compiles every module. The second one exists because 1.1.0 imported
`calibre.gui2.ui` at module scope, which leaves that module half-built and crashes Calibre
later, in a screen with nothing to do with this plugin.

## Testing

There is no unit-test harness, and that is deliberate rather than an omission: almost
every line of this plugin is a call into Calibre's database API, Qt, or the Seekquel
server, so a mocked test would mostly assert that the mocks were written to match the
code. What is worth doing instead is running it against the real thing.

`calibre-debug -e <script>` runs a Python file inside Calibre's own interpreter, with
`calibre_plugins.seekquel_sync` importable and the full Calibre API available. That is
enough to drive a whole sync headlessly:

```python
from calibre.library import db as open_library

from calibre_plugins.seekquel_sync.config import prefs
from calibre_plugins.seekquel_sync.sync import push_library, pull_library

prefs['base_url'] = 'http://localhost:8000/calibre'
prefs['key'] = 'YOUR-DEVICE-KEY'
prefs.commit()

database = open_library('/path/to/a/scratch/library').new_api

print(push_library(database, sorted(database.all_book_ids())))
print(pull_library(database))
```

Use a scratch library, never your own, and point `CALIBRE_CONFIG_DIRECTORY` somewhere
scratch as well, or the script writes over the settings and the device key of the Calibre
you actually use.

`calibredb --with-library <path> add -e -t Title -a Author -I "isbn:9780441013593"` builds
one in a few seconds, and `calibredb add_custom_column` adds the columns to map. Both
refuse to run while Calibre is open; inside `calibre-debug` the same work is
`database.add_books`, `database.create_custom_column`, and `database.set_pref` for the
`virtual_libraries` and `saved_searches` a scope test needs. Keep the library path short:
Calibre refuses one longer than 89 characters.

The Qt layer can be driven the same way by constructing `Application([])` first, then the
dialog or widget you want to exercise. Doing that is how the pairing dialog and the
settings widget were checked without a human clicking through them.

## What to expect from a review

A change that alters what is written into somebody's library will be read closely, and
the question asked of it is always the same one: what happens to a reader who has typed
something into that column already.
