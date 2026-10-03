# Changelog

## Unreleased — the build repairs its own test environment

Found the hard way in a fresh session (2026-10-03): the merged fail-fast
precheck diagnosed a missing-Chromium environment correctly, but nothing in
that session executed the fix, so the book shipped without the 41-test
interactive suite. Diagnosing was never the bottleneck; doing was.

### Changed

- `browser_preflight()` now self-heals: when the launch probe fails it runs
  `python3 -m playwright install chromium`, and if that is not enough and
  `sudo -n true` succeeds, `sudo -n python3 -m playwright install-deps
  chromium`, probing again after each step. A clean session therefore turns
  the single build command into the whole setup; the old hint-only behavior
  remains available as `--no-auto-setup`, and `--skip-tests` still bypasses
  the browser entirely.
- README quick start documents the self-repair and the two opt-out flags.

### Verified

- Purged `libnspr4` / `libnss3` / `libasound2t64` and pointed
  `PLAYWRIGHT_BROWSERS_PATH` at an empty directory (a fresh session's state):
  the build reinstalled the browser and the libraries by itself and finished
  `RESULT: 41 passed, 0 failed`.
- Same broken environment with `--no-auto-setup`: aborts in ~1s with the fix
  hint, nothing converted.

## Unreleased — environment failures now fail fast, with instructions

Found while converting *Christ and His Threefold Office* (John Flavel, 143 pages,
2026-10-03) on a fresh machine: the build did all of its work — conversion,
dictionary, structural checks — and then died inside the behavior suite because
Chromium's system libraries were missing. Every change below was reproduced
before and after.

### Fixed

- **`build_enhanced.py` checked Playwright too shallowly and too late.** The
  behavior-test gate ran `python3 -c "import playwright"`, which passes even
  when the Chromium binary is missing or its system libraries are not
  installed; the full pipeline (~12 s of conversion and dictionary work) ran
  anyway, then failed amid Playwright's process-debug spew. Now
  `browser_preflight()` launches headless Chromium exactly the way
  `run_tests.py` does, before any heavy work. A broken environment aborts in
  ~2 s with the exact fix commands (`playwright install chromium`,
  `playwright install-deps chromium` — which needs sudo — or `--skip-tests`).
  Verified: with an empty `PLAYWRIGHT_BROWSERS_PATH` the build aborts before
  conversion, leaves no work directory, and exits 1.
- **A missing PyMuPDF produced a raw traceback** from `pdf_to_book.py`'s
  module-level `import pymupdf`, reported only as `BUILD FAILED: PDF
  conversion`. The import is now guarded with a one-line install instruction
  (exit 2); the lazy `from PIL import Image` in the facsimile path is guarded
  the same way for `--facsimile webp` runs.

### Added

- `requirements.txt` is version-floored (`pymupdf>=1.24,<2`, `Pillow>=10`,
  `nltk>=3.8`, `playwright>=1.44`) and documents the two extra Playwright
  install steps next to the dependency that needs them.
- Root `README.md` gained the quick start (setup + one-command build) and a map
  of the repository; previously the entire README was one sentence and the real
  instructions were only in `annotator-toolkit v.3/README.txt`.

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
