#!/usr/bin/env python3
"""같은 대상을 부르는 말과 빗댄 말의 횟수를 사람 글, skill 글, 스킬 없이 쓴 AI 글에서 잰다.

plain-terms.md의 표를 만든 도구다. lint_ko.py의 항목과 달리 문장 단위가 아니라 표면형이 나온 횟수를 세고,
lint에 넣지 않은 말과 사람 글이 쓰는 말의 횟수도 함께 출력한다.

- 사람 글: --cache의 md 폴더에서 stats.json에 included로 표시한 글. 기간(base, mid, drift)별 횟수도 출력한다.
- --extra 이름=glob: 비교할 글(skill이 쓴 글, skill 문서). 여러 번 줄 수 있다.
- --sessions DIR: Claude Code 세션 기록 폴더(예: ~/.claude/projects). 모델 이름에 --model 값이 든 assistant의 대화 응답과
  Write 도구로 쓴 .md 내용을 모은다. 프로젝트 폴더 이름에 StudyNote가 있으면 note, K-Writer나 Skill-Techblog가 있으면 뺀다.
  나머지는 dev다. 세션 내용은 파일에 남기지 않고 횟수만 출력한다. 저장소의 표에는 프로젝트 이름을 적지 않는다.

코드 블록, 인라인 코드, URL, HTML 태그, 따옴표 안은 세지 않는다. 비율은 한글 글자 1만 자당 횟수다.

사용법
  python -I dev/baseline/techblog/term_stats.py --cache docs/corpus --sessions ~/.claude/projects \
      --extra "skill=docs/dogfood/*/*/article.md" --extra "skill=examples/*.default.md" [--samples 3]
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
L = r"(?<![가-힣])"
PARTICLE = (r"(?:은|는|이|가|을|를|에서는|에서도|에서|에는|에도|에|의|과|와|으로|로|도|만|까지|부터|보다|입니다|이다|이고|이며|이라)?"
            r"(?=[\s,.)\]:;|]|$)")

# (표에 쓸 이름, 정규식). 앞의 묶음은 lint에 넣은 말, 뒤의 묶음은 비교할 말과 자료가 지목했지만 사람 글에 흔한 말이다.
TERMS = (
    ("판(영어, 숫자 뒤)", rf"(?<![가-힣A-Za-z0-9._+-])(?:[A-Za-z][A-Za-z0-9._+-]*|[0-9]+(?:\.[0-9]+)+|[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})\s?판{PARTICLE}"),
    ("판(수식어 뒤)", rf"{L}(?<!처음부터\s)(?:이전|예전|옛|지난|새|새로운|최신|다음|현재|지금|마지막|수정|고친|수정한|수정된|개정된|공개된|설치된|패치|안정|이번|같은|다른|두|세|네|각|모든|첫|이|그)\s판{PARTICLE}"),
    ("판(N번째)", rf"{L}(?:[0-9]+|첫|두|세|네|다섯|여섯)\s?번째\s판{PARTICLE}"),
    ("버전", rf"{L}버전"),
    ("낱말", rf"{L}낱말"),
    ("단어", rf"{L}단어"),
    ("판본", rf"{L}판본"),
    ("시험(test)", rf"{L}시험(?=\s?(?:실행|운영|환경|코드|결과|케이스|대상|데이터|서버|배포)|했|합니다|한다|하는|한\s|할\s|하면|해\s?(?:봤|보|야)|하지|하고|을\s(?:돌|실행|통과)|이\s(?:통과|실패))"),
    ("시험(전체)", rf"{L}시험"),
    ("테스트", rf"{L}테스트"),
    ("뜻(~는 뜻 제외)", rf"{L}(?<!는\s)(?<!란\s)뜻(?:은|이|을|의|에|으로|입니다|이다|이고|이며|이에요|도|만|과|대로)?(?=[\s,.)\]:;|!?]|$)"),
    ("뜻(전체)", rf"{L}뜻(?:은|이|을|의|에|으로|입니다|이다|이고|이며|이에요|도|만|과|대로)?(?=[\s,.)\]:;|!?]|$)"),
    ("의미", rf"{L}의미(?:는|가|를|의|에|로|입니다|이다|예요|도|만)?(?=[\s,.)])"),
    ("짝", rf"{L}짝(?!수|짝|지)"),
    ("쌍", rf"{L}쌍"),
    ("가운데(이 가운데, N개 가운데)", rf"{L}(?<!화면\s)가운데(?=\s)(?!\s(?:정렬|맞춤|토큰|부분|값|글자|줄|칸|열|행))"),
    ("중(N개 중, 이 중)", rf"[0-9]\s?(?:개|건|편|명|가지)\s중\s|{L}이\s중\s|{L}그\s?중\s"),
    ("세기(강도)", rf"(?<![0-9가-힣])세기(?:를|가)\s(?:정하|조절|판단|높|낮|줄|키우|바꾸|나타내)|의\s세기"),
    ("강도", rf"{L}강도"),
    ("사본", rf"{L}(?<!신분증\s)(?<!등본\s)사본"),
    ("복사본, 복제본", rf"{L}복(?:사|제)본"),
    ("실측", rf"{L}실측"),
    ("측정", rf"{L}측정"),
    ("되풀이", rf"{L}되풀이"),
    ("반복", rf"{L}반복"),
    ("이웃한", rf"{L}이웃(?:한|하는|해|끼리)"),
    ("인접한", rf"{L}인접(?:한|하|해)"),
    ("덮다(cover)", rf"{L}덮(?:습니다|는다|지\s못|지\s않|어야|었|으면)"),
    ("커버하다", rf"{L}커버(?:하|합|해|한|할|했)"),
    ("커버리지", rf"{L}커버리지"),
    ("더하다(add)", r"(?:항목|기능|규칙|문장|설정|테스트|옵션|코드|필드|열|행|컬럼|절|예문|조건|케이스|문서|단계|지침)(?:을|를|도|만)?\s(?:\S+\s)?더(?:했|합니다|한다|하면|해|하고|한\s)"),
    ("추가하다", rf"{L}추가(?:했|합니다|한다|하면|해|하고|한\s|하는)"),
    # lint에 넣지 않은 비교
    ("결함", rf"{L}결함"),
    ("버그", rf"{L}버그"),
    ("갱신", rf"{L}갱신"),
    ("업데이트", rf"{L}업데이트"),
    ("지우다", rf"{L}지(?:웁니다|운다|웠|우면|우고|워|우는|운\s|울\s)"),
    ("삭제하다", rf"{L}삭제(?:했|합니다|한다|하면|해|하고|한\s|하는|됩|된)"),
    ("빼다", rf"{L}(?:뺍니다|뺀다|뺐|빼면|빼고|빼서|빼는|뺀\s|뺄\s)"),
    ("제외하다", rf"{L}제외(?:했|합니다|한다|하면|해|하고|한\s|하는|됩|된)"),
    ("내보내다", rf"내보(?:내|냅|낸|낼)"),
    ("출력하다", rf"{L}출력(?:하|합|해|한|할|했|됩|된|되)"),
    ("돌려주다", rf"{L}돌려(?:줍|주|준|줄|줘|줬)"),
    ("반환하다", rf"{L}반환(?:하|합|해|한|할|했|됩|된|되)"),
    ("헤더", rf"{L}헤더"),
    ("호출하다", rf"{L}호출(?:하|합|해|한|할|했|됩|된|되)"),
    ("섹션", rf"{L}섹션"),
    ("옛", rf"{L}옛\s"),
    ("상한", rf"{L}상한"),
    ("잔여", rf"{L}잔여"),
    ("묶음", rf"{L}묶음"),
    ("N곳", r"[0-9]+\s?곳"),
    # 자료가 지목한 말
    ("못 박다", r"못\s?박(?:아|았|는|습|은)"),
    ("갈리다", r"(?<![헷가-힣])갈(?:립니다|린다|렸|려(?:\s|요|서)|리는|리며|리고|리면)"),
    ("갈래", rf"{L}갈래"),
    ("층위", rf"{L}층위"),
    ("기둥", rf"{L}기둥"),
    ("문턱", rf"{L}문턱"),
    ("쥐다", rf"{L}쥐(?:고|는|어|었|면|며|습|지|도록|려|니)|쥡니다|쥔\s"),
    ("건네다", rf"{L}건네|건넵|건넸|건넨"),
    ("짚다", rf"{L}짚(?:어|고|습|는|은|으|었|자|을|읍)|짚입"),
    ("걷어내다", r"걷어(?:내|냅|낸|낼)"),
    ("덜어내다", r"덜어(?:내|냅|낸|낼)"),
    ("비로소", rf"{L}비로소"),
    ("들여다보다", r"들여다\s?(?:보|봅|봤|본)"),
    ("흩어지다", rf"{L}흩어"),
    ("풀어내다", r"풀어(?:내|냅|낸|낼)"),
    ("끌어올리다", r"끌어올"),
    ("그 자체로", r"그\s자체(?:로|가)"),
    ("솔직히", rf"{L}(?:솔직히|솔직한\s답|정직하게|정직한\s답)"),
)

FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")
URL = re.compile(r"https?://\S+")
HTML = re.compile(r"<[^>]+>")
FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)
QUOTE = re.compile(r'"[^"\n]{0,300}"|“[^”\n]{0,300}”')
HANGUL = re.compile(r"[가-힣]")


def clean(text):
    for rx in (FRONT, FENCE, INLINE, URL, HTML):
        text = rx.sub(" ", text)
    return QUOTE.sub(' "" ', text)


def human_docs(cache, stats_path):
    stats = json.load(open(stats_path, encoding="utf-8"))
    for art in stats["articles"]:
        path = os.path.join(cache, "md", art["id"] + ".md")
        if art.get("included") and os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                yield "human_" + str(art.get("period")), art["id"], clean(f.read())


def session_docs(roots, model):
    """세션 기록에서 AI가 쓴 한국어 글을 모은다. 대화 응답은 세션 단위, 문서는 파일 단위로 묶는다."""
    grouped = defaultdict(list)
    for root in roots:
        root = os.path.expanduser(root)
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".jsonl"):
                    continue
                project = os.path.relpath(dirpath, root).split(os.sep)[0]
                low = project.lower()
                if "k-writer" in low or "skill-techblog" in low or "kwriter" in low:
                    continue
                group = "note" if "studynote" in low else "dev"
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if '"assistant"' not in line or model not in line:
                            continue
                        try:
                            msg = json.loads(line).get("message") or {}
                        except json.JSONDecodeError:
                            continue
                        if msg.get("role") != "assistant" or model not in str(msg.get("model")):
                            continue
                        for block in msg.get("content") or []:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "text":
                                text = block.get("text") or ""
                                if len(HANGUL.findall(text)) >= 40:
                                    grouped[(group, "chat:" + fn)].append(text)
                            elif block.get("type") == "tool_use" and block.get("name") == "Write":
                                inp = block.get("input") or {}
                                if str(inp.get("file_path") or "").lower().endswith((".md", ".mdx", ".txt")):
                                    text = str(inp.get("content") or "")
                                    if len(HANGUL.findall(text)) >= 200:
                                        grouped[(group, "doc:" + str(inp.get("file_path")))] = [text]
    for (group, key), texts in grouped.items():
        yield group, key, clean("\n\n".join(texts))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", required=True, help="measure.py collect로 모은 사람 글 cache")
    ap.add_argument("--stats", default=os.path.join(ROOT, "dev", "baseline", "techblog", "stats.json"))
    ap.add_argument("--sessions", nargs="*", default=[], help="Claude Code 세션 기록 폴더")
    ap.add_argument("--model", default="opus-5-5", help="세션 기록에서 고를 모델 이름의 일부")
    ap.add_argument("--extra", action="append", default=[], help="이름=glob")
    ap.add_argument("--samples", type=int, default=0, help="사람 글과 extra에서 말마다 보여 줄 문맥 수")
    args = ap.parse_args()

    docs = list(human_docs(args.cache, args.stats))
    if args.sessions:
        docs += list(session_docs(args.sessions, args.model))
    extra_names = []
    for spec in args.extra:
        name, pattern = spec.split("=", 1)
        if name not in extra_names:
            extra_names.append(name)
        for path in sorted(glob.glob(pattern if os.path.isabs(pattern) else os.path.join(ROOT, pattern))):
            with open(path, encoding="utf-8", errors="replace") as f:
                docs.append((name, os.path.relpath(path, ROOT), clean(f.read())))

    chars, ndocs = Counter(), Counter()
    for group, _, text in docs:
        chars[group] += len(HANGUL.findall(text))
        ndocs[group] += 1
    human_groups = ("human_base", "human_mid", "human_drift")
    human_chars = sum(chars[g] for g in human_groups)
    columns = [g for g in ("dev", "note", *extra_names) if chars[g]]
    print("집단: " + ", ".join(f"{g} {ndocs[g]}개 한글 {chars[g]:,}자" for g in chars))
    print()
    print("| 말 | 사람 글(글 수) | 기준 기간 | " + " | ".join(columns) + " | 사람 글 1만 자당 | " + " | ".join(f"{c} 1만 자당" for c in columns) + " |")
    print("|---|---|---|" + "---|" * (2 * len(columns) + 1))
    samples = []
    for label, pattern in TERMS:
        rx = re.compile(pattern)
        count, dfs = Counter(), Counter()
        hits = []
        for group, doc_id, text in docs:
            found = list(rx.finditer(text))
            if found:
                count[group] += len(found)
                dfs[group] += 1
                if not group.startswith(("dev", "note")):
                    for m in found[:1]:
                        hits.append((group, doc_id, text[max(0, m.start() - 25):m.end() + 20].replace("\n", " ")))
        human = sum(count[g] for g in human_groups)
        hdf = sum(dfs[g] for g in human_groups)
        rate = human / human_chars * 10000 if human_chars else 0
        cells = [str(count[c]) for c in columns] + [f"{count[c] / chars[c] * 10000:.2f}" for c in columns]
        print(f"| {label} | {human}({hdf}) | {count['human_base']} | " + " | ".join(cells[:len(columns)]) + f" | {rate:.2f} | " + " | ".join(cells[len(columns):]) + " |")
        if args.samples:
            samples.append((label, hits[:args.samples]))
    for label, hits in samples:
        print(f"\n### {label}")
        for group, doc_id, snippet in hits:
            print(f"- {group} {doc_id[:40]}: {snippet}")


if __name__ == "__main__":
    main()
