#!/usr/bin/env python3
"""Build a book HTML edition from either a text PDF or a paged HTML source.

PDF input (the reader shell already includes the annotation tools):
    python3 build_enhanced.py --input book.pdf --output out.html \
        --title "My Book" --author "A. Author" \
        --prefix my-book-a-author --slug my-book --picker my-book-file \
        [--facsimile webp] [--no-dictionary] [--skip-tests]

HTML input (adds the annotation tools to a pristine paged HTML source):
    python3 build_enhanced.py --input book.html --output out.html \
        --title "My Book" --author "A. Author" \
        --prefix my-book-a-author --slug my-book --picker my-book-file

PDF route: convert -> re-key -> rebuild book-specific dictionary -> check.
The PDF shell already has the annotator, so this route deliberately does NOT
run the non-idempotent patchers a second time.

HTML route: re-key -> dark mode -> highlights -> notes -> panel -> optional
dictionary -> check. Existing output files are replaced only after all checks
(and behavior tests, unless skipped) pass.
"""

import argparse
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

TOOLKIT_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLKIT_DIR not in sys.path:
    sys.path.insert(0, TOOLKIT_DIR)

from resource_checks import (  # noqa: E402
    external_resource_references,
    is_remote_resource_url,
    parse_start_tag_attributes,
)

PDF_CONVERTER = os.path.join(TOOLKIT_DIR, "pdf_to_book.py")
PATCHERS = [
    "add_dark_mode.py",
    "add_highlights.py",
    "add_notes.py",
    "add_panel.py",
    "add_dictionary.py",
]
SUBSTITUTIONS = [
    ('/home/user/uploads/The Doctrine of Repentance - Thomas Watson.html', '@WORKFILE@'),
    ('/home/user/The Doctrine of Repentance - Thomas Watson.html', '@WORKFILE@'),
    ('/home/user/dict_data.json', '@DICT@'),
    ("watson-repentance", "@PREFIX@"),
    ("doctrine-of-repentance", "@SLUG@"),
    ("doctrine-book", "@PICKER@"),
]
SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.I | re.S)


def run(command, **kwargs):
    try:
        process = subprocess.run(command, capture_output=True, text=True, **kwargs)
    except FileNotFoundError as error:
        return 127, str(error)
    return process.returncode, (process.stdout or "") + (process.stderr or "")


def _browser_launch_probe():
    """Launch headless Chromium exactly the way run_tests.py does.
    Returns (ok, raw_output)."""
    probe = (
        "from playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as pw:\n"
        "    browser = pw.chromium.launch()\n"
        "    browser.close()\n"
    )
    code, output = run([sys.executable, "-c", probe])
    return code == 0, output


def _launch_error_hint(output):
    # The real cause is the last `SomeError: message` line of the traceback;
    # everything after it is Playwright's box-drawn advice frame.
    lines = [line.strip().lstrip("║").strip()
             for line in (output or "").strip().splitlines()]
    tail = "unknown error"
    for line in lines:
        match = re.match(r"^[\w.]*(?:Error|Exception):\s*(.+)$", line)
        if match:
            tail = match.group(1).strip()
    return (
        "   Chromium cannot launch: %s\n"
        "   Fix it with:\n"
        "       python3 -m playwright install chromium\n"
        "       python3 -m playwright install-deps chromium   (needs sudo/root)\n"
        "   Or build without browser tests by adding --skip-tests."
        % tail[:220]
    )


def browser_preflight(auto_setup):
    """Ensure the behavior-test browser can launch; repair the environment if not.

    Fresh sessions start from a clean OS: pip packages may be present while the
    Chromium binary and its system libraries are not, and a hint-only abort
    still left the fix to a human (or another assistant) in every new session.
    So when the launch probe fails and auto_setup is enabled, install the
    browser, then the system libraries (sudo only when it works without a
    password), probing again after each step. Abort with the fix hint only if
    the repair fails or is disabled (--no-auto-setup). Returns (ok, hint).
    """
    ok, output = _browser_launch_probe()
    if ok:
        return True, ""
    if auto_setup:
        print("   Chromium cannot launch; repairing environment:")
        print("   1/2 python3 -m playwright install chromium")
        code, out = run([sys.executable, "-m", "playwright", "install", "chromium"])
        if code != 0:
            print("       " + (out.strip().splitlines() or ["failed"])[-1])
        ok, output = _browser_launch_probe()
        if not ok:
            sudo_code, _ = run(["sudo", "-n", "true"])
            if sudo_code == 0:
                print("   2/2 sudo -n python3 -m playwright install-deps chromium")
                code, out = run(["sudo", "-n", sys.executable, "-m",
                                 "playwright", "install-deps", "chromium"])
                if code != 0:
                    print("       " + (out.strip().splitlines() or ["failed"])[-1])
                ok, output = _browser_launch_probe()
        if ok:
            return True, ""
    return False, _launch_error_hint(output)


def is_pdf_file(path):
    if path.lower().endswith(".pdf"):
        return True
    try:
        with open(path, "rb") as source:
            return source.read(5) == b"%PDF-"
    except OSError:
        return False


def sanitize_remote_code(source):
    """Remove tracking/challenge scripts accidentally inherited from templates."""
    removed = 0

    def clean(match):
        nonlocal removed
        tag = match.group(0)
        opening = match.group(1).lower()
        markers = ("cloudflareinsights", "__cf$cv$params", "challenge-platform", "/cdn-cgi/")
        if "src" in parse_start_tag_attributes(opening) or any(marker in tag.lower() for marker in markers):
            removed += 1
            return ""
        return tag

    source = SCRIPT_RE.sub(clean, source)

    def clean_link(match):
        attributes = parse_start_tag_attributes(match.group(0))
        href = attributes.get("href", "")
        if is_remote_resource_url(href):
            return ""
        return match.group(0)

    source = re.sub(r"<link\b[^>]*>", clean_link, source, flags=re.I | re.S)
    return source, removed


def _python_string_contents(value):
    """Escape a value for a double-quoted Python string in a staged patcher."""
    return (str(value).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r", "\\r").replace("\n", "\\n"))


def _apply_patcher_substitutions(source, workfile, dictionary_path, args):
    values = {
        "@WORKFILE@": _python_string_contents(workfile),
        "@DICT@": _python_string_contents(dictionary_path),
        "@PREFIX@": args.prefix,
        "@SLUG@": args.slug,
        "@PICKER@": args.picker,
    }
    replacements = {old: values[token] for old, token in SUBSTITUTIONS}
    pattern = re.compile("|".join(re.escape(old) for old in sorted(replacements, key=len, reverse=True)))
    return pattern.sub(lambda match: replacements[match.group(0)], source)


def _configure_panel_identity(source, title, author):
    """Set safe Python string literals consumed by add_panel.py's JSON encoder."""
    for name, value in (("BOOK_TITLE", title), ("BOOK_AUTHOR", author)):
        pattern = re.compile(r"^%s\s*=.*$" % re.escape(name), re.M)
        source, count = pattern.subn(lambda _match: "%s = %r" % (name, value), source, count=1)
        if count != 1:
            raise ValueError("add_panel.py is missing the %s identity constant" % name)
    return source


def run_patchers(workfile, workdir, args, dictionary_path):
    print("2. patchers, in order (pristine HTML input)")
    for name in PATCHERS:
        if name == "add_dictionary.py" and args.no_dictionary:
            print("   %-20s skipped (--no-dictionary)" % name)
            continue
        path = os.path.join(TOOLKIT_DIR, name)
        with io.open(path, encoding="utf-8") as source:
            text = source.read()
        text = _apply_patcher_substitutions(text, workfile, dictionary_path, args)
        if name == "add_panel.py":
            text = _configure_panel_identity(text, args.title, args.author)
        staged = os.path.join(workdir, name)
        with io.open(staged, "w", encoding="utf-8") as output:
            output.write(text)
        code, output = run([sys.executable, staged])
        ok_lines = re.findall(r"^ok\s+\[(.+?)\]", output, re.M)
        good = code == 0 and bool(ok_lines)
        print("   %-20s %s  %s" % (name, "OK " if good else "FAIL", ", ".join(ok_lines) or output.strip()[:200]))
        if not good:
            print(output[-1500:])
            return False
    return True


def check_output(workfile, args, is_pdf, no_dictionary):
    with io.open(workfile, encoding="utf-8") as source:
        book = source.read()
    failures = []

    def check(label, condition):
        print("   %s %s" % ("OK  " if condition else "FAIL", label))
        if not condition:
            failures.append(label)

    check("doctype and closing tags", book.startswith("<!DOCTYPE html>") and book.rstrip().endswith("</html>"))
    check("book-specific highlights key", ("'%s-highlights'" % args.prefix) in book)
    check("book-specific notes key", ("'%s-notes'" % args.prefix) in book)
    check("book-specific theme key", ("'%s-theme'" % args.prefix) in book)
    chrome = re.sub(r'<main class="book">.*?</main>', "", book, flags=re.S)
    if args.prefix != "watson-repentance":
        check("no old Watson storage keys", "watson-repentance" not in chrome)
    if args.slug != "doctrine-of-repentance" or args.picker != "doctrine-book":
        check("no old book slug/picker",
              (args.slug == "doctrine-of-repentance" or "doctrine-of-repentance" not in chrome)
              and (args.picker == "doctrine-book" or "doctrine-book" not in chrome))
    if args.title != "The Doctrine of Repentance" or args.author != "Thomas Watson":
        check("no old sample title/author",
              (args.title == "The Doctrine of Repentance" or "The Doctrine of Repentance" not in chrome)
              and (args.author == "Thomas Watson" or "Thomas Watson" not in chrome))
    check("book title present", args.title in book or html.escape(args.title, quote=True) in book)
    check("one panel button set", all(book.count('id="%s"' % item) == 1 for item in ("ann-bake", "ann-overwrite", "ann-open")))
    check("one toolbar set", all(book.count('id="%s"' % item) == 1 for item in ("theme-toggle", "notes-toggle")))
    check("no pre-baked annotations", book.count('<script type="application/json" id="baked-annotations">') == 0)

    references = external_resource_references(book)
    check("self-contained: no external or sidecar resources", not references)
    if references:
        for reference in references[:5]:
            print("        resource: " + reference[:240])
        if len(references) > 5:
            print("        and %d more" % (len(references) - 5))
    check("no Cloudflare tracking/challenge", all(value not in book.lower() for value in ("cloudflareinsights", "__cf$cv$params", "challenge-platform", "/cdn-cgi/")))

    if no_dictionary:
        check("dictionary controls removed (--no-dictionary)", all(value not in book for value in ('id="dict-data"', 'id="dict-script"', 'id="dict-style"')))
    else:
        blocks = re.findall(r'<script type="application/json" id="dict-data">(.*?)</script>', book, re.S)
        try:
            dictionary = json.loads(blocks[0].replace(r"\u003c", "<")) if len(blocks) == 1 else {}
        except Exception:
            dictionary = {}
        check("book-specific dictionary data present", len(blocks) == 1 and len(dictionary) > 0)
        check("dictionary Define hook present", 'id="dict-script"' in book and "function lookup" in book)

    if is_pdf:
        check("PDF pages converted", book.count('class="source-page"') > 0)
        page_layer = re.sub(r"<script\b.*?</script\s*>", "", book, flags=re.I | re.S)
        headings = len(re.findall(r"<h2[^>]*>", page_layer))
        destinations = len(re.findall(r'<option value="\d+">', page_layer))
        print("   %s navigation has %d destination(s) for %d heading(s) on the page layer"
              % ("OK  " if destinations or not headings else "WARN", destinations, headings))
        if headings and not destinations:
            print("        the book has headings but no navigation; rebuild with --toc headings")
    if not shutil.which("node"):
        if args.require_node:
            check("Node.js is installed for script checks", False)
        else:
            print("   SKIP all inline JavaScript passes node --check (Node.js not installed; "
                  "install it, or pass --require-node to make this fatal)")
    else:
        scripts = []
        for opening, body, _closing in SCRIPT_RE.findall(book):
            if "src=" not in opening.lower() and "application/json" not in opening.lower():
                scripts.append(body)
        bad = 0
        with tempfile.TemporaryDirectory(prefix=".js-check-") as temp_dir:
            for index, body in enumerate(scripts):
                if not body.strip():
                    continue
                script_path = os.path.join(temp_dir, "script-%03d.js" % index)
                with io.open(script_path, "w", encoding="utf-8") as script_file:
                    script_file.write(body)
                code, _ = run(["node", "--check", script_path])
                bad += int(code != 0)
        check("all inline JavaScript passes node --check", bad == 0)
    return not failures, failures


def main():
    parser = argparse.ArgumentParser(description="Build a paged, annotated HTML book from PDF or pristine HTML.")
    parser.add_argument("--input", required=True, help="text PDF or pristine paged HTML")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--prefix", required=True, help="unique annotation prefix, e.g. my-book-author")
    parser.add_argument("--slug", required=True, help="download/book slug, e.g. my-book")
    parser.add_argument("--picker", required=True, help="unique file-picker id, e.g. my-book-file")
    parser.add_argument("--skip-tests", action="store_true", help="skip Playwright behavior tests")
    parser.add_argument("--no-auto-setup", action="store_true",
                        help="do not auto-install Chromium / its system libraries "
                             "when the behavior-test browser cannot launch")
    parser.add_argument("--no-dictionary", action="store_true", help="omit the offline dictionary")
    parser.add_argument("--orig-views", action="store_true", help="HTML input has Original pages view")
    parser.add_argument("--facsimile", choices=["none", "webp"], default="none", help="PDF-only original-page images")
    parser.add_argument("--dpi", type=int, default=90, help="PDF facsimile resolution (36-240)")
    parser.add_argument("--quality", type=int, default=50, help="PDF WebP quality (1-100)")
    parser.add_argument("--digit-order", choices=["auto", "normal", "reverse-arabic"], default="auto",
                        help="PDF-only order handling for Arabic-Indic digit runs")
    parser.add_argument("--toc", choices=["auto", "pdf", "headings", "none"], default="auto",
                        help="PDF-only navigation source: auto (outline when usable, else page headings), "
                             "pdf, headings, none")
    parser.add_argument("--require-node", action="store_true",
                        help="fail when Node.js is missing instead of skipping the inline-JS syntax check")
    parser.add_argument("--dict-word", default="",
                        help="word the behavior tests use for the Define check "
                             "(default: chosen from the book's own dictionary)")
    args = parser.parse_args()

    for field in ("prefix", "slug", "picker"):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", getattr(args, field)):
            parser.error("--%s must use lowercase letters, numbers, and hyphens only" % field)

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)
    if not os.path.isfile(input_path):
        parser.error("input not found: " + input_path)
    if input_path == output_path:
        parser.error("input and output paths must be different")
    pdf_input = is_pdf_file(input_path)
    output_dir = os.path.dirname(output_path) or "."

    print("=" * 74)
    print("BUILDING: %s (%s)" % (args.title, args.author))
    print("INPUT ROUTE: %s" % ("PDF conversion" if pdf_input else "HTML annotation"))
    print("=" * 74)

    if not args.skip_tests:
        # Launch the browser the way run_tests.py will, before any heavy work:
        # a missing Chromium or missing system libraries used to burn the whole
        # pipeline and then fail late, inside Playwright's debug output.
        print("PRECHECK: behavior-test browser")
        browser_ok, browser_hint = browser_preflight(not args.no_auto_setup)
        if not browser_ok:
            print(browser_hint)
            print("BUILD FAILED: Chromium cannot launch (see precheck above)", file=sys.stderr)
            return 1
        print("   Chromium launches ok")

    os.makedirs(output_dir, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix=".build-%s-" % args.prefix, dir=output_dir)
    workfile = os.path.join(workdir, "book.html")
    dictionary_path = os.path.join(workdir, "dict_data.json")
    failures = []

    try:
        if pdf_input:
            # pdf_to_book already uses the fully-featured shell. Running the
            # patchers again would duplicate controls and break their anchors.
            command = [
                sys.executable, PDF_CONVERTER,
                "--pdf", input_path,
                "--out", workfile,
                "--title", args.title,
                "--author", args.author,
                "--prefix", args.prefix,
                "--slug", args.slug,
                "--picker", args.picker,
                "--facsimile", args.facsimile,
                "--dpi", str(args.dpi),
                "--quality", str(args.quality),
                "--digit-order", args.digit_order,
                "--toc", args.toc,
            ]
            if args.no_dictionary:
                command.append("--no-dictionary")
            code, output = run(command, cwd=TOOLKIT_DIR)
            print(output.strip())
            if code != 0:
                failures.append("PDF conversion")
        else:
            shutil.copyfile(input_path, workfile)
            with io.open(workfile, encoding="utf-8") as source:
                raw = source.read()
            if any(marker in raw for marker in ('id="ann-bake"', 'id="ann-open"', 'id="hl-pop"')):
                raise ValueError("HTML already contains toolkit annotations; patchers are not idempotent. Use the pristine source.")
            for old, new in {
                "watson-repentance": args.prefix,
                "doctrine-of-repentance": args.slug,
                "doctrine-book": args.picker,
            }.items():
                raw = raw.replace(old, new)
            raw, removed = sanitize_remote_code(raw)
            with io.open(workfile, "w", encoding="utf-8") as output:
                output.write(raw)
            if removed:
                print("removed %d analytics/remote script(s)" % removed)

            if not args.no_dictionary:
                print("1. book-specific offline dictionary")
                code, output = run(
                    [sys.executable, os.path.join(TOOLKIT_DIR, "make_dict_data.py"),
                     "--book", workfile, "--out", dictionary_path],
                    cwd=TOOLKIT_DIR,
                )
                print("\n".join(output.strip().splitlines()[-4:]))
                if code != 0:
                    failures.append("dictionary data")
            if not failures and not run_patchers(workfile, workdir, args, dictionary_path):
                failures.append("HTML patchers")

        if not failures:
            print("CHECKS")
            passed, check_failures = check_output(workfile, args, pdf_input, args.no_dictionary)
            if not passed:
                failures.extend("check: " + name for name in check_failures)

        if not failures and not args.skip_tests:
            with io.open(workfile, encoding="utf-8") as check_file:
                behavior_page_count = check_file.read().count('class="source-page"')
            if behavior_page_count < 20:
                print("BEHAVIOR TESTS: skipped for short document (<20 pages); structural checks passed")
            else:
                print("BEHAVIOR TESTS")
                command = [
                    sys.executable,
                    os.path.join(TOOLKIT_DIR, "run_tests.py"),
                    "--book", workfile,
                    "--title", args.title,
                    "--prefix", args.prefix,
                ]
                if args.dict_word:
                    command += ["--dict-word", args.dict_word]
                if args.orig_views or (pdf_input and args.facsimile == "webp"):
                    command.append("--orig-views")
                code, output = run(command, cwd=TOOLKIT_DIR)
                print("\n".join(output.strip().splitlines()[-8:]))
                if code != 0:
                    failures.append("behavior tests failed (output above; if the browser "
                                    "broke mid-run, fix the environment or use --skip-tests)")

        if failures:
            print("BUILD FAILED: " + "; ".join(failures), file=sys.stderr)
            return 1

        # Atomic replace: a failed build never destroys a previous deliverable.
        fd, temp_output = tempfile.mkstemp(prefix=".book-final-", suffix=".html", dir=output_dir)
        os.close(fd)
        try:
            shutil.copyfile(workfile, temp_output)
            os.replace(temp_output, output_path)
        except Exception:
            try:
                os.unlink(temp_output)
            except OSError:
                pass
            raise
        print("BUILD OK: %s (%.1f MB)" % (output_path, os.path.getsize(output_path) / 1e6))
        return 0
    except Exception as error:
        print("BUILD FAILED: %s" % error, file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
