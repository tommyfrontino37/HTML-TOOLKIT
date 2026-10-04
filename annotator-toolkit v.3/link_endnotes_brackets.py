#!/usr/bin/env python3
"""
link_endnotes_brackets.py — cross-link a book's printed [ N ] endnote markers.

Adapted from HTML-TOOLKIT's link_endnotes.py (annotator-toolkit v.3) for books
whose PDF prints endnotes in the form  [ 1 ]  rather than  1.  The stock script
looks for numbered note paragraphs ("1." / "1)") and finds nothing in such a
book; this one handles the bracket form, in both spellings the source uses:

    body:      ...as an earnest penny [ 1 ] for all the glory...
               ...and Bible and accidence,[2] and so to his grammar...
    endnotes:  [ 1 ] A first instalment which guarantees that the rest...

What it does
------------
  * gives every note paragraph an invisible anchor  <span id="endnote-N">
  * wraps each printed marker in a link, both ways:
        in-text  [ N ]  ->  #endnote-N
        note     [ N ]  ->  #endnote-ref-N   (first reference)
  * flashes the landed note with :target.  Nothing is drawn beside the marker:
    the printed number is itself the link, so the DOM text stays exactly what
    the PDF printed.

The one rule it will not break
------------------------------
Highlights and notes are stored as character offsets inside each page's
.reading-content.  Adding or removing one text character moves every offset on
that page and yesterday's highlights land on the wrong words.  So this script
only ever wraps characters that are already there, and inserts empty elements.
Before writing it re-extracts the text of every .reading-content section and
refuses to write unless it is byte-identical to the input.

Usage
-----
    python3 link_endnotes_brackets.py --input "Book.html" \
        --output "Book (linked endnotes).html"

    python3 link_endnotes_brackets.py --input "Book.html" --in-place   # keeps .bak
"""

import argparse
import re
import sys

MARKER = re.compile(r"\[\s*(\d+)\s*\]")
LINE_SPAN = re.compile(
    r'<span id="line-(\d+)-(\d+)" class="text-line">(.*?)</span>', re.S)
SECTION = re.compile(r'<section id="page-(\d+)"')
READING_OPEN = re.compile(r'<div class="reading-content">')
TAGS = re.compile(r"<[^>]+>")
SKIP_BLOCK = re.compile(r"<(script|style)\b.*?</\1\s*>", re.S | re.I)

CSS = """
/* ---------- cross-linked printed endnotes (link_endnotes_brackets.py) ---------- */
.endnote-anchor{display:inline-block;width:0;height:0;overflow:hidden;scroll-margin-top:110px}
a.endnote-ref,a.endnote-back{color:inherit;text-decoration:none;cursor:pointer;
  border-bottom:1px dotted rgba(140,140,140,.75);border-radius:2px}
a.endnote-ref{scroll-margin-top:110px}
a.endnote-ref:hover,a.endnote-back:hover{border-bottom-style:solid;
  background:rgba(255,208,92,.30)}
html[data-theme="dark"] a.endnote-ref:hover,
html[data-theme="dark"] a.endnote-back:hover{background:rgba(228,196,72,.26)}
/* No back-arrow glyph on the notes: the printed marker is the link, and a
   reader asked for the notes list to stay plain (2026-10-04).  The cue that a
   note is clickable is the dotted underline below. */
.endnote-anchor:target + .text-line{background:rgba(255,208,92,.42);
  border-radius:3px;box-shadow:0 0 0 3px rgba(255,208,92,.42)}
html[data-theme="dark"] .endnote-anchor:target + .text-line{
  background:rgba(228,196,72,.28);box-shadow:0 0 0 3px rgba(228,196,72,.28)}
@media print{a.endnote-ref,a.endnote-back{border-bottom:0}}
"""


# --------------------------------------------------------------------------- #
# document geometry
# --------------------------------------------------------------------------- #
def sections(doc):
    """[(page_no, start, end)] for every <section id="page-N">."""
    hits = [(int(m.group(1)), m.start()) for m in SECTION.finditer(doc)]
    out = []
    for i, (page, start) in enumerate(hits):
        end = hits[i + 1][1] if i + 1 < len(hits) else len(doc)
        out.append((page, start, end))
    return out


def reading_region(doc, sec_start, sec_end):
    """(start, end) raw span of the section's <div class="reading-content">."""
    m = READING_OPEN.search(doc, sec_start, sec_end)
    if not m:
        return None
    start = m.end()
    depth, i = 1, start
    while i < sec_end:
        nxt_open = doc.find("<div", i, sec_end)
        nxt_close = doc.find("</div>", i, sec_end)
        if nxt_close == -1:
            return None
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            i = nxt_close + 6
            if depth == 0:
                return (start, nxt_close)
    return None


def text_with_map(raw):
    """Concatenated text nodes plus, per character, its offset in `raw`."""
    chars, offsets = [], []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "<":
            m = SKIP_BLOCK.match(raw, i)
            if m:
                i = m.end()
                continue
            j = raw.find(">", i)
            if j == -1:
                break
            i = j + 1
            continue
        chars.append(c)
        offsets.append(i)
        i += 1
    return "".join(chars), offsets


def strip_tags(fragment):
    return TAGS.sub("", fragment)


# --------------------------------------------------------------------------- #
# the work
# --------------------------------------------------------------------------- #
def find_endnote_block(doc):
    """(heading_page, {note_number: (span_start, inner_start, inner_text)})."""
    heading_page = None
    for page, s, e in sections(doc):
        reg = reading_region(doc, s, e)
        if not reg:
            continue
        text, _ = text_with_map(doc[reg[0]:reg[1]])
        head = text.strip()[:80]
        if re.match(r"^Endnotes\b", head):
            heading_page = page
            break
    if heading_page is None:
        sys.exit("no page whose text starts with 'Endnotes' — nothing to link")

    notes, expected = {}, 1
    for page, s, e in sections(doc):
        if page < heading_page:
            continue
        reg = reading_region(doc, s, e)
        if not reg:
            break
        rstart = reg[0]
        found_here = 0
        for m in LINE_SPAN.finditer(doc, rstart, reg[1]):
            inner = m.group(3)
            inner_start = m.end(3) - len(inner)
            mk = re.match(r"\s*\[\s*(\d+)\s*\]", strip_tags(inner))
            if not mk:
                continue
            num = int(mk.group(1))
            if num != expected:
                continue
            notes[num] = (m.start(), inner_start, inner)
            expected += 1
            found_here += 1
        if not found_here and notes:
            break                      # the endnote run has ended
    return heading_page, notes


def link(doc, heading_page, notes):
    """Return (new_doc, report). Every edit is an insert or a pure wrap."""
    secs = sections(doc)
    endnote_pages = {p for p, s, e in secs
                     if p >= heading_page and _has_note_start(doc, s, e, notes)}
    edits = []                                  # (start, end, replacement)
    ref_count = {}

    # ---- 1. in-text references -> #endnote-N --------------------------------
    for page, s, e in secs:
        if page in endnote_pages:
            continue
        reg = reading_region(doc, s, e)
        if not reg:
            continue
        raw = doc[reg[0]:reg[1]]
        text, omap = text_with_map(raw)
        for m in MARKER.finditer(text):
            num = int(m.group(1))
            if num not in notes:
                continue
            a = omap[m.start()]
            b = omap[m.end() - 1] + 1
            ref_count[num] = ref_count.get(num, 0) + 1
            anchor_id = "endnote-ref-%d" % num
            if ref_count[num] > 1:
                anchor_id += "-%d" % ref_count[num]
            html = ('<a class="endnote-ref" id="%s" href="#endnote-%d" '
                    'title="Endnote %d">%s</a>'
                    % (anchor_id, num, num, doc[reg[0] + a:reg[0] + b]))
            edits.append((reg[0] + a, reg[0] + b, html))

    # ---- 2. the notes themselves: anchor + back-link ------------------------
    for num, (span_start, inner_start, inner) in notes.items():
        back = "endnote-ref-%d" % num
        marker = re.match(r"\s*\[\s*%d\s*\]" % num, strip_tags(inner))
        lead = inner[:marker.end()]
        lead_raw = re.sub(r"<[^>]+>", "", lead)          # inner markup is plain
        assert lead_raw.strip() == lead.strip(), "unexpected markup in marker"
        edits.append((span_start, span_start,
                      '<span id="endnote-%d" class="endnote-anchor"></span>' % num))
        edits.append((inner_start, inner_start + len(lead),
                      '<a class="endnote-back" href="#%s" title="Back to the '
                      'text (endnote %d)">%s</a>' % (back, num, lead)))

    # ---- 3. apply, last edit first ----------------------------------------
    edits.sort(key=lambda t: (t[0], t[1]), reverse=True)
    for a, b, repl in edits:
        doc = doc[:a] + repl + doc[b:]
    doc = doc.replace("</head>", "<style>%s</style>\n</head>" % CSS, 1)
    return doc, len(ref_count), sum(ref_count.values())


def _has_note_start(doc, s, e, notes):
    reg = reading_region(doc, s, e)
    if not reg:
        return False
    for m in LINE_SPAN.finditer(doc, reg[0], reg[1]):
        inner = strip_tags(m.group(3))
        mk = re.match(r"\s*\[\s*(\d+)\s*\]", inner)
        if mk and int(mk.group(1)) in notes:
            return True
    return False


def section_texts(doc):
    """Byte-identical text of every reading-content, for the safety check."""
    return {p: text_with_map(doc[r0:r1])[0]
            for p, s, e in sections(doc)
            for r0, r1 in [reading_region(doc, s, e) or (0, 0)]}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite --input (keeps a .bak copy)")
    args = ap.parse_args()
    if not args.in_place and not args.output:
        sys.exit("give --output or --in-place")

    doc = open(args.input, encoding="utf-8").read()
    before = section_texts(doc)

    # Linking is not idempotent the way a re-run would like: the markers are
    # still text, so a second pass would wrap them again and nest <a> elements.
    # The stock toolkit's rule for its patchers, applied here.
    if 'class="endnote-ref"' in doc or 'class="endnote-anchor"' in doc:
        sys.exit("this book is already endnote-linked (found endnote-ref/anchor "
                 "markup) — refusing to link it twice. Start from the unlinked "
                 "file, and delete any stale .bak before rebuilding.")

    heading_page, notes = find_endnote_block(doc)
    nums = sorted(notes)
    print("endnotes block: starts on page %d" % heading_page)
    print("notes found: %d (numbered %d-%d, sequential)"
          % (len(nums), nums[0], nums[-1]) if nums else "notes found: 0")
    if not nums:
        sys.exit("no numbered note paragraphs in the endnotes block")

    new, linked_notes, linked_refs = link(doc, heading_page, notes)
    print("linked %d in-text markers, %d notes, %d back-links"
          % (linked_refs, linked_notes, linked_notes))

    after = section_texts(new)
    if before != after:
        diff = [p for p in before if before[p] != after.get(p)]
        sys.exit("REFUSING TO WRITE: text changed on page(s) %s" % diff[:10])
    print("verified: all %d sections' text is byte-identical to the input"
          % len(before))

    if args.in_place:
        import shutil
        shutil.copyfile(args.input, args.input + ".bak")
        open(args.input, "w", encoding="utf-8").write(new)
        print("wrote %s (backup at %s.bak)" % (args.input, args.input))
    else:
        open(args.output, "w", encoding="utf-8").write(new)
        print("wrote %s" % args.output)


if __name__ == "__main__":
    main()
