# Seekquel for Calibre

Connects a Calibre library to [Seekquel](https://seekquel.app). Your shelves, ratings,
reviews and reading dates travel in both directions, so the library you already keep on
your computer and the one you carry on your phone stay the same library.

Works with Calibre 6 and later on Windows, macOS and Linux.

## Install

1. Download the zip from the [latest release](https://github.com/sabristratos/seekquel-calibre/releases/latest).
2. In Calibre, open **Preferences > Plugins > Load plugin from file** and pick it.
3. Restart Calibre.

A **Seekquel** button appears in the toolbar. If you ever remove it, Calibre puts it back
under **Preferences > Toolbars & menus > The main toolbar**; the plugin will not add it
again by itself.

You need a Seekquel account. The plugin is useless without one.

## Connect

1. Click **Seekquel > Connect to Seekquel**, then **Start**. Eight characters appear.
2. In Seekquel, open **Settings > Integrations > Calibre** and enter them.

Calibre picks up its key a second or two later and the dialog closes itself.

Nothing is pasted. The usual way a desktop app connects to a service is to ask you for an
account API token, which then sits in a plain configuration file for as long as the app is
installed. Instead, Calibre is handed a key that can only sync, that you never see, and
that you can revoke from the same screen that lists your other devices.

## Choose your columns

Open **Seekquel > Settings**. Every field is optional, and a column you leave unset is
never read and never written.

| Field | Column type to create |
| --- | --- |
| Status | Text, column shown in the tag browser |
| Rating | Calibre's own rating, or a rating column |
| Review | Long text, like comments |
| Date started | Date |
| Date finished | Date |
| Progress (%) | Integers, or a floating point column |

Custom columns are made under **Preferences > Add your own columns**. Calibre asks you to
restart after adding one.

Status labels are read loosely, so a column already holding `Read`, `Currently reading`,
`TBR`, `On hold`, `DNF` or `Finished` works without being renamed first.

The switches under **What to send** control what leaves Calibre. Turning off Reviews
keeps your reviews on your own machine; it does not stop Seekquel's reviews arriving.

Covers are the fifth switch and behave differently from the rest: Seekquel asks for the
ones it is missing and the plugin sends those and no others, up to twenty five per sync.
A cover for a book only you have is used straight away. One for a catalogue book with no
cover at all is offered as a suggestion and waits for a reviewer, since a catalogue cover
is seen by everybody. A book that already has a cover is left alone.

## Sync

**Seekquel > Send my whole library**, or select books first and use **Send the selected
books**. It runs as a background job, so Calibre stays usable and you can stop it.

Matching happens on the server, so give it a moment before reading the results back.

**Seekquel > Bring Seekquel up to date here** pulls, and writes into the columns you
mapped. Each matched book also gains a `seekquel` identifier, which is what **View this
book on Seekquel** uses.

## When something is not right

**Seekquel > Show the log** lists every request the plugin made, what came back and how
long it took, plus the books a sync skipped and the reason. Read it before assuming
nothing happened: a sync that appears to do nothing is usually one that sent books the
server has already seen.

The file sits beside Calibre's other plugin files, as `plugins/seekquel-sync.log` inside
your Calibre configuration directory, and trims itself, so it cannot grow without bound.
Attach it to a bug report.

## What it will not do

**It never clears anything.** A field Seekquel does not hold leaves your Calibre column
exactly as you typed it. Most people map two or three columns out of six, so reading an
empty answer as "delete this" would empty a library the first time anybody synced.

**It never rewrites a review.** Reviews are the one field where both sides refuse to
overwrite: a review you typed in Calibre is not replaced by Seekquel's, and one you wrote
in Seekquel is not replaced by your Calibre column. Whichever side is empty gets filled.
Everything else is short enough that losing it costs a retype; paragraphs are not.

**It never un-marks a finished book.** Marking a book read in Seekquel posts to your feed,
counts towards a reading goal and can earn a badge. A status column you last touched two
years ago is not grounds for taking all of that back.

**It never invents a book.** A book the Seekquel catalogue cannot place is not guessed at
and not silently filed as a private copy. It waits for you under **Settings > Integrations
> Calibre > Books from Calibre**, where you can look for it online, point it at the right
book, say the catalogue does not have it, or set it aside. Looking online searches the book
sources and shows you what came back; nothing is added until you pick one. That last one matters for a real library: a
Calibre folder holds manuals, RPG rulebooks and conference papers alongside novels, and
those are refused correctly and would otherwise sit in that list forever.

**Reading progress does not count as reading.** Calibre is a library manager, not a
reader. Its progress column is typed by hand or copied off a device days later, and it
cannot know when you read those pages. So a percentage moves your place in the book and is
never credited to a day's reading, because crediting it would bill an afternoon for a book
you finished in March.

## How a book is matched

By ISBN first, and by title and author after that. Downloading metadata in Calibre before
the first sync is the single most useful thing you can do: an ISBN matches outright, where
a title has to clear a much higher bar to be accepted.

Nothing is sent to any third party. Books are matched against the Seekquel catalogue and
nowhere else.

## Building from source

```bash
python build.py
calibre-customize -a "dist/Seekquel Sync.zip"
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the layout, the house style, and how to run a
whole sync headlessly through `calibre-debug`.

## Licence

[GPL-3.0-or-later](LICENSE), the same as Calibre, which this loads into the process of.
