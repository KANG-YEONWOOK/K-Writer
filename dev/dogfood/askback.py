#!/usr/bin/env python3
"""Blind sentence-level judge for short Korean texts (summaries, notices, reports).

The judge reads only the text, restates every sentence, and decides whether a reader who has not read the source can
restate what the sentence says or has to ask the writer back ("무엇을 무엇으로 바꿨나요?"). The same judge runs on skill
outputs and on human-written texts, so the human rate is the control. It was added after the 2026-11-11 user review:
the clarity judge of judge.py asks what a sentence is about, and the reviewed sentence had a subject.

Usage
  python dev/dogfood/askback.py --out <work>/judge --label after <file.md> [<file.md> ...] [--model opus] [--runs 2]
  python dev/dogfood/askback.py --report <work>/judge/after.json [--show]
Each file is judged on its own. Results go to <out>/<label>.json.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "skills", "brief", "scripts"))
import lint_ko as L  # noqa: E402

DEFAULT_READER = "이 글이 다루는 분야의 지식은 있지만 원래 자료를 읽지 않았고 그 자료를 만든 팀의 사정도 모르는 사람"
VERDICTS = ["clear", "ask_back", "two_readings", "awkward"]
SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "integer"},
        "restated": {"type": "string"},
        "verdict": {"type": "string", "enum": VERDICTS},
        "phrase": {"type": "string"},
        "question": {"type": "string"}},
        "required": ["id", "restated", "verdict", "phrase", "question"]}}},
    "required": ["items"]}

PROMPT = """현재 폴더의 items.md에는 한국어 글 한 편의 문장이 번호와 함께 있습니다. 글 전체가 items.md에 순서대로 들어 있고, 이 글이 요약하거나 정리한 원래 자료는 볼 수 없습니다. 독자는 {reader}입니다. Read 도구로 items.md를 끝까지 읽고, 이 독자의 입장에서 모든 번호의 문장을 하나씩 판정하세요. 앞에 나온 문장은 읽은 것으로 간주합니다.

문장마다 먼저 restated에 그 문장이 전하는 일을 이 독자가 다른 사람에게 설명하듯 자기 말로 다시 적습니다. 문장의 단어를 그대로 옮겨 적지 말고, 누가(무엇이) 무엇을 어떻게 했는지나 무엇이 어떤 값이고 어떤 상태인지를 구체적으로 적습니다. 이 글에 없는 내용은 짐작해서 채우지 않습니다. 구체적으로 적을 수 없는 부분은 "(알 수 없음: 무엇을 무엇으로 바꿨는지)"처럼 괄호로 표시합니다. 그다음 넷 중 하나를 선택하세요. restated에 "(알 수 없음"이 있으면 clear가 아닙니다.
- clear: 이 문장이 전하는 일을 자기 말로 다시 설명할 수 있다. 누가(무엇이) 무엇을 어떻게 했는지, 무엇이 어떤 상태인지가 이 문장과 앞 문장들에 있다.
- ask_back: 단어는 다 알지만 문장이 전하는 내용을 구체적으로 말할 수 없어서 글쓴이에게 되물어야 한다. 구체적인 내용 대신 범주를 나타내는 말(내용, 방식, 부분, 값, 기준, 범위, 구성, 문제, 결과, 사항, 몇 가지)만 있는 문장, 바꿨다, 정했다, 수정했다, 개선했다고만 하고 무엇을 무엇으로 바꿨는지 없는 문장, 구분만 하고("A가 아니라 B다", "A와 다르다") 그 구분이 구체적으로 무엇을 의미하는지 알 수 없는 문장, 가리키는 대상이 이 글에 없는 구절(그 테스트, 2차, 위 조건)이 여기에 해당한다.
- two_readings: 수식 범위, 비교 대상, 부정의 범위, 생략된 주어 때문에 두 가지 이상으로 읽힌다.
- awkward: 내용은 알 수 있지만 사람이 쓴 한국어 글에 그대로 실리면 어색한 표현이 있다. 주어나 목적어와 함께 사용하지 않는 서술어, 영어를 단어 그대로 옮긴 표현, 번역투, 사람이 쓴 글이 다른 단어로 부르는 표현, 조사나 어순이 어색한 구절이 여기에 해당한다.

판정 기준:
- 분야의 전문 용어를 설명하지 않았다는 것은 이유가 아닙니다. 독자는 그 분야의 용어를 압니다. 다만 이 글이나 원래 자료 안에서만 통하는 이름과 줄임 표현은 독자가 모릅니다.
- 더 자세히 알고 싶은 것은 이유가 아닙니다. 문장이 한 말 자체를 구체적으로 다시 말할 수 없을 때만 ask_back입니다.
- 한 문장에 둘 이상 해당하면 ask_back, two_readings, awkward 순서로 먼저 해당하는 것을 선택합니다.
clear가 아니면 phrase에 문제가 되는 구절을 문장에서 그대로 옮겨 적고, question에 독자가 되묻게 되는 질문이나 어색한 이유를 한 문장으로 적습니다. clear이면 phrase와 question은 빈 문자열로 둡니다."""


def sentences_of(text):
    """Sentences with inline code and URLs restored. lint_ko masks them with placeholders, which the judge cannot read."""
    a = L.analyze(text)
    codes = [m.group(2) for m in L.INLINE_CODE_RE.finditer(text)]
    urls = [m.group(0) for m in L.URL_RE.finditer(L.INLINE_CODE_RE.sub(" ", text))]
    out, ci, ui = [], 0, 0
    for s in a["_sentences"]:
        def rep(m):
            nonlocal ci, ui
            if m.group(0) == L.PH_CODE:
                ci += 1
                return "`" + codes[ci - 1] + "`" if ci <= len(codes) else ""
            if m.group(0) == L.PH_URL:
                ui += 1
                return urls[ui - 1] if ui <= len(urls) else "URL"
            return ""
        out.append(L.PH_RE.sub(rep, s.text).strip())
    return out


def call_judge(prompt, cwd, model, timeout=900):
    cmd = [shutil.which("claude") or "claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--json-schema", json.dumps(SCHEMA, ensure_ascii=False), "--tools", "Read",
           "--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config", "--allowedTools", "Read"]
    env = dict(os.environ)
    env.update({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
    p = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    out = p.stdout.decode("utf-8", "replace")
    try:
        data = json.loads(out)
    except ValueError:
        return {"error": out[:500] + p.stderr.decode("utf-8", "replace")[:300]}
    so = data.get("structured_output")
    if so is None:
        return {"error": str(data.get("result"))[:500], "_cost": data.get("total_cost_usd")}
    so["_cost"] = data.get("total_cost_usd")
    return so


def judge_file(path, reader, model, runs):
    sents = sentences_of(open(path, encoding="utf-8").read())
    if not sents:
        return {"file": path, "error": "no sentences"}
    work = tempfile.mkdtemp(prefix="askback-")
    with open(os.path.join(work, "items.md"), "w", encoding="utf-8") as f:
        for i, s in enumerate(sents, 1):
            f.write(f"{i}. {s}\n\n")
    results = [call_judge(PROMPT.format(reader=reader), work, model) for _ in range(runs)]
    shutil.rmtree(work, ignore_errors=True)
    rows = []
    for i, s in enumerate(sents, 1):
        votes = [next((x for x in r.get("items", []) if x.get("id") == i),
                      {"verdict": "missing", "phrase": "", "question": ""}) for r in results]
        rows.append({"id": i, "sentence": s, "votes": votes})
    return {"file": path, "chars": len(re.sub(r"\s", "", " ".join(sents))), "sentences": len(sents), "rows": rows,
            "cost": sum((r.get("_cost") or 0) for r in results), "errors": [r["error"] for r in results if "error" in r]}


def report(path, show=False):
    """Print the share of sentences that one run ("any") or every run ("all") flagged."""
    res = json.load(open(path, encoding="utf-8"))
    tot = {"files": 0, "sentences": 0, "ask_any": 0, "ask_all": 0, "two_any": 0, "awkward_any": 0}
    for r in res:
        if "rows" not in r:
            print("오류:", r.get("file"), r.get("error"))
            continue
        tot["files"] += 1
        tot["sentences"] += r["sentences"]
        if show:
            print(f"{os.path.basename(r['file'])}: {r['sentences']}문장")
        for row in r["rows"]:
            vs = [v["verdict"] for v in row["votes"]]
            tot["ask_any"] += "ask_back" in vs
            tot["ask_all"] += all(v == "ask_back" for v in vs)
            tot["two_any"] += "two_readings" in vs
            tot["awkward_any"] += "awkward" in vs
            if show and any(v not in ("clear", "missing") for v in vs):
                print(f"  {vs} {row['sentence'][:120]}")
                for v in row["votes"]:
                    if v["verdict"] not in ("clear", "missing"):
                        print(f"      [{v['verdict']}] {v['phrase'][:60]} → {v['question'][:140]}")
    n = max(tot["sentences"], 1)
    print(f"{os.path.basename(path)}: 글 {tot['files']}편, {tot['sentences']}문장 | ask_back 한 번 이상 {tot['ask_any']}"
          f"({tot['ask_any'] / n:.1%}), 모든 실행 {tot['ask_all']}({tot['ask_all'] / n:.1%}) | two_readings "
          f"{tot['two_any']}({tot['two_any'] / n:.1%}) | awkward {tot['awkward_any']}({tot['awkward_any'] / n:.1%})")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--label")
    ap.add_argument("--report", nargs="*", help="result files to summarize")
    ap.add_argument("--show", action="store_true", help="with --report, also print the flagged sentences")
    ap.add_argument("--reader", default=DEFAULT_READER)
    ap.add_argument("--model", default="opus")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    if args.report:
        for path in args.report:
            report(path, args.show)
        return
    if not (args.files and args.out and args.label):
        ap.error("files, --out, and --label are required")
    os.makedirs(args.out, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        res = list(ex.map(lambda p: judge_file(p, args.reader, args.model, args.runs), args.files))
    out = os.path.join(args.out, args.label + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    report(out)


if __name__ == "__main__":
    main()
