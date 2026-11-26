#!/usr/bin/env python3
"""K-Writer plan: checks a writing plan (<name>.plan.md) and compares an article with its plan.

The source of this file is core/scripts/plan_ko.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.

Usage
  python plan_ko.py check PLAN [--facts FACTS.md] [--json]
  python plan_ko.py compare PLAN ARTICLE [--json]

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
  "## 제외한 사실"                              (facts left out, one per line with the reason)

check: reports structure errors (exit 1) and candidates to read (exit 0): plan lines that are not full sentences,
lines without a source, units that share no word with the main point, lines that hold several things, sentences
repeated across units, and numbers of the fact sheet that no line uses.
compare: reports plan lines with no matching sentence in the article, article sentences with no matching plan line,
and numbers of the plan that the article does not have. check_ko.py prints the same comparison when a plan file is
next to the article.

Exit codes: 0 no structure error, 1 structure errors (check only), 2 usage or input error
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
BLOCK_RE = re.compile(r"^\s*[-*]\s*\[(목록|표|코드|그림|인용)\]\s*(.*)$")
SOURCE_RE = re.compile(r"\s*\(([^()]*)\)\s*$")
PROPOSITION_END_RE = re.compile(r"(?:다|까|요|오)[.?!]?[\"'”’)]*$")
# Roles whose line is not a statement of fact, so it needs no source.
NO_SOURCE_ROLES = ("전환", "예고", "연결", "질문", "인사", "맺음", "요청", "소개")
SHORT_LINE = 15
LONG_LINE = 110
MATCH_PLAN = 0.5       # share of a plan line's words that an article sentence (or two adjacent ones) must have
MATCH_ARTICLE = 0.5    # share of an article sentence's words that a plan line (or two adjacent ones) must have
DUPLICATE = 0.8


def plan_path(article):
    """The plan of <name>.md and of the Default draft <name>.draft.md is <name>.plan.md, like the fact sheet."""
    base = article[:-3] if article.endswith(".md") else article
    if base.endswith(".draft"):
        base = base[:-len(".draft")]
    return base + PLAN_SUFFIX


def split_source(content):
    m = SOURCE_RE.search(content)
    if m and len(m.group(1)) <= 60:
        return content[:m.start()].rstrip(), m.group(1).strip()
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
            unit["blocks"].append({"kind": m.group(1), "text": m.group(2).strip(), "line": n, "para": para})
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
        for s in u["sentences"]:
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
    # The same thing planned in two units
    for i, a in enumerate(sents):
        wa = words(a["text"])
        if len(wa) < 4:
            continue
        for b in sents[i + 1:]:
            if b["unit"] == a["unit"]:
                continue
            wb = words(b["text"])
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
            if key not in plan_nums and key not in seen:
                seen.add(key)
                nums["unassigned"].append(raw)
        fact_nums = L.number_set(facts_text)
        seen = set()
        for key, raw in L.extract_numbers(plan_text):
            if key not in fact_nums and key not in seen:
                seen.add(key)
                nums["unknown"].append(raw)
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
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not args.cmd:
        ap.print_usage(sys.stderr)
        return 2
    for path in [args.plan] + ([args.article] if args.cmd == "compare" else []):
        if not os.path.isfile(path):
            print(f"파일이 없습니다: {path}", file=sys.stderr)
            return 2
    try:
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
