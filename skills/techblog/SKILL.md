---
name: techblog
description: 전달받은 자료(논문 PDF, 문서 PDF, 마크다운, URL, 붙여넣은 텍스트)를 한국어 기술 블로그 글로 정리하거나 기존 글의 어투를 바꾼다. 토스, 카카오, 당근, 우아한형제들, 네이버 D2 기술 블로그 문체를 참고하고 사실 대조와 검사 스크립트로 AI 문체 패턴을 줄인다. Default(합니다체)와 Casual(해요체)을 지원하며 어투만 바꿀 때 내용은 보존한다. "$techblog", "/techblog", "기술 블로그 글로 정리해줘", "아티클로 써줘", "블로그 포스트로 요약해줘" 같은 요청에 사용한다.
license: MIT
allowed-tools: Read Write Edit Glob Grep WebFetch WebSearch Agent Bash(python "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
metadata:
  version: "0.8.0"
  repository: https://github.com/KANG-YEONWOOK/K-Writer
---

# techblog

이 스킬은 자료를 읽고 핵심을 한국어 기술 블로그 글로 정리한다. 기본 독자는 자료 분야의 지식이 충분하지 않거나 없을 수 있는 사람이다. 글은 토스, 카카오, 당근, 우아한형제들, 네이버 D2 기술 블로그 글처럼 읽혀야 한다. 글은 쓰기 전에 설계한다. 글 전체의 핵심 주제, 섹션과 문단마다 전할 내용, 문장마다 전할 내용을 차례로 정하고, 정한 문장을 하나씩 쓰면서 문장, 섹션, 글 전체 순서로 점검한다. 중심 대상과 생소한 용어는 처음 나올 때 무엇인지 설명한다. 모든 문장은 따로 읽어도 무엇에 대한 내용이고 누구의 주장인지 알 수 있어야 한다. 영어 자료를 옮긴 문장도 기준 글(사람이 쓴 한국어 기술 블로그 글)의 표현으로 쓴다. 서술어는 사람이 쓴 한국어 글에서 그 주어, 목적어와 함께 사용하는 표현을 쓴다. 제목과 헤딩은 명사나 명사형으로 끝낸다. 필요한 주어, 목적어, 조건은 반복하고 요청하지 않은 길이 상한 때문에 생략하지 않는다.

Claude Code와 Codex에서 사용한다. 먼저 [실행 환경 안내](references/runtime.md)를 읽고 현재 환경의 입력, 도구, 스킬 경로를 확인한다.

Claude Code 호출 인자: $ARGUMENTS

Codex에서는 `$techblog`와 함께 보낸 사용자 요청을 입력으로 받는다. `$ARGUMENTS`가 치환되지 않았거나 자연어로 호출했다면 현재 사용자 요청에서 자료와 옵션을 읽는다.

## 인자와 설정

먼저 [settings.md](references/settings.md)를 읽고 인자(`casual`/`default`, `-o`, `--retone`, `--keep-work`, `--defaults`, `--quick`)를 해석한다. 요청에 없는 설정값(새 글은 독자, 어투, 분량)은 사용자에게 한 번에 묻고 값을 정한 뒤 자료를 읽는다. 질문할 수 없으면 기본값을 사용하고 보고한다.

## 파일

- 글은 `<이름>.md`에 저장한다.
- 작업 파일은 출력 파일과 같은 폴더에 만든다. fact sheet는 `<이름>.facts.md`, 설계 문서는 `<이름>.plan.md`이고 Casual 글을 쓸 때만 만드는 Default 초안은 `<이름>.draft.md`다. 검사 스크립트는 검사한 글의 복사본을 `<점검 대상 이름>.checked.md`에 저장한다. 작업 파일은 8단계에서 삭제한다.
- 점검 대상은 합니다체 글이다. Default 글이면 출력 파일 `<이름>.md`, Casual 글이면 Default 초안 `<이름>.draft.md`다.

## 작업 순서와 필수 문서

단계마다 지정한 문서만 읽는다. 일부 섹션만 읽으라고 정한 문서는 그 섹션만 읽는다. 도구 출력이 잘리면 나머지를 나눠 읽는다. 모든 `references/`와 `scripts/`는 이 `SKILL.md`가 있는 디렉터리 기준이다.

### 새 글

1. [drafting.md](references/drafting.md)를 읽고 1~4단계를 수행한다. 자료 전체 읽기, fact sheet 작성, 설계, 문장 쓰기와 단위 점검 순서다. Casual도 먼저 합니다체로 쓴다. [style-guide.md](references/style-guide.md), [planning.md](references/planning.md), [style-sources.md](references/style-sources.md), [genre.md](references/genre.md)는 3단계에서 읽는다. 3단계의 설계 문서를 쓰지 않고 4단계로 넘어가지 않는다. AI 패턴 문서는 초안 작성 전에 읽지 않는다.
2. [validation.md](references/validation.md)와 [checking.md](references/checking.md)를 읽고 5~8단계를 수행한다. 글 전체 검사와 설계 대조, 자료 대조, 독립 점검, 수정한 부분 확인, Casual 어투 적용, 결과 보고 순서다. 글 전체는 검사 스크립트와 독립 점검이 한 번씩만 확인하고 그 뒤에는 수정한 문장과 그 앞뒤 세 문장씩만 다시 확인한다. [ai-patterns.md](references/ai-patterns.md), [korean-review.md](references/korean-review.md), [revision.md](references/revision.md)는 검출되거나 지적된 항목이 있을 때 그 항목의 섹션만 읽는다. [tone.md](references/tone.md)는 어투를 적용할 때 읽는다.

### 완성된 글의 어투만 변환

`--retone` 또는 같은 의미의 요청이면 [validation.md](references/validation.md)의 7~8단계, [checking.md](references/checking.md)의 "어투 적용하기", [tone.md](references/tone.md)를 따른다. 1~6단계는 수행하지 않는다. 입력은 수정하거나 삭제하지 않고 fact sheet를 만들지 않는다. 원문의 어투 외 검사 항목은 보고만 한다. 종결부는 문장마다 바꾸고 정규식이나 스크립트로 일괄 치환하지 않는다.
