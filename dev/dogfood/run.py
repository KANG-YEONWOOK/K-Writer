#!/usr/bin/env python3
"""Run the installed techblog skill with headless Claude Code (`claude -p`) and collect dogfooding results.

- Runs with the user's ~/.claude/CLAUDE.md and auto memory turned off (CLAUDE_CODE_DISABLE_CLAUDE_MDS=1), so the
  conditions match another user who has installed only the skill.
- Source files are copied into the run folder. The original folder is not opened with --add-dir.
- Output under <work>/<iter>/<case>/: article.md, work files, run.jsonl (stream-json), run.err, meta.json

Usage
  python dev/dogfood/run.py --cases dev/dogfood/cases.json --iter iter-1 [--only A B] [--jobs 2]
  python dev/dogfood/run.py --iter iter-11r --revise-from iter-11 [--only B] [--jobs 1]
    (A new session runs only step 6 post-processing on the draft copy of each iter-11 case. Result case names match
    the original cases.)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_DIR = os.path.join(ROOT, "skills", "techblog")
DEFAULT_WORK = os.path.join(os.environ.get("TEMP", "/tmp"), "techblog-work", "dogfood")
BASELINE_PROMPT = ("{src} 자료의 핵심 내용을 한국어 기술 블로그 아티클로 정리해서 article.md 파일로 저장해줘. "
                   "어투는 {tone_ko}로 써줘.")
# revise mode: a new session, without the context of the session that wrote the draft, runs only step 6 (post-processing).
REVISE_PROMPT = """현재 폴더의 article.md는 techblog 스킬이 1~5단계(초안 작성과 점검)를 마친 합니다체 초안이다. 이 글에는 techblog 스킬의 6단계(후처리)만 실행한다. 어투 변환과 작업 파일 삭제는 하지 않는다.
- 스킬 폴더: {skill}
- 자료: {src}
- fact sheet: article.facts.md
절차는 {skill}/references/finalization.md의 "### 6. 후처리" 섹션과 {skill}/references/revision.md를 따른다. 스크립트는 python "{skill}/scripts/revise_ko.py" start "article.md"처럼 한 번에 명령 하나씩 Bash로 실행한다. 끝나면 수정한 문장 수와 check 결과를 짧게 보고한다."""


def build_revise(case, run_dir, skill_dir=SKILL_DIR):
    """Copy the draft copy, fact sheet, and source from a case in another iteration, and build a prompt that runs only
    post-processing."""
    work = os.path.dirname(os.path.dirname(os.path.dirname(run_dir)))
    src_dir = os.path.join(work, "dogfood", case["revise_from"])
    shutil.copyfile(os.path.join(src_dir, "article.unrevised.md"), os.path.join(run_dir, "article.md"))
    if os.path.exists(os.path.join(src_dir, "article.facts.md")):
        shutil.copyfile(os.path.join(src_dir, "article.facts.md"), os.path.join(run_dir, "article.facts.md"))
    src_arg = case.get("source", "")
    local = case.get("source_local")
    if local:
        local = local.replace("{work}", work)
        shutil.copyfile(local, os.path.join(run_dir, "source" + os.path.splitext(local)[1]))
        src_arg = "./source" + os.path.splitext(local)[1]
    else:
        inputs = [f for f in os.listdir(src_dir) if f.startswith("input.")]
        if inputs:
            shutil.copyfile(os.path.join(src_dir, inputs[0]), os.path.join(run_dir, inputs[0]))
            src_arg = "./" + inputs[0]
    prompt = REVISE_PROMPT.format(skill=skill_dir, src=src_arg)
    extra = ["--disable-slash-commands", "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "WebFetch",
             "Bash(python *)"]
    return prompt, extra


def build(case, run_dir):
    """Build the prompt and extra CLI arguments from the case settings."""
    if case.get("mode") == "revise":
        return build_revise(case, run_dir, case.get("skill_dir") or SKILL_DIR)
    src = case.get("source")
    if src and not src.startswith(("http://", "https://")):
        src = src.replace("{work}", os.path.dirname(os.path.dirname(os.path.dirname(run_dir)))).replace("{root}", ROOT)
        src = src.replace("{last}", os.environ.get("TECHBLOG_LAST_ITER", "iter-1"))
        if not os.path.isabs(src):
            src = os.path.join(ROOT, src)
    src_arg = src
    if src and not src.startswith(("http://", "https://")):
        name = "input" + os.path.splitext(src)[1]
        shutil.copyfile(src, os.path.join(run_dir, name))
        src_arg = "./" + name
    tone = case.get("tone", "default")
    # The skill asks for settings the request leaves out (reader, tone, length). A headless run has nobody to answer,
    # so --defaults makes it use the default values. A "settings": "ask" case runs without the tone and --defaults to
    # check that the skill proceeds with the defaults when it cannot ask.
    ask = case.get("settings") == "ask"
    tone_arg = "" if ask else f"{tone} "
    defaults = "" if ask else " --defaults"
    extra = []
    if case.get("mode") == "baseline":
        prompt = BASELINE_PROMPT.format(src=src_arg, tone_ko="해요체" if tone == "casual" else "합니다체")
        extra.append("--disable-slash-commands")
    elif case.get("mode") == "retone":
        prompt = f"/techblog {tone_arg}--retone {src_arg} -o article.md{defaults}"
    elif case.get("mode") == "pasted":
        with open(src, encoding="utf-8-sig") as f:
            text = f.read()
        prompt = f"/techblog {tone_arg}-o article.md --keep-work{defaults}\n\n{text}"
        os.remove(os.path.join(run_dir, "input" + os.path.splitext(src)[1]))
    else:
        prompt = f"/techblog {tone_arg}{src_arg} -o article.md --keep-work{defaults}"
    if case.get("allowed_tools"):
        # A baseline run has no skill, so it has no skill allowed-tools. WebFetch must be allowed separately to read a URL.
        extra += ["--allowedTools"] + case["allowed_tools"]
    return prompt, extra


def run_case(case, iter_dir, model, effort, budget, timeout):
    run_dir = os.path.join(iter_dir, case["name"])
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir)
    prompt, extra = build(case, run_dir)
    cmd = [shutil.which("claude") or "claude", "-p", prompt,
           "--model", case.get("model", model), "--effort", case.get("effort", effort),
           "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--strict-mcp-config",
           "--permission-mode", "acceptEdits", "--max-budget-usd", str(budget),
           # Nobody can answer in this run, so remove the settings question tool from context (this checks that the
           # skill uses the defaults instead of asking).
           "--disallowedTools", "AskUserQuestion"] + extra
    env = dict(os.environ)
    env.update({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
    env.pop("PYTHONUTF8", None)
    t0 = time.time()
    with open(os.path.join(run_dir, "run.jsonl"), "wb") as out, open(os.path.join(run_dir, "run.err"), "wb") as err:
        try:
            p = subprocess.run(cmd, cwd=run_dir, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                               timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    meta = {"case": case, "prompt": prompt, "cmd": cmd[3:], "exit": code, "seconds": round(time.time() - t0),
            "claude_version": subprocess.run([cmd[0], "--version"], capture_output=True, text=True).stdout.strip()}
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[{case['name']}] exit={code} {meta['seconds']}s", flush=True)
    return meta


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=os.path.join(ROOT, "dev", "dogfood", "cases.json"))
    ap.add_argument("--iter", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--work", default=DEFAULT_WORK)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--effort", default="xhigh")
    # Budget for a run that starts all four step 6 subagents (reader check, post-processing, Korean sentence review,
    # post-revision review). The 2026-11-02 run spent $6.75 through the reader check, judged that it could not start the
    # remaining three subagents within $8, and cut step 6 short.
    ap.add_argument("--budget", type=float, default=15.0)
    ap.add_argument("--timeout", type=int, default=45 * 60)
    ap.add_argument("--revise-from", help="Build revise mode cases from the draft copies of this iteration")
    ap.add_argument("--skill-dir", help="Skill folder to read in revise mode (use it to pin the instruction version)")
    args = ap.parse_args()
    with open(args.cases, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if args.revise_from:
        src_iter = os.path.join(args.work, args.revise_from)
        cases = []
        for name in sorted(os.listdir(src_iter)):
            d = os.path.join(src_iter, name)
            if not (os.path.isfile(os.path.join(d, "article.unrevised.md")) and os.path.isfile(os.path.join(d, "meta.json"))):
                continue
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                orig = json.load(f)["case"]
            cases.append(dict(orig, mode="revise", tone="default", tone_orig=orig.get("tone", "default"),
                              revise_from=f"{args.revise_from}/{name}", skill_dir=args.skill_dir))
    if args.only:
        cases = [c for c in cases if c["name"] in args.only]
    iter_dir = os.path.join(args.work, args.iter)
    os.makedirs(iter_dir, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        list(ex.map(lambda c: run_case(c, iter_dir, args.model, args.effort, args.budget, args.timeout), cases))


if __name__ == "__main__":
    main()
