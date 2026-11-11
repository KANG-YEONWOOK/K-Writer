# K-Writer 구조

K-Writer는 한국어 글쓰기 스킬 여러 개를 제공하는 플러그인이다. 모든 스킬이 같은 한국어 규칙과 검사 스크립트(core)를 사용하고, 글의 종류(장르)에 따라 달라지는 독자, 어투 선택지, 글의 구성, 기준치는 스킬이 정한다. 이 문서는 저장소를 수정하는 사람을 위한 문서이고, 스킬을 실행할 때는 읽지 않는다.

## 스킬

글을 쓰려면 글의 바탕이 될 자료, 글의 목적, 분량, 어투를 정해야 한다. write는 이 값을 모두 사용자에게 받는 기본 스킬이다. 나머지 스킬은 목적, 어투 선택지, 구성을 미리 정해 두고 남은 값만 사용자에게 받는다.

| 스킬 | 목적 | 사용자에게 받는 값 | 어투 | 구성 | 독립 점검 | 출력 |
|---|---|---|---|---|---|---|
| write | 사용자가 정한다(설명, 설득, 안내, 기록, 직접 입력) | 자료나 주제, 목적, 분량, 어투 | Default, Casual, Plain, 직접 입력 | 목적별 구성 | 본문 1,500자 이상이면 subagent 네 개, 미만이면 두 개 | 파일 |
| techblog | 자료를 기술 블로그 글로 정리 | 자료, 독자, 어투, 분량 | Default, Casual | 기술 블로그 글의 구성 | subagent 네 개 | 파일 |
| brief | 자료를 요약 | 자료, 분량, 어투 | Default, Casual, Plain, 직접 입력 | 핵심 문장과 분량별 형식 | 요약만 읽고 보고하는 subagent 한 개 | 대화(`-o`가 있으면 파일에도 저장) |

새 스킬은 write가 사용자에게 묻는 값 중 어느 것을 미리 정할지부터 정한다. 목적을 정하면 그 목적의 독자, 화자, 구성을 genre.md에 적고, 어투 선택지와 기본값을 settings.md에 적는다.

독립 점검의 범위는 글의 길이에 맞춘다. core의 독자 점검, 후처리, 한국어 문장 점검 문서는 긴 글을 기준으로 작성했다. 0.5.0의 테스트 실행에서 이 절차를 다섯 문장짜리 요약에 그대로 적용했더니 독자 점검이 찾은 질문마다 설명이 추가되어 요약이 469자에서 630자로 늘었고 실행에 27분이 걸렸다. 그래서 brief는 요약만 읽는 subagent가 읽다가 멈춘 부분을 보고하고, 수정은 상위 agent가 정한 분량 안에서 한다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `core/` | 모든 스킬이 함께 사용하는 문서(`references/`)와 검사 스크립트(`scripts/`)의 원본. `dev/sync_core.py`가 스킬 폴더마다 같은 이름으로 복사하므로 스킬 폴더의 복사본은 직접 수정하지 않는다 |
| `dev/sync_core.py`, `dev/new_skill.py`, `dev/borrow_thresholds.py` | core를 스킬 폴더에 복사하는 스크립트, 새 스킬 폴더를 만드는 스크립트, 기준 글 표본이 없는 스킬에 다른 스킬의 기준치를 복사하는 스크립트 |
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
| `references/tone.md` | Default(합니다체), Casual(해요체), Plain(해라체)의 종결과 대응표, 사용자가 직접 정한 어투의 규칙, 숫자와 영어 뒤 조사 | 7단계(어투 적용) |
| `references/ai-patterns.md` | lint 항목마다 AI 문체 표현을 수정하는 방법 | 5단계부터. 초안을 작성하기 전에는 읽지 않는다 |
| `references/reader-check.md`, `revision.md`, `korean-review.md` | 독자 점검, 후처리, 한국어 문장 점검 절차 | 6단계(독립 점검) |
| `scripts/lint_ko.py`, `patterns_ko.json`, `rules.json` | 문체 검사 스크립트, 정규식 패턴, 검사 항목 정의와 짧은 글 기준 | 5단계부터 |
| `scripts/revise_ko.py`, `tone_check.py` | 후처리 보조, 어투를 바꾼 글과 Default 초안이 문장 끝만 다른지 검사, 작업 파일 삭제 | 6~8단계 |

### 스킬 폴더의 파일(slot)

| 파일 | 내용 |
|---|---|
| `SKILL.md` | frontmatter(`name`은 폴더 이름, `description`은 1,024자 이하, `allowed-tools`, `metadata.version`은 플러그인 버전), 장르와 기준 글, 기본 독자, 작업 순서와 단계마다 읽을 문서. Codex는 플러그인 스킬의 SKILL.md를 8,000바이트까지만 읽으므로 LF와 CRLF 모두 6,000바이트 이하로 유지한다 |
| `README.md` | 사람이 읽는 스킬 소개: 사용법, 작성 과정, 기준치와 검사 항목, 한계. 스킬을 실행할 때는 읽지 않는다 |
| `references/settings.md` | 인자, 설정값 표(묻는 모드, 기본값, 선택지), AskUserQuestion 질문 표, 정한 값을 사용하는 단계 |
| `references/genre.md` | 독자와 화자, 글의 구성, 분량, 장르 표현 규칙과 예. genre.md가 style-guide.md의 규칙을 바꾼다고 명시한 부분만 genre.md가 우선한다 |
| `references/rubric.md` | 합격 조건, 판정 항목, 기준치의 근거 |
| `scripts/thresholds.json` | `skill.standard`(기준 글 이름)와 기준 글로 보정한 값 |
| 작업 문서 | 이름은 스킬이 정한다. techblog와 write는 `drafting.md`, `validation.md`, `finalization.md`이고 brief는 `drafting.md`, `validation.md`다. 초안을 작성하기 전에 읽는 작업 문서는 `drafting.md`로 이름을 정하고 사용할 표현만 적는다(AGENTS.md) |

Codex 0.155.1과 0.162.1은 플러그인 스킬의 `SKILL.md`를 frontmatter까지 포함해 UTF-8 기준 8,000바이트까지만 프롬프트에 넣는다. 이 한도를 넘으면 앞부분만 남기고 내용이 잘렸다는 경고를 출력한다. `tests/test_portability.py`는 2,000바이트의 여유를 두고 스킬마다 `SKILL.md`가 6,000바이트 이하인지 확인한다.

core 문서는 스킬 문서를 slot 이름(settings.md, genre.md, rubric.md, thresholds.json)으로만 가리키고, 스킬의 단계 번호와 작업 문서 이름을 사용하지 않는다. 단계는 이름으로 가리킨다: 자료 읽기, fact sheet, 개요, 초안 쓰기, 초안 점검, 독자 점검, 후처리, 한국어 문장 점검, 수정 후 검토, 어투 적용, 결과 보고. 자연스러움의 기준은 "스킬이 정한 기준 글"로 표현하고, 스킬은 SKILL.md와 subagent prompt에 기준 글을 적는다. techblog의 기준 글은 사람이 쓴 한국어 기술 블로그 글이다. `tests/test_core.py`가 이 규칙을 검사한다.

## core 복사본

`dev/sync_core.py`가 core 파일을 모든 스킬 폴더의 `references/`, `scripts/`에 같은 이름으로 복사한다. 스킬 폴더는 하나씩 따로 설치되고 로드되기 때문이다(플러그인 cache의 `skills/<이름>/`, `~/.claude/skills/`, `~/.agents/skills/`, Codex `$skill-installer`). 복사본이 있으면 링크, 검사 명령, `allowed-tools`의 `${CLAUDE_SKILL_DIR}/scripts/*`가 모두 그 폴더 안의 경로를 가리킨다. Codex는 SKILL.md의 변수를 치환하지 않으므로, 스킬 폴더 밖의 core를 읽게 하면 모델이 경로를 직접 계산해야 한다.

- core를 수정한 뒤 `python dev/sync_core.py`를 실행한다. 스킬 폴더의 복사본은 직접 수정하지 않는다.
- `python dev/sync_core.py --check`와 `tests/test_core.py`가 복사본이 원본과 바이트 단위로 같은지 확인한다.
- core에서 파일을 삭제하거나 이름을 바꾸면 `python dev/sync_core.py --remove <이름>`으로 모든 스킬에서 복사본도 삭제한다.
- 검사 스크립트 출력의 첫 줄(`techblog lint`, `techblog repeats`)에는 스크립트가 있는 스킬 폴더의 이름이 들어간다.

## 설정과 어투

스킬의 settings.md가 설정값과 선택지, 기본값을 정하고, core의 settings-protocol.md가 묻는 순서를 정한다. 사용자는 요청에 값을 적거나 질문에 답해 값을 선택하고, 선택지에 없는 값은 "직접 입력"으로 적는다. 자료나 주제처럼 기본값이 없는 값은 settings.md의 "반드시 받는 값"에 적는다. 이 값이 요청에 없으면 스킬은 대화에서 먼저 묻고 답을 받은 뒤에 나머지 값을 묻는다.

core의 어투는 Default(합니다체), Casual(해요체), Plain(해라체) 세 가지이고, 스킬은 이 중 사용할 어투와 기본값을 정한다. 스킬이 어투의 "직접 입력"을 허용하면 사용자가 적은 어투(반말, 개조식 등)로도 쓴다. 어느 어투든 내용은 Default 초안에서 정하고 문장마다 종결부만 바꾼다(tone.md). `lint_ko.py --tone`과 `tone_check.py --tone`은 `plain`으로 해라체를 판정하고, `free`로 직접 정한 어투를 받아 종결 판정을 생략한다. 종결을 판정하는 어투를 추가하려면 tone.md와 `lint_ko.py`의 `TONE_CLASSES`, `tone_check.py`의 `TARGETS`를 함께 수정한다.

스킬의 출력은 파일로 저장하는 글일 수도 있고 대화로 하는 답변일 수도 있다. 대화로 답하는 스킬이 검사 스크립트를 사용하려면 답변을 작업 파일에 쓰고 lint를 실행한 뒤 그 파일을 삭제한다.

## 기준치

`lint_ko.py`는 core의 `rules.json`과 스킬의 `thresholds.json`을 합친 값으로 판정한다(`load_thresholds`).

- `rules.json`: 검사 항목 110개의 정의, Gate와 policy, 고정 기준(fixed), 짧은 글 기준(`short`). 모든 스킬에 공통이다. 항목을 추가하거나 수정할 때는 이 파일을 수정한다.
- `thresholds.json`: 그 스킬의 기준 글로 보정한 값(gate도 fixed도 아닌 항목의 PASS, WARN 경계와 사람 글 분포). metric 필드를 덮어쓰거나 `drop`으로 항목을 제외할 수 있다. 보정값이 없는 분포 지표는 INFO로 값만 보고한다.
- 가져온 기준치: write와 brief는 아직 기준 글 표본이 없다. 표본이 없으면 부정 대구나 번역투 같은 AI 문체 항목도 판정하지 못하므로, 두 스킬은 특정 표현의 빈도를 세는 항목 15개의 기준치를 techblog에서 가져온다. `thresholds.json`의 `borrowed`에 가져올 스킬과 항목을 적고 `python dev/borrow_thresholds.py`로 복사한다. techblog의 기준치를 다시 보정하면 이 명령을 다시 실행하고, `--check`와 `tests/test_tones_and_profiles.py`가 복사한 값이 원본과 같은지 확인한다. 문장 길이, 문단, 목록 비중처럼 글의 종류에 따라 달라지는 항목은 가져오지 않는다.
- 짧은 글 기준: `lint_ko.py --short`와 `revise_ko.py`의 `check --short`, `audit --short`는 `short`의 값을 적용한다. 문장 수가 적으면 문장 하나로 값이 크게 달라지는 분포 항목을 제외하고, `count`에 적은 1,000자당 비율 항목을 개수로 판정하며, poisson 항목은 한 번까지 허용한다. brief는 요약에, write는 본문이 공백 제외 1,500자 미만인 글에 이 기준을 사용한다. 스킬의 `thresholds.json`에 `short`가 있으면 그 값이 core의 값을 대신한다.
- 스킬별 허용: 스킬의 `thresholds.json`은 `allow_patterns`(패턴 ID마다 검사하지 않을 정규식), `allow_imperative`(Default 글의 요청문 "~해 주세요"), `allow_inga_question`(Default 글의 질문 "~인가요?")으로 그 장르에서 자연스러운 표현을 허용한다. 항목의 `kind`를 `check`로 바꾸면 Gate 대신 점검 후보로 출력하고, `group`을 `fact`로 정하면 "자료 대조 후보"로 묶어 출력한다. write가 이 값들을 사용하고 근거는 write의 rubric.md에 있다.
- 보정은 `dev/baseline/<skill>/`의 표본으로 한다([dev/baseline/README.md](dev/baseline/README.md)). techblog의 `calibrate.py`는 합친 값으로 계산하고 보정값(`split_thresholds`)만 저장한다.

## 스킬 추가

1. `python dev/new_skill.py <이름>`으로 slot 파일, 작업 문서 `workflow.md`, core 복사본을 만든다. 이름은 소문자, 숫자, 하이픈으로 쓴다.
2. 만든 파일의 `TODO:`를 채운다. SKILL.md에는 장르, 기준 글, 기본 독자와 단계마다 읽을 core 문서를, settings.md에는 반드시 받는 값, 어투 선택지와 기본값을, genre.md에는 구성과 분량을 적는다. 작업 문서는 `workflow.md` 하나로 두거나 초안 작성 전후로 나눈다. `TODO:`가 남아 있으면 `tests/test_core.py`가 실패한다.
3. 기준 글 표본이 있으면 `dev/baseline/<이름>/`에서 기준치를 보정한다. 없으면 core의 Gate, policy, 고정 기준만으로 검사하거나, `thresholds.json`에 `borrowed`를 적고 `python dev/borrow_thresholds.py`로 표현 항목의 기준치를 다른 스킬에서 가져온다.
4. eval 케이스는 `evals/<이름>-<케이스>/`에 추가하고 `claude plugin eval . --case '<이름>-*'`로 실행한다. techblog의 케이스는 이 규칙을 정하기 전에 만들어서 이름에 스킬 이름이 없다.
5. `python -m unittest discover -s tests`와 `claude plugin validate .`를 실행한다. 사람이 읽을 소개를 `skills/<이름>/README.md`에 작성하고, 루트 README.md의 스킬 표와 manifest 설명에 새 스킬을 추가한다.
