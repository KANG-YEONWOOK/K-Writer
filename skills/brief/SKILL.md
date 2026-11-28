---
name: brief
description: 전달받은 자료(파일, PDF, URL, 붙여넣은 텍스트)나 대화의 내용을 자연스러운 한국어로 요약한다. 자료의 결론을 첫 문장에 쓰고 핵심 수치를 조건과 함께 남기며 자료에 없는 내용은 덧붙이지 않는다. 분량(한 줄, 한 문단, 자세히)과 어투(합니다체, 해요체, 해라체, 사용자가 직접 정한 어투)를 선택할 수 있고 요약은 대화에 답하거나 파일로 저장한다. 사실 대조, 검사 스크립트, 독립 읽기 점검으로 AI 문체 패턴과 어색한 문장을 줄인다. "$brief", "/brief", "요약해줘", "핵심만 정리해줘", "세 줄로 줄여줘" 같은 요청에 사용한다.
license: MIT
allowed-tools: Read Write Edit Glob Grep WebFetch WebSearch Agent Bash(python "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
metadata:
  version: "0.9.2"
  repository: https://github.com/KANG-YEONWOOK/K-Writer
---

# brief

이 스킬은 사용자가 요약을 요청한 자료나 내용을 읽고 한국어 요약을 쓴다. 기본 독자는 자료를 읽지 않았고 자료가 대상으로 삼은 독자와 같은 수준의 지식이 있는 사람이다. 독자는 요약만 읽어도 자료가 무엇을 말하는지 알 수 있어야 한다. 기준 글은 사람이 자료를 읽고 쓴 한국어 요약이다. 요약은 쓰기 전에 핵심 요소를 추출한다. 핵심 요소는 요약에 반드시 들어가야 하는 내용 하나다. 먼저 자료 전체에서 핵심 요소를 추출하고, 분량에 담을 수가 될 때까지 추출한 요소를 합치거나 다시 선택하는 일을 반복한다. 그런 다음 마지막 요소를 하나씩 문장으로 쓰면서 문장, 문단, 요약 전체 순서로 점검한다. 요약의 첫 문장에는 자료의 결론을 쓴다. 요약에 쓰는 사실은 자료에서만 가져오고 요약하는 사람의 평가, 해석, 전망은 덧붙이지 않는다. 분량은 요약에 담는 요소의 수로 맞춘다. 글자 수에 맞추려고 문장을 줄여 쓰지 않고, 요소를 쓴 문장에는 주어, 목적어, 수치의 조건을 모두 쓴다. 바꾼 일과 정한 값은 무엇을 무엇으로 바꿨는지, 누가 어떤 값으로 정했는지까지 써서 독자가 되묻지 않게 한다. 독자가 문장의 의미를 다시 따져 보지 않고 한 번에 이해할 수 있게 한 문장에는 요소 하나만 쓴다. 서술어는 사람이 쓴 한국어 글에서 그 주어, 목적어와 함께 사용하는 표현을 쓴다.

Claude Code와 Codex에서 사용한다. 먼저 [실행 환경 안내](references/runtime.md)를 읽고 현재 환경의 입력, 도구, 스킬 경로를 확인한다.

Claude Code 호출 인자: $ARGUMENTS

Codex에서는 `$brief`와 함께 보낸 사용자 요청을 입력으로 받는다. `$ARGUMENTS`가 치환되지 않았거나 자연어로 호출했다면 현재 사용자 요청에서 자료와 옵션을 읽는다.

## 인자와 설정

먼저 [settings.md](references/settings.md)를 읽고 인자(`default`/`casual`/`plain`, `-o`, `--keep-work`, `--defaults`, `--quick`)를 해석한다. 요약할 자료가 요청에도 대화에도 없으면 먼저 대화에서 요청하고 답을 기다린다. 분량과 어투 중 요청에 없는 값은 한 번에 묻고 값을 정한 뒤 자료를 읽는다. 질문할 수 없으면 분량과 어투는 기본값을 사용하고 보고한다.

## 파일

- 요약은 대화에 답한다. `-o <경로>`가 있으면 그 파일에도 저장한다.
- 작업 파일은 `-o`가 있으면 출력 파일과 같은 폴더에, 없으면 현재 작업 디렉터리에 만든다. `<이름>`은 자료의 주제를 나타내는 영문 kebab-case 이름이다. fact sheet는 `<이름>.facts.md`, 합니다체 요약 초안은 `<이름>.draft.md`다. 핵심 요소는 fact sheet에 적는다. 검사 스크립트는 검사한 초안의 복사본을 `<이름>.draft.checked.md`에 저장한다. 어투를 바꾼 요약은 `<이름>.answer.md`에 저장해 검사한다. 작업 파일은 7단계에서 삭제한다.

## 작업 순서와 필수 문서

단계마다 지정한 문서만 읽는다. 일부 섹션만 읽으라고 정한 문서는 그 섹션만 읽는다. 모든 `references/`와 `scripts/`는 이 `SKILL.md`가 있는 디렉터리 기준이다.

1. [drafting.md](references/drafting.md)를 읽고 1~3단계를 수행한다. 자료 읽기, fact sheet 작성, 핵심 요소 추출과 합니다체 요약 초안 작성 순서다. 3단계에서는 fact sheet에 핵심 요소를 차수마다 적고 마지막 차수의 요소를 하나씩 문장으로 쓴다. 문단이 여럿인 요약은 마지막 차수의 요소를 문단마다 묶은 뒤에 쓴다. 어떤 어투로 요청받아도 먼저 합니다체로 쓴다. [genre.md](references/genre.md)는 2단계에서, [style-guide.md](references/style-guide.md)와 [planning.md](references/planning.md)의 지정한 섹션은 3단계에서 읽고 AI 패턴 문서는 초안 작성 전에 읽지 않는다.
2. [validation.md](references/validation.md)와 [checking.md](references/checking.md)를 읽고 4~7단계를 수행한다. 요약 전체 검사와 핵심 요소 대조, 자료 대조, 독립 점검, 수정한 부분 확인, 어투 적용, 출력과 보고 순서다. 요약 전체는 검사 스크립트와 독립 점검이 한 번씩만 확인하고 그 뒤에는 수정한 문장만 다시 확인한다. [ai-patterns.md](references/ai-patterns.md)와 [korean-review.md](references/korean-review.md)는 검출되거나 지적된 항목이 있을 때 그 항목의 섹션만 읽고, [tone.md](references/tone.md)는 어투를 적용할 때 읽는다.
