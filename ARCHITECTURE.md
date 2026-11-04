# K-Writer 구조

K-Writer는 한국어 글쓰기 스킬 여러 개를 제공하는 플러그인이다. 모든 스킬이 같은 한국어 규칙과 검사 스크립트(core)를 사용하고, 글의 종류(장르)에 따라 달라지는 독자, 어투 선택지, 글의 구성, 기준치는 스킬이 정한다. 이 문서는 저장소를 수정하는 사람을 위한 문서이고, 스킬을 실행할 때는 읽지 않는다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `core/` | 모든 스킬이 함께 사용하는 문서(`references/`)와 검사 스크립트(`scripts/`)의 원본. `dev/sync_core.py`가 스킬 폴더마다 같은 이름으로 복사하므로 스킬 폴더의 복사본은 직접 수정하지 않는다 |
| `dev/sync_core.py`, `dev/new_skill.py` | core를 스킬 폴더에 복사하는 스크립트, 새 스킬 폴더를 만드는 스크립트 |
| `dev/baseline/techblog/` | techblog의 기준 글(사람이 쓴 기술 블로그 글)을 측정하는 `measure.py`, 측정값으로 기준치를 계산하는 `calibrate.py`, 계산 결과 보고서 `calibration.md` |
| `dev/dogfood/` | `claude -p`로 스킬을 실행하고 스킬이 작성한 글을 judge 모델(글을 읽고 판정 항목처럼 정해진 기준으로 점수를 매기는 모델)로 평가하는 스크립트 |
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
| `references/runtime.md` | Claude Code와 Codex의 입력, 경로, 도구, 검사 명령, PDF와 URL 읽기, subagent 실행 | SKILL.md를 읽은 다음, 모든 subagent가 시작할 때 |
| `references/settings-protocol.md` | 설정값을 묻는 순서(Claude Code의 AskUserQuestion, Codex의 대화), 질문할 수 없을 때의 처리, 값의 출처 보고 | settings.md와 함께 |
| `references/style-guide.md` | 장르와 무관한 한국어 문장 규칙: 처음 나오는 용어 설명, 문장을 따로 읽어도 이해되게 쓰기, 영어 자료 옮기기, 자료의 말 옮기기, 문단과 문장, 서술어 호응, 단어 고르기, 용어 표기, 수치, 문장 부호 | 3단계(개요) |
| `references/fact-sheet.md` | 자료 기반 글의 fact sheet 항목 | 1단계 전(drafting.md와 함께) |
| `references/tone.md` | Default(합니다체)와 Casual(해요체)의 종결, 대응표, 숫자와 영어 뒤 조사 | 7단계(어투 적용) |
| `references/ai-patterns.md` | lint 항목마다 AI 문체 표현을 수정하는 방법 | 5단계부터. 초안을 작성하기 전에는 읽지 않는다 |
| `references/reader-check.md`, `revision.md`, `korean-review.md` | 독자 점검, 후처리, 한국어 문장 점검 절차 | 6단계(독립 점검) |
| `scripts/lint_ko.py`, `patterns_ko.json`, `rules.json` | 문체 검사 스크립트, 정규식 패턴, 검사 항목 정의 | 5단계부터 |
| `scripts/revise_ko.py`, `tone_check.py` | 후처리 보조, Casual 글과 Default 초안이 문장 끝만 다른지 검사, 작업 파일 삭제 | 6~8단계 |

### 스킬 폴더의 파일(slot)

| 파일 | 내용 |
|---|---|
| `SKILL.md` | frontmatter(`name`은 폴더 이름, `description`은 1,024자 이하, `allowed-tools`, `metadata.version`은 플러그인 버전), 장르와 기준 글, 기본 독자, 작업 순서와 단계마다 읽을 문서. Codex는 플러그인 스킬의 SKILL.md를 8,000바이트까지만 읽으므로 LF와 CRLF 모두 6,000바이트 이하로 유지한다 |
| `README.md` | 사람이 읽는 스킬 소개: 사용법, 작성 과정, 기준치와 검사 항목, 한계. 스킬을 실행할 때는 읽지 않는다 |
| `references/settings.md` | 인자, 설정값 표(묻는 모드, 기본값, 선택지), AskUserQuestion 질문 표, 정한 값을 사용하는 단계 |
| `references/genre.md` | 독자와 화자, 글의 구성, 분량, 장르 표현 규칙과 예. genre.md가 style-guide.md의 규칙을 바꾼다고 명시한 부분만 genre.md가 우선한다 |
| `references/rubric.md` | 합격 조건, 판정 항목, 기준치의 근거 |
| `scripts/thresholds.json` | `skill.standard`(기준 글 이름)와 기준 글로 보정한 값 |
| 작업 문서 | 이름은 스킬이 정한다. techblog는 `drafting.md`, `validation.md`, `finalization.md`, `short.md`다 |

Codex 0.155.1과 0.162.1은 플러그인 스킬의 `SKILL.md`를 frontmatter까지 포함해 UTF-8 기준 8,000바이트까지만 프롬프트에 넣는다. 이 한도를 넘으면 앞부분만 남기고 내용이 잘렸다는 경고를 출력한다. `tests/test_portability.py`는 2,000바이트의 여유를 두고 스킬마다 `SKILL.md`가 6,000바이트 이하인지 확인한다.

core 문서는 스킬 문서를 slot 이름(settings.md, genre.md, rubric.md, thresholds.json)으로만 가리키고, 스킬의 단계 번호와 작업 문서 이름을 사용하지 않는다. 단계는 이름으로 가리킨다: 자료 읽기, fact sheet, 개요, 초안 쓰기, 초안 점검, 독자 점검, 후처리, 한국어 문장 점검, 수정 후 검토, 어투 적용, 결과 보고. 자연스러움의 기준은 "스킬이 정한 기준 글"로 표현하고, 스킬은 SKILL.md와 subagent prompt에 기준 글을 적는다. techblog의 기준 글은 사람이 쓴 한국어 기술 블로그 글이다. `tests/test_core.py`가 이 규칙을 검사한다.

## core 복사본

`dev/sync_core.py`가 core 파일을 모든 스킬 폴더의 `references/`, `scripts/`에 같은 이름으로 복사한다. 스킬 폴더는 하나씩 따로 설치되고 로드되기 때문이다(플러그인 cache의 `skills/<이름>/`, `~/.claude/skills/`, `~/.agents/skills/`, Codex `$skill-installer`). 복사본이 있으면 링크, 검사 명령, `allowed-tools`의 `${CLAUDE_SKILL_DIR}/scripts/*`가 모두 그 폴더 안의 경로를 가리킨다. Codex는 SKILL.md의 변수를 치환하지 않으므로, 스킬 폴더 밖의 core를 읽게 하면 모델이 경로를 직접 계산해야 한다.

- core를 수정한 뒤 `python dev/sync_core.py`를 실행한다. 스킬 폴더의 복사본은 직접 수정하지 않는다.
- `python dev/sync_core.py --check`와 `tests/test_core.py`가 복사본이 원본과 바이트 단위로 같은지 확인한다.
- core에서 파일을 삭제하거나 이름을 바꾸면 `python dev/sync_core.py --remove <이름>`으로 모든 스킬에서 복사본도 삭제한다.
- 검사 스크립트 출력의 첫 줄(`techblog lint`, `techblog repeats`)에는 스크립트가 있는 스킬 폴더의 이름이 들어간다.

## 설정과 어투

스킬의 settings.md가 설정값과 선택지, 기본값을 정하고, core의 settings-protocol.md가 묻는 순서를 정한다. 사용자는 요청에 값을 적거나 질문에 답해 값을 선택하고, 선택지에 없는 값은 "직접 입력"으로 적는다. core의 어투는 Default(합니다체)와 Casual(해요체) 두 가지이고, 스킬은 이 중 사용할 어투와 기본값을 정한다. 내용은 Default 초안에서 정하고 Casual은 문장마다 종결부만 바꾼다(tone.md, `tone_check.py`). 새 어투(해라체, 개조식)를 추가하려면 tone.md와 `lint_ko.py`의 G4, T 항목(`tone_metrics`의 허용 종결)을 함께 수정한다.

스킬의 출력은 파일로 저장하는 글일 수도 있고 대화로 하는 답변일 수도 있다. 대화로 답하는 스킬이 검사 스크립트를 사용하려면 답변을 작업 파일에 쓰고 lint를 실행한 뒤 그 파일을 삭제한다.

## 기준치

`lint_ko.py`는 core의 `rules.json`과 스킬의 `thresholds.json`을 합친 값으로 판정한다(`load_thresholds`).

- `rules.json`: 검사 항목 118개의 정의, Gate와 policy, 고정 기준(fixed). 모든 스킬에 공통이다. 항목을 추가하거나 수정할 때는 이 파일을 수정한다.
- `thresholds.json`: 그 스킬의 기준 글로 보정한 값(gate도 fixed도 아닌 항목의 PASS, WARN 경계와 사람 글 분포). metric 필드를 덮어쓰거나 `drop`으로 항목을 제외할 수 있다. 보정값이 없는 분포 지표는 INFO로 값만 보고한다.
- 보정은 `dev/baseline/<skill>/`의 표본으로 한다([dev/baseline/README.md](dev/baseline/README.md)). techblog의 `calibrate.py`는 합친 값으로 계산하고 보정값(`split_thresholds`)만 저장한다.

## 스킬 추가

1. `python dev/new_skill.py <이름>`으로 slot 파일, 작업 문서 `workflow.md`, core 복사본을 만든다. 이름은 소문자, 숫자, 하이픈으로 쓴다.
2. 만든 파일의 `TODO:`를 채운다. SKILL.md에는 장르, 기준 글, 기본 독자와 단계마다 읽을 core 문서를, settings.md에는 어투 선택지와 기본값을, genre.md에는 구성과 분량을 적는다. `TODO:`가 남아 있으면 `tests/test_core.py`가 실패한다.
3. 기준 글 표본이 있으면 `dev/baseline/<이름>/`에서 기준치를 보정한다. 없으면 core의 Gate, policy, 고정 기준만으로 검사한다.
4. eval 케이스는 `evals/<이름>-<케이스>/`에 추가하고 `claude plugin eval . --case '<이름>-*'`로 실행한다. techblog의 케이스는 이 규칙을 정하기 전에 만들어서 이름에 스킬 이름이 없다.
5. `python -m unittest discover -s tests`와 `claude plugin validate .`를 실행한다. 사람이 읽을 소개를 `skills/<이름>/README.md`에 작성하고, 루트 README.md의 스킬 표와 manifest 설명에 새 스킬을 추가한다.
