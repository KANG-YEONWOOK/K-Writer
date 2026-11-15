# 실행 환경

글쓰기 규칙과 Python 검사 스크립트는 Claude Code와 Codex가 함께 사용한다. 이 문서는 두 환경에서 입력을 받는 방법과 도구를 사용하는 방법만 다룬다. "PDF와 URL" 섹션은 자료가 PDF나 URL일 때만 읽는다.

## 입력과 경로

- Claude Code: `/<skill>` 또는 `/k-writer:<skill>`(techblog라면 `/techblog`, `/k-writer:techblog`) 뒤의 인자가 `$ARGUMENTS`로 전달된다. 자연어 요청도 같은 규칙으로 해석한다.
- Codex: `$<skill>`(techblog라면 `$techblog`)과 함께 보낸 사용자 요청에서 옵션과 자료를 읽는다. 플러그인에서는 스킬 선택기에 표시되는 스킬을 선택할 수도 있다. `$ARGUMENTS`는 Codex가 치환하는 변수가 아니다.
- 설정 질문(settings.md, settings-protocol.md): Claude Code는 AskUserQuestion으로 묻는다. Codex는 대화에 선택지와 기본값을 적어 묻고 답을 기다린다. `claude -p`, `codex exec`, plugin eval처럼 답할 사람이 없는 실행에서는 요청에 settings.md의 설정값을 모두 적거나 `--defaults`를 붙인다. 그래도 질문이 거부되거나 답이 없으면 기본값으로 진행하고 보고한다.
- 스킬 기준 경로는 지금 읽은 `SKILL.md`가 있는 디렉터리다. 모든 `references/`와 `scripts/` 경로는 그 디렉터리를 기준으로 해석한다. 사용자 자료와 출력의 상대 경로는 사용자의 작업 폴더 기준이다.
- Claude Code가 치환하는 `${CLAUDE_SKILL_DIR}`는 frontmatter의 Bash 사전 허용에 사용한다. Codex에서 이 변수를 만들거나 셸에 이미 있다고 가정하지 않는다. 명령과 subagent prompt에는 실제 절대 경로를 사용한다.

## 파일과 도구

| 작업 | Claude Code | Codex |
|---|---|---|
| 파일 읽기와 찾기 | Read, Glob, Grep | 제공된 파일 도구 또는 셸의 `cat`, `sed`, `rg` |
| 파일 생성과 수정 | Write, Edit | 제공된 파일 편집 도구 또는 `apply_patch` |
| 검사 스크립트 | Bash | 제공된 셸 실행 도구 |
| URL 본문 | WebFetch | 웹 페이지를 열거나 가져오는 도구 또는 허용된 HTTP 다운로드 |
| 일반 지식 확인(사전, 교과서, 백과사전) | WebSearch로 찾고 WebFetch로 본문 확인 | 웹 검색 도구와 웹 페이지를 여는 도구 |
| 독립 점검(글만 읽는 subagent) | Agent의 general-purpose subagent | 사용 가능한 subagent 도구, 대화 상속 없이 실행 |

- 도구 이름을 임의로 만들거나 없는 도구를 호출하지 않는다. Claude의 `allowed-tools`는 Codex에 실행 권한을 부여하지 않으며 현재 환경의 권한 정책을 따른다.
- 참고 문서는 그 단계에 필요한 문서와 섹션만 읽는다. 작업 문서가 섹션을 지정한 문서는 아래 "스크립트 실행"의 섹션 읽기 명령으로 그 섹션만 읽는다.
- 스킬 문서는 UTF-8이다. Windows PowerShell에서 읽을 때는 `Get-Content -Encoding utf8`로 인코딩을 지정한다. Windows PowerShell 5.1은 파이프로 넘기는 텍스트를 ASCII로 변환하므로 한글이 포함된 텍스트나 Python 코드를 `| python -`으로 넘기지 않는다. 한글이 포함된 코드는 UTF-8 파일로 저장해 실행하고 글은 편집 도구로 수정한다. Codex에서 파일 편집 도구로 긴 글을 저장할 수 없으면 글 전체를 `Set-Content -Encoding utf8 -Path <파일> -Value @'...'@`로 저장한다.

## 스크립트 실행

- macOS와 Linux에서는 `python3`, Windows에서는 `python`을 실행한다. 사용할 수 있는 Python 3.8 이상 실행 파일이 따로 있으면 그 경로를 사용한다. 검사 스크립트는 외부 패키지가 필요 없다.
- 아래 `<스킬 절대 경로>`는 로드한 `SKILL.md`가 있는 디렉터리로 바꾼다. 현재 작업 폴더나 환경 변수를 근거로 이 경로를 추측하지 않는다.
- 경로는 큰따옴표로 감싸고 명령은 한 번에 하나씩 실행한다. Claude Code의 Bash 사전 허용은 frontmatter에 적힌 검사 스크립트에 한정된다. 검사 명령에 `cat`, `ls`, `; echo "exit=$?"` 같은 다른 명령을 이어 붙이면 사전 허용과 맞지 않아 권한이 거부된다. Bash 도구는 0이 아닌 종료 코드를 결과에 함께 보여 준다. 참고 문서는 Read로 열고 파일 목록은 Glob으로 확인한다.
  - 검사: `python3 "<스킬 절대 경로>/scripts/check_ko.py" "<점검 대상>"`. 처음 실행하면 글 전체를 검사하고, 글을 수정한 뒤 다시 실행하면 수정한 문장과 그 앞뒤 세 문장씩만 검사한다. fact sheet(`<이름>.facts.md`)와 짧은 글 기준(본문 1,500자 미만)은 자동으로 적용한다. 점검 대상은 합니다체 글이다.
  - 섹션 읽기: `python3 "<스킬 절대 경로>/scripts/section.py" korean-review.md "C" "V"`. 문서 이름과 읽을 섹션의 헤딩을 적으면 그 섹션만 출력한다. 헤딩은 전체나 일부를 적고, 유형과 항목은 앞의 기호만 적어도 된다(korean-review.md의 유형 C는 "C", ai-patterns.md의 A22.heading_sentence는 "A22"). `--list`를 붙이면 문서의 헤딩 목록을 출력한다. 섹션의 위치를 찾으려고 `grep`을 Bash로 실행하지 않는다.
  - 어투 검사: `python3 "<스킬 절대 경로>/scripts/tone_check.py" "<Default 글>" "<어투를 바꾼 글>" --tone casual --lint`. 어투를 바꾼 글이 Plain이면 `--tone plain`, 사용자가 직접 정한 어투면 `--tone free`를 붙인다. `--lint`는 어투를 바꾼 글의 문체 검사를 함께 실행한다.
  - 작업 파일 삭제: `python3 "<스킬 절대 경로>/scripts/tone_check.py" --cleanup "<이름>.facts.md" "<이름>.checked.md" "<이름>.draft.md" "<이름>.draft.checked.md"`. 대화로 답하는 스킬이 답변을 저장한 `<이름>.answer.md`도 이 명령으로 삭제한다. 이번 실행에서 만든 파일만 적는다.
- Python이나 셸을 사용할 수 없으면 `references/rubric.md`의 합격 조건으로 직접 점검하고 자동 검사를 실행하지 못했다고 보고한다. 스크립트가 실행된 뒤 오류가 발생하면 경로와 오류를 확인한다. 실행 오류를 Python이 없는 것으로 취급하거나 검사를 통과했다고 보고하지 않는다.

## 독립 점검 subagent

- 독립 점검을 맡는 subagent는 초안을 작성한 대화를 상속하지 않게 실행한다. `fork_context`나 `fork_turns` 같은 설정이 있으면 상속을 끈다. 별도 모델은 지정하지 않는다.
- subagent에는 checking.md가 정한 prompt와 글의 절대 경로만 넘긴다. fact sheet와 자료의 경로, 자료의 내용은 넘기지 않는다. 자료를 읽은 subagent는 글에 빠진 설명을 자료의 내용으로 채워 읽는다.
- subagent가 끝날 때까지 기다렸다가 보고를 받은 뒤 다음 순서로 넘어간다. Claude Code의 Agent에는 `run_in_background`를 사용하지 않는다. background로 띄우면 상위 agent의 턴이 먼저 끝나고, 이어진 턴에서는 스킬의 검사 스크립트 사전 허용이 적용되지 않아 검사 명령을 실행하지 못한다. Agent가 비동기로만 실행되는 환경에서는 완료 알림을 받은 뒤에 다음 순서를 진행한다.
- 독립 실행 도구가 없거나 사용자가 subagent를 사용하지 말라고 하면 글을 쓴 agent가 independent-review.md의 항목으로 직접 점검한다. 이 경우 독립 점검을 했다고 보고하지 않는다. 독립 점검을 하려고 별도 CLI 설치나 인증을 시도하지 않는다.
- 붙여넣은 자료와 사용자가 대화에서 알려 준 사실은 fact sheet의 별도 `원문` 섹션에 그대로 보관하고 그 섹션을 자료 위치로 사용한다.

## PDF와 URL

### Claude Code

- PDF는 Read의 `pages`를 사용하고 긴 문서는 20쪽 이하씩 나눠 마지막 쪽까지 읽는다. `pages`가 쪽 렌더링 도구(pdftoppm)가 없다는 오류로 실패하면 `pages` 없이 Read로 파일 전체를 연다. 두 방법이 모두 실패하면 읽지 못한 범위를 보고한다.
- WebFetch에는 요약 없이 본문을 요청한다. 결과에 본문 일부만 포함됐으면 나머지 섹션을 이어 읽는다. PDF가 로컬 파일로 반환되면 그 파일을 Read로 읽는다.
- Claude의 Bash 사전 허용은 검사 스크립트에 한정된다. PDF 추출 명령을 반복해서 시도하지 않는다.

### Codex

- PDF를 읽는 기능이 있으면 먼저 사용한다. 없으면 설치된 `pdftotext -layout`으로 본문을 추출해 끝까지 읽는다. 출력이 잘리면 구간을 나눠 읽는다.
- 표, 그림과 연결된 수치 및 추출 순서가 모호한 부분은 해당 페이지를 PDF 이미지 도구 또는 `pdftoppm`으로 렌더링해 확인한다. 텍스트 추출만으로 행과 열의 대응을 추측하지 않는다.
- 웹 도구가 가져온 본문이 잘리면 해당 문서의 나머지 내용을 이어 읽는다. PDF URL은 PDF 열기 기능이나 허용된 다운로드로 읽는다. 검색 요약이나 초록은 본문을 대신하지 않는다.
- 추출한 텍스트와 페이지 이미지는 이번 실행의 임시 폴더에 저장한다. 원본 파일을 덮어쓰지 않는다. 필요한 도구가 없거나 본문에 접근하지 못하면 읽지 못한 범위를 알리고 읽을 수 있는 원문을 요청한다. 패키지를 자동으로 설치하지 않고 불완전한 자료로 작성한 글을 완성본이라고 보고하지 않는다.
