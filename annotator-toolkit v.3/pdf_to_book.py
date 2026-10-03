#!/usr/bin/env python3
"""Convert a PDF book into the same paged-HTML shape as the Watson edition,
so the four annotation patchers can build on it.

    python3 pdf_to_book.py --pdf FILE --out FILE --title T --author A \
        [--facsimile none|webp] [--dpi 90] [--quality 50]

The shell (CSS, fonts, toolbar, tail script) is taken from the Watson master so
the result is structurally identical; only the content sections, the title, the
chapter jump list, the table of contents and the page count change.

Reading view:  <section id="page-N" class="source-page" data-page="N">
                 <div class="reading-content"><p><span class="text-line">…</span>…</p></div>
Original view: <div class="original-content"><div class="original-sheet"><img src="data:image/webp;base64,…"></div></div>
Both are exactly what the patchers and the book's own CSS expect.
"""

import argparse
import base64
import html
import io
import re
import statistics
import os
from collections import Counter

import pymupdf

SHELL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shell.html")


def clean_text(t):
    t = t.replace("\u00ad", "")          # soft hyphen: never a real break
    t = t.replace("\ufb01", "fi").replace("\ufb02", "fl")
    return t


def line_runs(line):
    """One PDF line -> (plain text, size, [(text, is_superscript, is_italic)]).

    Superscript and italic come from the PDF's own span flags:
    bit 0 = superscript, bit 1 = italic."""
    runs, plain, size = [], [], 0.0
    for s in line["spans"]:
        t = clean_text(s["text"])
        if not t:
            continue
        flags = int(s.get("flags", 0))
        fname = s["font"].lower()
        sup = bool(flags & 1)
        ital = bool(flags & 2) or "italic" in fname or "oblique" in fname
        runs.append((t, sup, ital))
        plain.append(t)
        size = max(size, s["size"])
    if runs:
        # trim the trailing whitespace of the last run only
        t, sup, ital = runs[-1]
        runs[-1] = (t.rstrip(), sup, ital)
    return "".join(plain).rstrip(), size, runs


def page_lines(page, body_size):
    """Return a list of ('p'|'h2'|'h3', [line strings]) for one PDF page."""
    dct = page.get_text("dict")
    out = []
    for block in dct["blocks"]:
        if block.get("type") != 0:
            continue
        block_items = []
        for line in block.get("lines", []):
            txt, size, runs = line_runs(line)
            if not txt.strip():
                continue
            block_items.append((txt, size, runs))
        if not block_items:
            continue
        # one block = one paragraph, unless the size changes inside it
        para = []
        kind = None
        for txt, size, runs in block_items:
            if size > body_size * 1.45:
                k = "h2"
            elif size > body_size * 1.12:
                k = "h3"
            else:
                k = "p"
            if kind is None:
                kind = k
            if k != kind and para:
                out.append((kind, para))
                para = []
                kind = k
            para.append((txt, runs))
        if para:
            out.append((kind, para))
    return out


def join_paragraph(lines):
    """PDF line breaks are layout, not meaning: join them back into a paragraph.

    Returns (plain text, html).  A line ending in "-" joins without a space;
    superscripts become <sup> and italics <em>."""
    plain = ""
    out = []
    for txt, runs in lines:
        if not txt.strip():
            continue
        glued = bool(plain) and plain.rstrip().endswith("-")
        if plain and not glued:
            out.append((" ", False, False))
            plain += " "
        for t, sup, ital in runs:
            if not t:
                continue
            out.append((t, sup, ital))
            plain += t
    # squeeze runs of spaces in the plain text for checks, and in the html output
    pieces = []
    for t, sup, ital in out:
        h = html.escape(t)
        if sup:
            h = "<sup>" + h + "</sup>"
        if ital:
            h = "<em>" + h + "</em>"
        pieces.append(h)
    html_out = re.sub(r"\s+", " ", "".join(pieces)).strip()
    return re.sub(r"\s+", " ", plain).strip(), html_out


def looks_like_furniture(text, page_no, total):
    t = text.strip()
    if re.fullmatch(r"\d{1,4}", t):
        return True
    if re.fullmatch(r"(?i)(page\s*)?\d{1,4}\s*(of\s*\d{1,4})?", t):
        return True
    return False


def build_reading_content(page, body_size, page_no, total):
    kinds = page_lines(page, body_size)
    out = []
    n = 0
    for kind, raw_lines in kinds:
        lines = [item for item in raw_lines if item[0].strip()]
        if not lines:
            continue
        if len(lines) == 1 and looks_like_furniture(lines[0][0], page_no, total):
            continue
        plain, _ = join_paragraph(lines)
        if not plain:
            continue
        spans = []
        for txt, runs in lines:
            n += 1
            inner = ""
            for t, sup, ital in runs:
                h = html.escape(t)
                if sup:
                    h = "<sup>" + h + "</sup>"
                if ital:
                    h = "<em>" + h + "</em>"
                inner += h
            spans.append('<span id="line-%d-%d" class="text-line">%s</span>'
                         % (page_no, n, inner.strip()))
        tag = "p" if kind == "p" else kind
        out.append("<%s>%s</%s>" % (tag, " ".join(spans), tag))
    return "\n".join(out)


def render_page_image(doc, pno, dpi, quality):
    import io as _io
    from PIL import Image
    pix = doc[pno].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    buf = _io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=6)
    return base64.b64encode(buf.getvalue()).decode("ascii"), pix.width, pix.height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--facsimile", choices=["none", "webp"], default="none")
    ap.add_argument("--dpi", type=int, default=90)
    ap.add_argument("--quality", type=int, default=50)
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    total = doc.page_count
    shell = io.open(SHELL, encoding="utf-8").read()

    # ---- work out the body font size from a sample
    sizes = Counter()
    for i in range(0, min(total, 40)):
        for b in doc[i].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if len(s["text"].strip()) > 20:
                        sizes[round(s["size"], 1)] += len(s["text"].strip())
    body_size = sizes.most_common(1)[0][0]

    # ---- table of contents from the PDF
    toc = []
    for level, title, pno in doc.get_toc():
        t = re.sub(r"\s+", " ", clean_text(title)).strip()
        if t:
            toc.append((t, max(1, min(total, pno))))

    # ---- the shell: swap the book-specific parts
    pre = shell[:shell.index('<main class="book">')]
    post = shell[shell.index("</main>"):]

    text = lambda t: html.escape(t, quote=False)      # title/h1/byline: keep apostrophes literal
    attr = lambda t: html.escape(t, quote=True)        # attributes: escape quotes too
    pre = pre.replace('<meta name="author" content="Thomas Watson">',
                      '<meta name="author" content="%s">' % attr(args.author), 1)
    blurb = (" With a reading view and an original-page view." if args.facsimile != "none"
             else " With a reading view.")
    desc = ("%s by %s. Complete HTML conversion of the supplied %d-page PDF.%s"
            % (attr(args.title), attr(args.author), total, blurb))
    pre = re.sub(r'<meta name="description" content="[^"]*">',
                 lambda m: '<meta name="description" content="%s">' % desc, pre, count=1)
    pre = re.sub(r"<title>[^<]*</title>", "<title>%s &#8212; %s</title>" % (text(args.title), text(args.author)), pre, count=1)
    pre = pre.replace('<p class="eyebrow">HTML edition</p>',
                      '<p class="eyebrow">HTML edition</p>', 1)
    pre = re.sub(r'<h1>[^<]*</h1>', '<h1>%s</h1>' % text(args.title), pre, count=1)
    pre = re.sub(r'<p class="byline">[^<]*</p>',
                 '<p class="byline">%s &#183; %d original PDF pages</p>' % (text(args.author), total),
                 pre, count=1)
    pre = re.sub(r'(<input id="page-number"[^>]*max=")\d+(")', r"\g<1>%d\g<2>" % total, pre, count=1)

    # chapter jump + table of contents
    jump = ['<option value="">Jump to a chapter&#8230;</option>']
    nav = []
    for t, pno in toc:
        jump.append('<option value="%d">%s</option>' % (pno, html.escape(t)))
        nav.append('<a href="#page-%d"><span>%s</span><small>%d</small></a>' % (pno, html.escape(t), pno))
    pre = re.sub(r'(<select id="chapter-jump"[^>]*>)<option value="">.*?</option>.*?</select>',
                 lambda m: m.group(1) + "".join(jump) + "</select>", pre, count=1, flags=re.S)
    pre = re.sub(r'(<nav class="toc" aria-label="Table of contents">).*?(</nav>)',
                 lambda m: m.group(1) + "".join(nav) + m.group(2), pre, count=1, flags=re.S)
    if args.facsimile == "none":
        # no page images: drop the "Original pages" option rather than offer a blank view
        pre = pre.replace('<option value="original">Original pages</option>', "", 1)

    # ---- the sections
    parts = []
    img_bytes = 0
    for i in range(total):
        pno = i + 1
        page = doc[i]
        reading = build_reading_content(page, body_size, pno, total)
        has_text = bool(reading.strip())
        original = ""
        if args.facsimile == "webp" or not has_text:
            b64, w, h = render_page_image(doc, i, args.dpi, args.quality)
            img_bytes += len(b64)
            original = ('<div class="original-content"><div class="original-sheet">'
                        '<img src="data:image/webp;base64,%s" alt="Original PDF page %d" '
                        'width="%d" height="%d"></div></div>' % (b64, pno, w, h))
        if not has_text and original:
            # a page with no text layer is shown as a picture in the reading view too
            reading = ('<figure><img src="%s" alt="Page %d"></figure>'
                       % (re.search(r'src="([^"]+)"', original).group(1), pno))
        parts.append('<section id="page-%d" class="source-page" data-page="%d" aria-label="Page %d">\n'
                     '<div class="page-label"><span>Page %d of %d</span>'
                     '<a href="#top" aria-label="Back to top">&#8593; Top</a></div>\n'
                     '<div class="reading-content">%s</div>\n%s</section>'
                     % (pno, pno, pno, pno, total, reading, original))

    out = pre + '<main class="book">' + "\n".join(parts) + post
    io.open(args.out, "w", encoding="utf-8").write(out)

    print("wrote %s" % args.out)
    print("  pages: %d | body font: %.1fpt | toc entries: %d" % (total, body_size, len(toc)))
    print("  file: %.1f MB (page images: %.1f MB)" % (len(out) / 1e6, img_bytes / 1e6))
    print("  sections: %d | os.1" % out.count('class="source-page"'))


if __name__ == "__main__":
    main()
