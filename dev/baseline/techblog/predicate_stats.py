#!/usr/bin/env python3
"""Re-measure adjacent predicate repetition candidates on the existing human article list.

Source text is read from the measure.py collect cache. Missing articles are not counted as 0, and distributions with and
without holdout are both recorded. The output does not store source text.
These figures are candidate frequencies, not a count of sentences to fix or a PASS/FAIL threshold.

  python dev/baseline/techblog/predicate_stats.py --cache DIR [--stats PATH] [--out JSON] [--samples N]
"""

import argparse
import collections
import datetime
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "skills", "techblog", "scripts"))
import lint_ko as L  # noqa: E402

METRIC = "A8.same_predicate_adjacent"
GROUPS = ("default", "casual", "mid-default", "mid-casual", "drift-default", "drift-casual")


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (position - lo), 3)


def summarize(rows):
    values = [r["count"] for r in rows]
    chars = sum(r["chars"] for r in rows)
    return {
        "n": len(rows), "zero": sum(v == 0 for v in values), "total": sum(values),
        "p10": quantile(values, .1), "p50": quantile(values, .5), "p90": quantile(values, .9),
        "max": max(values) if values else None,
        "chars": chars, "per_1k": round(sum(values) * 1000 / chars, 3) if chars else None,
    }


def measure(cache, stats, samples=0):
    rows, missing = [], []
    words = collections.Counter()
    shown = 0
    for article in stats["articles"]:
        path = os.path.join(cache, "md", article["id"] + ".md")
        if not os.path.isfile(path):
            missing.append(article["id"])
            continue
        source = L.read_text(path)
        analysis = L.analyze(source)
        metric = analysis["metrics"][METRIC]
        rows.append({
            "id": article["id"], "group": article["group"], "holdout": article["holdout"],
            "site": article["site"], "chars": analysis["stats"]["chars"],
            "count": metric["value"], "ending_run4": analysis["metrics"]["A8.ending_run4"]["value"],
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        })
        words.update(hit["match"] for hit in metric["hits"])
        for hit in metric["hits"]:
            if samples < 0 or shown < samples:
                print(f"{article['id']} L{hit['line']} [{hit['match']}]")
                print("  " + hit["previous"]["text"])
                print("  " + hit["text"])
                shown += 1
    groups = {}
    for group in GROUPS:
        group_rows = [r for r in rows if r["group"] == group]
        groups[group] = {
            "expected": sum(a["group"] == group for a in stats["articles"]),
            "all": summarize(group_rows),
            "without_holdout": summarize([r for r in group_rows if not r["holdout"]]),
        }
    return {
        "measured_at": datetime.date.today().isoformat(), "metric": METRIC,
        "basis": "stats.json의 기존 글 목록과 그룹. 측정일에 확보한 원문 캐시를 현재 lint로 분석.",
        "interpretation": "검토 후보 분포. 실제 반복 문제의 판정이나 자동 수정 기준으로 사용하지 않음.",
        "coverage": {"expected": len(stats["articles"]), "available": len(rows), "missing": missing},
        "groups": groups,
        "calibration_without_holdout": summarize(
            [r for r in rows if r["group"] in ("default", "casual") and not r["holdout"]]),
        "mid_without_holdout": summarize(
            [r for r in rows if r["group"] in ("mid-default", "mid-casual") and not r["holdout"]]),
        "last_words": dict(words.most_common()), "articles": rows,
    }


def main():
    L.setup_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--out", help="JSON path to save aggregates and per-article values, without source text")
    parser.add_argument("--samples", type=int, default=0, help="Number of candidates to review. -1 prints all")
    parser.add_argument("--stats", default=os.path.join(ROOT, "dev", "baseline", "techblog", "stats.json"))
    args = parser.parse_args()
    stats = L.load_json(args.stats)
    result = measure(args.cache, stats, args.samples)
    if not result["coverage"]["available"]:
        parser.error("캐시에 기존 사람 글이 없습니다. measure.py collect로 원문을 먼저 수집하세요.")
    print(json.dumps({key: value for key, value in result.items() if key != "articles"},
                     ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
