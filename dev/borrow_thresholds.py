#!/usr/bin/env python3
"""Copy calibrated limits from one skill's thresholds.json into skills that have no baseline sample of their own.

A skill without human sample articles reports every calibrated metric as INFO, so its lint would not judge even
the expression items that the plugin exists to reduce (negative parallelism, salience sentences, calques). Until
such a skill has its own baseline, it borrows the limits of the expression items from a calibrated skill.

A skill opts in with a "borrowed" key in its scripts/thresholds.json:

  "borrowed": {"from": "techblog", "metrics": ["A1.np", "A3.salience", ...]}

For each listed metric this script copies the limit fields (LIMIT_FIELDS) from the source skill into the borrowing
skill's "metrics", replacing what was there. Every other key of the file is kept. Only metrics whose count does not
depend on the genre belong in the list: counts of a phrase, word, or sentence pattern. Distribution and format
metrics (sentence length, paragraph shape, list share, comma density, question ratio) do not, because they differ
by genre.

Usage
  python dev/borrow_thresholds.py           # copy into every skill that has "borrowed"
  python dev/borrow_thresholds.py --check   # check that the borrowed limits match the source

Run it again after recalibrating the source skill. Exit codes: 0 OK, 1 --check found a difference, 2 input error
Uses only the standard library (Python 3.8+).
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Fields that set a verdict. Sample sizes and human distributions stay with the skill that measured them.
LIMIT_FIELDS = ("rate_per_1k", "pass_max", "warn_max", "pass_min", "warn_min", "pass", "warn", "by_tone")


def thresholds_path(skill, root=ROOT):
    return os.path.join(root, "skills", skill, "scripts", "thresholds.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def borrowers(root=ROOT):
    """Names of the skills whose thresholds.json has a "borrowed" key."""
    base = os.path.join(root, "skills")
    return [d for d in sorted(os.listdir(base))
            if os.path.isfile(thresholds_path(d, root)) and "borrowed" in load(thresholds_path(d, root))]


def borrowed_limits(skill, root=ROOT):
    """The {metric: limits} a skill should hold according to its "borrowed" key and the source skill."""
    spec = load(thresholds_path(skill, root))["borrowed"]
    source = load(thresholds_path(spec["from"], root))["metrics"]
    out = {}
    for mid in spec["metrics"]:
        limits = {k: v for k, v in (source.get(mid) or {}).items() if k in LIMIT_FIELDS}
        if not limits:
            raise ValueError(f"{spec['from']}에 {mid}의 기준치가 없다")
        out[mid] = limits
    return out


def differences(skill, root=ROOT):
    """Metrics whose limits in the borrowing skill differ from the source. Each item is (metric, held, expected)."""
    held = load(thresholds_path(skill, root)).get("metrics") or {}
    return [(mid, held.get(mid), limits) for mid, limits in borrowed_limits(skill, root).items()
            if {k: v for k, v in (held.get(mid) or {}).items() if k in LIMIT_FIELDS} != limits]


def apply(skill, root=ROOT):
    """Write the borrowed limits into the skill's thresholds.json. Return the metrics that changed."""
    path = thresholds_path(skill, root)
    data = load(path)
    changed = [mid for mid, _, _ in differences(skill, root)]
    metrics = dict(data.get("metrics") or {})
    for mid, limits in borrowed_limits(skill, root).items():
        own = {k: v for k, v in (metrics.get(mid) or {}).items() if k not in LIMIT_FIELDS}
        metrics[mid] = dict(limits, **own)
    data["metrics"] = metrics
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return changed


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Copy borrowed limits into skills without a baseline")
    ap.add_argument("--check", action="store_true", help="Only check that borrowed limits match the source")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        status = 0
        for skill in borrowers():
            if args.check:
                for mid, held, expected in differences(skill):
                    print(f"다름: {skill} {mid}: {held} != {expected}")
                    status = 1
            else:
                changed = apply(skill)
                print(f"{skill}: 가져온 항목 {len(borrowed_limits(skill))}개, 바뀐 항목 {len(changed)}개")
        if args.check and status:
            print("기준치를 다시 보정했으면 python dev/borrow_thresholds.py로 다시 복사한다.")
        elif args.check:
            print(f"가져온 기준치 확인: 스킬 {len(borrowers())}개 모두 같음")
        return status
    except (OSError, ValueError, KeyError) as e:
        print(f"borrow_thresholds 오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
