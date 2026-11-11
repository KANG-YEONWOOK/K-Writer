# K-Writer

K-Writer는 AI가 사람처럼 자연스러운 한국어 글을 쓰게 하는 Claude Code, Codex 플러그인입니다. 스킬은 세 가지입니다. write는 자료나 주제를 받아 사용자가 정한 목적, 분량, 어투에 맞는 글을 씁니다. techblog는 자료를 한국어 기술 블로그 글로 정리하고, brief는 자료를 요약합니다.

AI가 쓴 한국어 글은 문법이 맞아도 어색합니다. 사람이 쓴 글과 비교하면 다음과 같은 문제가 있습니다.

| 문제 | AI가 쓴 문장 | 수정한 문장 |
|---|---|---|
| 같은 문형과 상투적인 표현을 반복합니다 | "캐시 문제가 아니라 배치 크기 문제입니다. 핵심은 배치 크기입니다." | "배치 크기가 원인입니다." |
| 쉼표를 너무 많이 사용합니다 | "캐시를 비우고, 서버를 재시작했습니다." | "캐시를 비우고 서버를 재시작했습니다." |
| 영어 표현을 직역합니다 | "새로운 문제가 열렸습니다."(open) | "새로운 문제가 발생했습니다." |
| 사람들이 쓰지 않는 단어를 고릅니다 | "이전 판을 시험했습니다.", "결과 표를 함께 냅니다." | "이전 버전을 테스트했습니다.", "결과 표를 함께 출력합니다." |
| 설명할 내용을 물건이나 몸동작에 비유합니다 | "동작을 못 박았습니다.", "기준은 둘로 갈립니다." | "동작을 명확히 정의했습니다.", "기준은 둘 중 하나입니다." |
| 처음 나온 용어를 설명하지 않습니다 | "write-back이라는 캐시를 사용합니다." | "write-back 캐시(쓰기를 캐시에만 먼저 반영하고 저장소에는 나중에 반영하는 캐시)를 사용합니다." |
| 수치가 무엇을 측정한 값인지 쓰지 않습니다 | "지연이 80% 줄었습니다." | "쓰기 비율이 30% 미만인 서비스에서 p99 지연이 4.2초에서 0.8초로 줄었습니다." |
| 자료에 없는 내용을 지어냅니다 | "저희 팀이 직접 운영해 보니 지연이 줄었습니다." | 자료에 있는 사실만 씁니다 |

K-Writer는 세 단계를 거쳐 이런 문제를 줄입니다.

1. 모델이 글을 쓰기 전에 한국어 문장 규칙을 읽습니다. 규칙의 근거는 사람이 쓴 글에서 측정한 값과, K-Writer 개발자가 AI 글을 다시 읽고 수정한 기록입니다.
2. 초안을 작성하면 검사 스크립트가 AI 글에 자주 나오는 표현을 세어 기준치와 비교하고, 자료에 없는 수치를 찾습니다. 기준치는 사람이 쓴 글에서 측정한 값으로 정했습니다.
3. 초안을 작성하지 않은 subagent가 글을 한 문장씩 다시 읽습니다. 스크립트로 찾을 수 없는 직역과 어색한 문장을 수정하고, 설명이 빠진 용어에는 설명을 추가합니다.

사람이 쓴 글에도 있는 표현을 모두 없애지는 않습니다. 표현의 빈도가 기준치 안으로 들어오면 수정을 멈춥니다. 글의 수치와 주장은 사용자가 제공한 자료와 사용자가 알려 준 내용에서만 가져오고, write가 자료 없이 주제만 받았을 때만 웹에서 출처를 확인한 일반 지식을 함께 사용합니다.

## 설치

### Claude Code

Claude Code 세션에서 marketplace(설치할 수 있는 플러그인의 목록)를 등록하고 플러그인을 설치합니다.

```
/plugin marketplace add KANG-YEONWOOK/K-Writer
/plugin install k-writer@k-writer
```

새 버전으로 업데이트하려면 아래 명령을 실행한 뒤 Claude Code를 다시 시작합니다.

```bash
claude plugin marketplace update k-writer
claude plugin update k-writer@k-writer --scope user
```

### Codex

`codex plugin add` 명령을 지원하는 Codex CLI에서 아래 명령을 실행합니다.

```bash
codex plugin marketplace add KANG-YEONWOOK/K-Writer
codex plugin add k-writer@k-writer
```

업데이트할 때는 아래 명령을 실행하고 새 세션을 엽니다.

```bash
codex plugin marketplace upgrade k-writer
codex plugin add k-writer@k-writer
```

### 스킬 폴더 직접 복사

플러그인을 설치하지 않고 `skills/` 아래의 스킬 폴더를 개인 스킬 폴더에 복사해도 같은 스킬을 사용할 수 있습니다. 개인 스킬 폴더는 Claude Code에서는 `~/.claude/skills/`, Codex에서는 `~/.agents/skills/`입니다. Codex에서 폴더를 직접 복사하고 플러그인도 설치하면 스킬이 두 번 표시되므로 둘 중 하나만 선택합니다.

```bash
git clone https://github.com/KANG-YEONWOOK/K-Writer.git
mkdir -p ~/.claude/skills && cp -r K-Writer/skills/* ~/.claude/skills/   # Claude Code
mkdir -p ~/.agents/skills && cp -r K-Writer/skills/* ~/.agents/skills/   # Codex
```

### 필요한 환경

Python 3.8 이상이 있으면 스킬이 검사 스크립트를 실행합니다. 검사 스크립트는 외부 패키지를 사용하지 않습니다. Python이 없으면 스킬은 기준을 적은 문서를 읽어 글을 직접 점검한 뒤, 자동 검사를 실행하지 못했다고 보고합니다. 스킬마다 추가로 필요한 도구는 스킬 문서에 있습니다.

## 스킬

모든 스킬은 같은 한국어 문장 규칙, 어투 규칙, 검사 스크립트를 사용합니다. write는 글의 종류를 미리 정해 두지 않은 기본 스킬입니다. 자료나 주제, 목적, 분량, 어투를 모두 사용자에게 받고, 요청에 없는 값은 글을 쓰기 전에 묻습니다. techblog와 brief는 글의 목적과 구성을 미리 정해 둔 스킬이라 나머지 값만 묻습니다.

| 스킬 | 하는 일 | 사용자가 정하는 값 | 호출 | 문서 |
|---|---|---|---|---|
| write | 자료(파일, URL, 붙여넣은 텍스트)나 주제로 목적에 맞는 글을 씁니다. 공지, 보고, 제안, 소개 글처럼 기술 블로그 글이나 요약이 아닌 글을 쓸 때 사용합니다. | 자료나 주제, 목적, 분량, 어투(합니다체, 해요체, "~다"로 끝나는 해라체, 직접 입력) | Claude Code `/k-writer:write`, Codex `$k-writer:write` | [사용법과 작성 과정](skills/write/README.md) |
| techblog | 논문 PDF, 기술 문서, 웹 페이지, 붙여넣은 텍스트의 핵심 내용을 한국어 기술 블로그 글로 정리합니다. | 자료, 독자, 분량, 어투(합니다체, 해요체) | Claude Code `/k-writer:techblog`, Codex `$k-writer:techblog` | [사용법과 작성 과정](skills/techblog/README.md) |
| brief | 문서, 웹 페이지, 붙여넣은 텍스트, 대화 내용을 요약합니다. | 자료, 분량(한 줄, 한 문단, 자세히), 어투(합니다체, 해요체, 해라체, 직접 입력) | Claude Code `/k-writer:brief`, Codex `$k-writer:brief` | [사용법과 요약 과정](skills/brief/README.md) |

예를 들어 Claude Code에서 `/k-writer:brief report.pdf`를 실행하면 brief가 분량과 어투를 물은 뒤 보고서를 요약합니다. `/k-writer:write`만 실행하면 write가 어떤 자료나 주제로 글을 쓸지부터 묻습니다.

## 검사할 표현을 정한 근거

어떤 표현을 검사할지는 AI가 쓴 한국어 글을 분석한 자료를 근거로 정했습니다.

- LLM(Claude 같은 대규모 언어 모델)과 관련된 문체 변화를 분석한 [Lee(2026)](https://arxiv.org/abs/2609.07447)에 따르면 한국어 학술지 초록 398,296건에서 "단순한 X를 넘어"가 들어간 초록의 비율은 2019년 0.12%, 2026년 4.93%였습니다.
- AI가 쓴 한국어 글의 표현을 분류하고 사람이 쓴 글과 비교한 GitHub 프로젝트 [im-not-ai](https://github.com/epoko77-ai/im-not-ai)에서 "A가 아니라 B입니다"처럼 한쪽을 부정한 뒤 다른 쪽을 말하는 문장(부정 대구)은 1,000자당 AI 글에서 5.8회, 사람이 쓴 글에서 0.6회 나왔습니다.
- LLM이 생성한 한국어 글을 가려내는 연구 [KatFishNet](https://arxiv.org/abs/2503.00032)에서 쉼표가 있는 문장의 비율은 사람이 쓴 에세이가 26.3%, LLM 글이 61.0%였습니다.
- 사람이 쓴 기술 블로그 글 600편에서 "버전"은 1,305번 나왔지만 version을 의미하는 "판"은 한 번도 나오지 않았습니다. 스킬 없이 Claude Opus 5.5로 작성한 개발 문서와 대화(한글 81만 자)에는 같은 의미의 "판"이 74번 나왔습니다.

모델은 읽은 문서의 단어를 그대로 따라 씁니다. 이전 버전의 스킬 문서에서 "낱말"을 107번 사용했더니 그 문서를 읽고 작성한 글에도 "낱말"이 29번 나왔습니다. 그래서 0.4.0부터 스킬 문서도 사람이 쓴 글에서 사용하는 단어로 작성합니다. 같은 가상 노트로 작성한 최종 글에서 이런 표현은 0.3.1이 15개, 0.4.0이 0개였습니다. 자료 목록과 측정값은 [`plain-terms.md`](dev/baseline/techblog/plain-terms.md)에 있습니다.

## 한계

검사 스크립트는 형태소 분석기 없이 정규식으로 표현을 세므로 잘못 검출하는 경우가 있습니다. 그래서 기준치도 사람이 쓴 글에 같은 스크립트를 실행해 얻은 값으로 정했습니다. 지금까지 측정한 사람 글은 기술 블로그 글뿐입니다. 그래서 write와 brief는 부정 대구나 번역투처럼 특정 표현의 빈도를 세는 항목에 기술 블로그 글의 기준치를 가져와 사용하고, 문장 길이나 목록 비중처럼 글의 종류에 따라 달라지는 항목은 판정하지 않습니다.

문장 점검은 subagent가 글을 한 문장씩 읽어 문제를 찾는 방식이라 실행할 때마다 찾아내는 문장이 다릅니다. 스킬로 작성한 글에 자료와 다른 내용이 없다는 보장도 없으므로, 글을 공개하기 전에 수치와 고유명사를 자료 원문과 대조해야 합니다.

## 개발

저장소의 구조와 스킬을 추가하는 방법은 [`ARCHITECTURE.md`](ARCHITECTURE.md)에 있습니다. 이 저장소의 README, 참조 문서, 커밋 메시지 같은 한국어 글도 플러그인의 검사와 점검 절차를 거쳐 작성합니다. 작업 규칙은 [`AGENTS.md`](AGENTS.md)에 있습니다.

```bash
python -m unittest discover tests        # 단위 테스트
python dev/sync_core.py --check           # 스킬 폴더의 core 복사본이 원본과 같은지 확인
python dev/borrow_thresholds.py --check   # write와 brief가 가져온 기준치가 techblog의 값과 같은지 확인
claude plugin validate .                  # 플러그인 manifest 검사
claude plugin eval . --allow-tools Write Edit --scaffold   # evals/ 케이스로 스킬이 있을 때와 없을 때를 비교
```

## License

MIT
