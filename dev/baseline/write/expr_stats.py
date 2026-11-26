#!/usr/bin/env python3
"""Frequent sentence-final and sentence-initial expressions per corpus.

Usage: python -I expr_stats.py <cache> <repo> <out.json>
Writes expression-stats.json: the share of sentences that end or start with each word or word pair.
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus as C  # noqa: E402

cache, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(repo, "skills", "write", "scripts"))
import lint_ko as L  # noqa: E402

corp = C.load_all(cache, repo)
res = {}
for name, docs in corp.items():
    fin1, fin2, ini1, ini2 = (collections.Counter() for _ in range(4))
    n = 0
    for d in docs:
        for p in d["paragraphs"]:
            for s in L.split_sentences(p):
                s = s.strip()
                toks = [t.strip("\"'“”‘’()[],") for t in s.rstrip(".?! ”’\"").split()]
                toks = [t for t in toks if t]
                if len(toks) < 4:
                    continue
                n += 1
                fin1[toks[-1]] += 1
                fin2[" ".join(toks[-2:])] += 1
                ini1[toks[0]] += 1
                ini2[" ".join(toks[:2])] += 1
    res[name] = {"sentences": n,
                 "final_1": [(k, v, round(100 * v / n, 2)) for k, v in fin1.most_common(60)],
                 "final_2": [(k, v, round(100 * v / n, 2)) for k, v in fin2.most_common(50)],
                 "initial_1": [(k, v, round(100 * v / n, 2)) for k, v in ini1.most_common(50)],
                 "initial_2": [(k, v, round(100 * v / n, 2)) for k, v in ini2.most_common(30)]}
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for name, r in res.items():
    print("==", name, r["sentences"])
    print(" final_1:", " ".join(f"{k}({p})" for k, v, p in r["final_1"][:40]))
    print(" final_2:", " / ".join(f"{k}({p})" for k, v, p in r["final_2"][:28]))
    print(" initial_1:", " ".join(f"{k}({p})" for k, v, p in r["initial_1"][:36]))
