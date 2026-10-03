#!/usr/bin/env python3
"""Convert a text PDF into a self-contained, paged HTML book.

Basic use:
    python3 pdf_to_book.py --pdf book.pdf --out book.html \
        --title "My Book" --author "A. Author"

The HTML shell supplies the reader UI (dark mode, highlights, notes, the
annotations panel, and an offline dictionary). This converter replaces the
sample book's content, re-keys its browser storage for this title, strips
Cloudflare/remote scripts, and builds a dictionary from the new book rather
than carrying over the sample book's dictionary.

PDF-specific repairs:
  * large drop-cap initials are moved back to the first paragraph, after the
    page heading, when PDF block order puts them out of sequence;
  * Arabic-Indic digit runs can be reversed when extraction order disagrees
    with the left-to-right visual order (automatic for Latin-text PDFs).

The converter is for PDFs with a text layer. Scanned-only PDFs need OCR first.
"""

import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter

try:
    import pymupdf
except ImportError:
    sys.stderr.write(
        "pdf_to_book.py needs PyMuPDF. Install the toolkit's requirements:\n"
        "    python3 -m pip install -r requirements.txt\n"
    )
    sys.exit(2)

TOOLKIT_DIR = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(TOOLKIT_DIR, "shell.html")
DICT_BUILDER = os.path.join(TOOLKIT_DIR, "make_dict_data.py")
SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>)", re.I | re.S)
DICT_DATA_RE = re.compile(
    r'(<script type="application/json" id="dict-data">).*?(</script>)',
    re.I | re.S,
)


def clean_text(text, reverse_arabic_digits=False):
    """Normalize common PDF ligatures and optional reversed digit sequences."""
    text = text.replace("\u00ad", "")  # soft hyphen is a layout artifact
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    if reverse_arabic_digits:
        text = re.sub(
            r"[\u0660-\u0669]+", lambda match: match.group(0)[::-1], text
        )
    return text


def detect_reversed_arabic_digits(doc):
    """Return True for an English/Latin-text PDF using Arabic-Indic digits.

    The target PDF family is English books whose digit glyphs are stored in
    reverse logical order. Avoid applying this heuristic to a document that
    contains Arabic-script letters; callers can override it with --digit-order.
    """
    sample = "\n".join(doc[i].get_text("text") for i in range(min(doc.page_count, 40)))
    digit_runs = re.findall(r"[\u0660-\u0669]{2,}", sample)
    latin_letters = sum(char.isascii() and char.isalpha() for char in sample)
    arabic_letters = sum(
        "\u0600" <= char <= "\u06ff"
        and not "\u0660" <= char <= "\u0669"
        for char in sample
    )
    return bool(digit_runs) and latin_letters >= 200 and arabic_letters == 0


def line_runs(line, reverse_arabic_digits=False):
    """One PDF line -> (plain text, size, [(text, superscript, italic)])."""
    runs, plain, size = [], [], 0.0
    for span in line.get("spans", []):
        text = clean_text(span.get("text", ""), reverse_arabic_digits)
        if not text:
            continue
        flags = int(span.get("flags", 0))
        font = str(span.get("font", "")).lower()
        superscript = bool(flags & 1)
        italic = bool(flags & 2) or "italic" in font or "oblique" in font
        runs.append((text, superscript, italic))
        plain.append(text)
        size = max(size, float(span.get("size", 0.0)))
    if runs:
        text, superscript, italic = runs[-1]
        runs[-1] = (text.rstrip(), superscript, italic)
    return "".join(plain).rstrip(), size, runs


def page_lines(page, body_size, reverse_arabic_digits=False):
    """Return ordered paragraph/heading groups for one PDF page."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        block_items = []
        for line in block.get("lines", []):
            text, size, runs = line_runs(line, reverse_arabic_digits)
            if text.strip():
                block_items.append((text, size, runs))
        if not block_items:
            continue

        paragraph, kind = [], None
        for text, size, runs in block_items:
            if size > body_size * 1.45:
                next_kind = "h2"
            elif size > body_size * 1.12:
                next_kind = "h3"
            else:
                next_kind = "p"
            if kind is not None and next_kind != kind and paragraph:
                out.append((kind, paragraph))
                paragraph = []
            kind = next_kind
            paragraph.append((text, runs))
        if paragraph:
            out.append((kind, paragraph))
    return out


def join_paragraph(lines):
    """Join PDF visual lines, retaining italic and superscript markup."""
    plain_parts, html_parts = [], []
    previous = ""
    for text, runs in lines:
        if not text.strip():
            continue
        if previous and not previous.rstrip().endswith("-"):
            plain_parts.append(" ")
            html_parts.append(" ")
        for run_text, superscript, italic in runs:
            if not run_text:
                continue
            plain_parts.append(run_text)
            rendered = html.escape(run_text)
            if superscript:
                rendered = "<sup>" + rendered + "</sup>"
            if italic:
                rendered = "<em>" + rendered + "</em>"
            html_parts.append(rendered)
        previous = text
    plain = re.sub(r"\s+", " ", "".join(plain_parts)).strip()
    rendered = re.sub(r"\s+", " ", "".join(html_parts)).strip()
    return plain, rendered


def looks_like_furniture(text):
    """Detect isolated page-number furniture, without dropping body numbers."""
    text = text.strip()
    return bool(
        re.fullmatch(r"\d{1,4}", text)
        or re.fullmatch(r"(?i)(page\s*)?\d{1,4}\s*(of\s*\d{1,4})?", text)
    )


def repair_drop_caps(elements):
    """Join a one-letter drop cap to its paragraph after any page heading.

    A common PDF layout stores a large initial in its own block. The PDF reader
    may report it before the chapter heading even though readers encounter the
    heading first. Remove only the unmistakable pattern: one capital H2, zero or
    more following headings, then a paragraph beginning with a lowercase letter.
    """
    index = 0
    while index < len(elements):
        match = re.fullmatch(
            r'<h2><span id="line-\d+-\d+" class="text-line">([A-Z])</span></h2>',
            elements[index],
        )
        if not match:
            index += 1
            continue
        paragraph_index = index + 1
        while paragraph_index < len(elements) and re.match(r"<h[23]>", elements[paragraph_index]):
            paragraph_index += 1
        if paragraph_index >= len(elements) or not elements[paragraph_index].startswith("<p>"):
            index += 1
            continue
        first_text = html.unescape(re.sub(r"<[^>]*>", "", elements[paragraph_index])).lstrip()
        if not first_text or not first_text[0].islower():
            index += 1
            continue
        letter = match.group(1)
        updated, count = re.subn(
            r"(<p><span\b[^>]*>)",
            lambda opening: opening.group(1) + letter,
            elements[paragraph_index],
            count=1,
        )
        if count != 1:
            index += 1
            continue
        elements[paragraph_index] = updated
        elements.pop(index)
        # Continue at this index: another leading initial may be adjacent.
    return elements


UNTITLED_RE = re.compile(r"^\(?\s*untitled\s*\)?$", re.I)
RUNNING_HEAD_WINDOW = 2   # a heading repeated within this many pages is furniture


def clean_outline(toc, total):
    """Return (entries, usable) for a PDF outline.

    Retail PDFs often carry a degenerate outline: entries titled "(Untitled)",
    duplicates, or every entry pointing at the same page. Passing that straight
    into the reader shell yields a table of contents that cannot be used, so
    filter it and report whether what is left is worth showing.
    """
    entries, seen = [], set()
    for title, page_no in toc:
        title = re.sub(r"\s+", " ", str(title or "")).strip()
        if not title or UNTITLED_RE.match(title):
            continue
        try:
            page_no = max(1, min(total, int(page_no)))
        except (TypeError, ValueError):
            continue
        key = (title.casefold(), page_no)
        if key in seen:
            continue
        seen.add(key)
        entries.append((title, page_no))
    pages = {page_no for _, page_no in entries}
    return entries, len(entries) >= 2 and len(pages) >= 2


def is_identity_heading(text, title="", author=""):
    """True for a title-page heading that just repeats the book's identity."""
    if not title:
        return False
    flat = re.sub(r"\s+", " ", text).casefold()
    if flat == title.casefold():
        return True
    return title.casefold() in flat and bool(author) and author.casefold() in flat


def detect_headings(doc, body_size, total, reverse_arabic_digits=False, title="", author=""):
    """Build a table of contents from the pages' own big-text headings.

    Uses the same size thresholds as build_reading_content(), so what is set as
    an <h2> in the book is what appears in the navigation. Larger headings win;
    h3 is used only when a book has no h2 at all. A heading repeated within
    RUNNING_HEAD_WINDOW pages is a running head and is dropped, while a title
    that legitimately recurs much later (e.g. "Chapter 1" in each part) is kept.
    """
    for kind_wanted in ("h2", "h3"):
        entries, last_page = [], {}
        for index in range(total):
            page_no = index + 1
            for kind, lines in page_lines(doc[index], body_size, reverse_arabic_digits):
                if kind != kind_wanted:
                    continue
                text = " ".join(line[0].strip() for line in lines if line[0].strip())
                text = re.sub(r"\s+", " ", text).strip()
                if not 2 <= len(text) <= 120:
                    continue
                if looks_like_furniture(text) or UNTITLED_RE.match(text):
                    continue
                if is_identity_heading(text, title, author):
                    continue
                key = text.casefold()
                if page_no - last_page.get(key, -RUNNING_HEAD_WINDOW) <= RUNNING_HEAD_WINDOW:
                    last_page[key] = page_no
                    continue
                last_page[key] = page_no
                entries.append((text, page_no))
        if entries:
            return entries
    return []


def build_reading_content(page, body_size, page_no, total, reverse_arabic_digits=False):
    elements = []
    line_no = 0
    for kind, raw_lines in page_lines(page, body_size, reverse_arabic_digits):
        lines = [item for item in raw_lines if item[0].strip()]
        if not lines or (len(lines) == 1 and looks_like_furniture(lines[0][0])):
            continue
        plain, _ = join_paragraph(lines)
        if not plain:
            continue
        spans = []
        for _, runs in lines:
            line_no += 1
            inner = ""
            for text, superscript, italic in runs:
                rendered = html.escape(text)
                if superscript:
                    rendered = "<sup>" + rendered + "</sup>"
                if italic:
                    rendered = "<em>" + rendered + "</em>"
                inner += rendered
            spans.append(
                '<span id="line-%d-%d" class="text-line">%s</span>'
                % (page_no, line_no, inner.strip())
            )
        tag = "p" if kind == "p" else kind
        elements.append("<%s>%s</%s>" % (tag, " ".join(spans), tag))
    return "\n".join(repair_drop_caps(elements))


def render_page_image(doc, page_index, dpi, quality):
    try:
        from PIL import Image
    except ImportError:
        sys.stderr.write(
            "--facsimile webp needs Pillow. Install it with:\n"
            "    python3 -m pip install Pillow\n"
        )
        sys.exit(2)

    pixmap = doc[page_index].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=quality, method=6)
    return base64.b64encode(buffer.getvalue()).decode("ascii"), pixmap.width, pixmap.height


def slugify(value, fallback="book"):
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or fallback


def js_string_fragment(value):
    """Escape text for safe insertion inside existing JS string literals."""
    value = str(value)
    value = value.replace("\\", "\\\\")
    value = value.replace("'", "\\'").replace('"', '\\"').replace("`", "\\`")
    value = value.replace("\r", "\\r").replace("\n", "\\n")
    value = value.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    # Prevent literal HTML script terminators inside an inline string.
    value = value.replace("<", "\\x3c").replace(">", "\\x3e")
    value = value.replace("${", "\\${")
    return value


def replace_book_identity(source, title, author):
    """Replace sample title/author in HTML and inline scripts safely."""
    pieces = []
    cursor = 0
    for match in SCRIPT_RE.finditer(source):
        outside = source[cursor:match.start()]
        outside = outside.replace("The Doctrine of Repentance", html.escape(title, quote=True))
        outside = outside.replace("Thomas Watson", html.escape(author, quote=True))
        pieces.append(outside)
        opening, body, closing = match.groups()
        if "application/json" not in opening.lower():
            body = body.replace("The Doctrine of Repentance", js_string_fragment(title))
            body = body.replace("Thomas Watson", js_string_fragment(author))
        pieces.extend((opening, body, closing))
        cursor = match.end()
    outside = source[cursor:]
    outside = outside.replace("The Doctrine of Repentance", html.escape(title, quote=True))
    outside = outside.replace("Thomas Watson", html.escape(author, quote=True))
    pieces.append(outside)
    return "".join(pieces)


def sanitize_template(source):
    """Remove analytics/challenge code and remote script dependencies."""
    removed = 0

    def clean_script(match):
        nonlocal removed
        full_tag = match.group(0)
        opening = match.group(1).lower()
        markers = ("cloudflareinsights", "__cf$cv$params", "challenge-platform", "/cdn-cgi/")
        if "src=" in opening or any(marker in full_tag.lower() for marker in markers):
            removed += 1
            return ""
        return full_tag

    source = SCRIPT_RE.sub(clean_script, source)
    # The reader is offline-first; remove remote stylesheets/preconnect hints.
    source = re.sub(r'<link[^>]*href="https?://[^"]+"[^>]*>', "", source, flags=re.I)
    return source, removed


def strip_dictionary_assets(source):
    """Remove dictionary payload, styles, and Define hook for --no-dictionary."""
    patterns = (
        r'<script type="application/json" id="dict-data">.*?</script>',
        r'<script id="dict-script">.*?</script>',
        r'<style id="dict-style">.*?</style>',
    )
    for pattern in patterns:
        source = re.sub(pattern, "", source, flags=re.I | re.S)
    return source


def set_dictionary_data(source, data):
    """Replace the one JSON data block with book-specific dictionary entries."""
    payload = data.replace("<", r"\u003c")
    updated, count = DICT_DATA_RE.subn(
        lambda match: match.group(1) + payload + match.group(2), source, count=1
    )
    if count != 1:
        raise ValueError("reader shell must contain exactly one dict-data placeholder")
    return updated


def external_resource_references(source):
    """List resource-bearing external refs (ordinary outbound links are fine)."""
    refs = re.findall(r'<script[^>]*src=', source, flags=re.I)
    refs += re.findall(r'<link[^>]*href="https?://', source, flags=re.I)
    refs += re.findall(r'<img[^>]*src="https?://', source, flags=re.I)
    refs += re.findall(r'url\s*\(\s*["\']?https?://', source, flags=re.I)
    return refs


def build_book_shell(shell, args, total, toc, body_size, reverse_digits):
    marker = '<main class="book">'
    if shell.count(marker) != 1 or shell.count("</main>") < 1:
        raise ValueError("shell.html must have a single main.book container")
    main_start = shell.index(marker)
    main_end = shell.index("</main>", main_start) + len("</main>")
    pre = shell[:main_start]
    post = shell[main_end - len("</main>"):]

    pre, removed_pre = sanitize_template(pre)
    post, removed_post = sanitize_template(post)
    rekeys = {
        "watson-repentance": args.prefix,
        "doctrine-of-repentance": args.slug,
        "doctrine-book": args.picker,
    }
    for old, new in rekeys.items():
        pre = pre.replace(old, new)
        post = post.replace(old, new)
    pre = replace_book_identity(pre, args.title, args.author)
    post = replace_book_identity(post, args.title, args.author)

    # Replace metadata and visible header fields in the template.
    attr = lambda value: html.escape(value, quote=True)
    text = lambda value: html.escape(value, quote=False)
    pre = re.sub(
        r'<meta\s+name="author"\s+content="[^"]*">',
        '<meta name="author" content="%s">' % attr(args.author),
        pre,
        count=1,
        flags=re.I,
    )
    blurb = " With a reading view and an original-page view." if args.facsimile == "webp" else " With a reading view."
    description = "%s by %s. Complete HTML conversion of the supplied %d-page PDF.%s" % (
        attr(args.title), attr(args.author), total, blurb
    )
    pre = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*">',
        lambda _: '<meta name="description" content="%s">' % description,
        pre,
        count=1,
        flags=re.I,
    )
    pre = re.sub(
        r"<title>.*?</title>",
        "<title>%s &#8212; %s</title>" % (text(args.title), text(args.author)),
        pre,
        count=1,
        flags=re.I | re.S,
    )
    pre = re.sub(r"<h1>.*?</h1>", "<h1>%s</h1>" % text(args.title), pre, count=1, flags=re.I | re.S)
    pre = re.sub(
        r'<p\s+class="byline">.*?</p>',
        '<p class="byline">%s &#183; %d original PDF pages</p>' % (text(args.author), total),
        pre,
        count=1,
        flags=re.I | re.S,
    )
    pre = re.sub(r'(<input\s+id="page-number"[^>]*\bmax=")[0-9]+(")',
                 lambda m: m.group(1) + str(total) + m.group(2), pre, count=1, flags=re.I)

    jump = ['<option value="">Jump to a chapter&#8230;</option>']
    nav = []
    for title, page_no in toc:
        safe = html.escape(title, quote=True)
        jump.append('<option value="%d">%s</option>' % (page_no, safe))
        nav.append('<a href="#page-%d"><span>%s</span><small>%d</small></a>' % (page_no, safe, page_no))
    pre = re.sub(
        r'(<select\s+id="chapter-jump"[^>]*>).*?</select>',
        lambda match: match.group(1) + "".join(jump) + "</select>",
        pre,
        count=1,
        flags=re.I | re.S,
    )
    pre = re.sub(
        r'(<nav\s+class="toc"\s+aria-label="Table of contents">).*?(</nav>)',
        lambda match: match.group(1) + "".join(nav) + match.group(2),
        pre,
        count=1,
        flags=re.I | re.S,
    )
    if args.facsimile == "none":
        pre = pre.replace('<option value="original">Original pages</option>', "", 1)

    if args.no_dictionary:
        pre = strip_dictionary_assets(pre)
        post = strip_dictionary_assets(post)
    else:
        # Never ship the sample Watson vocabulary. The builder fills this safe
        # placeholder after the new book's text sections have been generated.
        placeholder, count = DICT_DATA_RE.subn(
            lambda m: m.group(1) + "{}" + m.group(2), post, count=1
        )
        if count != 1:
            raise ValueError("sample shell has no unique dict-data block to replace")
        post = placeholder

    sections = []
    image_bytes = 0
    doc = args._doc
    for index in range(total):
        page_no = index + 1
        page = doc[index]
        reading = build_reading_content(page, body_size, page_no, total, reverse_digits)
        has_text = bool(reading.strip())
        original = ""
        if args.facsimile == "webp" or not has_text:
            encoded, width, height = render_page_image(doc, index, args.dpi, args.quality)
            image_bytes += len(encoded)
            original = (
                '<div class="original-content"><div class="original-sheet">'
                '<img src="data:image/webp;base64,%s" alt="Original PDF page %d" '
                'width="%d" height="%d"></div></div>'
                % (encoded, page_no, width, height)
            )
        if not has_text and original:
            source = re.search(r'src="([^"]+)"', original).group(1)
            reading = '<figure><img src="%s" alt="Page %d"></figure>' % (source, page_no)
        sections.append(
            '<section id="page-%d" class="source-page" data-page="%d" aria-label="Page %d">\n'
            '<div class="page-label"><span>Page %d of %d</span>'
            '<a href="#top" aria-label="Back to top">&#8593; Top</a></div>\n'
            '<div class="reading-content">%s</div>\n%s</section>'
            % (page_no, page_no, page_no, page_no, total, reading, original)
        )

    book = pre + marker + "\n".join(sections) + post
    return book, image_bytes, removed_pre + removed_post


def main():
    parser = argparse.ArgumentParser(description="Convert a text PDF into a paged, annotated HTML book.")
    parser.add_argument("--pdf", required=True, help="input PDF with a text layer")
    parser.add_argument("--out", required=True, help="output HTML path")
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--prefix", help="unique annotation/storage prefix (default: derived from title + author)")
    parser.add_argument("--slug", help="book filename slug (default: derived from title)")
    parser.add_argument("--picker", help="unique file-picker ID (default: derived from slug)")
    parser.add_argument("--facsimile", choices=["none", "webp"], default="none")
    parser.add_argument("--dpi", type=int, default=90)
    parser.add_argument("--quality", type=int, default=50)
    parser.add_argument("--digit-order", choices=["auto", "normal", "reverse-arabic"], default="auto",
                        help="auto-detect reversed Arabic-Indic digit runs in Latin-text PDFs")
    parser.add_argument("--toc", choices=["auto", "pdf", "headings", "none"], default="auto",
                        help="navigation source: auto (outline when usable, else headings), "
                             "pdf (outline only), headings (scan the pages), none (no navigation)")
    parser.add_argument("--no-dictionary", action="store_true",
                        help="omit dictionary UI/data; useful for offline builds without NLP data")
    args = parser.parse_args()

    try:
        pdf_path = os.path.abspath(args.pdf)
        out_path = os.path.abspath(args.out)
        if pdf_path == out_path:
            raise ValueError("input PDF and output HTML paths must be different")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError("PDF not found: " + pdf_path)
        if args.dpi < 36 or args.dpi > 240:
            raise ValueError("--dpi must be between 36 and 240")
        if not 1 <= args.quality <= 100:
            raise ValueError("--quality must be between 1 and 100")
        if not os.path.isfile(SHELL):
            raise FileNotFoundError("reader shell not found: " + SHELL)

        args.slug = args.slug or slugify(args.title)
        args.prefix = args.prefix or slugify(args.title + " " + args.author)
        args.picker = args.picker or (args.slug + "-file")
        for name in ("prefix", "slug", "picker"):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", getattr(args, name)):
                raise ValueError("--%s must contain lowercase letters, numbers, and hyphens only" % name)

        doc = pymupdf.open(pdf_path)
        total = doc.page_count
        if total < 1:
            raise ValueError("PDF contains no pages")
        if args.digit_order == "reverse-arabic":
            reverse_digits = True
        elif args.digit_order == "normal":
            reverse_digits = False
        else:
            reverse_digits = detect_reversed_arabic_digits(doc)

        sizes = Counter()
        for index in range(min(total, 40)):
            for block in doc[index].get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if len(text) > 20:
                            sizes[round(float(span.get("size", 0)), 1)] += len(text)
        if not sizes:
            raise ValueError("PDF has no extractable text layer. OCR the PDF first, then convert it.")
        body_size = sizes.most_common(1)[0][0]

        toc = []
        for _, title, page_no in doc.get_toc():
            title = re.sub(r"\s+", " ", clean_text(title, reverse_digits)).strip()
            toc.append((title, page_no))
        outline, outline_usable = clean_outline(toc, total)
        raw_count = len(toc)
        raw_pages = len({page_no for _, page_no in toc})

        def headings_toc():
            print("   scanning page headings for navigation\u2026")
            return detect_headings(doc, body_size, total, reverse_digits, args.title, args.author)

        if args.toc == "none":
            toc, source = [], "none"
        elif args.toc == "pdf":
            toc, source = outline, "PDF outline"
            if not toc:
                print("WARNING: --toc pdf, but this PDF has no usable outline; navigation will be empty")
        elif args.toc == "headings":
            toc, source = headings_toc(), "page headings"
        else:                                             # auto
            if outline_usable:
                toc, source = outline, "PDF outline"
            else:
                if raw_count:
                    print("WARNING: PDF outline unusable (%d entries pointing at %d unique page(s)); "
                          "building navigation from the pages' own headings"
                          % (raw_count, raw_pages))
                else:
                    print("NOTE: this PDF has no outline; building navigation from the "
                          "pages' own headings")
                toc, source = headings_toc(), "page headings"
        if args.toc == "auto" and source == "PDF outline" and len(outline) != raw_count:
            print("NOTE: dropped %d unusable or duplicate outline entry/entries"
                  % (raw_count - len(outline)))
        if toc:
            print("navigation: %d entries from the %s" % (len(toc), source))
        elif args.toc != "none":
            print("WARNING: no navigation entries found; the table of contents will be empty "
                  "(use --toc pdf|headings|none to choose)")

        with io.open(SHELL, encoding="utf-8") as file:
            shell = file.read()
        shell, removed_scripts = sanitize_template(shell)
        args._doc = doc
        output_html, image_bytes, _ = build_book_shell(shell, args, total, toc, body_size, reverse_digits)
        if not args.no_dictionary:
            # The dictionary builder reads only .reading-content inside <main>,
            # so it sees the current book and not tool UI/script vocabulary.
            with tempfile.TemporaryDirectory(prefix=".pdf-to-book-", dir=os.path.dirname(out_path) or ".") as tmp:
                base_path = os.path.join(tmp, "book-base.html")
                dict_path = os.path.join(tmp, "dict_data.json")
                with io.open(base_path, "w", encoding="utf-8") as file:
                    file.write(output_html)
                result = subprocess.run(
                    [sys.executable, DICT_BUILDER, "--book", base_path, "--out", dict_path],
                    cwd=TOOLKIT_DIR,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    print(result.stdout.strip())
                if result.stderr.strip():
                    print(result.stderr.strip(), file=sys.stderr)
                if result.returncode != 0:
                    raise RuntimeError("offline dictionary build failed; rerun with --no-dictionary to skip it")
                with io.open(dict_path, encoding="utf-8") as file:
                    dictionary = json.load(file)
                if not isinstance(dictionary, dict):
                    raise ValueError("dictionary builder did not return a JSON object")
                output_html = set_dictionary_data(output_html, json.dumps(dictionary, ensure_ascii=False, separators=(",", ":")))
                print("dictionary entries: %d" % len(dictionary))

        refs = external_resource_references(output_html)
        if refs:
            raise ValueError("reader template still has external resource references; refusing to write an online-dependent book")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        fd, temp_output = tempfile.mkstemp(prefix=".book-", suffix=".html", dir=os.path.dirname(out_path) or ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(output_html)
            os.replace(temp_output, out_path)
        except Exception:
            try:
                os.unlink(temp_output)
            except OSError:
                pass
            raise

        print("wrote %s" % out_path)
        print("  pages: %d | body font: %.1fpt | toc entries: %d" % (total, body_size, len(toc)))
        print("  digit order repair: %s" % ("on" if reverse_digits else "off"))
        print("  removed %d remote/tracker script(s)" % removed_scripts)
        print("  file: %.1f MB (embedded page images: %.1f MB)" % (os.path.getsize(out_path) / 1e6, image_bytes / 1e6))
        print("  sections: %d" % output_html.count('class="source-page"'))
        return 0
    except Exception as error:  # provide a useful command-line failure instead of a traceback
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
