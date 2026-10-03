#!/usr/bin/env python3
"""Add a text highlighter (4 colours + eraser) to 'The Doctrine of Repentance' HTML.

Run AFTER add_dark_mode.py -- it patches the themed file in place.

How the feature works
  * Highlights are stored as character offsets inside each page's .reading-content
    text, e.g. {page: 12, start: 40, end: 91, color: 'yellow'}. Because the text is
    static, those offsets survive reloads exactly.
  * Painted highlights are <mark class="hl hl-yellow"> spans. Re-rendering a page
    unwraps the old marks, then re-wraps from the stored ranges, so overlaps and
    trims always stay consistent.
  * Paint over an existing highlight and the old range is trimmed/split around the
    new one (classic highlighter behaviour).
  * Stored in localStorage, so highlights come back on the next visit.
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
HL_CSS = """/* ---------- text highlighting ---------- */
:root{--hl-yellow:#fdf0a6;--hl-green:#c9edc5;--hl-blue:#c3e3f8;--hl-red:#fac9c4}
html[data-theme="dark"]{--hl-yellow:rgba(228,196,72,.42);--hl-green:rgba(96,186,112,.40);--hl-blue:rgba(84,158,226,.44);--hl-red:rgba(226,98,92,.40)}

mark.hl{border-radius:3px;padding:.06em .05em;color:inherit;-webkit-box-decoration-break:clone;box-decoration-break:clone;cursor:pointer}
mark.hl-yellow{background:var(--hl-yellow)}
mark.hl-green{background:var(--hl-green)}
mark.hl-blue{background:var(--hl-blue)}
mark.hl-red{background:var(--hl-red)}
mark.hl:hover{box-shadow:0 0 0 1px rgba(128,128,128,.65)}
mark.hl{-webkit-print-color-adjust:exact;print-color-adjust:exact}

.hl-tools{display:inline-flex;align-items:center;gap:4px}
.hl-swatch{width:24px;height:24px;min-height:0;padding:0;border-radius:6px;border:1px solid var(--control-border);cursor:pointer;flex:none}
.hl-swatch[data-hl-color="yellow"]{background:var(--hl-yellow)}
.hl-swatch[data-hl-color="green"]{background:var(--hl-green)}
.hl-swatch[data-hl-color="blue"]{background:var(--hl-blue)}
.hl-swatch[data-hl-color="red"]{background:var(--hl-red)}
.hl-swatch:hover{filter:brightness(.95)}
.hl-swatch[aria-pressed="true"]{outline:2px solid var(--accent);outline-offset:2px}
.hl-swatch.hl-swatch-lg{width:30px;height:30px}
.hl-pop .hl-erase{width:30px;height:30px}
.hl-pop .hl-swatch[aria-pressed="true"]{outline-offset:1px}
.hl-pop .hl-erase svg{width:17px;height:17px}
.hl-erase,.hl-clear-all{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;min-height:0;padding:0;border-radius:6px;border:1px solid var(--control-border);background:var(--control-bg);color:var(--ink);cursor:pointer;flex:none}
.hl-erase svg,.hl-clear-all svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.hl-erase:hover,.hl-clear-all:hover{background:rgba(128,128,128,.18)}
.hl-clear-all.hl-armed{background:rgba(210,86,80,.35);border-color:#c0625c;outline:2px solid rgba(210,86,80,.55);outline-offset:1px}
.hl-clear-all[hidden]{display:none}

.hl-pop{position:fixed;z-index:30;display:flex;align-items:center;gap:5px;padding:6px 7px;border:1px solid var(--line);background:var(--paper);border-radius:9px;box-shadow:0 8px 22px rgba(0,0,0,.24)}
.hl-pop[hidden]{display:none}

.hl-status{position:absolute;right:28px;top:calc(100% + 7px);padding:5px 9px;border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:6px;font:12px/1.3 system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.14);pointer-events:none}
.hl-status[hidden]{display:none}
html[data-theme="dark"] mark.hl:hover{box-shadow:0 0 0 1px rgba(200,200,200,.5)}

"""
html = sub_once(html, "@media print{", HL_CSS + "@media print{", "highlight css")

# print: keep highlights visible/legible on paper even in dark mode
PRINT_ANCHOR = 'html[data-theme="dark"] .original-sheet::after{display:none}'
html = sub_once(
    html,
    PRINT_ANCHOR,
    PRINT_ANCHOR
    + 'html[data-theme="dark"]{--hl-yellow:#fdf0a6;--hl-green:#c9edc5;--hl-blue:#c3e3f8;--hl-red:#fac9c4}'
    + "mark.hl{color:#000}"
    + ".hl-pop,.hl-status{display:none}",
    "print highlight rules",
)

# ==========================================================================
# 2. toolbar controls
# ==========================================================================
SWATCHES = "".join(
    '<button type="button" class="hl-swatch" data-hl-color="%s" aria-label="Highlight selected text %s" '
    'title="Highlight selected text in %s" aria-pressed="false"></button>' % (c, c, c)
    for c in ("yellow", "green", "blue", "red")
)
ERASER_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path d="M9 20 3.6 14.6a2 2 0 0 1 0-2.8l7.2-7.2a2 2 0 0 1 2.8 0l5.6 5.6a2 2 0 0 1 0 2.8L13 20z"/>'
    '<path d="M20 20H9"/><path d="M8.5 9.5l6 6"/></svg>'
)
TRASH_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path d="M4 7h16"/><path d="M10 7V5.2A1.2 1.2 0 0 1 11.2 4h1.6A1.2 1.2 0 0 1 14 5.2V7"/>'
    '<path d="M6.2 7l.8 12.1A1.9 1.9 0 0 0 8.9 21h6.2a1.9 1.9 0 0 0 1.9-1.9L17.8 7"/>'
    '<path d="M10.2 11v6"/><path d="M13.8 11v6"/></svg>'
)
TOOLS = (
    '<span class="hl-tools" role="group" aria-label="Highlighter: select text, then pick a colour">'
    + SWATCHES
    + '<button type="button" class="hl-erase" data-hl-erase="1" aria-label="Remove highlight from selected text" '
    'title="Remove the highlight from the selected text">' + ERASER_SVG + "</button>"
    '<button type="button" class="hl-clear-all" id="hl-clear-all" hidden '
    'aria-label="Remove all highlights" title="Remove every highlight in this document">' + TRASH_SVG + "</button>"
    "</span>"
)
html = sub_once(
    html,
    '<button type="button" id="theme-toggle"',
    TOOLS + '<button type="button" id="theme-toggle"',
    "toolbar controls",
)

# status toast lives inside the toolbar (absolutely positioned, so it cannot
# change the toolbar height)
html = sub_once(
    html,
    "<span class=\"theme-toggle-text\">Dark mode</span></button>",
    "<span class=\"theme-toggle-text\">Dark mode</span></button>\n"
    '<span class="hl-status" id="hl-status" role="status" aria-live="polite" hidden></span>',
    "status toast",
)

# ==========================================================================
# 3. behaviour
# ==========================================================================
JS = """
<script>
/* ---------- text highlighter ---------- */
(function(){
 const KEY = 'watson-repentance-highlights';
 const COLORS = ['yellow','green','blue','red'];
 let store = load();
 let lastColor = 'yellow';

 /* ----- popup (appears next to a text selection) ----- */
 const pop = document.createElement('div');
 pop.className = 'hl-pop';
 pop.setAttribute('role','toolbar');
 pop.setAttribute('aria-label','Highlight the selected text');
 pop.hidden = true;
 pop.innerHTML = COLORS.map(function(c){
  return '<button type="button" class="hl-swatch hl-swatch-lg" data-hl-color="' + c + '" title="Highlight ' + c +
   '" aria-label="Highlight selected text ' + c + '" aria-pressed="false"></button>';
 }).join('') +
 '<button type="button" class="hl-erase" data-hl-erase="1" aria-label="Remove highlight from selected text" title="Remove the highlight">' +
 '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 20 3.6 14.6a2 2 0 0 1 0-2.8l7.2-7.2a2 2 0 0 1 2.8 0l5.6 5.6a2 2 0 0 1 0 2.8L13 20z"/><path d="M20 20H9"/><path d="M8.5 9.5l6 6"/></svg></button>';
 document.body.appendChild(pop);

 const status = document.getElementById('hl-status');
 const clearBtn = document.getElementById('hl-clear-all');
 let statusTimer = null;

 /* ----- storage ----- */
 function load(){
  try{
   const raw = localStorage.getItem(KEY);
   if(!raw) return [];
   const data = JSON.parse(raw);
   if(!Array.isArray(data)) return [];
   return data.filter(function(r){
    return r && typeof r.page === 'number' && typeof r.start === 'number' && typeof r.end === 'number'
      && r.end > r.start && COLORS.indexOf(r.color) >= 0;
   }).map(function(r){ return {page:r.page,start:r.start,end:r.end,color:r.color}; });
  }catch(e){ return []; }
 }
 function save(){
  try{ localStorage.setItem(KEY, JSON.stringify(store)); }catch(e){}
  syncControls();
 }
 function setStatus(text){
  if(!status) return;
  if(!text){ status.hidden = true; return; }
  status.textContent = text;
  status.hidden = false;
  if(statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(function(){ status.hidden = true; }, 1800);
 }
 function syncControls(){
  Array.prototype.forEach.call(document.querySelectorAll('.hl-swatch'), function(b){
   b.setAttribute('aria-pressed', b.getAttribute('data-hl-color') === lastColor ? 'true' : 'false');
  });
  if(clearBtn){
   clearBtn.hidden = (store.length === 0);
   if(store.length){
    const msg = 'Remove all ' + store.length + ' highlight' + (store.length === 1 ? '' : 's');
    clearBtn.title = msg; clearBtn.setAttribute('aria-label', msg);
   }
  }
 }

 /* ----- text offsets inside a .reading-content element ----- */
 function textNodes(root){
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
   acceptNode: function(n){ return n.nodeValue ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT; }
  });
  let n;
  while((n = walker.nextNode())) out.push(n);
  return out;
 }
 function boundaryOffset(content, container, offset){
  const nodes = textNodes(content);
  let acc = 0;
  const probe = document.createRange();
  if(container.nodeType === 3){
   probe.setStart(container, Math.min(offset, container.nodeValue.length));
  }else{
   probe.setStart(container, Math.min(offset, container.childNodes.length));
  }
  probe.collapse(true);
  for(let i = 0; i < nodes.length; i++){
   const n = nodes[i];
   if(n === container) return acc + Math.min(offset, n.nodeValue.length);
   const r = document.createRange();
   r.selectNodeContents(n);
   if(probe.compareBoundaryPoints(Range.START_TO_START, r) <= 0) return acc;
   acc += n.nodeValue.length;
  }
  return acc;
 }
 function pageOf(content){
  const sec = content.closest ? content.closest('.source-page') : null;
  return sec ? parseInt(sec.getAttribute('data-page'), 10) : null;
 }
 function pageContent(page){ return document.querySelector('#page-' + page + ' .reading-content'); }

 /* ----- current selection -> [{page,start,end}] (may span pages) ----- */
 function selectionRanges(){
  const sel = window.getSelection();
  if(!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
  const range = sel.getRangeAt(0);
  if(!range) return null;
  const out = [];
  const blocks = document.querySelectorAll('.reading-content');
  Array.prototype.forEach.call(blocks, function(content){
   if(range.intersectsNode && !range.intersectsNode(content)) return;
   const cr = document.createRange();
   cr.selectNodeContents(content);
   const r = range.cloneRange();
   if(r.compareBoundaryPoints(Range.START_TO_START, cr) < 0) r.setStart(cr.startContainer, cr.startOffset);
   if(r.compareBoundaryPoints(Range.END_TO_END, cr) > 0) r.setEnd(cr.endContainer, cr.endOffset);
   if(r.collapsed) return;
   const start = boundaryOffset(content, r.startContainer, r.startOffset);
   const end = boundaryOffset(content, r.endContainer, r.endOffset);
   if(end <= start) return;
   const page = pageOf(content);
   if(page === null) return;
   out.push({page:page, start:start, end:end});
  });
  return out.length ? out : null;
 }

 /* ----- render marks for a page ----- */
 function clearMarks(content){
  const marks = content.querySelectorAll('mark.hl');
  for(let i = 0; i < marks.length; i++){
   const m = marks[i], parent = m.parentNode;
   if(!parent) continue;
   while(m.firstChild) parent.insertBefore(m.firstChild, m);
   parent.removeChild(m);
  }
  content.normalize();
 }
 function wrapRange(content, start, end, color){
  const nodes = textNodes(content);
  let acc = 0;
  const parts = [];
  for(let i = 0; i < nodes.length; i++){
   const n = nodes[i];
   const ns = acc, ne = acc + n.nodeValue.length;
   if(ne > start && ns < end){
    parts.push({node:n, from:Math.max(0, start - ns), to:Math.min(n.nodeValue.length, end - ns)});
   }
   acc = ne;
   if(acc >= end) break;
  }
  parts.forEach(function(p){
   let target = p.node;
   if(p.from > 0) target = target.splitText(p.from);
   const len = p.to - p.from;
   if(len <= 0 || !target.nodeValue) return;
   if(len < target.nodeValue.length) target.splitText(len);
   const mark = document.createElement('mark');
   mark.className = 'hl hl-' + color;
   mark.setAttribute('data-hl-color', color);
   mark.title = 'Click to remove this highlight';
   target.parentNode.insertBefore(mark, target);
   mark.appendChild(target);
  });
 }
 function renderPage(page){
  const content = pageContent(page);
  if(!content) return;
  clearMarks(content);
  store.filter(function(r){ return r.page === page; })
       .sort(function(a,b){ return a.start - b.start; })
       .forEach(function(r){ wrapRange(content, r.start, r.end, r.color); });
 }
 function renderAll(){
  const pages = {};
  store.forEach(function(r){ pages[r.page] = 1; });
  Object.keys(pages).forEach(function(p){ renderPage(parseInt(p, 10)); });
 }

 /* ----- range arithmetic ----- */
 function normalize(){
  const byPage = {};
  store.forEach(function(r){ (byPage[r.page] = byPage[r.page] || []).push(r); });
  const out = [];
  Object.keys(byPage).forEach(function(p){
   const list = byPage[p].sort(function(a,b){ return a.start - b.start || a.end - b.end; });
   const merged = [];
   list.forEach(function(r){
    const last = merged[merged.length - 1];
    if(last && last.color === r.color && r.start <= last.end){
     last.end = Math.max(last.end, r.end);
    }else{
     merged.push({page:r.page, start:r.start, end:r.end, color:r.color});
    }
   });
   out.push.apply(out, merged);
  });
  store = out.sort(function(a,b){ return a.page - b.page || a.start - b.start; });
 }
 function subtract(ranges){
  const touched = {};
  ranges.forEach(function(r){
   const keep = [];
   store.forEach(function(s){
    if(s.page !== r.page || s.end <= r.start || s.start >= r.end){ keep.push(s); return; }
    if(s.start < r.start) keep.push({page:s.page, start:s.start, end:r.start, color:s.color});
    if(s.end > r.end) keep.push({page:s.page, start:r.end, end:s.end, color:s.color});
   });
   store = keep;
   touched[r.page] = 1;
  });
  return Object.keys(touched).map(function(p){ return parseInt(p, 10); });
 }
 function applyColor(color, ranges){
  const pages = subtract(ranges);
  ranges.forEach(function(r){ store.push({page:r.page, start:r.start, end:r.end, color:color}); });
  normalize();
  save();
  pages.forEach(renderPage);
 }

 /* ----- selection popup ----- */
 function selectionRect(){
  const sel = window.getSelection();
  if(!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  const rects = range.getClientRects();
  if(rects && rects.length) return rects[rects.length - 1];
  const r = range.getBoundingClientRect();
  return (r && (r.width || r.height)) ? r : null;
 }
 function usableSelection(){
  if(document.body.getAttribute('data-mode') === 'original') return null;
  const sel = window.getSelection();
  if(!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
  if(String(sel.toString()).trim() === '') return null;
  const node = sel.anchorNode;
  const el = node ? (node.nodeType === 1 ? node : node.parentNode) : null;
  if(!el || !el.closest || !el.closest('.reading-content')) return null;
  return selectionRanges();
 }
 function showPop(){
  const ranges = usableSelection();
  if(!ranges){ hidePop(); return; }
  const rect = selectionRect();
  if(!rect){ hidePop(); return; }
  pop.hidden = false;
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let left = rect.left + rect.width / 2 - pw / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
  let top = rect.top - ph - 10;
  if(top < 8) top = rect.bottom + 10;
  top = Math.max(8, Math.min(top, window.innerHeight - ph - 8));
  pop.style.left = Math.round(left) + 'px';
  pop.style.top = Math.round(top) + 'px';
  syncControls();
 }
 function hidePop(){ pop.hidden = true; }
 function currentSelectionText(){
  const sel = window.getSelection();
  return sel ? String(sel.toString()) : '';
 }

 /* ----- events ----- */
 document.addEventListener('mousedown', function(e){
  const el = e.target;
  if(el && el.closest && el.closest('.hl-pop,.hl-tools')) e.preventDefault();
 }, true);

 document.addEventListener('click', function(e){
  const el = e.target;
  if(!el || !el.closest) return;
  const swatch = el.closest('[data-hl-color]');
  const erase = el.closest('[data-hl-erase]');
  if(!swatch && !erase) return;
  e.preventDefault();
  const ranges = usableSelection();
  if(!ranges){
   setStatus(document.body.getAttribute('data-mode') === 'original'
     ? 'Switch to Reading view to highlight'
     : 'Select some text first');
   if(swatch) lastColor = swatch.getAttribute('data-hl-color');
   syncControls();
   return;
  }
  if(swatch){
   lastColor = swatch.getAttribute('data-hl-color');
   applyColor(lastColor, ranges);
   setStatus('Highlighted in ' + lastColor);
  }else{
   subtract(ranges);
   normalize(); save();
   ranges.forEach(function(r){ renderPage(r.page); });
   setStatus('Highlight removed');
  }
  const sel = window.getSelection();
  if(sel && sel.removeAllRanges) sel.removeAllRanges();
  hidePop();
 });

 /* click an existing highlight -> remove it (whole stored range) */
 document.addEventListener('click', function(e){
  const el = e.target;
  if(!el || !el.closest) return;
  const mark = el.closest('mark.hl');
  if(!mark) return;
  if(el.closest('a')) return;
  const sel = window.getSelection();
  if(sel && !sel.isCollapsed) return;
  const content = mark.closest('.reading-content');
  if(!content) return;
  const page = pageOf(content);
  if(page === null) return;
  const first = mark.firstChild, last = mark.lastChild;
  if(!first || !last) return;
  const start = boundaryOffset(content, first, 0);
  const end = boundaryOffset(content, last, last.nodeValue ? last.nodeValue.length : 0);
  const hits = store.filter(function(r){ return r.page === page && r.start <= start && r.end >= end; });
  if(hits.length){
   store = store.filter(function(r){ return hits.indexOf(r) === -1; });
  }else{
   subtract([{page:page, start:start, end:end}]);
  }
  normalize(); save(); renderPage(page);
  setStatus('Highlight removed');
  e.preventDefault();
 });

 let selTimer = null;
 function onSelectionChange(){
  if(selTimer) clearTimeout(selTimer);
  selTimer = setTimeout(function(){
   const ranges = usableSelection();
   if(ranges) showPop(); else hidePop();
  }, 120);
 }
 document.addEventListener('selectionchange', onSelectionChange);
 document.addEventListener('mouseup', onSelectionChange);
 document.addEventListener('keyup', function(e){ if(e.key === 'Escape'){ hidePop(); return; } onSelectionChange(); });
 document.addEventListener('mousedown', function(e){
  const el = e.target;
  if(el && el.closest && el.closest('.hl-pop')) return;
  hidePop();
 });
 window.addEventListener('scroll', hidePop, {passive:true, capture:true});
 window.addEventListener('resize', hidePop);

 let armed = false, armTimer = null;
 function disarm(){
  armed = false;
  if(armTimer){ clearTimeout(armTimer); armTimer = null; }
  if(clearBtn){
   clearBtn.classList.remove('hl-armed');
   const n = store.length;
   clearBtn.title = n ? 'Remove all ' + n + ' highlight' + (n === 1 ? '' : 's') : '';
  }
 }
 if(clearBtn){
  clearBtn.addEventListener('click', function(e){
   e.preventDefault();
   if(!store.length){ setStatus('No highlights yet'); return; }
   const n = store.length;
   if(!armed){
    armed = true;
    clearBtn.classList.add('hl-armed');
    clearBtn.title = 'Click again to remove all ' + n + ' highlight' + (n === 1 ? '' : 's');
    setStatus('Click the bin again to remove all ' + n + ' highlight' + (n === 1 ? '' : 's'));
    if(armTimer) clearTimeout(armTimer);
    armTimer = setTimeout(disarm, 3500);
    return;
   }
   disarm();
   const pages = {};
   store.forEach(function(r){ pages[r.page] = 1; });
   store = [];
   save();
   Object.keys(pages).forEach(function(p){ renderPage(parseInt(p, 10)); });
   setStatus('All highlights removed');
  });
  /* safety: forget the armed state when the pointer leaves the button */
  clearBtn.addEventListener('mouseleave', function(){ if(armed) disarm(); });
 }

 /* ----- keep page-jump scroll offset in sync with the real toolbar height ----- */
 function syncToolbarOffset(){
  const tb = document.querySelector('.toolbar');
  if(!tb) return;
  const h = Math.round(tb.getBoundingClientRect().height) + 6;
  if(h > 0) document.documentElement.style.setProperty('--toolbar-offset', h + 'px');
 }
 window.addEventListener('resize', syncToolbarOffset);
 if(document.readyState === 'complete') syncToolbarOffset();
 else window.addEventListener('load', syncToolbarOffset);
 setTimeout(syncToolbarOffset, 300);

 renderAll();
 syncControls();
})();
</script>
"""

MARK = "if(mq.addEventListener){ mq.addEventListener('change', follow); }"
idx = html.find(MARK)
if idx == -1:
    sys.exit("FAIL [behaviour]: theme script marker not found")
close_idx = html.find("</script>", idx)
if close_idx == -1:
    sys.exit("FAIL [behaviour]: closing script tag not found")
insert_at = close_idx + len("</script>")
html = html[:insert_at] + JS + html[insert_at:]
print("ok  [behaviour]")

io.open(PATH, "w", encoding="utf-8").write(html)
print("\nwrote %s (%.1f MB)" % (PATH, len(html.encode("utf-8")) / 1e6))
