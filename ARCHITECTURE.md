# K-Writer 구조

K-Writer는 한국어 글쓰기 스킬 여러 개를 제공하는 플러그인이다. 사용자가 스킬을 호출했을 때만 동작하고, 스킬을 호출하지 않은 세션에는 아무 내용도 추가하지 않는다. 모든 스킬이 같은 한국어 규칙과 검사 스크립트(core)를 사용하고, 글의 종류(장르)에 따라 달라지는 독자, 어투 선택지, 글의 구성, 기준치는 스킬이 정한다. 이 문서는 저장소를 수정하는 사람을 위한 문서이고, 스킬을 실행할 때는 읽지 않는다.

## 스킬

글을 쓰려면 글의 바탕이 될 자료, 글의 목적, 분량, 어투를 정해야 한다. write는 이 값을 모두 사용자에게 받는 기본 스킬이다. 나머지 스킬은 목적, 어투 선택지, 구성을 미리 정해 두고 남은 값만 사용자에게 받는다.

| 스킬 | 목적 | 사용자에게 받는 값 | 어투 | 구성 | 독립 점검 | 출력 |
|---|---|---|---|---|---|---|
| write | 사용자가 정한다(설명, 설득, 안내, 기록, 직접 입력). 발표 자료의 문구도 쓴다 | 자료나 주제, 목적, 분량, 어투 | Default, Casual, Plain, 직접 입력 | 목적별 구성, 발표 자료의 형식. 글을 쓰기 전에 설계 문서에 단위와 문장별 내용을 정한다 | 글만 읽고 보고하는 subagent 한 개. 본문이 300자 미만이면 생략한다 | 파일 |
| techblog | 자료를 기술 블로그 글로 정리 | 자료, 독자, 어투, 분량 | Default, Casual | 기술 블로그 글의 구성. 글을 쓰기 전에 설계 문서에 섹션과 문장별 내용을 정한다 | 글만 읽고 보고하는 subagent 한 개 | 파일 |
| brief | 자료를 요약 | 자료, 분량, 어투 | Default, Casual, Plain, 직접 입력 | 핵심 문장과 분량별 형식. 요약을 쓰기 전에 문장별 내용을 정한다. 문단이 하나인 요약은 fact sheet에, 문단이 여럿인 요약은 설계 문서에 적는다 | 요약만 읽고 보고하는 subagent 한 개. 분량이 한 줄이면 생략한다 | 대화(`-o`가 있으면 파일에도 저장) |

새 스킬은 write가 사용자에게 묻는 값 중 어느 것을 미리 정할지부터 정한다. 목적을 정하면 그 목적의 독자, 화자, 구성을 genre.md에 적고, 어투 선택지와 기본값을 settings.md에 적는다.

## 설계와 점검 흐름

세 스킬은 글을 위에서 아래로 설계하고 아래에서 위로 쓰고 점검한다. 0.7.0에서 write에, 0.7.1에서 techblog에, 0.8.0에서 brief에 추가한 순서이고 방법은 core의 `planning.md`와 스킬의 `drafting.md`가 정한다.

1. 설계: 글 전체의 핵심 주제를 정하고, 핵심 주제를 단위(소주제 하나를 다루는 문단이나 섹션)로 나누고, 단위마다 전할 내용과 전개를 정하고, 문장마다 전할 내용을 한 줄씩 정해 설계 문서(`<이름>.plan.md`)에 적는다. `plan_ko.py check`가 설계 문서의 형식, 문장으로 적지 않은 계획 문장, 근거가 없는 계획 문장, 핵심 주제와 겹치는 단어가 없는 단위를 출력한다.
2. 문장 쓰기와 단위 점검: 계획 문장을 하나씩 글의 문장으로 쓰고 쓴 직후 그 문장의 표현을 확인한다. 단위의 문장을 모두 쓰면 그 단위를 한 번 읽고 문장의 연결, 전개 순서, 용어와 수치의 일치를 확인한다.
3. 글 전체 점검: 아래 점검 순서를 따른다. `check_ko.py`는 설계 문서가 있으면 글을 설계와 대조해 글에서 찾지 못한 계획 문장, 글에서 빠진 수치, 설계에 없는 문장을 출력한다.

사용자는 2026-11-26에 번역투와 어색한 단어는 줄었지만 중요한 내용을 줄여 말하는 문장과 글의 주제와 관계없는 내용이 계속 나온다고 지적하고 이 순서를 제안했다. 설계의 기준은 수능 국어 지문, 신문 기사, 논문 초록, 연설문을 측정한 값이다(`dev/baseline/write`). brief는 요약에 쓸 사실을 선택한 뒤 문장마다 전할 내용을 적는다. 문단이 하나인 요약은 fact sheet의 "문장별 내용" 섹션에 적고 설계 검사를 실행하지 않는다. 한 문단 요약에 설계 문서를 쓰게 했을 때 실행 시간이 6.1분에서 9.3분으로 늘었기 때문이다. 문단이 여럿인 요약은 문단을 단위로 설계 문서를 쓰고, `planning.md`는 "3. 문장별 내용"과 "설계 문서 형식" 섹션만 읽는다. 한 줄 요약은 문장이 한두 개라서 설계를 따로 적지 않는다.

세 스킬은 같은 순서로 글 전체를 점검하고 방법은 core의 `checking.md`가 정한다.

1. 검사: `check_ko.py`가 글 전체를 한 번 검사한다. 글을 쓴 agent는 검출된 문장을 수정하고 글을 fact sheet와 대조한다.
2. 독립 점검: 초안을 작성한 대화를 상속하지 않는 subagent 하나가 `independent-review.md`와 글만 읽고 독자가 이해하지 못하거나 어색하게 읽을 부분, 건너뛴 내용, 글의 핵심과 관계없는 부분을 보고한다. 문단마다 그 문단이 전하는 내용도 한 줄씩 보고하고, 글을 쓴 agent는 이 줄을 설계 문서의 단위별 "전할 내용"과 비교한다. 이 subagent는 글을 수정하지 않는다. 글을 쓴 agent가 fact sheet와 자료를 확인하면서 수정한다.
3. 수정한 부분 확인: `check_ko.py`를 다시 실행하면 지난 검사 뒤에 바뀐 문장, 헤딩, 표의 행과 그 앞뒤 세 문장씩만 출력한다. 글을 쓴 agent는 출력된 부분만 다시 읽는다.

글 전체를 읽는 점검은 1과 2뿐이다. 0.5.2까지는 독자 점검, 후처리, 한국어 문장 점검, 수정 후 검토를 subagent 네 개가 차례로 했고 단계마다 글 전체를 다시 검사했다. 0.5.1에서 `claude -p`로 실행한 write는 한 건에 13.1~20.6분, 4.01~5.66달러가 들었고 본문 8,304자인 글은 58.5분, 15.78달러가 들었다. 사용자는 2026-11-15에 이미 통과한 부분까지 수정할 때마다 다시 검사하는 방식 때문에 시간과 토큰이 지나치게 든다고 지적했다. 그래서 0.6.0에서 점검을 위 세 단계로 줄였다. 실행 비용을 늘리지 않기 위한 규칙은 AGENTS.md의 "Keeping a run cheap"에 있다.

스킬을 실행하는 agent가 읽는 문서도 줄였다. 초안을 쓰기 전에 읽는 `style-guide.md`에는 규칙과 예만 남기고, 자료가 영어일 때나 자료의 주장을 옮길 때만 필요한 섹션은 `style-sources.md`로 옮겼다. `ai-patterns.md`, `korean-review.md`, `revision.md`는 검출되거나 지적된 항목의 섹션만 읽는다. 규칙을 추가하게 된 검토와 테스트 실행의 기록은 `dev/style-guide-history.md`와 korean-review.md의 "유형을 추가한 경위"에 있다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `core/` | 모든 스킬이 함께 사용하는 문서(`references/`)와 검사 스크립트(`scripts/`)의 원본. `dev/sync_core.py`가 스킬 폴더마다 같은 이름으로 복사하므로 스킬 폴더의 복사본은 직접 수정하지 않는다 |
| `dev/sync_core.py`, `dev/new_skill.py`, `dev/borrow_thresholds.py` | core를 스킬 폴더에 복사하는 스크립트, 새 스킬 폴더를 만드는 스크립트, 기준 글 표본이 없는 스킬에 다른 스킬의 기준치를 복사하는 스크립트 |
| `dev/baseline/techblog/` | techblog의 기준 글(사람이 쓴 기술 블로그 글)을 측정하는 `measure.py`, 측정값으로 기준치를 계산하는 `calibrate.py`, 계산 결과 보고서 `calibration.md` |
| `dev/baseline/brief/` | 사람이 쓴 요약의 표본(KCI 논문 초록 1,206편)을 수집하고 측정하는 `measure.py`. brief의 한 문단 분량 범위를 이 표본의 문장 길이와 대조하고, 점검 후보 항목이 이 표본에 얼마나 나오는지 측정한다. 기준치 보정에는 사용하지 않는다 |
| `dev/baseline/write/` | write의 기준 글 표본(수능 국어 지문 82편, 한국경제 기사 1,200편, KCI 논문 초록 301편, 대통령 연설문 412편)의 문장 연결, 문단 구성, 종결 표현을 측정한 도구와 결과. 문단과 문장에 역할 라벨을 붙인 구조 주석의 지침과 집계도 있다. 원문은 저장소에 없다 |
| `dev/baseline/headings/` | 제목과 헤딩이 명사로 끝나는지 문장으로 끝나는지를 사람이 쓴 기술 블로그 글과 보도자료 제목, 스킬 없이 쓴 모델의 발표 자료에서 측정하는 `measure.py`와 측정 기록 |
| `dev/dogfood/` | `claude -p`로 스킬을 실행하고 스킬이 작성한 글을 judge 모델(글을 읽고 판정 항목처럼 정해진 기준으로 점수를 매기는 모델)로 평가하는 스크립트. |
| `evals/` | 스킬에 맡길 요청과 채점 기준을 묶은 평가 케이스. `claude plugin eval`로 실행한다 |
| `dev/codex/` | Codex에서 설치와 글 작성을 검증하는 스크립트 |

## 계층

| 계층 | 위치 | 정하는 것 |
|---|---|---|
| core | `core/references/`, `core/scripts/` | 실행 환경(Claude Code, Codex), 설정을 묻는 절차, 장르와 무관한 한국어 문장 규칙, 어투, AI 문체 패턴, fact sheet, 독립 점검 절차, 검사 스크립트와 검사 항목 정의 |
| 스킬 | `skills/<이름>/` | 장르, 기준 글(그 스킬이 문체의 기준으로 삼는 사람 글), 기본 독자, 설정값, 표현과 글의 구성, 작업 순서, 판정 기준, 기준 글로 보정한 기준치 |

### core 파일

| 파일 | 내용 | techblog가 읽는 시점 |
|---|---|---|
| `references/runtime.md` | Claude Code와 Codex의 입력, 경로, 도구, 검사 명령, PDF와 URL 읽기, subagent 실행 | SKILL.md를 읽은 다음 |
| `references/settings-protocol.md` | 설정값을 묻는 순서(Claude Code의 AskUserQuestion, Codex의 대화), 질문할 수 없을 때의 처리, 값의 출처 보고 | settings.md와 함께 |
| `references/style-guide.md` | 장르와 무관한 한국어 문장 규칙: 문단과 문장이 전할 내용, 문장을 이어 쓰기, 처음 나오는 용어 설명, 문장을 따로 읽어도 이해되게 쓰기, 문단과 문장, 제목과 헤딩, 서술어 호응, 단어 고르기, 용어 표기, 수치, 문장 부호 | 3단계(개요) |
| `references/planning.md` | 글 설계: 핵심 주제와 단위, 단위의 전개, 문장별 내용, 설계 문서의 형식, 설계 점검 | 3단계(설계). brief는 문단이 여럿인 요약을 쓸 때 "3. 문장별 내용"과 "설계 문서 형식" 섹션만 읽는다 |
| `references/style-sources.md` | 자료를 옮기는 문장의 규칙: 영어 자료를 한국어로 옮기기, 자료의 말을 옮기는 문장, 위치와 순서의 대응 보여 주기 | 3단계(개요). 해당하는 섹션만 읽는다 |
| `references/fact-sheet.md` | 자료 기반 글의 fact sheet 항목 | 1단계 전(drafting.md와 함께) |
| `references/tone.md` | Default(합니다체), Casual(해요체), Plain(해라체)의 종결과 대응표, 사용자가 직접 정한 어투의 규칙, 숫자와 영어 뒤 조사 | 7단계(어투 적용) |
| `references/checking.md` | 점검 방법: 검사 명령, 검사 결과 수정, 독립 점검의 prompt, 지적 반영, 수정한 부분 확인, 어투 적용, 작업 파일 정리 | 5단계(검사)부터 |
| `references/independent-review.md` | 독립 점검을 맡은 subagent가 읽는 문서: 지킬 것, 읽는 순서, 찾는 항목 열 가지, 보고 형식(핵심 한 문장, 문단별 내용, 찾은 부분) | 6단계(독립 점검)의 subagent |
| `references/ai-patterns.md` | lint 항목마다 AI 문체 표현을 수정하는 방법 | 5단계부터 검출된 항목의 섹션만. 초안을 작성하기 전에는 읽지 않는다 |
| `references/korean-review.md`, `revision.md` | 어색한 표현과 문장의 유형별 수정 방법, 반복과 빠진 정보를 수정하는 방법 | 6단계에서 지적된 유형의 섹션만 |
| `scripts/check_ko.py` | 검사 명령. 처음 실행하면 글 전체를 검사하고, 그 뒤에는 지난 검사 뒤에 바뀐 문장과 앞뒤 세 문장씩만 검사한다. 설계 문서가 있으면 글을 설계와 대조한다 | 5단계부터 |
| `scripts/plan_ko.py` | 설계 문서 검사(`check`)와 설계 문서와 글의 대조(`compare`). `check_ko.py`가 대조 함수를 사용한다 | 3단계(설계) |
| `scripts/lint_ko.py`, `patterns_ko.json`, `rules.json` | 문체 검사 스크립트, 정규식 패턴, 검사 항목 정의와 짧은 글 기준. `check_ko.py`와 `tone_check.py`가 사용한다 | 5단계부터 |
| `scripts/tone_check.py` | 어투를 바꾼 글과 Default 초안이 문장 끝만 다른지 검사, 어투를 바꾼 글의 문체 검사(`--lint`), 작업 파일 삭제 | 7~8단계 |
| `scripts/revise_ko.py` | 문장 단위 비교와 반복 후보 찾기. `check_ko.py`가 이 스크립트의 함수를 사용한다. 0.5.2까지의 후처리 명령(`start`, `check`, `mark`, `audit`)은 기존 글과 수정본을 직접 비교할 때 사용할 수 있다 | 스킬의 작업 순서에서는 직접 실행하지 않는다 |

### 스킬 폴더의 파일(slot)

| 파일 | 내용 |
|---|---|
| `SKILL.md` | frontmatter(`name`은 폴더 이름, `description`은 1,024자 이하, `allowed-tools`, `metadata.version`은 플러그인 버전), 장르와 기준 글, 기본 독자, 작업 순서와 단계마다 읽을 문서. Codex는 플러그인 스킬의 SKILL.md를 8,000바이트까지만 읽으므로 LF와 CRLF 모두 6,000바이트 이하로 유지한다 |
| `README.md` | 사람이 읽는 스킬 소개: 사용법, 작성 과정, 기준치와 검사 항목, 한계. 스킬을 실행할 때는 읽지 않는다 |
| `references/settings.md` | 인자, 설정값 표(묻는 모드, 기본값, 선택지), AskUserQuestion 질문 표, 정한 값을 사용하는 단계 |
| `references/genre.md` | 독자와 화자, 글의 구성, 분량, 장르 표현 규칙과 예. genre.md가 style-guide.md의 규칙을 바꾼다고 명시한 부분만 genre.md가 우선한다 |
| `references/rubric.md` | 합격 조건, 판정 항목, 기준치의 근거 |
| `scripts/thresholds.json` | `skill.standard`(기준 글 이름)와 기준 글로 보정한 값 |
| 작업 문서 | 이름은 스킬이 정한다. 세 스킬 모두 `drafting.md`(자료 읽기부터 초안까지)와 `validation.md`(점검과 마무리)다. `validation.md`는 스킬마다 다른 대조 항목과 보고 형식만 정하고 점검 방법은 core의 `checking.md`를 따른다. 초안을 작성하기 전에 읽는 작업 문서는 `drafting.md`로 이름을 정하고 사용할 표현만 적는다(AGENTS.md) |

Codex 0.155.1과 0.162.1은 플러그인 스킬의 `SKILL.md`를 frontmatter까지 포함해 UTF-8 기준 8,000바이트까지만 프롬프트에 넣는다. 이 한도를 넘으면 앞부분만 남기고 내용이 잘렸다는 경고를 출력한다. `tests/test_portability.py`는 2,000바이트의 여유를 두고 스킬마다 `SKILL.md`가 6,000바이트 이하인지 확인한다.

core 문서는 스킬 문서를 slot 이름(settings.md, genre.md, rubric.md, thresholds.json)으로만 가리키고, 스킬의 단계 번호와 작업 문서 이름을 사용하지 않는다. 단계는 이름으로 가리킨다: 자료 읽기, fact sheet, 개요, 설계, 초안 쓰기, 검사, 독립 점검, 수정한 부분 확인, 어투 적용, 결과 보고. 자연스러움의 기준은 "스킬이 정한 기준 글"로 표현하고, 스킬은 SKILL.md와 subagent prompt에 기준 글을 적는다. techblog의 기준 글은 사람이 쓴 한국어 기술 블로그 글이다. `tests/test_core.py`가 이 규칙을 검사한다.

## core 복사본

`dev/sync_core.py`가 core 파일을 모든 스킬 폴더의 `references/`, `scripts/`에 같은 이름으로 복사한다. 스킬 폴더는 하나씩 따로 설치되고 로드되기 때문이다(플러그인 cache의 `skills/<이름>/`, `~/.claude/skills/`, `~/.agents/skills/`, Codex `$skill-installer`). 복사본이 있으면 링크, 검사 명령, `allowed-tools`의 `${CLAUDE_SKILL_DIR}/scripts/*`가 모두 그 폴더 안의 경로를 가리킨다. Codex는 SKILL.md의 변수를 치환하지 않으므로, 스킬 폴더 밖의 core를 읽게 하면 모델이 경로를 직접 계산해야 한다.

- core를 수정한 뒤 `python dev/sync_core.py`를 실행한다. 스킬 폴더의 복사본은 직접 수정하지 않는다.
- `python dev/sync_core.py --check`와 `tests/test_core.py`가 복사본이 원본과 바이트 단위로 같은지 확인한다.
- core에서 파일을 삭제하거나 이름을 바꾸면 `python dev/sync_core.py --remove <이름>`으로 모든 스킬에서 복사본도 삭제한다.
- 검사 스크립트 출력의 첫 줄(`techblog lint`, `techblog check`)에는 스크립트가 있는 스킬 폴더의 이름이 들어간다.

## 설정과 어투

스킬의 settings.md가 설정값과 선택지, 기본값을 정하고, core의 settings-protocol.md가 묻는 순서를 정한다. 사용자는 요청에 값을 적거나 질문에 답해 값을 선택하고, 선택지에 없는 값은 "직접 입력"으로 적는다. 자료나 주제처럼 기본값이 없는 값은 settings.md의 "반드시 받는 값"에 적는다. 이 값이 요청에 없으면 스킬은 대화에서 먼저 묻고 답을 받은 뒤에 나머지 값을 묻는다.

core의 어투는 Default(합니다체), Casual(해요체), Plain(해라체) 세 가지이고, 스킬은 이 중 사용할 어투와 기본값을 정한다. 스킬이 어투의 "직접 입력"을 허용하면 사용자가 적은 어투(반말, 개조식 등)로도 쓴다. 어느 어투든 내용은 Default 초안에서 정하고 문장마다 종결부만 바꾼다(tone.md). `lint_ko.py --tone`과 `tone_check.py --tone`은 `plain`으로 해라체를 판정하고, `free`로 직접 정한 어투를 받아 종결 판정을 생략한다. 종결을 판정하는 어투를 추가하려면 tone.md와 `lint_ko.py`의 `TONE_CLASSES`, `tone_check.py`의 `TARGETS`를 함께 수정한다.

스킬의 출력은 파일로 저장하는 글일 수도 있고 대화로 하는 답변일 수도 있다. 대화로 답하는 스킬이 검사 스크립트를 사용하려면 답변을 작업 파일에 쓰고 검사 명령을 실행한 뒤 그 파일을 삭제한다.

## 기준치

`lint_ko.py`는 core의 `rules.json`과 스킬의 `thresholds.json`을 합친 값으로 판정한다(`load_thresholds`).

- `rules.json`: 검사 항목 122개의 정의, Gate와 policy, 고정 기준(fixed), 짧은 글 기준(`short`). 모든 스킬에 공통이다. 항목을 추가하거나 수정할 때는 이 파일을 수정한다.
- `thresholds.json`: 그 스킬의 기준 글로 보정한 값(gate도 fixed도 아닌 항목의 PASS, WARN 경계와 사람 글 분포). metric 필드를 덮어쓰거나 `drop`으로 항목을 제외할 수 있다. 보정값이 없는 분포 지표는 INFO로 값만 보고한다.
- 가져온 기준치: write와 brief는 분포 항목의 기준치를 보정할 기준 글 표본이 아직 없다. brief는 논문 초록 1,206편을 측정했지만 초록이 학술 문체라서 대조에만 사용한다([dev/baseline/brief/README.md](dev/baseline/brief/README.md)). write는 수능 국어 지문, 신문 기사, 논문 초록, 연설문을 측정했지만 표본의 글이 대부분 본문 1,500자 미만이라 문장 연결의 기준과 표현 항목 세 개의 기준치에만 사용한다([dev/baseline/write/README.md](dev/baseline/write/README.md)). 보정한 값이 없으면 부정 대구나 번역투 같은 AI 문체 항목도 판정하지 못하므로, brief는 특정 표현의 빈도를 세는 항목 15개의 기준치를, write는 13개의 기준치를 techblog에서 가져온다. write는 지시어로 시작하는 문장(A13), 번역투(A14.translationese_per_1k), 판단을 옮기는 "~라고 봅니다"(A7.see_judgment)를 수능 국어 지문의 빈도를 비율로 하는 Poisson 한도로 판정한다. techblog의 기준치로는 수능 국어 지문의 37%가 A13에서 불합격이었기 때문이다. `thresholds.json`의 `borrowed`에 가져올 스킬과 항목을 적고 `python dev/borrow_thresholds.py`로 복사한다. techblog의 기준치를 다시 보정하면 이 명령을 다시 실행하고, `--check`와 `tests/test_tones_and_profiles.py`가 복사한 값이 원본과 같은지 확인한다. 문장 길이, 문단, 목록 비중처럼 글의 종류에 따라 달라지는 항목은 가져오지 않는다.
- 짧은 글 기준: `check_ko.py`는 본문이 공백 제외 1,500자 미만이면 `short`의 값을 자동으로 적용한다(`--short`와 `--full`로 직접 정할 수 있다). `lint_ko.py --short`와 `revise_ko.py`의 `check --short`, `audit --short`도 같은 값을 적용한다. 문장 수가 적으면 문장 하나로 값이 크게 달라지는 분포 항목을 제외하고, `count`에 적은 1,000자당 비율 항목과 해요체 종결 비율 항목을 개수로 판정하며, poisson 항목은 한 번까지 허용한다. 스킬이 `thresholds.json`에서 Poisson 한도로 판정하도록 바꾼 항목(write의 A13, A14)은 개수 기준으로 바꾸지 않는다. Poisson 한도는 글의 길이에 따라 달라지기 때문이다. 한 번까지 허용하는 부정 대구 문장은 점검 후보(`A1.np_check`)로도 출력한다(`short`의 `check`). brief는 요약에, write는 본문이 공백 제외 1,500자 미만인 글에 이 기준을 사용한다. 스킬의 `thresholds.json`에 `short`가 있으면 그 값이 core의 값을 대신한다.
- 스킬별 허용: 스킬의 `thresholds.json`은 `allow_patterns`(패턴 ID마다 검사하지 않을 정규식), `allow_imperative`(Default 글의 요청문 "~해 주세요"), `allow_inga_question`(Default 글의 질문 "~인가요?")으로 그 장르에서 자연스러운 표현을 허용한다. 항목의 `kind`를 `check`로 바꾸면 Gate 대신 점검 후보로 출력하고, `group`을 `fact`로 정하면 "자료 대조 후보"로 묶어 출력한다. write가 이 값들을 사용하고 근거는 write의 rubric.md에 있다.
- 보정은 `dev/baseline/<skill>/`의 표본으로 한다([dev/baseline/README.md](dev/baseline/README.md)). techblog의 `calibrate.py`는 합친 값으로 계산하고 보정값(`split_thresholds`)만 저장한다.

## 스킬 추가

1. `python dev/new_skill.py <이름>`으로 slot 파일, 작업 문서 `workflow.md`, core 복사본을 만든다. 이름은 소문자, 숫자, 하이픈으로 쓴다.
2. 만든 파일의 `TODO:`를 채운다. SKILL.md에는 장르, 기준 글, 기본 독자와 단계마다 읽을 core 문서를, settings.md에는 반드시 받는 값, 어투 선택지와 기본값을, genre.md에는 구성과 분량을 적는다. 작업 문서는 `workflow.md` 하나로 두거나 초안 작성 전후로 나눈다. `TODO:`가 남아 있으면 `tests/test_core.py`가 실패한다.
3. 기준 글 표본이 있으면 `dev/baseline/<이름>/`에서 기준치를 보정한다. 없으면 core의 Gate, policy, 고정 기준만으로 검사하거나, `thresholds.json`에 `borrowed`를 적고 `python dev/borrow_thresholds.py`로 표현 항목의 기준치를 다른 스킬에서 가져온다.
4. eval 케이스는 `evals/<이름>-<케이스>/`에 추가하고 `claude plugin eval . --case '<이름>-*'`로 실행한다. techblog의 케이스는 이 규칙을 정하기 전에 만들어서 이름에 스킬 이름이 없다.
5. `python -m unittest discover -s tests`와 `claude plugin validate .`를 실행한다. 사람이 읽을 소개를 `skills/<이름>/README.md`에 작성하고, 루트 README.md의 스킬 표와 manifest 설명에 새 스킬을 추가한다.
