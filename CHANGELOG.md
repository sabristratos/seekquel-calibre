# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-24

First release.

### Added

- **Connect a Calibre library to Seekquel without pasting anything.** Click Start, and
  Calibre shows eight characters that you enter in Seekquel under Settings, Integrations,
  Calibre. Calibre collects a key of its own a moment later. That key can only sync, you
  never have to handle it, and you can revoke it from the same screen that lists your
  other devices.
- **Send your library, or just the books you have selected.** Both run in the background,
  so Calibre stays usable and you can stop a long sync part way through.
- **Bring Seekquel's answers back into your own columns.** Status, rating, review, the
  dates you started and finished, and how far through you are. Every one of them is
  optional: you choose which of your columns holds what, and a column you leave unset is
  never read and never written.
- **Status labels are read as you already write them.** A column holding `Read`,
  `Currently reading`, `TBR`, `On hold`, `DNF` or `Finished` works without renaming
  anything first.
- **Each matched book gains a `seekquel` identifier**, so View this book on Seekquel opens
  its page, and you can build a Calibre column that shows at a glance which books are
  linked.
- **Books Seekquel could not place are listed for you** under Settings, Integrations,
  Calibre in the app, rather than guessed at. You can point one at the right book, say the
  catalogue does not have it, or set it aside if it is a manual rather than a book.

### Notes on what it deliberately does not do

- **Syncing never clears a value.** A field Seekquel does not hold leaves your Calibre
  column exactly as you typed it. Most libraries map two or three columns out of six, so
  reading an empty answer as a deletion would empty a library on the first sync.
- **A book you have marked read is never un-marked from Calibre.** Marking a book read in
  Seekquel posts to your feed, counts towards a goal and can earn a badge, and a status
  column last touched two years ago is not grounds for taking that back.
- **Reading progress moves your place without counting as a day's reading.** Calibre
  cannot know when you read those pages, and crediting them to today would bill an
  afternoon for a book you finished months ago.

[1.0.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.0.0
