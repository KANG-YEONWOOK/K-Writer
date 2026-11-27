---
name: write
description: 전달받은 자료(파일, PDF, URL, 붙여넣은 텍스트)나 주제로 사용자가 정한 목적, 분량, 어투에 맞는 한국어 글을 쓴다. 글의 종류를 미리 정하지 않는 K-Writer의 기본 글쓰기 스킬이고 공지, 보고서, 제안서, 메일과 발표 자료(슬라이드)의 제목과 문구도 쓴다. 요청에 자료나 주제, 목적, 분량, 어투가 없으면 글을 쓰기 전에 사용자에게 묻는다. 합니다체, 해요체, 해라체와 사용자가 직접 정한 어투를 지원하고 사실 대조, 검사 스크립트, 독립 점검으로 AI 문체 패턴과 어색한 문장을 줄인다. "$write", "/write", "이 자료로 글 써줘", "공지문 써줘", "보고서 써줘", "발표 자료 문구 써줘" 같은 요청에 사용한다. 기술 블로그 글은 techblog, 요약은 brief를 사용한다.
license: MIT
allowed-tools: Read Write Edit Glob Grep WebFetch WebSearch Agent Bash(python "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
metadata:
  version: "0.8.1"
  repository: https://github.com/KANG-YEONWOOK/K-Writer
---

# write

이 스킬은 사용자가 전달한 자료나 주제로 사용자가 정한 목적, 분량, 어투에 맞는 한국어 글을 쓴다. K-Writer의 기본 스킬이고 공지, 보고서, 제안서, 메일, 발표 자료의 문구를 쓴다. 기준 글은 사람이 같은 목적으로 쓴 한국어 글이다. 글은 쓰기 전에 설계한다. 글 전체의 핵심 주제, 단위(소주제 하나를 다루는 문단이나 섹션)마다 전할 내용, 문장마다 전할 내용을 차례로 정하고, 정한 문장을 하나씩 쓰면서 문장, 단위, 글 전체 순서로 점검한다. 핵심 주제와 관계없는 내용은 쓰지 않고, 독자에게 필요한 이유, 과정, 값은 줄이지 않고 쓴다. 독자가 모를 용어는 처음 나올 때 설명하고, 문장은 앞 문장과 이어지면서 따로 읽어도 무엇에 대한 내용인지 알 수 있게 쓴다. 제목과 헤딩은 명사나 명사형으로 끝낸다. 글의 사실은 자료와 사용자가 알려 준 내용에서만 가져온다.

Claude Code와 Codex에서 사용한다. 먼저 [실행 환경 안내](references/runtime.md)를 읽고 현재 환경의 입력, 도구, 스킬 경로를 확인한다.

Claude Code 호출 인자: $ARGUMENTS

Codex에서는 `$write`와 함께 보낸 사용자 요청을 입력으로 받는다. `$ARGUMENTS`가 치환되지 않았거나 자연어로 호출했다면 현재 사용자 요청에서 자료와 옵션을 읽는다.

## 인자와 설정

먼저 [settings.md](references/settings.md)를 읽고 인자(`default`/`casual`/`plain`, `-o`, `--keep-work`, `--defaults`, `--quick`)를 해석한다. 글을 쓰려면 자료나 주제, 목적, 분량, 어투 네 값이 필요하다. 요청에 자료나 주제가 없으면 먼저 대화에서 요청하고 답을 기다린다. 목적, 분량, 어투 중 요청에 없는 값은 한 번에 묻는다. 네 값을 모두 정한 뒤에 자료를 읽는다. 질문할 수 없으면 목적, 분량, 어투는 기본값을 사용하고 보고한다.

## 파일

- 글은 `<이름>.md`에 저장한다.
- 작업 파일은 출력 파일과 같은 폴더에 만든다. fact sheet는 `<이름>.facts.md`, 설계 문서는 `<이름>.plan.md`다. 어투가 Default가 아니면 Default 초안을 `<이름>.draft.md`에 작성한다. 검사 스크립트는 검사한 글의 복사본을 `<점검 대상 이름>.checked.md`에 저장한다. 작업 파일은 8단계에서 삭제한다.
- 점검 대상은 합니다체 글이다. Default 글이면 출력 파일 `<이름>.md`, 그 밖의 어투면 Default 초안 `<이름>.draft.md`다.

## 작업 순서와 필수 문서

단계마다 지정한 문서만 읽는다. 일부 섹션만 읽으라고 정한 문서는 그 섹션만 읽는다. 모든 `references/`와 `scripts/`는 이 `SKILL.md`가 있는 디렉터리 기준이다.

1. [drafting.md](references/drafting.md)를 읽고 1~4단계를 수행한다. 자료 읽기, fact sheet 작성, 설계, 문장 쓰기와 단위 점검 순서다. 어떤 어투로 요청받아도 먼저 합니다체로 쓴다. [genre.md](references/genre.md)는 2단계에서, [style-guide.md](references/style-guide.md)와 [planning.md](references/planning.md)는 3단계에서 읽는다. 자료가 영어이거나 자료의 주장을 옮기는 글이면 [style-sources.md](references/style-sources.md)도 3단계에서 읽는다. 3단계의 설계 문서를 쓰지 않고 4단계로 넘어가지 않는다. AI 패턴 문서는 초안 작성 전에 읽지 않는다.
2. [validation.md](references/validation.md)와 [checking.md](references/checking.md)를 읽고 5~8단계를 수행한다. 글 전체 검사와 설계 대조, 자료 대조, 독립 점검, 수정한 부분 확인, 어투 적용, 결과 보고 순서다. 글 전체는 검사 스크립트와 독립 점검이 한 번씩만 확인하고 그 뒤에는 수정한 문장과 그 앞뒤 세 문장씩만 다시 확인한다. [ai-patterns.md](references/ai-patterns.md), [korean-review.md](references/korean-review.md), [revision.md](references/revision.md)는 검출되거나 지적된 항목이 있을 때 그 항목의 섹션만 읽는다. [tone.md](references/tone.md)는 어투가 Default가 아닐 때 읽는다.
