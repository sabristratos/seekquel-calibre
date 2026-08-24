# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-24

### Added

- **The toolbar button has the Seekquel mark on it** instead of Calibre's generic plugin
  icon, so it is findable at a glance among the other buttons.
- **A log you can read.** Seekquel, Show the log lists every request the plugin made, what
  came back and how long it took, along with the books a sync skipped and why. It is the
  first thing to look at when a sync does not do what you expected, and the right thing to
  attach to a bug report. It lives beside Calibre's other plugin files as
  `plugins/seekquel-sync.log` and trims itself, so it cannot grow without bound.

### Fixed

- **Settings opens.** Choosing Settings from the Seekquel menu raised an error instead,
  and because the menu is rebuilt each time you open it, the error appeared every time.
  Nothing below Settings in that menu could be reached either.
- **Reviews actually sync.** The Review column could be mapped and the Reviews switch
  could be turned on, and neither did anything: a review was sent, counted and then
  dropped, and none ever came back. Reviews now travel in both directions, converted
  between Calibre's formatting and Seekquel's on the way.
- **Two libraries no longer share one place-marker.** Reading Seekquel's answers back in
  one library moved the marker for all of them, so the next library asked only for what
  had changed since, and quietly skipped everything before that. Each library now keeps
  its own.
- **The tag browser updates after reading Seekquel's answers back.** A status column shown
  in the tag browser kept the old counts until Calibre was restarted.
- **Books sent to Seekquel now carry which library they came from.** They were all
  arriving unlabelled.

## [1.0.1] - 2026-08-24

### Fixed

- **The Seekquel button now appears in the toolbar on its own.** Calibre does not add a
  newly installed plugin to the toolbar, so after installing 1.0.0 and restarting there
  was nothing to click and no indication anything had been installed. The plugin now puts
  itself there the first time it runs. It does this once: if you move it or take it off
  the toolbar, it stays as you left it.

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

[1.1.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.1.0
[1.0.1]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.0.1
[1.0.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.0.0
