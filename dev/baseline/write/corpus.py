#!/usr/bin/env python3
"""Load the four reference corpora of write into one format: {"id", "corpus", "paragraphs": [str], "para_ok": bool}.

The texts are not in the repository. collect_csat.py, collect_speech.py, and the commands in README.md put them in a
cache folder (default: docs/corpus/write, which is gitignored). The abstracts are the cache of dev/baseline/brief.
para_ok is False when the source lost the paragraph breaks; such texts are used for sentence-level measurements only.
"""
import glob
import html
import json
import os
import random
import re

PARA_BREAK = re.compile(r"(?<=[가-힣][.?!])(?=[가-힣“‘'\"(\[<])|(?<=[.?!][”’])(?=[가-힣“‘])")


# Two student texts from the writing section that the passage filter let through (found while annotating).
CSAT_EXCLUDE = {"csat-2023-082", "csat-2023-083"}


def load_csat(path):
    docs = []
    for p in json.load(open(path, encoding="utf-8")):
        if p["id"] in CSAT_EXCLUDE:
            continue
        docs.append({"id": p["id"], "corpus": "csat", "paragraphs": p["paragraphs"], "para_ok": p["para_ok"],
                     "year": p["year"]})
    return docs


def load_news(parquet, limit=1200, seed=7):
    import pyarrow.parquet as pq
    rows = pq.read_table(parquet).to_pylist()
    seen, docs = set(), []
    for r in rows:
        if r["source"] != "hankyung" or r["context"] in seen:
            continue
        seen.add(r["context"])
        text = re.sub(r"[ \t]+", " ", r["context"]).strip()
        # KLUE joined the paragraphs of an article without a space, so a sentence end directly followed by a
        # Hangul character or an opening quote marks a paragraph break.
        paras = [p.strip() for p in PARA_BREAK.split(text) if p.strip()]
        if len(text) < 800 or len(paras) < 3:
            continue
        docs.append({"id": "news-" + r["guid"], "corpus": "news", "paragraphs": paras, "para_ok": True,
                     "title": r["title"], "truncated": not text.endswith((".", "”", "’", ")"))})
    random.Random(seed).shuffle(docs)
    return docs[:limit]


def load_abstracts(folder, meta_path, max_year=2019):
    meta = json.load(open(meta_path, encoding="utf-8"))
    docs = []
    for path in sorted(glob.glob(os.path.join(folder, "*.md"))):
        key = os.path.basename(path)[:-3]
        m = meta.get(key)
        if not m or int(m.get("year") or 9999) > max_year:
            continue
        text = open(path, encoding="utf-8").read().strip()
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        docs.append({"id": key, "corpus": "abstract", "paragraphs": paras, "para_ok": False, "year": int(m["year"]),
                     "category": m.get("category")})
    return docs


def load_speeches(path, limit=600, seed=7):
    docs = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        raw = html.unescape(r.get("artcont") or "")
        paras = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip() for p in re.split(r"(?:<br\s*/?>\s*){2,}", raw)]
        paras = [p for p in paras if p]
        body = [p for p in paras if len(p) >= 40 and re.search(r"[다요까][.?!]?$", p)]
        if sum(len(p) for p in body) < 800 or len(body) < 4:
            continue
        docs.append({"id": f"speech-{r['artid']}", "corpus": "speech", "paragraphs": paras, "para_ok": True,
                     "year": int((r.get("fullDate") or "0")[:4] or 0), "speaker": r.get("damPst"),
                     "event": r.get("speechEvent"), "title": r.get("artsubject")})
    random.Random(seed).shuffle(docs)
    return docs[:limit]


def load_all(cache, repo):
    return {
        "csat": load_csat(os.path.join(cache, "csat/passages.json")),
        "news": load_news(os.path.join(cache, "news/klue_mrc_train.parquet")),
        "abstract": load_abstracts(os.path.join(repo, "docs/corpus/kci/md"), os.path.join(repo, "docs/corpus/kci/meta.json")),
        "speech": load_speeches(os.path.join(cache, "speech/speeches.jsonl")),
    }


def default_paths():
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(repo, "docs", "corpus", "write"), repo


if __name__ == "__main__":
    import sys
    cache, repo = default_paths()
    if len(sys.argv) > 1:
        cache = sys.argv[1]
    for name, docs in load_all(cache, repo).items():
        chars = sum(len(p) for d in docs for p in d["paragraphs"])
        paras = sum(len(d["paragraphs"]) for d in docs)
        print(name, "docs", len(docs), "paragraphs", paras, "chars", chars)
        d = docs[0]
        print("  ", d["id"], [len(p) for p in d["paragraphs"]][:12], d["paragraphs"][0][:60])
