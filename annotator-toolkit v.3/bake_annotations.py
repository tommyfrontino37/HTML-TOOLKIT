#!/usr/bin/env python3
"""Bake a highlights/notes JSON export into a copy of the book, producing an
annotated .html that carries your marks inside it (same format the in-file
"Save into HTML" button writes).

Usage:
    python3 bake_annotations.py your-export.json --master "My Book.html"
    python3 bake_annotations.py your-export.json "My annotated book.html" --master "My Book.html"

--master names the book to bake into. Without it the script looks for the
original toolkit book next to itself, which is how it was first written; point
it at your own build instead. The baked payload's app name and the default
output file name come from the master's <title>, so a baked copy says which
book it belongs to.
"""
import io, json, os, re, sys, time, random
from html import unescape

MASTER_DEFAULT = "The Doctrine of Repentance - Thomas Watson.html"  # legacy default, next to this script
BLOCK_RE = re.compile(r'\s*<script type="application/json" id="baked-annotations">.*?</script>', re.S)

def esc_for_script(text):
    """Keep '</' from ever appearing inside the data block (JSON-safe escaping)."""
    return text.replace("<", "\\u003c")

def book_identity(html, fallback):
    """(app label, short name) from the book's own <title>, for payload naming."""
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if not m:
        return fallback, fallback
    title = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
    # "<book> <dash> <author>" -> "<book>"; only real dashes, never a hyphen
    short = re.split(r"\s+[\u2014\u2013]\s+", title)[0].strip() or title
    return short + " (HTML edition)", short


def main():
    argv = [a for a in sys.argv[1:]]
    master_path = None
    for flag in ("--master", "--book"):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                sys.exit("%s needs a path" % flag)
            master_path = argv[i + 1]
            del argv[i:i + 2]
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        print(__doc__)
        sys.exit(2)
    src_json = positional[0]
    out_path = positional[1] if len(positional) > 1 else None

    master = (os.path.abspath(master_path) if master_path else
              os.path.join(os.path.dirname(os.path.abspath(__file__)), MASTER_DEFAULT))
    if not os.path.exists(master):
        sys.exit("master book not found: %s\nPass --master \"My Book.html\" to name it." % master)

    data = json.load(io.open(src_json, encoding="utf-8"))
    if isinstance(data, list):
        data = {"highlights": [], "notes": data}
    hl = data.get("highlights", []) or []
    nt = data.get("notes", []) or []

    # keep only well-formed entries
    hl = [h for h in hl if isinstance(h, dict) and all(isinstance(h.get(k), (int, float)) for k in ("page", "start", "end"))
          and h.get("color") in ("yellow", "green", "blue", "red")]
    nt = [n for n in nt if isinstance(n, dict) and isinstance(n.get("body"), str)
          and all(isinstance(n.get(k), (int, float)) for k in ("page", "start", "end"))]

    html = io.open(master, encoding="utf-8").read()
    app_label, short_name = book_identity(html, "The Doctrine of Repentance")

    payload = {
        "app": app_label,
        "version": 1,
        "baked": "%d-%d" % (int(time.time() * 1000), random.randint(0, 999999)),
        "bakedOn": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "highlights": hl,
        "notes": nt,
    }
    block = ('<script type="application/json" id="baked-annotations">%s</script>'
             % esc_for_script(json.dumps(payload, separators=(",", ":"), ensure_ascii=False)))
    removed = len(BLOCK_RE.findall(html))
    html = BLOCK_RE.sub("", html)                     # replace, never append
    m = re.search(r"<body[^>]*>", html)
    if not m:
        sys.exit("could not find <body> in the master file")
    html = html[:m.end()] + "\n" + block + html[m.end():]

    if not out_path:
        stamp = time.strftime("%Y-%m-%d")
        out_path = "%s (annotated %s).html" % (short_name, stamp)
    io.open(out_path, "w", encoding="utf-8").write(html)

    before, after = os.path.getsize(master), os.path.getsize(out_path)
    print("master        : %s (%.2f MB)" % (os.path.basename(master), before / 1e6))
    print("wrote         : %s (%.2f MB, %+.0f KB)" % (out_path, after / 1e6, (after - before) / 1024))
    print("contains      : %d highlights, %d notes" % (len(hl), len(nt)))
    print("old blocks    : %d replaced" % removed)
    # Count the whole tag, never the bare id: the reader's own JavaScript also
    # mentions 'baked-annotations', so the bare-id count cries wolf on a
    # perfectly good bake (it reported PROBLEM on every v.3 book).
    blocks = len(BLOCK_RE.findall(html))
    print("data block    : 1" if blocks == 1 else "data block    : PROBLEM (%d found)" % blocks)

if __name__ == "__main__":
    main()
