# HTML-TOOLKIT

Convert a text PDF into a readable, self-contained, paged HTML book with
optional annotations: table of contents, dark mode, four-colour highlighting,
per-quote notes, an annotations panel, and an offline dictionary built from the
book's own vocabulary.

## Quick start

```bash
cd "annotator-toolkit v.3"
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m playwright install-deps chromium   # needs sudo/root; only needed if Chromium won't launch

python3 build_enhanced.py \
    --input book.pdf --output "My Book.html" \
    --title "My Book" --author "A. Author" \
    --prefix my-book-a-author --slug my-book --picker my-book-file
```

The output is a single HTML file that works offline in any modern browser.
`build_enhanced.py` checks the browser up front, so a broken environment
fails in seconds with the exact fix commands instead of after the whole
conversion.

## Documentation

- `annotator-toolkit v.3/README.txt` — every flag, the dictionary, the tests
- `annotator-toolkit v.3/HOW-TO-REQUEST-ANOTHER-BOOK.md` — ordering another book
- `annotator-toolkit v.3/NOTES-FOR-A-FUTURE-ASSISTANT.md` — design scars and landmines
- `Changelog/CHANGELOG.md` — what changed and why

## Layout

| Path | What it is |
|---|---|
| `annotator-toolkit v.3/` | the working toolkit (converter, patchers, tests) |
| `HTML files using V.1 tool kit/` | example output built with the v.1 toolkit |
| `Changelog/` | version history |
