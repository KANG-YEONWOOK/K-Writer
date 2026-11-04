# K-Writer

K-Writer는 Claude Code와 Codex에서 사용하는 한국어 글쓰기 plugin입니다. AI가 한국어로 쓴 글에는 "A가 아니라 B입니다"처럼 한쪽을 부정한 뒤 다른 쪽을 말하는 문장(부정 대구)이 사람이 쓴 글보다 훨씬 자주 나오고, 영어 자료를 옮긴 글에는 영어 구절을 단어 그대로 옮긴 직역이 생깁니다. K-Writer의 목표는 부정 대구처럼 AI가 쓴 글에 자주 나오는 표현의 빈도를 사람 글에서 측정한 수준으로 줄이고 직역을 찾아 수정한 자연스러운 한국어 글을 만드는 것입니다. 글에는 사용자가 건넨 자료(정리하거나 옮길 원문)에 있는 사실만 담습니다.

K-Writer는 글의 종류마다 skill을 하나씩 담습니다. 모든 skill은 같은 한국어 문장 규칙, 어투 규칙, 검사 스크립트를 사용하고, skill마다 그 글의 독자, 어투 선택지, 구성, 기준치를 정합니다. 지금 제공하는 skill은 techblog 하나입니다. 저장소의 구조와 skill을 추가하는 방법은 [`ARCHITECTURE.md`](ARCHITECTURE.md)에 있습니다.

| skill | 하는 일 | 호출 |
|---|---|---|
| techblog | 논문 PDF, 기술 문서, 웹 페이지, 붙여넣은 텍스트의 핵심 내용을 한국어 기술 블로그 글로 정리합니다. | Claude Code `/k-writer:techblog`, Codex `$k-writer:techblog` |

## AI가 쓴 글에 자주 나오는 표현을 줄이는 방법

### 사람이 쓴 글로 정한 기준치

techblog에 든 검사 스크립트 `lint_ko.py`는 글에서 부정 대구와 쉼표 같은 표현의 수, 문장과 문단의 길이를 세는 lint입니다. `lint_ko.py`는 항목마다 센 값을 기준치와 비교해 통과, 경고, 불합격으로 판정합니다.

기준치는 토스, 카카오, 당근, 네이버 D2, 우아한형제들, NAVER CLOVA 기술 블로그의 사람 글 600편을 `lint_ko.py`로 측정해 정했습니다. 쉼표처럼 많을수록 나쁜 항목은 대부분 사람 글의 95%가 넘지 않는 값까지를 통과로, 99.5%가 넘지 않는 값에 여유를 추가한 값까지를 경고로, 그보다 큰 값을 불합격으로 판정합니다. 항목별 계산 방식은 [`rubric.md`](skills/techblog/references/rubric.md)에 있습니다. 저장소에는 사람 글의 원문을 저장하지 않고 URL 목록과 측정값만 저장합니다.

기준치를 계산할 때 측정한 글에는 발행 시기에 따라 다른 가중치를 줍니다. 글쓰기에 AI를 사용한 비중이 낮은 2018-01-01~2022-11-30(기준 기간)의 글은 1.0, 2022-12-01~2024-12-31 글은 0.5, 2025년 이후 글은 0입니다. 부정 대구와 쉼표 같은 항목의 기준치는 기준 기간 글로만 계산합니다. 2022-12-01~2024-12-31 글의 가중치 0.5는 문장 길이와 문단 길이 같은 나머지 항목에만 적용합니다. 가중치가 0인 2025년 이후 글에는 부정 대구처럼 AI가 쓴 글에 자주 나오는 표현이 기준 기간 글보다 많았습니다. 예를 들어 합니다체 글 한 편에 든 부정 대구 문장 수의 중앙값은 2025년 이후 글이 3.0, 기준 기간 글이 1.0이었습니다.

기준치를 계산할 때 빼 둔 기준 기간 사람 글 31편(holdout)으로는 만든 기준치가 사람 글을 얼마나 통과시키는지 확인합니다. 이 31편을 techblog가 초안의 `lint_ko.py` 결과에 적용하는 통과 조건(아래 표의 Gate에 해당하는 표현과 불합격 항목이 없고 경고가 3개 이하)으로 판정하면 28편(90%)이 통과합니다. 목표는 85% 이상입니다. 이 판정에서 어투 혼용과 맞춤법처럼 techblog의 글에만 적용하는 규칙은 뺐습니다.

techblog는 `lint_ko.py`의 판정에 따라 수정할 때 경고나 불합격으로 판정된 항목만 수정하고 그 항목이 기준치 안으로 들어오면 멈춥니다. 사람 글에도 있는 표현을 0으로 만드는 것은 목표가 아닙니다. AI 모델의 글과 사람 글에 나오는 부정 대구를 비교한 논문 Boggia(2026)는 초안을 완성한 뒤 다시 작성하게 하면 모델이 모든 장르에서 부정 대구를 0으로 만들어 부정 대구의 빈도 분포가 사람 글과 달라진다고 보고했습니다.

### 연구와 검토로 정한 검사 항목

어떤 표현을 셀지는 AI가 한국어로 쓴 글을 측정한 연구로 정했습니다. 한국어 학술지 초록 398,296건을 분석한 Lee(2026)에서 "단순한 X를 넘어"가 들어간 초록의 비율은 2019년 0.12%, 2026년 4.93%였습니다. AI가 쓴 한국어 글의 표현을 분류하고 사람 글과 비교한 GitHub 프로젝트 im-not-ai에서 부정 대구는 1,000자당 AI 글이 5.8회, 사람 글이 0.6회였습니다. LLM(Claude 같은 대규모 언어 모델)이 생성한 한국어 글을 가려내는 연구 KatFishNet에서 쉼표가 있는 문장의 비율은 사람 에세이가 26.3%, LLM 글이 61.0%였습니다.

평가 기준 문서 [`rubric.md`](skills/techblog/references/rubric.md)는 검사 항목을 네 종류로 나누고 항목마다 근거 자료를 적어 둡니다.

| 종류 | 판정 | 예 |
|---|---|---|
| Gate | 한 번만 나와도 불합격. 정해 둔 형태는 `lint_ko.py`가 세고 자료에 없는 사실은 techblog가 글과 자료를 대조해 찾음 | 자료에 없는 사실, 글쓴이가 직접 겪은 것처럼 꾸민 경험, "물론입니다" 같은 챗봇 응답 흔적, 어투 혼용, "단순한 X를 넘어", 가운뎃점(`·`), em dash(영어 문장에서 사용하는 긴 줄표 `—`), 맞춤법 오류 |
| 자동 측정 항목 | `lint_ko.py`가 기준치와 비교해 통과, 경고, 불합격 | 부정 대구, 쉼표, 강조 문장("핵심은 ~입니다" 같은 문장), 번역투("~에 의해", "중요한 역할을 하다" 같은 정해 둔 표현), 굵은 글씨와 목록 비중, 문장 길이와 문단 길이 분포 |
| 점검 후보 | `lint_ko.py`가 판정하지 않고 다시 읽을 문장을 보여 주면 아래 순서의 5단계(초안 점검)에서 techblog가 읽고 고칠지 정함 | 직역 후보("변화가 남아 있다"), 사람 글이 다른 말로 부르는 말("낱말"), 물건이나 몸동작에 빗댄 말("행동을 못 박았습니다"), 부정이 걸리는 범위가 둘로 읽히는 문장, 처음 나온 용어 |
| 판정 항목 | 5단계에서 techblog가 초안을 읽고 항목마다 0~2점을 매김 | 문장을 따로 읽어도 무엇에 대한 말인지 알 수 있는가, 한국어가 자연스러운가 |

초안은 Gate 위반과 불합격 항목이 없고 경고가 3개 이하이며 판정 항목이 평균 1.6점 이상이고 0점이 없어야 합격입니다. 아래 순서의 6단계(점검과 수정)를 마친 최종 글은 Gate 위반과 불합격 항목이 없어야 하고, 6단계의 수정 때문에 Gate와 자동 측정 항목의 판정이 초안보다 나빠지면 안 됩니다. 다만 자동 측정 항목 중 문장 길이, 문단 길이, 목록 비중처럼 문장과 문단의 분포를 측정하는 항목의 경고는 후처리에서 그 글의 독자에게 더 읽기 쉬운 형태로 고른 결과라면 남길 수 있으므로 최종 글의 경고는 3개를 넘을 수 있습니다. techblog는 남긴 경고를 이유와 함께 사용자에게 보고합니다.

AI가 쓴 글은 사전에서 맞는 단어를 고르고도 어색할 때가 있습니다. version을 "판"으로, test를 "시험"으로, word를 "낱말"로 쓰는 경우입니다. 사람 글 600편에서 "버전"은 1,305번 나왔지만 version을 의미하는 "판"은 한 번도 나오지 않았고, 스킬 없이 Claude Opus 5.5로 쓴 개발 문서와 대화(한글 81만 자)에는 74번 나왔습니다. `lint_ko.py`는 version을 쓴 "판"을 한 번만 나와도 불합격으로 판정합니다. "낱말", "시험", "사본"처럼 사람 글이 다른 말로 부르는 말은 사람 글의 비율을 넘으면 경고나 불합격으로 판정하고, 판정과 상관없이 걸린 문장을 점검 후보로 보여 줍니다. 이전 버전의 skill 문서가 "낱말"을 107번 사용하자 그 문서를 읽고 쓴 글에도 "낱말"이 29번 나와서, 0.4.0에서 문서의 말도 같은 기준으로 바꿨습니다. 같은 가상 노트로 쓴 최종 글에서 이런 말은 0.3.1이 15곳, 0.4.0이 0곳이었습니다. 자료 목록과 측정값은 [`plain-terms.md`](dev/baseline/techblog/plain-terms.md)에 있습니다.

AI가 쓴 글에 자주 나오는 표현의 목록(`skills/techblog/references/ai-patterns.md`)은 techblog가 초안을 작성한 뒤에만 읽습니다. 언어 모델이 반복하는 상투 표현(slop)을 찾아 없애는 방법을 다룬 연구 Antislop(2025)은 피할 표현의 목록을 초안 작성 전에 보여 주면 그 표현이 오히려 늘 수 있다고 지적했습니다.

`lint_ko.py`는 정규식으로 표현을 셉니다. 직역, 그 분야에서 사용하지 않는 번역어, 주어와 어울리지 않는 서술어 중 정규식으로 셀 수 있는 형태는 위 표의 번역투와 직역 후보 같은 일부뿐입니다. 나머지는 아래 6단계의 한국어 문장 점검이 문장마다 읽어서 찾습니다. 이 점검의 유형 21가지는 K-Writer 개발자가 techblog로 쓴 글을 다시 읽고 수정한 검토 기록과, 피동을 두 번 겹친 말이나 같은 의미가 두 번 들어간 겹말처럼 글쓰기에서 일반적으로 점검하는 표현에서 정했습니다.

### techblog가 글을 쓰는 순서

techblog는 1~5단계에서 아래 4단계의 초안 규칙과 `lint_ko.py`의 기준치를 어느 글에나 같게 적용해 초안을 작성하고 점검합니다. 6단계에서는 초안을 작성한 대화를 이어받지 않은 subagent 네 개가 차례로 글을 다시 읽습니다.

1. 자료를 끝까지 읽습니다.
2. 자료의 수치, 주장, 한계와 글에 사용할 용어의 표기와 설명을 fact sheet에 적습니다. fact sheet는 이렇게 자료의 사실을 모아 두는 작업 파일이고, 글의 수치와 주장은 fact sheet에서만 가져옵니다.
3. 한국어 문장 규칙(`skills/techblog/references/style-guide.md`)과 기술 블로그 글의 구성 지침(`skills/techblog/references/genre.md`)을 읽고 제목과 절 구성을 정합니다.
4. 합니다체로 초안을 작성합니다. 문장마다 무엇에 대한 말인지 드러내고, 수치가 포함된 문장에는 무엇을 측정한 값이고 무엇과 비교한 값인지 함께 씁니다. 처음 나오는 용어는 그 자리에서 무엇인지 설명하고 한 글에서 한 단어는 한 의미로만 사용합니다.
5. `lint_ko.py`로 초안을 검사합니다. Gate와 불합격 항목은 반드시 수정하고 경고 항목은 삭제해도 정보가 줄지 않는 구절이 있을 때만 수정합니다. 어느 항목이든 기준치 안으로 들어오면 수정을 멈춥니다. `lint_ko.py`는 글의 수치 중 fact sheet에 없는 값도 찾습니다. 이어서 techblog가 문장을 하나씩 따로 읽어 무엇에 대한 말인지 알 수 있는지 확인합니다. 그다음 점검 후보 문장을 읽고 글의 수치와 주장을 fact sheet와 대조한 뒤 위 표의 판정 항목을 0~2점으로 매깁니다.
6. subagent 네 개가 차례로 글을 점검합니다.
   - 자료와 fact sheet를 읽지 않은 subagent가 글만 읽고, 무엇인지와 무엇을 하는지 글의 설명으로 답할 수 없는 말을 적습니다(독자 점검). 자료를 읽고 1~5단계를 수행한 상위 agent(techblog를 실행하고 subagent에게 점검을 맡긴 agent)는 빠진 설명을 이미 아는 내용으로 채워 읽기 때문에 이 점검을 따로 맡깁니다.
   - 초안을 작성하지 않은 subagent가 글 전체를 처음부터 읽은 뒤, 수치가 포함된 문장마다 반복된 같은 비교 기준을 줄이거나 독자 점검이 적은 말에 빠진 설명을 더하는 수정을 필요한 곳에만 합니다(후처리). 독자 점검이 적은 말마다 설명을 더했는지, 더하지 않았다면 그 이유를 보고합니다. 이 subagent는 상위 agent가 초안에서 계산한 차이와 비율을 자료 원문으로 다시 확인합니다. 어떤 형태가 읽기 쉬운지는 글마다 다르므로 수정할지는 "이 구절을 삭제하면 독자가 잃는 정보가 있는가" 같은 판단 질문으로 정합니다. 이 subagent는 글을 처음부터 다시 쓰지 않습니다.
   - 또 다른 subagent가 문장마다 읽고 영어 동사의 직역, 그 분야에서 사용하지 않는 번역어, 주어와 어울리지 않는 서술어 같은 21가지 유형에 해당하는 문장만 수정합니다(한국어 문장 점검). 상위 agent는 이 subagent가 수치나 사실을 바꾼 수정을 되돌립니다.
   - 마지막 subagent가 초안과 수정한 글을 대조해 수정한 문장 앞뒤의 문단과 결론에서 주체, 조건, 추정의 강도가 그대로인지 검토합니다(수정 후 검토). 이 subagent는 찾은 곳을 보고만 하고 수정은 상위 agent가 합니다.
7. Casual(해요체)로 요청했으면 6단계를 마친 Default(합니다체) 글의 문장 끝만 해요체로 바꾸고, `tone_check.py`로 Default 글과 Casual 글의 문장 수와 수치가 같은지 확인합니다.
8. 작업 파일을 삭제하고 저장 경로와 검사 결과를 보고합니다.

subagent를 실행하는 도구가 없거나 사용자가 subagent를 사용하지 말라고 하면 상위 agent가 6단계의 네 점검을 차례로 직접 수행하고 그 사실을 보고합니다.

## techblog 사용법

techblog의 어투는 Default(합니다체)와 Casual(해요체) 중에서 선택합니다. Casual 글은 "~더라고요", "~네요" 같은 어미 없이 정중한 해요체로만 문장을 맺습니다. Casual 글은 같은 실행에서 6단계를 마친 Default 글의 문장 끝만 바꿔 만들기 때문에 Default 글과 Casual 글은 문장 끝만 다르고 내용이 같습니다. Casual로 요청한 실행에서 Default 글은 작업 파일이라서, `--keep-work`를 붙이지 않으면 techblog가 Casual 글을 만든 뒤 지웁니다.

Claude Code:

```
/techblog paper.pdf
/techblog casual https://arxiv.org/pdf/2309.06180 -o paged-attention.md --defaults
/techblog default design-doc.md 독자는 백엔드 개발자, 분량은 5,000자 안팎
/techblog casual --retone paged-attention.md
```

Codex:

```text
$techblog paper.pdf
$techblog casual https://arxiv.org/pdf/2309.06180 -o paged-attention.md --defaults
$techblog default design-doc.md 독자는 백엔드 개발자, 분량은 5,000자 안팎
$techblog casual --retone paged-attention.md
```

다른 plugin이나 skill에 같은 이름의 명령이 있으면 Claude Code에서는 `/k-writer:techblog`, Codex에서는 `$k-writer:techblog`로 호출합니다. 셸에서 `codex exec`로 호출할 때는 셸이 `$techblog`를 셸 변수로 읽지 않도록 호출 문자열 전체를 작은따옴표로 감쌉니다(`codex exec '$techblog default design-doc.md --defaults'`).

요청에 독자, 어투, 분량이 없으면 techblog는 글을 쓰기 전에 그 값을 묻습니다. 기본값은 사전 지식이 없는 독자, Default 어투, 자료 크기에 맞춘 분량(논문 한 편이면 공백 제외 5,000~10,000자)입니다. `claude -p`나 `codex exec`처럼 답할 사람이 없는 실행에는 `--defaults`를 붙입니다.

| 인자 | 설명 |
|---|---|
| `default`, `casual` | 글의 어투입니다. `합니다체`, `해요체`라고 써도 됩니다. |
| 자료 | 정리할 파일(PDF, 마크다운, 텍스트)의 경로나 URL입니다. 생략하면 대화에 붙여넣은 텍스트를 사용합니다. |
| `-o <경로>` | 글을 저장할 경로입니다. 생략하면 현재 폴더에 글 주제를 나타내는 영문 이름으로 저장합니다. |
| `--retone` | 이미 쓴 글의 어투만 바꿉니다. 문장 순서, 수치, 고유명사는 바꾸지 않습니다. |
| `--keep-work` | fact sheet와 후처리 전 초안 같은 작업 파일을 삭제하지 않습니다. |
| `--defaults` | 설정값을 묻지 않고 기본값을 사용합니다. |
| `short` | short 모드로 실행합니다. |
| 추가 지시 | "독자는 백엔드 개발자"처럼 문장으로 덧붙입니다. 값을 적으면 그 값은 다시 묻지 않습니다. |

short 모드는 Slack에 올리는 질문, 검토 요청, 보고, 진행 알림의 고정 문형처럼 도구가 만든 짧은 영어 글을 같은 구조, 순서, 분량 그대로 한국어로 옮기는 모드입니다. fact sheet와 subagent 점검을 거치지 않고 몇 분 안에 끝내는 것이 목표이고, 규칙은 [`short.md`](skills/techblog/references/short.md)에 있습니다.

[`examples/`](examples/) 폴더에는 LLM이 여러 요청에 동시에 답할 때 메모리를 관리하는 방법을 제안한 PagedAttention 논문(SOSP 2023, CC BY 4.0)을 techblog로 정리한 Default 글과 Casual 글이 있습니다.

## 설치

### Claude Code

Claude Code 세션에서 marketplace(설치할 수 있는 plugin의 목록)를 등록하고 plugin을 설치합니다.

```
/plugin marketplace add KANG-YEONWOOK/K-Writer
/plugin install k-writer@k-writer
```

새 버전은 아래 명령으로 갱신한 뒤 Claude Code를 다시 시작해 적용합니다.

```bash
claude plugin marketplace update k-writer
claude plugin update k-writer@k-writer --scope user
```

### Codex

`codex plugin add` 명령이 있는 Codex CLI에서 아래 명령을 실행합니다.

```bash
codex plugin marketplace add KANG-YEONWOOK/K-Writer
codex plugin add k-writer@k-writer
```

업데이트할 때는 아래 명령을 실행하고 새 세션을 엽니다.

```bash
codex plugin marketplace upgrade k-writer
codex plugin add k-writer@k-writer
```

### skill 폴더 직접 복사

plugin 대신 `skills/techblog` 폴더를 개인 skill 폴더에 복사해도 같은 skill을 사용할 수 있습니다. Claude Code의 개인 skill 폴더는 `~/.claude/skills/`이고 Codex의 개인 skill 폴더는 `~/.agents/skills/`입니다. Codex에서는 skill이 두 번 표시되지 않도록 직접 복사와 plugin 설치 중 하나만 합니다.

```bash
git clone https://github.com/KANG-YEONWOOK/K-Writer.git
mkdir -p ~/.claude/skills && cp -r K-Writer/skills/techblog ~/.claude/skills/   # Claude Code
mkdir -p ~/.agents/skills && cp -r K-Writer/skills/techblog ~/.agents/skills/   # Codex
```

### 필요한 환경

Python 3.8 이상이 설치돼 있으면 techblog가 검사 스크립트를 실행합니다. Python이 없으면 techblog는 같은 기준을 문서로 읽고 직접 점검하며 자동 검사를 하지 못했다고 보고합니다. 검사 스크립트는 외부 패키지를 사용하지 않습니다.

Codex에 PDF 읽기 기능이 없으면 techblog는 PDF를 처리하는 오픈소스 라이브러리 Poppler의 `pdftotext`(텍스트 추출)와 `pdftoppm`(PDF의 쪽을 이미지로 변환)으로 PDF를 읽습니다. techblog는 필요한 도구를 자동으로 설치하지 않습니다.

## 한계

`lint_ko.py`는 형태소 분석기 없이 정규식으로 표현을 세므로 사람 글의 일부 표현도 잘못 잡습니다. 그래서 기준치도 사람 글에 같은 스크립트를 실행한 값으로 정했습니다. 기준 기간의 해요체 사람 글 15편은 모두 당근 글이라서 해요체 글로만 계산하는 기준치는 대부분 당근 글의 값으로 정해집니다.

한국어 문장 점검은 subagent가 문장마다 읽어서 찾기 때문에 실행마다 찾는 문장이 다릅니다. techblog로 쓴 글에 자료와 다른 내용이 없다는 것도 보장되지 않습니다. 후처리는 수정한 문장과, 상위 agent가 초안에서 자료의 값으로 계산한 차이와 비율만 자료 원문에서 다시 확인합니다. 그래서 초안 단계에서 생긴 사실 오류는 후처리 뒤에도 남을 수 있습니다. 글을 공개하기 전에 수치와 고유명사를 자료 원문과 대조해야 합니다.

## 개발

```bash
python -m unittest discover tests        # 단위 테스트
python dev/sync_core.py --check           # skill 폴더의 core 복사본이 원본과 같은지 확인
claude plugin validate .                  # plugin manifest 검사
claude plugin eval . --allow-tools Write Edit --scaffold   # evals/ 케이스로 skill이 있을 때와 없을 때를 비교
```

개발에 사용하는 폴더는 아래 표와 같습니다.

| 폴더 | 내용 |
|---|---|
| `core/` | 모든 skill이 함께 사용하는 문서(`references/`)와 검사 스크립트(`scripts/`)의 원본. `dev/sync_core.py`가 skill 폴더마다 같은 이름으로 복사하므로 skill 폴더의 복사본은 고치지 않습니다 |
| `dev/sync_core.py`, `dev/new_skill.py` | core를 skill 폴더에 복사하는 스크립트, 새 skill 폴더를 만드는 스크립트 |
| `dev/baseline/techblog/` | techblog의 기준 글(기술 블로그 사람 글)을 측정하는 `measure.py`, 측정값으로 기준치를 계산하는 `calibrate.py`, 계산 결과 보고서 `calibration.md` |
| `dev/dogfood/` | `claude -p`로 skill을 실행하고 결과 글을 judge 모델(글을 읽고 판정 항목 같은 기준으로 점수를 매기는 모델)로 평가하는 스크립트 |
| `evals/` | skill에 맡길 요청과 채점 기준을 묶은 평가 케이스. `claude plugin eval`로 실행 |
| `dev/codex/` | Codex에서 설치와 글 작성을 검증하는 실행기 |

Codex 0.155.1과 0.162.1은 plugin skill의 `SKILL.md` 중 frontmatter를 포함한 UTF-8 8,000바이트까지만 프롬프트에 넣습니다. 이 한도를 넘으면 앞부분만 남기고 잘림 경고를 출력합니다. `tests/test_portability.py`는 이 한도에 2,000바이트 여유를 두고 skill마다 `SKILL.md`가 6,000바이트 이하인지 확인합니다.

## License

MIT
