#!/usr/bin/env python3
"""
link_endnotes.py — make the endnote superscripts in a toolkit-built book clickable.

A post-processor for the HTML that "HTML-TOOLKIT" (build_enhanced.py / pdf_to_book.py)
produces. It turns every in-text marker <sup>N</sup> into a link to endnote N, makes
the endnote's own number link back to the text, and flashes the destination.

Why a post-processor and not another toolkit patcher
----------------------------------------------------
The toolkit's patchers are NOT idempotent and must never be re-run over a built
book (that is the documented duplicate-anchor failure). So this script treats the
built HTML as an input and writes a *new* file, leaving the original untouched.

The one hard rule
-----------------
Highlights are stored as character offsets inside each page's .reading-content
(add_highlights.py). If this script added or removed a single character of text,
every existing highlight on that page would shift onto the wrong words.

So it never does. Links only *wrap* digits that are already there, and the
back-arrow is drawn with CSS ::before (pseudo-element content is not DOM text).
The script verifies the invariant at the end: the tag-stripped text of all 274
sections must be byte-identical between input and output, or it refuses to write.

It also repairs two extraction artefacts it finds on the way:
  * a merged marker <sup>324325</sup>  ->  <sup>324</sup><sup>325</sup>
  * a "naked" marker that an older converter dropped the <sup> from when the
    superscript sat at the start of a line ("78 Joseph was famous ...").
    pdf_to_book.py now wraps those itself, so on a freshly built book the
    repair is a no-op; it stays for books built before that fix.

Usage
-----
    python3 link_endnotes.py \
        --input  "Book (annotated).html" \
        --output "Book (annotated, linked endnotes).html"

    # in place (a .bak copy is kept):
    python3 link_endnotes.py --input "Book.html" --in-place
"""

import argparse
import re
import sys

# ---------------------------------------------------------------- CSS -------

CSS = """
/* --- endnote links (added by link_endnotes.py) --- */
sup.en-ref { line-height: 0; }
sup.en-ref a { color: inherit; text-decoration: none; border-bottom: 1px dotted currentColor;
               scroll-margin-top: calc(var(--toolbar-offset) + 24px); }
sup.en-ref a:hover { text-decoration: underline; }
sup.en-ref a:target { background: rgba(255, 214, 10, .45); border-bottom-color: transparent; }

p.en-note { scroll-margin-top: calc(var(--toolbar-offset) + 8px); border-radius: 4px; }
p.en-note:target { background: rgba(255, 214, 10, .22); box-shadow: -6px 0 0 rgba(255, 214, 10, .7); }
html[data-theme="dark"] p.en-note:target { background: rgba(255, 214, 10, .14); box-shadow: -6px 0 0 rgba(255, 214, 10, .45); }

a.en-num { color: inherit; text-decoration: none; font-weight: 600; }
a.en-num:hover { text-decoration: underline; }

a.en-back { display: inline-block; margin-left: .4em; text-decoration: none; opacity: .5; }
a.en-back::before { content: "\\21A9"; font-size: .9em; }   /* ↩ drawn in CSS, not text */
a.en-back:hover { opacity: 1; text-decoration: none; }
html[data-theme="dark"] a.en-back { opacity: .65; }
"""

RE_SECTION = re.compile(r'<section\b[^>]*id="page-(\d+)"[^>]*>.*?</section>', re.S)
# a note paragraph: <p><span id="line-A-B" class="text-line">12 The note text...
# the number may already be wrapped in <sup> by a fixed converter, or bare.
RE_NOTE_PARA = re.compile(
    r'(<p>)(<span id="line-(\d+)-(\d+)" class="text-line">)'
    r'(?:<sup[^>]*>)?(\d{1,3})(?:</sup>)?(?=\s)')
# markers already wrapped by the converter
RE_SUP = re.compile(r'<sup>(\d{1,3})</sup>')
# a merged marker, e.g. <sup>324325</sup>
RE_SUP_MERGED = re.compile(r'<sup>(\d{4,6})</sup>')


def split_marker_run(run, known):
    """Split '324325' into [324, 325] if every piece is a note number."""
    def rec(s):
        if not s:
            return []
        for ln in (3, 2, 1):
            head = s[:ln]
            if len(head) == ln and int(head) in known and head == str(int(head)):
                rest = rec(s[ln:])
                if rest is not None:
                    return [int(head)] + rest
        return None
    if run != str(int(run)):          # leading zeros: not a marker run
        return None
    out = rec(run)
    return out if out and len(out) > 1 else None


def main():
    ap = argparse.ArgumentParser(description="Link superscript markers to endnotes in a built book HTML.")
    ap.add_argument("--input", required=True, help="built book HTML (the toolkit's output)")
    ap.add_argument("--output", help="where to write the linked book")
    ap.add_argument("--in-place", action="store_true", help="overwrite --input (keeps a .bak copy)")
    ap.add_argument("--heading", default="Endnotes", help="heading that starts the endnotes (default: Endnotes)")
    args = ap.parse_args()

    if not args.in_place and not args.output:
        ap.error("give --output PATH, or --in-place")

    src = open(args.input, encoding="utf-8").read()
    original = src[:]

    # --- 1. locate every page section, and the endnotes block -----------------
    secs = [(int(m.group(1)), m.start(), m.end()) for m in RE_SECTION.finditer(src)]
    if not secs:
        sys.exit("no <section id=\"page-N\"> elements found — is this a toolkit-built book?")

    note_start = note_end = None
    for page, s, e in secs:
        chunk = src[s:e]
        if re.search(r'<h[12][^>]*>\s*(?:<span[^>]*>)?\s*%s\s*(?:</span>)?\s*</h[12]>' % re.escape(args.heading),
                     chunk, re.I):
            note_start, note_end = s, e
            break
    if note_start is None:
        sys.exit('no "%s" heading found — nothing to link to (use --heading to name it)' % args.heading)

    # the endnotes run until the next page section that starts a new heading
    for page, s, e in secs:
        if s > note_start and re.search(r'<h[12][^>]*>', src[s:e]):
            note_end = s
            break
    else:
        note_end = secs[-1][2]

    notes_region = src[note_start:note_end]
    print("endnotes block: %d section(s), pages %d-%d"
          % (sum(1 for p, s, e in secs if s >= note_start and e <= note_end),
             min(p for p, s, e in secs if s >= note_start and e <= note_end),
             max(p for p, s, e in secs if s >= note_start and e <= note_end)))

    # --- 2. read the endnote numbers -----------------------------------------
    notes = []                                   # (number, para_start, para_end)
    for m in RE_NOTE_PARA.finditer(notes_region):
        p_start = note_start + m.start()
        p_end = src.index("</p>", p_start) + 4
        notes.append((int(m.group(5)), p_start, p_end))
    known = {n for n, _, _ in notes}
    if not notes:
        sys.exit("no numbered note paragraphs found in the endnotes block")
    nums = [n for n, _, _ in notes]
    print("endnotes found: %d (numbered %d-%d, %s)"
          % (len(notes), min(nums), max(nums),
             "sequential" if nums == list(range(min(nums), max(nums) + 1)) else "NOT sequential"))

    # --- 3. work out which markers exist in the body --------------------------
    body_region = src[:note_start]
    marked = set(int(v) for v in RE_SUP.findall(body_region))
    merged_runs = RE_SUP_MERGED.findall(body_region)
    merged_fixed = []
    for run in merged_runs:
        parts = split_marker_run(run, known)
        if parts:
            merged_fixed.append((run, parts))
            marked.update(parts)
    naked = sorted(known - marked)
    print("markers already in <sup> form: %d" % len(marked - set(sum((p for _, p in merged_fixed), []))))
    for run, parts in merged_fixed:
        print("  merged marker <sup>%s</sup> -> %s" % (run, " + ".join(str(p) for p in parts)))
    print("notes with no marker yet (naked): %s" % (naked or "none"))

    # --- 4. build the edit list (applied last-to-first) -----------------------
    edits = []                                    # (start, end, replacement)

    # 4a. note paragraphs: id, back-link, and the number becomes a link home
    for n, p_start, p_end in notes:
        para = src[p_start:p_end]
        m = RE_NOTE_PARA.match(para)              # para begins with <p><span ...>N
        assert m, "note paragraph %d does not match the expected shape" % n
        num_at = p_start + m.start(5)
        num_end = p_start + m.end(5)

        new_open = '<p id="note-%d" class="en-note">%s<a class="en-num" href="#ref-%d" title="Back to the text">%d</a>' % (
            n, m.group(2), n, n)
        # replace "<p><span ...>N" with the new opening + linked number
        edits.append((p_start, num_end, new_open))
        # back arrow before the paragraph's closing tag (drawn in CSS)
        edits.append((p_end - 4, p_end - 4,
                      '<a class="en-back" href="#ref-%d" aria-label="Back to the text" title="Back to the text"></a>' % n))

    # 4b. markers in the body
    seen = {}
    def marker_link(n, anchor=True):
        seen[n] = seen.get(n, 0) + 1
        rid = "ref-%d" % n if seen[n] == 1 else "ref-%d-%d" % (n, seen[n])
        if not anchor:
            return '<sup class="en-ref">%d</sup>' % n
        return '<sup class="en-ref"><a id="%s" href="#note-%d" title="Endnote %d">%d</a></sup>' % (rid, n, n, n)

    for m in RE_SUP_MERGED.finditer(src[:note_start]):
        parts = split_marker_run(m.group(1), known)
        if parts:
            edits.append((m.start(), m.end(), "".join(marker_link(p) for p in parts)))
    for m in RE_SUP.finditer(src[:note_start]):
        edits.append((m.start(), m.end(), marker_link(int(m.group(1)))))

    # 4c. naked markers: a text-line that begins with the note's number
    for n in naked:
        pat = re.compile(r'(<span id="line-\d+-\d+" class="text-line">)(%d)(?=\s)' % n)
        hits = [(m.start(1), m.end(2), m) for m in pat.finditer(src[:note_start])]
        if len(hits) != 1:
            print("  ! note %d: expected 1 naked marker, found %d — skipped" % (n, len(hits)))
            continue
        s, e, m = hits[0]
        # keep the digits, just wrap them: <span ...><sup class="en-ref"><a ...>78</a></sup>
        edits.append((m.start(2), m.end(2), marker_link(n)))

    # 4d. the stylesheet, before the FIRST </head> (the toolkit embeds a second
    #     </head> inside the panel's report template — never anchor on that)
    head_at = src.find("</head>")
    if head_at < 0:
        sys.exit("no </head> found")
    edits.append((head_at, head_at, "<style>%s</style>" % CSS))

    # --- 5. apply, then prove the text was not changed ------------------------
    for s, e, rep in sorted(edits, reverse=True, key=lambda t: t[0]):
        src = src[:s] + rep + src[e:]

    def sections_text(blob):
        out = {}
        for m in RE_SECTION.finditer(blob):
            inner = blob[m.start():m.end()]
            out[int(m.group(1))] = re.sub(r'<[^>]+>', '', inner)
        return out

    old_t, new_t = sections_text(original), sections_text(src)
    if old_t != new_t:
        changed = [p for p in old_t if old_t.get(p) != new_t.get(p)]
        sys.exit("ABORT: text of section(s) %s changed — highlights would shift. Nothing written."
                 % changed[:10])

    # --- 6. write -------------------------------------------------------------
    out_path = args.input if args.in_place else args.output
    if args.in_place:
        open(args.input + ".bak", "w", encoding="utf-8").write(original)
        print("backup: %s.bak" % args.input)
    open(out_path, "w", encoding="utf-8").write(src)

    linked = sum(1 for n in seen if n in known)
    print("linked %d markers, %d endnotes, %d back-links"
          % (sum(seen.values()), len(notes), len(notes)))
    unreferenced = sorted(known - set(seen))
    if unreferenced:
        print("endnotes with no marker in the text: %s (still reachable by the TOC/panel)"
              % unreferenced)
    print("wrote %s (%.1f MB)" % (out_path, len(src.encode()) / 1e6))
    print("verified: all %d sections' text is byte-identical to the input" % len(old_t))


if __name__ == "__main__":
    main()
