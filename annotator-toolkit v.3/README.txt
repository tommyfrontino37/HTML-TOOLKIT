THE ANNOTATED-BOOK TOOLKIT
=========================

Turns a paged HTML book - or a text PDF - into the annotated edition:
dark mode, four-colour highlighting, hideable click-to-open notes, and a panel
with Export / Import / Report / Print / Save into HTML / Save over my book.

THE EASY WAY (one command)
--------------------------
    python3 build_enhanced.py \
        --input book.html --output "My Book (annotated).html" \
        --title "My Book" --author "A. Author" \
        --prefix mybook-slug --slug my-book --picker mybook-file

It re-keys every storage name (so two books can never share annotations), runs the
four patchers in order, checks the result (script syntax, leftovers, self-contained)
and runs the behaviour tests.  Exit 0 means everything passed.

THE OFFLINE DICTIONARY
----------------------
Any book built this way can carry a dictionary inside it: select a word in the text,
click Define in the popup, and get a definition - no internet, and it works inside a
baked copy too.

    python3 make_dict_data.py --book book.html --out dict_data.json

Only the words that actually appear in the book are included, so the data stays
small (Watson: 4,596 unique words -> 4,354 entries -> 548 KB).  Sources, in order:
  1. glossary.py     hand-written definitions for Puritan/theological vocabulary
                     (WordNet gives "repentance: remorse for your past conduct" -
                      wrong register for this material, and worse for mortification,
                      vivification, effectual calling, means of grace, and so on)
  2. WordNet         clean modern glosses
  3. Webster's 1913  public domain, and the right vintage for archaic words
Add to glossary.py and re-run to improve the hand-written layer.

FROM A PDF
----------
    python3 pdf_to_book.py --pdf "book.pdf" --out book.html \
        --title "My Book" --author "A. Author" [--facsimile webp --dpi 90 --quality 48]

Text layer becomes the reading view; --facsimile also embeds a WebP picture of every
page so the book keeps an "Original pages" view (bigger file: ~30 MB for 274 pages).
Superscripts, italics and paragraph joins are taken from the PDF's own spans.

FILES
-----
  build_enhanced.py     the pipeline (start here)
  pdf_to_book.py        PDF -> paged HTML in the right shape
  run_tests.py          behaviour tests for one book
  test_isolation.py     proves two books cannot share annotations
  make_dict_data.py     builds the dictionary data for one book
  glossary.py           the hand-written definitions (edit these freely)
  add_dark_mode.py      the five patchers, in order:
  add_highlights.py       dark mode -> highlighting -> notes -> panel -> dictionary
  add_notes.py
  add_panel.py
  add_dictionary.py       (dictionary: needs dict_data.json)
  bake_annotations.py   the same "bake" from the command line
  HOW-TO-REQUEST-ANOTHER-BOOK.md   what to tell the assistant
  NOTES-FOR-A-FUTURE-ASSISTANT.md  every trap found while building this

DO NOT run the four patchers by hand on an already-built file: they are not
idempotent.  Always start from the pristine original (build_enhanced.py does).
