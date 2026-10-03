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
    ("The Doctrine of Repentance", "@TITLE@"),
    ("Thomas Watson", "@AUTHOR@"),
]
SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.I | re.S)


def run(command, **kwargs):
    try:
        process = subprocess.run(command, capture_output=True, text=True, **kwargs)
    except FileNotFoundError as error:
        return 127, str(error)
    return process.returncode, (process.stdout or "") + (process.stderr or "")


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
        if "src=" in opening or any(marker in tag.lower() for marker in markers):
            removed += 1
            return ""
        return tag

    source = SCRIPT_RE.sub(clean, source)
    source = re.sub(r'<link[^>]*href="https?://[^"]+"[^>]*>', "", source, flags=re.I)
    return source, removed


def run_patchers(workfile, workdir, args, dictionary_path):
    values = {
        "@WORKFILE@": workfile,
        "@DICT@": dictionary_path,
        "@PREFIX@": args.prefix,
        "@SLUG@": args.slug,
        "@PICKER@": args.picker,
        "@TITLE@": args.title,
        "@AUTHOR@": args.author,
    }
    print("2. patchers, in order (pristine HTML input)")
    for name in PATCHERS:
        if name == "add_dictionary.py" and args.no_dictionary:
            print("   %-20s skipped (--no-dictionary)" % name)
            continue
        path = os.path.join(TOOLKIT_DIR, name)
        with io.open(path, encoding="utf-8") as source:
            text = source.read()
        for old, new in SUBSTITUTIONS:
            text = text.replace(old, values.get(new, new))
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

    references = re.findall(r'<script[^>]*src=', book, re.I)
    references += re.findall(r'<link[^>]*href="https?://', book, re.I)
    references += re.findall(r'<img[^>]*src="https?://', book, re.I)
    check("self-contained: no external resources", not references)
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
    if not shutil.which("node"):
        check("Node.js is installed for script checks", False)
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
    parser.add_argument("--no-dictionary", action="store_true", help="omit the offline dictionary")
    parser.add_argument("--orig-views", action="store_true", help="HTML input has Original pages view")
    parser.add_argument("--facsimile", choices=["none", "webp"], default="none", help="PDF-only original-page images")
    parser.add_argument("--dpi", type=int, default=90, help="PDF facsimile resolution (36-240)")
    parser.add_argument("--quality", type=int, default=50, help="PDF WebP quality (1-100)")
    parser.add_argument("--digit-order", choices=["auto", "normal", "reverse-arabic"], default="auto",
                        help="PDF-only order handling for Arabic-Indic digit runs")
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
    os.makedirs(output_dir, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix=".build-%s-" % args.prefix, dir=output_dir)
    workfile = os.path.join(workdir, "book.html")
    dictionary_path = os.path.join(workdir, "dict_data.json")
    failures = []

    print("=" * 74)
    print("BUILDING: %s (%s)" % (args.title, args.author))
    print("INPUT ROUTE: %s" % ("PDF conversion" if pdf_input else "HTML annotation"))
    print("=" * 74)

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
            elif not shutil.which("node"):
                failures.append("Node.js is required for the behavior tests")
            else:
                playwright_code, _ = run([sys.executable, "-c", "import playwright"])
                if playwright_code != 0:
                    failures.append("behavior tests need Playwright (install it or use --skip-tests)")
                else:
                    print("BEHAVIOR TESTS")
                    command = [
                        sys.executable,
                        os.path.join(TOOLKIT_DIR, "run_tests.py"),
                        "--book", workfile,
                        "--title", args.title,
                        "--prefix", args.prefix,
                    ]
                    if args.orig_views or (pdf_input and args.facsimile == "webp"):
                        command.append("--orig-views")
                    code, output = run(command, cwd=TOOLKIT_DIR)
                    print("\n".join(output.strip().splitlines()[-8:]))
                    if code != 0:
                        failures.append("behavior tests (install Playwright/Chromium system dependencies or use --skip-tests)")

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
