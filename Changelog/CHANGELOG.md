# Changelog

## v4.2 — navigation no longer trusts the PDF outline

Found while converting a 267-page retail PDF (Grapevine India's *1984*, 2026-10-03).
Every fix below was reproduced before and after the change.

### Fixed

- **A broken PDF outline could ship a book with no usable navigation.** `pdf_to_book.py`
  copied `doc.get_toc()` into both navigation blocks unchanged, so an outline of
  `("(Untitled)", 3) × 3` produced three identical dead links, and an empty outline
  produced an empty table of contents *that still passed every check* (`BUILD OK`).
  Now:
  - `clean_outline()` drops `(Untitled)` titles, duplicates and out-of-range pages, and
    treats an outline with fewer than two distinct target pages as unusable;
  - when the outline is unusable (or absent), `detect_headings()` rebuilds navigation
    from the pages' own big-text headings, using the same font-size classification that
    already decided what becomes an `<h2>`. Title-page headings that just repeat the
    book's identity are skipped, and a heading repeated within two pages is treated as a
    running head;
  - the build says what it did: `WARNING: PDF outline unusable (3 entries pointing at 1
    unique page(s)); building navigation from the pages' own headings`, then
    `navigation: 27 entries from the page headings`;
  - new `--toc auto|pdf|headings|none` (default `auto`) chooses the source explicitly;
  - `build_enhanced.py` reports `navigation has N destination(s) for N heading(s)` and
    warns when a book has headings but no destinations.
- **`build_enhanced.py` treated a missing Node.js as a build failure**, even with
  `--skip-tests`, and never documented the requirement. It is now a skipped check with a
  clear notice; `--require-node` restores the old strict behaviour. Node is also no longer
  demanded for the behavior tests, which need Playwright, not Node.
- **The behavior suite hard-coded the probe word `sin`** (written against a theology
  title), so its dictionary check failed on any book that never uses that word while the
  feature itself worked. `choose_dict_probe()` now takes the word from the book's own
  dictionary data, and `--dict-word` overrides it. Reported as
  `-- dictionary (probe word: victory)`.
- **An offline machine with nltk installed but no WordNet corpus crashed the build.**
  Two causes, both fixed in `make_dict_data.py`: the import-time `nltk.download()` result
  was never checked, and nltk corpora load *lazily*, so `from nltk.corpus import wordnet`
  succeeds without the data and the `LookupError` only fired later, at first use, outside
  every guard. The corpus is now force-loaded inside the guard (and a mid-run failure
  falls back too). Verified: 7,825 entries from Webster + glossary, exit 0, instead of a
  traceback and no book.
- **Webster cache and URL:** the 22 MB Webster file no longer caches in `/tmp` (wiped per
  session); it uses `$XDG_CACHE_HOME/html-toolkit-wrn1913.json` and reuses any old
  `/tmp/wrn1913.json` already there. New `--webster-url` override.

### Added

- `tests/test_navigation.py` — 11 browser-free regression tests for outline cleanup,
  heading detection and the converter end to end (empty outline, degenerate outline,
  usable outline, `--toc headings`, `--toc none`).

### Documentation

- `HOW-TO-REQUEST-ANOTHER-BOOK.md`: the "PDF / EPUB / MOBI are a different job" claim is
  replaced with the one-command PDF route, and the section that implied `pdf_to_book.py`
  output should be fed to `build_enhanced.py` (which fails on duplicate anchors) now says
  not to.
- `README.txt`: documents the Node.js situation, the new flags, and how offline machines
  degrade.

### Test results

- Repository unit tests: **17 passed** (6 existing + 11 new).
- Full behavior suite on the 267-page test book, run by `build_enhanced.py`:
  **41 passed, 0 failed** (was 39 passed, 1 failed — the `sin` artifact).
- Air-gapped build (no WordNet, no network), no-Node build, and unknown-outline builds all
  complete successfully.
