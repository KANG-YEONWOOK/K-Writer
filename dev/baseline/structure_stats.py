#!/usr/bin/env python3
"""사람 글의 서술 방식(글 골격과 설명 방식)을 잰다. 글의 내용(사실, 주장, 수치)은 재지 않는다.

style-guide.md의 글 골격 관례(제목 형태, 도입, 절 수, 절 첫 문장, 마무리, 용어 설명, 예시, 수치 문장)를
사람 글 분포로 다시 확인하는 데 쓴다. 저장소에는 글 ID와 지표 값만 남기고 원문은 남기지 않는다.

사용법
  python dev/baseline/structure_stats.py --cache DIR [--stats PATH] [--out JSON] [--extra 이름=경로 ...]
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "skills", "techblog", "scripts"))
import lint_ko as L  # noqa: E402

EXPERIENCE_RE = re.compile(r"(개발기|구축기|도입기|적용기|전환기|이전기|개선기|여정|후기|회고|경험기|일지|분투기|정복기)")
HOWTO_RE = re.compile(r"(방법|하는 법|[가-힣]{2,}기)\s*$")
REASON_RE = re.compile(r"(이유|왜 )")
SELF_INTRO_RE = re.compile(r"안녕하세요")
AGENDA_RE = re.compile(r"(이 글에서는|이번 글에서는|이 글은|본 글에서는|이 포스트에서는|이번 포스트에서는|이 글을 통해|이번 글을 통해)")
CONCLUSION_FIRST_RE = re.compile(r"결론부터")
PREVIEW_RE = re.compile(r"(알아보겠습니다|알아봅시다|알아볼게요|살펴보겠습니다|살펴봅시다|살펴볼게요|소개하겠습니다|소개할게요|"
                        r"다뤄 ?보겠습니다|다뤄 ?볼게요|이야기해 ?보겠습니다|이야기해 ?볼게요|설명하겠습니다|설명할게요|"
                        r"정리해 ?보겠습니다|정리해 ?볼게요|공유하겠습니다|공유할게요|공유해 ?드리겠습니다)\s*[.!]?$")
CLOSING_RE = re.compile(r"(마치며|맺음말|맺으며|마무리|정리|결론|끝으로|나가며|나오며|마치면서|요약|회고)")
REFERENCES_RE = re.compile(r"^\s*(참고\s*자료|참고\s*문헌|참고|레퍼런스|References?|Reference|출처|각주|부록)\s*$", re.I)
GLOSS_RE = re.compile(r"[가-힣]+\([A-Za-z][A-Za-z0-9 .,/\-]*\)|[A-Za-z][A-Za-z0-9.\-]*\([가-힣][^)]{0,40}\)")
EXAMPLE_RE = re.compile(r"(예를 들어|예를 들면|예컨대|가령|이를테면)")
LEADIN_RE = re.compile(r"((아래|다음|위)(의)? ?(그림|표|코드|예제|예시|이미지|화면|결과|그래프|다이어그램)|(다음|아래)과 같|(다음|아래)와 같)")
READER_RE = re.compile(r"여러분")
FIRST_PERSON_RE = re.compile(r"(저는|제가|저희|우리는|우리가|우리 팀)")
NUMERIC_RE = re.compile(r"\d[\d,.]*\s*(%|배|ms|초|분|시간|개|건|명|회|GB|MB|KB|TB|px|원|만|억|점)")
COMPARE_RE = re.compile(r"(에서\s*(약\s*)?[\d,.]+\S*\s*(으로|로)|대비|보다|만큼|증가|감소|줄었|줄어|줄일|늘었|늘어|늘릴|향상|개선|"
                        r"단축|차이|[\d.]+\s*배|%p|퍼센트포인트|절반|두 배)")


def clean(s):
    return L.clean_inline(s)[0]


def title_form(title):
    t = title.strip()
    if t.endswith("?") or re.search(r"(까|나요|ㄹ까)\s*$", t):
        return "question"
    if EXPERIENCE_RE.search(t):
        return "experience"
    if HOWTO_RE.search(t):
        return "howto"
    if REASON_RE.search(t):
        return "reason"
    if ":" in t:
        return "colon"
    return "noun"


def prose_sentences(blocks):
    out = []
    for b in blocks:
        if b.type in ("paragraph", "list_item"):
            out += L.split_sentences(clean(b.text))
    return out


def measure(text):
    blocks = L.parse_blocks(text)
    heads = [(i, b) for i, b in enumerate(blocks) if b.type == "heading"]
    title = heads[0][1].text if heads and heads[0][1].level == 1 else ""
    sections = [(i, b) for i, b in heads if b.level <= 2 and not (i == heads[0][0] and title)]
    if not sections:  # 절을 H3로만 나눈 글
        sections = [(i, b) for i, b in heads if b.level == 3]
    body_start = heads[0][0] + 1 if title else 0
    first_sec = sections[0][0] if sections else len(blocks)
    intro = [b for b in blocks[body_start:first_sec] if b.type == "paragraph"]
    intro_text = " ".join(clean(b.text) for b in intro)
    sents = prose_sentences(blocks[body_start:])
    prose = " ".join(sents)
    chars = sum(L.visible_chars(s) for s in sents) or 1
    lens = [len(s) for s in sents]
    previews = 0
    for k, (i, _) in enumerate(sections):
        end = sections[k + 1][0] if k + 1 < len(sections) else len(blocks)
        para = next((b for b in blocks[i + 1:end] if b.type == "paragraph"), None)
        if para:
            first = (L.split_sentences(clean(para.text)) or [""])[0]
            previews += bool(PREVIEW_RE.search(first))
    closing = None
    closing_sents = None
    body_secs = [(k, ib) for k, ib in enumerate(sections) if not REFERENCES_RE.search(ib[1].text)]
    if body_secs:
        k, (i, b) = body_secs[-1]
        m = CLOSING_RE.search(b.text)
        if m:
            end = sections[k + 1][0] if k + 1 < len(sections) else len(blocks)
            closing = m.group(1)
            closing_sents = len(prose_sentences(blocks[i + 1:end]))
    numeric = [s for s in sents if NUMERIC_RE.search(s)]
    per_1k = 1000 / chars
    return {
        "chars": chars,
        "sentences": len(sents),
        "title_form": title_form(title) if title else "none",
        "intro_paragraphs": len(intro) if sections else None,
        "intro_chars": sum(L.visible_chars(clean(b.text)) for b in intro) if sections else None,
        "self_intro": bool(SELF_INTRO_RE.search(prose[:300])),
        "agenda_in_intro": bool(AGENDA_RE.search(intro_text)) if sections else None,
        "conclusion_first": bool(CONCLUSION_FIRST_RE.search(prose)),
        "sections": len(sections),
        "h3": sum(1 for _, b in heads if b.level == 3),
        "section_preview_ratio": round(previews / len(sections), 3) if sections else None,
        "closing": closing,
        "closing_sentences": closing_sents,
        "gloss_per_1k": round(len(GLOSS_RE.findall(prose)) * per_1k, 3),
        "example_per_1k": round(len(EXAMPLE_RE.findall(prose)) * per_1k, 3),
        "leadin_per_1k": round(len(LEADIN_RE.findall(prose)) * per_1k, 3),
        "reader_per_1k": round(len(READER_RE.findall(prose)) * per_1k, 3),
        "first_person_per_1k": round(len(FIRST_PERSON_RE.findall(prose)) * per_1k, 3),
        "numeric_sentences": len(numeric),
        "numeric_compared_ratio": round(sum(1 for s in numeric if COMPARE_RE.search(s)) / len(numeric), 3)
        if numeric else None,
        "short_ratio": round(sum(1 for x in lens if x < 35) / len(lens), 3) if lens else None,
        "long100_ratio": round(sum(1 for x in lens if x >= 100) / len(lens), 3) if lens else None,
    }


def quantile(vals, q):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 3)


NUMERIC_KEYS = ("intro_paragraphs", "intro_chars", "sections", "h3", "section_preview_ratio", "closing_sentences",
                "gloss_per_1k", "example_per_1k", "leadin_per_1k", "reader_per_1k", "first_person_per_1k",
                "numeric_compared_ratio", "short_ratio", "long100_ratio")
SHARE_KEYS = ("self_intro", "agenda_in_intro", "conclusion_first")


def summarize(rows):
    out = {"n": len(rows)}
    for k in NUMERIC_KEYS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = {"n": len(vals), "p25": quantile(vals, .25), "p50": quantile(vals, .5), "p75": quantile(vals, .75)}
    for k in SHARE_KEYS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = {"n": len(vals), "yes": sum(1 for v in vals if v)}
    forms = {}
    for r in rows:
        forms[r["title_form"]] = forms.get(r["title_form"], 0) + 1
    out["title_form"] = forms
    closing = {}
    for r in rows:
        closing[r["closing"] or "없음"] = closing.get(r["closing"] or "없음", 0) + 1
    out["closing"] = closing
    return out


def main():
    L.setup_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--stats", default=os.path.join(ROOT, "dev", "baseline", "stats.json"))
    ap.add_argument("--out", help="글별 값과 그룹별 요약을 저장할 JSON")
    ap.add_argument("--extra", action="append", default=[], help="비교할 글: 이름=경로")
    args = ap.parse_args()
    stats = json.load(open(args.stats, encoding="utf-8"))
    rows = []
    for a in stats["articles"]:
        path = os.path.join(args.cache, "md", a["id"] + ".md")
        if not os.path.exists(path):
            continue
        r = measure(L.read_text(path))
        r.update(id=a["id"], group=a["group"], site=a["site"], holdout=a["holdout"])
        rows.append(r)
    groups = {}
    for g in sorted({r["group"] for r in rows}):
        groups[g] = summarize([r for r in rows if r["group"] == g])
    base = [r for r in rows if r["group"] in ("default", "casual")]
    by_site = {s: summarize([r for r in base if r["site"] == s]) for s in sorted({r["site"] for r in base})}
    extra = {}
    for spec in args.extra:
        name, path = spec.split("=", 1)
        extra[name] = measure(L.read_text(path if os.path.isabs(path) else os.path.join(ROOT, path)))
    result = {"groups": groups, "base_by_site": by_site, "extra": extra,
              "articles": [{k: r[k] for k in ("id", "group", "site", "holdout") + NUMERIC_KEYS + SHARE_KEYS
                            + ("title_form", "closing", "chars", "sentences", "numeric_sentences")} for r in rows]}
    print(json.dumps({k: v for k, v in result.items() if k != "articles"}, ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
            f.write("\n")


if __name__ == "__main__":
    main()
