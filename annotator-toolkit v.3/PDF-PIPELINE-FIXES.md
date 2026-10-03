# PDF-to-annotated-HTML fixes

This drop-in update fixes the template and PDF-order issues found while converting
`Mere Christianity`, and gives PDF input a one-command route through the existing
book builder.

## Files in this update

- **`pdf_to_book.py`** — replaces the Watson sample's title, author, storage IDs,
  and dictionary; removes inherited Cloudflare/remote scripts; repairs isolated
  drop caps; and detects/reverses Arabic-Indic digit runs when an otherwise-Latin
  PDF has the same extraction-order issue. It also fails clearly on scanned-only
  PDFs instead of crashing on an empty text layer.
- **`build_enhanced.py`** — now accepts either PDF or pristine paged-HTML input. For
  PDFs it calls the converter and **does not rerun the non-idempotent patchers**
  already present in the reader shell. For HTML it keeps the existing patcher flow.
  It checks JavaScript, external dependencies, IDs, and book-specific keys, and
  only replaces an existing output after a successful build.
- **`tests/test_pdf_toolkit_fixes.py`** — regression tests for drop caps, digit
  order, shell cleanup, dictionary replacement, and safe title/author escaping.

The current facsimile settings and default are unchanged.

## Install into the repository

1. Download and extract `HTML-TOOLKIT-PDF-fixes.zip` at the repository root.
2. Allow it to overwrite the two files under `annotator-toolkit v.3/` and add the
   included documentation and tests.
3. Run the unit tests:

   ```bash
   python3 -m unittest discover -s "annotator-toolkit v.3/tests" -v
   ```

No `shell.html` replacement is needed: the updated converter sanitizes the legacy
shell during PDF conversion and rebuilds the dictionary from the current book.

## One-command PDF build

Install the repository requirements first:

```bash
python3 -m pip install -r "annotator-toolkit v.3/requirements.txt"
```

Then run:

```bash
python3 "annotator-toolkit v.3/build_enhanced.py" \
  --input "book.pdf" \
  --output "Book.html" \
  --title "Book Title" \
  --author "A. Author" \
  --prefix book-title-a-author \
  --slug book-title \
  --picker book-title-file
```

Optional PDF controls:

- `--facsimile webp` preserves the original-page view; the existing default is
  still `none`.
- `--digit-order auto|normal|reverse-arabic` controls repair of Arabic-Indic digit
  runs. `auto` only enables the repair for Latin-text PDFs with Arabic-Indic
  numerals and no Arabic-script letters.
- `--no-dictionary` skips dictionary data generation and removes its controls.
- `--skip-tests` skips browser behavior tests but **still runs** structural and
  inline-JavaScript checks.

For browser behavior tests, install Playwright's browser and system dependencies:

```bash
python3 -m playwright install chromium
python3 -m playwright install-deps chromium
```

The PDF converter can also be run directly. It creates an annotated, book-specific
HTML file on its own, so **do not run `build_enhanced.py` on that output again**:

```bash
python3 "annotator-toolkit v.3/pdf_to_book.py" \
  --pdf "book.pdf" --out "Book.html" \
  --title "Book Title" --author "A. Author"
```

## HTML input

For an unannotated, paged HTML source, continue using `build_enhanced.py --input
book.html` as before. Do not feed it an already annotated file; the builder now
recognizes common existing toolkit controls and stops with an explanation rather
than applying the patchers twice.

## Test results

The included unit tests pass (6 tests). The one-command PDF route was exercised
against a real 182-page text PDF with the original-page view and book-specific
offline dictionary enabled. Structural checks, JavaScript syntax checks, and the
repository's browser behavior suite all passed (**41 passed, 0 failed**). If the
host lacks Playwright's browser libraries, use `--skip-tests` to retain the
structural and JavaScript checks.
