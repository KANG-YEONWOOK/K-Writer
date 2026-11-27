#!/usr/bin/env python3
"""K-Writer check: one command for the whole check loop of a skill.

The source of this file is core/scripts/check_ko.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.

Usage
  python check_ko.py ARTICLE [--tone default|casual|plain|free|auto] [--facts FACTS.md] [--short | --full]
                             [--all] [--context N] [--keep] [--json]

First run on ARTICLE (no checked copy yet), or any run with --all: runs the full style lint (the same verdict and
output as lint_ko.py) and saves a copy of ARTICLE as the checked copy (<name>.checked.md, next to ARTICLE).

Later runs: compares ARTICLE with the checked copy by sentence, heading, and table row, and reports only what changed
since the last run:
  - the verdict of the whole article (one line), and every GATE and FAIL item wherever it is
  - WARN items and check candidates found in the changed units only
  - lint items whose status got worse than in the checked copy
  - numbers that are only in the checked copy, and new numbers (with whether the fact sheet has them)
  - each changed part with N unchanged units before and after it (--context, default 3), so the changed sentences
    can be reread in place without rereading the whole article
Then ARTICLE is saved as the new checked copy, so text that was already checked is not reported again. --keep leaves
the checked copy as it is.

The fact sheet path defaults to <name>.facts.md when that file exists. The short profile (lint_ko.py --short) is
applied automatically when the body of ARTICLE is under 1,500 characters; --short and --full override that.
When a writing plan (<name>.plan.md) is next to ARTICLE, the article is also compared with the plan (plan_ko.py):
plan lines with no matching sentence, numbers of the plan that the article lost, and sentences with no plan line.
Later runs list unplanned sentences only among the changed sentences.

Exit codes: 0 the whole article passes, 1 a Gate violation, a FAIL, too many WARN items, or a worsened AI style item,
2 usage or input error
Uses only the standard library (Python 3.8 or later).
"""

import argparse
import difflib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_ko as L  # noqa: E402
import revise_ko as R  # noqa: E402
import plan_ko as P  # noqa: E402

SKILL_NAME = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKED_SUFFIX = ".checked.md"
SHORT_CHARS = 1500
MAX_UNIT_CHARS = 400

QUESTIONS = (
    "주어, 목적어, 가리키는 대상이 바뀐 문장과 바로 앞 문장에서 드러나는가",
    "앞뒤 문장과 이어지는가(지시어가 가리키는 대상, 접속어, 인접한 같은 서술어)",
    "수치, 이름, 조건, 추정의 강도가 fact sheet나 자료와 같은가",
    "삭제한 문장에만 있던 용어 설명, 조건, 수치를 뒤 문장이 필요로 하지 않는가",
    "제목과 헤딩을 바꿨다면 명사나 명사형으로 끝나고 그 섹션의 내용과 맞는가",
)


def checked_path(path):
    base = path[:-3] if path.endswith(".md") else path
    return base + CHECKED_SUFFIX


def default_facts(path):
    fp = R.facts_path(path)
    return fp if os.path.isfile(fp) else None


def default_plan(path):
    pp = P.plan_path(path)
    return pp if os.path.isfile(pp) else None


def plan_report(plan_file, text, only_lines=None):
    """The comparison of the article with its plan as text, or "" when there is nothing to report after an edit."""
    res = P.compare(P.parse_plan(L.read_text(plan_file)), text)
    out = P.render_compare(res, only_lines=only_lines, title=only_lines is None)
    return out, res


def lint(text, tone, facts_text, short):
    thresholds, patterns_spec = L.apply_profile(L.load_thresholds(), L.load_json(L.PATTERNS_PATH), short)
    analysis = L.analyze(text, patterns_spec=patterns_spec, facts_text=facts_text)
    if tone == "auto":
        tone = L.detect_tone(analysis)
    ev = L.evaluate(analysis, thresholds, tone, max_hits=-1, patterns_spec=patterns_spec)
    return analysis, ev, thresholds, tone


def use_short(text, forced):
    if forced is not None:
        return forced
    return L.analyze(text)["stats"]["chars"] < SHORT_CHARS


def _trim(hits, n):
    return hits[:n] if n >= 0 else hits


def full_report(path, tone, facts, short, max_hits=5):
    text = L.read_text(path)
    facts_text = L.read_text(facts) if facts else None
    analysis, ev, thresholds, tone = lint(text, tone, facts_text, short)
    shown = {"results": [dict(r, hits=_trim(r["hits"], max_hits),
                              more=[{"line": h["line"], "match": h.get("match", "")} for h in r["hits"][max_hits:]]
                              if r.get("hits") and len(r["hits"]) > max_hits >= 0 and _compact(thresholds, r["id"])
                              else [])
                         if r.get("hits") else r for r in ev["results"]],
             "summary": ev["summary"]}
    return L.render_text(path, tone, analysis, shown, False, L.standard_text(thresholds)), ev


def _compact(thresholds, mid):
    return bool((thresholds["metrics"].get(mid) or {}).get("compact"))


# ---------------------------------------------------------------- Changes since the checked copy

def diff_units(before, after):
    """Returns (old units, new units, opcodes) of the unit-level diff."""
    old, new = R.audit_units(before), R.audit_units(after)
    sm = difflib.SequenceMatcher(None, [u["clean"] for u in old], [u["clean"] for u in new], autojunk=False)
    return old, new, sm


def _in_changed(hit, changed):
    """True if a lint hit lies in a changed unit. Sentence and heading hits carry the first 160 characters of the unit.
    Table hits join the cells differently, so they match by line. Punctuation hits quote the whole block, so they
    match by the expression they found."""
    text = hit.get("text", "")
    match = (hit.get("match") or "").strip()
    core = match[4:-4] if len(match) > 14 else match  # punctuation hits carry eight characters of context per side
    for u in changed:
        if u["line"] != hit.get("line"):
            continue
        if u["kind"] == "표" or u["clean"][:160] == text or (text and u["clean"].startswith(text[:40])):
            return True
        if core and core in u["clean"]:
            return True  # a hit that quotes the whole block: the matched expression is inside this unit
    prev = hit.get("previous")
    return bool(prev) and _in_changed(prev, changed)


def delta(before, after, tone, facts_text, short, context=3):
    old, new, sm = diff_units(before, after)
    changed_new = []
    removed = written = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            removed += i2 - i1
            written += j2 - j1
            changed_new.extend(new[j1:j2])
    groups = []
    for grp in sm.get_grouped_opcodes(context):
        rows = []
        for op, i1, i2, j1, j2 in grp:
            if op == "equal":
                rows.extend((" ", u) for u in new[j1:j2])
            else:
                rows.extend(("-", u) for u in old[i1:i2])
                rows.extend(("+", u) for u in new[j1:j2])
        if any(mark != " " for mark, _ in rows):
            groups.append(rows)

    _, ev_b, _, tone_b = lint(before, tone, facts_text, short)
    _, ev_a, thresholds, tone_a = lint(after, tone_b if tone == "auto" else tone, facts_text, short)
    st_b = {r["id"]: r["status"] for r in ev_b["results"]}
    seen_b = {r["id"] for r in ev_b["results"] if r.get("hits")}
    must, scoped, worse, warn_ids = [], [], [], []
    for r in ev_a["results"]:
        hits = r.get("hits") or []
        if r["status"] in ("GATE", "FAIL"):
            must.append(dict(r, hits=[dict(h, changed=_in_changed(h, changed_new)) for h in hits]))
            continue
        if r["status"] == "WARN":
            warn_ids.append(r["id"])
        if r["status"] in ("WARN", "CHECK"):
            mine = [h for h in hits if _in_changed(h, changed_new)]
            if mine:
                # The fix hint of an item the last run already reported is not repeated.
                scoped.append(dict(r, hits=mine, hint=None if r["id"] in seen_b else r.get("hint")))
        if R.RANK.get(r["status"], 0) > R.RANK.get(st_b.get(r["id"], "PASS"), 0) and r["status"] == "WARN":
            worse.append(r)

    nb, na = R._numbers(before), R._numbers(after)
    fact_keys = L.number_set(facts_text) if facts_text else None
    lost = [{"value": k, "line": v[0][0], "raw": v[0][1]} for k, v in nb.items() if k not in na]
    fresh = [{"value": k, "line": v[0][0], "raw": v[0][1],
              "in_facts": (k in fact_keys) if fact_keys is not None else None} for k, v in na.items() if k not in nb]
    worse_ai = [r for r in worse if not r["id"].startswith(R.DIST_PREFIX)]
    summary = ev_a["summary"]
    return {"units": [len(old), len(new)], "removed": removed, "written": written, "groups": groups,
            "must": must, "scoped": scoped, "worse": worse, "warn_ids": warn_ids,
            "lost_numbers": lost, "new_numbers": fresh, "summary": summary, "summary_before": ev_b["summary"],
            "tone": tone_a, "chars": L.analyze(after)["stats"]["chars"],
            "fail": summary["verdict"] != "PASS" or bool(worse_ai)}


def _unit_line(mark, u):
    text = u["text"] if len(u["text"]) <= MAX_UNIT_CHARS else u["text"][:MAX_UNIT_CHARS - 1] + "…"
    kind = "" if u["kind"] == "문장" else f"[{u['kind']}] "
    return f"  {mark} L{u['line']} {kind}{text}"


def _hit_lines(r, show_changed=False):
    out = [f"[{r['status']}] {r['id']} {r['title']}: {r['value']}"]
    if r.get("hint"):
        out.append(f"    수정 방향: {r['hint']}")
    for h in r.get("hits", [])[:8]:
        m = f" «{h['match']}»" if h.get("match") else ""
        where = f"L{h['line']}" if h.get("line") else "fact sheet"
        tag = " (이번에 바뀐 문장)" if show_changed and h.get("changed") else ""
        out.append(f"    {where}{m}{tag}: {R.excerpt(h['text'], 110)}")
    rest = len(r.get("hits", [])) - 8
    if rest > 0:
        out.append(f"    나머지 {rest}개는 --all로 확인한다.")
    return out


def render_delta(base, path, res, short, saved):
    sm, sb = res["summary"], res["summary_before"]
    profile = "짧은 글 기준" if short else "기본 기준"
    lines = [
        f"{SKILL_NAME} check | {os.path.basename(base)} → {os.path.basename(path)} | tone={res['tone']} | {profile} | "
        f"{res['chars']:,}자",
        f"글 전체 판정: {sm['verdict']} (Gate 위반 {sm['gate_fail']}, FAIL {sm['fail']}, WARN {sm['warn']}). "
        f"지난 검사: Gate 위반 {sb['gate_fail']}, FAIL {sb['fail']}, WARN {sb['warn']}",
    ]
    if not res["groups"]:
        lines.append("지난 검사 뒤에 바뀐 문장, 헤딩, 표의 행이 없다.")
    else:
        lines.append(f"지난 검사 뒤에 바뀐 부분 {len(res['groups'])}곳: 수정하거나 삭제한 단위 {res['removed']}개, "
                     f"새로 쓴 단위 {res['written']}개. 아래에 나오지 않은 문장은 지난 검사와 같으므로 다시 읽지 않는다.")
    if res["must"]:
        lines.append("")
        lines.append("반드시 수정할 항목(글 전체):")
        for r in res["must"]:
            lines.extend(_hit_lines(r, show_changed=True))
    if res["scoped"]:
        lines.append("")
        lines.append("바뀐 문장에서 검출된 표현(WARN과 점검 후보. 읽고 수정할지 정한다):")
        for r in res["scoped"]:
            lines.extend(_hit_lines(r))
    if res["worse"]:
        lines.append("")
        lines.append("지난 검사보다 나빠진 항목: " + ", ".join(f"{r['id']} {r['title']}({r['value']})" for r in res["worse"]))
    elif res["warn_ids"] and sm["verdict"] != "PASS" and not res["must"]:
        lines.append("")
        lines.append("WARN 항목: " + ", ".join(res["warn_ids"]) + ". 문장 위치는 --all로 확인한다.")
    if res["lost_numbers"]:
        lines.append("")
        lines.append("지난 검사에만 있는 수치(삭제한 것이 맞는지 확인한다): "
                     + ", ".join(f"{n['raw']}(L{n['line']})" for n in res["lost_numbers"][:12]))
    if res["new_numbers"]:
        def tag(n):
            if n["in_facts"] is None:
                return ""
            return " fact sheet에 있음" if n["in_facts"] else " fact sheet에 없음"
        lines.append("")
        lines.append("새 수치(자료와 대조한다): "
                     + ", ".join(f"{n['raw']}(L{n['line']}{tag(n)})" for n in res["new_numbers"][:12]))
    for k, rows in enumerate(res["groups"], 1):
        ls = [u["line"] for _, u in rows]
        lines.append("")
        lines.append(f"바뀐 부분 {k} (L{min(ls)}~L{max(ls)}). -는 지난 검사의 문장, +는 지금 문장, 표시가 없는 줄은 앞뒤 문맥이다.")
        lines.extend(_unit_line(mark, u) for mark, u in rows)
    if res.get("plan_text"):
        lines.append("")
        lines.append(res["plan_text"])
    if res["groups"]:
        lines.append("")
        lines.append("바뀐 부분마다 + 문장을 앞뒤 문맥과 이어 읽고 확인한다:")
        lines.extend(f"  {i}. {q}" for i, q in enumerate(QUESTIONS, 1))
    if saved:
        lines.append("")
        lines.append(f"지금 글을 검사한 글로 저장했다: {saved}. 다음 실행은 이 뒤에 바뀐 부분만 검사한다.")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    L.setup_stdio()
    ap = argparse.ArgumentParser(description=f"{SKILL_NAME} check: full lint on the first run, changed parts afterwards")
    ap.add_argument("article")
    ap.add_argument("--tone", choices=L.TONES + ("auto",), default="default")
    ap.add_argument("--facts", help="fact sheet path (default: <name>.facts.md when it exists)")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--short", dest="short", action="store_const", const=True, default=None,
                     help="apply the short profile")
    grp.add_argument("--full", dest="short", action="store_const", const=False, help="do not apply the short profile")
    ap.add_argument("--all", action="store_true", help="run the full lint again and reset the checked copy")
    ap.add_argument("--context", type=int, default=3, help="unchanged units shown before and after a change")
    ap.add_argument("--keep", action="store_true", help="do not update the checked copy")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if not os.path.isfile(args.article):
        print(f"파일이 없습니다: {args.article}", file=sys.stderr)
        return 2
    if args.article.endswith(CHECKED_SUFFIX):
        print(f"검사한 글의 복사본이 아니라 글 파일을 지정합니다: {args.article}", file=sys.stderr)
        return 2
    facts = args.facts or default_facts(args.article)
    if facts and not os.path.isfile(facts):
        print(f"파일이 없습니다: {facts}", file=sys.stderr)
        return 2
    base = checked_path(args.article)
    plan = default_plan(args.article)
    try:
        text = L.read_text(args.article)
        short = use_short(text, args.short)
        if args.all or not os.path.isfile(base):
            out, ev = full_report(args.article, args.tone, facts, short)
            code = 0 if ev["summary"]["verdict"] == "PASS" else 1
            plan_text, plan_res = plan_report(plan, text) if plan else ("", None)
            if args.json:
                out = json.dumps({"mode": "full", "file": args.article, "short": short, "summary": ev["summary"],
                                  "results": ev["results"], "plan": plan_res}, ensure_ascii=False, indent=1)
            else:
                if plan_text:
                    out += "\n\n" + plan_text
                out += "\n\n" + ("짧은 글 기준(본문 1,500자 미만)을 적용했다. " if short else "")
                if not args.keep:
                    out += (f"지금 글을 검사한 글로 저장했다: {base}. 글을 수정한 뒤 같은 명령을 다시 실행하면 "
                            f"바뀐 문장과 앞뒤 {args.context}문장만 검사한다.")
            if not args.keep:
                shutil.copyfile(args.article, base)
            print(out)
            return code
        facts_text = L.read_text(facts) if facts else None
        res = delta(L.read_text(base), text, args.tone, facts_text, short, max(0, args.context))
        if plan:
            changed = {u["line"] for rows in res["groups"] for mark, u in rows if mark == "+"}
            res["plan_text"], res["plan"] = plan_report(plan, text, only_lines=changed)
        saved = None
        if not args.keep and res["groups"]:
            shutil.copyfile(args.article, base)
            saved = base
        if args.json:
            slim = dict(res, groups=[[{"mark": m, "line": u["line"], "kind": u["kind"], "text": u["text"]}
                                      for m, u in rows] for rows in res["groups"]])
            for k in ("must", "scoped", "worse"):
                slim[k] = [{"id": r["id"], "status": r["status"], "value": r["value"], "hits": r.get("hits", [])}
                           for r in res[k]]
            slim.pop("plan_text", None)
            print(json.dumps(dict(slim, mode="delta", file=args.article, base=base, short=short),
                             ensure_ascii=False, indent=1))
        else:
            print(render_delta(base, args.article, res, short, saved))
        return 1 if res["fail"] else 0
    except (OSError, ValueError, KeyError) as e:
        print(f"check 실행 오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
