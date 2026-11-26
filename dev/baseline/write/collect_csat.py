#!/usr/bin/env python3
"""Extract expository reading passages from the CSAT-QA dataset (HAERAE-HUB/csatqa).

Input: csatqa.json (JSON lines) of the dataset, downloaded as README.md describes. Output: passages.json with
de-wrapped paragraphs. Needs kiwipiepy (it joins the printed lines and repairs spacing).
Run with: python -I collect_csat.py <cache>/csat/csatqa.json <cache>/csat/passages.json

The dataset stores three layouts. "wrapped": one line per printed line (paragraph breaks are recovered from short
last lines). "paras": one line per paragraph. "flat": the whole passage on one line (paragraph breaks are lost, so
these passages are kept for sentence-level measurements only).
"""
import collections
import difflib
import json
import re
import sys
import unicodedata

from kiwipiepy import Kiwi

INSTRUCTION = re.compile(r"^\s*(?:\[\d+\s*[~～]\s*\d+\]\s*)?다음 글을 읽고 물음에 답하시오\.?\s*")
TAG = re.compile(r"</?(?:word|sent|par|etc)/?>")
MARK = re.compile(r"\((?:[ㄱ-ㅎ]|[a-e])\)\s*|[㉠-㉮ⓐ-ⓩ]\s*")
BRACKET = re.compile(r"\[[A-E]\]\s*")
FOOTNOTE = re.compile(r"^\s*\*\s*\S[^:：]{0,30}[:：]")
GRAMMAR_WORDS = ("형태소", "음운", "어미", "품사", "합성어", "파생어", "중세 국어", "표준 발음", "문장 성분",
                 "어간", "접사", "관형어", "부사어", "안긴문장", "용언", "체언", "훈민정음", "음절", "어근")
TERMINATORS = (".", "?", "!", "”", "’", ")", "]", "」", "』")
# Literature, student drafts, and grammar passages that the feature filter lets through (checked by reading the list).
EXCLUDE_HEADS = ("주재소는 그를", "이윽고 서씨의", "남다른 눈썰미로", "어머니는 조각마루", "는 (가)를 바탕으로",
                 "한 줄의 시(詩)는커녕", "글을 쓰기 위해 (가)의", "그 골목이 그렇게도", "김달채 씨는",
                 "우리나라의 연간 1인당 커피", "일상생활에서 우리는 음절을", "국어사적 사실이", "다의어란",
                 "우리는 단어의 의미와 유래", "합성 명사는", "이 이론의 핵심은")
SPEECH = re.compile(r"안녕하세요|안녕하십니까|^\s*[가-힣○□△]{1,6}\s*[:：]", re.M)


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def clean_line(line):
    line = TAG.sub("", line)
    line = MARK.sub("", line)
    line = BRACKET.sub("", line)
    return re.sub(r"\s+", " ", line).strip()


def strip_extras(ctx):
    """Drops question boxes appended after the passage and the instruction line."""
    ctx = re.split(r"<par>\s*<보기>|<보기>|※", ctx)[0]
    return INSTRUCTION.sub("", ctx, count=1)


def split_pair(ctx):
    """A context that starts with (가) holds two texts; returns them separately."""
    plain = ctx
    m = re.match(r"\s*(?:<par>)?\s*\(가\)", plain)
    if not m:
        return [ctx]
    if re.search(r"\(다\)", plain):
        return [re.sub(r"(?m)^\s*(?:<par/?>)?\s*\([가-마]\)\s*", "", plain)]
    body = plain[m.end():]
    parts = re.split(r"(?:<par/?>)?\s*\n?\s*(?:<par>)?\s*\(나\)", body, maxsplit=1)
    return [p for p in parts if p.strip()]


def layout(lines):
    ws = [width(clean_line(x)) for x in lines if clean_line(x)]
    if len(ws) <= 2:
        return "flat"
    ws_sorted = sorted(ws)
    med = ws_sorted[len(ws_sorted) // 2]
    return "wrapped" if med < 90 and len(ws) >= 10 else "paras"


def wrapped_paragraphs(raw, kiwi):
    lines, region = [], 0
    for ln in raw:
        if "<sent>" in ln:
            region += 1
        c = clean_line(ln)
        if c:
            lines.append([c, region])
        if "<sent/>" in ln:
            region += 1
    for i, (c, _) in enumerate(lines):
        if FOOTNOTE.match(c):
            lines = lines[:i]
            break
    # A footnote star is typeset on its own, so the particle after it lands on a separate short line.
    merged = []
    for c, r in lines:
        if merged and merged[-1][2]:
            merged[-1][0] = merged[-1][0].rstrip("* ") + c.lstrip("* ")
            merged[-1][2] = c.rstrip().endswith("*") and len(c) <= 3
            continue
        merged.append([c, r, c.rstrip().endswith("*")])
    lines = [[c.replace("*", "").strip(), r] for c, r, _ in merged if c.replace("*", "").strip()]
    paras, cur = [], []
    for i, (c, r) in enumerate(lines):
        cur.append(c)
        window = [width(x) for x, rr in lines[max(0, i - 4):i + 5] if rr == r]
        ref = max(window) if window else width(c)
        region_ends = i + 1 < len(lines) and lines[i + 1][1] != r
        if c.endswith(TERMINATORS) and (width(c) <= ref - 4 or region_ends or i + 1 == len(lines)):
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    return [kiwi.glue(p) if len(p) > 1 else p[0] for p in paras]


def tidy(text, kiwi, respace=False):
    text = re.sub(r"\s+", " ", text).strip()
    if respace:
        # Flat entries keep the spaces left by joined line breaks ("단백 질"); the analyzer re-spaces them.
        text = kiwi.space(text, reset_whitespace=True)
    text = re.sub(r"\s+([.,?!])", r"\1", text)
    return text


def to_paragraphs(ctx, kiwi):
    raw = [x for x in ctx.split("\n")]
    kind = layout(raw)
    if kind == "wrapped":
        paras = wrapped_paragraphs(raw, kiwi)
        return kind, [tidy(p, kiwi) for p in paras if p.strip()]
    paras = []
    for ln in raw:
        c = clean_line(ln)
        if not c or FOOTNOTE.match(c) or re.search(r"그려져\s*있다\.?$|그림이다\.?$", c) and len(c) < 80:
            continue
        c = c.replace("*", "")
        if paras and not paras[-1].rstrip().endswith(TERMINATORS):
            paras[-1] = paras[-1].rstrip() + " " + c
        else:
            paras.append(c)
    return kind, [tidy(p, kiwi, respace=True) for p in paras]


def classify(paras, ctx):
    text = " ".join(paras)
    sents = [s for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    if not sents:
        return "empty", {}
    da = sum(1 for s in sents if re.search(r"다[.”’)]*$", s.strip()))
    quotes = len(re.findall(r"“[^”]{2,80}[요죠까니라냐네지오소게마구나군][.?!]?”", text))
    grammar = sum(1 for w in GRAMMAR_WORDS if w in text)
    feats = {"sent": len(sents), "da": round(da / len(sents), 2), "quotes": quotes, "grammar": grammar,
             "chars": len(text)}
    if SPEECH.search(TAG.sub("", ctx)):
        return "speech", feats
    if feats["da"] < 0.82 or quotes >= 3:
        return "literature", feats
    if grammar >= 3:
        return "grammar", feats
    if feats["chars"] < 700:
        return "short", feats
    return "expository", feats


def main():
    src, dst = sys.argv[1], sys.argv[2]
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    groups = collections.OrderedDict()
    for x in rows:
        c = x.get("context") or ""
        if c.strip():
            groups.setdefault((x["test_name"], c), []).append(x)
    kiwi = Kiwi()
    cands = []
    counts = collections.Counter()
    for (test, ctx), qs in groups.items():
        head = TAG.sub("", ctx.split("\n")[0])
        if "물음에 답하시오" in head and "다음 글을 읽고 물음에 답하시오" not in head:
            counts["other_instruction"] += 1
            continue
        year = int(re.search(r"(\d{4}) 대학수학능력시험", test).group(1))
        for k, part in enumerate(split_pair(strip_extras(ctx))):
            kind, paras = to_paragraphs(part, kiwi)
            label, feats = classify(paras, part)
            counts[label] += 1
            if label != "expository":
                continue
            cands.append({"year": year, "test": re.sub(r"\s+", " ", test), "part": k,
                          "questions": sorted(q["question_number"] for q in qs),
                          "category": next((q["Category"] for q in qs if q.get("Category")), None),
                          "layout": kind, "feats": feats, "paragraphs": paras})
    # The same passage appears once per question set and in both A and B papers; keep the shortest copy.
    kept = []
    for c in sorted(cands, key=lambda c: c["feats"]["chars"]):
        key = re.sub(r"\s+", "", "".join(c["paragraphs"]))[:160]
        dup = False
        for k in kept:
            if difflib.SequenceMatcher(None, key, k["_key"], autojunk=False).ratio() > 0.8:
                dup = True
                k["questions"] = sorted(set(k["questions"]) | set(c["questions"])) if k["test"] == c["test"] else k["questions"]
                k["category"] = k["category"] or c["category"]
                break
        if dup:
            counts["duplicate"] += 1
            continue
        c["_key"] = key
        kept.append(c)
    kept.sort(key=lambda c: (c["year"], c["test"], c["questions"][0], c["part"]))
    kept = [c for c in kept if not any(c["paragraphs"][0].startswith(h) for h in EXCLUDE_HEADS)]
    for i, c in enumerate(kept):
        c.pop("_key")
        c["id"] = f"csat-{c['year']}-{i:03d}"
        lens = [len(x) for x in c["paragraphs"]]
        c["para_ok"] = (c["layout"] == "wrapped" or (c["layout"] == "paras" and c["year"] in (2014, 2022, 2023))) \
            and min(lens) >= 60 and len(lens) >= 2
    json.dump(kept, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(dict(counts), "kept", len(kept))
    print("chars", sum(p["feats"]["chars"] for p in kept), "paragraphs", sum(len(p["paragraphs"]) for p in kept))
    print(sorted(collections.Counter(p["year"] for p in kept).items()))
    print(collections.Counter(p["layout"] for p in kept))


if __name__ == "__main__":
    main()
