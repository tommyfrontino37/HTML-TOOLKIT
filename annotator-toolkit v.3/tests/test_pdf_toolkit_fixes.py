"""Regression tests for the PDF-reader fixes (no browser required).

Run from the toolkit directory:
    python -m unittest discover -s tests -v
"""

import importlib.util
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "pdf_to_book.py"
SPEC = importlib.util.spec_from_file_location("pdf_to_book_fixes", MODULE_PATH)
pdf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdf)


class FakePage:
    def __init__(self, blocks, text=""):
        self.blocks = blocks
        self.text = text

    def get_text(self, mode):
        if mode == "dict":
            return {"blocks": self.blocks}
        if mode == "text":
            return self.text
        raise AssertionError("unexpected text mode: " + mode)


def block(text, size):
    return {
        "type": 0,
        "lines": [{
            "spans": [{"text": text, "size": size, "flags": 0, "font": "Arial"}]
        }],
    }


class PdfToolkitFixTests(unittest.TestCase):
    def test_digit_runs_can_be_repaired_without_changing_default(self):
        source = "First published ٢٥٩١; page ١٤."
        self.assertEqual(pdf.clean_text(source), source)
        self.assertEqual(pdf.clean_text(source, True), "First published ١٩٥٢; page ٤١.")

    def test_auto_digit_order_only_triggers_for_latin_text(self):
        latin = "This is ordinary English text. " * 20 + "١٩٥٢"
        self.assertTrue(pdf.detect_reversed_arabic_digits(FakeDoc([latin])))
        self.assertFalse(pdf.detect_reversed_arabic_digits(FakeDoc(["English text " * 30])))
        self.assertFalse(pdf.detect_reversed_arabic_digits(FakeDoc([latin + " العربية"])))

    def test_drop_cap_moves_after_heading_and_rejoins_first_paragraph(self):
        page = FakePage([
            block("T", 42),
            block("PREFACE", 26),
            block("he contents of this book were first given on the air.", 15),
        ])
        result = pdf.build_reading_content(page, 15, 5, 182)
        self.assertNotIn(">T</span>", result)
        self.assertLess(result.index("PREFACE"), result.index("The contents"))
        self.assertIn("The contents of this book", result)

    def test_template_scrubber_removes_analytics_but_keeps_reader_scripts(self):
        source = (
            "<script>window.readerReady = true;</script>"
            "<script src=\"https://static.cloudflareinsights.com/beacon.js\"></script>"
            "<script>window.__CF$cv$params = {}; document.write('challenge-platform');</script>"
            "<link rel=\"stylesheet\" href=\"https://example.test/theme.css\">"
        )
        clean, count = pdf.sanitize_template(source)
        self.assertEqual(count, 2)
        self.assertIn("window.readerReady = true", clean)
        self.assertNotIn("cloudflareinsights", clean.lower())
        self.assertNotIn("challenge-platform", clean.lower())
        self.assertNotIn("https://example.test", clean)
        self.assertEqual(pdf.external_resource_references(clean), [])

    def test_identity_replacement_is_safe_for_quotes_and_script_terminators(self):
        source = (
            "<h1>The Doctrine of Repentance</h1>"
            "<script>const title = 'The Doctrine of Repentance';"
            "const author = 'Thomas Watson';</script>"
        )
        title = "Reader's <Guide> </script>"
        result = pdf.replace_book_identity(source, title, "A. Writer's Name")
        self.assertIn("Reader&#x27;s &lt;Guide&gt; &lt;/script&gt;", result)
        self.assertNotIn("The Doctrine of Repentance", result)
        self.assertNotIn("Thomas Watson", result)
        self.assertNotIn("</script>\nconst author", result)
        if shutil.which("node"):
            body = re.search(r"<script>(.*?)</script>", result, re.S).group(1)
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as script:
                script.write(body)
                script.flush()
                check = subprocess.run(["node", "--check", script.name], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_dictionary_can_be_replaced_or_removed(self):
        source = (
            '<style id="dict-style">.dict { color: red; }</style>'
            '<script type="application/json" id="dict-data">{"old":1}</script>'
            '<script id="dict-script">function lookup(){}</script>'
        )
        updated = pdf.set_dictionary_data(source, '{"book":1}')
        self.assertIn('id="dict-data">{"book":1}</script>', updated)
        stripped = pdf.strip_dictionary_assets(source)
        self.assertNotIn("dict-style", stripped)
        self.assertNotIn("dict-data", stripped)
        self.assertNotIn("dict-script", stripped)


class FakeDoc:
    def __init__(self, pages):
        self.pages = pages
        self.page_count = len(pages)

    def __getitem__(self, index):
        return FakePage([], self.pages[index])


if __name__ == "__main__":
    unittest.main()
