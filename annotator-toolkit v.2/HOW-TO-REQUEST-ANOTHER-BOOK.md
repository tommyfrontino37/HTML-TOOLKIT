# How to order another annotated HTML book

*A one-page brief for turning another `.html` book into a copy of this format
(dark mode, four-colour highlighting, hideable click-to-open notes, the panel with
Export / Import / Report / Print / Save into HTML / Save over my book).*

---

## 1. What to send me

| Item | Why | Example |
|---|---|---|
| **The `.html` file itself** | It is the thing I rebuild from. Attach the *original*, not a copy you have already annotated | `The Three Impostors.html` |
| **The exact title** | It gets stamped into the file: the save guards, the "annotated" download name, the report heading | `The Doctrine of Repentance` |
| **The author** | Used in the notes report and markdown export | `Thomas Watson` |
| **One line about the file's shape** | Tells me whether the same patchers fit or need adapting | "Same shape as the Watson file" — or just "not sure, take a look" |
| **Any changes you want** | Otherwise you get the current defaults | "notes hidden by default", "no Save over my book button", "same four colours" |

### Copy-paste request

> Same treatment as the Watson file, please.
> File attached: **\<filename\>**
> Title: **\<Book Title\>**  Author: **\<Author\>**
> Changes: *(none / list them)*

That is genuinely all I need. Everything else — the four-step build, the re-keying,
the tests — is on me.

---

## 2. What I do with it

1. **Back up your original** untouched in `uploads/`, then rebuild from it (never
   patch an already-patched file — that is how the duplicate-data bugs happened).
2. **Re-key the book.** All `file://` pages in Chrome share *one* storage area, so a
   second book built with the current keys would show this book's highlights. Every
   book gets its own key prefix (e.g. `pilgrims-progress-highlights`), its own
   picker id and its own save-guard title.
3. **Run the four-step chain**: dark mode → highlighting → notes → panel
   (`add_dark_mode.py`, `add_highlights.py`, `add_notes.py`, `add_panel.py`).
4. **Test before handing it over** — highlighting, notes, the notes toggle, panel,
   Export/Import, Report, Print, Save into HTML, Save over my book, and "Go to"
   (Reading view *and* Original pages view), plus a check that a baked copy restores
   its own marks.
5. **Tell you what it needs**: Chrome or Edge for "Save over my book"; any browser
   for "Save into HTML".

---

## 3. Honest limits

- **Structure must match.** The patchers hook into this layout: pages as
  `#page-N .source-page`, the readable text in `.reading-content`, a view selector
  `#view-mode`, and `body[data-mode="reading"]`. A file from a different exporter
  may have none of that — then I read its markup first and adapt the anchors (a
  small job, but it is a first pass over the file, not a one-liner).
- **"Original pages" is images.** Highlights can only exist on the text layer, so in
  that view "Go to" switches you back to Reading and rings the sentence.
- **Save over my book** needs the File System Access API: Chrome / Edge / Opera on
  desktop, and it must be called from a click. Firefox and Safari get "Save into
  HTML" only.
- **PDF / EPUB / MOBI are a different job.** They first have to become a paged HTML
  with a text layer (that means pagination, and OCR if there is no text). Send one
  and I will tell you what it would take; it is not a same-day rebuild.
- **Annotations live in two places**: the browser's storage for the book, *and* baked
  into any file you save or bake. Export (or Save into HTML) is the portable copy.

---

## 4. The one-command pipeline (built and proven)

```
python3 build_enhanced.py --input mybook.html --output "My Book (annotated).html" \
    --title "My Book" --author "A. Author" \
    --prefix mybook-slug --slug my-book --picker mybook-file [--orig-views]
```

It re-keys the storage names, runs the four patchers, checks the result and runs the
behaviour tests.  From a PDF, first:

```
python3 pdf_to_book.py --pdf book.pdf --out mybook.html \
    --title "My Book" --author "A. Author" [--facsimile webp --dpi 90 --quality 48]
```

`--facsimile` embeds a WebP picture of every page so the book keeps the
"Original pages" view; without it the file is ~7x smaller and the view selector is
removed rather than offering an empty view.

Every build now also gets the **offline dictionary** (select a word -> Define) unless
you pass `--no-dictionary`.  It adds roughly 120 KB per 1,000 unique words.

## 5. The engine, if you ever want to run it yourself

```
uploads/<your file>                      the pristine original — never edited
add_dark_mode.py  →  add_highlights.py  →  add_notes.py  →  add_panel.py
                                         each rewrites the working copy in place
bake_annotations.py your-export.json out.html      the same bake from the command line
```

Build order matters and the patchers are **not** idempotent: always start again from
`uploads/`, never re-run one over an already-built file.

Storage keys and guards to re-key for a new book (find and replace across the four
patchers before building):

| What | Current value |
|---|---|
| storage keys | `watson-repentance-highlights`, `-notes`, `-notes-visible`, `-baked-applied` |
| remembered file handle | IndexedDB database `watson-repentance-file-handle` |
| file picker id | `doctrine-book` |
| save guard | the strings `id="view-mode"`, `The Doctrine of Repentance`, `reading-content` |
| download names | `The Doctrine of Repentance (annotated <date>).html` |
