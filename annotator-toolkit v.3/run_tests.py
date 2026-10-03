#!/usr/bin/env python3
"""run_tests.py - behaviour tests for an annotated book.

    python3 run_tests.py --book out.html --title "..." --prefix brooks-remedies [--orig-views]

Drives the real file in headless Chromium: highlighting, notes, hide/show, the
panel, Go to (in both views when the book has them), Export, Save into HTML and
Save over my book (with a stubbed file dialog, since headless cannot show the
real one).  Also proves the re-keying: nothing may be written under another
book's keys.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RESULTS = []

DICT_DATA_RE = re.compile(
    r'<script type="application/json" id="dict-data">(.*?)</script>', re.S)


def choose_dict_probe(book_path, preferred=""):
    """Pick a probe word this book can actually define.

    The offline dictionary holds only the book's own vocabulary, so a
    hard-coded probe word (as this suite once used) fails on any book that
    never uses it, while the feature itself works fine. Prefer an explicit
    --dict-word; otherwise take the longest dictionary word that also appears
    in the visible text.
    """
    try:
        source = Path(book_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = DICT_DATA_RE.search(source)
    if not match:
        return ""
    try:
        entries = json.loads(match.group(1).replace("\\u003c", "<"))
    except ValueError:
        return ""

    preferred = (preferred or "").strip().lower()
    if preferred:
        if preferred in entries:
            return preferred
        print("  ! --dict-word %r is not in this book's dictionary; choosing one instead"
              % preferred)

    body = " ".join(re.findall(r'<div class="reading-content">(.*?)</div>', source, re.S))
    body = re.sub(r"<[^>]+>", " ", body).lower()
    for word in sorted((w for w in entries if isinstance(w, str) and re.fullmatch(r"[a-z]{5,12}", w)),
                       key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(word), body):
            return word
    return ""


def check(name, cond, detail=""):
    RESULTS.append((bool(cond), name))
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (("   <- " + str(detail)[:260]) if (detail and not cond) else ""))


STUB = r"""
window.__ow = {writes:0, picks:0, perm:'granted', failStep:null, failName:'',
              bookText: window.__STUB_BOOKTEXT || ''};
window.showOpenFilePicker = async function(){
  var H = window.__ow; H.picks++;
  if(H.abortPick) throw Object.assign(new Error('cancelled'), {name:'AbortError'});
  return [{
    name: 'The Book.html',
    getFile: async function(){ return { text: async function(){ return H.bookText; } }; },
    queryPermission: async function(){ return H.perm; },
    requestPermission: async function(){ H.perm = 'granted'; return 'granted'; },
    createWritable: async function(){
      if(H.failStep === 'createWritable') throw Object.assign(new Error('no'), {name: H.failName || 'NotAllowedError'});
      return {
        write: async function(s){ if(H.failStep === 'write')
            throw Object.assign(new Error('no'), {name: H.failName || 'NotAllowedError'});
          H.writes++; H.blocks = (String(s).match(/<script type="application\/json" id="baked-annotations">/g) || []).length;
          H.mode = /<body[^>]*data-mode="reading"/.test(String(s)) ? 'reading' : 'other'; },
        close: async function(){}
      };
    }
  }];
};
"""

SELECT_T = """(function(){
  var pg = %d, s0 = %d, e0 = %d;
  window.scrollTo(0, document.querySelector('#page-' + pg).offsetTop);
  var c = document.querySelector('#page-' + pg + ' .reading-content');
  var w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT, null), n, best = null;
  while((n = w.nextNode())){ if(n.nodeValue && n.nodeValue.trim().length > 60){ best = n; break; } }
  if(!best) return false;
  var r = document.createRange(); r.setStart(best, s0); r.setEnd(best, e0);
  var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
  return true;
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--orig-views", action="store_true")
    ap.add_argument("--page", type=int, default=0, help="a mid-book page to test in")
    ap.add_argument("--dict-word", default="",
                    help="word used for the Define test (default: chosen from the book's own dictionary)")
    args = ap.parse_args()

    book = Path(args.book).resolve()
    errors = []
    downloads = []

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(accept_downloads=True, viewport={"width": 1200, "height": 800})
        page = ctx.new_page()
        page.add_init_script(STUB.replace("window.__STUB_BOOKTEXT", json.dumps(
            '<div id="view-mode"></div><div class="reading-content"></div>' + args.title)))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("download", lambda d: downloads.append(d))
        page.goto(book.as_uri())
        page.wait_for_timeout(600)

        def js(code, arg=None):
            if arg is not None:
                code = code % tuple(arg)
            return page.evaluate(code)

        def click(sel):
            return page.evaluate("(function(){ var e = document.querySelector(%s);"
                                 " if(e){ e.click(); return true; } return false; })()" % json.dumps(sel))

        def wait(expr, ms=10000):
            page.wait_for_function(expr, timeout=ms)

        total = js("document.querySelectorAll('.source-page').length")
        check("the book has pages (%d)" % total, total > 20)
        test_page = args.page or max(2, total // 2)
        # the guard looks for the view-mode id, the reading text layer and the title
        pass

        # ---------------------------------------------------------------- tools
        check("dark-mode toggle present", js("!!document.querySelector('#theme-toggle')"))
        check("notes toggle present", js("!!document.querySelector('#notes-toggle')"))
        check("panel button present", js("!!document.querySelector('#ann-open')"))
        check("exactly four highlight colours",
              js("new Set(Array.from(document.querySelectorAll('.hl-swatch'))"
                 ".map(function(b){return getComputedStyle(b).backgroundColor;})).size") == 4)

        # ---------------------------------------------------------------- highlight
        js("localStorage.clear()")
        page.reload()
        page.wait_for_timeout(600)
        check("a sentence can be selected on page %d" % test_page, js(SELECT_T, [test_page, 5, 45]))
        wait("!!document.querySelector('.hl-pop') && !document.querySelector('.hl-pop').hidden")
        click(".hl-pop .hl-swatch")
        wait("(JSON.parse(localStorage.getItem('%s-highlights')||'[]')).length === 1" % args.prefix)
        check("the highlight is stored under this book's own key",
              js("document.querySelectorAll('mark.hl').length") == 1,
              js("Object.keys(localStorage)"))
        keys = js("Object.keys(localStorage)")
        foreign = [k for k in keys if k.startswith("watson-repentance")
                   and not args.prefix.startswith("watson-repentance")]
        check("no other book's keys were touched", not foreign, keys)
        page.reload()
        page.wait_for_timeout(700)
        check("the highlight survives a reload", js("document.querySelectorAll('mark.hl').length") == 1)

        # ---------------------------------------------------------------- note
        js(SELECT_T, [test_page + 2, 5, 55])
        wait("!!document.querySelector('.hl-pop') && !document.querySelector('.hl-pop').hidden")
        click(".hl-pop .note-add")
        wait("!!document.querySelector('.note-editor textarea')")
        js("""(function(){ var ta = document.querySelector('.note-editor textarea');
             ta.value = 'a test note'; ta.dispatchEvent(new Event('input', {bubbles:true})); })()""")
        click(".note-editor-save")
        wait("(JSON.parse(localStorage.getItem('%s-notes')||'[]')).length === 1" % args.prefix)
        check("the note is stored and marked",
              js("document.querySelectorAll('.note-marker').length") == 1,
              js("Object.keys(localStorage)"))
        check("its card is open while it is new",
              js("document.querySelectorAll('.note-card:not(.is-closed)').length") == 1)

        # ---------------------------------------------------------------- hide/show
        click("#notes-toggle")
        page.wait_for_timeout(300)
        check("notes can be hidden", js("document.documentElement.getAttribute('data-notes')") == "off")
        click("#notes-toggle")
        page.wait_for_timeout(300)
        check("and shown again", js("document.documentElement.getAttribute('data-notes')") == "on")

        # ---------------------------------------------------------------- panel
        click("#ann-open")
        page.wait_for_timeout(400)
        check("the panel lists both entries", js("document.querySelectorAll('.ann-item').length") == 2,
              js("document.querySelectorAll('.ann-item').length"))
        for bid in ("ann-export", "ann-import", "ann-report", "ann-print", "ann-bake", "ann-overwrite"):
            check("panel button %s" % bid, js("!!document.getElementById('%s')" % bid))

        # ---------------------------------------------------------------- go to
        js("""(function(){ window.__flash = [];
             setInterval(function(){ Array.prototype.forEach.call(
               document.querySelectorAll('.ann-target-flash'), function(e){
                 if(window.__flash.indexOf(e.tagName) < 0) window.__flash.push(e.tagName); }); }, 50); })()""")
        js("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        click(".ann-item .ann-go")
        page.wait_for_timeout(1600)
        check("Go to on a highlight jumps and rings the sentence",
              js("Math.round(window.scrollY)") > 500 and "MARK" in js("window.__flash"),
              {"scrollY": js("Math.round(window.scrollY)"), "flash": js("window.__flash")})

        idx = js("""(function(){ var it = document.querySelectorAll('.ann-item');
            for(var i=0;i<it.length;i++) if(it[i].querySelector('.ann-body')) return i; return -1; })()""")
        if idx >= 0:
            js("""(function(){ document.querySelectorAll('.ann-item')[%d].querySelector('.ann-go').click(); })()""" % idx)
            page.wait_for_timeout(1500)
            check("Go to on a note opens its card and jumps",
                  js("Math.round(window.scrollY)") > 500 and
                  js("document.querySelectorAll('.note-card:not(.is-closed)').length") >= 1)

        if args.orig_views:
            js("""(function(){ var s = document.getElementById('view-mode');
                 s.value = 'original'; s.dispatchEvent(new Event('change', {bubbles:true})); })()""")
            page.wait_for_timeout(600)
            js("window.scrollTo(0, 0)")
            page.wait_for_timeout(250)
            click("#ann-open")
            page.wait_for_timeout(300)
            click(".ann-item .ann-go")
            page.wait_for_timeout(2200)
            res = js("""({scrollY: Math.round(window.scrollY), mode: document.body.getAttribute('data-mode')})""")
            check("Go to works from the Original pages view (switches to Reading)",
                  res["scrollY"] > 500 and res["mode"] == "reading", res)
            js("""(function(){ var s = document.getElementById('view-mode');
                 s.value = 'reading'; s.dispatchEvent(new Event('change', {bubbles:true})); })()""")
            page.wait_for_timeout(400)

        # ---------------------------------------------------------------- export
        n0 = len(downloads)
        click("#ann-open")
        page.wait_for_timeout(300)
        click("#ann-export")
        page.wait_for_timeout(1400)
        check("Export downloads a JSON backup", len(downloads) == n0 + 1, len(downloads) - n0)
        if len(downloads) > n0:
            out = Path("/tmp") / "export.json"
            downloads[-1].save_as(out)
            try:
                data = json.loads(out.read_text(encoding="utf-8"))
                ok = len(data.get("highlights", [])) == 1 and len(data.get("notes", [])) == 1
            except Exception as exc:  # noqa: BLE001
                data, ok = str(exc), False
            check("the backup holds one highlight and one note", ok, data if not ok else "")

        # ---------------------------------------------------------------- bake
        n1 = len(downloads)
        js("document.getElementById('ann-open').click()")
        page.wait_for_timeout(300)
        click("#ann-bake")
        page.wait_for_timeout(1800)
        check("Save into HTML downloads a copy", len(downloads) == n1 + 1, len(downloads) - n1)
        baked = None
        if len(downloads) > n1:
            baked = Path("/tmp") / "baked_test.html"
            downloads[-1].save_as(baked)
            text = baked.read_text(encoding="utf-8", errors="replace")
            check("the copy carries exactly one data block",
                  text.count('<script type="application/json" id="baked-annotations">') == 1,
                  text.count('<script type="application/json" id="baked-annotations">'))
            check("no duplicated panel or toolbar",
                  text.count('id="theme-toggle"') == 1 and text.count('id="ann-bake"') == 1)

        # ---------------------------------------------------------------- save over
        js("document.getElementById('ann-open').click()")
        page.wait_for_timeout(300)
        js("window.__ow.perm='granted'; window.__ow.failStep=null;")
        click("#ann-overwrite")
        wait("!document.getElementById('ann-overwrite').disabled")
        page.wait_for_timeout(600)
        check("Save over my book writes through the picker", js("window.__ow.writes") == 1,
              js("window.__ow.writes"))
        check("what it wrote is one whole book",
              js("window.__ow.blocks") == 1 and js("window.__ow.mode") == "reading",
              {"blocks": js("window.__ow.blocks"), "mode": js("window.__ow.mode")})
        d0, w0 = len(downloads), js("window.__ow.writes")
        js("window.__ow.failStep='createWritable'; window.__ow.failName='AbortError';")
        click("#ann-overwrite")
        wait("!document.getElementById('ann-overwrite').disabled")
        page.wait_for_timeout(900)
        msg = js("(document.getElementById('ow-msg')||{}).textContent || ''")
        check("a refused write is explained inside the panel",
              "Could not write" in msg or "Downloads" in msg, msg)
        check("a refused write hands over a copy instead", len(downloads) - d0 == 1, len(downloads) - d0)
        js("window.__ow.failStep=null;")
        click("#ann-overwrite")
        wait("!document.getElementById('ann-overwrite').disabled")
        page.wait_for_timeout(700)
        check("the next click recovers and writes again", js("window.__ow.writes") - w0 == 1,
              js("window.__ow.writes"))

        # ---------------------------------------------------------------- dictionary
        probe = choose_dict_probe(book, args.dict_word)
        if js("!!document.querySelector('.hl-pop .dict-define')") and not probe:
            print("  -- dictionary")
            check("Define shows a definition for a selected word", False,
                  "no probe word available in this book's dictionary data")
        elif probe:
            print("  -- dictionary (probe word: %s)" % probe)
            selected = js("""(function(){
              var s = window.getSelection(); s.removeAllRanges();
              var el = document.querySelector('#ann-list'); if(el) el.innerHTML = '';
              var pattern = new RegExp(%s);
              var pages = document.querySelectorAll('.source-page');
              for(var i = 0; i < pages.length; i++){
                var c = pages[i].querySelector('.reading-content'); if(!c) continue;
                var w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT, null), n;
                while((n = w.nextNode())){
                  var m = pattern.exec(n.nodeValue || '');
                  if(m){
                    var r = document.createRange();
                    r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
                    s.removeAllRanges(); s.addRange(r);
                    pages[i].scrollIntoView();
                    document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    return true;
                  }
                }
              }
              return false;
            })()""" % json.dumps(r"\b%s\b" % probe))
            page.wait_for_timeout(500)
            check("the probe word can be selected", selected, probe)
            click(".hl-pop .dict-define")
            page.wait_for_timeout(500)
            shown = js("""(function(){ var c = document.getElementById('dict-card');
                return c && !c.hidden ? c.textContent.replace(/\\s+/g,' ').trim() : ''; })()""")
            check("Define shows a definition for a selected word (%s)" % probe,
                  len(shown) > 40 and "No entry" not in shown, shown[:160])
            check("the definition names its source",
                  "Glossary" in shown or "WordNet" in shown or "Webster" in shown, shown[:120])
            js("document.querySelector('.dict-close').click()")
            page.wait_for_timeout(300)
            check("the definition can be closed",
                  js("document.getElementById('dict-card').hidden"))
            js("document.getElementById('ann-open').click()")
            page.wait_for_timeout(300)

        # ---------------------------------------------------------------- baked copy
        if baked and baked.exists():
            ctx2 = b.new_context(accept_downloads=True, viewport={"width": 1200, "height": 800})
            p2 = ctx2.new_page()
            p2.add_init_script(STUB)
            errs2 = []
            p2.on("pageerror", lambda e: errs2.append(str(e)))
            p2.goto(baked.as_uri())
            p2.wait_for_timeout(700)
            check("the baked copy opens in Reading view",
                  p2.evaluate("document.body.getAttribute('data-mode')") == "reading")
            check("the baked copy restores its own marks",
                  p2.evaluate("document.querySelectorAll('mark.hl').length") == 1 and
                  p2.evaluate("document.querySelectorAll('.note-marker').length") == 1)
            p2.click("#ann-open")
            p2.wait_for_timeout(400)
            p2.evaluate("(function(){ window.scrollTo(0,0);"
                        " document.querySelector('.ann-item .ann-go').click(); })()")
            p2.wait_for_timeout(1600)
            check("Go to works in the baked copy",
                  p2.evaluate("Math.round(window.scrollY)") > 500)
            check("no javascript errors in the baked copy", not errs2, errs2[:2])
            ctx2.close()

        check("no javascript errors", not errors, errors[:3])
        b.close()

    passed = sum(1 for ok, _ in RESULTS if ok)
    print("-" * 74)
    print("RESULT: %d passed, %d failed" % (passed, len(RESULTS) - passed))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
