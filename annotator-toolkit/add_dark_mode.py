#!/usr/bin/env python3
"""Add a light/dark theme toggle to 'The Doctrine of Repentance' HTML edition.

Edits made to the source file:
  1. <head>: color-scheme meta + tiny inline script that applies a saved (or
     system) theme before first paint, so there is no flash of the wrong theme.
  2. <style>: a dark palette keyed on html[data-theme="dark"], overriding every
     hard-coded colour in the original stylesheet.
  3. print styles: forced black-on-white even when dark mode is on.
  4. toolbar: a theme toggle button (with an icon that swaps via CSS).
  5. before </body>: the toggle logic (persists choice in localStorage).
"""

import io
import sys

SRC = "/home/user/uploads/The Doctrine of Repentance - Thomas Watson.html"
DST = "/home/user/The Doctrine of Repentance - Thomas Watson.html"

html = io.open(SRC, encoding="utf-8").read()


def sub_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.exit("FAIL [%s]: anchor found %d times" % (label, n))
    print("ok  [%s]" % label)
    return text.replace(old, new, 1)


# --------------------------------------------------------------------------
# 1. head: colour-scheme hint + pre-paint theme bootstrap
# --------------------------------------------------------------------------
HEAD_ANCHOR = '<meta name="viewport" content="width=device-width, initial-scale=1">'
HEAD_ADDITION = HEAD_ANCHOR + """
<meta name="color-scheme" content="light dark">
<script>
(function(){
 try{
  var key = 'watson-repentance-theme', saved = null;
  try { saved = localStorage.getItem(key); } catch (e) {}
  var dark;
  /* No saved choice yet? Follow the operating system's setting.
     To always start in light mode instead, replace the else-branch with: dark = false; */
  if (saved === 'dark' || saved === 'light') {
   dark = (saved === 'dark');
  } else {
   dark = !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }
  if (dark) document.documentElement.setAttribute('data-theme', 'dark');
 } catch (e) {}
})();
</script>"""
html = sub_once(html, HEAD_ANCHOR, HEAD_ADDITION, "head bootstrap")

# --------------------------------------------------------------------------
# 2. dark palette, inserted just before the print styles so it wins the cascade
# --------------------------------------------------------------------------
DARK_CSS = """/* ---------- dark theme ---------- */
html[data-theme="dark"]{
  color-scheme:dark;
  --ink:#e7e4da;
  --muted:#a2a498;
  --accent:#a9bd85;
  --line:#3a3d35;
  --paper:#1d201a;
  --bg:#131512;
  --control-bg:#272b23;
  --control-border:#464b3e;
  --focus:#8fa86f;
  --link-hover:#cfdcb2;
}
html[data-theme="dark"] body{background:var(--bg);color:var(--ink)}
html[data-theme="dark"] a{color:var(--accent)}
html[data-theme="dark"] a:hover{color:var(--link-hover)}
html[data-theme="dark"] a:focus-visible,
html[data-theme="dark"] button:focus-visible,
html[data-theme="dark"] select:focus-visible,
html[data-theme="dark"] input:focus-visible{outline-color:var(--focus)}
html[data-theme="dark"] ::selection{background:#4b5a39;color:#fdfcf7}
html[data-theme="dark"] .toolbar{background:rgba(19,21,18,.96);border-color:var(--line)}
html[data-theme="dark"] select,
html[data-theme="dark"] input,
html[data-theme="dark"] button{color:var(--ink);background:var(--control-bg);border-color:var(--control-border)}
html[data-theme="dark"] button:hover{background:#333a2b}
html[data-theme="dark"] .toc{background:var(--paper);border-color:var(--line)}
html[data-theme="dark"] .toc a{border-bottom-color:var(--line)}
html[data-theme="dark"] .source-page{background:var(--paper);border-color:var(--line)}
html[data-theme="dark"] .page-label{border-bottom-color:var(--line)}
html[data-theme="dark"] .reading-content img{filter:brightness(.9)}
html[data-theme="dark"] .original-sheet{background:#fffefe;border-radius:2px}
html[data-theme="dark"] .original-sheet::after{content:"";position:absolute;inset:0;background:#000;opacity:.08;pointer-events:none}
html[data-theme="dark"] .pdf-link:hover{fill:#b6cf85;fill-opacity:.25}

/* ---------- theme toggle control ---------- */
.theme-toggle{display:inline-flex;align-items:center;gap:7px}
.theme-toggle svg{width:16px;height:16px;flex:none;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.theme-toggle .icon-moon{display:none}
html[data-theme="dark"] .theme-toggle .icon-sun{display:none}
html[data-theme="dark"] .theme-toggle .icon-moon{display:block}
.theme-toggle-text{display:inline-block;min-width:5.4em;text-align:left}

body,.toolbar,.toc,.source-page,.document-footer,select,input,button{transition:background-color .2s ease,color .2s ease,border-color .2s ease}
@media (prefers-reduced-motion: reduce){body,.toolbar,.toc,.source-page,.document-footer,select,input,button{transition:none}}

"""
PRINT_ANCHOR = "@media print{"
html = sub_once(html, PRINT_ANCHOR, DARK_CSS + PRINT_ANCHOR, "dark palette css")

# --------------------------------------------------------------------------
# 3. printing always renders black on white
# --------------------------------------------------------------------------
PRINT_BODY = "body{background:#fff}"
PRINT_OVERRIDES = (
    "body{background:#fff;color:#000}"
    'html[data-theme="dark"] body{background:#fff;color:#000}'
    'html[data-theme="dark"] .source-page,html[data-theme="dark"] .toc{background:#fff;border-color:#ddd}'
    'html[data-theme="dark"] a{color:inherit}'
    'html[data-theme="dark"] .reading-content img{filter:none}'
    'html[data-theme="dark"] .original-sheet::after{display:none}'
)
html = sub_once(html, PRINT_BODY, PRINT_OVERRIDES, "print force light")

# --------------------------------------------------------------------------
# 4. toolbar button
# --------------------------------------------------------------------------
VIEW_ANCHOR = '<label>View <select id="view-mode">'
BUTTON_HTML = """<button type="button" id="theme-toggle" class="theme-toggle" aria-pressed="false" aria-label="Switch to dark mode" title="Switch between the light and dark reading themes"><svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.6v2.2M12 19.2v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.6 12h2.2M19.2 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg><svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 14.2A8.2 8.2 0 1 1 9.8 4a6.6 6.6 0 0 0 10.2 10.2z"/></svg><span class="theme-toggle-text">Dark mode</span></button>
"""
html = sub_once(
    html,
    VIEW_ANCHOR,
    BUTTON_HTML + VIEW_ANCHOR,
    "toolbar button",
)

# --------------------------------------------------------------------------
# 5. toggle logic, appended after the existing inline script
# --------------------------------------------------------------------------
SCRIPT = """
<script>
(function(){
 const root = document.documentElement;
 const btn = document.getElementById('theme-toggle');
 if(!btn) return;
 const label = btn.querySelector('.theme-toggle-text');
 const KEY = 'watson-repentance-theme';
 const mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
 function saved(){
  try{ const v = localStorage.getItem(KEY); return (v === 'dark' || v === 'light') ? v : null; }catch(e){ return null; }
 }
 function isDark(){ return root.getAttribute('data-theme') === 'dark'; }
 function apply(theme){
  const dark = (theme === 'dark');
  if(dark){ root.setAttribute('data-theme','dark'); } else { root.removeAttribute('data-theme'); }
  btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
  btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  btn.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
  if(label) label.textContent = dark ? 'Light mode' : 'Dark mode';
 }
 apply(isDark() ? 'dark' : 'light');
 btn.addEventListener('click', function(){
  const next = isDark() ? 'light' : 'dark';
  apply(next);
  try{ localStorage.setItem(KEY, next); }catch(e){}
 });
 if(mq){
  const follow = function(e){ if(!saved()) apply(e.matches ? 'dark' : 'light'); };
  if(mq.addEventListener){ mq.addEventListener('change', follow); }
  else if(mq.addListener){ mq.addListener(follow); }
 }
})();
</script>
"""
TAIL_ANCHOR = "})();\n</script>\n</body>"
html = sub_once(html, TAIL_ANCHOR, "})();\n</script>\n" + SCRIPT + "</body>", "toggle logic")

io.open(DST, "w", encoding="utf-8").write(html)
print("\nwrote %s (%.1f MB)" % (DST, len(html.encode("utf-8")) / 1e6))
