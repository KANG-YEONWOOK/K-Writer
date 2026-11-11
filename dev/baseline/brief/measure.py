#!/usr/bin/env python3
"""Collect Korean abstracts of journal articles from KCI (Korea Citation Index) and measure them with lint_ko.analyze().

An abstract is a summary that the authors wrote for their own article. brief uses these measurements as the human
sample for one-paragraph summaries in the Plain tone.

Source text is stored only in the --cache folder and is not committed. The repo keeps the article ID list (urls.json)
and the measurements (stats.json).

Collection
  KCI serves bibliographic records over OAI-PMH without an API key. ListRecords with from=until=<day> returns up to
  100 records registered or modified on that day. The collector walks the days between --from and --until with
  --step days, one request per second, and keeps a record when
    - the article language is Korean and the abstract in the original language has at least MIN_HANGUL Hangul
      characters and Hangul is at least HANGUL_SHARE of its letters,
    - pub-year is 2018~2021 (pub-year has no day, so 2022 is left out: the base period ends on 2022-11-30),
    - the journal has fewer than --per-journal abstracts so far.

Usage
  python -I -X utf8 dev/baseline/brief/measure.py collect --cache DIR [--target 1500] [--per-journal 5]
  python -I -X utf8 dev/baseline/brief/measure.py measure --cache DIR [--out dev/baseline/brief/stats.json]
  python -I -X utf8 dev/baseline/brief/measure.py summary [--stats dev/baseline/brief/stats.json]
  python -I -X utf8 dev/baseline/brief/measure.py endings --cache DIR [--techblog-cache DIR]
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "skills", "brief", "scripts"))
import lint_ko as L  # noqa: E402

ENDPOINT = "https://open.kci.go.kr/oai/request"
UA = {"User-Agent": os.environ.get("BASELINE_USER_AGENT", "Mozilla/5.0 (compatible; text-measurement)")}
NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "kci": "http://www.kci.go.kr/kciportal/OAI/"}
BASE_YEARS = ("2018", "2019", "2020", "2021")
MIN_HANGUL = 200
HANGUL_SHARE = 0.7


def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return None
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def text_of(node):
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip() if node is not None else ""


def parse_records(raw):
    """Yield one dict per record of a ListRecords response in the oai_kci format."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return
    for rec in root.iterfind(".//oai:record", NS):
        ident = text_of(rec.find("oai:header/oai:identifier", NS))
        info = rec.find(".//kci:articleInfo", NS)
        jour = rec.find(".//kci:journalInfo", NS)
        if info is None or jour is None:
            continue
        abstract = ""
        for a in info.iterfind("kci:abstract-group/kci:abstract", NS):
            if a.get("lang") == "original":
                abstract = text_of(a)
        yield {
            "id": "kci-" + (info.get("article-id") or ident.rsplit("/", 1)[-1]),
            "url": text_of(info.find("kci:url", NS)),
            "journal": text_of(jour.find("kci:journal-name", NS)),
            "category": text_of(info.find("kci:article-categories", NS)),
            "year": text_of(jour.find("kci:pub-year", NS)),
            "month": text_of(jour.find("kci:pub-mon", NS)),
            "language": text_of(info.find("kci:language", NS)),
            "abstract": abstract,
        }


def eligible(rec):
    if rec["language"] != "한국어" or rec["year"] not in BASE_YEARS:
        return False
    hangul = len(re.findall(r"[가-힣]", rec["abstract"]))
    letters = len(re.findall(r"[가-힣A-Za-z]", rec["abstract"]))
    return hangul >= MIN_HANGUL and letters > 0 and hangul / letters >= HANGUL_SHARE


def cmd_collect(args):
    os.makedirs(os.path.join(args.cache, "md"), exist_ok=True)
    meta_path = os.path.join(args.cache, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    per_journal = {}
    for e in meta.values():
        per_journal[e["journal"]] = per_journal.get(e["journal"], 0) + 1
    day = date.fromisoformat(args.start)
    end = date.fromisoformat(args.until)
    seen = requests = 0
    while day <= end and len(meta) < args.target:
        d = day.isoformat()
        raw = fetch(f"{ENDPOINT}?verb=ListRecords&metadataPrefix=oai_kci&set=ARTI&from={d}&until={d}")
        requests += 1
        time.sleep(1.0)
        day += timedelta(days=args.step)
        if not raw:
            continue
        for rec in parse_records(raw):
            seen += 1
            if rec["id"] in meta or not eligible(rec):
                continue
            if per_journal.get(rec["journal"], 0) >= args.per_journal:
                continue
            per_journal[rec["journal"]] = per_journal.get(rec["journal"], 0) + 1
            with open(os.path.join(args.cache, "md", rec["id"] + ".md"), "w", encoding="utf-8") as f:
                f.write(rec["abstract"] + "\n")
            meta[rec["id"]] = {k: rec[k] for k in ("url", "journal", "category", "year", "month")}
        if requests % 20 == 0:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
            print(f"[collect] {d}: {requests} requests, {seen} records, {len(meta)} kept, "
                  f"{len(per_journal)} journals", flush=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[collect] done: {requests} requests, {seen} records, {len(meta)} kept, {len(per_journal)} journals")


def holdout(aid):
    return int(hashlib.sha1(aid.encode()).hexdigest(), 16) % 5 == 0  # 20%


def tone_of(analysis):
    c = analysis["endings"]["class"]
    hap, hae, hra = c.get("HAPNIDA", 0), c.get("HAEYO", 0), c.get("HAERA", 0)
    pred = hap + hae + hra
    if pred == 0:
        return "unknown", 0.0
    for name, n in (("default", hap), ("casual", hae), ("plain", hra)):
        if n / pred >= 0.9:
            return name, round(n / pred, 3)
    return "mixed", round(max(hap, hae, hra) / pred, 3)


def verdict_of(analysis, thresholds, patterns):
    """Verdict of brief's lint for a Plain summary under the short profile. Policy items apply only to skill output
    (rules.json bands), so they are left out, as in the techblog holdout check."""
    ev = L.evaluate(analysis, thresholds, "plain", max_hits=0, patterns_spec=patterns)
    flagged = {}
    for r in ev["results"]:
        spec = thresholds["metrics"].get(r["id"], {})
        if spec.get("policy") or r["status"] not in ("GATE", "FAIL", "WARN"):
            continue
        flagged[r["id"]] = r["status"]
    fail = sum(1 for v in flagged.values() if v in ("GATE", "FAIL"))
    warn = sum(1 for v in flagged.values() if v == "WARN")
    return {"pass": fail == 0 and warn <= thresholds.get("max_warn", 2), "flagged": flagged}


def cmd_measure(args):
    meta = json.load(open(os.path.join(args.cache, "meta.json"), encoding="utf-8"))
    thresholds, patterns = L.apply_profile(L.load_thresholds(), L.load_json(L.PATTERNS_PATH), short=True)
    rows, urls = [], []
    for aid in sorted(meta):
        e = meta[aid]
        path = os.path.join(args.cache, "md", aid + ".md")
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        a = L.analyze(text, patterns)
        tone, share = tone_of(a)
        included = tone == "plain"
        urls.append({"id": aid, "url": e["url"], "year": e["year"], "month": e["month"], "category": e["category"],
                     "tone": tone, "tone_share": share, "included": included,
                     "holdout": holdout(aid) if included else None,
                     "reason": None if included else "해라체 종결 90% 미만"})
        if not included:
            continue
        row = {"id": aid, "year": e["year"], "category": e["category"], "holdout": holdout(aid),
               "stats": {k: v for k, v in a["stats"].items() if k != "title"},
               "metrics": {mid: m["value"] for mid, m in a["metrics"].items() if m["value"]},
               "sent_len": [len(s.text) for s in a["_sentences"]],
               "sent_chars": [len(re.sub(r"\s", "", s.text)) for s in a["_sentences"]],
               "endings": a["endings"], "lint": verdict_of(a, thresholds, patterns)}
        rows.append(row)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"measured": date.today().isoformat(), "source": "KCI OAI-PMH (oai_kci), abstract lang=original",
                   "n": len(rows), "articles": rows}, f, ensure_ascii=False, indent=1)
    with open(args.urls, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=1)
    print(f"[measure] {len(rows)} included of {len(urls)}")


def quantile(values, q):
    xs = sorted(values)
    if not xs:
        return 0
    i = (len(xs) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


SUMMARY_ITEMS = ("A18.category_change", "A18.count_only", "A18.value_kind", "A18.value_kind_check", "A1.np", "A13.demonstrative_start", "A5.style_words",
                 "A14.translationese", "A12.progressive")


def cmd_summary(args):
    """Print the tables that README.md quotes."""
    arts = json.load(open(args.stats, encoding="utf-8"))["articles"]
    chars = [a["stats"]["chars"] for a in arts]
    sents = [a["stats"]["sentences"] for a in arts]
    sent_chars = [x for a in arts for x in a["sent_chars"]]
    sent_len = [x for a in arts for x in a["sent_len"]]
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    print(f"abstracts {len(arts)}, characters {sum(chars)}, sentences {sum(sents)}, "
          f"holdout {sum(1 for a in arts if a['holdout'])}")
    print("| 값 | p5 | p25 | 중앙값 | p75 | p95 |\n|---|---|---|---|---|---|")
    for name, xs in (("초록의 본문 글자 수(공백 제외)", chars), ("초록의 문장 수", sents),
                     ("문장의 글자 수(공백 제외)", sent_chars), ("문장의 글자 수(공백 포함)", sent_len)):
        print(f"| {name} | " + " | ".join(str(round(quantile(xs, q))) for q in qs) + " |")
    over = sum(1 for x in sent_len if x > 120)
    print(f"sentences over 120 characters with spaces: {over} of {len(sent_len)} ({over / len(sent_len):.1%})")
    total = sum(chars)
    short = [a for a in arts if a["stats"]["chars"] <= 350]
    print(f"abstracts of 350 characters or fewer: {len(short)}")
    print("| 항목 | 검출 횟수 | 검출된 초록 | 1,000자당 | 350자 이하 초록 중 검출 |\n|---|---|---|---|---|")
    for mid in SUMMARY_ITEMS:
        n = sum(a["metrics"].get(mid, 0) for a in arts)
        docs = sum(1 for a in arts if a["metrics"].get(mid, 0))
        short_docs = sum(1 for a in short if a["metrics"].get(mid, 0))
        print(f"| {mid} | {n} | {docs}({docs / len(arts):.1%}) | {1000 * n / total:.4f} | "
              f"{short_docs}({short_docs / len(short):.1%}) |")
    for name, group in (("all", arts), ("holdout", [a for a in arts if a["holdout"]]), ("350 or fewer", short)):
        ok = sum(1 for a in group if a["lint"]["pass"])
        print(f"brief short-profile verdict, {name}: PASS {ok} of {len(group)} ({ok / len(group):.1%})")
    flagged = {}
    for a in arts:
        for mid, status in a["lint"]["flagged"].items():
            flagged.setdefault(mid, {"WARN": 0, "FAIL": 0, "GATE": 0})[status] += 1
    print("| 항목 | WARN | FAIL |\n|---|---|---|")
    for mid, c in sorted(flagged.items(), key=lambda kv: -(kv[1]["WARN"] + kv[1]["FAIL"] + kv[1]["GATE"]))[:8]:
        print(f"| {mid} | {c['WARN']}({c['WARN'] / len(arts):.1%}) | {c['FAIL'] + c['GATE']}"
              f"({(c['FAIL'] + c['GATE']) / len(arts):.1%}) |")


PAST_ENDINGS = ("았다", "었다", "였다", "했다", "됐다", "왔다", "봤다", "줬다", "났다", "갔다", "섰다", "졌다", "켰다", "렸다", "쳤다")
ADJECTIVE_ENDINGS = ("않다", "못하다", "하다", "같다", "크다", "작다", "많다", "적다", "높다", "낮다", "다르다", "어렵다", "쉽다",
                     "좋다")


def plain_ending(sentence, word):
    """Rough class of a Plain-tone ("해라체") sentence ending. A regex-level classification: "~하다" counts as an
    adjective ending, so a few verbs written in the base form land there."""
    w = word.rstrip(".?!\"')]”’")
    tail = sentence.rstrip(" .?!\"')]”’")
    if re.search(r"수\s*(있|없)다$", tail):
        return "~수 있다, ~수 없다"
    if w.endswith("것이다"):
        return "~것이다"
    if w.endswith(("있다", "없다")):
        return "~있다, ~없다"
    if w.endswith(PAST_ENDINGS) or (len(w) >= 2 and L._jong(w[-2]) == L.JONG_SS and w[-2] not in "있"):
        return "과거형(~었다, ~했다)"
    if w.endswith(("이다", "아니다")):
        return "~이다, ~아니다"
    if w.endswith("는다") or (len(w) >= 2 and L._jong(w[-2]) == 4):   # final consonant ㄴ before "다"
        return "현재형 동사(~ㄴ다, ~는다)"
    if w.endswith(ADJECTIVE_ENDINGS):
        return "형용사(~하다, ~않다, ~같다)"
    return "그 밖의 ~다"


def ending_table(name, paths):
    counts, texts = {}, 0
    for path in paths:
        if not os.path.exists(path):
            continue
        texts += 1
        for s in L.analyze(open(path, encoding="utf-8").read())["_sentences"]:
            if s.cls == "HAERA" and s.kind == "paragraph":
                key = plain_ending(s.text, s.word)
                counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    print(f"{name}: {texts} texts, {total} sentences")
    for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"| {key} | {n} | {n / total:.1%} |")


def cmd_endings(args):
    """Ending distribution of human Plain-tone texts: the abstracts and, with --techblog-cache, the base-period "haera"
    group of the techblog sample."""
    md = os.path.join(args.cache, "md")
    ending_table("KCI abstracts", [os.path.join(md, name) for name in sorted(os.listdir(md))])
    if args.techblog_cache:
        urls = json.load(open(os.path.join(ROOT, "dev", "baseline", "techblog", "urls.json"), encoding="utf-8"))
        ids = [u["id"] for u in urls if u.get("included") and u.get("group") == "haera"]
        ending_table("techblog haera group", [os.path.join(args.techblog_cache, "md", i + ".md") for i in ids])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--cache", required=True)
    c.add_argument("--start", default="2018-03-01")
    c.add_argument("--until", default="2022-06-30")
    c.add_argument("--step", type=int, default=3)
    c.add_argument("--target", type=int, default=1500)
    c.add_argument("--per-journal", type=int, default=5)
    m = sub.add_parser("measure")
    m.add_argument("--cache", required=True)
    m.add_argument("--out", default=os.path.join(ROOT, "dev", "baseline", "brief", "stats.json"))
    m.add_argument("--urls", default=os.path.join(ROOT, "dev", "baseline", "brief", "urls.json"))
    r = sub.add_parser("summary")
    r.add_argument("--stats", default=os.path.join(ROOT, "dev", "baseline", "brief", "stats.json"))
    e = sub.add_parser("endings")
    e.add_argument("--cache", required=True)
    e.add_argument("--techblog-cache", help="cache folder of dev/baseline/techblog/measure.py")
    args = ap.parse_args()
    {"collect": cmd_collect, "measure": cmd_measure, "summary": cmd_summary, "endings": cmd_endings}[args.cmd](args)


if __name__ == "__main__":
    main()
