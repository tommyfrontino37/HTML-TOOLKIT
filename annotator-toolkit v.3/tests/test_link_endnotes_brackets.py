"""Regression tests for link_endnotes_brackets.py (no browser required).

The stock link_endnotes.py recognises notes printed as "1." / "1)". A book that
prints them as "[ 1 ]" — in the body both spaced ("penny [ 1 ]") and attached
("accidence,[2]") — produces no links at all from it. This suite pins the
bracket route, and above all pins the rule that matters: the tool wraps text,
it never changes it, because highlights are stored as character offsets inside
each page's .reading-content.

Covered here:
  * spaced and attached markers are both linked, forward;
  * note paragraphs get an anchor and a back-link, both ways;
  * every .reading-content's text is byte-identical before and after (the
    invariant link_endnotes.py also refuses to write without);
  * running it over an already-linked book refuses instead of nesting <a>;
  * a book with no Endnotes block fails loudly instead of writing.

The fixture is a synthetic two-page book; no real book's text is used.

Run from the toolkit directory:
    python3 -m unittest discover -s tests -v
"""

import html as htmllib
import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

TOOLKIT_DIR = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = TOOLKIT_DIR / "link_endnotes_brackets.py"


def load_module():
    spec = importlib.util.spec_from_file_location("link_endnotes_brackets",
                                                  MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


libr = load_module()

TAGS = re.compile(r"<[^>]+>")
SECTION = re.compile(r'<section id="page-(\d+)"')
SKIP = re.compile(r"<(script|style)\b.*?</\1\s*>", re.S | re.I)


def reading_texts(doc):
    """{page: text nodes of that page's .reading-content} — the offsets source."""
    out = {}
    for page, s, e in libr.sections(doc):
        reg = libr.reading_region(doc, s, e)
        if reg:
            out[page] = libr.text_with_map(doc[reg[0]:reg[1]])[0]
    return out


def book(markers=True, endnotes=True):
    """A two-page fixture shaped like the toolkit's output."""
    body = ""
    if markers:
        body = (
            'have is but as an earnest penny [ 1 ] for all the glory\n'
            'and Bible and accidence,[2] and so to his grammar.\n'
            'It is said of Pompey, [ 3 ] that when he was carrying corn.'
        )
    pages = [
        (1, body or "A page with no markers in it at all."),
    ]
    if endnotes:
        pages.append((2, "[ 1 ] A first instalment which guarantees the rest.\n"
                         "[ 2 ] Accidence = the part of grammar dealing with inflexions.\n"
                         "[ 3 ] Gnaeus Pompey Magnus (106-48 bc)."))
    else:
        pages.append((2, "Just another ordinary page of body text here."))

    sections = []
    for page, text in pages:
        lines = []
        for n, line in enumerate(text.split("\n"), 1):
            lines.append('<span id="line-%d-%d" class="text-line">%s</span>'
                         % (page, n, htmllib.escape(line)))
        heading = "<h2><span>Endnotes</span></h2>\n" if (endnotes and page == 2) else ""
        sections.append(
            '<section id="page-%d" class="source-page" data-page="%d">'
            '<div class="page-head">Page %d of 2</div>'
            '<div class="reading-content"><p>%s%s</p></div></section>'
            % (page, page, page, heading, " ".join(lines)))
    return ("<!DOCTYPE html>\n<html><head><title>Fixture</title></head>\n"
            "<body>%s</body></html>" % "\n".join(sections))


def run(source_text, *extra):
    """Write the fixture in a tempdir and run the tool over it, as a user would."""
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "in.html"
        out = pathlib.Path(tmp) / "out.html"
        src.write_text(source_text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--input", str(src),
             "--output", str(out), *extra],
            capture_output=True, text=True, cwd=str(TOOLKIT_DIR))
        produced = out.read_text(encoding="utf-8") if out.exists() else None
        return result, produced


class BracketedMarkerTests(unittest.TestCase):
    def test_spaced_and_attached_markers_are_both_linked(self):
        result, out = run(book())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("linked 3 in-text markers, 3 notes, 3 back-links", result.stdout)
        for n in (1, 2, 3):
            self.assertIn('href="#endnote-%d"' % n, out)
            self.assertIn('id="endnote-%d"' % n, out)
            self.assertIn('href="#endnote-ref-%d"' % n, out)

    def test_the_note_number_is_what_identifies_a_note(self):
        _, out = run(book())
        # note 2's paragraph carries its own anchor, immediately before the line
        i = out.index('id="endnote-2"')
        after = out[i:i + 400]
        self.assertIn('href="#endnote-ref-2"', after)
        self.assertIn("[ 2 ] Accidence", htmllib.unescape(TAGS.sub("", after)))

    def test_offsets_are_untouched(self):
        source = book()
        _, out = run(source)
        self.assertEqual(reading_texts(source), reading_texts(out))

    def test_no_text_character_is_added_or_removed(self):
        source = book()
        _, out = run(source)
        before = "".join(reading_texts(source).values())
        after = "".join(reading_texts(out).values())
        self.assertEqual(before, after)

    def test_linking_twice_refuses(self):
        _, once = run(book())
        result, out = run(once)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already endnote-linked", result.stderr)
        self.assertIsNone(out)

    def test_a_book_with_no_endnotes_block_stops(self):
        result, out = run(book(endnotes=False))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Endnotes", result.stderr)
        self.assertIsNone(out)

    def test_markers_without_notes_are_left_alone(self):
        # page 1 references [ 1 ]..[ 3 ] but there is no Endnotes block, so
        # nothing may be linked and nothing may be written.
        result, out = run(book(endnotes=False))
        self.assertIsNone(out)

    def test_in_place_keeps_a_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "book.html"
            src.write_text(book(), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--input", str(src), "--in-place"],
                capture_output=True, text=True, cwd=str(TOOLKIT_DIR))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((pathlib.Path(tmp) / "book.html.bak").exists())
            self.assertIn('class="endnote-ref"',
                          src.read_text(encoding="utf-8"))

    def test_nothing_is_drawn_beside_a_note(self):
        # The notes list must print exactly as the book does: the marker is the
        # link and its own affordance. A back-arrow glyph was drawn here once and
        # was removed at the reader's request, so this pins it out.
        _, out = run(book())
        self.assertNotIn("endnote-back::before", out)
        self.assertNotIn("21A9", out)               # the U+21A9 ↩ code point
        self.assertNotIn("\u21a9", out)
        self.assertIn("endnote-anchor:target", out)  # the landing flash stays
        self.assertIn("scroll-margin-top", out)      # so does the toolbar offset

    def test_the_clickable_cue_is_a_style_not_text(self):
        # Whatever the cue looks like, it lives in CSS: the marker's own text
        # stays exactly "[ 1 ]".
        _, out = run(book())
        self.assertIn("[ 1 ]", out)
        self.assertNotIn("[ \u21a9 1 ]", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
