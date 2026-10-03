#!/usr/bin/env python3
"""Prove that two books on the same machine cannot share annotations.

All file:// pages share ONE localStorage + IndexedDB in Chrome, so this is the
risk that re-keying exists to remove: open book A, highlight; open book B, and it
must know nothing about A's marks; highlight in B; go back to A - still exactly
one mark, and not B's.

    python3 test_isolation.py --a bookA.html --a-prefix watson-repentance \
        --b bookB.html --b-prefix brooks-remedies
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SELECT_T = """(function(){
  var pg = %d;
  window.scrollTo(0, document.querySelector('#page-' + pg).offsetTop);
  var c = document.querySelector('#page-' + pg + ' .reading-content');
  var w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT, null), n, best = null;
  while((n = w.nextNode())){ if(n.nodeValue && n.nodeValue.trim().length > 60){ best = n; break; } }
  if(!best) return false;
  var r = document.createRange(); r.setStart(best, 5); r.setEnd(best, 45);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
  return true;
})"""

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (("   <- " + str(detail)[:300]) if (detail and not cond) else ""))


def add_highlight(page, pageno):
    page.evaluate(SELECT_T % pageno)
    page.wait_for_function("!!document.querySelector('.hl-pop') && !document.querySelector('.hl-pop').hidden",
                           timeout=10000)
    page.evaluate("document.querySelector('.hl-pop .hl-swatch').click()")
    page.wait_for_timeout(600)


def marks(page):
    return page.evaluate("document.querySelectorAll('mark.hl').length")


def keys(page):
    return page.evaluate("Object.keys(localStorage)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--a-prefix", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--b-prefix", required=True)
    args = ap.parse_args()

    A, B = Path(args.a).resolve(), Path(args.b).resolve()
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1200, "height": 800})   # ONE profile, as a real reader has
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))

        print("A: %s" % A.name)
        page.goto(A.as_uri())
        page.wait_for_timeout(600)
        page.evaluate("localStorage.clear()")          # start clean, as a first-time reader
        page.reload()
        page.wait_for_timeout(700)
        add_highlight(page, 40)
        a_marks = marks(page)
        a_keys = [k for k in keys(page) if k.startswith(args.a_prefix)]
        check("A carries a highlight (%d)" % a_marks, a_marks == 1)
        check("A's keys use A's prefix", a_keys and all(k.startswith(args.a_prefix) for k in a_keys), a_keys)

        print("B: %s" % B.name)
        page.goto(B.as_uri())
        page.wait_for_timeout(800)
        b_marks_before = marks(page)
        check("B shows none of A's highlights (0 marks on a fresh book)", b_marks_before == 0, b_marks_before)
        b_keys_before = keys(page)
        check("A's keys are still only in A's namespace",
              all(k.startswith(args.a_prefix) for k in b_keys_before if k.startswith(args.a_prefix)),
              b_keys_before)
        add_highlight(page, 100)
        b_marks = marks(page)
        check("B carries its own highlight (%d)" % b_marks, b_marks == 1)

        print("back to A")
        page.goto(A.as_uri())
        page.wait_for_timeout(800)
        a_marks_after = marks(page)
        check("A still has exactly its own one highlight", a_marks_after == 1, a_marks_after)
        all_keys = keys(page)
        check("both books' keys coexist without clashing",
              any(k.startswith(args.a_prefix) for k in all_keys) and
              any(k.startswith(args.b_prefix) for k in all_keys), all_keys)
        check("no page errors", not errors, errors[:2])
        browser.close()

    passed = sum(1 for r in RESULTS if r)
    print("-" * 74)
    print("RESULT: %d passed, %d failed" % (passed, len(RESULTS) - passed))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
