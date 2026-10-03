#!/usr/bin/env python3
"""Bake a highlights/notes JSON export into a copy of the book, producing an
annotated .html that carries your marks inside it (same format the in-file
"Save into HTML" button writes).

Usage:
    python3 bake_annotations.py your-export.json
    python3 bake_annotations.py your-export.json "My annotated book.html"
"""
import io, json, os, re, sys, time, random

MASTER_DEFAULT = "The Doctrine of Repentance - Thomas Watson.html"
BLOCK_RE = re.compile(r'\s*<script type="application/json" id="baked-annotations">.*?</script>', re.S)

def esc_for_script(text):
    """Keep '</' from ever appearing inside the data block (JSON-safe escaping)."""
    return text.replace("<", "\\u003c")

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src_json = sys.argv[1]
    master = os.path.join(os.path.dirname(os.path.abspath(__file__)), MASTER_DEFAULT)
    out_path = sys.argv[2] if len(sys.argv) > 2 else None

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

    payload = {
        "app": "The Doctrine of Repentance (HTML edition)",
        "version": 1,
        "baked": "%d-%d" % (int(time.time() * 1000), random.randint(0, 999999)),
        "bakedOn": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "highlights": hl,
        "notes": nt,
    }
    block = ('<script type="application/json" id="baked-annotations">%s</script>'
             % esc_for_script(json.dumps(payload, separators=(",", ":"), ensure_ascii=False)))

    html = io.open(master, encoding="utf-8").read()
    removed = len(BLOCK_RE.findall(html))
    html = BLOCK_RE.sub("", html)                     # replace, never append
    m = re.search(r"<body[^>]*>", html)
    if not m:
        sys.exit("could not find <body> in the master file")
    html = html[:m.end()] + "\n" + block + html[m.end():]

    if not out_path:
        stamp = time.strftime("%Y-%m-%d")
        out_path = "The Doctrine of Repentance (annotated %s).html" % stamp
    io.open(out_path, "w", encoding="utf-8").write(html)

    before, after = os.path.getsize(master), os.path.getsize(out_path)
    print("master        : %s (%.2f MB)" % (os.path.basename(master), before / 1e6))
    print("wrote         : %s (%.2f MB, %+.0f KB)" % (out_path, after / 1e6, (after - before) / 1024))
    print("contains      : %d highlights, %d notes" % (len(hl), len(nt)))
    print("old blocks    : %d replaced" % removed)
    print("data block    : 1" if html.count('id="baked-annotations"') == 1 else "data block : PROBLEM")

if __name__ == "__main__":
    main()
