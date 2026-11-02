#!/usr/bin/env python3
"""사람 글 측정값(stats.json)으로 lint 기준치(thresholds.json)를 다시 만든다.

- 기준치는 holdout이 아닌 사람 글에서 잡는다(holdout은 글 ID 해시로 20%).
- 기간 가중치: base(2018-01~2022-11) 1.0, mid(2022-12~2024-12) 0.5, drift(2025~) 0. 2018~2022년 글에
  가중치를 많이 두라는 사용자 요구를 따른다. drift 글은 비교에만 쓴다. 기준 기간 전용 항목(AI_FAMILIES)은 mid 글도
  가중치 0이라 base 글로만 잡는다.
- 사이트 상한: 지표 pool마다 한 사이트의 가중치 합이 40%를 넘지 않게 줄인다. 글 5편 이상인 사이트가
  셋 이상일 때만 적용한다.
- upper: PASS ≤ 가중 p95, WARN ≤ 가중 p99.5에 여유(횟수 +1, 비율 ×1.2) / lower: PASS ≥ 가중 p5,
  WARN ≥ 가중 p0.5×0.8. 표본 끝의 글 몇 편이 경계를 정하지 않게 최댓값과 최솟값 대신 분위수를 쓴다.
  thresholds.json에서 "bound": "extreme"인 항목은 이전 공식(최댓값과 p99 중 큰 값, 최솟값과 p1 중 작은 값)을 쓴다.
- info, check: 점수에 넣지 않고 사람 글 가중 p10/p50/p90만 기록한다.
- poisson: 사람 글 전체의 가중 1,000자당 비율(pooled rate).
- 어투별 지표(tone 지정)는 해당 어투만, 나머지는 두 어투를 합쳐서 잡는다.
- 만든 기준치로 base holdout 사람 글을 판정해 통과율을 보고하고, 보고서를 calibration.md에 쓴다.
  dev/baseline/README.md는 사람이 쓴 측정 기록이라 덮어쓰지 않는다.

사용법
  python dev/baseline/calibrate.py [--stats dev/baseline/stats.json] [--write]
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "skills", "techblog", "scripts"))
import lint_ko as L  # noqa: E402

THRESHOLDS = os.path.join(ROOT, "skills", "techblog", "scripts", "thresholds.json")
REPORT = os.path.join(ROOT, "dev", "baseline", "calibration.md")
TONES = ("default", "casual")
PERIOD_WEIGHT = {"base": 1.0, "mid": 0.5, "drift": 0.0}
SITE_CAP = 0.40
SITE_CAP_MIN_SITES = 3
SITE_CAP_MIN_ARTICLES = 5
PASS_Q, TAIL_Q = 0.95, 0.995
# 사람 글에는 적용하지 않는 Gate: 사용자 요구로 정한 어투 규칙
TONE_RULES = ("G4.off_tone", "G4.banned_ending")
# 2025년 이후 글에서 함께 높아진 AI 문체 지표(rubric.md "사람 글 측정에서 확인한 것")
AI_METRICS = ("A1.np", "A2.connective_comma_ratio", "A3.salience", "A4.para_end", "A5.style_words_per_1k",
              "A9.bold_per_1k", "A10.triad_per_1k", "A13.demonstrative_start_per_1k")
# 기준 기간 전용 항목. 2026-11-02 측정에서 mid(2022-12~2024-12) 글의 중앙값이 base의 p75를 넘은 지표가 있었다:
# A2.connective_comma_ratio(합니다체 0.27, base p75 0.24), A13.demonstrative_start_per_1k(합니다체 0.50 대 0.40,
# 해요체 0.27 대 0.19). A4.para_end(합니다체)는 mid 중앙값 1.0이 base p75와 같았다. 그래서 이 항목들은 base 글로만
# 기준치를 잡고(mid 가중치 0), 문장 길이, 문단, 종결어미 분포처럼 이 묶음에 들지 않는 지표에만 mid를 PERIOD_WEIGHT로 넣는다.
# 6단계 판정의 "AI 문체 항목"(G, A1~A7, A10~A15, T, rubric.md)과 다른 묶음이라 이름을 따로 붙였다.
AI_FAMILIES = ("A1.", "A2.", "A3.", "A4.", "A5.", "A6.", "A7.", "A9.bold", "A9.label_list", "A9.list_ratio",
               "A10.", "A12.", "A13.", "A14.")


def period_weight(mid, period):
    if period == "mid" and mid.startswith(AI_FAMILIES):
        return 0.0
    return PERIOD_WEIGHT[period]


def tone_of(group):
    return group.rsplit("-", 1)[-1]


def period_of(group):
    return group.split("-", 1)[0] if "-" in group else "base"


def wpct(values, weights, q):
    """가중 분위수. 가중치가 모두 같으면 (n-1)q 위치를 선형 보간하는 기존 pct와 같다."""
    pairs = sorted((float(v), float(w)) for v, w in zip(values, weights) if w > 0)
    if not pairs:
        return 0.0
    if len(pairs) == 1:
        return pairs[0][0]
    total = sum(w for _, w in pairs)
    denom = total - pairs[-1][1]
    cum = 0.0
    pts = []
    for v, w in pairs:
        cum += w
        pts.append(((cum - w) / denom, v))
    if q <= 0:
        return pts[0][1]
    if q >= 1:
        return pts[-1][1]
    for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
        if p0 <= q <= p1:
            return v1 if p1 == p0 else v0 + (v1 - v0) * (q - p0) / (p1 - p0)
    return pts[-1][1]


def pct(values, q):
    return wpct(values, [1.0] * len(values), q)


def n_eff(weights):
    s = sum(weights)
    s2 = sum(w * w for w in weights)
    return round(s * s / s2, 1) if s2 else 0.0


def site_factors(pool, mid):
    """pool 안에서 사이트마다 가중치를 줄일 비율. 한 사이트가 SITE_CAP을 넘지 않게 한다."""
    base_w = {}
    counts = {}
    for a in pool:
        w = period_weight(mid, period_of(a["group"]))
        if w <= 0:
            continue
        base_w[a["site"]] = base_w.get(a["site"], 0.0) + w
        counts[a["site"]] = counts.get(a["site"], 0) + 1
    if sum(1 for s, c in counts.items() if c >= SITE_CAP_MIN_ARTICLES) < SITE_CAP_MIN_SITES:
        return {s: 1.0 for s in base_w}
    over = set()
    total = sum(base_w.values())
    for _ in range(len(base_w)):
        free_total = sum(w for s, w in base_w.items() if s not in over)
        total = free_total / (1 - SITE_CAP * len(over)) if over else free_total
        new_over = {s for s, w in base_w.items() if s not in over and w > SITE_CAP * total}
        if not new_over:
            break
        over |= new_over
    return {s: (SITE_CAP * total / w if s in over and w else 1.0) for s, w in base_w.items()}


def weighted(pool, mid):
    """pool의 (값, 가중치) 목록. 값이 없는 글과 이 지표에서 가중치가 0인 글은 뺀다."""
    pool = [a for a in pool if mid in a["metrics"] and period_weight(mid, period_of(a["group"])) > 0]
    f = site_factors(pool, mid)
    return [a["metrics"][mid] for a in pool], [period_weight(mid, period_of(a["group"])) * f[a["site"]]
                                               for a in pool], pool


def calib_articles(arts):
    return [a for a in arts if not a["holdout"] and PERIOD_WEIGHT.get(period_of(a["group"]), 0) > 0
            and tone_of(a["group"]) in TONES]


def is_count_metric(mid, values):
    return all(float(x).is_integer() for x in values) and not mid.endswith(("_ratio", "_per_1k", "_cv", "_mean"))


def round_limit(mid, x, values, up=True):
    if is_count_metric(mid, values):
        return int(math.ceil(x)) if up else int(math.floor(x))
    return round(x, 3)


def upper_limits(mid, vals, ws, extreme=False):
    pm = round_limit(mid, wpct(vals, ws, PASS_Q), vals)
    top = max(wpct(vals, ws, 0.99), max(vals)) if extreme else wpct(vals, ws, TAIL_Q)
    top = top + 1 if is_count_metric(mid, vals) else top * 1.2
    return pm, max(pm, round_limit(mid, top, vals))


def calibrate(stats, template):
    arts = stats["articles"]
    calib = calib_articles(arts)
    new = json.loads(json.dumps(template))
    notes = {}
    for mid, spec in new["metrics"].items():
        extreme = spec.get("bound") == "extreme"
        if "by_tone" in spec and spec.get("kind") == "upper" and not spec.get("fixed"):
            for tone in TONES:
                vals, ws, pool = weighted([a for a in calib if tone_of(a["group"]) == tone], mid)
                if vals:
                    pm, wm = upper_limits(mid, vals, ws, extreme)
                    spec["by_tone"][tone] = {"pass_max": pm, "warn_max": wm, "n": len(vals), "n_eff": n_eff(ws)}
            continue
        kind = spec.get("kind")
        pool = [a for a in calib if (not spec.get("tone") or tone_of(a["group"]) == spec["tone"])
                and a["site"] not in spec.get("exclude_sites", [])]
        vals, ws, pool = weighted(pool, mid)
        if kind == "gate" or spec.get("fixed") or not vals:
            continue
        if kind in ("info", "check"):
            spec["human"] = {"p10": round(wpct(vals, ws, .1), 3), "p50": round(wpct(vals, ws, .5), 3),
                             "p90": round(wpct(vals, ws, .9), 3), "n": len(vals)}
            continue
        if kind == "poisson":
            cnt = sum(w * a["metrics"].get(mid, 0) for a, w in zip(pool, ws))
            chars = sum(w * a["chars"] for a, w in zip(pool, ws))
            spec["rate_per_1k"] = round(cnt / chars * 1000, 3) if chars else spec["rate_per_1k"]
            notes[mid] = (f"가중 pooled {cnt:.1f}회 / {chars:,.0f}자 "
                          f"(글 {len(pool)}편, 가중치 없는 합계 {sum(a['metrics'].get(mid, 0) for a in pool)}회)")
        elif kind == "upper":
            spec["pass_max"], spec["warn_max"] = upper_limits(mid, vals, ws, extreme)
        elif kind == "lower":
            spec["pass_min"] = round_limit(mid, wpct(vals, ws, 1 - PASS_Q), vals, up=False)
            bottom = min(wpct(vals, ws, 0.01), min(vals)) if extreme else wpct(vals, ws, 1 - TAIL_Q)
            spec["warn_min"] = min(spec["pass_min"], round_limit(mid, bottom * 0.8, vals, up=False))
        elif kind == "range":
            spec["pass"] = [round(wpct(vals, ws, 1 - PASS_Q), 3), round(wpct(vals, ws, PASS_Q), 3)]
            lo = min(wpct(vals, ws, 0.01), min(vals)) if extreme else wpct(vals, ws, 1 - TAIL_Q)
            hi = max(wpct(vals, ws, 0.99), max(vals)) if extreme else wpct(vals, ws, TAIL_Q)
            spec["warn"] = [round(lo * 0.8, 3), round(hi * 1.2, 3)]
        spec["n"] = len(vals)
        spec["n_eff"] = n_eff(ws)
    try:
        commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True).stdout.strip()
    except OSError:
        commit = ""
    n_by = {(p, t): sum(1 for a in calib if period_of(a["group"]) == p and tone_of(a["group"]) == t)
            for p in ("base", "mid") for t in TONES}
    new["version"] = "v2"
    new["generated_at"] = time.strftime("%Y-%m-%d")
    new["basis"] = (f"사람 글 baseline(dev/baseline/stats.json, holdout 제외). 기준 기간(2018-01~2022-11, 가중치 1.0) "
                    f"Default {n_by[('base', 'default')]}편, Casual {n_by[('base', 'casual')]}편. "
                    f"중간 기간(2022-12~2024-12, 가중치 {PERIOD_WEIGHT['mid']}) Default {n_by[('mid', 'default')]}편, "
                    f"Casual {n_by[('mid', 'casual')]}편. 기준 기간 전용 항목(A1~A7, A9 굵은 글씨·목록, A10, A12~A14)은 "
                    f"기준 기간 글만 쓴다. 한 사이트의 가중치는 지표마다 {SITE_CAP:.0%} 이하. "
                    f"calibrate.py가 생성. 기준 commit {commit}")
    return new, notes


def judge_article(a, thresholds, skip=()):
    tone = tone_of(a["group"])
    res = {}
    for mid, spec in thresholds["metrics"].items():
        if mid in skip or mid not in a["metrics"] or spec.get("policy"):
            continue
        if spec.get("tone") and spec["tone"] != tone:
            continue
        if "by_tone" in spec:
            spec = dict(spec, **spec["by_tone"].get(tone, {}))
        status, _ = L.judge(a["metrics"][mid], spec, a["chars"])
        if spec.get("min_chars") and a["chars"] < spec["min_chars"] and status != "GATE":
            status = "INFO"
        res[mid] = status
    gate = sum(1 for s in res.values() if s == "GATE")
    fail = sum(1 for s in res.values() if s == "FAIL")
    warn = sum(1 for s in res.values() if s == "WARN")
    verdict = "PASS" if gate == 0 and fail == 0 and warn <= thresholds.get("max_warn", 3) else "FAIL"
    return verdict, res


def holdout_rate(arts, thresholds):
    hold = [a for a in arts if a["holdout"]]
    passed = 0
    by_site = {}
    stat_count = {}
    for a in hold:
        verdict, res = judge_article(a, thresholds)
        ok = verdict == "PASS"
        passed += ok
        s = by_site.setdefault(a["site"], [0, 0])
        s[0] += ok
        s[1] += 1
        for mid, st in res.items():
            if st in ("FAIL", "WARN", "GATE"):
                stat_count.setdefault(mid, {"FAIL": 0, "WARN": 0, "GATE": 0})[st] += 1
    return passed, len(hold), by_site, stat_count


def limit_text(spec):
    if spec.get("kind") == "upper":
        return f"{spec.get('pass_max')} / {spec.get('warn_max')}"
    if spec.get("kind") == "lower":
        return f"{spec.get('pass_min')} / {spec.get('warn_min')}"
    if spec.get("kind") == "poisson":
        return f"{spec.get('rate_per_1k')}/1k"
    return "-"


def report(stats, thresholds, notes, old=None):
    arts = stats["articles"]
    groups = stats["groups"]
    sites = sorted({s for g in groups.values() for s in g["sites"]})
    lines = ["# 기준치 계산 보고서", "",
             "`dev/baseline/calibrate.py --write`가 만든 문서다. 손으로 고치지 않는다. 측정 기록과 해석은 "
             "[README.md](README.md)에 있다.", "",
             "- 기간과 그룹: base(2018-01-01~2022-11-30)는 default/casual, mid(2022-12-01~2024-12-31)는 "
             "mid-default/mid-casual, drift(2025-01-01~)는 drift-default/drift-casual이다.",
             f"- 가중치: base {PERIOD_WEIGHT['base']}, mid {PERIOD_WEIGHT['mid']}(기준 기간 전용 항목 "
             f"{', '.join(AI_FAMILIES)}은 0), drift {PERIOD_WEIGHT['drift']}. "
             f"지표 pool마다 한 사이트의 가중치는 {SITE_CAP:.0%} 이하(글 {SITE_CAP_MIN_ARTICLES}편 이상인 사이트가 "
             f"{SITE_CAP_MIN_SITES}개 이상일 때).",
             f"- 경계: PASS는 가중 p{PASS_Q * 100:g}(하한은 p{(1 - PASS_Q) * 100:g}), WARN은 가중 "
             f"p{TAIL_Q * 100:g}(하한은 p{(1 - TAIL_Q) * 100:g}×0.8)에 여유(횟수 +1, 비율 ×1.2). "
             "\"bound\": \"extreme\" 항목은 최댓값과 최솟값을 쓴다.", "",
             "## 그룹", "",
             "| 그룹 | 편수 | holdout | " + " | ".join(sites) + " |",
             "|---|---|---|" + "---|" * len(sites)]
    order = ["default", "casual", "mid-default", "mid-casual", "drift-default", "drift-casual"]
    for g in [x for x in order if x in groups] + sorted(set(groups) - set(order)):
        s = groups[g]
        lines.append(f"| {g} | {s['n']} | {s['holdout']} | " +
                     " | ".join(str(s["sites"].get(x, 0)) for x in sites) + " |")
    keys = ["A1.np", "A2.comma_per_sentence", "A2.connective_comma_ratio", "A3.salience", "A4.para_end",
            "A5.style_words_per_1k", "A6.calque", "A8.sent_len_mean", "A8.sent_len_cv", "A8.long_ratio",
            "A8.ending_top_share", "A8.sentences_per_para", "A8.single_para_ratio", "A9.bold_per_1k",
            "A9.list_ratio", "A9.heading_per_1k", "A10.triad_per_1k", "A11.body_questions",
            "A13.demonstrative_start_per_1k", "A14.translationese_per_1k", "T.kkayo_ratio"]
    present = [g for g in order if g in groups]
    lines += ["", "## 그룹별 분포 (holdout 제외, 가중치 없이 p10 / p50 / p90)", "",
              "| 지표 | " + " | ".join(present) + " |", "|---|" + "---|" * len(present)]
    for k in keys:
        row = [k]
        for g in present:
            vals = [a["metrics"][k] for a in arts if a["group"] == g and not a["holdout"] and k in a["metrics"]]
            row.append(f"{pct(vals, .1):.2f} / {pct(vals, .5):.2f} / {pct(vals, .9):.2f}" if vals else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## AI 문체 지표의 기간별 중앙값", "",
              "기준 기간 전용 항목의 mid 가중치 0은 이 표의 2026-11-02 측정으로 정했다. 가중치는 이 표로 자동으로 "
              "바꾸지 않는다.", "",
              "| 지표 | 어투 | base p50 (p75) | mid p50 | drift p50 |", "|---|---|---|---|---|"]
    for k in AI_METRICS:
        for t in TONES:
            def vals(p):
                return [a["metrics"][k] for a in arts if tone_of(a["group"]) == t and period_of(a["group"]) == p
                        and not a["holdout"] and k in a["metrics"]]
            b, m, d = vals("base"), vals("mid"), vals("drift")
            lines.append(f"| {k} | {t} | {pct(b, .5):.2f} ({pct(b, .75):.2f}) | "
                         f"{pct(m, .5):.2f} | {pct(d, .5):.2f} |" if b else f"| {k} | {t} | - | - | - |")
    lines += ["", "## 사람 글의 Gate 위반 비율 (base 그룹)", "",
              "policy 표시 항목은 이 skill의 출력에만 적용하는 규칙이라 사람 글 판정에서 뺀다.", "",
              "| Gate | 구분 | default | casual |", "|---|---|---|---|"]
    for mid, spec in thresholds["metrics"].items():
        if spec.get("kind") != "gate":
            continue
        row = [mid, "policy" if spec.get("policy") else "사람 글 기준"]
        for g in TONES:
            pool = [a for a in arts if a["group"] == g]
            row.append(f"{sum(1 for a in pool if a['metrics'].get(mid, 0) > 0)}/{len(pool)}")
        lines.append("| " + " | ".join(row) + " |")
    base_arts = [a for a in arts if period_of(a["group"]) == "base" and tone_of(a["group"]) in TONES]
    passed, n_hold, by_site, stat_count = holdout_rate(base_arts, thresholds)
    rate = passed / n_hold if n_hold else 0.0
    lines += ["", "## holdout 검증", "",
              f"기준치를 만들 때 쓰지 않은 base 사람 글 {n_hold}편 중 {passed}편이 통과했다(통과율 {rate:.0%}). "
              "목표는 85% 이상이다. 통과 조건은 skill 출력과 같다(Gate 0, FAIL 0, WARN 3 이하). policy Gate는 뺀다.", "",
              "| 사이트 | 통과 / holdout | 통과율 |", "|---|---|---|"]
    for s in sorted(by_site):
        ok, n = by_site[s]
        lines.append(f"| {s} | {ok}/{n} | {ok / n:.0%}{'' if n >= 10 else ' (10편 미만, 목표 적용 안 함)'} |")
    mid_arts = [a for a in arts if period_of(a["group"]) == "mid"]
    if mid_arts:
        mp, mn, _, _ = holdout_rate(mid_arts, thresholds)
        lines += ["", f"mid holdout은 {mn}편 중 {mp}편이 통과했다({(mp / mn if mn else 0):.0%})."]
    lines += ["", "| 지표 | FAIL | WARN | GATE |", "|---|---|---|---|"]
    for mid, c in sorted(stat_count.items(), key=lambda kv: -(kv[1]["FAIL"] * 3 + kv[1]["GATE"] * 3 + kv[1]["WARN"])):
        lines.append(f"| {mid} | {c['FAIL']} | {c['WARN']} | {c['GATE']} |")
    if old:
        lines += ["", "## 이전 기준치와 새 기준치", "",
                  "upper는 PASS 상한 / WARN 상한, lower는 PASS 하한 / WARN 하한, poisson은 1,000자당 비율이다.", "",
                  "| 지표 | 종류 | 이전 | 새 기준 | n | 유효 n |", "|---|---|---|---|---|---|"]
        for mid, spec in thresholds["metrics"].items():
            o = old["metrics"].get(mid, {})
            if spec.get("kind") not in ("upper", "lower", "poisson") or spec.get("fixed"):
                continue
            if "by_tone" in spec:
                for t, bt in spec["by_tone"].items():
                    ob = (o.get("by_tone") or {}).get(t, {})
                    lines.append(f"| {mid} ({t}) | upper | {ob.get('pass_max')} / {ob.get('warn_max')} | "
                                 f"{bt.get('pass_max')} / {bt.get('warn_max')} | {bt.get('n')} | {bt.get('n_eff')} |")
                continue
            lines.append(f"| {mid} | {spec['kind']} | {limit_text(o)} | {limit_text(spec)} | {spec.get('n')} | "
                         f"{spec.get('n_eff')} |")
    if notes:
        lines += ["", "## pooled rate", ""] + [f"- {k}: {v}" for k, v in notes.items()]
    return "\n".join(lines) + "\n", rate


def main():
    L.setup_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default=os.path.join(ROOT, "dev", "baseline", "stats.json"))
    ap.add_argument("--write", action="store_true", help="thresholds.json과 calibration.md를 덮어쓴다")
    args = ap.parse_args()
    stats = json.load(open(args.stats, encoding="utf-8"))
    template = json.load(open(THRESHOLDS, encoding="utf-8"))
    new, notes = calibrate(stats, template)
    text, rate = report(stats, new, notes, old=template)
    print(text)
    if args.write:
        with open(THRESHOLDS, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(new, ensure_ascii=False, indent=2) + "\n")
        with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"[write] {THRESHOLDS}, {REPORT}")


if __name__ == "__main__":
    main()
