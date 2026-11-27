# sync_core.py

`core/`에 있는 공유 문서와 검사 스크립트를 `skills/` 아래 모든 스킬 폴더에 복사하고, 복사본이 원본과 같은지 확인하는 스크립트다.

공유 파일의 원본은 `core/` 한 곳에만 있다. 스킬 폴더에 있는 같은 이름의 파일은 모두 복사본이다. 공유 파일을 고칠 때는 복사본이 아니라 `core/`의 원본을 고치고, 이 스크립트로 다시 복사한다.

## 폴더 구조

스크립트는 자기 위치로 프로젝트 루트를 찾는다. `sync_core.py`가 들어 있는 폴더(`dev/`)의 상위 폴더가 프로젝트 루트다. 그래서 어느 폴더에서 실행해도 같은 프로젝트를 대상으로 동작한다.

```
<프로젝트 루트>/
├── dev/
│   └── sync_core.py
├── core/
│   ├── references/       # 모든 스킬이 함께 쓰는 문서 (원본)
│   └── scripts/          # 모든 스킬이 함께 쓰는 검사 스크립트 (원본)
└── skills/
    ├── techblog/
    │   ├── SKILL.md      # 이 파일이 있어야 스킬 폴더로 인식된다
    │   ├── references/   # core/references/의 복사본 + 스킬 고유 파일
    │   └── scripts/      # core/scripts/의 복사본 + 스킬 고유 파일
    └── ...
```

- 복사 대상은 `core/references/`와 `core/scripts/` 바로 아래에 있는 파일이다. 같은 이름으로 `skills/<스킬>/references/`와 `skills/<스킬>/scripts/`에 복사된다.
- `skills/` 아래에서 `SKILL.md`가 있는 폴더만 스킬로 인식한다. `SKILL.md`가 없는 폴더는 건너뛴다.
- `core/references/`, `core/scripts/`, `skills/`는 비어 있어도 폴더가 있어야 한다. 하나라도 없으면 오류로 끝난다.

## 빠른 시작

프로젝트 루트에서 실행한다.

```bash
# 1. 현재 상태 확인 (파일을 바꾸지 않는다)
python dev/sync_core.py --check

# 2. 모든 스킬에 복사
python dev/sync_core.py

# 3. 다시 확인
python dev/sync_core.py --check
```

## 명령

| 명령 | 하는 일 |
|---|---|
| `python dev/sync_core.py` | core 파일을 모든 스킬에 복사한다. 내용이 이미 같은 파일은 건너뛰고, 없는 파일은 새로 만들고, 다른 파일은 덮어쓴다. 스킬에 `references/`나 `scripts/` 폴더가 없으면 만든다. |
| `python dev/sync_core.py --check` | 파일을 바꾸지 않고 복사본이 원본과 바이트 단위로 같은지만 확인한다. |
| `python dev/sync_core.py --skill techblog` | `skills/techblog` 한 곳에만 복사한다. `--check`와 함께 쓰면 그 스킬만 확인한다. |
| `python dev/sync_core.py --remove NAME` | core에서 지운 파일 `NAME`의 복사본을 모든 스킬에서 지운다. |

### 출력 예시

복사할 때는 바뀐 파일만 출력한다. 모두 최신이면 `복사한 파일 0개`만 나온다.

```
복사: skills/novel/references/style.md
복사: skills/novel/scripts/lint.py
복사한 파일 2개
```

확인했을 때 모두 같으면:

```
복사본 확인: 스킬 2개, core 파일 3개 모두 같음
```

문제가 있으면:

```
없음: skills/novel/scripts/lint.py
다름: skills/novel/references/style.md
core를 수정했으면 python dev/sync_core.py로 다시 복사한다. 복사본을 수정했으면 수정 내용을 core로 옮긴다.
```

- `없음`: 스킬 폴더에 복사본이 없다.
- `다름`: 복사본 내용이 원본과 다르다.

## 종료 코드

| 코드 | 뜻 |
|---|---|
| 0 | 정상 (`--help` 포함) |
| 1 | `--check`가 `없음` 또는 `다름`인 복사본을 찾았다 |
| 2 | 사용법 또는 입력 오류. 알 수 없는 옵션, 없는 스킬 이름, 필요한 폴더 없음, core에 스킬 전용 이름의 파일이 있음, `--remove`로 지울 수 없는 이름 등 |

`--check`는 문제가 있으면 1로 끝나므로 커밋 전 확인이나 CI 검사에 쓸 수 있다.

## 자주 하는 작업

### 공유 파일을 고치거나 추가할 때

1. `core/references/` 또는 `core/scripts/`에서 원본을 고치거나 새 파일을 넣는다.
2. `python dev/sync_core.py`로 복사한다.
3. `python dev/sync_core.py --check`로 확인한다.

### 새 스킬을 추가할 때

1. `skills/<새 스킬>/SKILL.md`를 만든다.
2. `python dev/sync_core.py --skill <새 스킬>`을 실행한다. 전체 복사를 해도 된다. `references/`와 `scripts/` 폴더는 스크립트가 만든다.

### 공유 파일을 지우거나 이름을 바꿀 때

`--check`는 core에 없는 파일의 복사본이 스킬에 남아 있어도 찾지 못한다. 남은 복사본은 직접 지워야 한다.

1. core에서 파일을 지우거나 이름을 바꾼다.
2. 이름을 바꿨으면 `python dev/sync_core.py`로 새 이름의 복사본을 만든다.
3. `python dev/sync_core.py --remove <옛 이름>`으로 옛 복사본을 지운다.

### 복사본을 실수로 고쳤을 때

`--check`가 그 파일을 `다름`으로 보고한다. 이 상태에서 복사하면 복사본에서 고친 내용은 덮어써져 사라진다. 고친 내용을 살리려면 먼저 core 원본에 옮긴 다음 복사한다.

```bash
# 예: novel 스킬의 복사본에서 고친 내용을 그대로 원본으로 삼을 때
cp skills/novel/references/style.md core/references/style.md
python dev/sync_core.py
```

## 주의할 점

- **복사본은 묻지 않고 덮어쓴다.** 스킬의 `references/`나 `scripts/`에 core 파일과 같은 이름의 스킬 고유 파일을 두면 복사할 때 덮어써진다. 스킬 고유 파일에는 core에 없는 이름을 쓴다.
- **스킬 전용 파일 이름은 core에 둘 수 없다.** `SKILL.md`, `settings.md`, `genre.md`, `rubric.md`, `thresholds.json`은 각 스킬이 직접 관리하는 파일이다. `core/references/`나 `core/scripts/`에 이 이름의 파일이 있으면 복사, `--check`, `--remove`가 모두 오류(종료 코드 2)로 끝난다.
- **`--remove`는 항상 모든 스킬에 적용된다.** `--skill`과 함께 써도 범위가 좁혀지지 않는다. `--check`와 함께 쓰면 `--remove`만 실행된다.
- **`--remove`는 복사본과 스킬 고유 파일을 구분하지 않는다.** 모든 스킬의 `references/`와 `scripts/`에서 그 이름의 파일을 모두 지운다. 실행하기 전에 지워질 파일을 확인한다.
  ```bash
  ls skills/*/references/NAME skills/*/scripts/NAME
  ```
- **`--remove`에는 파일 이름만 줄 수 있다.** `sub/a.md` 같은 경로, core에 아직 있는 파일 이름, 스킬 전용 파일 이름은 거부된다. 지울 파일이 하나도 없으면 아무것도 출력하지 않고 0으로 끝난다.
- **숨김 파일도 복사된다.** `.pyc`와 `.pyo`만 빼고 `.DS_Store` 같은 숨김 파일까지 모두 복사된다. core 폴더에 불필요한 파일이 없게 관리한다.
- **하위 폴더는 복사하지 않는다.** `core/references/`와 `core/scripts/` 바로 아래에 있는 파일만 대상이다.
- **파일 내용만 복사한다.** 실행 권한 같은 파일 속성은 복사되지 않는다. 복사된 스크립트는 실행 권한에 기대지 말고 `python`으로 실행한다.
- **줄바꿈 문자만 달라도 `다름`이다.** 바이트 단위로 비교하므로 Git의 줄바꿈 자동 변환(`core.autocrlf`) 등으로 CRLF와 LF만 달라져도 `다름`으로 나온다.

## 요구 사항

- Python 3.8 이상. 표준 라이브러리만 쓰므로 따로 설치할 패키지가 없다.
- `python` 명령이 Python 3를 가리키지 않으면 `python3`로 실행한다.
