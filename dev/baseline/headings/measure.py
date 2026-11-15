#!/usr/bin/env python3
"""Measure how titles and headings end in human writing and in model writing without the skill.

Classifies each title and heading with lint_ko.heading_form (noun, nominal, question, plain, polite, polite_q) and
counts the forms per source and period. The repo keeps only the counts (stats.json) and the IDs of the sampled
press releases. Source text stays in the gitignored docs/ cache.

Sources
  --techblog DIR   cache of human tech blog posts: DIR/meta.json (id -> {date, title, site}) and DIR/md/<id>.md
  --press JSON     press release titles from fetch_press_titles.py: [{date, id, title}, ...]
  --no-skill DIR   markdown files the model wrote with skills disabled (deck*.md: "## title" and "### subtitle" per
                   slide, report*.md: "# title" and section headings)

Usage
  python -I dev/baseline/headings/measure.py --techblog docs/corpus/techblog --press docs/corpus/press/titles.json \
      --no-skill dev/baseline/headings/no-skill --out dev/baseline/headings/stats.json

Uses only the standard library (Python 3.8 or later).
"""

import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "core", "scripts"))
import lint_ko as L  # noqa: E402

FORMS = ("noun", "nominal", "question", "plain", "polite", "polite_q")
SENTENCE_FORMS = ("plain", "polite", "polite_q")
# A press release title often starts with a label such as "[참고]" or "(설명자료)". The label is not part of the title.
PRESS_LABEL_RE = re.compile(r"^(?:\[[^\]]*\]|\([^)]*\))\s*")


def period(date):
    ym = (date or "")[:7]
    if not ym:
        return "unknown"
    if ym <= "2020-12":
        return "~2020"
    if ym <= "2022-11":
        return "2021~2022-11"
    if ym <= "2024-12":
        return "2022-12~2024"
    return "2025~"


def summarize(counter):
    n = sum(counter.values())
    sent = sum(counter[f] for f in SENTENCE_FORMS)
    out = {"n": n, "sentence": sent, "sentence_share": round(sent / n, 4) if n else 0.0}
    out.update({f: counter[f] for f in FORMS})
    return out


def headings_of(text, min_level=1):
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type == "heading" and b.level >= min_level:
            yield b.level, L.clean_inline(b.text)[0]


def measure_techblog(cache):
    meta = json.load(open(os.path.join(cache, "meta.json"), encoding="utf-8"))
    titles = collections.defaultdict(collections.Counter)
    heads = collections.defaultdict(collections.Counter)
    docs = collections.defaultdict(lambda: {"docs": 0, "docs_with_sentence_heading": 0})
    for item in meta.values():
        titles[period(item.get("date"))][L.heading_form(item.get("title") or "")] += 1
    md = os.path.join(cache, "md")
    for name in sorted(os.listdir(md)):
        if not name.endswith(".md"):
            continue
        p = period((meta.get(name[:-3]) or {}).get("date"))
        forms = [L.heading_form(t) for _, t in headings_of(L.read_text(os.path.join(md, name)), min_level=2)]
        if not forms:
            continue
        heads[p].update(forms)
        docs[p]["docs"] += 1
        docs[p]["docs_with_sentence_heading"] += any(f in SENTENCE_FORMS for f in forms)
    return {"titles": {p: summarize(c) for p, c in sorted(titles.items())},
            "headings": {p: dict(summarize(c), **docs[p]) for p, c in sorted(heads.items())}}


def measure_press(path):
    rows = json.load(open(path, encoding="utf-8"))
    by_year = collections.defaultdict(collections.Counter)
    for r in rows:
        by_year[r["date"][:4]][L.heading_form(PRESS_LABEL_RE.sub("", r["title"].strip()))] += 1
    total = collections.Counter()
    for c in by_year.values():
        total.update(c)
    return {"all": summarize(total), "by_year": {y: summarize(c) for y, c in sorted(by_year.items())}}


def measure_no_skill(folder):
    roles = collections.defaultdict(collections.Counter)
    files = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.md"))):
        name = os.path.basename(path)
        deck = name.startswith("deck")
        own = collections.Counter()
        for level, text in headings_of(L.read_text(path)):
            if deck:
                role = "deck_title" if level <= 2 else "deck_subtitle"
            else:
                role = "report_title" if level == 1 else "report_heading"
            form = L.heading_form(text)
            roles[role][form] += 1
            own[form] += 1
        files[name] = summarize(own)
    return {"roles": {r: summarize(c) for r, c in sorted(roles.items())}, "files": files}


def main(argv=None):
    ap = argparse.ArgumentParser(description="title and heading form statistics")
    ap.add_argument("--techblog")
    ap.add_argument("--press")
    ap.add_argument("--no-skill")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    out = {}
    if args.techblog:
        out["techblog"] = measure_techblog(args.techblog)
    if args.press:
        out["press"] = measure_press(args.press)
    if args.no_skill:
        out["no_skill"] = measure_no_skill(args.no_skill)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
