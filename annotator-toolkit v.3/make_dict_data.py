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

try:
    import nltk
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        print("Downloading WordNet data...")
        try:
            # An offline machine with nltk installed but no corpus must fall
            # through to the "(wordnet unavailable)" path below, not kill the
            # build: the glossary and Webster sources can carry the book.
            nltk.download('wordnet', quiet=True)
        except Exception as exc:                          # noqa: BLE001
            print("   (wordnet download failed: %s)" % exc)
except ImportError:
    pass

WEBSTER_URL = ("https://raw.githubusercontent.com/matthewreagan/"
               "WebstersEnglishDictionary/master/dictionary.json")
# The cache used to live in /tmp, which containers wipe between sessions and
# which every session re-downloaded 22 MB into. Prefer the user cache; keep
# reading the old location so existing machines do not re-download.
LEGACY_WEBSTER_CACHE = "/tmp/wrn1913.json"
WEBSTER_CACHE = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
    "html-toolkit-wrn1913.json")

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


def load_webster(url=WEBSTER_URL):
    cache = WEBSTER_CACHE
    if not os.path.exists(cache) and os.path.exists(LEGACY_WEBSTER_CACHE):
        cache = LEGACY_WEBSTER_CACHE                      # reuse an earlier download
    if not os.path.exists(cache):
        print("   fetching Webster's 1913 (22 MB, cached for next time)…")
        try:
            os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
            urllib.request.urlretrieve(url, cache)
        except Exception:                                 # noqa: BLE001
            # Not fatal: fall back to the legacy path (writable almost anywhere)
            # so a read-only or missing ~/.cache cannot stop the build.
            cache = LEGACY_WEBSTER_CACHE
            urllib.request.urlretrieve(url, cache)
    data = json.load(io.open(cache, encoding="utf-8"))
    return {k.lower(): v for k, v in data.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-webster", action="store_true")
    ap.add_argument("--webster-url", default=WEBSTER_URL,
                    help="override the Webster's 1913 source URL")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from glossary import GLOSSARY

    vocab = book_vocabulary(args.book)
    print("   vocabulary: %d unique words" % len(vocab))

    try:
        from nltk.corpus import wordnet as wn
        # nltk corpora are loaded lazily: the import above succeeds even when
        # the corpus is missing, and the LookupError only fires at first use -
        # by which point it is outside this guard. Force the load here.
        wn.synsets("the")
        have_wn = True
    except Exception:                                     # noqa: BLE001
        have_wn = False
        print("   (wordnet unavailable)")

    webster = {}
    if not args.no_webster:
        try:
            webster = load_webster(args.webster_url)
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
                try:
                    ss = wn.synsets(f)
                except Exception as exc:                  # noqa: BLE001
                    # Corpus vanished or was never fully downloaded: stop using
                    # WordNet and let the glossary/Webster sources carry on.
                    have_wn = False
                    print("   (wordnet failed mid-run: %s; continuing without it)" % exc)
                    break
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
