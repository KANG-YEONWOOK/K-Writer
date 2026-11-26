#!/usr/bin/env python3
"""Collect presidential speeches (text) from the Presidential Archives list endpoint, one request per second.

Usage: python -I collect_speech.py <cache>/speech/speeches.jsonl [first_year] [last_year] [pages_per_year]
The measurement of 2026-11-26 used 2003 2019 5.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

URL = "https://www.pa.go.kr/portal/research/speech/mList.do"


def fetch(year, page):
    data = urllib.parse.urlencode({"speechEvent": "", "searchKeyword": "", "damPst": "",
                                   "searchStartDate": f"{year}.01.01", "searchEndDate": f"{year}.12.31",
                                   "mediaType": "", "pageIndex": page}).encode()
    req = urllib.request.Request(URL, data=data, headers={"User-Agent": "Mozilla/5.0 (research; style measurement)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    out = sys.argv[1]
    y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2003
    y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2019
    per_year = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    seen = set()
    with open(out, "w", encoding="utf-8") as f:
        for year in range(y0, y1 + 1):
            try:
                first = fetch(year, 1)
            except Exception as e:  # noqa: BLE001
                print(year, "error", e, flush=True)
                time.sleep(2)
                continue
            total = first["paginationInfo"]["totalPageCount"]
            pages = sorted({1 + round(k * (total - 1) / max(1, per_year - 1)) for k in range(per_year)}) if total > 1 else [1]
            kept = 0
            for p in pages:
                time.sleep(1.0)
                try:
                    d = first if p == 1 else fetch(year, p)
                except Exception as e:  # noqa: BLE001
                    print(year, p, "error", e, flush=True)
                    continue
                for r in d.get("resultList", []):
                    key = (r.get("catid"), r.get("artid"))
                    if key in seen or r.get("catnm") != "연설문":
                        continue
                    seen.add(key)
                    f.write(json.dumps({k: r.get(k) for k in ("catid", "artid", "artsubject", "artcont", "damPst",
                                                                "fullDate", "speechEvent", "speechField",
                                                                "speechPlace", "koglYn", "catnm")},
                                       ensure_ascii=False) + "\n")
                    kept += 1
            print(year, "pages", total, "fetched", pages, "kept", kept, flush=True)


if __name__ == "__main__":
    main()
