---
name: brief
description: 전달받은 자료(파일, PDF, URL, 붙여넣은 텍스트)나 대화의 내용을 자연스러운 한국어로 요약한다. 자료의 결론을 첫 문장에 쓰고 핵심 수치를 조건과 함께 남기며 자료에 없는 내용은 덧붙이지 않는다. 분량(한 줄, 한 문단, 자세히)과 어투(합니다체, 해요체, 해라체, 사용자가 직접 정한 어투)를 선택할 수 있고 요약은 대화에 답하거나 파일로 저장한다. 사실 대조, 검사 스크립트, 독립 읽기 점검으로 AI 문체 패턴과 어색한 문장을 줄인다. "$brief", "/brief", "요약해줘", "핵심만 정리해줘", "세 줄로 줄여줘" 같은 요청에 사용한다.
license: MIT
allowed-tools: Read Write Edit Glob Grep WebFetch WebSearch Agent Bash(python "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
metadata:
  version: "0.5.0"
  repository: https://github.com/KANG-YEONWOOK/K-Writer
---

# brief

이 스킬은 사용자가 요약을 요청한 자료나 내용을 읽고 한국어 요약을 쓴다. 기본 독자는 자료를 읽지 않았고 자료가 대상으로 삼은 독자와 같은 수준의 지식이 있는 사람이다. 독자는 요약만 읽어도 자료가 무엇을 말하는지 알 수 있어야 한다. 기준 글은 사람이 자료를 읽고 쓴 한국어 요약이다. 요약의 첫 문장에는 자료의 결론을 쓴다. 요약에 쓰는 사실은 자료에서만 가져오고 요약하는 사람의 평가, 해석, 전망은 덧붙이지 않는다. 분량은 요약의 조건이라서 정한 분량을 넘기지 않는다. 분량 안에 다 넣을 수 없으면 사실의 수를 줄이고, 남긴 문장의 주어, 목적어, 수치의 조건은 그대로 쓴다. 독자가 문장의 의미를 다시 따져 보지 않고 한 번에 이해할 수 있게 한 문장에는 사실을 하나나 둘만 쓴다. 서술어는 사람이 쓴 한국어 글에서 그 주어, 목적어와 함께 사용하는 표현을 쓴다.

Claude Code와 Codex에서 사용한다. 먼저 [실행 환경 안내](references/runtime.md)를 읽고 현재 환경의 입력, 도구, 스킬 경로를 확인한다.

Claude Code 호출 인자: $ARGUMENTS

Codex에서는 `$brief`와 함께 보낸 사용자 요청을 입력으로 받는다. `$ARGUMENTS`가 치환되지 않았거나 자연어로 호출했다면 현재 사용자 요청에서 자료와 옵션을 읽는다.

## 인자와 설정

먼저 [settings.md](references/settings.md)를 읽고 인자(`default`/`casual`/`plain`, `-o`, `--keep-work`, `--defaults`)를 해석한다. 요약할 자료가 요청에도 대화에도 없으면 먼저 대화에서 요청하고 답을 기다린다. 분량과 어투 중 요청에 없는 값은 subagent를 띄우기 전에 한 번에 묻고 값을 정한 뒤 자료를 읽는다. 질문할 수 없으면 분량과 어투는 기본값을 사용하고 보고한다.

## 파일

- 요약은 대화에 답한다. `-o <경로>`가 있으면 그 파일에도 저장한다.
- 작업 파일은 `-o`가 있으면 출력 파일과 같은 폴더에, 없으면 현재 작업 디렉터리에 만든다. `<이름>`은 자료의 주제를 나타내는 영문 kebab-case 이름이다. fact sheet는 `<이름>.facts.md`, 합니다체 요약 초안은 `<이름>.draft.md`다. 5단계에서 스크립트가 점검 전 초안을 `<이름>.unrevised.md`에 복사하고 `<이름>.repeats.md`도 함께 만든다. 어투를 바꾼 요약은 `<이름>.answer.md`에 저장해 검사한다. 작업 파일은 7단계에서 삭제한다.

## 작업 순서와 필수 문서

아래 문서는 각 단계의 실행 지침이다. 단계를 시작하기 전에 지정한 문서를 끝까지 읽는다. 작업 문서가 일부 섹션만 읽으라고 정한 문서는 그 섹션만 읽는다. 모든 `references/`와 `scripts/`는 이 `SKILL.md`가 있는 디렉터리 기준이다. 검사 명령과 실행 오류 처리도 [runtime.md](references/runtime.md)를 따른다.

1. [drafting.md](references/drafting.md)를 읽고 1~3단계를 수행한다. 자료 읽기, fact sheet 작성, 합니다체 요약 초안 작성 순서다. 어떤 어투로 요청받아도 먼저 합니다체로 쓴다. [genre.md](references/genre.md)는 2단계에서, [style-guide.md](references/style-guide.md)는 3단계에서 읽고 AI 패턴 문서는 초안 작성 전에 읽지 않는다.
2. [validation.md](references/validation.md)를 읽고 4~7단계를 수행한다. 요약 점검(문체 검사, fact sheet 대조, 분량, [rubric.md](references/rubric.md)의 판정 항목), 독립 읽기 점검(요약만 읽는 subagent의 보고를 받아 직접 수정), 어투 적용, 출력과 보고 순서다. [ai-patterns.md](references/ai-patterns.md)와 [korean-review.md](references/korean-review.md)는 검출되거나 지적된 항목이 있을 때 그 항목의 섹션만 읽고, [tone.md](references/tone.md)는 어투를 적용할 때 읽는다.
