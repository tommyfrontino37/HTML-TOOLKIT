"""Regression tests for navigation building (no browser required).

Covered here, because the earlier suite had no navigation coverage at all:
  * a degenerate outline ("(Untitled)" entries, duplicates, one target page)
    must not reach the reader shell;
  * no outline at all must still produce usable navigation, built from the
    pages' own headings, and must say so;
  * a good outline must pass through unchanged and silently;
  * --toc none must leave navigation empty without failing the build.

Run from the toolkit directory:
    python3 -m unittest discover -s tests -v
"""

import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import pymupdf

TOOLKIT_DIR = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = TOOLKIT_DIR / "pdf_to_book.py"
SPEC = importlib.util.spec_from_file_location("pdf_to_book_navigation", MODULE_PATH)
pdf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdf)

BODY = ("This paragraph exists so the converter can measure the body font size "
        "and classify the headings above it correctly.")
HEADINGS = ("PART ONE", "Chapter 1", "PART TWO", "Chapter 2", "Chapter 1")


def make_pdf(path, outline=None, headings=HEADINGS):
    """A small text PDF: one big heading per page, body text under each."""
    doc = pymupdf.open()
    for heading in headings:
        page = doc.new_page()
        page.insert_text((72, 100), heading, fontsize=22)
        page.insert_text((72, 140), BODY, fontsize=11)
        page.insert_text((72, 156), BODY, fontsize=11)
    if outline is not None:
        doc.set_toc(outline)
    doc.save(str(path))
    doc.close()


def convert(source, out, *extra):
    command = [sys.executable, str(MODULE_PATH), "--pdf", str(source), "--out", str(out),
               "--title", "Test Book", "--author", "A. Author", "--no-dictionary", *extra]
    return subprocess.run(command, capture_output=True, text=True, cwd=str(TOOLKIT_DIR))


def options(html):
    return re.findall(r'<option value="(\d+)">([^<]*)</option>', html)


class OutlineCleanupTests(unittest.TestCase):
    def test_untitled_entries_and_duplicates_are_dropped(self):
        entries, usable = pdf.clean_outline(
            [("(Untitled)", 3), ("(Untitled)", 3), ("Chapter 1", 4), ("Chapter 1", 4), ("Chapter 2", 9)], 20)
        self.assertEqual(entries, [("Chapter 1", 4), ("Chapter 2", 9)])
        self.assertTrue(usable)

    def test_degenerate_outline_is_not_usable(self):
        entries, usable = pdf.clean_outline([("(Untitled)", 3)] * 3, 267)
        self.assertEqual(entries, [])
        self.assertFalse(usable)

    def test_single_page_outline_is_not_usable(self):
        entries, usable = pdf.clean_outline([("Chapter 1", 4), ("Chapter 2", 4)], 20)
        self.assertEqual(len(entries), 2)
        self.assertFalse(usable, "one target page cannot navigate a book")

    def test_pages_are_clamped_to_the_document(self):
        entries, _ = pdf.clean_outline([("Chapter 1", 0), ("Chapter 2", 9999)], 50)
        self.assertEqual(entries, [("Chapter 1", 1), ("Chapter 2", 50)])


class HeadingDetectionTests(unittest.TestCase):
    def test_headings_are_read_from_the_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "headings.pdf"
            make_pdf(source)
            doc = pymupdf.open(str(source))
            found = pdf.detect_headings(doc, 11.0, doc.page_count, False, "Test Book", "A. Author")
            doc.close()
        self.assertEqual(found, [("PART ONE", 1), ("Chapter 1", 2), ("PART TWO", 3), ("Chapter 2", 4),
                                 ("Chapter 1", 5)],
                         "a title may repeat across parts; only near repeats are running heads")

    def test_identity_headings_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "identity.pdf"
            make_pdf(source, headings=("Test Book By A. Author", "Chapter 1", "Chapter 2"))
            doc = pymupdf.open(str(source))
            found = pdf.detect_headings(doc, 11.0, doc.page_count, False, "Test Book", "A. Author")
            doc.close()
        self.assertEqual(found, [("Chapter 1", 2), ("Chapter 2", 3)])


class ConvertedBookTests(unittest.TestCase):
    def test_empty_outline_builds_navigation_from_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp) / "in.pdf", pathlib.Path(tmp) / "out.html"
            make_pdf(source, outline=[])
            result = convert(source, out)
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
            book = out.read_text(encoding="utf-8")
        labels = [label for _, label in options(book)]
        self.assertIn("Chapter 1", labels)
        self.assertIn("PART ONE", labels)
        self.assertEqual(book.count('<option value="">Jump to a chapter&#8230;</option>'), 1)

    def test_degenerate_outline_is_replaced_and_the_build_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp) / "in.pdf", pathlib.Path(tmp) / "out.html"
            make_pdf(source, outline=[[1, "(Untitled)", 1], [1, "(Untitled)", 1], [1, "(Untitled)", 1]])
            result = convert(source, out)
            book = out.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertIn("WARNING: PDF outline unusable", result.stdout)
        self.assertNotIn("(Untitled)", book)
        self.assertIn("Chapter 1", [label for _, label in options(book)])
        self.assertIn("entries from the page headings", result.stdout)

    def test_usable_outline_passes_through_without_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp) / "in.pdf", pathlib.Path(tmp) / "out.html"
            make_pdf(source, outline=[[1, "Chapter 1", 2], [1, "Chapter 2", 4]])
            result = convert(source, out)
            book = out.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertNotIn("WARNING: PDF outline unusable", result.stdout)
        self.assertIn("entries from the PDF outline", result.stdout)
        self.assertIn("Chapter 2", [label for _, label in options(book)])

    def test_toc_headings_forces_the_page_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp) / "in.pdf", pathlib.Path(tmp) / "out.html"
            make_pdf(source, outline=[[1, "A Wrong Title", 2], [1, "Another Wrong Title", 4]])
            result = convert(source, out, "--toc", "headings")
            book = out.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        labels = [label for _, label in options(book)]
        self.assertNotIn("A Wrong Title", labels)
        self.assertIn("PART ONE", labels)

    def test_toc_none_leaves_navigation_empty_but_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = pathlib.Path(tmp) / "in.pdf", pathlib.Path(tmp) / "out.html"
            make_pdf(source, outline=[[1, "Chapter 1", 2], [1, "Chapter 2", 4]])
            result = convert(source, out, "--toc", "none")
            book = out.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertEqual(options(book), [])
        self.assertIn('class="source-page"', book)


if __name__ == "__main__":
    unittest.main()
