# NOTES FOR A FUTURE ASSISTANT

You are being handed a working toolkit that turns a paged HTML book into an
annotated edition. It was built and tested over one long session; this file is what
that session learned. Read it before touching anything — several of the notes are
scars.

---

## The job

Given a pristine book HTML plus a title and author, produce the annotated edition:
dark mode, four-colour highlighting, hideable click-to-open notes, and the notes
panel with **Export / Import / Report / Print / Save into HTML / Save over my book**.
All self-contained JS/CSS, no network calls, no `confirm`/`alert`/`prompt`.

## Build

```
add_dark_mode.py  ->  add_highlights.py  ->  add_notes.py  ->  add_panel.py
```

- Each patcher rewrites the working copy **in place** and prints `ok [...]` per anchor.
- **Not idempotent. Never re-run one over an already-built file.** Always start from
  the untouched original in `uploads/`.
- The patchers carry absolute paths and the title/keys of the original book. For a
  new book, before building: swap the paths, swap the display title, and re-key the
  storage identifiers (table at the end of `HOW-TO-REQUEST-ANOTHER-BOOK.md`).

## Structure the patchers expect

`#page-N` sections containing a `.reading-content` text layer, a `#view-mode` select
(`reading` / `original`), and `body[data-mode="reading"]`. If a new file differs,
read its markup first and adapt the anchors — do not guess.

## Landmines (each of these cost real debugging time)

1. **Escaping.** Never hand-write backslash escapes in generated JS. Use
   `String.fromCharCode(92)` for a literal backslash and `(10)` for a newline. A
   regex you meant as `/<\/g` can silently gain a backslash and break the page.
   After any patch: `node --check` the extracted `<script>`, always.
2. **Baking must replace, not append.** `cleanClone()` strips an existing
   `[id="baked-annotations"]` block and resets transient UI state
   (`#hl-status`, `#ow-msg`, panel hidden, list empty, `body[data-mode]="reading"`,
   `#view-mode` value). Re-bake must always yield exactly **one** data block.
   Check with: `text.count('<script type="application/json" id="baked-annotations">') == 1`.
   This bit twice: `bake_annotations.py`'s own summary printed `PROBLEM` on
   every *correct* bake of a v.3 book, because it counted the bare id, which the
   reader's JavaScript also mentions. It counts the whole tag now (2026-10-04).
3. **The panel's status line is invisible.** `#hl-status` lives in the toolbar and the
   panel overlay covers it. Any panel action that reports an outcome must ALSO write
   into the panel's own message line (`#ow-msg`). This was the cause of a "dead button".
4. **Save over my book.** Chrome throws `AbortError` both when the user cancels the
   picker AND when it refuses a write — distinguish by *stage*. Permissions never
   survive a reload: call `queryPermission()` then `requestPermission()` on the next
   user click. Remember the handle in IndexedDB so a reload is one click + Allow.
   On any refusal: forget the handle, put an annotated copy in Downloads, say why.
   `showOpenFilePicker` must be called straight from a click (user gesture).
5. **Go to must arrive.** In "Original pages" view the text layer is `display:none`,
   so the highlight has a 0×0 position and `scrollTo` goes nowhere: switch back to
   Reading view via `#view-mode` first. Prefer flashing the `mark.hl` itself; an
   offset landing on a node boundary resolves to the text *before* it.
6. **Go to on a note must SHOW it.** The click-to-open card is a toggle
   (`notesAPI.open`); reusing it can close the note you asked to see — use
   `notesAPI.show`.
7. **All `file://` pages share ONE storage area.** Two books built with the same keys
   would show each other's annotations. Re-key per book.
8. **Overwriting the file is never automatic.** Explicit picker + permission, and a
   guard that the picked file really is this book (`id="view-mode"`,
   the title, `reading-content`).

## The offline dictionary (added later, same session)

- Data lives in `<script type="application/json" id="dict-data">` with every `<`
  escaped as `\u003c`; the reader un-escapes before `JSON.parse`.  Never inject raw
  JSON into an inline script without that escape.
- Build the data from the book's **own vocabulary** (5k words -> ~550 KB).  A full
  dictionary would be tens of MB and mostly unused.
- Definition sources, best first: `glossary.py` (hand-written, covers theological
  vocabulary and archaic words), WordNet, then Webster's 1913.  Label the source in
  the card - a reader deserves to know whether a gloss is modern or 1913.
- The Define button is appended to the highlighter's own popup (`.hl-pop`), which is
  built at runtime by add_highlights.py.  add_dictionary.py therefore runs last.
- **Landmine:** `</head>` and the viewport meta each appear TWICE in a built book -
  once in the real head, once inside the panel's report template string.  Anchor on
  something unique, or insert before the *first* `</head>`.
- **Landmine:** the pipeline's `node --check` must skip `application/json` script
  tags, or it reports the data block as a syntax error.
- **Landmine:** after patching, `add_*` scripts are NOT idempotent - running the
  pipeline on an already-built file fails on the first duplicate anchor.  Always
  rebuild from `uploads/`.

## Where the patchers get their paths (asked often, looks wrong, is not)

The five patchers open a fixed path with the Watson title and storage keys, which
reads like a landmine and is instead the design: `build_enhanced.py` stages an
edited copy of each patcher into the work directory, substituting
`/home/user/…`, the title, author, prefix, slug and picker (`SUBSTITUTIONS`), and
runs the copy. The originals on disk are never executed. If you change a
patcher's opening line, keep the literal strings the substitution table matches,
or the staged copy will keep the old book's path. Parameterising the patchers
properly (argparse, no substitution) has been considered twice and not done: it
touches every literal in ~100 KB of code, and there is no pristine-HTML fixture
in the tree to regression-test the HTML route against — the v.1 example is
already annotated, so the patchers fail on it at the second anchor.

## The PDF converter's superscript rule, and why it is narrow

`line_runs()` trusts the PDF's superscript flag, and additionally promotes a
short digit run (≤ 3 digits) set clearly under the body size (< 0.85×) that is
also the smallest size on its line. Some producers mark an endnote marker that
*opens* a line by size alone with the flag clear; on *Precious Remedies Against
Satan's Devices* (Brooks, 274 pages, Banner of Truth/calibre, 2026-10-04) that
silently demoted markers 78 and 339 to body text and cost a chase. Before
widening the rule, re-run the scan rather than reasoning about it: across the
whole Brooks PDF the only small digit runs are the 412 endnote markers, and the
printed endnote numbers are set at body size, so the rule cannot reach them.
A merged run that the PDF itself packs into one span (`324325`) is *not*
splittable here — the converter has no note table — and is left to
`link_endnotes.py`, which splits it against the real note numbers.

## Test before handing over

Drive it with Playwright (headless Chromium):
`python3 -m playwright install chromium`, `sudo python3 -m playwright install-deps chromium`.
Headless **cannot** show the real file dialog — stub `showOpenFilePicker` with fake
handles and assert on what gets written.

Check at minimum: highlight a sentence → it persists across a reload; notes show and
toggle; Go to works in **both** views, for a highlight and for a note; Export JSON
round-trips; Save into HTML yields one data block; a baked copy reopens in Reading view
with its marks restored; Save over my book writes, refuses politely, and recovers on
the next click; no `pageerror` anywhere.

**Pitfalls in the tests themselves** (all seen and fixed): count the full
`<script type="application/json" id="baked-annotations">` tag, not the bare id (it also
appears in JS); read `document.body` after load, not raw file bytes (a font blob
precedes it); remember the flash ring self-clears after **1500 ms** and `#hl-status`
after **1800 ms** — poll, don't sleep; toolbar buttons are covered while the panel is
open, so click via the DOM; `page.evaluate` with an argument does **not** bind it into
an IIFE string — interpolate values instead.
