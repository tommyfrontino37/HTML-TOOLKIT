#!/usr/bin/env python3
"""make_dict_data.py - build the offline dictionary that ships inside a book.

    python3 make_dict_data.py --book book.html --out dict_data.json

Only the words that actually appear in the book are included, so the data stays
small.  Sources, in order of preference:

  1. glossary.py    - hand-written definitions for Puritan/theological vocabulary
                      (the machine-readable sources give modern or wrong senses)
  2. WordNet        - clean, concise modern glosses
  3. Webster's 1913 - public domain, and the right vintage for archaic words

Webster's 1913 is fetched once and cached in /tmp (wrn1913.json).
"""

import argparse
import collections
import io
import json
import os
import re
import sys
import urllib.request

WEBSTER_URL = ("https://raw.githubusercontent.com/matthewreagan/"
               "WebstersEnglishDictionary/master/dictionary.json")
WEBSTER_CACHE = "/tmp/wrn1913.json"

SOURCES = ("glossary", "wordnet", "webster")


def lemma_forms(w):
    """Cheap English morphology: enough for plurals, tenses and archaic -eth."""
    forms = [w]
    if w.endswith("ies") and len(w) > 4:
        forms.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 3:
        forms.append(w[:-2])
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        forms.append(w[:-1])
    if w.endswith("ed") and len(w) > 4:
        forms += [w[:-2], w[:-1]]
        if len(w) > 5 and w[-3] == w[-4]:
            forms.append(w[:-3])
    if w.endswith("ing") and len(w) > 5:
        forms += [w[:-3], w[:-3] + "e"]
        if w[-4] == w[-5]:
            forms.append(w[:-4])
    if w.endswith("ly") and len(w) > 4:
        forms.append(w[:-2])
    if w.endswith("est") and len(w) > 5:
        forms.append(w[:-3])
    if w.endswith("eth") and len(w) > 5:
        forms.append(w[:-3])
    if w.endswith("th") and len(w) > 5:
        forms.append(w[:-2])
    return forms


def book_vocabulary(path):
    s = io.open(path, encoding="utf-8", errors="replace").read()
    i, j = s.find('<main class="book">'), s.find("</main>")
    if i < 0 or j < 0:
        i, j = 0, len(s)
    text = re.sub(r"<[^>]+>", " ", s[i:j])
    text = re.sub(r"data:[^\s\"']+", " ", text)          # base64 blobs
    words = re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", text)
    counts = collections.Counter(w.lower().strip("'-") for w in words)
    return {w for w in counts if len(w) > 2}


def load_webster():
    if not os.path.exists(WEBSTER_CACHE):
        print("   fetching Webster's 1913 (22 MB, cached for next time)…")
        urllib.request.urlretrieve(WEBSTER_URL, WEBSTER_CACHE)
    data = json.load(io.open(WEBSTER_CACHE, encoding="utf-8"))
    return {k.lower(): v for k, v in data.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-webster", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from glossary import GLOSSARY

    vocab = book_vocabulary(args.book)
    print("   vocabulary: %d unique words" % len(vocab))

    try:
        from nltk.corpus import wordnet as wn
        have_wn = True
    except Exception:                                     # noqa: BLE001
        have_wn = False
        print("   (wordnet unavailable)")

    webster = {}
    if not args.no_webster:
        try:
            webster = load_webster()
        except Exception as exc:                          # noqa: BLE001
            print("   (webster unavailable: %s)" % exc)

    entries, counts = {}, collections.Counter()
    for w in sorted(vocab):
        forms = lemma_forms(w)

        # 1. the hand-written glossary (also matched through the forms)
        hit = None
        for f in forms:
            if f in GLOSSARY:
                hit = ("glossary", [GLOSSARY[f]], f)
                break

        # 2. WordNet
        if hit is None and have_wn:
            for f in forms:
                ss = wn.synsets(f)
                if ss:
                    hit = ("wordnet", [x.definition()[:160] for x in ss[:2]], f)
                    break

        # 3. Webster's 1913
        if hit is None and webster:
            for f in forms:
                v = webster.get(f)
                if v:
                    d = re.sub(r"\s+", " ", v).strip()
                    hit = ("webster", [d[:230]], f)
                    break

        if hit is None:
            continue
        src, senses, base = hit
        senses = [s.rstrip() for s in senses if s and s.strip()]
        if not senses:
            continue
        entries[w] = {"s": {"glossary": "GL", "wordnet": "WN", "webster": "WB"}[src], "d": senses}
        if base != w:
            entries[w]["f"] = base                        # "showed as"
        counts[src] += 1

    blob = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    io.open(args.out, "w", encoding="utf-8").write(blob)
    print("   entries: %d (glossary %d | wordnet %d | webster %d)"
          % (len(entries), counts["glossary"], counts["wordnet"], counts["webster"]))
    print("   data: %.0f KB -> %s" % (len(blob) / 1024, args.out))


if __name__ == "__main__":
    main()
