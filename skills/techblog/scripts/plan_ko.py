#!/usr/bin/env python3
"""K-Writer plan: checks a writing plan (<name>.plan.md) and compares an article with its plan.

The source of this file is core/scripts/plan_ko.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.

Usage
  python plan_ko.py check PLAN [--facts FACTS.md] [--json]
  python plan_ko.py compare PLAN ARTICLE [--json]
  python plan_ko.py elements FACTS.md [--max N] [--json]

A plan lists the units of an article top-down: the main point of the whole article, each unit (one subtopic, written
as a paragraph or a section) with what it tells the reader and how it unfolds, and one line per sentence.

  "- 핵심 주제: <one sentence>"
  "## 단위 1. <name>"
  "- 형태: 문단"                                (the form of the unit: a paragraph, a section, a list)
  "- 전할 내용: <one sentence>"
  "- 전개: <step → step → step>"
  "문단 1: <what this paragraph tells>"        (only when a unit has more than one paragraph)
  "1. [role] <what the sentence tells, written as a full sentence> (source)"
  "- [목록] <items of a list, table, or code block that is not written as sentences>"
  "- [제목] <title or heading, a noun phrase>"
  "## 제외한 사실"                              (facts left out, one per line with the reason)

check: reports structure errors (exit 1) and candidates to read (exit 0): plan lines that are not full sentences,
lines without a source, units that share no word with the main point, lines that hold several things, sentences
repeated across units, and numbers of the fact sheet that no line uses.

When the material holds more than the text can, the fact sheet lists the key elements of the text before the plan is
written ("## 핵심 요소"). Each round ("### 1차", "### 2차", ...) extracts again from the round before it, by merging
elements or by keeping the ones the reader cannot do without, until the number of elements fits the length. The text
is written from the last round.

  "### 2차: 한 문단 (요소 4개)"
  "문단 1: <what this paragraph tells>"       (only in the last round of a text of several paragraphs)
  "1. [role] <what must be in the text, as a full sentence> | 키워드: <name>, <value>, <condition> | <source>"
  "2. = 1차 5"                                 (element 5 of round 1, kept as it is)
  "- 제외: <elements of the round before that were left out, with the reason>"

elements: reports candidates to read in this section: elements that are not full sentences or run over 130
characters, elements without keywords, keywords that their own element does not contain, a reference to an element
that does not exist, a paragraph line that joins two points or holds more than five elements, a round that keeps less
than 40% of the round before it, and (with --max N) a last round of more than N elements. It then
prints the last round with every reference filled in, which is the list the text is written from. check prints the
same candidates and the keywords of the last round that the plan does not have. compare_elements (used by check_ko.py) lists the keywords of the last round
that the article does not have.
compare: reports plan lines with no matching sentence in the article, article sentences with no matching plan line,
and numbers of the plan that the article does not have. check_ko.py prints the same comparison when a plan file is
next to the article.

Exit codes: 0 no structure error, 1 structure errors (check), no key elements in the fact sheet (elements),
2 usage or input error
Uses only the standard library (Python 3.8 or later).
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_ko as L  # noqa: E402

SKILL_NAME = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLAN_SUFFIX = ".plan.md"

UNIT_RE = re.compile(r"^#{2,3}\s*단위\s*(\d+)\s*[.:)]?\s*(.*)$")
EXCLUDED_RE = re.compile(r"^#{1,3}\s*제외한\s*사실")
HEADING_RE = re.compile(r"^#{1,6}\s+")
KEY_RE = re.compile(r"^\s*(?:[-*]\s*)?(핵심 주제|전할 내용|전개 순서|전개|형태|독자|목적|분량|앞 단위와의 연결)\s*[:：]\s*(.*)$")
PARA_RE = re.compile(r"^\s*(?:[-*]\s*)?문단\s*(\d+)?\s*[:：.]\s*(.*)$")
SENT_RE = re.compile(r"^\s*(\d+(?:-\d+)?)[.)]\s*\[([^\]]+)\]\s*(.+?)\s*$")
BLOCK_RE = re.compile(r"^\s*(?:[-*]|\d+(?:-\d+)?[.)])\s*\[(제목|부제|헤딩|소제목|목록|표|코드|그림|인용)\]\s*(.*)$")
SOURCE_RE = re.compile(r"\s*\(((?:[^()]|\([^()]*\))*)\)\s*$")
PROPOSITION_END_RE = re.compile(r"(?:다|까|요|오)[.?!]?[\"'”’)]*$")
# Roles whose line is not a statement of fact, so it needs no source.
NO_SOURCE_ROLES = ("전환", "예고", "연결", "질문", "인사", "맺음", "요청", "소개")
SHORT_LINE = 15
LONG_LINE = 130
SOURCE_MAX = 60        # a longer parenthetical at the end is a source only when a full sentence comes before it
MATCH_PLAN = 0.5       # share of a plan line's words that an article sentence (or two adjacent ones) must have
MATCH_ARTICLE = 0.5    # share of an article sentence's words that a plan line (or two adjacent ones) must have
DUPLICATE = 0.8

ELEMENTS_RE = re.compile(r"^(#{1,4})\s*핵심\s*요소\s*$")
ROUND_RE = re.compile(r"^#{2,5}\s*(\d+)\s*차")
KEYWORDS_RE = re.compile(r"^키워드\s*[:：]\s*(.*)$")
DROPPED_RE = re.compile(r"^\s*[-*]\s*제외\s*[:：]\s*(.*)$")
KEPT_RE = re.compile(r"^\s*(\d+(?:-\d+)?)[.)]\s*(?:\[([^\]]+)\]\s*)?=\s*(\d+)\s*차\s*(\d+(?:-\d+)?)\s*$")
TWO_POINTS_RE = re.compile(r"(?:([가-힣])고|으며|이며|지만),?\s")   # a connective that may join two clauses
PARA_MAX = 5           # elements that one paragraph of a summary holds
ROUND_KEEP = 0.4       # a round that keeps a smaller share of the round before it has skipped a level
ROUND_MIN = 6          # rounds with fewer elements than this may be cut to any size


def plan_path(article):
    """The plan of <name>.md and of the Default draft <name>.draft.md is <name>.plan.md, like the fact sheet."""
    base = article[:-3] if article.endswith(".md") else article
    if base.endswith(".draft"):
        base = base[:-len(".draft")]
    return base + PLAN_SUFFIX


def split_source(content):
    """Splits "<sentence> (<source>)". The source may list several fact sheet rows and hold parentheses itself."""
    m = SOURCE_RE.search(content)
    if m:
        before = content[:m.start()].rstrip()
        if before and (len(m.group(1)) <= SOURCE_MAX or PROPOSITION_END_RE.search(before)):
            return before, m.group(1).strip()
    return content, ""


def parse_plan(text):
    plan = {"main": "", "keys": {}, "units": [], "excluded": [], "loose": []}
    unit = None
    para = 0
    in_excluded = False
    for n, raw in enumerate(L.normalize_text(text).split("\n"), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if EXCLUDED_RE.match(line):
            in_excluded, unit = True, None
            continue
        m = UNIT_RE.match(line)
        if m:
            in_excluded = False
            unit = {"n": int(m.group(1)), "name": m.group(2).strip(), "line": n, "point": "", "flow": "", "form": "",
                    "paras": [], "sentences": [], "blocks": []}
            plan["units"].append(unit)
            para = 0
            continue
        if HEADING_RE.match(line):
            in_excluded = False
            if not line.lstrip("# ").startswith("설계"):
                unit = None
            continue
        if in_excluded:
            plan["excluded"].append(line.strip(" -*"))
            continue
        m = KEY_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if unit is None:
                plan["keys"][key] = value
                if key == "핵심 주제":
                    plan["main"] = value
            elif key == "전할 내용":
                unit["point"] = value
            elif key == "전개":
                unit["flow"] = value
            elif key == "형태":
                unit["form"] = value
            continue
        if unit is None:
            continue
        m = PARA_RE.match(line)
        if m:
            para += 1
            unit["paras"].append({"n": para, "point": m.group(2).strip(), "line": n})
            continue
        m = BLOCK_RE.match(line)
        if m:
            text, _ = split_source(m.group(2).strip())
            unit["blocks"].append({"kind": m.group(1), "text": text, "line": n, "para": para})
            continue
        m = SENT_RE.match(line)
        if m:
            content, source = split_source(m.group(3))
            unit["sentences"].append({"id": m.group(1), "role": m.group(2).strip(), "text": content, "source": source,
                                      "line": n, "unit": unit["n"], "para": para})
            continue
        plan["loose"].append({"line": n, "text": line.strip()})
    return plan


def all_sentences(plan):
    return [s for u in plan["units"] for s in u["sentences"]]


def words(text):
    return set(L.flow_words(text))


def numbers(text):
    return {key for key, _ in L.extract_numbers(text)}


# ---------------------------------------------------------------- key elements

def parse_elements(text):
    """Rounds of the "## 핵심 요소" section of a fact sheet, in order. [] when the fact sheet has no such section.

    "2. = 1차 5" keeps element 5 of round 1 as it is: its role, text, and keywords are copied. A reference to an element
    that does not exist stays in the round with "missing" set.
    """
    rounds, cur, level, para = [], None, 0, 0
    for n, raw in enumerate(L.normalize_text(text or "").split("\n"), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        m = ELEMENTS_RE.match(line)
        if m:
            level, cur = len(m.group(1)), None
            continue
        if not level:
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            if len(h.group(1)) <= level:       # the next section of the fact sheet
                level, cur = 0, None
                continue
            m = ROUND_RE.match(line)
            cur = {"n": int(m.group(1)) if m else len(rounds) + 1, "title": h.group(2).strip(), "line": n,
                   "elements": [], "dropped": [], "paras": []}
            rounds.append(cur)
            para = 0
            continue
        if cur is None:                        # elements listed without a round heading are one round
            cur = {"n": 1, "title": "", "line": n, "elements": [], "dropped": [], "paras": []}
            rounds.append(cur)
        m = DROPPED_RE.match(line)
        if m:
            cur["dropped"].append(m.group(1).strip())
            continue
        m = PARA_RE.match(line)
        if m:
            para += 1
            cur["paras"].append({"n": para, "point": m.group(2).strip(), "line": n})
            continue
        m = KEPT_RE.match(line)
        if m:
            ref = f"{m.group(3)}차 {m.group(4)}"
            found = next((e for r in rounds if r is not cur and r["n"] == int(m.group(3))
                          for e in r["elements"] if e["id"] == m.group(4)), None)
            base = found or {"role": "", "text": "", "keywords": []}
            cur["elements"].append({"id": m.group(1), "role": m.group(2) or base["role"], "text": base["text"],
                                    "keywords": list(base["keywords"]), "source": ref, "line": n, "para": para,
                                    "kept": True, "missing": found is None})
            continue
        m = SENT_RE.match(line)
        if not m:
            continue
        parts = [p.strip() for p in m.group(3).split("|")]
        keywords, source = [], ""
        for part in parts[1:]:
            k = KEYWORDS_RE.match(part)
            if k:
                keywords = [w.strip() for w in re.split(r",\s+|;|，", k.group(1)) if w.strip()]
            elif part:
                source = part
        content, tail = split_source(parts[0])
        cur["elements"].append({"id": m.group(1), "role": m.group(2).strip(), "text": content,
                                "keywords": keywords, "source": source or tail, "line": n, "para": para})
    return [r for r in rounds if r["elements"] or r["dropped"]]


def joins_two_points(text):
    """True when a paragraph point joins two clauses: a past-tense "~했고", or "~으며", "~이며", "~지만"."""
    for m in TWO_POINTS_RE.finditer(text):
        ch = m.group(1)
        # "~고" joins two statements when the syllable before it ends in ㅆ (했고, 졌고, 있었고).
        if ch is None or (ord(ch) - 0xAC00) % 28 == 20:
            return True
    return False


def squash(text):
    """Text without spaces, emphasis marks, and thousands separators, to look a keyword up in."""
    text = re.sub(r"[*_`~]", "", L.normalize_text(text or ""))
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return re.sub(r"\s+", "", text).lower()


def check_elements(rounds, plan_text=None, limit=None):
    """Candidates to read in the key elements. plan_text: the sentences of the plan written from the last round.
    limit: the number of elements that the length of the text holds."""
    cands = []

    def cand(kind, line, text, why):
        cands.append({"kind": kind, "line": line, "text": text, "why": why})

    for r in rounds:
        for q in r["paras"]:
            label = f"{r['n']}차 문단 {q['n']}: {q['point']}"
            if q["point"] and not PROPOSITION_END_RE.search(q["point"]):
                cand("문장이 아닌 문단의 전할 내용", q["line"], label,
                     "그 문단을 읽은 독자가 알게 되는 것을 서술어까지 한 문장으로 적는다")
            elif joins_two_points(q["point"]):
                cand("두 내용을 이은 문단의 전할 내용", q["line"], label,
                     "한 문단은 한 가지 내용을 다룬다. 서로 다른 내용 둘을 이었으면 문단을 둘로 나눈다")
            held = sum(1 for e in r["elements"] if e.get("para") == q["n"])
            if held > PARA_MAX:
                cand("요소가 많은 문단", q["line"], f"{label} (요소 {held}개)",
                     f"한 문단에는 요소를 {PARA_MAX}개까지 묶는다. 내용이 바뀌는 곳에서 문단을 나눈다")
        for e in r["elements"]:
            if e.get("missing"):
                cand("앞 차수에 없는 요소", e["line"], f"{r['n']}차 {e['id']}. = {e['source']}",
                     "\"= 1차 3\"은 앞 차수의 요소를 그대로 남긴다는 표시다. 차수와 번호를 확인한다")
                continue
            if e.get("kept"):                  # checked where the element was written
                continue
            label = f"{r['n']}차 {e['id']}. {e['text']}"
            if not PROPOSITION_END_RE.search(e["text"]):
                cand("문장이 아닌 핵심 요소", e["line"], label,
                     "요소의 내용을 무엇이 어떠한지, 누가 무엇을 했는지 서술어까지 적는다")
            elif len(e["text"]) > LONG_LINE:
                cand("여러 내용을 담은 핵심 요소", e["line"], label,
                     f"요소 하나는 공백을 포함해 {LONG_LINE}자 안의 한 문장이다. 서로 다른 사실을 합쳐 길어졌으면 합치지 "
                     "않고 더 필요한 요소를 선택한다. 내용을 줄여 쓰지 않는다")
            if not e["keywords"]:
                cand("키워드가 없는 핵심 요소", e["line"], label,
                     "글에 그대로 나와야 하는 대상의 이름, 수치, 조건을 \"| 키워드: \" 뒤에 적는다")
            body = squash(e["text"])
            lost = [k for k in e["keywords"] if squash(k) not in body]
            if lost:
                cand("요소의 내용에 없는 키워드", e["line"], f"{', '.join(lost)} ← {label}",
                     "키워드는 그 요소의 내용에 나온 말로 적는다. 내용에 없는 대상이나 값이면 내용에 추가한다")
    for prev, cur in zip(rounds, rounds[1:]):
        a, b = len(prev["elements"]), len(cur["elements"])
        if a >= ROUND_MIN and b < a * ROUND_KEEP:
            cand("한 차수에서 절반 넘게 줄인 핵심 요소", cur["line"], f"{prev['n']}차 {a}개 → {cur['n']}차 {b}개",
                 "한 차수에서는 요소를 절반 정도까지만 줄인다. 합칠 수 있는 요소를 먼저 합치고, 남은 목록으로 다시 추출한다")
    if limit and rounds and len(rounds[-1]["elements"]) > limit:
        last = rounds[-1]
        cand("분량에 담을 수보다 많은 마지막 차수", last["line"], f"{last['n']}차 {len(last['elements'])}개, 분량에 담을 요소 {limit}개",
             "이 목록에서 요소를 합치거나 꼭 필요한 요소를 다시 선택해 다음 차수를 적는다. 요소의 내용을 줄여 쓰지 않는다")
    if plan_text is not None and rounds:
        body = squash(plan_text)
        last = rounds[-1]
        for e in last["elements"]:
            lost = [k for k in e["keywords"] if squash(k) not in body]
            if lost:
                cand("설계에 없는 핵심 요소의 키워드", e["line"], f"{', '.join(lost)} ← {last['n']}차 {e['id']}. {e['text']}",
                     "마지막 차수의 요소는 모두 설계의 문장으로 적는다. 다른 표현으로 적었으면 키워드를 그 표현으로 수정한다")
    return cands


def compare_elements(rounds, article_text):
    """Keywords of the last round that the article does not have."""
    if not rounds:
        return None
    last = rounds[-1]
    body = squash(article_text)
    missing, total = [], 0
    for e in last["elements"]:
        total += len(e["keywords"])
        lost = [k for k in e["keywords"] if squash(k) not in body]
        if lost:
            missing.append({"id": e["id"], "line": e["line"], "text": e["text"], "keywords": lost})
    return {"round": last["n"], "elements": len(last["elements"]), "keywords": total, "missing": missing,
            "rounds": [{"n": r["n"], "elements": len(r["elements"])} for r in rounds]}


def render_elements(res, before=None):
    """before: the comparison of the last checked text. When given, only the keywords that the edit removed are listed."""
    if not res:
        return ""
    missing = res["missing"]
    if before is not None:
        had = {(m["id"], k) for m in before["missing"] for k in m["keywords"]}
        missing = [dict(m, keywords=[k for k in m["keywords"] if (m["id"], k) not in had]) for m in missing]
        missing = [m for m in missing if m["keywords"]]
    lost = sum(len(m["keywords"]) for m in missing)
    if not lost:
        return "" if before is not None else (
            f"핵심 요소 대조: 마지막 차수({res['round']}차)의 요소 {res['elements']}개에 적은 키워드 {res['keywords']}개가 "
            "글에 모두 있다.")
    if before is not None:
        lines = [f"핵심 요소 대조: 지난 검사 뒤에 글에서 빠진 키워드 {lost}개. 문장을 수정하면서 빠진 대상, 수치, 조건이면 "
                 "그 문장에 다시 쓴다. 그 요소를 쓰지 않기로 했으면 핵심 요소 섹션에 차수를 하나 더 적어 제외한다."]
    else:
        lines = [f"핵심 요소 대조: 마지막 차수({res['round']}차)의 요소 {res['elements']}개에 적은 키워드 {res['keywords']}개 "
                 f"중 {lost}개를 글에서 찾지 못했다.",
                 "[핵심 요소 대조] 글에 없는 키워드: 그 요소의 내용이 글에 있는지 확인한다. 줄여 쓰면서 빠진 대상, 수치, "
                 "조건이면 그 문장에 다시 쓴다. 다른 표현으로 이미 썼으면 그대로 둔다. 쓰지 않기로 한 요소는 핵심 요소 "
                 "섹션에 차수를 하나 더 적어 제외한다."]
    for m in missing[:15]:
        lines.append(f"    요소 {m['id']} (fact sheet L{m['line']}): {', '.join(m['keywords'])} ← {m['text'][:110]}")
    return "\n".join(lines)


ELEMENT_QUESTIONS = (
    "마지막 차수의 요소마다 \"이 요소가 없으면 독자가 무엇을 모르거나 잘못 알게 되는가\"에 답할 수 있는가",
    "결론의 범위를 바꾸는 조건과 한계, 결론을 얻는 대신 생긴 비용, 독자가 할 일의 기한과 방법이 마지막 차수에 남아 있는가",
    "합친 요소를 한 문장으로 말할 수 있는가. 합치면서 대상의 이름이나 값이 사라지지 않았는가",
    "요소의 내용이 주어, 목적어, 값, 조건을 갖춘 문장인가. 분량은 요소의 수로 맞추고 요소의 내용은 줄이지 않았는가",
)


def render_element_check(path, rounds, cands):
    flow = " → ".join(f"{r['n']}차 {len(r['elements'])}개" for r in rounds)
    lines = [f"{SKILL_NAME} elements | {os.path.basename(path)} | {flow}"]
    if cands:
        lines.append("")
        lines.append("핵심 요소 점검 후보 (줄을 읽고 해당하면 수정한다):")
        kinds = []
        for c in cands:
            if c["kind"] not in kinds:
                kinds.append(c["kind"])
        for kind in kinds:
            group = [c for c in cands if c["kind"] == kind]
            lines.append(f"[{kind}] {len(group)}개: {group[0]['why']}.")
            lines.extend(f"    L{c['line']}: {c['text'][:150]}" for c in group[:12])
    else:
        lines.append("점검 후보가 없다.")
    last = rounds[-1]
    lines.append("")
    lines.append(f"마지막 차수({last['n']}차)의 요소. 글은 이 목록의 요소를 순서대로 하나씩 문장으로 쓴다:")
    points = {q["n"]: q["point"] for q in last["paras"]}
    para = 0
    for e in last["elements"]:
        if e.get("para") and e["para"] != para:
            para = e["para"]
            lines.append(f"  문단 {para}: {points.get(para, '')}")
        if e.get("missing"):
            continue
        lines.append(f"  {e['id']}. [{e['role']}] {e['text']} | 키워드: {', '.join(e['keywords'])}")
    lines.append("")
    lines.append("마지막 차수를 읽고 확인한다:")
    lines.extend(f"  {i}. {q}" for i, q in enumerate(ELEMENT_QUESTIONS, 1))
    return "\n".join(lines)


# ---------------------------------------------------------------- check

def check(plan, facts_text=None):
    errors, cands = [], []

    def cand(kind, line, text, why):
        cands.append({"kind": kind, "line": line, "text": text, "why": why})

    if not plan["main"]:
        errors.append("핵심 주제가 없다. 설계 맨 위에 \"- 핵심 주제: <이 글을 읽은 독자가 알게 되거나 하게 될 것>\"을 한 문장으로 적는다.")
    if not plan["units"]:
        errors.append("단위가 없다. \"## 단위 1. <이름>\" 아래에 전할 내용, 전개, 문장별 내용을 적는다.")
    main_words = words(plan["main"])
    sents = all_sentences(plan)
    with_source = sum(1 for s in sents if s["source"])
    want_source = facts_text is not None or (sents and with_source * 2 >= len(sents))
    for u in plan["units"]:
        label = f"단위 {u['n']}"
        if not u["point"]:
            errors.append(f"{label}(L{u['line']})에 \"전할 내용\"이 없다. 이 단위를 읽은 독자가 알게 되는 것을 한 문장으로 적는다.")
        if not u["sentences"] and not u["blocks"]:
            errors.append(f"{label}(L{u['line']})에 문장이 없다. \"1. [역할] 전할 내용 (근거)\" 형식으로 문장마다 한 줄씩 적는다.")
        if u["point"] and not PROPOSITION_END_RE.search(u["point"]):
            cand("문장이 아닌 전할 내용", u["line"], u["point"],
                 "단위의 전할 내용을 무엇이 어떠한지, 누가 무엇을 했는지 서술어까지 적는다")
        unit_words = set()
        for s in u["sentences"] + u["blocks"]:
            unit_words |= words(s["text"])
        point_words = words(u["point"])
        if u["point"] and main_words and not (point_words | unit_words) & main_words:
            cand("핵심 주제와 겹치는 단어가 없는 단위", u["line"], f"{label}. {u['name']}: {u['point']}",
                 "이 단위가 핵심 주제의 어느 부분을 설명하는지 확인한다. 설명하지 않으면 단위를 제외한다")
        if u["point"] and u["sentences"] and point_words and not point_words & unit_words:
            cand("전할 내용과 문장이 겹치지 않는 단위", u["line"], f"{label}. {u['name']}: {u['point']}",
                 "문장별 내용이 이 단위의 전할 내용을 설명하는지 확인한다")
        for s in u["sentences"]:
            if not PROPOSITION_END_RE.search(s["text"]):
                cand("서술어로 끝나지 않은 계획 문장", s["line"], s["text"],
                     "단어만 나열하지 않고 무엇이 어떠한지, 누가 무엇을 어떻게 했는지 문장으로 적는다")
            elif len(re.sub(r"\s", "", s["text"])) < SHORT_LINE:
                cand("짧은 계획 문장", s["line"], s["text"], "대상, 값, 조건이 빠지지 않았는지 확인한다")
            if len(s["text"]) > LONG_LINE or len(re.findall(r"(?:고|며|으며),? ", s["text"])) >= 3:
                cand("여러 내용을 담은 계획 문장", s["line"], s["text"],
                     "서로 다른 사실이 둘 이상이면 계획 문장을 나눈다. 한 사실과 그 조건, 이유면 그대로 둔다")
            if want_source and not s["source"] and not any(r in s["role"] for r in NO_SOURCE_ROLES):
                cand("근거가 없는 계획 문장", s["line"], s["text"],
                     "이 문장의 사실이 있는 fact sheet 항목을 괄호에 적는다. fact sheet에 없는 사실이면 문장을 제외한다")
    # The same thing planned in two units. The opening unit states the main point that the later
    # units explain, so it is not compared. Two sentences that share their words but give
    # different values ("24시간 넘게" and "48시간 넘게") are two facts.
    opening = plan["units"][0]["n"] if plan["units"] else None
    for i, a in enumerate(sents):
        wa = words(a["text"])
        if len(wa) < 4 or a["unit"] == opening:
            continue
        na = numbers(a["text"])
        for b in sents[i + 1:]:
            if b["unit"] == a["unit"]:
                continue
            wb = words(b["text"])
            nb = numbers(b["text"])
            if na and nb and not na & nb:
                continue
            if len(wb) >= 4 and len(wa & wb) / min(len(wa), len(wb)) >= DUPLICATE:
                cand("두 단위에 겹치는 계획 문장", b["line"], f"L{a['line']} {a['text']} / L{b['line']} {b['text']}",
                     "같은 내용이면 그 내용을 다루는 단위 한 곳에만 남긴다")
    plan_text = "\n".join([plan["main"]] + [u["point"] for u in plan["units"]] + [s["text"] for s in sents]
                          + [b["text"] for u in plan["units"] for b in u["blocks"]])
    nums = {"unassigned": [], "unknown": []}
    if facts_text is not None:
        plan_nums = numbers(plan_text) | numbers("\n".join(plan["excluded"]))
        seen = set()
        for key, raw in L.extract_numbers(L.strip_general_knowledge(facts_text)):
            # A bare number in a fact sheet is mostly a line or page of the source, a year, or an item number.
            if key not in plan_nums and key not in seen and not re.fullmatch(r"[\d,.\s]+", raw):
                seen.add(key)
                nums["unassigned"].append(raw)
        fact_nums = L.number_set(facts_text)
        seen = set()
        for key, raw in L.extract_numbers(plan_text):
            if key not in fact_nums and key not in seen:
                seen.add(key)
                nums["unknown"].append(raw)
    if facts_text is not None:
        cands.extend(check_elements(parse_elements(facts_text), plan_text))
    stats = {"units": len(plan["units"]),
             "paragraphs": sum(max(1, len(u["paras"])) for u in plan["units"] if u["sentences"]),
             "sentences": len(sents),
             "chars": sum(len(re.sub(r"\s", "", s["text"])) for s in sents),
             "with_source": with_source}
    return {"errors": errors, "candidates": cands, "numbers": nums, "stats": stats}


def render_check(path, plan, res):
    st = res["stats"]
    lines = [f"{SKILL_NAME} plan | {os.path.basename(path)} | 단위 {st['units']}개, 문단 {st['paragraphs']}개, "
             f"문장 {st['sentences']}개, 계획 문장의 글자 수 합계 {st['chars']:,}자(공백 제외)"]
    if plan["keys"].get("분량"):
        lines.append(f"정한 분량: {plan['keys']['분량']}. 글은 계획 문장을 풀어 쓰므로 보통 계획 문장의 글자 수 합계보다 길어진다.")
    if res["errors"]:
        lines.append("")
        lines.append("반드시 수정할 항목:")
        lines.extend(f"  - {e}" for e in res["errors"])
    if res["candidates"]:
        lines.append("")
        lines.append("설계 점검 후보 (줄을 읽고 해당하면 수정한다):")
        kinds = []
        for c in res["candidates"]:
            if c["kind"] not in kinds:
                kinds.append(c["kind"])
        for kind in kinds:
            group = [c for c in res["candidates"] if c["kind"] == kind]
            lines.append(f"[{kind}] {len(group)}개: {group[0]['why']}.")
            for c in group[:12]:
                lines.append(f"    L{c['line']}: {c['text'][:150]}")
            if len(group) > 12:
                lines.append(f"    나머지 {len(group) - 12}개: " + ", ".join(f"L{c['line']}" for c in group[12:]))
    nums = res["numbers"]
    if nums["unassigned"]:
        lines.append("")
        lines.append("fact sheet에 있는데 설계의 어느 문장에도 없는 수치: " + ", ".join(nums["unassigned"][:20])
                     + ". 독자가 핵심 주제를 이해하거나 행동하는 데 필요한 수치가 빠지지 않았는지 확인한다. 쓰지 않기로 한 "
                       "사실을 \"## 제외한 사실\"에 적어 두면 다시 검출되지 않는다.")
    if nums["unknown"]:
        lines.append("")
        lines.append("설계에 있는데 fact sheet에 없는 수치: " + ", ".join(nums["unknown"][:20])
                     + ". 자료에서 확인해 fact sheet에 적거나 설계에서 삭제한다.")
    if not res["errors"] and not res["candidates"] and not nums["unassigned"] and not nums["unknown"]:
        lines.append("구조 오류와 점검 후보가 없다.")
    lines.append("")
    lines.append("설계를 끝까지 읽고 확인한다:")
    lines.extend(f"  {i}. {q}" for i, q in enumerate(PLAN_QUESTIONS, 1))
    return "\n".join(lines)


PLAN_QUESTIONS = (
    "단위마다 전할 내용이 핵심 주제의 한 부분을 설명하거나 뒷받침하는가. 그 단위를 제외하면 독자가 무엇을 모르게 되는지 말할 수 있는가",
    "앞 단위를 읽어야 뒤 단위를 이해할 수 있는 순서인가. 뒤 단위에서 필요한 용어와 사실을 앞 단위에서 먼저 설명하는가",
    "단위 안에서 한 문장에서 다음 문장으로 넘어갈 때 독자가 스스로 채워야 하는 이유, 과정, 조건이 없는가",
    "정의나 주장처럼 추상적인 문장 다음에 풀이, 예, 이유, 수치 중 하나가 이어지는가",
    "독자가 핵심 주제를 이해하거나 행동하는 데 필요한 fact sheet의 사실이 모두 어느 문장에 배정됐는가",
)


# ---------------------------------------------------------------- compare

def article_units(text):
    """Sentences, list items, table rows, and headings of the article with their content words."""
    units = []
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type in ("code", "html"):
            continue
        if b.type == "heading":
            clean, _, _ = L.clean_inline(b.text)
            units.append({"line": b.line, "kind": "헤딩", "text": clean})
        elif b.type == "table":
            for k, row in enumerate(b.text.split("\n")):
                if row.strip() and not L.TABLE_DELIM_RE.match(row):
                    clean, _, _ = L.clean_inline(row)
                    units.append({"line": b.line + k, "kind": "표", "text": clean})
        else:
            clean, _, codes = L.clean_inline(b.text)
            kind = {"list_item": "목록", "blockquote": "인용"}.get(b.type, "문장")
            for s in L.split_sentences(clean) or [clean]:
                shown = s
                for c in codes[:s.count(L.PH_CODE)]:
                    shown = shown.replace(L.PH_CODE, "`" + c + "`", 1)
                codes = codes[s.count(L.PH_CODE):]
                units.append({"line": b.line, "kind": kind, "text": shown})
    for u in units:
        u["words"] = words(u["text"])
        u["nums"] = numbers(u["text"])
    return units


def _best(target, pool):
    """Best share of target's words found in one item of pool or in two adjacent items. Returns (share, index)."""
    if not target:
        return 1.0, -1
    best, where = 0.0, -1
    for i, w in enumerate(pool):
        got = len(target & w) / len(target)
        if i + 1 < len(pool):
            got = max(got, len(target & (w | pool[i + 1])) / len(target) - 0.05)
        if got > best:
            best, where = got, i
    return best, where


def compare(plan, article_text):
    units = article_units(article_text)
    sents = all_sentences(plan)
    art_words = [u["words"] for u in units]
    plan_words = [words(s["text"]) for s in sents]
    art_nums = set()
    for u in units:
        art_nums |= u["nums"]
    missing, order = [], []
    last = -1
    for s, pw in zip(sents, plan_words):
        if len(pw) < 2:
            continue
        nums = numbers(s["text"])
        share, where = _best(pw, art_words)
        if share < MATCH_PLAN and not (nums and nums <= art_nums and share >= MATCH_PLAN - 0.2):
            missing.append({"line": s["line"], "id": s["id"], "unit": s["unit"], "text": s["text"],
                            "share": round(share, 2)})
            continue
        if where < last - 3:
            order.append({"line": s["line"], "id": s["id"], "text": s["text"], "article_line": units[where]["line"]})
        last = max(last, where)
    unplanned = []
    block_words = [words(b["text"]) for u in plan["units"] for b in u["blocks"]]
    pool = plan_words + block_words + [words(u["point"]) for u in plan["units"]]
    for u in units:
        if u["kind"] != "문장" or len(u["words"]) < 3:
            continue
        share, _ = _best(u["words"], pool)
        if share < MATCH_ARTICLE:
            unplanned.append({"line": u["line"], "text": u["text"], "share": round(share, 2)})
    lost_nums = []
    seen = set()
    for s in sents:
        for key, raw in L.extract_numbers(s["text"]):
            if key not in art_nums and key not in seen:
                seen.add(key)
                lost_nums.append({"value": raw, "line": s["line"]})
    paragraphs = sum(1 for b in L.parse_blocks(L.normalize_text(article_text)) if b.type == "paragraph")
    return {"missing": missing, "unplanned": unplanned, "order": order, "lost_numbers": lost_nums,
            "plan": {"units": len(plan["units"]), "sentences": len(sents),
                     "paragraphs": sum(max(1, len(u["paras"])) for u in plan["units"] if u["sentences"])},
            "article": {"sentences": sum(1 for u in units if u["kind"] == "문장"), "paragraphs": paragraphs}}


def render_compare(res, only_lines=None, title=True):
    """only_lines: when given, article sentences outside these lines are not listed (used after an edit)."""
    lines = []
    p, a = res["plan"], res["article"]
    if title:
        lines.append(f"설계 대조: 설계는 단위 {p['units']}개, 문단 {p['paragraphs']}개, 문장 {p['sentences']}개이고 "
                     f"글은 문단 {a['paragraphs']}개, 문장 {a['sentences']}개다.")
    unplanned = [u for u in res["unplanned"] if only_lines is None or u["line"] in only_lines]
    if res["missing"]:
        lines.append(f"[설계 대조] 글에서 찾지 못한 계획 문장 {len(res['missing'])}개: 그 내용을 글에 쓰거나, 쓰지 않기로 "
                     "했으면 설계에서 삭제하고 이유를 \"제외한 사실\"에 적는다. 다른 표현으로 이미 썼으면 그대로 둔다.")
        for m in res["missing"][:15]:
            lines.append(f"    설계 L{m['line']} (단위 {m['unit']}, {m['id']}): {m['text'][:140]}")
        if len(res["missing"]) > 15:
            lines.append("    나머지: " + ", ".join(f"설계 L{m['line']}" for m in res["missing"][15:]))
    if res["lost_numbers"]:
        lines.append("[설계 대조] 설계에 있는데 글에 없는 수치: "
                     + ", ".join(f"{n['value']}(설계 L{n['line']})" for n in res["lost_numbers"][:15])
                     + ". 줄여 쓰면서 빠진 수치면 그 문장에 다시 쓴다.")
    if unplanned:
        lines.append(f"[설계 대조] 설계에 대응하는 문장이 없는 글의 문장 {len(unplanned)}개: 그 단위의 전할 내용을 "
                     "설명하는 문장이면 설계에 추가하고, 아니면 삭제한다. 용어 설명이나 표를 소개하는 문장은 그대로 둔다.")
        for u in unplanned[:15]:
            lines.append(f"    L{u['line']}: {u['text'][:140]}")
        if len(unplanned) > 15:
            lines.append("    나머지: " + ", ".join(f"L{u['line']}" for u in unplanned[15:]))
    if res["order"]:
        lines.append(f"[설계 대조] 설계와 다른 순서로 쓴 문장 {len(res['order'])}개: 순서를 바꾼 이유가 있으면 설계를 "
                     "그 순서로 수정한다.")
        for o in res["order"][:8]:
            lines.append(f"    설계 L{o['line']} → 글 L{o['article_line']}: {o['text'][:120]}")
    if title and len(lines) == 1:
        lines.append("설계의 문장과 글의 문장이 모두 대응한다.")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    L.setup_stdio()
    ap = argparse.ArgumentParser(description=f"{SKILL_NAME} plan: check a writing plan and compare an article with it")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("plan")
    c.add_argument("--facts", help="fact sheet path (default: <name>.facts.md when it exists)")
    c.add_argument("--json", action="store_true")
    m = sub.add_parser("compare")
    m.add_argument("plan")
    m.add_argument("article")
    m.add_argument("--json", action="store_true")
    e = sub.add_parser("elements")
    e.add_argument("facts")
    e.add_argument("--max", type=int, help="the number of elements that the length of the text holds")
    e.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not args.cmd:
        ap.print_usage(sys.stderr)
        return 2
    paths = [args.facts] if args.cmd == "elements" else [args.plan] + ([args.article] if args.cmd == "compare" else [])
    for path in paths:
        if not os.path.isfile(path):
            print(f"파일이 없습니다: {path}", file=sys.stderr)
            return 2
    try:
        if args.cmd == "elements":
            rounds = parse_elements(L.read_text(args.facts))
            if not rounds:
                print(f"핵심 요소가 없습니다: {args.facts}에 \"## 핵심 요소\" 섹션과 \"### 1차\" 아래의 요소를 적습니다.",
                      file=sys.stderr)
                return 1
            cands = check_elements(rounds, limit=args.max)
            if args.json:
                print(json.dumps({"rounds": rounds, "candidates": cands}, ensure_ascii=False, indent=1))
            else:
                print(render_element_check(args.facts, rounds, cands))
            return 0
        plan = parse_plan(L.read_text(args.plan))
        if args.cmd == "check":
            facts = args.facts
            if not facts and args.plan.endswith(PLAN_SUFFIX):
                guess = args.plan[:-len(PLAN_SUFFIX)] + ".facts.md"
                facts = guess if os.path.isfile(guess) else None
            if facts and not os.path.isfile(facts):
                print(f"파일이 없습니다: {facts}", file=sys.stderr)
                return 2
            res = check(plan, L.read_text(facts) if facts else None)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=1))
            else:
                print(render_check(args.plan, plan, res))
            return 1 if res["errors"] else 0
        res = compare(plan, L.read_text(args.article))
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"{SKILL_NAME} plan | {os.path.basename(args.plan)} ↔ {os.path.basename(args.article)}")
            print(render_compare(res))
        return 0
    except (OSError, ValueError, KeyError) as e:
        print(f"plan 실행 오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
