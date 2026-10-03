THE ANNOTATED-BOOK TOOLKIT (v.3)
=================================

Build a self-contained, paged HTML book with dark mode, four-colour highlighting,
hideable notes, an annotations panel, and an optional offline dictionary.

INSTALL
-------
    python3 -m pip install -r requirements.txt

For browser behavior tests, also install Chromium and its system dependencies:
    python3 -m playwright install chromium
    python3 -m playwright install-deps chromium

ONE-COMMAND BUILD — FROM PDF OR HTML
------------------------------------
A text PDF (the built-in reader shell already contains the annotation tools):
    python3 build_enhanced.py \
        --input "book.pdf" --output "My Book.html" \
        --title "My Book" --author "A. Author" \
        --prefix my-book-a-author --slug my-book --picker my-book-file \
        [--facsimile webp] [--no-dictionary] [--skip-tests]

A pristine, paged HTML source (the toolkit adds the annotation tools):
    python3 build_enhanced.py \
        --input "book.html" --output "My Book.html" \
        --title "My Book" --author "A. Author" \
        --prefix my-book-a-author --slug my-book --picker my-book-file \
        [--no-dictionary] [--skip-tests]

The PDF route does not run the patchers a second time. It rebuilds the title's
storage keys and dictionary, cleans inherited analytics scripts, repairs common
PDF drop-cap ordering, and automatically handles reversed Arabic-Indic digit runs
in Latin-text PDFs. The HTML route still applies patchers in order. Both routes
check the output and keep an existing output file untouched unless the build passes.

PDF OPTIONS
-----------
  --facsimile webp       Embed page images and keep an Original pages view.
                         Existing default remains: none.
  --digit-order auto     Detect reversed Arabic-Indic runs in Latin-text PDFs.
  --digit-order normal   Leave digit order as extracted.
  --digit-order reverse-arabic  Force-reverse Arabic-Indic digit sequences.
  --toc auto             Where navigation comes from (default: auto).
                           auto      the PDF outline when it is usable, otherwise
                                     the pages' own headings
                           pdf       the outline only
                           headings  scan the pages' big-text headings
                           none      no navigation
                         A retail PDF whose outline is broken (entries titled
                         "(Untitled)", duplicates, or every entry on one page) is
                         detected and replaced with a heading scan, with a warning
                         on stdout. Use --toc headings to force the scan.
  --no-dictionary        Omit dictionary scripts, styles, and data.
  --dict-word WORD       Word the behavior tests use for the Define check.
                         Default: chosen from the book's own dictionary.
  --require-node         Fail when Node.js is missing, instead of skipping the
                         inline-JavaScript syntax check.
  --skip-tests           Skip Playwright behavior tests; structural and JavaScript
                         checks still run.

REQUIREMENTS
------------
Python 3 with the packages in requirements.txt. Playwright's Chromium is needed
only for the behavior tests:

    python3 -m playwright install chromium && python3 -m playwright install-deps chromium

Node.js is optional: if it is installed, build_enhanced.py runs `node --check`
over every inline script; if it is missing, that check is skipped with a notice
(add --require-node if you want it to be fatal instead).

Offline machines: a missing WordNet corpus, a missing Webster file, or a missing
nltk install all degrade to the sources that are available (glossary, then
Webster's 1913) instead of failing the build. See CHANGELOG.md.

The direct PDF converter is also available:
    python3 pdf_to_book.py --pdf "book.pdf" --out "My Book.html" \
        --title "My Book" --author "A. Author"

It builds a complete annotated HTML file by itself; do not run build_enhanced.py on
that output again.

THE OFFLINE DICTIONARY
----------------------
By default, the PDF builder creates definitions only for words found in the book.
Sources (best first): glossary.py (hand-written theological definitions), WordNet,
and Webster's 1913. First-time dictionary generation may download WordNet and
Webster data. Use --no-dictionary for an offline build or to omit the feature.

TESTS
-----
Run the browser-free PDF regression tests:
    python3 -m unittest discover -s tests -v

The full behavior tests are run by build_enhanced.py unless --skip-tests is passed.
They exercise highlighting, notes, the panel, export/import, baking, file saving,
and navigation in both reading and original-page views.

FILES
-----
  build_enhanced.py     one command for PDF or pristine HTML input
  pdf_to_book.py        PDF -> paged, annotated HTML
  make_dict_data.py    builds book-specific offline dictionary entries
  glossary.py           hand-written definitions and preferred senses
  add_dark_mode.py      theme-toggle patcher for pristine HTML
  add_highlights.py     highlighter patcher
  add_notes.py          per-quote note patcher
  add_panel.py          annotations panel patcher
  add_dictionary.py     offline dictionary patcher for pristine HTML
  run_tests.py          browser behavior tests
  test_isolation.py     checks that separate books cannot share annotations
  tests/                browser-free regression tests for PDF fixes

The patchers are not idempotent. Do not run them manually on a book that has
already been enhanced; start from the pristine HTML input or use the PDF route.
