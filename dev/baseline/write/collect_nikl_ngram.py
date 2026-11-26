#!/usr/bin/env python3
"""Collect top-100 eojeol n-grams of the NIKL newspaper corpus from the public web analyzer (no login).

Usage: python -I collect_nikl_ngram.py <cache>/nikl/ngram_news.jsonl [first_year] [last_year]
One request per second. Each line: {"year", "n", "topics", "rows": [[ngram, freq, share], ...]}.
"""
import json
import sys
import time
import urllib.request

URL = "https://kli.korean.go.kr/corpus/resultRequest/ngramStatProc.do"
TOPICS = ["IT/과학", "경제", "문화", "미용/건강", "사회", "생활", "스포츠", "연예", "정치", "미분류"]


def fetch(year, n, topics):
    body = json.dumps({"corpusCl": "newspaper", "analsYear": [str(year)], "analsTopic": topics, "morpheme": "phrase",
                       "ngramTy": str(n), "symbolCheck": "no"}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json; charset=UTF-8",
                                                          "User-Agent": "Mozilla/5.0 (research; style measurement)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    out = sys.argv[1]
    y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2009
    y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2019
    with open(out, "w", encoding="utf-8") as f:
        for year in range(y0, y1 + 1):
            for n in (2, 3, 4):
                for label, topics in (("all", TOPICS), ("경제", ["경제"]), ("사회", ["사회"]), ("IT/과학", ["IT/과학"])):
                    time.sleep(1.0)
                    try:
                        rows = fetch(year, n, topics)
                    except Exception as e:  # noqa: BLE001
                        print(year, n, label, "error", e, flush=True)
                        continue
                    f.write(json.dumps({"year": year, "n": n, "topics": label,
                                        "rows": [[r["ngramVal"], r["ngramFrq"], r["ngramShrt"]] for r in rows]},
                                       ensure_ascii=False) + "\n")
                    f.flush()
                    print(year, n, label, len(rows), flush=True)


if __name__ == "__main__":
    main()
