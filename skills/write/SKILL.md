---
name: write
description: 전달받은 자료(파일, PDF, URL, 붙여넣은 텍스트)나 주제로 사용자가 정한 목적, 분량, 어투에 맞는 한국어 글을 쓴다. 글의 종류를 미리 정하지 않는 K-Writer의 기본 글쓰기 스킬이다. 요청에 자료나 주제, 목적, 분량, 어투가 없으면 글을 쓰기 전에 사용자에게 묻는다. 합니다체, 해요체, 해라체와 사용자가 직접 정한 어투를 지원하고 사실 대조, 검사 스크립트, 독립 점검으로 AI 문체 패턴과 어색한 문장을 줄인다. "$write", "/write", "이 자료로 글 써줘", "공지문 써줘", "소개 글 작성해줘" 같은 요청에 사용한다. 기술 블로그 글은 techblog, 요약은 brief를 사용한다.
license: MIT
allowed-tools: Read Write Edit Glob Grep WebFetch WebSearch Agent Bash(python "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
metadata:
  version: "0.5.0"
  repository: https://github.com/KANG-YEONWOOK/K-Writer
---

# write

이 스킬은 사용자가 전달한 자료나 주제로 사용자가 정한 목적, 분량, 어투에 맞는 한국어 글을 쓴다. K-Writer의 기본 스킬이다. techblog와 brief는 글의 목적, 어투 선택지, 구성을 미리 정해 둔 스킬이고 write는 이 값을 사용자에게 받는다. 기준 글은 사람이 같은 목적으로 쓴 한국어 글이다. 독자가 문장의 의미를 다시 따져 보지 않고 한 번에 이해할 수 있게 쓴다. 독자가 모를 용어는 처음 나올 때 무엇인지 설명한다. 모든 문장은 따로 읽어도 무엇에 대한 내용인지 알 수 있어야 한다. 서술어는 사람이 쓴 한국어 글에서 그 주어, 목적어와 함께 사용하는 표현을 쓴다. 글의 사실은 자료와 사용자가 알려 준 내용에서만 가져온다.

Claude Code와 Codex에서 사용한다. 먼저 [실행 환경 안내](references/runtime.md)를 읽고 현재 환경의 입력, 도구, 스킬 경로를 확인한다.

Claude Code 호출 인자: $ARGUMENTS

Codex에서는 `$write`와 함께 보낸 사용자 요청을 입력으로 받는다. `$ARGUMENTS`가 치환되지 않았거나 자연어로 호출했다면 현재 사용자 요청에서 자료와 옵션을 읽는다.

## 인자와 설정

먼저 [settings.md](references/settings.md)를 읽고 인자(`default`/`casual`/`plain`, `-o`, `--keep-work`, `--defaults`)를 해석한다. 글을 쓰려면 자료나 주제, 목적, 분량, 어투 네 값이 필요하다. 요청에 자료나 주제가 없으면 먼저 대화에서 요청하고 답을 기다린다. 목적, 분량, 어투 중 요청에 없는 값은 subagent를 띄우기 전에 한 번에 묻는다. 네 값을 모두 정한 뒤에 자료를 읽는다. 질문할 수 없으면 목적, 분량, 어투는 기본값을 사용하고 보고한다.

## 파일

- 글은 `<이름>.md`에 저장한다.
- 작업 파일은 출력 파일과 같은 폴더에 만든다. fact sheet는 `<이름>.facts.md`다. 어투가 Default가 아니면 Default 초안을 `<이름>.draft.md`에 작성한다. 6단계를 시작할 때 스크립트가 점검 전 초안을 `<이름>.unrevised.md`에 복사하고 반복 후보를 `<이름>.repeats.md`에 적는다. 독자 점검 결과는 `<이름>.reader.md`, 수정 후 검토의 점검 목록은 `<이름>.audit.md`, 지적을 반영하기 전 글의 복사본은 `<이름>.pre-fix.md`다. 작업 파일은 8단계에서 삭제한다.
- 독립 점검 대상은 합니다체 글이다. Default 글이면 출력 파일 `<이름>.md`, 그 밖의 어투면 Default 초안 `<이름>.draft.md`다.

## 작업 순서와 필수 문서

아래 문서는 각 단계의 실행 지침이다. 단계를 시작하기 전에 지정한 문서를 끝까지 읽는다. 작업 문서가 일부 섹션만 읽으라고 정한 문서는 그 섹션만 읽는다. 도구 출력이 잘리면 나머지를 나눠 읽는다. 모든 `references/`와 `scripts/`는 이 `SKILL.md`가 있는 디렉터리 기준이다. 검사 명령과 실행 오류 처리도 [runtime.md](references/runtime.md)를 따른다.

1. [drafting.md](references/drafting.md)를 읽고 1~4단계를 수행한다. 자료 읽기, fact sheet 작성, 개요, Default 초안 작성 순서다. 어떤 어투로 요청받아도 먼저 합니다체로 쓴다. [genre.md](references/genre.md)는 2단계에서, [style-guide.md](references/style-guide.md)는 3단계에서 읽고 AI 패턴 문서는 초안 작성 전에 읽지 않는다.
2. [validation.md](references/validation.md)를 읽고 5단계를 수행한다. 문체 검사, 문장별 단독 읽기, fact sheet 대조, [rubric.md](references/rubric.md)의 판정 항목 점검을 한다. [ai-patterns.md](references/ai-patterns.md)는 이 단계에서 검출된 항목이 있을 때 그 항목의 섹션을 읽는다.
3. [finalization.md](references/finalization.md)를 읽고 6~8단계를 수행한다. [reader-check.md](references/reader-check.md)에 따른 독자 점검, [revision.md](references/revision.md)에 따른 후처리, [korean-review.md](references/korean-review.md)에 따른 한국어 문장 점검(도구가 없으면 직접 수행), 어투 적용, 작업 파일 정리와 결과 보고 순서다. 어투를 적용할 때 [tone.md](references/tone.md)를 읽는다.
