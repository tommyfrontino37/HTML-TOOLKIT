#!/usr/bin/env python3
"""build_enhanced.py - one command that turns a book HTML into the annotated edition.

    python3 build_enhanced.py --input book.html --output out.html \
        --title "Precious Remedies Against Satan's Devices" --author "Thomas Brooks" \
        --prefix brooks-remedies --slug precious-remedies --picker brooks-book

What it does:
  1. works on a copy (never your original),
  2. re-keys every storage name so two books on one machine cannot share annotations,
  3. runs the four patchers in order: dark mode -> highlights -> notes -> panel,
  4. checks the result (script syntax, key uniqueness, no leftovers from another book),
  5. runs the behaviour tests (unless --skip-tests).

Exit code 0 means every step passed.
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

TOOLKIT_DIR = os.path.dirname(os.path.abspath(__file__))
PATCHERS = ["add_dark_mode.py", "add_highlights.py", "add_notes.py", "add_panel.py",
            "add_dictionary.py"]

# every book-specific string the patchers carry, and what it becomes
SUBSTITUTIONS = [
    # paths first (they contain the title); quotes are left alone by anchoring inside them
    ('/home/user/uploads/The Doctrine of Repentance - Thomas Watson.html', '@WORKFILE@'),
    ('/home/user/The Doctrine of Repentance - Thomas Watson.html', '@WORKFILE@'),
    ('/home/user/dict_data.json', '@DICT@'),
    # slugs / identifiers
    ("watson-repentance", "@PREFIX@"),
    ("doctrine-of-repentance", "@SLUG@"),
    ("doctrine-book", "@PICKER@"),
    # the book's own name
    ("The Doctrine of Repentance", "@TITLE@"),
    ("Thomas Watson", "@AUTHOR@"),
]


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="the book HTML to build on")
    ap.add_argument("--output", required=True, help="where the finished book goes")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--prefix", required=True, help="storage key prefix, e.g. brooks-remedies")
    ap.add_argument("--slug", required=True, help="file-name slug, e.g. precious-remedies")
    ap.add_argument("--picker", required=True, help="file-picker id, e.g. brooks-book")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--no-dictionary", action="store_true",
                    help="skip the offline dictionary (smaller file)")
    ap.add_argument("--orig-views", action="store_true",
                    help="the book has an 'Original pages' view (pass to the tests)")
    args = ap.parse_args()

    fails = []
    print("=" * 74)
    print("BUILDING: %s  (%s)" % (args.title, args.author))
    print("=" * 74)

    workdir = os.path.join(os.path.dirname(os.path.abspath(args.output)), ".build_%s" % args.prefix.replace("/", "_"))
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    workfile = os.path.join(workdir, "book.html")
    shutil.copyfile(args.input, workfile)
    size0 = os.path.getsize(workfile)

    # The PDF converter starts from the Watson HTML shell.  That shell contains
    # Watson-specific localStorage identifiers, so re-key the copied HTML before
    # running the annotation patchers.  Otherwise every converted book can read
    # and write the same highlights, notes, theme, and file-handle data.
    base_rekeys = {
        "watson-repentance": args.prefix,
        "doctrine-of-repentance": args.slug,
        "doctrine-book": args.picker,
    }
    raw = io.open(workfile, encoding="utf-8").read()
    for old, new in base_rekeys.items():
        raw = raw.replace(old, new)
    io.open(workfile, "w", encoding="utf-8").write(raw)

    # a book must be self-contained: drop any <script src="..."> the shell brought along
    raw = io.open(workfile, encoding="utf-8").read()
    stripped = re.findall(r"<script\b[^>]*\bsrc=[^>]*>\s*</script>", raw)
    if stripped:
        raw = re.sub(r"<script\b[^>]*\bsrc=[^>]*>\s*</script>", "", raw)
        io.open(workfile, "w", encoding="utf-8").write(raw)
        print("   removed %d external script tag(s) so the book stays self-contained" % len(stripped))
    print("1. working copy: %s (%.1f MB)" % (workfile, size0 / 1e6))
    if os.path.exists(args.output):
        print("   (the existing output is left alone until a successful build)")

    # ---- the offline dictionary: only the words in this book, so it stays small
    if not args.no_dictionary:
        print("1b. offline dictionary")
        rc, out = run([sys.executable, os.path.join(TOOLKIT_DIR, "make_dict_data.py"),
                       "--book", workfile, "--out", os.path.join(workdir, "dict_data.json")])
        for line in out.strip().splitlines()[-3:]:
            print("   " + line.strip())
        if rc != 0:
            fails.append("dictionary data")

    # ---- re-key and run the patchers, in order
    print("2. patchers, in order")
    values = {"@WORKFILE@": workfile, "@DICT@": os.path.join(workdir, "dict_data.json"),
              "@PREFIX@": args.prefix, "@SLUG@": args.slug,
              "@PICKER@": args.picker, "@TITLE@": args.title, "@AUTHOR@": args.author}
    for name in PATCHERS:
        if name == "add_dictionary.py" and args.no_dictionary:
            print("   %-20s skipped (--no-dictionary)" % name)
            continue
        src_path = os.path.join(TOOLKIT_DIR, name)
        text = io.open(src_path, encoding="utf-8").read()
        for old, new in SUBSTITUTIONS:
            pass  # a patcher need not contain every string
            text = text.replace(old, values.get(new, new))
        staged = os.path.join(workdir, name)
        io.open(staged, "w", encoding="utf-8").write(text)
        rc, out = run([sys.executable, staged])
        ok_lines = re.findall(r"^ok\s+\[(.+?)\]", out, re.M)
        good = rc == 0 and ok_lines
        print("   %-20s %s  %s" % (name, "OK " if good else "FAIL", ", ".join(ok_lines) or out.strip()[:200]))
        if not good:
            fails.append("%s failed" % name)
            print(out[-1500:])
            break

    if not fails:
        # ---- checks
        print("3. checks")
        book = io.open(workfile, encoding="utf-8").read()
        checks = []

        checks.append(("doctype and closing tags",
                       book.startswith("<!DOCTYPE html>") and book.rstrip().endswith("</html>")))
        checks.append(("new key prefix present (%s-highlights)" % args.prefix,
                       ("'%s-highlights'" % args.prefix) in book))
        for stale, current in (("watson-repentance", args.prefix),
                               ("doctrine-book", args.picker),
                               ("doctrine-of-repentance", args.slug)):
            if stale != current:
                checks.append(("no leftover '%s'" % stale, stale not in book))
        checks.append(("book-specific annotation keys present", all(
            key in book for key in (
                args.prefix + "-highlights",
                args.prefix + "-notes",
                args.prefix + "-theme",
            )
        )))
        if args.title != "The Doctrine of Repentance":
            checks.append(("no leftover 'The Doctrine of Repentance'", "The Doctrine of Repentance" not in book))
        checks.append(("title present", args.title in book))
        checks.append(("one panel button set",
                       book.count('id="ann-bake"') == 1 and book.count('id="ann-overwrite"') == 1
                       and book.count('id="ann-open"') == 1))
        checks.append(("toolbar not duplicated",
                       book.count('id="theme-toggle"') == 1 and book.count('id="notes-toggle"') == 1))
        checks.append(("no baked block in the master",
                       book.count('<script type="application/json" id="baked-annotations">') == 0))
        res_refs = re.findall(r"<script\b[^>]*\bsrc=", book)
        res_refs += re.findall(r"<link\b[^>]*href=[\"']https?:", book)
        res_refs += re.findall(r"<img\b[^>]*src=[\"']https?:", book)
        checks.append(("self-contained (no external resources)", not res_refs))
        if not args.no_dictionary:
            n_dict = book.count('id="dict-data"')
            try:
                n_entries = len(json.loads(re.search(
                    r'<script type="application/json" id="dict-data">(.*?)</script>',
                    book, re.S).group(1).replace("\\u003c", "<")))
            except Exception:                                  # noqa: BLE001
                n_entries = 0
            checks.append(("dictionary data present (%d entries)" % n_entries,
                           n_dict == 1 and n_entries > 100))
            checks.append(("Define button wired", "dict-define" in book and "function lookup" in book))

        # extract every script and syntax-check it
        # only real JavaScript: skip data blocks (application/json) and external tags
        scripts = re.findall(
            r"<script(?![^>]*\bsrc=)(?![^>]*type=[\"'](?!text/javascript|module)[^\"']*[\"'])[^>]*>(.*?)</script>",
            book, re.S)
        bad = 0
        for i, body in enumerate(scripts):
            if not body.strip():
                continue
            tmp = os.path.join(workdir, "chk_%02d.js" % i)
            io.open(tmp, "w", encoding="utf-8").write(body)
            rc, out = run(["node", "--check", tmp])
            if rc != 0:
                bad += 1
                print("      script %d failed node --check: %s" % (i, out.strip()[:200]))
        checks.append(("all %d scripts pass node --check" % len(scripts), bad == 0))

        for label, ok, *rest in checks:
            print("   %s %s" % ("OK  " if ok else "FAIL", label))
            if not ok:
                fails.append("check: " + label)

    if not fails:
        shutil.copyfile(workfile, args.output)
        print("4. wrote %s (%.1f MB, from %.1f MB)" % (args.output, os.path.getsize(args.output) / 1e6, size0 / 1e6))

    if not fails and not args.skip_tests:
        print("5. behaviour tests")
        test = os.path.join(TOOLKIT_DIR, "run_tests.py")
        cmd = [sys.executable, test, "--book", args.output, "--title", args.title,
               "--prefix", args.prefix]
        if args.orig_views:
            cmd.append("--orig-views")
        rc, out = run(cmd, cwd=TOOLKIT_DIR)
        tail = out.strip().splitlines()
        for line in tail[-2:]:
            print("   " + line)
        if rc != 0:
            fails.append("behaviour tests")
            for line in tail:
                if "FAIL" in line or "Error" in line or "error" in line:
                    print("      " + line.strip()[:200])

    print("-" * 74)
    if fails:
        print("BUILD FAILED: " + "; ".join(fails))
        return 1
    print("BUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
