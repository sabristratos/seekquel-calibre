# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-08-25

### Added

- **Choose which books get sent.** A library holds manuals, rulebooks and conference papers
  alongside novels, and until now all of it went, leaving you to set each one aside in the
  app afterwards. Under Settings, What to send, point Seekquel at one of your virtual
  libraries or saved searches, or type a search of your own, and it sends only those. The
  menu says which set it is sending so you cannot forget you set it. Sending books you have
  selected ignores this and sends exactly what you picked.
- **A search that no longer exists stops the sync rather than widening it.** If you delete
  the virtual library Seekquel was pointed at, the next send says so and does nothing.
  Falling back to the whole library would send the manuals you set it up to avoid.
- **Tell Seekquel what your own status column says.** Under Settings, Columns, there is now
  a row per status where you write the words you actually use. It reads them and writes them
  back, so a column holding "Leyendo" stays a column holding "Leyendo". Separate several
  with commas and the first is the one Seekquel writes. Leave a row blank and the built-in
  labels work as before.
- **See what a sync would do before it does it.** Seekquel, Preview a sync, reads your
  library and asks Seekquel what it would send back, then tells you how many books would
  change, which columns they are, and shows the first forty as "was, becomes". Nothing is
  sent and nothing is written. It leaves the place-marker where it was, so the real sync
  afterwards still brings everything.

### Changed

- **Nothing is mapped until you map it, the rating included.** The rating was the one field
  set up for you, pointed at Calibre's own star column before you had said so, which meant a
  first sync could write a Seekquel rating over one you typed in a column you never chose.
  Every field is now yours to pick, which is what the plugin claimed all along. If you were
  relying on it, open Settings, Columns, and choose Calibre's own rating.
- **Connecting takes you into Settings** rather than telling you to go there, since there is
  nothing to sync until you have chosen your columns.
- Settings is now three tabs, Connection, Columns and What to send, because it had grown
  taller than some screens.

## [1.3.0] - 2026-08-24

### Added

- **Your Calibre tags can become your tags in Seekquel.** Switch on "Tags, as your own tags
  in Seekquel" under What to send, and the tags on each book come across as tags on your
  copy in the app. It is off to begin with, because a Calibre tag is a personal filing
  system and a library routinely carries "kindle", "borrowed" or "to-read" among the real
  ones, and nobody's tag list should fill with those without being asked.
- Tags are added, never removed. A tag you add in the app stays where it is however many
  times the library is sent again.

### Changed

- **A heavily-tagged book no longer loses its tail.** The plugin used to cut every book to
  forty tags; the ceiling is far higher now, and it reads the real one from the server so
  an already-installed copy learns when it moves.

## [1.2.3] - 2026-08-24

### Fixed

- **Sending your library no longer wedges Calibre.** The window that reports the result was
  being built by the background task itself rather than by Calibre, which is not something
  Qt allows: the window came up blank, the rest of Calibre stopped drawing, and the job
  never finished, so the count in the corner stayed at one forever. Reading Seekquel's
  answers back had the same fault. Both now hand the result to Calibre and let it put the
  window up.
- **Reading your library back no longer skips books.** Seekquel remembers where the last
  read-back stopped by the time it happened, and it records times to the second, so a
  library sent in one go leaves hundreds of books sharing a single second. Where a page of
  results ended in the middle of one of those groups, the rest of it was never asked for
  again and those books simply never came back. The place is now remembered as a book
  rather than as a time.

## [1.2.2] - 2026-08-24

### Fixed

- **Calibre no longer freezes while connecting.** Every step of the connect exchange ran
  where Calibre draws, so the window stopped repainting for as long as the server took to
  answer. Measured against a local server that answers in two seconds, against a check that
  repeats every three, the window was frozen for most of the exchange, and a server that
  never answered would have held it for thirty seconds. Windows records that as the program
  hanging and it reads as a crash. The requests happen out of the way now: measured over
  the same exchange the window pauses for less than a tenth of a second.

## [1.2.1] - 2026-08-24

### Fixed

- **Calibre could crash on a dialog after installing 1.1.0 or 1.2.0.** The plugin was
  loading part of Calibre's own main window while that window was still being built, which
  leaves it half-finished and can take the program down later, in screens that have nothing
  to do with Seekquel. It loads that piece only when it actually needs it now. Fully quit
  and reopen Calibre after updating: a plugin swapped underneath a running Calibre is a
  second, separate way to see this.

## [1.2.0] - 2026-08-24

### Added

- **Seekquel now gets the rest of what Calibre knows about a book**: the description, the
  publisher, the publication date, the language and your tags. A book Seekquel does not
  hold and that you keep as your own now arrives as a real record rather than a bare title
  and author.
- **Covers, for books Seekquel has none for.** It asks for the ones it is missing and the
  plugin sends those and no others, up to twenty five per sync, so a large library does not
  spend ten minutes uploading. A cover for a book only you have is used straight away; one
  for a catalogue book that has no cover at all is offered as a suggestion and waits for a
  reviewer, because a catalogue cover is seen by everybody. A book that already has one is
  left alone. There is a switch for it under What to send.
- **Look for it online.** A book Seekquel could not place now has a Find it online button
  in the app, under Settings, Integrations, Calibre. It searches the book sources, shows
  you what came back, and adds nothing until you pick one.

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

[1.4.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.4.0
[1.3.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.3.0
[1.2.3]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.2.3
[1.2.2]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.2.2
[1.2.1]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.2.1
[1.2.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.2.0
[1.1.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.1.0
[1.0.1]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.0.1
[1.0.0]: https://github.com/sabristratos/seekquel-calibre/releases/tag/v1.0.0
