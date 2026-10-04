# Making printed endnotes clickable

`link_endnotes.py` is a post-processor for a book built by this toolkit. It
turns the book's own printed endnote numbers into links — marker to note, and
note back to the sentence — so a reader does not have to page-hop by hand.

It is deliberately **not** one of the patchers. The patchers are not
idempotent, and running them over a finished book is the documented
duplicate-anchor failure. This script treats the built book as an input and
writes a new file, or edits in place with `--in-place` after keeping a `.bak`.

## Use

```bash
python3 link_endnotes.py \
    --input  "My Book (annotated).html" \
    --output "My Book (annotated, linked endnotes).html"

# in place:
python3 link_endnotes.py --input "My Book.html" --in-place

# if the endnotes are not under a heading called "Endnotes":
python3 link_endnotes.py --input "My Book.html" --output out.html --heading "Notes"
```

The script prints what it found and what it did:

```
endnotes block: 47 section(s), pages 227-273
endnotes found: 412 (numbered 1-412, sequential)
markers already in <sup> form: 410
  merged marker <sup>324325</sup> -> 324 + 325
notes with no marker yet (naked): none
linked 412 markers, 412 endnotes, 412 back-links
verified: all 274 sections' text is byte-identical to the input
```

## What it assumes

- the book has numbered endnote paragraphs starting with their number, inside
  pages that follow an `Endnotes` heading — that is what the converter produces
  from a book that has printed endnotes;
- the in-text markers are `<sup>N</sup>` (the converter's normal output), and
  each note number appears at most a handful of times;
- endnote numbering is the book's own, not the toolkit's per-quote notes. The
  two coexist: the toolkit's notes are stored separately and are untouched.

## The one rule it will not break

Highlights and notes are stored as **character offsets inside each page's
`.reading-content`**. Adding or removing one character of text moves every
offset on that page, and yesterday's highlights land on the wrong words.

So `link_endnotes.py` never changes text. It only wraps digits that are already
there, and the back-arrow on each note is drawn by CSS `::before` (pseudo-element
content is not DOM text). Before writing anything it re-extracts the text of
every section and refuses to write unless it is byte-identical to the input.

If you ever edit this script: that check is the point of it. Do not remove it,
and do not let a "tidy-up" replace the CSS arrow with a literal character.

## What it repairs along the way

Two extraction artefacts, seen in roughly one book in one:

- a merged marker — the PDF itself packs two adjacent markers into a single
  text run, and the conversion faithfully produces `<sup>324325</sup>`. The
  script splits it against the book's real note numbers, descending;
- a naked marker — an older `pdf_to_book.py` left a marker that opened a line
  as body text (`78 Joseph was famous …`) because the PDF set it in a smaller
  size without setting the superscript flag. **The converter now handles this**
  (see the changelog), so on a freshly built book the repair reports nothing to
  do and stays quiet. It remains for books built before the fix.

## Verified

On *Precious Remedies Against Satan's Devices* (Thomas Brooks, 274 pages):
412 of 412 markers linked, 412 back-links, no dangling targets, forward and
back jumps land clear of the sticky toolbar in both light and dark themes, and
the toolkit's own 41-test behaviour suite still passes against the linked file.
