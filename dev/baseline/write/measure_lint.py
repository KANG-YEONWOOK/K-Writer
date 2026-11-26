#!/usr/bin/env python3
"""Measure the lint's flow items (A23, A24) on the reference corpora and on AI-written texts in the repo.

Usage: python -I measure_lint.py <cache> <repo> <out.json> [--show corpus N]
Writes lint-stats.json. --show prints N random hits of one corpus for reading.
"""
import collections
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus as C  # noqa: E402

cache, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(repo, "skills", "write", "scripts"))
import lint_ko as L  # noqa: E402

IDS = ("A23.unlinked", "A23.unlinked_share", "A23.offtopic_para", "A23.topic_cover", "A24.noun_run")
show_corpus, show_n = None, 0
if "--show" in sys.argv:
    i = sys.argv.index("--show")
    show_corpus, show_n = sys.argv[i + 1], int(sys.argv[i + 2])


def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 3) if xs else None


def measure(name, texts):
    per = collections.defaultdict(list)
    tot = collections.Counter()
    samples = collections.defaultdict(list)
    for text in texts:
        an = L.analyze(text)
        st = an["stats"]
        if st["sentences"] < L.FLOW_MIN_SENTENCES:
            continue
        m = an["metrics"]
        paras = sum(1 for _ in text.split("\n\n"))
        tot["docs"] += 1
        tot["sentences"] += st["sentences"]
        tot["chars"] += st["chars"]
        tot["unlinked"] += m["A23.unlinked"]["value"]
        tot["unlinked_notopic"] += sum(1 for h in m["A23.unlinked"]["hits"] if h.get("match"))
        tot["offtopic"] += m["A23.offtopic_para"]["value"]
        tot["runs"] += m["A24.noun_run"]["value"]
        share = m["A23.unlinked_share"]["value"]
        pairs = round(m["A23.unlinked"]["value"] / share) if share else 0
        tot["pairs"] += pairs
        per["unlinked"].append(m["A23.unlinked"]["value"])
        per["unlinked_share"].append(share)
        per["offtopic"].append(m["A23.offtopic_para"]["value"])
        per["topic_cover"].append(m["A23.topic_cover"]["value"])
        per["runs_per_1k"].append(1000 * m["A24.noun_run"]["value"] / max(1, st["chars"]))
        per["runs"].append(m["A24.noun_run"]["value"])
        for h in m["A24.noun_run"]["hits"]:
            samples["run"].append(h["match"])
        for h in m["A23.unlinked"]["hits"]:
            samples["unlinked"].append((h["previous"]["text"][:80], h["text"][:100], h.get("match")))
        for h in m["A23.offtopic_para"]["hits"]:
            samples["offtopic"].append(h["text"][:110])
    n = max(1, tot["docs"])
    res = {
        "docs": tot["docs"], "sentences": tot["sentences"], "chars": tot["chars"],
        "unlinked_share_pooled": None,
        "unlinked_per_doc": {"median": q(per["unlinked"], .5), "p90": q(per["unlinked"], .9), "p95": q(per["unlinked"], .95)},
        "unlinked_share": {"p10": q(per["unlinked_share"], .1), "median": q(per["unlinked_share"], .5),
                           "p90": q(per["unlinked_share"], .9), "p95": q(per["unlinked_share"], .95)},
        "unlinked_without_topic_word_per_100_sentences": round(100 * tot["unlinked_notopic"] / max(1, tot["sentences"]), 2),
        "unlinked_per_100_sentences": round(100 * tot["unlinked"] / max(1, tot["sentences"]), 2),
        "offtopic_para_docs_share": round(sum(1 for x in per["offtopic"] if x) / n, 3),
        "offtopic_para_per_doc_mean": round(tot["offtopic"] / n, 3),
        "topic_cover": {"p10": q(per["topic_cover"], .1), "median": q(per["topic_cover"], .5), "p90": q(per["topic_cover"], .9)},
        "noun_run_per_1k_chars_pooled": round(1000 * tot["runs"] / max(1, tot["chars"]), 3),
        "noun_run_per_1k_chars": {"median": q(per["runs_per_1k"], .5), "p90": q(per["runs_per_1k"], .9), "p95": q(per["runs_per_1k"], .95)},
        "noun_run_docs_share": round(sum(1 for x in per["runs"] if x) / n, 3),
    }
    if show_corpus == name:
        rnd = random.Random(5)
        for k in ("run", "unlinked", "offtopic"):
            xs = samples[k]
            rnd.shuffle(xs)
            for x in xs[:show_n]:
                print("  ", k, "|", x)
    return res


corp = C.load_all(cache, repo)
results = {}
for name, docs in corp.items():
    texts = ["\n\n".join(d["paragraphs"]) + "\n" for d in docs[:400] if d.get("para_ok") or name == "abstract"]
    results[name] = measure(name, texts)
ai = {
    "ai_no_skill_reports": sorted(glob.glob(os.path.join(repo, "dev/baseline/headings/no-skill/report*.md"))),
    "k_writer_outputs": [os.path.join(repo, "k-writer-overview.md")] + sorted(glob.glob(os.path.join(repo, "examples/*.default.md")))
    + sorted(glob.glob(os.path.join(repo, "evals/*/results/*detail.md"))),
}
for name, paths in ai.items():
    results[name] = measure(name, [L.read_text(p) for p in paths])
json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for name, r in results.items():
    print(f"{name:20s} docs {r['docs']:4d} | unlinked/100 sent {r['unlinked_per_100_sentences']:5.2f} (no topic word {r['unlinked_without_topic_word_per_100_sentences']:5.2f})"
          f" share med {r['unlinked_share']['median']} p90 {r['unlinked_share']['p90']} p95 {r['unlinked_share']['p95']}"
          f" | offtopic docs {r['offtopic_para_docs_share']} | topic_cover p10 {r['topic_cover']['p10']} med {r['topic_cover']['median']}"
          f" | noun_run/1k pooled {r['noun_run_per_1k_chars_pooled']} p90 {r['noun_run_per_1k_chars']['p90']} docs {r['noun_run_docs_share']}")
