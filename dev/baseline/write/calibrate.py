#!/usr/bin/env python3
"""Distribution of selected count items in the write reference corpora, split by text length (1,500 characters).

Usage: python -I calibrate.py <cache> <repo> <out.json> <metric id> [<metric id> ...]
Writes calibration.json. write judges A13, A14, and A7.see_judgment with the pooled rate of the CSAT passages.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus as C  # noqa: E402

cache, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
ids = sys.argv[4:]
sys.path.insert(0, os.path.join(repo, "skills", "write", "scripts"))
import lint_ko as L  # noqa: E402


def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 3) if xs else None


corp = C.load_all(cache, repo)
spec = L.load_json(L.PATTERNS_PATH)
res = {}
for name, docs in corp.items():
    long_rate, short_cnt = collections.defaultdict(list), collections.defaultdict(list)
    pooled = collections.Counter()
    chars_long = chars_all = 0
    for d in docs[:600]:
        text = "\n\n".join(d["paragraphs"]) + "\n"
        an = L.analyze(text, patterns_spec=spec)
        chars = an["stats"]["chars"]
        chars_all += chars
        for mid in ids:
            base_id = mid[:-7] if mid.endswith("_per_1k") else mid
            n = len(an["metrics"][base_id]["hits"]) if base_id in an["metrics"] else an["metrics"][mid]["value"]
            pooled[mid] += n
            if chars >= 1500:
                long_rate[mid].append(1000 * n / chars)
            else:
                short_cnt[mid].append(n)
        if chars >= 1500:
            chars_long += chars
    res[name] = {}
    for mid in ids:
        lr, sc = long_rate[mid], short_cnt[mid]
        res[name][mid] = {"pooled_per_1k": round(1000 * pooled[mid] / max(1, chars_all), 3),
                          "long": {"n": len(lr), "median": q(lr, .5), "p90": q(lr, .9), "p95": q(lr, .95), "p99": q(lr, .99), "max": q(lr, 1)},
                          "short": {"n": len(sc), "median": q(sc, .5), "p90": q(sc, .9), "p95": q(sc, .95), "p99": q(sc, .99), "max": q(sc, 1)}}
        print(name, mid, json.dumps(res[name][mid], ensure_ascii=False))
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
