# Making printed `[ N ]` endnotes clickable

`link_endnotes_brackets.py` is the companion to `link_endnotes.py`, for books
whose endnotes are printed as `[ 1 ]` instead of superscript numbers. It turns
those markers into links in both directions — marker to note, note back to the
sentence — so a reader does not have to page-hop by hand.

Run `link_endnotes.py` first on a book whose notes are superscript. Run this one
when it reports:

```
endnotes block: 3 section(s), pages 214-216
no numbered note paragraphs found in the endnotes block
```

That is this script's cue, not a failure: the block was found, the notes are
just not in the form the stock script reads.

## Use

```bash
python3 link_endnotes_brackets.py \
    --input  "The Rare Jewel of Christian Contentment.html" \
    --output "The Rare Jewel of Christian Contentment (linked endnotes).html"

# in place:
python3 link_endnotes_brackets.py --input "My Book.html" --in-place

# a book with no Endnotes heading, or a different one: not supported — the
# block is found by the pages whose text begins with "Endnotes".
```

It prints what it found and what it did:

```
endnotes block: starts on page 214
notes found: 21 (numbered 1-21, sequential)
linked 21 in-text markers, 21 notes, 21 back-links
verified: all 218 sections' text is byte-identical to the input
wrote The Rare Jewel of Christian Contentment.html (backup at ....bak)
```

## What it assumes

- the notes live in pages whose `.reading-content` text begins with
  `Endnotes`, and each note paragraph starts with `[ N ]` — numbering the
  book's own, sequential from 1;
- in the body the same marker appears both spaced (`an earnest penny [ 1 ]`)
  and attached to the word (`accidence,[2]`). Both spellings are linked; a
  marker with no matching note is left exactly as printed;
- a note is only accepted when its number is the next one expected. That is
  what stops a `[ 12 ]` inside note 12's *text* being read as a note of its
  own;
- the endnote run ends at the first page after it that opens no note, so the
  `Table of Contents` and `About the Trust` pages that follow are untouched.

## The one rule it will not break

Highlights and notes are stored as **character offsets inside each page's
`.reading-content`**. Adding or removing one character of text moves every
offset on that page, and yesterday's highlights land on the wrong words.

So this script only ever wraps characters that are already there and inserts
one empty element — `<span id="endnote-N" class="endnote-anchor">`, which
carries no text at all. Nothing is drawn beside the marker: the printed number
is itself the link and its own cue, with a dotted underline on hover. That is
deliberate, and it is also what a reader asked for: the first draft drew a
back-arrow glyph on every note with a CSS `::before`, which made the plain
notes list look decorative, so the arrow came off (2026-10-04) and the dotted
underline stayed as the affordance. It re-extracts the text of every section
before writing and refuses to write unless it is byte-identical to the input.
Its regression test pins exactly that, and a book that has already been linked
is refused rather than linked twice (the markers are still text, so a second
pass would nest `<a>` elements).

If you ever edit this script: those two checks are the point of it. Do not
remove them, and do not add a literal arrow character — a "tidy-up" that puts
one glyph back in the markup moves every highlight offset on that page.

## Two behaviours worth knowing

- The reader lays out the whole book in one document and lets the browser do
  fragment scrolling, so a same-page `#endnote-N` jump is natively handled and
  lights the note up with `:target`. Targets carry `scroll-margin-top:110px` so
  they clear the reader's sticky toolbar.
- The toolbar's page field can read one page behind after such a jump — that is
  the reader's own indicator, not the link.
- The notes list stays plain: the marker is the only thing you see, and the
  dotted underline under it is the whole affordance.
