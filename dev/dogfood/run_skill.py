#!/usr/bin/env python3
"""Run any K-Writer skill with headless Claude Code (`claude -p`) and collect the outputs.

run.py runs only techblog from an installed copy. This script loads the plugin from a folder with --plugin-dir, so one
checkout can be compared with another (for example a copy of an earlier commit). Each case runs in its own folder with
the user's CLAUDE.md and auto memory turned off.

Output under <out>/<case>/: the skill's files, run.jsonl (stream-json), run.err, meta.json

Usage
  python dev/dogfood/run_skill.py --out <work>/after [--plugin <plugin dir>] [--cases dev/dogfood/cases-brief-write.json]
      [--only b1-release-detail w1-notice-casual] [--jobs 5]
  python dev/dogfood/run_skill.py --summary <work>/after
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_case(case, plugin, out_dir, model, effort, budget, timeout):
    run_dir = os.path.join(out_dir, case["name"])
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir)
    for src in case.get("files", []):
        shutil.copyfile(os.path.join(ROOT, src), os.path.join(run_dir, os.path.basename(src)))
    cmd = [shutil.which("claude") or "claude", "-p", case["prompt"], "--plugin-dir", plugin,
           "--model", case.get("model", model), "--effort", case.get("effort", effort),
           "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--strict-mcp-config",
           "--permission-mode", "acceptEdits", "--max-budget-usd", str(case.get("budget", budget)),
           # Nobody can answer in this run, so the settings question tool is removed.
           "--disallowedTools", "AskUserQuestion"]
    env = dict(os.environ)
    env.update({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
    t0 = time.time()
    with open(os.path.join(run_dir, "run.jsonl"), "wb") as out, open(os.path.join(run_dir, "run.err"), "wb") as err:
        try:
            code = subprocess.run(cmd, cwd=run_dir, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                  timeout=case.get("timeout", timeout)).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    meta = {"case": case, "exit": code, "seconds": round(time.time() - t0), "plugin": plugin}
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[{case['name']}] exit={code} {meta['seconds']}s", flush=True)


def summarize(out_dir):
    """Print one row per case: minutes, cost, subagents, script runs, permission denials, last lint verdict."""
    print("| 케이스 | 분 | 비용 | subagent | lint | revise | tone_check | 권한 거부 | 마지막 문체 검사 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name in sorted(os.listdir(out_dir)):
        path = os.path.join(out_dir, name, "run.jsonl")
        if not os.path.isfile(path):
            continue
        result, counts, verdict = None, {"agent": 0, "lint_ko.py": 0, "revise_ko.py": 0, "tone_check.py": 0}, ""
        for line in open(path, encoding="utf-8"):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("type") == "result":
                result = o
            m = re.findall(r"판정: (PASS|FAIL) \(Gate 위반 (\d+), FAIL (\d+), WARN (\d+)\)", line) if "lint |" in line else None
            if m:
                verdict = "{} G{} F{} W{}".format(*m[-1])
            if o.get("type") != "assistant" or o.get("parent_tool_use_id"):
                continue
            for c in (o.get("message") or {}).get("content") or []:
                if c.get("type") != "tool_use":
                    continue
                if c.get("name") in ("Agent", "Task"):
                    counts["agent"] += 1
                command = (c.get("input") or {}).get("command", "") if c.get("name") == "Bash" else ""
                for script in ("lint_ko.py", "revise_ko.py", "tone_check.py"):
                    counts[script] += script in command
        if not result:
            print(f"| {name} | 결과 없음 | | | | | | | |")
            continue
        print(f"| {name} | {result['duration_ms'] / 60000:.1f} | ${result['total_cost_usd']:.2f} | {counts['agent']} | "
              f"{counts['lint_ko.py']} | {counts['revise_ko.py']} | {counts['tone_check.py']} | "
              f"{len(result.get('permission_denials') or [])} | {verdict} |")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=os.path.join(ROOT, "dev", "dogfood", "cases-brief-write.json"))
    ap.add_argument("--plugin", default=ROOT, help="plugin folder to load (default: this checkout)")
    ap.add_argument("--out")
    ap.add_argument("--summary", help="print the summary table of a finished output folder and exit")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--effort", default="xhigh")
    ap.add_argument("--budget", type=float, default=8.0)
    ap.add_argument("--timeout", type=int, default=40 * 60)
    args = ap.parse_args()
    if args.summary:
        summarize(args.summary)
        return
    if not args.out:
        ap.error("--out is required")
    with open(args.cases, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if args.only:
        cases = [c for c in cases if c["name"] in args.only]
    os.makedirs(args.out, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        list(ex.map(lambda c: run_case(c, os.path.abspath(args.plugin), args.out, args.model, args.effort, args.budget,
                                       args.timeout), cases))
    summarize(args.out)


if __name__ == "__main__":
    main()
