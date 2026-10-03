#!/usr/bin/env python3
"""Add an offline dictionary to a book.

  * a "Define" button appears in the selection popup next to the colours
  * clicking it looks up the selected word (up to four words at once)
  * the definitions are carried inside the file, so it works offline and in a
    baked copy

Run AFTER the other patchers.  Data comes from /home/user/dict_data.json
(built by make_dict_data.py).
"""

import io

PATH = "/home/user/The Doctrine of Repentance - Thomas Watson.html"
DATA = "/home/user/dict_data.json"

html = io.open(PATH, encoding="utf-8").read()
data = io.open(DATA, encoding="utf-8").read()


def sub_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit("anchor [%s] found %d times (expected 1) - aborting" % (label, n))
    print("ok  [%s]" % label)
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- 1. the data
data_block = ('<script type="application/json" id="dict-data">'
              + data.replace("<", "\\u003c") + "</script>\n")
html = sub_once(html, "\n</body>\n</html>", "\n" + data_block + "</body>\n</html>", "dictionary data")

# ---------------------------------------------------------------- 2. the css
CSS = """<style id="dict-style">
.dict-define{display:inline-flex;align-items:center;gap:5px;min-height:30px;padding:0 10px;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);font:12px/1 system-ui,sans-serif;cursor:pointer;white-space:nowrap}
.dict-define:hover{background:rgba(128,128,128,.16)}
.dict-card{position:fixed;z-index:70;width:min(420px,calc(100vw - 24px));max-height:min(64vh,460px);overflow:auto;padding:14px 40px 14px 15px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:10px;box-shadow:0 18px 46px rgba(0,0,0,.38);font:13.5px/1.55 system-ui,sans-serif}
.dict-card[hidden]{display:none}
.dict-close{position:absolute;top:6px;right:6px;width:26px;height:26px;padding:0;border:1px solid var(--control-border);border-radius:6px;background:var(--control-bg);color:var(--ink);font:15px/1 system-ui,sans-serif;cursor:pointer}
.dict-close:hover{background:rgba(128,128,128,.16)}
.dict-entry + .dict-entry{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.dict-word{margin:0 0 5px;font-weight:700;font-size:14.5px}
.dict-word .dict-as{font-weight:400;color:var(--muted)}
.dict-src{float:right;margin-left:8px;padding:1px 6px;border-radius:999px;border:1px solid var(--control-border);font:10.5px/1.6 system-ui,sans-serif;color:var(--muted);white-space:nowrap}
.dict-senses{margin:0;padding-left:18px}
.dict-senses li{margin:0 0 3px}
.dict-none .dict-hint,.dict-more{margin:4px 0 0;color:var(--muted);font-size:12.5px}
.dict-more{margin-top:10px;padding-top:8px;border-top:1px solid var(--line)}
@media print{.dict-card,.dict-define{display:none !important}}
</style>
"""
# "</head>" also appears inside the panel's report template, so insert before the
# first real </head>
i_head = html.index("</head>")
html = html[:i_head] + CSS + html[i_head:]
print("ok  [dictionary css]")

# ------------------------------------------------------- 3. the card + module
JS = r"""<script id="dict-script">
/* ---------- offline dictionary: select a word, click Define ---------- */
(function(){
 const dataEl = document.getElementById('dict-data');
 const SRC = {GL: 'Glossary', WN: 'WordNet', WB: "Webster's 1913"};
 let DICT = null;
 let card = null;

 function dict(){
  if(DICT) return DICT;
  try{
   /* the payload escapes "<" as \u003c so it can never close this script block */
   DICT = JSON.parse((dataEl.textContent || '').replace(/\\u003c/g, '<'));
  }catch(e){ DICT = {}; }
  return DICT;
 }
 function esc(t){
  return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
 }
 /* cheap English morphology - the same rules the data was built with */
 function forms(w){
  const out = [w];
  if(/ies$/.test(w) && w.length > 4) out.push(w.slice(0, -3) + 'y');
  if(/es$/.test(w) && w.length > 3) out.push(w.slice(0, -2));
  if(/s$/.test(w) && w.length > 3 && !/ss$/.test(w)) out.push(w.slice(0, -1));
  if(/ed$/.test(w) && w.length > 4){ out.push(w.slice(0, -2), w.slice(0, -1)); }
  if(/ing$/.test(w) && w.length > 5){ out.push(w.slice(0, -3), w.slice(0, -3) + 'e'); }
  if(/ly$/.test(w) && w.length > 4) out.push(w.slice(0, -2));
  if(/est$/.test(w) && w.length > 5) out.push(w.slice(0, -3));
  if(/eth$/.test(w) && w.length > 5) out.push(w.slice(0, -3));
  if(/th$/.test(w) && w.length > 5) out.push(w.slice(0, -2));
  return out;
 }
 function lookup(w){
  const d = dict(), f = forms(w);
  for(let i = 0; i < f.length; i++){ if(d[f[i]]) return {base: f[i], entry: d[f[i]]}; }
  return null;
 }
 function wordsOf(text){
  const raw = String(text || '').match(/[A-Za-z][A-Za-z'\-]+/g) || [];
  return raw.map(function(w){ return w.toLowerCase().replace(/^[-']+|[-']+$/g, ''); })
            .filter(function(w){ return w.length > 1; });
 }
 function ensureCard(){
  if(card) return card;
  card = document.createElement('div');
  card.className = 'dict-card';
  card.id = 'dict-card';
  card.hidden = true;
  card.setAttribute('role', 'dialog');
  card.setAttribute('aria-label', 'Dictionary definition');
  document.body.appendChild(card);
  card.addEventListener('click', function(e){
   if(e.target.closest && e.target.closest('.dict-close')) hide();
  });
  return card;
 }
 function hide(){ if(card) card.hidden = true; }
 function place(rect){
  const c = card, w = c.offsetWidth, h = c.offsetHeight;
  const vw = window.innerWidth, vh = window.innerHeight;
  let left = rect ? rect.left + rect.width / 2 - w / 2 : (vw - w) / 2;
  let top = rect ? rect.bottom + 10 : 80;
  if(top + h > vh - 10) top = rect ? Math.max(10, rect.top - h - 10) : Math.max(10, vh - h - 20);
  left = Math.max(10, Math.min(left, vw - w - 10));
  c.style.left = left + 'px';
  c.style.top = top + 'px';
 }
 function selectedRect(){
  try{
   const sel = window.getSelection();
   if(sel && sel.rangeCount){
    const r = sel.getRangeAt(0).getBoundingClientRect();
    if(r && (r.width || r.height)) return r;
   }
  }catch(e){}
  return null;
 }
 function show(text, rect){
  const c = ensureCard();
  const words = wordsOf(text);
  let out = '<button type="button" class="dict-close" aria-label="Close">&times;</button>';
  if(!words.length){
   out += '<div class="dict-entry"><p class="dict-word">Nothing selected</p>' +
          '<p class="dict-hint">Select a word in the text, then click Define.</p></div>';
  }else{
   const shown = words.slice(0, 4);
   shown.forEach(function(w){
    const hit = lookup(w);
    if(hit){
     const src = SRC[hit.entry.s] || hit.entry.s;
     out += '<div class="dict-entry"><p class="dict-word">' + esc(w) +
            (hit.base !== w ? ' <span class="dict-as">(' + esc(hit.base) + ')</span>' : '') +
            '<span class="dict-src">' + esc(src) + '</span></p>' +
            '<ol class="dict-senses">' +
            hit.entry.d.map(function(x){ return '<li>' + esc(x) + '</li>'; }).join('') +
            '</ol></div>';
    }else{
     out += '<div class="dict-entry dict-none"><p class="dict-word">' + esc(w) + '</p>' +
            '<p class="dict-hint">No entry for this word (names, place names and unusual ' +
            'spellings are not in the dictionary).</p></div>';
    }
   });
   if(words.length > shown.length){
    out += '<p class="dict-more">' + (words.length - shown.length) +
           ' more word(s) in your selection were not looked up - select one word for a full entry.</p>';
   }
  }
  c.innerHTML = out;
  c.hidden = false;
  place(rect);
 }

 /* the button lives in the selection popup the highlighter builds */
 let lastText = '';
 document.addEventListener('mouseup', function(){
  try{
   const t = window.getSelection().toString();
   if(t && t.trim()) lastText = t;      /* a click on a button can collapse the selection */
  }catch(e){}
 }, true);
 const pop = document.querySelector('.hl-pop');
 if(pop && !pop.querySelector('.dict-define')){
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'dict-define';
  btn.textContent = 'Define';
  btn.title = 'Look this word up in the dictionary built into this file';
  pop.appendChild(btn);
  btn.addEventListener('click', function(e){
   e.preventDefault();
   e.stopPropagation();
   let t = '';
   try{ t = window.getSelection().toString(); }catch(e){}
   show((t && t.trim()) ? t : lastText, selectedRect());
  });
 }
 document.addEventListener('keydown', function(e){
  if(e.key === 'Escape') hide();
 });
 /* a new selection or a click elsewhere starts clean */
 document.addEventListener('mouseup', hide, true);
 document.addEventListener('click', function(e){
  if(card && !card.hidden && e.target.closest &&
     !e.target.closest('.dict-card') && !e.target.closest('.dict-define')) hide();
 }, true);
})();
</script>
"""
html = sub_once(html, "\n</body>\n</html>", "\n" + JS + "</body>\n</html>", "dictionary module")

# ------------------------- 4. a baked copy must never carry an open definition
html = sub_once(
    html,
    "  const owMsg = get('#ow-msg');",
    "  const owMsg = get('#ow-msg');\n"
    "  const dictCard = get('#dict-card');\n"
    "  if(dictCard){ dictCard.hidden = true; dictCard.textContent = ''; dictCard.removeAttribute('style'); }",
    "bake resets the definition card",
)

io.open(PATH, "w", encoding="utf-8").write(html)
print("wrote %s (%.1f MB; dictionary %.0f KB)" % (PATH, len(html) / 1e6, len(data) / 1024))
