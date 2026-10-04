# Notice — third-party components and content

This repository's own code is licensed under the MIT License (see `LICENSE`).
That covers the toolkit's Python and its generated CSS/JavaScript. It does not
cover the third-party libraries the toolkit uses, the dictionary data it
builds, or the book text committed as an example.

## Runtime dependencies

| Component | Used for | License |
|---|---|---|
| [PyMuPDF](https://pymupdf.readthedocs.io/) | reading the PDF (`pdf_to_book.py`) | **AGPL-3.0** — see the note below |
| [Pillow](https://python-pillow.org/) | `--facsimile` page images | MIT-CMU |
| [NLTK](https://www.nltk.org/) | WordNet lookups in the dictionary | Apache-2.0 |
| [Playwright](https://playwright.dev/python/) | the behaviour test suite | Apache-2.0 |
| Node.js (optional) | `node --check` over inline scripts | MIT |

**PyMuPDF is AGPL-3.0.** That is worth a decision, not a footnote: if you
distribute this toolkit (or a binary bundle of it), AGPL obligations attach to
PyMuPDF itself. Calling it from your own MIT-licensed code is the ordinary case,
but read the license before shipping a bundle, and keep this notice with any
copy you pass on. If that is a problem, `pypdf`/`pdfplumber` are weaker but
permissively licensed alternatives to consider.

## Dictionary data

The offline dictionary is generated from the book's own vocabulary and
assembles definitions from, best first:

- `glossary.py` — hand-written for this toolkit (MIT, this repository);
- **WordNet 3.0** — Princeton University; the [WordNet License](https://wordnet.princeton.edu/license-and-commercial-use)
  permits use and redistribution provided the copyright notice is retained.
  Definitions produced from it keep the word "WordNet" as their source label in
  the definition card, which is that notice;
- **Webster's 1913** — public domain. Fetched as a JSON mirror from
  `matthewreagan/WebstersEnglishDictionary`; confirm that mirror's terms if you
  redistribute the data file itself rather than generating it.

Generated dictionary data is embedded in each built book and labelled per
definition. Built books are outputs, not source files; see below before
committing large ones.

## Content in this repository

One book file is committed — twice, byte for byte:

| Path | Size | md5 |
|---|---|---|
| `HTML files using V.1 tool kit/The Doctrine of Repentance - Thomas Watson .html` | 10.5 MB | `3590534d047e5c42d397ece18587ec8b` |
| `annotator-toolkit v.3/shell.html` | 10.5 MB | `3590534d047e5c42d397ece18587ec8b` |

They are the same file. `shell.html` is not a separate work of murky
provenance; it is the v.1 example, kept where the PDF route looks for its
template.

The duplication is load-bearing, not sloppiness. `pdf_to_book.py` opens the
shell, cuts out everything between `<main class="book">` and `</main>` — the 274
pages of Watson — keeps the surrounding toolbar, styles and reader scripts,
re-keys `watson-repentance` to the new book's prefix, swaps the title and
author, and drops the newly converted pages into the gap. A finished book *is*
the template, which is why the file is 10.5 MB and why `shell.html` cannot
simply be deleted without changing the converter. Git stores the content once
(both paths point at blob `f45ed41c891df17454a424fdf15af6b9b7aaefae`); only a
working tree pays for two copies.

So the content question is **one** question about one work: the *text* of
Thomas Watson's sermons is public domain (1693), but this file is a conversion
of a modern, commercially published edition, and the editorial matter and
typography belong to that publisher. Options, easiest first:

- **Leave it.** The repository stays functional and Git deduplicates the bytes;
  only a fresh clone carries 10 MB twice.
- **Rebuild both from a public-domain edition** (CCEL, Project Gutenberg). One
  conversion dropped in at both paths removes the question from the repository
  entirely — and a public-domain book makes a better example anyway.
- **Keep the licensed file out of tree** and document the one command that
  rebuilds a shell locally (a small change to the `SHELL` path in
  `pdf_to_book.py`, or a `--shell` flag).

Whichever you pick, say so in the README. The only real exposure is a public
repository quietly carrying a publisher's edition with nothing explaining why.

## Books you build with the toolkit

Books built from a licensed PDF (for example one carrying a purchaser's
watermark or an "exclusive use of …" line) keep that matter in the output —
the conversion is faithful, watermark included. Share builds only as far as
your licence for the source permits.
