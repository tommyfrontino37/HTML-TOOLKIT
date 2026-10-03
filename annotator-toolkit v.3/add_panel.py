#!/usr/bin/env python3
"""Add an "All notes & highlights" panel to the book HTML.

Run AFTER add_dark_mode.py, add_highlights.py and add_notes.py.

What it adds
  * A toolbar button that opens a full-screen panel listing every highlight and
    note in the book, grouped by chapter, newest data read live from the other
    two modules through window.__bookAPI / window.__notesAPI.
  * Search box to filter, "Go to" on each entry to jump into the book (opening
    the note card when the entry has a note).
  * Export JSON (portable backup), Import JSON (merge, with a summary),
    Download a standalone reading report (.html) and Copy as Markdown,
    plus Print — which prints just the panel when it is open.
"""

import io
import sys

PATH = "/home/user/The Doctrine of Repentance - Thomas Watson.html"
html = io.open(PATH, encoding="utf-8").read()


def sub_once(text, old, new, label):
    n = text.count(old)
    if n < 1:
        sys.exit("FAIL [%s]: anchor found %d times" % (label, n))
    print("ok  [%s]" % label)
    return text.replace(old, new, 1)


# ==========================================================================
# 1. CSS
# ==========================================================================
PANEL_CSS = """/* ---------- all notes & highlights panel ---------- */
.ann-open{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;min-height:0;padding:0;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);cursor:pointer;flex:none}
.ann-open svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.ann-open:hover{background:rgba(128,128,128,.16)}
.ann-open[aria-expanded="true"]{outline:2px solid var(--accent);outline-offset:1px}

.ann-panel{position:fixed;inset:0;z-index:60;background:rgba(20,22,18,.5);display:flex;align-items:flex-start;justify-content:center;padding:24px 16px;font:14px/1.6 system-ui,sans-serif}
.ann-panel[hidden]{display:none}
.ann-inner{display:flex;flex-direction:column;width:min(940px,100%);max-height:100%;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:0 24px 60px rgba(0,0,0,.4);overflow:hidden}
.ann-head{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:11px 14px;border-bottom:1px solid var(--line);background:var(--paper)}
.ann-actions{display:flex;flex-wrap:wrap;gap:6px;flex:1 1 100%}
.ow-msg{margin:0;flex:1 1 100%;padding:7px 10px;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);font:12.5px/1.45 system-ui,sans-serif;overflow-wrap:break-word}
.ow-msg[hidden]{display:none}
.ow-msg[data-kind="ok"]{border-color:rgba(76,140,90,.8);background:rgba(76,140,90,.14)}
.ow-msg[data-kind="warn"]{border-color:rgba(196,146,60,.85);background:rgba(196,146,60,.16)}
.ow-msg[data-kind="err"]{border-color:rgba(190,80,70,.85);background:rgba(190,80,70,.15)}
.ann-title{font:600 13px/1.2 system-ui,sans-serif;letter-spacing:.02em;margin-right:2px}
.ann-stats{font:12px/1.2 system-ui,sans-serif;color:var(--muted);margin-right:auto;white-space:nowrap}
.ann-search{flex:1 1 150px;min-width:110px;max-width:270px;padding:6px 9px;min-height:30px;border:1px solid var(--control-border);border-radius:6px;background:var(--control-bg);color:var(--ink);font:13px/1.2 system-ui,sans-serif}
.ann-btn{display:inline-flex;align-items:center;gap:5px;min-height:30px;padding:0 10px;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);font:12px/1 system-ui,sans-serif;cursor:pointer;white-space:nowrap}
.ann-btn:hover{background:rgba(128,128,128,.16)}
.ann-close{width:30px;min-width:30px;padding:0;justify-content:center;font-size:17px}
.ann-list{overflow:auto;padding:14px 16px 24px;scrollbar-gutter:stable}
.ann-empty{color:var(--muted);text-align:center;padding:38px 10px;font-size:14px}
.ann-chapter{margin:20px 0 8px;font:600 12px/1.3 system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.ann-chapter:first-child{margin-top:2px}
.ann-item{border:1px solid var(--line);border-left-width:4px;border-radius:0 8px 8px 0;padding:9px 12px 10px;margin:0 0 10px;background:var(--note-bg)}
.ann-item.ann-yellow{border-left-color:#d9bf3f}
.ann-item.ann-green{border-left-color:#6bab70}
.ann-item.ann-blue{border-left-color:#5f93cc}
.ann-item.ann-red{border-left-color:#c76a63}
.ann-item.ann-none{border-left-color:var(--note-accent)}
.ann-item-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.ann-page{font:600 11px/1 system-ui,sans-serif;letter-spacing:.04em;color:var(--muted)}
.ann-chips{display:inline-flex;gap:4px}
.ann-chip{width:12px;height:12px;border-radius:3px;border:1px solid var(--control-border)}
.ann-chip.ann-yellow{background:var(--hl-yellow)}
.ann-chip.ann-green{background:var(--hl-green)}
.ann-chip.ann-blue{background:var(--hl-blue)}
.ann-chip.ann-red{background:var(--hl-red)}
.ann-go{margin-left:auto;min-height:24px;padding:0 8px;border-radius:5px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);font:11px/1 system-ui,sans-serif;cursor:pointer}
.ann-go:hover{background:rgba(128,128,128,.16)}
.ann-quote{margin:0;padding:0 0 0 9px;border-left:2px solid var(--note-line);font-style:italic;font-size:13px;line-height:1.55;color:var(--ink)}
.ann-item.ann-quote-only .ann-quote{font-size:13.5px}
.ann-body{margin:7px 0 0;font-size:13px;line-height:1.6;white-space:pre-wrap;overflow-wrap:break-word}
.ann-body::before{content:"Note: ";font-weight:600;color:var(--note-accent)}
.ann-target-flash{animation:annFlash 1.4s ease-out}
@keyframes annFlash{0%{box-shadow:0 0 0 4px rgba(211,179,99,.75)}100%{box-shadow:0 0 0 0 rgba(211,179,99,0)}}
@media (max-width:640px){
 .ann-panel{padding:0}
 .ann-inner{border-radius:0;max-height:none;height:100%}
 .ann-head{gap:6px;padding:10px}
 .ann-title{width:100%}
 .ann-search{flex:1 1 100%;max-width:none}
 .ann-list{padding:12px}
}
@media print{
 html[data-ann="open"] body>*{display:none !important}
 html[data-ann="open"] body>.ann-panel{display:block !important;position:static !important;background:#fff !important;padding:0 !important}
 html[data-ann="open"] .ann-panel .ann-inner{display:block !important;max-height:none !important;border:0 !important;box-shadow:none !important;border-radius:0 !important;width:auto !important}
 html[data-ann="open"] .ann-head .ann-actions,
 html[data-ann="open"] .ann-head .ann-search,
 html[data-ann="open"] .ann-head .ann-close{display:none !important}
 html[data-ann="open"] .ann-head .ow-msg{display:none !important}
 html[data-ann="open"] .ann-list{overflow:visible !important;padding:0 !important}
 html[data-ann="open"] .ann-item{background:#fff !important;border-color:#bbb !important;color:#000 !important;break-inside:avoid}
 html[data-ann="open"] .ann-quote{color:#000 !important}
 html[data-ann="open"] .ann-body::before{color:#000 !important}
 html[data-ann="open"] .ann-go{display:none !important}
 html[data-ann="open"] .ann-chapter{color:#333 !important}
}

"""
html = sub_once(
    html,
    'html[data-notes="off"] .note-marker,html[data-notes="off"] .note-card{display:none}',
    'html[data-notes="off"] .note-marker,html[data-notes="off"] .note-card{display:none}\n' + PANEL_CSS,
    "panel css",
)

# ==========================================================================
# 2. toolbar button + panel markup
# ==========================================================================
BUTTON = (
    '<button type="button" id="ann-open" class="ann-open" aria-expanded="false" '
    'title="View all notes &amp; highlights" aria-label="View all notes and highlights">'
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<rect x="3.5" y="4" width="17" height="16" rx="2.2"/>'
    '<path d="M7.5 9h9M7.5 12.6h9M7.5 16.2h5.5"/></svg></button>'
)
html = sub_once(html, '<button type="button" id="notes-toggle"', BUTTON + '<button type="button" id="notes-toggle"', "toolbar button")

PANEL_HTML = """<div class="ann-panel" id="ann-panel" hidden role="dialog" aria-modal="true" aria-label="All notes and highlights">
 <div class="ann-inner">
  <div class="ann-head">
   <span class="ann-title">Your notes &amp; highlights</span>
   <span class="ann-stats" id="ann-stats"></span>
   <input type="search" id="ann-search" class="ann-search" placeholder="Search your notes and quotes\u2026" aria-label="Search notes and highlights">
   <button type="button" class="ann-btn ann-close" id="ann-close" aria-label="Close">&times;</button>
   <div class="ann-actions">
    <button type="button" class="ann-btn" id="ann-export" title="Save all highlights and notes as a JSON backup file">Export</button>
    <button type="button" class="ann-btn" id="ann-import" title="Load highlights and notes from a JSON backup file">Import</button>
    <button type="button" class="ann-btn" id="ann-report" title="Download a standalone reading report you can open on its own">Report</button>
    <button type="button" class="ann-btn" id="ann-print" title="Print just this list">Print</button>
    <button type="button" class="ann-btn" id="ann-bake" title="Save a new copy of the book with all your notes and highlights inside it">Save into HTML</button>
   <button type="button" class="ann-btn" id="ann-overwrite" hidden title="Write your notes and highlights straight into your book file - asks your permission first (Chrome and Edge)">Save over my book</button>
   </div>
   <p class="ow-msg" id="ow-msg" role="status" aria-live="polite" hidden></p>
  </div>
  <div class="ann-list" id="ann-list"></div>
 </div>
</div>
<input type="file" id="ann-file" accept=".json,application/json" hidden>
"""
html = sub_once(html, "\n</body>\n</html>", PANEL_HTML + "</body>\n</html>", "panel markup")

# ==========================================================================
# 3. behaviour
# ==========================================================================
PANEL_JS = """
<script>
/* ---------- all notes & highlights panel ---------- */
(function(){
 const api = window.__bookAPI, notesAPI = window.__notesAPI;
 if(!api || !notesAPI) return;

 const KEY_ORDER = ['yellow','green','blue','red'];
 const panel   = document.getElementById('ann-panel');
 const list    = document.getElementById('ann-list');
 const stats   = document.getElementById('ann-stats');
 const search  = document.getElementById('ann-search');
 const openBtn = document.getElementById('ann-open');
 const fileIn  = document.getElementById('ann-file');
 let clusters = [];

 /* ---------- text + chapter helpers ---------- */
 function pageText(page){
  const content = api.pageContent(page);
  if(!content) return '';
  return api.textNodes(content).map(function(n){ return n.nodeValue; }).join('');
 }
 const chapters = (function(){
  const sel = document.getElementById('chapter-jump');
  const out = [];
  if(!sel) return out;
  Array.prototype.forEach.call(sel.options, function(o){
   const p = parseInt(o.value, 10);
   if(!isNaN(p)) out.push({page:p, title:o.textContent});
  });
  return out.sort(function(a,b){ return a.page - b.page; });
 })();
 function chapterFor(page){
  let name = '';
  chapters.forEach(function(c){ if(c.page <= page) name = c.title; });
  return name;
 }
 function esc(s){
  return String(s).replace(/[&<>"]/g, function(c){
   return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
 }

 /* ---------- build the list: merge highlights + notes into clusters ---------- */
 function buildClusters(){
  const items = [];
  api.getStore().forEach(function(h){
   items.push({type:'hl', page:h.page, start:h.start, end:h.end, color:h.color});
  });
  notesAPI.get().forEach(function(n){
   items.push({type:'note', page:n.page, start:n.start, end:n.end, id:n.id, body:n.body});
  });
  items.sort(function(a,b){
   return a.page - b.page || a.start - b.start || a.end - b.end || (a.type === 'hl' ? 0 : 1);
  });
  const out = [];
  items.forEach(function(it){
   const last = out[out.length - 1];
   /* <= so a passage highlighted in two colours reads as ONE entry in the list */
   if(last && last.page === it.page && it.start <= last.end){
    last.items.push(it);
    last.start = Math.min(last.start, it.start);
    last.end = Math.max(last.end, it.end);
   }else{
    out.push({page:it.page, start:it.start, end:it.end, items:[it]});
   }
  });
  out.forEach(function(c, i){
   c.key = 'c' + i;
   c.colors = c.items.filter(function(x){ return x.type === 'hl'; })
                     .map(function(x){ return x.color; })
                     .filter(function(v, i2, a){ return a.indexOf(v) === i2; })
                     .sort(function(a,b){ return KEY_ORDER.indexOf(a) - KEY_ORDER.indexOf(b); });
   c.note = c.items.filter(function(x){ return x.type === 'note'; })[0] || null;
   const text = pageText(c.page);
   c.quote = (text || '').slice(c.start, Math.min(c.end, text.length)).trim();
   c.chapter = chapterFor(c.page);
  });
  return out.filter(function(c){ return c.quote || c.note; });
 }

 /* ---------- render ---------- */
 function render(){
  const q = (search.value || '').trim().toLowerCase();
  const shown = q ? clusters.filter(function(c){
   return (c.quote + ' ' + (c.note ? c.note.body : '') + ' ' + c.chapter + ' ' + c.page).toLowerCase().indexOf(q) >= 0;
  }) : clusters;
  const hCount = api.getStore().length, nCount = notesAPI.get().length;
  stats.textContent = hCount + (hCount === 1 ? ' highlight' : ' highlights') + ' \\u00b7 ' +
                      nCount + (nCount === 1 ? ' note' : ' notes') +
                      (q ? ' \\u2014 ' + shown.length + ' shown' : '');
  if(!clusters.length){
   list.innerHTML = '<p class="ann-empty">Nothing saved yet.<br>Select some text in the book, then pick one of the four colours or add a note \\u2014 everything you save shows up here.</p>';
   return;
  }
  if(!shown.length){
   list.innerHTML = '<p class="ann-empty">No entries match \\u201c' + esc(search.value) + '\\u201d</p>';
   return;
  }
  let html = '', chapter = null;
  shown.forEach(function(c){
   if(c.chapter !== chapter){
    chapter = c.chapter;
    if(chapter) html += '<h2 class="ann-chapter">' + esc(chapter) + '</h2>';
   }
   const cls = c.colors.length ? c.colors[0] : 'none';
   html += '<article class="ann-item ann-' + cls + (c.note ? '' : ' ann-quote-only') + '" data-key="' + c.key + '">';
   html += '<div class="ann-item-head"><span class="ann-page">Page ' + c.page + '</span>';
   if(c.colors.length){
    html += '<span class="ann-chips">' + c.colors.map(function(col){
     return '<span class="ann-chip ann-' + col + '" title="' + col + ' highlight"></span>';
    }).join('') + '</span>';
   }
   html += '<button type="button" class="ann-go" data-go="' + c.key + '">Go to \\u2192</button></div>';
   if(c.quote) html += '<blockquote class="ann-quote">' + esc(c.quote) + '</blockquote>';
   if(c.note) html += '<p class="ann-body">' + esc(c.note.body) + '</p>';
   html += '</article>';
  });
  list.innerHTML = html;
 }

 /* ---------- jumping into the book ---------- */
 function offsetRange(page, start){
  const content = api.pageContent(page);
  if(!content) return null;
  const nodes = api.textNodes(content);
  let acc = 0, hit = null;
  for(let i = 0; i < nodes.length && !hit; i++){
   const len = nodes[i].nodeValue.length;
   if(start <= acc + len) hit = {node:nodes[i], offset:Math.max(0, start - acc)};
   acc += len;
  }
  if(!hit) return null;
  const r = document.createRange();
  const off = Math.min(hit.offset, hit.node.nodeValue.length);
  r.setStart(hit.node, off);
  r.setEnd(hit.node, Math.min(hit.node.nodeValue.length, off + 1));
  return r;
 }
 function flashElement(el){
  if(!el) return;
  let target = el;
  if(el.closest) target = el.closest('mark.hl, .note-anchor') || el;
  target.classList.remove('ann-target-flash');
  void target.offsetWidth;
  target.classList.add('ann-target-flash');
  setTimeout(function(){ target.classList.remove('ann-target-flash'); }, 1500);
 }
 function ensureReadingView(page){
  /* the marks live in the text layer: in "Original pages" view that layer is
     display:none, so there is nothing to scroll to.  Switch back to Reading
     through the book's own selector, which keeps the current position. */
  const content = api.pageContent(page);
  if(content && content.getClientRects && content.getClientRects().length) return false;
  const sel = document.getElementById('view-mode');
  if(sel && sel.value !== 'reading'){
   sel.value = 'reading';
   sel.dispatchEvent(new Event('change', { bubbles: true }));
   return true;
  }
  if(document.body.getAttribute('data-mode') !== 'reading'){
   document.body.setAttribute('data-mode', 'reading');
   return true;
  }
  return false;
 }
 function markNear(node){
  /* the element the reader should see: the highlight (or note mark) itself, and
     if the offset sits on a boundary, the mark that immediately follows */
  if(!node) return null;
  const el = (node.nodeType === 1) ? node : node.parentElement;
  if(el && el.closest){
   const m = el.closest('mark.hl, .note-anchor');
   if(m) return m;
  }
  let s = node.nextSibling;
  for(let i = 0; s && i < 4; i++){
   if(s.nodeType === 1 && s.matches && s.matches('mark.hl, .note-anchor')) return s;
   s = s.nextSibling;
  }
  return null;
 }
 function goTo(key){
  const c = clusters.filter(function(x){ return x.key === key; })[0];
  if(!c) return;
  close();
  const switched = ensureReadingView(c.page);
  const run = function(){
   if(c.note){
    /* if notes are hidden there is nothing to scroll to - show them first */
    if(notesAPI.isVisible && !notesAPI.isVisible()){
     notesAPI.setVisible(true);
     api.setStatus('Notes shown so this note is visible');
    }
    if(notesAPI.show) notesAPI.show(c.note.id);   /* always show it, never toggle it off */
    else notesAPI.open(c.note.id);
    if(switched) api.setStatus('Switched to Reading view so the note is visible');
    return;
   }
   const r = offsetRange(c.page, c.start);
   const mark = r ? markNear(r.startContainer) : null;
   const anchor = mark || (r && r.startContainer.parentElement) || null;
   if(anchor){
    const rect = anchor.getBoundingClientRect();
    if(rect && (rect.width || rect.height)){
     window.scrollTo({ top: window.scrollY + rect.top - 140, behavior: 'smooth' });
     flashElement(anchor);
     if(switched) api.setStatus('Switched to Reading view so the highlight is visible');
     return;
    }
   }
   /* last resort: aim at the page itself (works in either view) */
   const sec = document.getElementById('page-' + c.page);
   if(sec){
    const sr = sec.getBoundingClientRect();
    window.scrollTo({ top: window.scrollY + sr.top - 90, behavior: 'smooth' });
    flashElement(sec);
    api.setStatus('Could not place the exact sentence - jumped to page ' + c.page);
    return;
   }
   api.setStatus('Could not find that place in the book');
  };
  /* after a view change the page needs one frame to lay out again */
  if(switched) setTimeout(run, 90); else run();
 }

 /* ---------- open / close ---------- */
 function open(){
  panel.hidden = false;
  document.documentElement.setAttribute('data-ann', 'open');
  if(openBtn) openBtn.setAttribute('aria-expanded', 'true');
  clusters = buildClusters();
  render();
  search.value = '';
  search.focus();
 }
 function close(){
  panel.hidden = true;
  document.documentElement.removeAttribute('data-ann');
  if(openBtn) openBtn.setAttribute('aria-expanded', 'false');
 }
 if(openBtn) openBtn.addEventListener('click', function(e){ e.preventDefault(); if(panel.hidden) open(); else close(); });
 document.getElementById('ann-close').addEventListener('click', close);
 panel.addEventListener('click', function(e){
  if(e.target === panel) close();
  const go = e.target.closest && e.target.closest('[data-go]');
  if(go) goTo(go.getAttribute('data-go'));
 });
 search.addEventListener('input', render);
 document.addEventListener('keydown', function(e){
  if(e.key === 'Escape' && !panel.hidden){ e.preventDefault(); close(); }
 });

 /* ---------- download helpers ---------- */
 function download(name, text, mime){
  try{
   const blob = new Blob([text], {type:(mime || 'text/plain') + ';charset=utf-8'});
   const url = URL.createObjectURL(blob);
   const a = document.createElement('a');
   a.href = url; a.download = name;
   document.body.appendChild(a); a.click(); a.remove();
   setTimeout(function(){ URL.revokeObjectURL(url); }, 5000);
   api.setStatus('Saved ' + name);
   return true;
  }catch(err){
   api.setStatus('This preview blocks downloads \\u2014 open the file in your browser');
   return false;
  }
 }
 function stamp(){
  const d = new Date();
  const p = function(n){ return (n < 10 ? '0' : '') + n; };
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
 }
 function totals(){
  const h = api.getStore().length, n = notesAPI.get().length;
  return {h:h, n:n, label:h + (h === 1 ? ' highlight' : ' highlights') + ', ' + n + (n === 1 ? ' note' : ' notes')};
 }
 function markdown(){
  const t = totals();
  let out = `# The Doctrine of Repentance \\u2014 my notes & highlights\\n\\n`;
  out += `_Thomas Watson \\u00b7 exported ${stamp()} \\u00b7 ${t.label}_\\n\\n`;
  let chapter = null;
  clusters.forEach(function(c){
   if(c.chapter !== chapter){ chapter = c.chapter; if(chapter) out += '## ' + chapter + '\\n\\n'; }
   out += '**Page ' + c.page + (c.colors.length ? ' \\u00b7 ' + c.colors.join('/') : '') + '**\\n\\n';
   if(c.quote) out += '> ' + c.quote.replace(/\\n/g, '\\n> ') + '\\n\\n';
   if(c.note) out += 'Note: ' + c.note.body.replace(/\\n/g, '\\n') + '\\n\\n';
   out += '---\\n\\n';
  });
  return out;
 }
 function reportHTML(){
  const t = totals();
  let body = '', chapter = null;
  clusters.forEach(function(c){
   if(c.chapter !== chapter){ chapter = c.chapter; if(chapter) body += '</section><section><h2>' + esc(chapter) + '</h2>'; }
   body += '<article><p class="meta">Page ' + c.page + (c.colors.length ? ' \\u00b7 ' + esc(c.colors.join(', ')) + ' highlight' : '') + '</p>';
   if(c.quote) body += '<blockquote>' + esc(c.quote) + '</blockquote>';
   if(c.note) body += '<p class="note"><b>Note:</b> ' + esc(c.note.body).replace(/\\n/g, '<br>') + '</p>';
   body += '</article>';
  });
  return '<!DOCTYPE html>\\n<html lang="en"><head><meta charset="utf-8">' +
   '<meta name="viewport" content="width=device-width, initial-scale=1">' +
   `<title>My notes \\u2014 The Doctrine of Repentance</title><style>` +
   'body{max-width:760px;margin:0 auto;padding:32px 20px 60px;background:#fffefa;color:#272923;' +
   'font:16px/1.65 Georgia,"Times New Roman",serif}' +
   'h1{font-size:27px;font-weight:normal;line-height:1.25;margin:0 0 6px}' +
   '.sub{color:#72746b;font:13px/1.6 system-ui,sans-serif;margin:0 0 26px}' +
   'h2{font:600 13px/1.4 system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:#47543a;margin:32px 0 10px}' +
   'article{border:1px solid #e0e2d8;border-left:4px solid #d9bf3f;border-radius:0 8px 8px 0;padding:11px 14px;margin:0 0 12px;background:#fdfcf7}' +
   '.meta{font:600 11px/1.4 system-ui,sans-serif;letter-spacing:.04em;color:#72746b;margin:0 0 6px}' +
   'blockquote{margin:0;padding:0 0 0 10px;border-left:2px solid #e0e2d8;font-style:italic;font-size:15px}' +
   '.note{margin:8px 0 0;font:14px/1.6 system-ui,sans-serif}' +
   '.note b{color:#a8761f}' +
   'footer{margin-top:34px;color:#72746b;font:12px/1.6 system-ui,sans-serif}' +
   '@media print{body{padding:0}article{break-inside:avoid}}' +
   '</style></head><body>' +
   `<h1>The Doctrine of Repentance \\u2014 my notes &amp; highlights</h1>` +
   `<p class="sub">Thomas Watson \\u00b7 exported ${stamp()} \\u00b7 ${t.label}</p>` +
   '<section>' + body + '</section>' +
   '<footer>Saved from your own copy of the HTML edition. Highlights are marked by colour; notes appear beneath the quote they belong to.</footer>' +
   '</body></html>';
 }

 /* ---------- export / import ---------- */
 const EXPORT_NAME = 'doctrine-of-repentance-annotations.json';
 document.getElementById('ann-export').addEventListener('click', function(){
  const data = {
   app: `The Doctrine of Repentance (HTML edition)`,
   version: 1,
   exported: new Date().toISOString(),
   highlights: api.getStore(),
   notes: notesAPI.get()
  };
  download(EXPORT_NAME, JSON.stringify(data, null, 2), 'application/json');
 });
 /* ---------- merging (shared by Import and by a baked file's own data) ---------- */
 function mergeIn(inH, inN){
  const key = function(h){ return h.page + '|' + h.start + '|' + h.end + '|' + h.color; };
  const have = {};
  const hl = api.getStore();
  hl.forEach(function(h){ have[key(h)] = 1; });
  let addedH = 0;
  (inH || []).forEach(function(h){
   if(!h || typeof h.page !== 'number' || typeof h.start !== 'number' || typeof h.end !== 'number') return;
   if(have[key(h)]) return;
   have[key(h)] = 1;
   hl.push({page:h.page, start:h.start, end:h.end, color:h.color});
   addedH++;
  });
  api.setStore(hl);

  const cur = notesAPI.get();
  const ids = {}, seen = {};
  cur.forEach(function(n){ ids[n.id] = 1; seen[n.page + '|' + n.start + '|' + n.end + '|' + n.body] = 1; });
  let addedN = 0;
  (inN || []).forEach(function(n){
   if(!n || typeof n.body !== 'string') return;
   const k = n.page + '|' + n.start + '|' + n.end + '|' + n.body;
   if(seen[k]) return;
   seen[k] = 1;
   const id = (typeof n.id === 'string' && !ids[n.id]) ? n.id : ('n' + Date.now() + '-' + Math.floor(Math.random() * 100000));
   ids[id] = 1;
   cur.push({id:id, page:n.page, start:n.start, end:n.end, body:n.body,
             quote:(typeof n.quote === 'string' ? n.quote : ''), created:n.created || 0, updated:n.updated || 0});
   addedN++;
  });
  notesAPI.set(cur);
  clusters = buildClusters();
  render();
  return {addedH:addedH, addedN:addedN};
 }

 document.getElementById('ann-import').addEventListener('click', function(){ fileIn.click(); });
 fileIn.addEventListener('change', function(){
  const file = fileIn.files && fileIn.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = function(){
   try{
    const data = JSON.parse(String(reader.result));
    const inH = Array.isArray(data) ? [] : (data.highlights || []);
    const inN = Array.isArray(data) ? [] : (data.notes || []);
    if(!inH.length && !inN.length && !Array.isArray(data)) throw new Error('no data');
    const res = mergeIn(inH, inN);
    api.setStatus('Imported ' + res.addedH + ' highlight' + (res.addedH === 1 ? '' : 's') +
                  ' and ' + res.addedN + ' note' + (res.addedN === 1 ? '' : 's') +
                  ((res.addedH + res.addedN) === 0 ? ' \\u2014 nothing new' : ''));
   }catch(err){
    api.setStatus('That file could not be read as an annotations backup');
   }
   fileIn.value = '';
  };
  reader.readAsText(file);
 });

 /* ---------- "Save into HTML": a copy of the book carrying your marks ---------- */
 const BACKSLASH = String.fromCharCode(92);   /* backslash, built to avoid escape traps */
 const NL = String.fromCharCode(10);          /* newline, same reason */
 const BAKED_ID = 'baked-annotations';
 const APPLIED_KEY = 'watson-repentance-baked-applied';
 function bakedPayload(){
  return {
   app: `The Doctrine of Repentance (HTML edition)`,
   version: 1,
   baked: String(Date.now()) + '-' + Math.floor(Math.random() * 1e6),
   bakedOn: new Date().toISOString(),
   highlights: api.getStore(),
   notes: notesAPI.get()
  };
 }
 /* strip everything this session painted into the page, so the saved copy is the
    book as it originally was - only the data block is new */
 function cleanClone(root){
  Array.prototype.forEach.call(root.querySelectorAll('mark.hl, .note-anchor'), function(el){
   const parent = el.parentNode;
   if(!parent) return;
   while(el.firstChild) parent.insertBefore(el.firstChild, el);
   parent.removeChild(el);
  });
  Array.prototype.forEach.call(root.querySelectorAll('.note-marker, .note-card, .hl-pop, .note-editor, .ann-target-flash'), function(el){
   if(el.classList && el.classList.contains('ann-target-flash')){
    el.classList.remove('ann-target-flash');
    return;
   }
   el.remove();
  });
  /* replace, never append: drop any annotations block this file already carries */
  Array.prototype.forEach.call(root.querySelectorAll('[id="baked-annotations"]'), function(el){ el.remove(); });
  root.normalize();
  root.removeAttribute('data-theme');
  root.removeAttribute('data-notes');
  root.removeAttribute('data-ann');
  root.removeAttribute('style');
  const get = function(sel){ return root.querySelector(sel); };
  /* a baked copy should open the way a fresh load does: Reading view */
  const bodyEl = get('body');
  if(bodyEl) bodyEl.setAttribute('data-mode', 'reading');
  const viewSel = get('#view-mode');
  if(viewSel) viewSel.value = 'reading';
  const panel = get('#ann-panel');
  if(panel) panel.hidden = true;
  const listEl = get('#ann-list');
  if(listEl) listEl.innerHTML = '';
  const searchEl = get('#ann-search');
  if(searchEl) searchEl.value = '';
  const statusEl = get('#hl-status');
  if(statusEl){ statusEl.hidden = true; statusEl.textContent = ''; }
  /* the save-over message row must not be baked in a "shown" state */
  const owMsg = get('#ow-msg');
  if(owMsg){ owMsg.hidden = true; owMsg.textContent = ''; owMsg.removeAttribute('data-kind'); }
  const owBtn2 = get('#ann-overwrite');
  if(owBtn2){ owBtn2.disabled = false; }
  const clearAll = get('#hl-clear-all');
  if(clearAll) clearAll.hidden = true;
  const countEl = get('#notes-count');
  if(countEl) countEl.textContent = '0';
  const openBtn2 = get('#ann-open');
  if(openBtn2) openBtn2.setAttribute('aria-expanded', 'false');
  const themeBtn = get('#theme-toggle');
  if(themeBtn){
   themeBtn.setAttribute('aria-pressed', 'false');
   themeBtn.setAttribute('aria-label', 'Switch to dark mode');
   themeBtn.title = 'Switch to dark mode';
   const lbl = themeBtn.querySelector('.theme-toggle-text');
   if(lbl) lbl.textContent = 'Dark mode';
  }
  Array.prototype.forEach.call(root.querySelectorAll('.hl-swatch'), function(b){ b.setAttribute('aria-pressed', 'false'); });
  Array.prototype.forEach.call(root.querySelectorAll('.hl-armed, .note-armed'), function(el){
   el.classList.remove('hl-armed'); el.classList.remove('note-armed');
  });
  return root;
 }
 function bakedHTML(payload){
  const clone = cleanClone(document.documentElement.cloneNode(true));
  const body = clone.querySelector('body');
  const block = document.createElement('script');
  block.type = 'application/json';
  block.id = BAKED_ID;
  /* JSON is safe inside a script block once "</" is escaped */
  block.textContent = JSON.stringify(payload).replace(/</g, BACKSLASH + 'u003c');
  body.insertBefore(block, body.firstChild);
  return '<!DOCTYPE html>' + NL + clone.outerHTML;
 }
 document.getElementById('ann-bake').addEventListener('click', function(){
  const payload = bakedPayload();
  api.setStatus('Preparing your annotated copy\u2026');
  setTimeout(function(){
   try{
    const out = bakedHTML(payload);
    download(`The Doctrine of Repentance (annotated ${stamp()}).html`, out, 'text/html');
   }catch(err){
    api.setStatus('Could not build the annotated copy here \u2014 try opening the file in your browser');
   }
  }, 30);
 });
 /* ---------- "Save over my book": write straight into the file you pick ---------- */
 const owBtn = document.getElementById('ann-overwrite');
 const owMsgEl = document.getElementById('ow-msg');
 let bookHandle = null;
 if(owBtn && typeof window.showOpenFilePicker === 'function') owBtn.hidden = false;

 if(owBtn){
  const OW_LABEL = 'Save over my book';
  const FS_DB = 'watson-repentance-file-handle';
  function shortName(nm){
   nm = String(nm || 'your book file');
   return nm.length > 22 ? (nm.slice(0, 19) + '...') : nm;
  }
  function showTarget(){
   if(!owBtn) return;
   if(bookHandle){
    owBtn.textContent = 'Save over: ' + shortName(bookHandle.name);
    owBtn.title = 'Writes your notes and highlights into ' + bookHandle.name +
                  ' - shift-click to choose a different file';
   }else{
    owBtn.textContent = OW_LABEL;
    owBtn.title = 'Write your notes and highlights straight into your book file' +
                  ' - you pick the file and the browser asks permission (Chrome and Edge)';
   }
  }
  /* the toolbar status line sits behind this panel, so repeat the message here */
  function say(text, kind){
   try{ api.setStatus(text); }catch(e){}
   if(owMsgEl){
    owMsgEl.textContent = text;
    owMsgEl.setAttribute('data-kind', kind || 'info');
    owMsgEl.hidden = false;
   }
  }
  /* remember the chosen file, so a reload does not force a fresh pick */
  function store(kind, value){
   return new Promise(function(done){
    try{
     const rq = indexedDB.open(FS_DB, 1);
     rq.onupgradeneeded = function(){ try{ rq.result.createObjectStore('h'); }catch(e){} };
     rq.onerror = function(){ done(null); };
     rq.onblocked = function(){ done(null); };
     rq.onsuccess = function(){
      try{
       const tx = rq.result.transaction('h', kind === 'get' ? 'readonly' : 'readwrite');
       const os = tx.objectStore('h');
       if(kind === 'get'){
        const g = os.get('book');
        g.onsuccess = function(){ done(g.result || null); };
        g.onerror = function(){ done(null); };
       }else{
        const p = os.put(value, 'book');
        p.onsuccess = function(){ done(true); };
        p.onerror = function(){ done(null); };
       }
      }catch(e){ done(null); }
     };
    }catch(e){ done(null); }
   });
  }
  function forgetBook(){
   bookHandle = null;
   showTarget();
   store('put', null);
  }
  function why(name){
   if(name === 'NotAllowedError') return 'the browser blocked writing';
   if(name === 'NoModificationAllowedError') return 'the file is open in another program';
   if(name === 'NotFoundError') return 'the file has moved or been deleted';
   if(name === 'SecurityError') return 'the browser blocked it for security';
   if(name === 'NotReadableError' || name === 'UnreadableError') return 'the file could not be read';
   if(name === 'AbortError') return 'the browser stopped the write';
   return 'the browser refused the write';
  }
  /* Chrome forgets file permissions when the page reloads: ask again, on a click */
  async function ensureWrite(handle){
   if(!handle || typeof handle.queryPermission !== 'function') return true;
   let state = await handle.queryPermission({ mode: 'readwrite' });
   if(state === 'granted') return true;
   if(state === 'prompt' && typeof handle.requestPermission === 'function'){
    say('Chrome needs your permission again after a reload - click Allow.', 'info');
    state = await handle.requestPermission({ mode: 'readwrite' });
   }
   return state === 'granted';
  }
  async function pickBook(){
   const picks = await window.showOpenFilePicker({
    multiple: false,
    id: 'doctrine-book',
    types: [{ description: 'HTML book', accept: { 'text/html': ['.html', '.htm'] } }]
   });
   const handle = picks && picks[0];
   if(!handle) throw { name: 'AbortError', message: 'nothing picked' };
   let existing = '';
   try{ existing = await (await handle.getFile()).text(); }
   catch(e2){ throw { name: 'UnreadableError', message: 'the file could not be read' }; }
   /* never write until we are sure this is the book */
   const looksRight = existing.indexOf('id="view-mode"') >= 0 &&
                      existing.indexOf(`The Doctrine of Repentance`) >= 0 &&
                      existing.indexOf('reading-content') >= 0;
   if(!looksRight) throw { name: 'NotBookError', message: 'not this book' };
   return handle;
  }
  function fallbackDownload(reason){
   try{
    const out = bakedHTML(bakedPayload());
    const name = `The Doctrine of Repentance (annotated ${stamp()}).html`;
    const saved = download(name, out, 'text/html');
    if(saved) say(reason + ' - an annotated copy went to your Downloads instead.', 'warn');
    else say(reason + ' - use Save into HTML instead.', 'warn');
   }catch(e){
    say('Could not write or download - use Save into HTML', 'err');
   }
  }
  owBtn.addEventListener('click', function(e){
   if(owBtn.disabled) return;
   if(e.shiftKey) bookHandle = null;      /* choose a different file */
   const wantTrail = !!e.altKey;          /* hold alt for a technical trail */
   owBtn.disabled = true;
   (async function(){
    try{
     for(let pass = 0; pass < 2; pass++){
      let stage = 'pick';
      try{
       if(!bookHandle){
        say(pass ? 'Choose your book file again...' : 'Choose your book file...', 'info');
        bookHandle = await pickBook();
        store('put', bookHandle);
        showTarget();
       }
       const name = bookHandle.name || 'your book file';
       stage = 'permission';
       const allowed = await ensureWrite(bookHandle);
       if(!allowed) throw { name: 'RefusedError', message: 'permission not granted' };
       stage = 'write';
       say('Writing your notes into ' + name + '...', 'info');
       const out = bakedHTML(bakedPayload());
       const writable = await bookHandle.createWritable();
       await writable.write(out);
       await writable.close();
       say('Saved into ' + name + ' - press F5 to read the updated file' +
           (wantTrail ? '  [write ok]' : ''), 'ok');
       return;
      }catch(err){
       const n = (err && err.name) || 'Error';
       const m = String((err && err.message) || '').trim().slice(0, 80);
       if(n === 'NotBookError'){
        forgetBook();
        say('That file is not this book - nothing was written', 'err');
        return;
       }
       if(n === 'AbortError' && stage === 'pick'){
        say('Cancelled - nothing was written', 'info');
        return;
       }
       if(pass === 0 && stage !== 'pick' &&
          (n === 'NotFoundError' || n === 'NoModificationAllowedError')){
        /* the file moved or was replaced under us: forget it and pick it again, once */
        forgetBook();
        continue;
       }
       const nm = (bookHandle && bookHandle.name) ? bookHandle.name : 'that file';
       const trail = 'stage=' + stage + ' name=' + n + (m ? ' msg=' + m : '');
       forgetBook();
       if(n === 'RefusedError'){
        fallbackDownload('Chrome did not let the page write to ' + nm);
       }else{
        fallbackDownload('Could not write into ' + nm + ' (' + why(n) + ')' +
                         (wantTrail ? ' [trail: ' + trail + ']' : ''));
       }
       return;
      }
     }
    }finally{
     showTarget();
     owBtn.disabled = false;
    }
   })();
  });
  showTarget();
  /* bring back the file picked last time, when the browser kept it */
  store('get').then(function(h){
   if(h && h.name && typeof h.createWritable === 'function' && !bookHandle){
    bookHandle = h;
    showTarget();
   }
  }, function(){});
 }

 /* a baked copy carries its own marks: load them once, on first open */
 function applyBaked(){
  const block = document.getElementById(BAKED_ID);
  if(!block) return;
  let data = null;
  try{ data = JSON.parse(block.textContent || block.innerText || ''); }catch(e){ return; }
  if(!data || typeof data !== 'object') return;
  const id = String(data.baked || '');
  let applied = null;
  try{ applied = localStorage.getItem(APPLIED_KEY); }catch(e){}
  if(id && applied === id) return;
  let res = { addedH: 0, addedN: 0 };
  try{
   res = mergeIn(data.highlights || [], data.notes || []);
  }catch(err){
   return;   /* a damaged block must not break the rest of the panel */
  }
  if(id){ try{ localStorage.setItem(APPLIED_KEY, id); }catch(e){} }
  if(res.addedH + res.addedN > 0){
   api.setStatus('Opened marks saved in this file: ' + res.addedH + ' highlight' + (res.addedH === 1 ? '' : 's') +
                 ' and ' + res.addedN + ' note' + (res.addedN === 1 ? '' : 's'));
  }
 }
 applyBaked();

 /* ---------- report + markdown + print ---------- */
 document.getElementById('ann-report').addEventListener('click', function(){
  download('doctrine-of-repentance-notes-' + stamp() + '.html', reportHTML(), 'text/html');
 });
 document.getElementById('ann-print').addEventListener('click', function(){
  window.print();
 });
 function copyText(text){
  const done = function(){ api.setStatus('Markdown copied to the clipboard'); };
  const fail = function(){
   try{
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', 'readonly');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    if(ok){ done(); return; }
   }catch(e){}
   api.setStatus('Copying is blocked here \\u2014 use Report instead');
  };
  if(navigator.clipboard && navigator.clipboard.writeText){
   navigator.clipboard.writeText(text).then(done, fail);
  }else{
   fail();
  }
 }
 /* shift-click Report to copy markdown instead */
 document.getElementById('ann-report').addEventListener('click', function(e){
  if(e.shiftKey){ e.preventDefault(); e.stopImmediatePropagation(); copyText(markdown()); }
 }, true);
})();
</script>
"""
html = sub_once(html, "\n</body>\n</html>", PANEL_JS + "</body>\n</html>", "panel behaviour")

io.open(PATH, "w", encoding="utf-8").write(html)
print("\nwrote %s (%.1f MB)" % (PATH, len(html.encode("utf-8")) / 1e6))
