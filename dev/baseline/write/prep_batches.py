#!/usr/bin/env python3
"""Write numbered passages (paragraph and sentence numbers) for the annotation agents.

Usage: python -I prep_batches.py <cache> <repo>
Writes <cache>/annot/*.md. The agents read annotation/GUIDE-csat.md or GUIDE-genre.md and one batch file each.
"""
import json
import os
import random
import sys

from kiwipiepy import Kiwi

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus as C  # noqa: E402

cache, repo = sys.argv[1], sys.argv[2]
kiwi = Kiwi()
corp = C.load_all(cache, repo)
out = os.path.join(cache, "annot")
os.makedirs(out, exist_ok=True)


def render(doc):
    lines = [f"### {doc['id']}" + (f" | {doc.get('title')}" if doc.get("title") else "")]
    n = 0
    for pi, p in enumerate(doc["paragraphs"], 1):
        lines.append(f"[P{pi}]")
        for s in kiwi.split_into_sents(p):
            t = s.text.strip()
            if len(t) < 5:
                continue
            n += 1
            lines.append(f"S{n}. {t}")
    return "\n".join(lines), n


def write(name, docs):
    body, total = [], 0
    for d in docs:
        text, n = render(d)
        body.append(text)
        total += n
    open(os.path.join(out, name), "w", encoding="utf-8").write("\n\n".join(body) + "\n")
    print(name, len(docs), "docs", total, "sentences", sum(len(b) for b in body), "chars")


rnd = random.Random(11)
csat = [d for d in corp["csat"] if d["para_ok"]]
csat.sort(key=lambda d: d["id"])
k = 4
for i in range(k):
    write(f"csat_batch{i + 1}.md", csat[i::k])
news = [d for d in corp["news"] if not d.get("truncated") and 900 <= sum(map(len, d["paragraphs"])) <= 1900]
rnd.shuffle(news)
write("news_batch.md", news[:18])
ab = [d for d in corp["abstract"] if 450 <= len(d["paragraphs"][0]) <= 1100]
rnd.shuffle(ab)
write("abstract_batch.md", ab[:26])
sp = [d for d in corp["speech"] if 1200 <= sum(map(len, d["paragraphs"])) <= 2600]
rnd.shuffle(sp)
write("speech_batch.md", sp[:10])
