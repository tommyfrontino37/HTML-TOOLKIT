"""Regression tests for offline-resource validation and safe HTML patching."""

import ast
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import pymupdf
from unittest import mock

TOOLKIT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from resource_checks import external_resource_references  # noqa: E402


def load_builder():
    path = TOOLKIT_DIR / "build_enhanced.py"
    spec = importlib.util.spec_from_file_location("build_enhanced_hardening", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_builder()


def load_pdf_converter():
    path = TOOLKIT_DIR / "pdf_to_book.py"
    spec = importlib.util.spec_from_file_location("pdf_to_book_hardening", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pdf_converter = load_pdf_converter()


class OfflineResourceTests(unittest.TestCase):
    def test_scanner_finds_remote_and_sidecar_dependencies(self):
        source = """
        <link rel='stylesheet' href = 'https://cdn.example.test/book.css'>
        <script src = \"https://cdn.example.test/book.js\"></script>
        <style>@import 'https://cdn.example.test/more.css';
               .cover { background-image: url(//img.example.test/cover.webp); }</style>
        <div style=\"background-image:url('../cover.png')\"></div>
        <div style=\"background-image:image-set('https://img.example.test/retina.png' 2x)\"></div>
        <iframe src='https://reader.example.test/'></iframe>
        <video poster=\"https://media.example.test/poster.jpg\"></video>
        <img srcset='data:image/png;base64,AAAA 1x, https://img.example.test/large.png 2x'>
        """
        references = external_resource_references(source)
        self.assertTrue(any("book.css" in item for item in references), references)
        self.assertTrue(any("book.js" in item for item in references), references)
        self.assertTrue(any("more.css" in item for item in references), references)
        self.assertTrue(any("cover.webp" in item for item in references), references)
        self.assertTrue(any("../cover.png" in item for item in references), references)
        self.assertTrue(any("retina.png" in item for item in references), references)
        self.assertTrue(any("reader.example.test" in item for item in references), references)
        self.assertTrue(any("poster.jpg" in item for item in references), references)
        self.assertTrue(any("large.png" in item for item in references), references)

    def test_embedded_data_fragments_and_outbound_anchors_are_allowed(self):
        source = """
        <a href='https://example.test/ordinary-link'>Outbound link</a>
        <img src='data:image/png;base64,AAAA'>
        <svg><use href='#local-symbol'></use></svg>
        <div style='mask:url(#local-mask); background:url(data:image/png;base64,BBBB)'></div>
        """
        self.assertEqual(external_resource_references(source), [])

    def test_sanitizer_handles_single_quotes_and_spaces_around_equals(self):
        source = (
            "<script SRC = 'https://cdn.example.test/tracker.js'></script>"
            "<link rel='stylesheet' href = 'https://cdn.example.test/theme.css'>"
            "<script>window.readerReady = true;</script>"
        )
        clean, removed_scripts = builder.sanitize_remote_code(source)
        self.assertEqual(removed_scripts, 1)
        self.assertNotIn("tracker.js", clean)
        self.assertNotIn("theme.css", clean)
        self.assertIn("window.readerReady = true", clean)
        self.assertEqual(external_resource_references(clean), [])

    def test_pdf_template_scrubber_handles_attribute_spacing_and_quotes(self):
        source = (
            "<script src = \\\"https://cdn.example.test/remote.js\\\"></script>"
            "<link rel='stylesheet' href = 'https://cdn.example.test/remote.css'>"
            "<script>window.readerReady = true;</script>"
        )
        clean, removed_scripts = pdf_converter.sanitize_template(source)
        self.assertEqual(removed_scripts, 1)
        self.assertNotIn("remote.js", clean)
        self.assertNotIn("remote.css", clean)
        self.assertIn("window.readerReady = true", clean)
        self.assertEqual(external_resource_references(clean), [])

    def test_build_check_rejects_remote_css_urls(self):
        book = """<!DOCTYPE html>
        <html><head><title>Test book</title>
        <style>.cover{background-image:url(https://cdn.example.test/cover.png)}</style>
        </head><body>
        test-book-highlights test-book-notes test-book-theme
        <button id='ann-bake'></button><button id='ann-overwrite'></button><button id='ann-open'></button>
        <button id='theme-toggle'></button><button id='notes-toggle'></button>
        </body></html>"""
        args = SimpleNamespace(
            prefix="test-book", slug="test-book", picker="test-book-file",
            title="Test book", author="A Writer", require_node=False,
        )
        with tempfile.TemporaryDirectory() as temporary, mock.patch("builtins.print"):
            path = pathlib.Path(temporary) / "book.html"
            path.write_text(book, encoding="utf-8")
            passed, failures = builder.check_output(str(path), args, False, True)
        self.assertFalse(passed)
        self.assertIn("self-contained: no external or sidecar resources", failures)


class PdfFrontMatterTests(unittest.TestCase):
    def test_searchable_text_after_forty_front_matter_pages_is_converted(self):
        text = "Searchable body text appears after forty blank front-matter pages."
        with tempfile.TemporaryDirectory() as temporary:
            source = pathlib.Path(temporary) / "front-matter.pdf"
            output = pathlib.Path(temporary) / "converted.html"
            document = pymupdf.open()
            for _ in range(40):
                document.new_page()
            page = document.new_page()
            page.insert_text((72, 100), text, fontsize=12)
            document.save(source)
            document.close()

            result = subprocess.run(
                [sys.executable, str(TOOLKIT_DIR / "pdf_to_book.py"),
                 "--pdf", str(source), "--out", str(output),
                 "--title", "Front Matter Test", "--author", "A. Writer",
                 "--no-dictionary", "--toc", "none"],
                cwd=str(TOOLKIT_DIR), capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
            self.assertIn(text, output.read_text(encoding="utf-8"))


class SafePatcherGenerationTests(unittest.TestCase):
    def test_replacements_are_simultaneous_not_cascading(self):
        args = SimpleNamespace(
            prefix="doctrine-of-repentance", slug="fresh-book", picker="fresh-book-file",
        )
        source = "watson-repentance | doctrine-of-repentance | doctrine-book"
        result = builder._apply_patcher_substitutions(source, "/tmp/book.html", "/tmp/dict.json", args)
        self.assertEqual(result, "doctrine-of-repentance | fresh-book | fresh-book-file")

    def test_paths_are_escaped_for_staged_python_strings(self):
        args = SimpleNamespace(prefix="safe-book", slug="safe-book", picker="safe-book-file")
        path = '/tmp/a "quoted"\\book.html'
        source = 'PATH = "/home/user/The Doctrine of Repentance - Thomas Watson.html"'
        result = builder._apply_patcher_substitutions(source, path, "/tmp/dict.json", args)
        self.assertEqual(ast.literal_eval(result.split("=", 1)[1].strip()), path)

    def test_book_identity_is_safe_in_inline_javascript_and_report_html(self):
        title = 'A "quoted" `title` ${globalThis.pwned = true} </script>'
        author = "O'Reilly ${globalThis.authorPwned = true} </script>"
        panel_path = TOOLKIT_DIR / "add_panel.py"
        source = panel_path.read_text(encoding="utf-8")
        configured = builder._configure_panel_identity(source, title, author)
        tree = ast.parse(configured)

        constants = {}
        panel_js_literal = None
        json_helper = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in ("BOOK_TITLE", "BOOK_AUTHOR"):
                    constants[name] = ast.literal_eval(node.value)
                elif name == "PANEL_JS" and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    panel_js_literal = node.value.value
            elif isinstance(node, ast.FunctionDef) and node.name == "_js_json_literal":
                json_helper = node

        self.assertEqual(constants, {"BOOK_TITLE": title, "BOOK_AUTHOR": author})
        self.assertIsNotNone(panel_js_literal)
        self.assertIsNotNone(json_helper)

        namespace = {"json": json}
        helper_module = ast.Module(body=[json_helper], type_ignores=[])
        exec(compile(helper_module, str(panel_path), "exec"), namespace)
        panel_js = panel_js_literal.replace("__BOOK_TITLE_JSON__", namespace["_js_json_literal"](title))
        panel_js = panel_js.replace("__BOOK_AUTHOR_JSON__", namespace["_js_json_literal"](author))
        script = panel_js.split("<script>", 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</script>", script)
        self.assertIn(r"\u003c/script>", script)
        self.assertIn("${esc(BOOK_TITLE)}", panel_js)
        self.assertIn("${esc(BOOK_AUTHOR)}", panel_js)

        if shutil.which("node"):
            declarations = "\n".join(
                line.strip() for line in script.splitlines()
                if "const BOOK_TITLE =" in line or "const BOOK_AUTHOR =" in line
            )
            probe = declarations + "\nconsole.log(JSON.stringify([BOOK_TITLE, BOOK_AUTHOR, typeof globalThis.pwned]));"
            result = subprocess.run(["node", "-e", probe], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [title, author, "undefined"])
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as staged_js:
                staged_js.write(script)
                staged_js.flush()
                syntax = subprocess.run(
                    ["node", "--check", staged_js.name], capture_output=True, text=True,
                )
            self.assertEqual(syntax.returncode, 0, syntax.stderr)


if __name__ == "__main__":
    unittest.main()
