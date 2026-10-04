# HTML-TOOLKIT

Convert a text PDF into a readable, self-contained, paged HTML book with
optional annotations: table of contents, dark mode, four-colour highlighting,
per-quote notes, an annotations panel, and an offline dictionary built from the
book's own vocabulary.

## Quick start

```bash
cd "annotator-toolkit v.3"
python3 -m pip install -r requirements.txt

python3 build_enhanced.py \
    --input book.pdf --output "My Book.html" \
    --title "My Book" --author "A. Author" \
    --prefix my-book-a-author --slug my-book --picker my-book-file
```

That is the whole setup. The build checks that its headless browser can launch
before doing any work, and on a fresh machine repairs itself: it installs the
Chromium the behaviour tests need, and — when `sudo` works without a password —
its system libraries, then carries on. Add `--no-auto-setup` to be told the fix
commands instead of having them run, or `--skip-tests` to build without the
browser suite.

<details>
<summary>If you would rather install the browser by hand first</summary>

```bash
python3 -m playwright install chromium
python3 -m playwright install-deps chromium   # needs sudo/root
```

Same commands the automatic repair runs. Either order works.
</details>

The output is a single HTML file that works offline in any modern browser.
A 274-page book with a 6,500-entry offline dictionary builds in a couple of
minutes; most of that is the dictionary and the test suite.

## After the build

| Tool | What it does |
|---|---|
| `link_endnotes.py` | turns the book's own printed endnote numbers into links, both ways — see `LINKING-ENDNOTES.md` |
| `bake_annotations.py my-export.json --master "My Book.html"` | bakes a highlights/notes export into a copy of the book |
| `make_dict_data.py` | builds the dictionary data on its own |
| `run_tests.py --book "My Book.html" --title … --prefix …` | the behaviour suite, against any built book |
| `test_isolation.py --a A.html --a-prefix … --b B.html --b-prefix …` | proves two books on one machine cannot see each other's annotations |

The patchers (`add_dark_mode.py`, `add_highlights.py`, `add_notes.py`,
`add_panel.py`, `add_dictionary.py`) are driven by `build_enhanced.py`; do not
run them by hand over a book that is already built.

## Documentation

- `annotator-toolkit v.3/README.txt` — every flag, the dictionary, the tests
- `annotator-toolkit v.3/LINKING-ENDNOTES.md` — making printed endnotes clickable
- `annotator-toolkit v.3/HOW-TO-REQUEST-ANOTHER-BOOK.md` — ordering another book
- `annotator-toolkit v.3/NOTES-FOR-A-FUTURE-ASSISTANT.md` — design scars and landmines
- `Changelog/CHANGELOG.md` — what changed and why

## Layout

| Path | What it is |
|---|---|
| `annotator-toolkit v.3/` | the working toolkit (converter, patchers, tests) |
| `HTML files using V.1 tool kit/` | example output built with the v.1 toolkit |
| `Changelog/` | version history |
| `LICENSE` | MIT, for this repository's own code |
| `NOTICE.md` | third-party components, licence questions, and the content caveats |

## Licence

MIT for the toolkit's own code. PyMuPDF, the dictionary sources and the example
book files each carry their own terms — `NOTICE.md` lays them out, including
what is worth deciding before publishing this repository.
