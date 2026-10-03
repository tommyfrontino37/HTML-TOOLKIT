#!/usr/bin/env python3
"""Add per-quote notes (type, edit, hide) to 'The Doctrine of Repentance' HTML.

Run AFTER add_dark_mode.py and add_highlights.py -- it patches the themed,
highlight-enabled file in place.

Feature summary
  * Select a quote -> the selection popup gains a note button -> a small editor
    opens where you type the note. Save / auto-save on dismiss / delete.
  * The quote gets a dotted underline + a numbered marker; the note itself shows
    as a card right below the paragraph it belongs to.
  * Hiding: the toolbar toggle hides every note card, marker and underline (your
    notes stay saved), and each card can also be collapsed on its own.
  * Notes live in localStorage under 'watson-repentance-notes'.

Two systems share one text model: add_notes.py patches the highlighter's text
walker so note chrome (cards/markers) is never counted in character offsets,
which keeps highlight and note anchors stable.
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
NOTE_CSS = """/* ---------- notes on quotes ---------- */
:root{--control-bg:#fffefa;--control-border:#cbd0c2;--note-accent:#a8761f;--note-pill-bg:rgba(168,118,31,.14);--note-pill-line:rgba(168,118,31,.5);--note-bg:#fdf8e9;--note-line:#e7dcb6;--note-ink:#fffdf7;--danger-ink:#8c2f28}
html[data-theme="dark"]{--note-accent:#d3b363;--note-pill-bg:rgba(211,179,99,.16);--note-pill-line:rgba(211,179,99,.5);--note-bg:#232a20;--note-line:#454c34;--note-ink:#131512;--danger-ink:#e79a92}

.note-anchor{text-decoration:underline dotted;text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:var(--note-accent);cursor:pointer}
.note-anchor:hover{text-decoration-style:solid}
html[data-notes="off"] .note-anchor{text-decoration:none;cursor:auto}
html[data-notes="off"] .note-marker,html[data-notes="off"] .note-card{display:none}

.note-marker{display:inline-block;vertical-align:super;margin:0 1px 0 2px;cursor:pointer;line-height:0}
.note-marker b{display:inline-block;min-width:14px;height:14px;padding:0 3px;border-radius:4px;background:var(--note-pill-bg);border:1px solid var(--note-pill-line);color:var(--note-accent);font:600 10px/12px system-ui,sans-serif;text-align:center;-webkit-print-color-adjust:exact;print-color-adjust:exact}

.note-card{margin:14px 0 18px;padding:10px 14px 12px;border:1px solid var(--note-line);border-left:3px solid var(--note-accent);border-radius:0 8px 8px 0;background:var(--note-bg);color:var(--ink);font:14px/1.6 system-ui,sans-serif}
.note-card-head{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:20px}
.note-badge{font:600 11px/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--note-accent)}
.note-close{width:22px;height:22px;min-height:0;padding:0;border:1px solid transparent;border-radius:5px;background:transparent;color:var(--muted);font:15px/1 system-ui,sans-serif;cursor:pointer}
.note-close:hover{background:rgba(128,128,128,.16);color:var(--ink)}
.note-quote{margin:5px 0 7px;padding:0 0 0 9px;border-left:2px solid var(--note-line);font-style:italic;font-size:13px;line-height:1.5;color:var(--muted);overflow-wrap:break-word}
.note-body-text{margin:0;white-space:pre-wrap;overflow-wrap:break-word}
.note-actions{display:flex;gap:6px;margin-top:10px}
.note-actions button{font:12px/1 system-ui,sans-serif;padding:5px 9px;min-height:26px;border-radius:5px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);cursor:pointer}
.note-actions button:hover{background:rgba(128,128,128,.16)}
.note-card.is-closed{display:none}
.note-card.note-flash{animation:noteFlash 1.1s ease-out}
@keyframes noteFlash{from{box-shadow:0 0 0 3px var(--note-pill-line)}to{box-shadow:0 0 0 0 rgba(0,0,0,0)}}
@media (prefers-reduced-motion: reduce){.note-card.note-flash{animation:none}}

.note-add{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;min-height:0;padding:0;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);cursor:pointer}
.note-add svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.note-add:hover{background:rgba(128,128,128,.16)}

.note-editor{position:fixed;z-index:40;width:min(360px,calc(100vw - 20px));padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);box-shadow:0 12px 30px rgba(0,0,0,.3);font:13px/1.5 system-ui,sans-serif}
.note-editor[hidden]{display:none}
.note-editor-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.note-editor-title{font:600 11px/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.note-editor-close{width:24px;height:24px;min-height:0;padding:0;border:1px solid transparent;border-radius:6px;background:transparent;color:var(--muted);font:16px/1 system-ui,sans-serif;cursor:pointer}
.note-editor-close:hover{background:rgba(128,128,128,.16);color:var(--ink)}
.note-editor-quote{margin:0 0 8px;padding:0 0 0 9px;border-left:3px solid var(--note-line);font-style:italic;font-size:12px;color:var(--muted);max-height:64px;overflow:auto}
.note-editor-quote[hidden]{display:none}
.note-editor-input{display:block;width:100%;min-height:92px;padding:8px 9px;border:1px solid var(--control-border);border-radius:6px;background:var(--control-bg);color:var(--ink);font:13px/1.55 system-ui,sans-serif;resize:vertical;box-sizing:border-box}
.note-editor-actions{display:flex;gap:6px;margin-top:8px}
.note-editor-actions button{padding:7px 12px;min-height:30px;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);font:13px/1 system-ui,sans-serif;cursor:pointer}
.note-editor-actions button:hover{background:rgba(128,128,128,.16)}
.note-editor-save{background:var(--accent);color:var(--note-ink);border-color:transparent;font-weight:600}
.note-editor-save:hover{background:var(--accent);opacity:.92}
.note-editor-delete{color:var(--danger-ink)}
.note-editor-delete[hidden]{display:none}
.note-armed{background:rgba(210,86,80,.35);border-color:#c0625c;outline:2px solid rgba(210,86,80,.55);outline-offset:1px;color:inherit}

.notes-toggle{display:inline-flex;align-items:center;gap:4px;height:26px;min-height:0;padding:0 7px;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);cursor:pointer;flex:none}
.notes-toggle svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.notes-toggle:hover{background:rgba(128,128,128,.16)}
html[data-notes="off"] .notes-toggle{color:var(--muted)}
.notes-count{font:600 11px/1 system-ui,sans-serif;color:var(--note-accent);min-width:8px;text-align:center}
.notes-count.is-zero{color:var(--muted)}

.hl-status{max-width:min(360px,calc(100vw - 64px));white-space:normal;text-align:right}

/* keep the sticky toolbar on a single row: below 1600px the theme button is
   icon-only (its tooltip and aria-label still spell it out) */
@media (min-width:601px){
 .theme-toggle-text{display:none}
 .theme-toggle{min-width:32px;justify-content:center}
}

"""
html = sub_once(
    html,
    'html[data-theme="dark"] mark.hl:hover{box-shadow:0 0 0 1px rgba(200,200,200,.5)}',
    'html[data-theme="dark"] mark.hl:hover{box-shadow:0 0 0 1px rgba(200,200,200,.5)}\n' + NOTE_CSS,
    "notes css",
)

# print: notes print as light cards, editor never prints
html = sub_once(
    html,
    ".hl-pop,.hl-status{display:none}",
    ".hl-pop,.hl-status,.note-editor{display:none}"
    ".note-card{background:#fff;border-color:#ccc}"
    ".note-card .note-quote{color:#333}"
    'html[data-theme="dark"] .note-card{background:#fff;color:#000;border-color:#ccc}'
    'html[data-theme="dark"] .note-card .note-quote{color:#333}'
    'html[data-theme="dark"] .note-anchor{text-decoration-color:#8a6a1c}html[data-notes="on"] .note-card.is-closed{display:block}.note-close,.note-actions{display:none}',
    "print note rules",
)

# ==========================================================================
# 2. toolbar toggle
# ==========================================================================
TOGGLE = (
    '<button type="button" id="notes-toggle" class="notes-toggle" aria-pressed="true" '
    'title="Hide notes" aria-label="Hide notes">'
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path d="M14.5 20H5.8A1.8 1.8 0 0 1 4 18.2V5.8A1.8 1.8 0 0 1 5.8 4h12.4A1.8 1.8 0 0 1 20 5.8v8.4"/>'
    '<path d="M14.5 20v-4a1.8 1.8 0 0 1 1.8-1.8H20"/>'
    '<path d="M8 9.2h8"/><path d="M8 12.6h4.5"/></svg>'
    '<span class="notes-count" id="notes-count">0</span></button>'
)
html = sub_once(
    html,
    '<button type="button" id="theme-toggle"',
    TOGGLE + '<button type="button" id="theme-toggle"',
    "toolbar toggle",
)

# ==========================================================================
# 3. share the text model with the highlighter
# ==========================================================================
# 3a. never count note chrome (cards, markers) in character offsets
html = sub_once(
    html,
    "acceptNode: function(n){ return n.nodeValue ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT; }",
    "acceptNode: function(n){\n"
    "    if(!n.nodeValue) return NodeFilter.FILTER_REJECT;\n"
    "    if(n.parentElement && n.parentElement.closest('.note-card,.note-marker')) return NodeFilter.FILTER_REJECT;\n"
    "    return NodeFilter.FILTER_ACCEPT;\n"
    "   }",
    "walker excludes note chrome",
)

# 3b. a selection made inside a note card is not book text
html = sub_once(
    html,
    "if(!el || !el.closest || !el.closest('.reading-content')) return null;",
    "if(!el || !el.closest || !el.closest('.reading-content') || el.closest('.note-card')) return null;",
    "walk-selection guard",
)

# 3c. clicking note chrome must not delete a highlight underneath
html = sub_once(
    html,
    "if(el.closest('a')) return;",
    "if(el.closest('a,.note-anchor,.note-marker,.note-card,.note-add,.note-editor')) return;",
    "mark-click guard",
)

# 3d. expose the shared helpers
html = sub_once(
    html,
    " renderAll();\n syncControls();\n})();",
    " window.__bookAPI = {\n"
    "  selectionRanges: selectionRanges,\n"
    "  textNodes: textNodes,\n"
    "  pageOf: pageOf,\n"
    "  pageContent: pageContent,\n"
    "  setStatus: setStatus,\n"
    "  getStore: function(){\n"
    "   return store.map(function(r){ return {page:r.page, start:r.start, end:r.end, color:r.color}; });\n"
    "  },\n"
    "  setStore: function(list){\n"
    "   store = (list || []).filter(function(r){\n"
    "    return r && typeof r.page === 'number' && typeof r.start === 'number'\n"
    "        && typeof r.end === 'number' && r.end > r.start && COLORS.indexOf(r.color) >= 0;\n"
    "   }).map(function(r){ return {page:r.page, start:r.start, end:r.end, color:r.color}; });\n"
    "   normalize();\n"
    "   save();\n"
    "   renderAll();\n"
    "   return store.length;\n"
    "  },\n"
    "  renderAll: renderAll,\n"
    "  renderPage: renderPage\n"
    " };\n"
    " renderAll();\n syncControls();\n})();",
    "shared api",
)

# ==========================================================================
# 4. the notes module
# ==========================================================================
NOTES_JS = """
<script>
/* ---------- notes on quotes ---------- */
(function(){
 const api = window.__bookAPI;
 if(!api) return;

 const KEY = 'watson-repentance-notes';
 const VIS_KEY = 'watson-repentance-notes-visible';
 const BLOCK_SEL = 'p,h2,h3,h4,li,blockquote,figure';

 let notes = load();
 let visible = loadVisible();
 let editing = null;
 let armedBtn = null, armTimer = null, flashTimer = null;

 /* ---------- storage ---------- */
 function load(){
  try{
   const raw = localStorage.getItem(KEY);
   if(!raw) return [];
   const data = JSON.parse(raw);
   if(!Array.isArray(data)) return [];
   return data.filter(function(n){
    return n && typeof n.id === 'string' && typeof n.page === 'number'
      && typeof n.start === 'number' && typeof n.end === 'number' && n.end > n.start
      && typeof n.body === 'string';
   }).map(function(n){
    return { id:n.id, page:n.page, start:n.start, end:n.end, body:n.body,
             quote:(typeof n.quote === 'string' ? n.quote : ''), created:n.created || 0, updated:n.updated || 0 };
   });
  }catch(e){ return []; }
 }
 function persist(){
  try{ localStorage.setItem(KEY, JSON.stringify(notes)); }catch(e){}
  syncToggle();
 }
 function loadVisible(){
  try{ const v = localStorage.getItem(VIS_KEY); return v === null ? true : v === '1'; }catch(e){ return true; }
 }
 function persistVisible(){
  try{ localStorage.setItem(VIS_KEY, visible ? '1' : '0'); }catch(e){}
 }
 function applyVisibility(){
  document.documentElement.setAttribute('data-notes', visible ? 'on' : 'off');
 }
 function ordered(){
  return notes.slice().sort(function(a,b){ return a.page - b.page || a.start - b.start || a.end - b.end; });
 }
 function noteById(id){
  const list = notes.filter(function(n){ return n.id === id; });
  return list.length ? list[0] : null;
 }
 function numberOf(id){
  const list = ordered();
  for(let i = 0; i < list.length; i++) if(list[i].id === id) return i + 1;
  return 0;
 }

 /* ---------- text helpers (same walker as the highlighter) ---------- */
 function nodeAt(content, offset){
  const nodes = api.textNodes(content);
  let acc = 0;
  for(let i = 0; i < nodes.length; i++){
   const len = nodes[i].nodeValue.length;
   if(offset <= acc + len) return { node: nodes[i], offset: Math.max(0, offset - acc) };
   acc += len;
  }
  const last = nodes[nodes.length - 1];
  return last ? { node: last, offset: last.nodeValue.length } : null;
 }
 /* nearest block element (paragraph etc.) at or after a character offset;
    boundaries that sit in whitespace between paragraphs attach to the next one */
 function blockFor(content, offset){
  const nodes = api.textNodes(content);
  let acc = 0, found = null;
  for(let i = 0; i < nodes.length; i++){
   const n = nodes[i], len = n.nodeValue.length;
   if(offset <= acc + len && /\\S/.test(n.nodeValue)){ found = n; break; }
   acc += len;
  }
  if(!found){
   acc = 0;
   for(let i = 0; i < nodes.length; i++){
    const n = nodes[i], len = n.nodeValue.length;
    if(acc >= offset) break;
    if(/\\S/.test(n.nodeValue)) found = n;
    acc += len;
   }
  }
  if(!found) return null;
  let el = found.parentElement;
  while(el && el !== content && !el.matches(BLOCK_SEL)) el = el.parentElement;
  return (el && el !== content) ? el : null;
 }
 function textLength(content){
  return api.textNodes(content).reduce(function(a,n){ return a + n.nodeValue.length; }, 0);
 }
 function textAt(content, start, end){
  const nodes = api.textNodes(content);
  let acc = 0, out = '';
  for(let i = 0; i < nodes.length; i++){
   const n = nodes[i], ns = acc, ne = acc + n.nodeValue.length;
   if(ne > start && ns < end) out += n.nodeValue.slice(Math.max(0, start - ns), Math.min(n.nodeValue.length, end - ns));
   acc = ne;
   if(acc >= end) break;
  }
  return out;
 }

 /* ---------- rendering ---------- */
 function clearChrome(content){
  Array.prototype.forEach.call(content.querySelectorAll('.note-card'), function(el){ el.remove(); });
  Array.prototype.forEach.call(content.querySelectorAll('.note-marker'), function(el){ el.remove(); });
  Array.prototype.forEach.call(content.querySelectorAll('.note-anchor'), function(el){
   const parent = el.parentNode;
   if(!parent) return;
   while(el.firstChild) parent.insertBefore(el.firstChild, el);
   parent.removeChild(el);
  });
  content.normalize();
 }
 function wrapAnchor(content, start, end, id){
  const nodes = api.textNodes(content);
  let acc = 0;
  const parts = [];
  for(let i = 0; i < nodes.length; i++){
   const n = nodes[i], ns = acc, ne = acc + n.nodeValue.length;
   if(ne > start && ns < end) parts.push({ node:n, from:Math.max(0, start - ns), to:Math.min(n.nodeValue.length, end - ns) });
   acc = ne;
   if(acc >= end) break;
  }
  parts.forEach(function(p){
   let target = p.node;
   if(p.from > 0) target = target.splitText(p.from);
   const len = p.to - p.from;
   if(len <= 0 || !target.nodeValue) return;
   if(len < target.nodeValue.length) target.splitText(len);
   const span = document.createElement('span');
   span.className = 'note-anchor';
   span.setAttribute('data-note-id', id);
   span.title = 'Click to show or hide this note';
   target.parentNode.insertBefore(span, target);
   span.appendChild(target);
  });
 }
 function insertMarker(content, offset, id, num){
  const at = nodeAt(content, offset);
  if(!at) return;
  const sup = document.createElement('sup');
  sup.className = 'note-marker';
  sup.setAttribute('data-note-id', id);
  sup.title = 'Note ' + num + ' \\u2014 click to show or hide it';
  const b = document.createElement('b');
  b.textContent = String(num);
  sup.appendChild(b);
  const node = at.node;
  if(at.offset > 0 && at.offset < node.nodeValue.length){
   const rest = node.splitText(at.offset);
   rest.parentNode.insertBefore(sup, rest);
  }else if(at.offset >= node.nodeValue.length){
   node.parentNode.insertBefore(sup, node.nextSibling);
  }else{
   node.parentNode.insertBefore(sup, node);
  }
 }
 function buildCard(note, num, quoteText){
  const card = document.createElement('aside');
  card.className = 'note-card';
  card.setAttribute('data-note-id', note.id);
  card.setAttribute('aria-label', 'Note ' + num);

  const head = document.createElement('div');
  head.className = 'note-card-head';
  const badge = document.createElement('span');
  badge.className = 'note-badge';
  badge.textContent = 'Note ' + num;
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'note-close';
  close.setAttribute('data-note-close', '1');
  close.setAttribute('aria-label', 'Hide note ' + num);
  close.title = 'Hide this note (click its number in the text to reopen)';
  close.textContent = '\u00d7';
  head.appendChild(badge);
  head.appendChild(close);

  const q = document.createElement('blockquote');
  q.className = 'note-quote';
  q.textContent = quoteText ? '\\u201c' + quoteText + '\\u201d' : '';

  const body = document.createElement('p');
  body.className = 'note-body-text';
  body.textContent = note.body;

  const actions = document.createElement('div');
  actions.className = 'note-actions';
  const edit = document.createElement('button');
  edit.type = 'button';
  edit.setAttribute('data-note-edit', '1');
  edit.textContent = 'Edit';
  const del = document.createElement('button');
  del.type = 'button';
  del.setAttribute('data-note-del', '1');
  del.textContent = 'Delete';
  actions.appendChild(edit);
  actions.appendChild(del);

  card.appendChild(head);
  if(quoteText) card.appendChild(q);
  card.appendChild(body);
  card.appendChild(actions);
  if(!openIds[note.id]) card.classList.add('is-closed');
  return card;
 }
 let openIds = {};
 function renderPage(page){
  const content = api.pageContent(page);
  if(!content) return;
  clearChrome(content);
  const mine = notes.filter(function(n){ return n.page === page; }).sort(function(a,b){ return a.start - b.start; });
  if(!mine.length) return;
  const total = textLength(content);
  mine.forEach(function(n){
   if(n.start >= total) return;
   const end = Math.min(n.end, total);
   const quote = textAt(content, n.start, end) || n.quote;
   const num = numberOf(n.id);
   wrapAnchor(content, n.start, end, n.id);
   insertMarker(content, end, n.id, num);
   const card = buildCard(n, num, quote);
   const block = blockFor(content, n.start);
   if(!block){
    content.appendChild(card);
   }else{
    /* several notes can belong to one paragraph: keep cards in text order */
    let anchor = block;
    while(anchor.nextElementSibling && anchor.nextElementSibling.classList &&
          anchor.nextElementSibling.classList.contains('note-card')) anchor = anchor.nextElementSibling;
    anchor.insertAdjacentElement('afterend', card);
   }
  });
 }
 function renderAll(){
  const pages = {};
  notes.forEach(function(n){ pages[n.page] = 1; });
  Object.keys(pages).forEach(function(p){ renderPage(parseInt(p, 10)); });
 }
 function cardFor(id){
  return document.querySelector('.note-card[data-note-id="' + id + '"]');
 }
 function flash(id){
  const card = cardFor(id);
  if(!card) return;
  card.classList.remove('note-flash');
  void card.offsetWidth;
  card.classList.add('note-flash');
  if(flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(function(){ card.classList.remove('note-flash'); }, 1200);
 }

 /* ---------- create / update / delete ---------- */
 function createNote(range, body){
  const content = api.pageContent(range.page);
  const quote = content ? textAt(content, range.start, range.end) : '';
  const now = Date.now();
  const note = {
   id: 'n' + now + '-' + Math.floor(Math.random() * 10000),
   page: range.page, start: range.start, end: range.end,
   quote: quote.slice(0, 400), body: body, created: now, updated: now
  };
  notes.push(note);
  persist();
  openIds[note.id] = 1;   /* show the note you just wrote */
  renderPage(note.page);
  const card = cardFor(note.id);
  if(card && card.scrollIntoView) card.scrollIntoView({ block:'nearest' });
  flash(note.id);
  api.setStatus('Note ' + numberOf(note.id) + ' saved');
 }
 function updateNote(id, body){
  const note = notes.filter(function(n){ return n.id === id; })[0];
  if(!note) return;
  note.body = body;
  note.updated = Date.now();
  persist();
  openIds[id] = 1;
  renderPage(note.page);
  flash(id);
  api.setStatus('Note saved');
 }
 function deleteNote(id){
  const note = notes.filter(function(n){ return n.id === id; })[0];
  if(!note) return;
  notes = notes.filter(function(n){ return n.id !== id; });
  delete openIds[id];
  persist();
  renderPage(note.page);
  api.setStatus('Note deleted');
 }
 function setOpen(id, value){
  if(value) openIds[id] = 1; else delete openIds[id];
  const card = cardFor(id);
  if(card) card.classList.toggle('is-closed', !value);
 }
 /* notes start out closed: nothing but the number shows until it is clicked */
 function closeAllNotes(){
  openIds = {};
  const pages = {};
  notes.forEach(function(n){ pages[n.page] = 1; });
  Object.keys(pages).forEach(function(p){ renderPage(parseInt(p, 10)); });
 }
 function showNote(id){
  /* always SHOW the note (Go to must never hide the thing it was asked for) */
  if(!cardFor(id)) renderPage(noteById(id) ? noteById(id).page : 1);
  setOpen(id, true);
  const card = cardFor(id);
  if(card && card.scrollIntoView) card.scrollIntoView({ block:'nearest' });
  flash(id);
 }
 function openNote(id){
  const card = cardFor(id);
  if(!card) return;
  if(openIds[id]){ setOpen(id, false); return; }
  setOpen(id, true);
  if(card.scrollIntoView) card.scrollIntoView({ block:'nearest' });
  flash(id);
 }

 /* ---------- armed (two-step) actions ---------- */
 function disarm(){
  if(armedBtn){
   armedBtn.classList.remove('note-armed');
   if(armedBtn.getAttribute('data-arm-label') !== null) armedBtn.textContent = armedBtn.getAttribute('data-arm-label');
   armedBtn = null;
  }
  if(armTimer){ clearTimeout(armTimer); armTimer = null; }
 }
 function arm(btn, label, fn){
  if(armedBtn === btn){ disarm(); fn(); return; }
  disarm();
  armedBtn = btn;
  if(btn.getAttribute('data-arm-label') === null) btn.setAttribute('data-arm-label', btn.textContent);
  btn.classList.add('note-armed');
  btn.textContent = label;
  api.setStatus(label);
  armTimer = setTimeout(disarm, 3500);
 }
 document.addEventListener('mouseout', function(e){
  if(armedBtn && e.target === armedBtn) disarm();
 });

 /* ---------- note editor ---------- */
 const ed = document.createElement('div');
 ed.className = 'note-editor';
 ed.hidden = true;
 ed.setAttribute('role', 'dialog');
 ed.setAttribute('aria-label', 'Note editor');
 ed.innerHTML =
  '<div class="note-editor-head"><span class="note-editor-title">New note</span>' +
  '<button type="button" class="note-editor-close" data-note-close="1" aria-label="Close the note editor" title="Close (saves your note)">\\u00d7</button></div>' +
  '<blockquote class="note-editor-quote"></blockquote>' +
  '<textarea class="note-editor-input" rows="5" placeholder="Type your note about this quote\\u2026" aria-label="Note text"></textarea>' +
  '<div class="note-editor-actions"><button type="button" class="note-editor-save" data-note-save="1">Save note</button>' +
  '<button type="button" class="note-editor-delete" data-note-delete="1" hidden>Delete</button></div>';
 document.body.appendChild(ed);
 const edTitle = ed.querySelector('.note-editor-title');
 const edQuote = ed.querySelector('.note-editor-quote');
 const edInput = ed.querySelector('.note-editor-input');
 const edDelete = ed.querySelector('.note-editor-delete');

 function placeEditor(rect){
  ed.hidden = false;
  const w = ed.offsetWidth, h = ed.offsetHeight;
  let left = rect ? rect.left + rect.width / 2 - w / 2 : (window.innerWidth - w) / 2;
  left = Math.max(10, Math.min(left, window.innerWidth - w - 10));
  let top;
  if(rect){
   top = rect.bottom + 10;
   if(top + h > window.innerHeight - 10) top = Math.max(10, rect.top - h - 10);
  }else{
   top = Math.max(10, (window.innerHeight - h) / 2);
  }
  ed.style.left = Math.round(left) + 'px';
  ed.style.top = Math.round(top) + 'px';
 }
 function openEditor(opts){
  editing = {
   isNew: !opts.note,
   id: opts.note ? opts.note.id : null,
   range: opts.range || null,
   original: opts.note ? opts.note.body : ''
  };
  edTitle.textContent = opts.note ? ('Note ' + numberOf(opts.note.id)) : 'New note';
  edQuote.textContent = opts.quote ? '\\u201c' + opts.quote + '\\u201d' : '';
  edQuote.hidden = !opts.quote;
  edInput.value = opts.note ? opts.note.body : '';
  edDelete.hidden = !opts.note;
  placeEditor(opts.rect || null);
  edInput.focus();
  edInput.setSelectionRange(edInput.value.length, edInput.value.length);
 }
 function saveEditor(){
  if(!editing) return;
  const body = edInput.value.trim();
  const state = editing;
  if(!body){
   api.setStatus(state.isNew ? 'Nothing typed \\u2014 no note added' : 'Note left unchanged \\u2014 use Delete to remove it');
   closeEditor(false);
   return;
  }
  if(state.isNew) createNote(state.range, body);
  else if(body !== state.original) updateNote(state.id, body);
  else api.setStatus('Note unchanged');
  closeEditor(false);
 }
 function closeEditor(commit){
  if(!editing) return;
  const state = editing;
  editing = null;
  if(commit){
   const body = edInput.value.trim();
   if(body && (state.isNew || body !== state.original)){
    if(state.isNew) createNote(state.range, body);
    else updateNote(state.id, body);
   }
  }
  ed.hidden = true;
 }

 /* ---------- wiring ---------- */
 const toggle = document.getElementById('notes-toggle');
 const countEl = document.getElementById('notes-count');
 function syncToggle(){
  const n = notes.length;
  if(countEl){
   countEl.textContent = String(n);
   countEl.classList.toggle('is-zero', n === 0);
  }
  if(toggle){
   toggle.setAttribute('aria-pressed', visible ? 'true' : 'false');
   const label = n
     ? (visible ? 'Hide notes (' + n + ')' : 'Show notes (' + n + ')')
     : 'No notes yet \\u2014 select text, then use the note button';
   toggle.title = label;
   toggle.setAttribute('aria-label', label);
  }
 }
 if(toggle){
  toggle.addEventListener('click', function(e){
   e.preventDefault();
   if(!notes.length){ api.setStatus('No notes yet \\u2014 select some text, then click the note icon'); return; }
   visible = !visible;
   persistVisible();
   applyVisibility();
   syncToggle();
   if(!visible){
    closeEditor(true);
    closeAllNotes();
    api.setStatus('Notes hidden \\u2014 they are still saved');
   }else{
    api.setStatus('Notes shown');
   }
  });
 }

 /* note button inside the selection popup */
 const pop = document.querySelector('.hl-pop');
 if(pop){
  const add = document.createElement('button');
  add.type = 'button';
  add.className = 'note-add';
  add.setAttribute('data-note-add', '1');
  add.title = 'Add a note about the selected text';
  add.setAttribute('aria-label', add.title);
  add.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
   '<path d="M14.5 20H5.8A1.8 1.8 0 0 1 4 18.2V5.8A1.8 1.8 0 0 1 5.8 4h12.4A1.8 1.8 0 0 1 20 5.8v8.4"/>' +
   '<path d="M14.5 20v-4a1.8 1.8 0 0 1 1.8-1.8H20"/><path d="M8 9.2h8"/><path d="M8 12.6h4.5"/></svg>';
  pop.appendChild(add);
 }

 document.addEventListener('click', function(e){
  const el = e.target;
  if(!el || !el.closest) return;

  if(el.closest('[data-note-add]')){
   e.preventDefault();
   if(document.body.getAttribute('data-mode') === 'original'){ api.setStatus('Switch to Reading view to add notes'); return; }
   const ranges = api.selectionRanges();
   if(!ranges || !ranges.length){ api.setStatus('Select some text first'); return; }
   const range = ranges[0];
   const content = api.pageContent(range.page);
   const quote = content ? textAt(content, range.start, range.end) : '';
   const sel = window.getSelection();
   let rect = null;
   if(sel && sel.rangeCount) rect = sel.getRangeAt(0).getBoundingClientRect();
   const existing = notes.filter(function(n){
    return n.page === range.page && n.start === range.start && n.end === range.end;
   })[0] || null;
   openEditor({ range: range, quote: quote, note: existing, rect: rect });
   return;
  }

  const closeBtn = el.closest('[data-note-close]');
  if(closeBtn){
   e.preventDefault();
   const card = closeBtn.closest('.note-card');
   if(card) setOpen(card.getAttribute('data-note-id'), false);
   return;
  }
  const editBtn = el.closest('[data-note-edit]');
  if(editBtn){
   e.preventDefault();
   const card = editBtn.closest('.note-card');
   if(!card) return;
   const id = card.getAttribute('data-note-id');
   const note = notes.filter(function(n){ return n.id === id; })[0];
   if(!note) return;
   let rect = null;
   const r2 = card.getBoundingClientRect();
   rect = { left:r2.left, right:r2.right, top:r2.top, bottom:r2.bottom, width:r2.width, height:r2.height };
   openEditor({ note: note, quote: note.quote, rect: rect });
   return;
  }
  const delBtn = el.closest('[data-note-del]');
  if(delBtn){
   e.preventDefault();
   const card = delBtn.closest('.note-card');
   if(!card) return;
   const id = card.getAttribute('data-note-id');
   arm(delBtn, 'Click again to delete', function(){ deleteNote(id); });
   return;
  }
  const marker = el.closest('.note-marker');
  if(marker){
   if(!visible) return;
   e.preventDefault();
   openNote(marker.getAttribute('data-note-id'));
   return;
  }
  const anchor = el.closest('.note-anchor');
  if(anchor){
   if(!visible) return;
   const sel = window.getSelection();
   if(sel && !sel.isCollapsed) return;
   e.preventDefault();
   openNote(anchor.getAttribute('data-note-id'));
   return;
  }
 });

 ed.addEventListener('click', function(e){
  const el = e.target;
  if(!el || !el.closest) return;
  if(el.closest('[data-note-save]')){ e.preventDefault(); saveEditor(); return; }
  if(el.closest('[data-note-close]')){ e.preventDefault(); closeEditor(true); return; }
  if(el.closest('[data-note-delete]')){
   e.preventDefault();
   if(!editing || !editing.id) return;
   const id = editing.id;
   arm(el.closest('[data-note-delete]'), 'Click again to delete', function(){
    closeEditor(false);
    deleteNote(id);
   });
   return;
  }
 });
 edInput.addEventListener('keydown', function(e){
  if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); closeEditor(true); }
  else if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); saveEditor(); }
 });
 document.addEventListener('mousedown', function(e){
  if(ed.hidden) return;
  const el = e.target;
  if(el && el.closest && el.closest('.note-editor')) return;
  closeEditor(true);
 }, true);

 /* ---------- api for the annotations panel ---------- */
 window.__notesAPI = {
  get: function(){
   return notes.map(function(n){
    return {id:n.id, page:n.page, start:n.start, end:n.end, body:n.body, quote:n.quote, created:n.created, updated:n.updated};
   });
  },
  set: function(list){
   notes = (list || []).filter(function(n){
    return n && typeof n.id === 'string' && typeof n.page === 'number'
      && typeof n.start === 'number' && typeof n.end === 'number' && n.end > n.start
      && typeof n.body === 'string';
   }).map(function(n){
    return {id:n.id, page:n.page, start:n.start, end:n.end, body:n.body,
            quote:(typeof n.quote === 'string' ? n.quote : ''), created:n.created || 0, updated:n.updated || 0};
   });
   persist();
   closeAllNotes();
   renderAll();
   syncToggle();
   return notes.length;
  },
  open: openNote,
  show: showNote,
  numberOf: numberOf,
  renderAll: renderAll,
  isVisible: function(){ return visible; },
  setVisible: function(v){ visible = !!v; persistVisible(); applyVisibility(); syncToggle(); }
 };

 /* ---------- init ---------- */
 applyVisibility();
 renderAll();
 syncToggle();
})();
</script>
"""
html = sub_once(
    html,
    "\n</body>\n</html>",
    NOTES_JS + "\n</body>\n</html>",
    "notes module",
)

io.open(PATH, "w", encoding="utf-8").write(html)
print("\nwrote %s (%.1f MB)" % (PATH, len(html.encode("utf-8")) / 1e6))
