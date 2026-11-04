#!/usr/bin/env python3
"""K-Writer post-processing helper: creates a draft copy, finds repeat candidates to reread, compares the article before and after post-processing, and checks edited sentences.

The source of this file is core/scripts/revise_ko.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.
The name in the output header is the name of the skill folder that contains the script.

Usage
  python revise_ko.py start ARTICLE [--force]
  python revise_ko.py repeats ARTICLE [--all] [--json]
  python revise_ko.py check ARTICLE [--facts FACTS.md] [--json]
  python revise_ko.py mark ARTICLE
  python revise_ko.py audit ARTICLE [--base FILE] [--facts FACTS.md] [--out FILE] [--json]

ARTICLE is the "합니다체" article to post-process: the output file (<name>.md) for a Default article, the Default draft
(<name>.draft.md) for a Casual article. The paths of the draft copy (<name>.unrevised.md), the pre-fix copy
(<name>.pre-fix.md), and the fact sheet (<name>.facts.md) are derived from the ARTICLE name.

- start: copies ARTICLE to the draft copy and writes the repeat candidates to <name>.repeats.md. That file lets a
  post-processing subagent without Bash permission read the candidates with Read. An existing copy is not overwritten
  without --force. A pre-fix copy left over from an earlier post-processing run is deleted.
- repeats: prints the positions to reread (repeat candidates). It makes no verdict. For each candidate, the writer
  decides whether the reader of this article needs the repetition.
- check: compares the draft copy with ARTICLE. Prints the number of changed sentences, numbers found only in the draft
  and new numbers, changes to headings, code, and tables, items whose lint status got worse, and new sentences with 3
  or more connective endings.
- mark: copies ARTICLE to the pre-fix copy (overwriting it if present) before fixing what the post-edit review flagged.
- audit: compares the base copy (--base, otherwise the pre-fix copy, otherwise the draft copy) with ARTICLE by sentence,
  heading, and table row. For each changed or newly written unit, prints the questions the post-edit reviewer asks
  (T, F, C, X, "같은 사실", S) and the positions to look at when answering them. Those positions are: the previous and
  next sentences, demonstratives, words that appear for the first time in the article, the line range of a section
  referenced as "…" 절 and the words absent from that section, other lines and fact sheet lines with the same number,
  candidate supporting fact sheet lines, reason and scope markers, the number of comma-separated items, object-predicate
  pairs, multiple subjects or objects sharing one predicate, definitions with overlapping names, lines where the
  pre-edit expression remains, and expressions lint counted in that unit. It makes no verdict. With --out, the result
  is written to that file.

Exit codes: 0 OK, 1 check or audit found a Gate violation, a FAIL, or a worsened AI style item, 2 usage or input error
Uses only the standard library (Python 3.8 or later).
"""

import argparse
import difflib
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_ko as L  # noqa: E402

SKILL_NAME = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SNAPSHOT_SUFFIX = ".unrevised.md"
FACTS_SUFFIX = ".facts.md"
REPEATS_SUFFIX = ".repeats.md"
MARK_SUFFIX = ".pre-fix.md"
AUDIT_SUFFIX = ".audit.md"
MAX_LINES = 8
CHANGED_SHARE_RECHECK = 0.25
SHORT_LEN = 35

# Strips one particle. Longer particles are tried first, and a particle is stripped only if at least two characters
# remain ("차이" stays as is).
# "도" and "만" are not included: tech writing has many nouns ending in these characters, such as "정확도", "속도", "빈도", "수만".
PARTICLES = sorted(("에서는", "에서", "으로", "보다", "까지", "부터", "처럼", "에는", "은", "는", "이", "가", "을",
                    "를", "의", "와", "과", "에", "로"), key=len, reverse=True)
EDGE = "\"'“”‘’()[]{}<>.,?!:;…·「」『』"
SUBJECT_END = ("은", "는", "이", "가")
DEMONSTRATIVES = ("이", "그", "저", "이런", "그런", "이러한", "그러한", "이번", "해당", "위의", "아래")
# Generic endings that R4 does not count. Human posts also use these endings in a row, and lint A8.ending_run4 counts
# runs of the same ending.
GENERIC_PREDICATES = ("있습니다", "없습니다", "합니다", "했습니다", "됩니다", "됐습니다", "되었습니다", "않습니다",
                      "같습니다", "입니다", "있었습니다", "없었습니다", "않았습니다")

# R6: predicates that state an amount of change, and comparison baseline markers
CHANGE_RE = re.compile(r"(줄었|줄어들|줄어든|줄였|늘었|늘어났|늘어난|늘렸|올랐|올라갔|올라간|떨어졌|떨어뜨|떨어진|"
                       r"내려갔|내려간|낮아졌|낮아진|낮췄|높아졌|높아진|높였|감소|증가|개선|향상|단축|커졌|커진|작아졌|"
                       r"작아진|빨라졌|빨라진|느려졌|느려진)")
TIMES_RE = re.compile(r"(?<![\w.\-])\d[\d.,]*\s*배(?:$|[^가-힣]|로|가|를|의|에|까지|였|입|이|나|만큼|씩|가량|정도)")
# Numbers with a unit. A value followed by "까지" or "로" ("1,850ms까지 올랐습니다", "0.8초로 줄었습니다") is the value after
# the change, so it does not count as an amount of change. A multiplier ("2배로") still counts as an amount of change.
UNIT_NUM_RE = re.compile(r"(?<![\w.\-])\d[\d.,]*\s*(%p|%|배|x|×|ms|초|분|시간|개|건|명|GB|MB|KB|TB|토큰|점|회|번)"
                         r"(까지|으로|로)?")
BASELINE_RE = re.compile(
    r"(보다|대비|에\s*비해|비교|이전|기준|대신|원래|기존|당초|종전|[가-힣]던\s|"
    r"[\d.,]+\s*[^\s\d]{0,6}에서\s+(?:약\s+)?[\d.,]+|"  # "1,850ms에서 420ms로"
    r"의\s+(?:최대\s+|약\s+|평균\s+)?[\d.,]+\s*배|"     # "Orca의 1.67배"
    r"(?<![가-힣])전(?:보다|에는|과|의|에)?(?=\s|$))")

# How check classifies status regressions. Items starting with these prefixes are sentence and paragraph distribution
# items. The rest (G, A1~A7, A10~A15, T) are AI style items.
DIST_PREFIX = ("A8.", "A9.", "A16.", "A17.")
RANK = {"PASS": 0, "INFO": 0, "CHECK": 0, "WARN": 1, "FAIL": 2, "GATE": 3}


# ---------------------------------------------------------------- Paths

def stem_of(path):
    base = path[:-3] if path.endswith(".md") else path
    if base.endswith(".draft"):
        base = base[:-len(".draft")]
    return base


def snapshot_path(path):
    return stem_of(path) + SNAPSHOT_SUFFIX


def facts_path(path):
    return stem_of(path) + FACTS_SUFFIX


def repeats_path(path):
    return stem_of(path) + REPEATS_SUFFIX


def mark_path(path):
    return stem_of(path) + MARK_SUFFIX


# ---------------------------------------------------------------- Sentences

def tokens(masked):
    s = L.PH_RE.sub(" ", masked)
    out = []
    for t in s.split():
        t = t.strip(EDGE)
        if t:
            out.append(t)
    return out


def strip_particle(tok):
    for p in PARTICLES:
        if tok.endswith(p) and len(tok) - len(p) >= 2:
            return tok[:-len(p)]
    return tok


def sentence_records(text, include_refs=False):
    """Return the article's narrative sentences in order, each with its heading, section number, whether it is the first sentence of its paragraph, and the type of the preceding block."""
    recs = []
    heading, section, in_refs, prev_type = "", 0, False, "start"
    for bi, b in enumerate(L.parse_blocks(L.normalize_text(text))):
        if b.type == "heading":
            heading = L.clean_inline(b.text)[0]
            in_refs = bool(L.REF_HEADING_RE.search(heading)) and b.level >= 2
            section += 1
            prev_type = "heading"
            continue
        if in_refs and not include_refs:
            continue
        if b.type in ("table", "code", "blockquote", "html"):
            prev_type = b.type
            continue
        if b.type not in ("paragraph", "list_item"):
            continue
        clean, _, _ = L.clean_inline(b.text)
        parts = L.split_sentences(clean)
        for i, s in enumerate(parts):
            masked = L.mask_quotes(s)
            word = L.last_word(s)
            cls = L.classify_ending(word, s.rstrip(L.CLOSERS + " ").endswith("?"))
            if b.type == "list_item" and cls in ("NOUN", "OTHER"):
                continue  # a noun-phrase list item is not a narrative sentence
            recs.append({"line": b.line, "heading": heading, "section": section, "block": bi, "kind": b.type,
                         "first": i == 0, "after": prev_type if i == 0 else "sentence",
                         "text": s, "masked": masked, "toks": tokens(masked), "word": word})
        prev_type = "list" if b.type == "list_item" else "paragraph"
    return recs


def excerpt(s, n=60):
    s = s.strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def fmt_lines(lines, n=6):
    uniq = sorted(set(lines))
    shown = ", ".join(f"L{x}" for x in uniq[:n])
    return shown + (", …" if len(uniq) > n else "")


# ---------------------------------------------------------------- Repeat candidates

def _baseline_keys(rec):
    """Keys of comparison baseline phrases that contain a number. Example: "무작위 추측 정확도 20%보다" → "추측 정확도 20%"."""
    toks = rec["toks"]
    keys = []
    for j, t in enumerate(toks):
        end = None  # position of the last token with the baseline noun attached
        if t.endswith("보다") and len(t) > 2:
            end = j
        elif t == "대비" and j > 0:
            end = j - 1
        elif t.startswith("비해") and j > 0 and toks[j - 1].endswith("에"):
            end = j - 1
        elif t.startswith("비교") and j > 0 and toks[j - 1].endswith(("와", "과")):
            end = j - 1
        if end is None:
            continue
        window = toks[max(0, end - 2):end + 1]
        if not any(L.NUM_RE.search(w) for w in window):
            continue  # a baseline with only a name ("Orca보다") does not count
        norm = [strip_particle(w) for w in window]
        if norm and norm[-1].endswith("에"):
            norm[-1] = norm[-1][:-1]
        keys.append(" ".join(w.lower() for w in norm if w))
    return keys


def find_repeats(text):
    recs = sentence_records(text)
    cands = []

    # R7: adjacent predicate candidates, separate from the ending buckets. Uses the same paragraph boundaries as lint.
    for hit in L.analyze(text)["metrics"]["A8.same_predicate_adjacent"]["hits"]:
        prev = hit["previous"]
        cands.append({"id": "R7", "item": 3, "lines": [prev["line"], hit["line"]],
                      "section": "", "text": prev["text"] + " " + hit["text"],
                      "previous": prev, "predicate": hit["match"],
                      "label": f"인접한 같은 서술어 «{hit['match']}» (문맥 검토)"})

    # R6 amounts of change without a comparison baseline
    for idx, r in enumerate(recs):
        m = r["masked"]
        amounts = [u for u in UNIT_NUM_RE.finditer(m) if u.group(1) == "배" or not u.group(2)]
        if not amounts:
            continue
        if not (CHANGE_RE.search(m) or TIMES_RE.search(m)):
            continue
        if BASELINE_RE.search(m):
            continue
        units = [u.group(1) for u in UNIT_NUM_RE.finditer(m)]
        if len(units) >= 2 and len(set(units)) < len(units):
            continue  # two numbers with the same unit mean the before and after values are both present
        after_block = r["after"] in ("table", "list", "code")
        prev = recs[idx - 1] if idx > 0 and r["after"] in ("sentence", "paragraph") else None
        if prev is not None and BASELINE_RE.search(prev["masked"]):
            continue
        cands.append({"id": "R6", "item": 2, "lines": [r["line"]], "section": r["heading"],
                      "text": r["text"], "after": "표나 목록 뒤" if after_block else "",
                      "label": "비교 기준 없는 변화량" + ("(표나 목록 바로 뒤)" if after_block else "")})

    # R1 the same comparison baseline containing a number
    occ = {}
    for idx, r in enumerate(recs):
        for k in set(_baseline_keys(r)):
            occ.setdefault(k, []).append(idx)
    for k, idxs in occ.items():
        adjacent = sum(1 for a, b in zip(idxs, idxs[1:]) if b == a + 1 and recs[a]["section"] == recs[b]["section"])
        if len(idxs) >= 3 or adjacent >= 1:
            cands.append({"id": "R1", "item": 1, "lines": [recs[i]["line"] for i in idxs], "section": "",
                          "text": recs[idxs[0]]["text"], "key": k, "count": len(idxs), "adjacent": adjacent,
                          "label": f"같은 비교 기준 «{k}» {len(idxs)}문장" + (f", 인접한 문장 {adjacent}쌍" if adjacent else "")})

    # R4 same sentence pattern: a (first word, last word) pair 3 or more times, or the same last word in 3 sentences in a row
    frames = {}
    for idx, r in enumerate(recs):
        toks = r["toks"]
        if len(toks) < 3 or not r["word"]:
            continue
        first = toks[0]
        if first in L.SENT_ADVERBS or r["word"] in GENERIC_PREDICATES:
            continue
        if first in DEMONSTRATIVES and len(toks) > 3:
            first = toks[0] + " " + toks[1]
        frames.setdefault((first, r["word"]), []).append(idx)
    for (first, last), idxs in frames.items():
        if len(idxs) >= 3:
            cands.append({"id": "R4", "item": 3, "lines": [recs[i]["line"] for i in idxs], "section": "",
                          "text": recs[idxs[0]]["text"], "count": len(idxs),
                          "label": f"같은 문형 «{first} … {last}» {len(idxs)}문장"})
    run = [0]
    for idx in range(1, len(recs) + 1):
        if (idx < len(recs) and recs[idx]["word"] and recs[idx]["word"] == recs[run[-1]]["word"]
                and recs[idx]["word"] not in GENERIC_PREDICATES):
            run.append(idx)
            continue
        if len(run) >= 3:
            w = recs[run[0]]["word"]
            cands.append({"id": "R4", "item": 3, "lines": [recs[i]["line"] for i in run], "section": "",
                          "text": recs[run[0]]["text"], "count": len(run),
                          "label": f"같은 서술어 «{w}» {len(run)}문장 연속"})
        run = [idx]

    # R3 3 or more sentences in a row within a section that start with the same subject
    run = []
    for idx in range(len(recs) + 1):
        cur = recs[idx] if idx < len(recs) else None
        key = None
        if cur is not None and cur["toks"] and cur["toks"][0].endswith(SUBJECT_END) and len(cur["toks"][0]) >= 2:
            key = (cur["section"], cur["toks"][0])
        if run and key is not None and key == run[-1][1]:
            run.append((idx, key))
            continue
        if len(run) >= 3:
            cands.append({"id": "R3", "item": 3, "lines": [recs[i]["line"] for i, _ in run], "section": "",
                          "text": recs[run[0][0]]["text"], "count": len(run),
                          "label": f"«{run[0][1][1]}»로 시작하는 문장 {len(run)}개 연속"})
        run = [(idx, key)] if key is not None else []

    # R5 4 or more paragraph sentences in a row within a section that are shorter than 35 characters
    run = []
    for idx in range(len(recs) + 1):
        cur = recs[idx] if idx < len(recs) else None
        if (cur is not None and cur["kind"] == "paragraph" and len(cur["text"]) < SHORT_LEN
                and (not run or recs[run[-1]]["section"] == cur["section"])):
            run.append(idx)
            continue
        if len(run) >= 4:
            cands.append({"id": "R5", "item": 3, "lines": [recs[i]["line"] for i in run], "section": "",
                          "text": recs[run[0]]["text"], "count": len(run),
                          "label": f"{SHORT_LEN}자 미만 문장 {len(run)}개 연속"})
        run = [idx] if cur is not None and cur["kind"] == "paragraph" and len(cur["text"]) < SHORT_LEN else []

    order = {"R6": 0, "R7": 1, "R1": 2, "R4": 3, "R3": 4, "R5": 5}
    cands.sort(key=lambda c: (order[c["id"]], -c.get("count", 1), c["lines"][0]))
    return {"sentences": len(recs), "candidates": cands}


def render_repeats(path, res, show_all=False):
    cands = res["candidates"]
    lines = [f"{SKILL_NAME} repeats | {os.path.basename(path)} | {res['sentences']}문장"]
    if not cands:
        lines.append("반복 후보 없음. 글을 읽으며 적은 부분만 수정한다.")
        return "\n".join(lines)
    lines.append("다시 읽을 부분(판정 아님): 후보마다 이 글의 독자에게 필요한 반복인지 판단한다. "
                 "필요한 반복은 유지한다. 괄호의 번호는 references/revision.md의 \"수정할 부분과 수정 방법\" 항목이다.")
    shown = cands if show_all else cands[:MAX_LINES]
    for c in shown:
        lines.append(f"[{c['id']}] {fmt_lines(c['lines'])} {c['label']} (항목 {c['item']}): «{excerpt(c['text'])}»")
    if len(cands) > len(shown):
        lines.append(f"+{len(cands) - len(shown)}개 (--all로 모두 출력한다)")
    return "\n".join(lines)


# ---------------------------------------------------------------- Before and after comparison

def _blocks_of(text, kind):
    return [b.text.strip() for b in L.parse_blocks(L.normalize_text(text)) if b.type == kind]


def _numbers(text):
    found = {}
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type == "code":
            continue
        s = b.text if b.type == "table" else L.clean_inline(b.text)[0]
        for key, raw in L.extract_numbers(s):
            found.setdefault(key, []).append((b.line, raw))
    return found


def _connectives(masked):
    n = 0
    toks = masked.split()
    for i, tok in enumerate(toks[:-1]):
        base = tok.rstrip(",，").rstrip(L.CLOSERS)
        if i == 0 and base in L.SENT_ADVERBS:
            continue
        if L.is_connective(base):
            n += 1
    return n


def _lint(text, facts_text):
    analysis = L.analyze(text, facts_text=facts_text)
    ev = L.evaluate(analysis, L.load_thresholds(), "default", max_hits=3)
    return analysis, ev


def compare(before, after, facts_text=None):
    pre = [r["text"] for r in sentence_records(before, include_refs=True)]
    post_recs = sentence_records(after, include_refs=True)
    post = [r["text"] for r in post_recs]
    sm = difflib.SequenceMatcher(None, pre, post, autojunk=False)
    kept = changed = written = 0
    new_idx = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            kept += i2 - i1
        else:
            changed += i2 - i1
            written += j2 - j1
            new_idx.extend(range(j1, j2))
    share = round(changed / len(pre), 3) if pre else 0.0

    nb, na = _numbers(before), _numbers(after)
    fact_keys = L.number_set(facts_text) if facts_text else None
    lost = [{"value": k, "count": len(v), "line": v[0][0], "raw": v[0][1]} for k, v in nb.items() if k not in na]
    new = [{"value": k, "line": v[0][0], "raw": v[0][1],
            "in_facts": (k in fact_keys) if fact_keys is not None else None} for k, v in na.items() if k not in nb]

    structure = {
        "headings_same": _blocks_of(before, "heading") == _blocks_of(after, "heading"),
        "code_same": _blocks_of(before, "code") == _blocks_of(after, "code"),
        "tables": [len(_blocks_of(before, "table")), len(_blocks_of(after, "table"))],
        "chars": [L.analyze(before)["stats"]["chars"], L.analyze(after)["stats"]["chars"]],
    }

    _, ev_b = _lint(before, facts_text)
    an_a, ev_a = _lint(after, facts_text)
    st_b = {r["id"]: r["status"] for r in ev_b["results"]}
    worse_ai, worse_dist, bad_now = [], [], []
    for r in ev_a["results"]:
        if r["status"] in ("GATE", "FAIL"):
            bad_now.append(r)
        if RANK.get(r["status"], 0) > RANK.get(st_b.get(r["id"], "PASS"), 0):
            (worse_dist if r["id"].startswith(DIST_PREFIX) else worse_ai).append(r)

    long_new = []
    for j in new_idx:
        r = post_recs[j]
        if _connectives(r["masked"]) >= 3:
            long_new.append({"line": r["line"], "text": r["text"]})

    must_fix = bool(bad_now or worse_ai)
    return {"sentences": [len(pre), len(post)], "kept": kept, "changed": changed, "written": written,
            "changed_share": share, "lost_numbers": lost, "new_numbers": new, "structure": structure,
            "lint_before": ev_b["summary"], "lint_after": ev_a["summary"],
            "worse_ai": worse_ai, "worse_dist": worse_dist, "gate_fail": bad_now, "long_new": long_new,
            "predicate_candidates": an_a["metrics"]["A8.same_predicate_adjacent"]["hits"],
            "must_fix": must_fix}


def _fmt_metric(r):
    out = [f"    [{r['status']}] {r['id']} {r['title']}: {r['value']}"]
    for h in r.get("hits", [])[:3]:
        m = f" «{h['match']}»" if h.get("match") else ""
        out.append(f"        L{h['line']}{m}: {excerpt(h['text'], 80)}")
    return out


def render_check(snap, path, res):
    st = res["structure"]
    lb, la = res["lint_before"], res["lint_after"]
    lines = [f"{SKILL_NAME} check | 초안 복사본 {os.path.basename(snap)} → {os.path.basename(path)}"]
    lines.append(f"문장: 초안 {res['sentences'][0]}문장 중 {res['kept']}문장 그대로, {res['changed']}문장 수정하거나 삭제"
                 f"({res['changed_share'] * 100:.1f}%), 새로 쓴 문장 {res['written']}개")
    if res["changed_share"] > CHANGED_SHARE_RECHECK:
        lines.append(f"    바뀐 문장이 {int(CHANGED_SHARE_RECHECK * 100)}%를 넘었다. 수정한 문장마다 revision.md의 판단 질문에 "
                     "답하는지, korean-review.md의 유형에 해당하는지 다시 확인한다.")
    lines.append(f"본문 글자 수: {st['chars'][0]:,}자 → {st['chars'][1]:,}자")
    lost = res["lost_numbers"]
    if lost:
        lines.append(f"초안에만 있는 수치 {len(lost)}개: 원자료와 일치하는 사실을 유일하게 언급한 수치였으면 복원한다. 근거를 확인한 오류 수정은 유지한다.")
        for x in lost[:8]:
            lines.append(f"    {x['raw']} (초안 L{x['line']}, 초안에서 {x['count']}회)")
    else:
        lines.append("초안에만 있는 수치: 없음")
    new = res["new_numbers"]
    if new:
        lines.append(f"새 수치 {len(new)}개:")
        for x in new[:8]:
            tag = "" if x["in_facts"] is None else (" fact sheet에 있음" if x["in_facts"] else
                                                    " fact sheet에 없음: 계산한 값이면 fact sheet에 적는다(A15)")
            lines.append(f"    {x['raw']} (L{x['line']}){tag}")
    else:
        lines.append("새 수치: 없음")
    lines.append("구조: 헤딩 " + ("같음" if st["headings_same"] else
                                 "바뀜(후처리는 헤딩과 섹션 구성을 바꾸지 않는다. 한국어 문장 점검의 유형 J 수정이면 유지하고 "
                                 "글 안에서 그 헤딩을 가리키는 링크도 함께 수정한다)")
                 + ", 코드 블록 " + ("같음" if st["code_same"] else "바뀜(코드는 바꾸지 않는다)")
                 + f", 표 {st['tables'][0]}개 → {st['tables'][1]}개")
    lines.append(f"lint: 초안 G{lb['gate_fail']} F{lb['fail']} W{lb['warn']} → 후처리 G{la['gate_fail']} F{la['fail']} W{la['warn']}")
    if res["gate_fail"]:
        lines.append("  Gate 위반과 FAIL(수정한다):")
        for r in res["gate_fail"]:
            lines += _fmt_metric(r)
    ai_only = [r for r in res["worse_ai"] if r["status"] not in ("GATE", "FAIL")]
    if ai_only:
        lines.append("  나빠진 AI 문체 항목(수정한다):")
        for r in ai_only:
            lines += _fmt_metric(r)
    if res["worse_dist"]:
        lines.append("  나빠진 문장과 문단의 분포 항목(후처리에서 의도했으면 유지하고 보고에 이유를 적는다):")
        for r in res["worse_dist"]:
            lines += _fmt_metric(r)
    if not (res["gate_fail"] or res["worse_ai"] or res["worse_dist"]):
        lines.append("  나빠진 항목 없음")
    if res["predicate_candidates"]:
        lines.append("  인접한 서술어 반복 후보(자동 수정 아님. 문맥을 읽고 수정하거나, 남긴 이유를 기록한다):")
        for h in res["predicate_candidates"]:
            lines.append(f"    L{h['previous']['line']} → L{h['line']} «{h['match']}»: "
                         f"{h['previous']['text']} {h['text']}")
    if res["long_new"]:
        lines.append(f"연결어미가 3개 이상인 새 문장 {len(res['long_new'])}개(절의 대상과 관계를 검토하고 필요한 문장만 나눈다):")
        for x in res["long_new"][:5]:
            lines.append(f"    L{x['line']}: {excerpt(x['text'], 80)}")
    lines.append("자동 판정: " + ("수정할 항목 있음" if res["must_fix"] else "수정할 항목 없음")
                 + ". 후보의 문맥과 수정 후 단독 읽기는 별도로 확인한다.")
    return "\n".join(lines)


# ---------------------------------------------------------------- Edited sentence check (audit)
#
# Most problems that reviewers found in the post-edit review (the review defined by the skill's workflow documents) were
# in sentences that an earlier edit had newly created. In the 2026-11-02 README work, sentences edited to fix what the
# review flagged were flagged again for these five reasons: conditions were dropped when restating, a reason or causal
# link absent from the fact sheet was added, a demonstrative or a single name pointed at two targets, splitting or merging
# sentences made the subject and predicate mismatch, and other lines stating the same fact were not edited. For each edited
# sentence, audit shows where to check these five things. It makes no verdict.

# Words whose target depends on the previous sentence or on when the article is read. Forms with a particle attached
# ("이는", "지금은") also count.
DEICTIC_WORDS = ("이", "그", "저", "이런", "그런", "이러한", "그러한", "이렇게", "그렇게", "해당", "이때", "그때",
                 "이것", "그것", "이들", "그들", "여기", "거기", "이번", "지금", "현재", "최근", "새", "새로운", "새롭게",
                 "기존", "이전", "당시")
RELATIVE_TIME = ("이번", "지금", "현재", "최근", "새", "새로운", "새롭게", "기존", "이전", "당시")
DEICTIC_TAILS = ("", "은", "는", "이", "가", "을", "를", "의", "에", "에서", "에는", "에서는", "에도", "으로", "로",
                 "와", "과", "도", "만", "부터", "까지", "처럼", "보다")
# Words that point to a position in the article. Uses that state the order of actions, like "모은 뒤", are excluded. These
# words count only before the name of an article unit or in a form that points to a position, like "위의" or "다음과".
POSITION_WORDS = ("위", "앞", "뒤", "아래", "다음")
POSITION_FORMS = ("위의", "앞의", "뒤의", "아래의", "위에서", "앞에서", "앞서", "다음과", "다음은", "아래와", "위와")
DOC_NOUNS = ("절", "문단", "문장", "표", "그림", "목록", "단계", "예", "예시", "코드", "식", "장", "항목", "글", "결과",
             "설명", "내용", "부분", "방법", "실험", "측정", "값", "수치", "정의", "질문", "사례")
FORWARD_WORDS = ("아래", "다음")
NUMERAL_DET = ("두", "세", "네")  # words like "두 값" and "세 항목" that refer back to targets counted earlier
COUNTERS = ("개", "편", "곳", "가지", "번", "명", "건", "줄", "문장", "단계", "차례", "쌍", "종", "회", "배", "글자",
            "자", "쪽", "장", "권")
# List used to strip particles more broadly (only when measuring the length of one-word expressions).
EXTRA_PARTICLES = ("이나", "이라는", "라는", "이란", "이며", "이고", "으로서", "로서", "으로써", "로써", "에게", "한테",
                   "이라고", "라고", "이라", "이든", "마저", "조차", "밖에", "도", "만", "나", "란")
# Markers of reason and purpose. "~어서" and "~아서" are found by _causal_seo below.
CAUSAL_RE = re.compile(r"때문|덕분|탓에|탓으로|인해|인한|그래서|따라서|그러므로|결과적으로|므로|니까|느라|도록|위해|려고|목적(?!어)")
SEO_NONCAUSAL = ("위해서", "대해서", "통해서", "의해서", "관해서", "비해서", "따라서", "에서", "께서", "부터서")
LEFTOVER_MAX_UNITS = 6  # a pre-edit expression found in more units than this is treated as common and not shown
# Words that set scope, frequency, or bounds. They are easily dropped or widened when restating.
SCOPE_EXACT = ("모두", "모든", "전부", "전체", "항상", "언제나", "늘", "대부분", "오직", "유일", "가운데", "중", "각",
               "이상", "이하", "미만", "초과", "등")
SCOPE_ENDS = ("처럼", "부터", "까지", "마다", "로만", "에만", "에서만", "만으로", "뿐")
# Nouns ending in "과" or "와". The "과" or "와" in these words is not a listing particle.
COORD_NOUN_END = ("결과", "효과", "성과", "통과", "초과", "경과", "학과", "사과", "부과", "교과")
GA_NOUNS = ("평가", "추가", "증가", "대가", "단가", "원가", "주가", "전문가", "작가", "국가", "휴가", "부가", "참가",
            "허가")
I_WORDS = ("같이", "많이", "높이", "깊이", "길이", "넓이", "없이", "굳이", "차이", "사이", "나이", "아이", "일일이",
           "낱낱이", "똑같이", "깨끗이")
PRED_LIKE_RE = re.compile(r"(?:니다|다|요|고|며|서|면|지만|는데|도록|게|던|은|는|한|된|할|될|인|운|른)$")
FACT_SCORE_MIN = 8.0


def audit_units(text):
    """Comparison units: headings, table rows, and the sentences of paragraphs, list items, and blockquotes. Noun-phrase list items are included. Code and HTML are excluded.
    text is the sentence with inline code restored, and clean is the sentence lint sees (inline code is a placeholder)."""
    units = []
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type in ("code", "html"):
            continue
        parts = []
        if b.type == "heading":
            clean, _, codes = L.clean_inline(b.text)
            parts.append((b.line, "헤딩", clean, codes))
        elif b.type == "table":
            for k, row in enumerate(b.text.split("\n")):
                if row.strip() and not L.TABLE_DELIM_RE.match(row):
                    clean, _, codes = L.clean_inline(row)
                    parts.append((b.line + k, "표", clean, codes))
        else:
            clean, _, codes = L.clean_inline(b.text)
            rest = list(codes)
            kind = {"list_item": "목록", "blockquote": "인용"}.get(b.type, "문장")
            for s in L.split_sentences(clean) or [clean]:
                n = s.count(L.PH_CODE)
                parts.append((b.line, kind, s, rest[:n]))
                rest = rest[n:]
        for line, kind, clean, codes in parts:
            shown = clean
            for c in codes:
                shown = shown.replace(L.PH_CODE, "`" + c + "`", 1)
            masked = L.mask_quotes(clean)
            toks = tokens(masked)
            main = L.PAREN_RE.sub(" ", masked)
            units.append({"line": line, "kind": kind, "clean": clean, "text": shown, "masked": masked,
                          "toks": toks, "keys": [strip_particle(t).lower() for t in toks],
                          "toks_main": tokens(main), "raw_main": L.PH_RE.sub(" ", main).split(),
                          "words": _words(masked)})
    return units


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-_.]*|[가-힣]+")
# Endings stripped to reduce conjugated verbs and adjectives to a noun stem. "측정했습니다" and "측정" count as the same word.
STEM_END_RE = re.compile(r"(?:했습니다|합니다|했고|하고|하는|하며|하면|하기|해서|해야|하지|한다|했다|하여|됐습니다|됩니다|"
                         r"되는|되고|되어|됐고|된|될|한|할|해)$")
ADVERBS = ("잘못", "다시", "먼저", "모두", "함께", "가장", "아직", "이미", "바로", "따로", "서로", "거의", "정도", "대부분",
           "그대로", "처음", "직접", "주로", "새로", "모든", "같은", "다른", "여러", "어떤", "아래", "위", "앞", "뒤", "다음")


def _stem(word):
    m = STEM_END_RE.search(word)
    if m and len(word) - len(m.group(0)) >= 2:
        return word[:m.start()]
    return word


def _words(masked):
    """Extract words from text without quotes and inline code, and return them as (original form, comparison form). The comparison form is lowercased,
    with particles and endings like "~했습니다" stripped. Parentheses count as word separators ("도입(H2로" → "도입", "H2로")."""
    out = []
    for raw in WORD_RE.findall(L.PH_RE.sub(" ", masked)):
        out.append((raw, _stem(_bare(raw.lower()))))
    return out


VERSION_RE = re.compile(r"(?<![\d.])\d+\.\d+\.\d+(?![\d.])")


def _audit_numbers(text):
    """List of numbers, excluding version numbers ("0.2.0") and source locations ("22~35줄")."""
    return L.extract_numbers(LOCATION_REF_RE.sub(" ", VERSION_RE.sub(" ", text)))


BARE_PARTICLES = sorted(set(PARTICLES) | set(EXTRA_PARTICLES), key=len, reverse=True)


def _bare(tok):
    """Strip one particle, including from one-character nouns ("글은", "수가")."""
    for p in BARE_PARTICLES:
        if tok.endswith(p) and len(tok) > len(p):
            return tok[:-len(p)]
    return tok


def _adnominal(tok):
    """Whether the token is a form that modifies the next noun, like "모은", "측정한", "여는", "쓰던". Nouns ending in the final consonant ㄴ also match."""
    if not tok or not L.HANGUL_RE.match(tok[-1]):
        return False
    return tok.endswith(("는", "던")) or L._jong(tok[-1]) == 4


def _clean_toks(toks):
    return [t.strip(EDGE).rstrip(",，") for t in toks]


def deictics_in(toks):
    clean = _clean_toks(toks)
    found = []
    for i, t in enumerate(clean):
        nxt = _bare(clean[i + 1]) if i + 1 < len(clean) else ""
        prev = clean[i - 1] if i > 0 else ""
        if t in NUMERAL_DET:
            if nxt and not nxt.startswith(COUNTERS):
                found.append(t)
            continue
        if t in POSITION_FORMS:
            found.append(t)
            continue
        if t in POSITION_WORDS:
            if not _adnominal(prev) and nxt in DOC_NOUNS:
                found.append(t)
            continue
        for w in DEICTIC_WORDS:
            if t.startswith(w) and t[len(w):] in DEICTIC_TAILS:
                found.append(t)
                break
    return list(dict.fromkeys(found))


def _causal_seo(tok):
    """A "~아서/~어서" that connects a reason, like "늘어서", "없어서", "나와서". Excludes "면서", "에서", "위해서"."""
    if len(tok) < 2 or not tok.endswith("서") or tok.endswith(SEO_NONCAUSAL) or tok.endswith("면서"):
        return False
    prev = tok[-2]
    return bool(L.HANGUL_RE.match(prev)) and L._jong(prev) == 0 and L._jung(prev) in L.SEO_VOWELS


def causal_in(masked, toks):
    found = [m.group(0) for m in CAUSAL_RE.finditer(L.PH_RE.sub(" ", masked))]
    found += [t for t in _clean_toks(toks) if _causal_seo(t)]
    return list(dict.fromkeys(found))


def scope_in(toks):
    found = []
    for t in toks:
        base = t.strip(EDGE).rstrip(",，")
        key = strip_particle(base)
        if key in SCOPE_EXACT or base in SCOPE_EXACT or (base.startswith("등") and base[1:] in DEICTIC_TAILS):
            found.append(key if key in SCOPE_EXACT else base)
        elif base.endswith(SCOPE_ENDS) or "뿐" in base:
            found.append(base)
    return list(dict.fromkeys(found))


def _role(tok):
    if len(tok) >= 2 and tok.endswith(("을", "를")):
        return "목적어"
    if len(tok) >= 2 and tok.endswith("가") and not tok.endswith(GA_NOUNS):
        return "주어"
    if tok.endswith("이") and tok not in I_WORDS and not tok.endswith(I_WORDS) and (
            len(tok) >= 3 or (len(tok) == 2 and L._jong(tok[0]) != 0)):
        return "주어"
    return None


def coordinated(toks):
    """Places like "A와 … B가(를)" where one predicate takes two or more subjects or objects, along with that predicate. B is searched for within six words after A."""
    out = []
    clean = _clean_toks(toks)
    i = 0
    while i < len(clean) - 1:
        t = clean[i]
        if len(t) >= 2 and t.endswith(("과", "와")) and not t.endswith(COORD_NOUN_END):
            for k in range(i + 1, min(len(clean), i + 7)):
                role = _role(clean[k])
                if role:
                    pred = next((clean[m] for m in range(k + 1, len(clean))
                                 if L.is_connective(clean[m]) or m == len(clean) - 1), "")
                    out.append({"role": role, "first": t, "head": clean[k], "predicate": pred})
                    i = k
                    break
                if L.is_connective(clean[k]):
                    break
        i += 1
    return out


FINAL_ENDINGS = ("다", "요", "까", "기", "음")
# Endings of forms that modify a noun. "인", "간", "본" are left out because they overlap with nouns ending in the final
# consonant ㄴ ("원인", "확인", "기간", "복사본").
ADNOMINAL_ENDS = ("는", "던", "한", "된", "할", "될", "든", "른", "운", "쓴", "친", "진", "난", "온")
# Forms ending in particles that look like predicate endings ("보다", "와", "가")
PARTICLE_ENDS = ("에서", "께서", "보다", "부터", "까지", "처럼", "마다", "에다", "에게", "한테")


def _verb_form(tok):
    """Whether the token is a predicate form: a word ending in an ending that closes or connects a sentence, a form that modifies a noun, "~기", or "~아/~어"."""
    if len(tok) < 2 or not L.HANGUL_RE.match(tok[-1]) or tok.endswith(PARTICLE_ENDS):
        return False
    if tok.endswith(FINAL_ENDINGS) or L.is_connective(tok) or tok.endswith(ADNOMINAL_ENDS):
        return True
    if tok.endswith(("와", "과", "가", "나")):
        return False  # the particles "와", "과", "가", "나" are not the "~아" form even though they end in the vowels ㅏ or ㅘ
    return L._jong(tok[-1]) == 0 and L._jung(tok[-1]) in L.SEO_VOWELS


def object_verbs(toks):
    """Pairs of an object (~을, ~를) and the first predicate-form word after it. Also shows the one word before the object."""
    clean = _clean_toks(toks)
    out = []
    for i, t in enumerate(clean):
        if _role(t) != "목적어":
            continue
        verb = next((clean[k] for k in range(i + 1, min(len(clean), i + 5)) if _verb_form(clean[k])), "")
        if verb:
            head = (clean[i - 1] + " " if i > 0 and not _verb_form(clean[i - 1]) and _role(clean[i - 1]) is None
                    else "") + t
            out.append({"object": head, "verb": verb})
    return out


def list_items(raw_toks):
    """Number of comma-separated items. Counts only commas after words outside parentheses, not commas after connective endings. Returns the count only when there are two or more commas."""
    n = 0
    for t in raw_toks:
        if t.endswith((",", "，")):
            base = t.rstrip(",，").strip(EDGE)
            if base and not L.is_connective(base):
                n += 1
    return n + 1 if n >= 2 else 0


def _mention_candidate(raw, norm):
    """Whether a word should be shown as a first mention. Filters out predicate forms and adverbs using the particle-stripped form norm ("기준치는" counts as "기준치")."""
    if len(norm) < 2 or norm in ADVERBS or raw in ADVERBS:
        return False
    if re.fullmatch(r"[가-힣]+", norm):
        return not (_verb_form(norm) or norm.endswith(("지", "게", "도록", "려", "며", "고")))
    return True


def first_mentions(units, idx, limit=8):
    """Words in units[idx] that never appear in earlier units of the article. Excludes predicate forms, adverbs, and one-character words."""
    seen = set()
    for u in units[:idx]:
        seen.update(norm for _, norm in u["words"])
    out = []
    for raw, norm in units[idx]["words"]:
        if norm in seen or norm in out or not _mention_candidate(raw, norm):
            continue
        out.append(norm)
    return out[:limit]


SECTION_REF_RE = re.compile(r"[\"“]([^\"”]{2,40})[\"”]\s*절")


def section_refs(units, idx):
    """Places that refer to another section as "…" 절. Returns the line range of that section and the words in this unit that do not appear in it."""
    u = units[idx]
    out = []
    heads = [(j, x) for j, x in enumerate(units) if x["kind"] == "헤딩"]
    for m in SECTION_REF_RE.finditer(u["clean"]):
        name = m.group(1).strip()
        hit = next(((j, x) for j, x in heads if x["text"].strip() == name), None)
        if hit is None:
            out.append({"name": name, "lines": None, "missing": []})
            continue
        j, h = hit
        nxt = next((k for k, _ in heads if k > j), len(units))
        in_section = set()
        for x in units[j:nxt]:
            in_section.update(norm for _, norm in x["words"])
        own = {norm for _, norm in _words(name)} | {"절"}
        missing = []
        for raw, norm in u["words"]:
            if norm in in_section or norm in own or norm in missing or not _mention_candidate(raw, norm):
                continue
            missing.append(norm)
        out.append({"name": name, "lines": [h["line"], units[nxt - 1]["line"]], "missing": missing[:8]})
    return out


def _content_keys(text):
    keys = set()
    for t in tokens(text):
        k = strip_particle(t).lower()
        if len(k) >= 2 and re.search(r"[가-힣A-Za-z]", k) and not PRED_LIKE_RE.search(k):
            keys.add(k)
    return keys


LOCATION_REF_RE = re.compile(r"\d[\d,]*(?:\s*[~\-–]\s*\d[\d,]*)?\s*(?:줄|쪽|행|절|페이지)")


def facts_rows(facts_text):
    """Numbers and content words for each fact sheet line. Excludes table delimiter rows and blank lines. Digits in source locations ("22~35줄", "8쪽") do not count as numbers."""
    rows = []
    for n, line in enumerate(facts_text.split("\n"), 1):
        if not line.strip() or L.TABLE_DELIM_RE.match(line):
            continue
        clean = L.clean_inline(line)[0]
        rows.append({"n": n, "text": line.strip(), "nums": {k for k, _ in _audit_numbers(clean)},
                     "keys": _content_keys(clean)})
    df = {}
    for r in rows:
        for k in r["keys"] | {"#" + x for x in r["nums"]}:
            df[k] = df.get(k, 0) + 1
    return rows, df


def _idf(df, key, total):
    return math.log((total + 1) / (df.get(key, 0) + 1))


def fact_candidates(unit, rows, df, top=2):
    """Fact sheet lines that share this sentence's numbers or rare words. Selects only lines that share at least one number or whose word score passes the threshold."""
    nums = {k for k, _ in _audit_numbers(unit["clean"])}
    keys = _content_keys(unit["clean"])
    total = len(rows)
    scored = []
    for r in rows:
        shared_n = nums & r["nums"]
        shared_k = keys & r["keys"]
        score = sum(2 + _idf(df, "#" + x, total) for x in shared_n) + sum(_idf(df, k, total) for k in shared_k)
        if shared_n or score >= FACT_SCORE_MIN:
            scored.append((score, r, shared_n))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, r, shared_n in scored[:top]:
        text = r["text"]
        pos = 0
        for raw in sorted((raw for k, raw in L.extract_numbers(text) if k in shared_n), key=len, reverse=True):
            pos = max(0, text.find(raw))
            break
        start = max(0, pos - 90)
        snippet = ("…" if start else "") + text[start:start + 200] + ("…" if start + 200 < len(text) else "")
        out.append({"line": r["n"], "text": snippet})
    return out


def _numbers_by_line(text):
    """Number positions for audit: lint_ko's number extraction without version numbers and source locations."""
    found = {}
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type == "code":
            continue
        s = b.text if b.type == "table" else L.clean_inline(b.text)[0]
        for key, raw in _audit_numbers(s):
            found.setdefault(key, []).append((b.line, raw))
    return found


def _find_phrase(units, phrase, skip):
    n = len(phrase)
    hits = []
    for idx, u in enumerate(units):
        if idx in skip:
            continue
        ks = u["keys"]
        if any(ks[p:p + n] == phrase for p in range(len(ks) - n + 1)):
            hits.append(idx)
    return hits


def removed_phrases(old_units, new_units):
    """Expressions found only in the pre-edit sentences. Breaks at predicate-form words and returns two-word pairs and single words (words containing Latin letters or digits,
    words of three or more characters after stripping particles, and time words like "이번" and "기존")."""
    gone = set(k for u in old_units for k in u["keys"]) - set(k for u in new_units for k in u["keys"])
    out = []
    for u in old_units:
        run = []
        for k in u["keys"] + [None]:
            if k is not None and k in gone and not PRED_LIKE_RE.search(k):
                run.append(k)
                continue
            for a, b in zip(run, run[1:]):
                out.append([a, b])
            for a in run:
                bare = _bare(a)
                if re.search(r"[A-Za-z0-9]", a) or len(bare) >= 3 or bare in RELATIVE_TIME:
                    out.append([a])
            run = []
    uniq = []
    for p in out:
        if p not in uniq:
            uniq.append(p)
    return uniq


def defined_names(unit):
    """Names written directly before a parenthesis in the form "이름(설명)". Up to five words before the parenthesis count as the name, stopping at a word with a comma attached
    or at a predicate that closes or connects a sentence. Return value: (list of name words, text in the parentheses)."""
    out = []
    s = unit["clean"]
    for m in re.finditer(r"\(([^()]{2,120})\)", s):
        before = s[:m.start()]
        if not before or before[-1] in " \t":
            continue
        # Restart the name after inline code or a quote ("`lint_ko.py`는 부정 대구(" → "부정 대구").
        raw = [t for t in L.PH_RE.split(L.mask_quotes(before))[-1].split() if t not in PARTICLES]
        keys = []
        for t in reversed(raw[-5:]):
            if t.endswith((",", "，", ".", ":", ";")) and keys:
                break
            w = t.strip(EDGE)
            if not w or (keys and L.is_connective(w)) or re.search(r"(?:니다|요)$", w):
                break
            keys.append(strip_particle(w).lower())
        keys.reverse()
        # A phrase ending in a quantity, like "두 개(…)", is not a name.
        if len(keys) >= 2 and not PRED_LIKE_RE.search(keys[-1]) and keys[-1] not in COUNTERS:
            out.append((keys, m.group(1).strip()))
    return out


def name_overlaps(units, idx):
    """Other definitions (with different text in the parentheses) that have the same last word as a name defined in units[idx] and share two or more words with it."""
    found = []
    mine = defined_names(units[idx])
    if not mine:
        return found
    for j, u in enumerate(units):
        if j == idx:
            continue
        for keys, paren in mine:
            for okeys, oparen in defined_names(u):
                if okeys[-1] == keys[-1] and len(set(keys) & set(okeys)) >= 2 and oparen != paren:
                    found.append({"name": " ".join(keys), "line": u["line"], "kind": u["kind"],
                                  "other": " ".join(okeys), "paren": excerpt(oparen, 60)})
    return found


def audit(before, after, facts_text=None):
    pre, post = audit_units(before), audit_units(after)
    sm = difflib.SequenceMatcher(None, [u["text"] for u in pre], [u["text"] for u in post], autojunk=False)
    opcodes = [op for op in sm.get_opcodes() if op[0] != "equal"]
    changed = set()
    for _, _, _, j1, j2 in opcodes:
        changed.update(range(j1, j2))
    nums_after = _numbers_by_line(after)
    rows, df = facts_rows(facts_text) if facts_text else ([], {})
    groups = []
    for op, i1, i2, j1, j2 in opcodes:
        old, new_idx = pre[i1:i2], list(range(j1, j2))
        g = {"op": op, "old_lines": sorted({u["line"] for u in old}), "old_count": len(old),
             "new_count": len(new_idx), "items": [], "leftover": [], "next": None}
        for j in new_idx:
            u = post[j]
            prev = post[j - 1] if j > 0 else None
            item = {"line": u["line"], "kind": u["kind"], "text": u["text"],
                    "previous": None if prev is None else {"line": prev["line"], "text": prev["text"],
                                                           "changed": (j - 1) in changed},
                    "deictic": deictics_in(u["toks"]), "causal": causal_in(u["masked"], u["toks"]),
                    "scope": scope_in(u["toks"]), "coordinated": coordinated(u["toks_main"]),
                    "objects": object_verbs(u["toks_main"]), "list_items": list_items(u["raw_main"]),
                    "first_mentions": first_mentions(post, j), "section_refs": section_refs(post, j),
                    "split": op == "replace" and len(new_idx) > len(old) and j != j1,
                    "merged": op == "replace" and len(new_idx) < len(old)}
            if any(d.startswith(FORWARD_WORDS) for d in item["deictic"]) and j + 1 < len(post):
                item["following"] = {"line": post[j + 1]["line"], "kind": post[j + 1]["kind"],
                                     "text": post[j + 1]["text"]}
            nums = []
            for key, raw in _audit_numbers(u["clean"]):
                if any(x["value"] == key for x in nums):
                    continue
                others = [ln for ln, _ in nums_after.get(key, []) if ln != u["line"]]
                in_facts = [r["n"] for r in rows if key in r["nums"]]
                nums.append({"value": key, "raw": raw, "lines": others, "facts": in_facts})
            item["numbers"] = nums
            item["facts"] = fact_candidates(u, rows, df) if rows else []
            item["names"] = name_overlaps(post, j)
            g["items"].append(item)
        skip = set(new_idx)
        for phrase in removed_phrases(old, [post[j] for j in new_idx]):
            hits = _find_phrase(post, phrase, skip)
            if hits and len(hits) <= LEFTOVER_MAX_UNITS:
                g["leftover"].append({"phrase": " ".join(phrase),
                                      "where": [{"line": post[h]["line"], "kind": post[h]["kind"]} for h in hits]})
        if j2 < len(post) and j2 not in changed and new_idx:
            g["next"] = {"line": post[j2]["line"], "text": post[j2]["text"]}
        groups.append(g)

    an_a = L.analyze(after, facts_text=facts_text)
    lint_hits = []
    changed_clean = {(post[j]["line"], post[j]["clean"][:160]) for j in changed}
    for mid, m in an_a["metrics"].items():
        if mid.startswith(DIST_PREFIX) and mid != "A8.same_predicate_adjacent":
            continue
        for h in m.get("hits", []):
            if (h.get("line"), h.get("text", "")) in changed_clean:
                lint_hits.append({"id": mid, "line": h["line"], "match": h.get("match", "")})
    cmp = compare(before, after, facts_text)
    return {"units": [len(pre), len(post)], "changed": len(changed), "groups": groups, "lint_hits": lint_hits,
            "lint_before": cmp["lint_before"], "lint_after": cmp["lint_after"], "gate_fail": cmp["gate_fail"],
            "worse_ai": cmp["worse_ai"], "worse_dist": cmp["worse_dist"], "must_fix": cmp["must_fix"]}


# The questions the post-edit reviewer asks for each changed sentence. They are placed at the top of the output so that
# the person who made the edit answers the same questions first. The parentheses name the output lines to look at when
# answering that question.
AUDIT_GUIDE = (
    "확인할 것(판정 아님). 바뀐 단위마다 수정 후 검토자가 묻는 아래 질문에 먼저 답한다. 답할 수 없으면 그 단위를 수정한 뒤 "
    "audit를 다시 실행한다.",
    "  T 대상: 구절과 지시어가 가리키는 자료, 절차, 결과를 이 문장이나 앞 문장, 가리킨 섹션, 글이 링크한 문서에서 찾을 수 "
    "있는가. 글에서 처음 나오는 단어는 독자가 그 위치에서 무엇인지 알 수 있는가(앞 문장, 지시어, 처음 나오는 단어, 섹션 참조)",
    "  F 주어와 목적어: 절마다 누가 무엇을 하는지 이 문장에서 답할 수 있는가. 나눈 문장은 앞 문장의 주어와 조건을 "
    "이어받는가(앞 문장)",
    "  C 서술어: 서술어마다 주어와 목적어를 붙여 읽으면 무슨 일이 일어났다는 의미인지 한 가지로 답할 수 있는가"
    "(목적어와 서술어, 공유 서술어)",
    "  X 사실: 값, 조건(모집단, 기간, 제외한 것과 예외, 판단 기준), 이유, 범위가 근거 후보 행과 그 행의 자료 원문과 같은가. "
    "글의 표현이 원문보다 강하거나 넓지 않은가(후보를 근거로, 일부를 전체로). 합계에 붙인 이름이 합계의 모든 항목에 맞는가. "
    "나열과 \"무엇이 바뀌었다\"처럼 여러 항목을 한꺼번에 가리키는 표현은 원문 목록과 한 항목씩 대조했는가. 일부만 다뤘다면 예시임을 밝혔는가"
    "(수치, 근거 후보, 이유·목적, 범위, 나열, 공유 서술어)",
    "  같은 사실: 같은 수치, 같은 이름, 수정 전 표현을 사용한 다른 줄도 같은 대상과 조건을 말하는가. 한 이름이 두 대상을 "
    "가리키지 않는가(수치, 수정 전 표현, 이름이 겹치는 정의)",
    "  S 반복: 바뀐 문장과 인접한 문장이 같은 서술어나 같은 문형으로 이어져 읽는 흐름을 끊지 않는가(앞 문장, 뒤 문장)",
)


def _q(text, n=None):
    return f"«{text if n is None else excerpt(text, n)}»"


def render_audit(base, path, res):
    lines = [f"{SKILL_NAME} audit | 기준 {os.path.basename(base)} → {os.path.basename(path)} | "
             f"단위 {res['units'][0]}개 → {res['units'][1]}개, 바뀌거나 새로 쓴 단위 {res['changed']}개, "
             f"바뀐 부분 {len(res['groups'])}개"]
    if not res["groups"]:
        lines.append("바뀐 문장 없음")
    else:
        lines.extend(AUDIT_GUIDE)
    for gi, g in enumerate(res["groups"], 1):
        if g["op"] == "insert":
            head = f"추가: {g['new_count']}단위"
        elif g["op"] == "delete":
            head = f"삭제: 기준 {fmt_lines(g['old_lines'])}의 {g['old_count']}단위"
        else:
            head = f"수정: 기준 {fmt_lines(g['old_lines'])}의 {g['old_count']}단위 → {g['new_count']}단위"
        lines.append(f"[{gi}] {head}")
        for it in g["items"]:
            lines.append(f"  L{it['line']} {it['kind']}: {_q(it['text'])}")
            pv = it["previous"]
            if pv is not None and not pv["changed"]:
                lines.append(f"    앞 문장 L{pv['line']}: {_q(pv['text'], 160)}")
            notes = []
            if it["split"]:
                notes.append("한 문장을 나눈 문장 중 뒤 문장이다. 앞 문장에만 있는 주어와 조건을 이 문장이 이어받는지 확인한다")
            if it["merged"]:
                notes.append("여러 문장을 합친 문장이다. 합친 주어 모두에 서술어가 맞는지 확인한다")
            for n in notes:
                lines.append(f"    {n}")
            if it["deictic"]:
                lines.append("    지시어: " + ", ".join(_q(d) for d in it["deictic"]))
            if it["first_mentions"]:
                lines.append("    처음 나오는 단어: " + ", ".join(_q(w) for w in it["first_mentions"]))
            for ref in it["section_refs"]:
                if ref["lines"] is None:
                    lines.append(f"    섹션 참조 «{ref['name']}»: 글에 그런 이름의 헤딩이 없다")
                else:
                    miss = (" / 그 섹션에 없는 단어: " + ", ".join(_q(w) for w in ref["missing"])) if ref["missing"] else ""
                    lines.append(f"    섹션 참조 «{ref['name']}»: L{ref['lines'][0]}~L{ref['lines'][1]}{miss}")
            if it.get("following"):
                fw = it["following"]
                lines.append(f"    뒤 단위 L{fw['line']} {fw['kind']}: {_q(fw['text'], 100)}")
            for x in it["numbers"]:
                where = []
                if x["lines"]:
                    where.append("글 " + fmt_lines(x["lines"]))
                if x["facts"]:
                    where.append("fact sheet " + ", ".join(str(n) for n in x["facts"][:6])
                                 + ("…" if len(x["facts"]) > 6 else "") + "줄")
                lines.append(f"    수치 {x['raw']}: " + (" / ".join(where) if where else "다른 위치 없음"))
            for f in it["facts"]:
                lines.append(f"    근거 후보 fact sheet {f['line']}줄: {_q(f['text'])}")
            if it["causal"]:
                lines.append("    이유·목적: " + ", ".join(_q(c) for c in it["causal"]))
            if it["scope"]:
                lines.append("    범위: " + ", ".join(_q(s) for s in it["scope"]))
            if it["list_items"]:
                lines.append(f"    나열: 쉼표로 나열한 항목 {it['list_items']}개")
            if it["objects"]:
                lines.append("    목적어와 서술어: " + ", ".join(f"«{o['object']} → {o['verb']}»" for o in it["objects"]))
            for c in it["coordinated"]:
                lines.append(f"    공유 서술어({c['role']}): «{c['first']} … {c['head']}» → «{c['predicate']}»")
            for nm in it["names"]:
                lines.append(f"    이름이 겹치는 정의 L{nm['line']}({nm['kind']}): «{nm['other']}({nm['paren']})» "
                             f"/ 이 문장 «{nm['name']}»")
        for lo in g["leftover"]:
            where = ", ".join(f"L{w['line']}({w['kind']})" for w in lo["where"])
            lines.append(f"  수정 전 표현 «{lo['phrase']}»이 남은 위치: {where}")
        if g["next"]:
            lines.append(f"  뒤 문장(변경 없음) L{g['next']['line']}: {_q(g['next']['text'], 160)}")
    if res["lint_hits"]:
        lines.append("바뀐 문장에서 lint가 검출한 표현:")
        for h in res["lint_hits"]:
            m = f" «{h['match']}»" if h["match"] else ""
            lines.append(f"    L{h['line']} {h['id']}{m}")
    lb, la = res["lint_before"], res["lint_after"]
    lines.append(f"lint: 기준 G{lb['gate_fail']} F{lb['fail']} W{lb['warn']} → 지금 G{la['gate_fail']} F{la['fail']} W{la['warn']}")
    worse = [r for r in res["worse_ai"] + res["worse_dist"]]
    for r in res["gate_fail"]:
        lines += _fmt_metric(r)
    for r in worse:
        if r not in res["gate_fail"]:
            lines += _fmt_metric(r)
    return "\n".join(lines)


# ---------------------------------------------------------------- Commands

def cmd_start(args):
    snap = snapshot_path(args.article)
    if os.path.exists(snap) and not args.force:
        print(f"초안 복사본이 이미 있습니다: {snap}. 후처리를 처음부터 다시 하려면 --force를 붙입니다.", file=sys.stderr)
        return 2
    shutil.copyfile(args.article, snap)
    mp = mark_path(args.article)
    if os.path.exists(mp):
        os.remove(mp)  # the pre-fix copy from the previous post-processing run. If kept, audit would use it as the base.
        print(f"이전 후처리의 수정 전 복사본을 삭제했습니다: {mp}")
    text = L.read_text(args.article)
    st = L.analyze(text)["stats"]
    rp = repeats_path(args.article)
    with open(rp, "w", encoding="utf-8") as f:
        f.write(render_repeats(args.article, find_repeats(text)) + "\n")
    print(f"초안 복사본: {snap} ({st['sentences']}문장, {st['chars']:,}자). 후처리는 {args.article}을 수정한다.")
    print(f"반복 후보 파일: {rp}. 글을 처음부터 끝까지 읽으면서 멈추게 되는 부분을 적은 뒤에 이 파일을 연다.")
    return 0


def cmd_mark(args):
    mp = mark_path(args.article)
    shutil.copyfile(args.article, mp)
    st = L.analyze(L.read_text(args.article))["stats"]
    print(f"수정 전 복사본: {mp} ({st['sentences']}문장). 수정한 뒤 audit를 실행하면 이 복사본과 비교한다.")
    return 0


def cmd_audit(args):
    if args.base:
        base = args.base
    elif os.path.isfile(mark_path(args.article)):
        base = mark_path(args.article)
    else:
        base = snapshot_path(args.article)
    if not os.path.isfile(base):
        print(f"비교할 복사본이 없습니다: {base}. 수정하기 전에 mark를 실행하거나 --base로 수정 전 글을 지정합니다.",
              file=sys.stderr)
        return 2
    if args.out and os.path.abspath(args.out) in (os.path.abspath(args.article), os.path.abspath(base)):
        print(f"--out에는 글이나 비교할 복사본이 아닌 새 파일 경로를 지정합니다: {args.out}", file=sys.stderr)
        return 2
    fp = args.facts or facts_path(args.article)
    facts_text = L.read_text(fp) if os.path.isfile(fp) else None
    res = audit(L.read_text(base), L.read_text(args.article), facts_text)
    if args.json:
        slim = dict(res)
        for k in ("worse_ai", "worse_dist", "gate_fail"):
            slim[k] = [{"id": r["id"], "status": r["status"], "value": r["value"]} for r in res[k]]
        out = json.dumps(dict(slim, file=args.article, base=base, facts=fp if facts_text else None),
                         ensure_ascii=False, indent=1)
    else:
        out = render_audit(base, args.article, res)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"audit 결과: {args.out} (바뀌거나 새로 쓴 단위 {res['changed']}개, 바뀐 부분 {len(res['groups'])}개)")
    else:
        print(out)
    return 1 if res["must_fix"] else 0


def cmd_repeats(args):
    res = find_repeats(L.read_text(args.article))
    if args.json:
        print(json.dumps(dict(res, file=args.article), ensure_ascii=False, indent=1))
    else:
        print(render_repeats(args.article, res, args.all))
    return 0


def cmd_check(args):
    snap = snapshot_path(args.article)
    if not os.path.isfile(snap):
        print(f"초안 복사본이 없습니다: {snap}. 후처리를 시작할 때 start를 먼저 실행합니다.", file=sys.stderr)
        return 2
    fp = args.facts or facts_path(args.article)
    facts_text = L.read_text(fp) if os.path.isfile(fp) else None
    res = compare(L.read_text(snap), L.read_text(args.article), facts_text)
    if args.json:
        slim = dict(res)
        for k in ("worse_ai", "worse_dist", "gate_fail"):
            slim[k] = [{"id": r["id"], "status": r["status"], "value": r["value"]} for r in res[k]]
        print(json.dumps(dict(slim, file=args.article, snapshot=snap, facts=fp if facts_text else None),
                         ensure_ascii=False, indent=1))
    else:
        print(render_check(snap, args.article, res))
    return 1 if res["must_fix"] else 0


def main(argv=None):
    L.setup_stdio()
    ap = argparse.ArgumentParser(description=f"{SKILL_NAME} post-processing helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start", help="Create the draft copy")
    p.add_argument("article")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("repeats", help="Print repeat candidates to reread")
    p.add_argument("article")
    p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("check", help="Compare against the draft copy")
    p.add_argument("article")
    p.add_argument("--facts")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("mark", help="Create the pre-fix copy")
    p.add_argument("article")
    p = sub.add_parser("audit", help="Print what to check for each edited sentence")
    p.add_argument("article")
    p.add_argument("--base")
    p.add_argument("--facts")
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.article.endswith((SNAPSHOT_SUFFIX, FACTS_SUFFIX, REPEATS_SUFFIX, MARK_SUFFIX, AUDIT_SUFFIX)):
        print(f"후처리할 글의 경로를 지정합니다. 입력한 경로는 작업 파일입니다: {args.article}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.article):
        print(f"파일이 없습니다: {args.article}", file=sys.stderr)
        return 2
    try:
        return {"start": cmd_start, "repeats": cmd_repeats, "check": cmd_check, "mark": cmd_mark,
                "audit": cmd_audit}[args.cmd](args)
    except (OSError, ValueError, KeyError) as e:
        print(f"revise_ko 실행 오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
