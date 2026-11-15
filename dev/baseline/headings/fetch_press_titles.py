#!/usr/bin/env python3
"""Fetch the titles of government press releases (korea.kr) published on sampled dates.

Only titles are fetched, from the list page of each date. korea.kr allows every path in robots.txt, and the text of
press releases is under KOGL Type 1 (source attribution). The titles go to the gitignored docs/ cache. The repo keeps
the sampled dates and press release IDs (press-ids.json), not the titles.

Sampled dates: the 12th of odd months and the 19th of even months, 2018 to 2020, up to three list pages per date.

Usage
  python -I dev/baseline/headings/fetch_press_titles.py docs/corpus/press/titles.json \
      --ids dev/baseline/headings/press-ids.json

Uses only the standard library (Python 3.8 or later).
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.request

LIST_URL = ("https://www.korea.kr/briefing/pressReleaseList.do?pageIndex={page}&srchWord=&startDate={date}"
            "&endDate={date}&period=direct")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-crawler)"}
ITEM_RE = re.compile(r'<a href="/briefing/pressReleaseView\.do\?newsId=(\d+)[^"]*">\s*<span class="text">\s*'
                     r"<strong>(.*?)</strong>", re.S)
YEARS = (2018, 2019, 2020)
MAX_PAGES = 3


def sample_dates():
    return ["%d-%02d-%02d" % (y, m, 12 if m % 2 else 19) for y in YEARS for m in range(1, 13)]


def fetch(date, page):
    req = urllib.request.Request(LIST_URL.format(page=page, date=date), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def main(argv=None):
    ap = argparse.ArgumentParser(description="fetch press release titles for sampled dates")
    ap.add_argument("out")
    ap.add_argument("--ids", help="write the sampled dates and press release IDs to this file")
    args = ap.parse_args(argv)
    rows, seen = [], set()
    for date in sample_dates():
        for page in range(1, MAX_PAGES + 1):
            try:
                found = ITEM_RE.findall(fetch(date, page))
            except OSError as e:
                print(f"ERR {date} page {page}: {e}", file=sys.stderr)
                break
            for news_id, title in found:
                if news_id not in seen:
                    seen.add(news_id)
                    rows.append({"date": date, "id": news_id,
                                 "title": html.unescape(re.sub(r"<[^>]+>", "", title)).strip()})
            print(date, page, len(found), flush=True)
            time.sleep(1.0)
            if len(found) < 10:
                break
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    if args.ids:
        by_date = {}
        for r in rows:
            by_date.setdefault(r["date"], []).append(r["id"])
        with open(args.ids, "w", encoding="utf-8") as f:
            json.dump({"source": "https://www.korea.kr/briefing/pressReleaseList.do", "ids": by_date}, f, indent=0)
    print("total", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
