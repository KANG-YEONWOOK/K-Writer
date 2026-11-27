# sync_core.py

`sync_core.py`는 `core/` 폴더에 있는 공통 문서와 검사 스크립트를 `skills/` 아래의 모든 스킬 폴더에 복사하는 스크립트입니다. 공통 파일의 원본은 `core/`에 하나만 두고 스킬 폴더에는 그 원본의 복사본을 둡니다. 스크립트는 복사본을 원본으로 덮어쓰므로 공통 파일은 **`core/`에서 수정한 뒤 이 스크립트로 복사**합니다.

## 복사하는 파일과 위치

`core/references/`의 파일은 `skills/<스킬 이름>/references/`에, `core/scripts/`의 파일은 `skills/<스킬 이름>/scripts/`에 같은 이름으로 복사합니다. 스킬 폴더는 `skills/` 아래에서 `SKILL.md`가 있는 폴더이고 `SKILL.md`가 없는 폴더에는 복사하지 않습니다. 스킬 폴더에 `references/`나 `scripts/` 폴더가 없으면 스크립트가 그 폴더를 만듭니다. 스킬 폴더가 `skills/write/` 하나인 저장소에서는 원본과 복사본이 다음 위치에 놓입니다.

```
<저장소 루트>/
├── dev/
│   └── sync_core.py
├── core/
│   ├── references/
│   │   └── style-guide.md      ← 원본
│   └── scripts/
│       └── check_ko.py         ← 원본
└── skills/
    └── write/
        ├── SKILL.md
        ├── references/
        │   └── style-guide.md  ← 복사본
        └── scripts/
            └── check_ko.py     ← 복사본
```

스크립트는 `core/references/`와 `core/scripts/` 바로 아래에 있는 파일만 복사하고 두 폴더 안의 하위 폴더와 확장자가 `.pyc`, `.pyo`인 파일은 복사하지 않습니다.

## 실행 환경

스크립트는 Python 3.8 이상에서 동작하고 표준 라이브러리만 사용하므로 따로 설치할 패키지가 없습니다. 스크립트는 자기가 있는 폴더의 상위 폴더를 저장소 루트로 사용하므로 저장소 루트 바로 아래의 `dev/` 폴더에 있어야 합니다. 저장소 루트를 스크립트 위치로 정하기 때문에 어느 폴더에서 실행해도 같은 `core/`와 `skills/`를 사용하고 출력하는 경로는 저장소 루트에서 시작하는 상대 경로입니다. 저장소 루트에 `core/references/`, `core/scripts/`, `skills/` 폴더 중 하나라도 없으면 스크립트는 `sync_core 오류:`로 시작하는 메시지를 출력하고 종료 코드 2로 끝납니다.

이 문서에 쓴 `sync_core.py` 명령은 저장소 루트에서 실행하는 기준입니다. `python` 명령이 Python 3을 실행하지 않는 환경에서는 `python3`을 사용합니다.

## 기본 사용 순서

1. `core/references/`나 `core/scripts/`의 파일을 수정하거나 새 파일을 추가합니다.
2. `python dev/sync_core.py`를 실행합니다. 스크립트는 원본과 내용이 다르거나 없는 복사본만 쓰고 쓴 파일마다 경로를 `복사:` 줄로 출력합니다.
3. `python dev/sync_core.py --check`를 실행해 모든 복사본이 원본과 같은지 확인합니다.

스킬 폴더 2개(`write`, `techblog`)와 core 파일 2개가 있는 저장소에서 `core/references/style-guide.md`를 수정한 뒤 두 명령을 실행하면 다음과 같이 출력합니다.

```
$ python dev/sync_core.py
복사: skills/techblog/references/style-guide.md
복사: skills/write/references/style-guide.md
복사한 파일 2개
$ python dev/sync_core.py --check
복사본 확인: 스킬 2개, core 파일 2개 모두 같음
```

모든 복사본이 이미 원본과 같으면 스크립트는 파일을 쓰지 않고 `복사한 파일 0개`를 출력합니다.

## 명령과 옵션

| 명령 | 하는 일 |
| --- | --- |
| `python dev/sync_core.py` | core 파일을 모든 스킬 폴더에 복사합니다. |
| `python dev/sync_core.py --check` | 파일을 쓰지 않고 모든 스킬 폴더의 복사본이 원본과 바이트 단위로 같은지 확인합니다. |
| `python dev/sync_core.py --skill techblog` | core 파일을 `skills/techblog/`에만 복사합니다. |
| `python dev/sync_core.py --skill techblog --check` | `skills/techblog/`의 복사본만 확인합니다. |
| `python dev/sync_core.py --remove NAME` | core에서 삭제한 파일 `NAME`의 복사본을 모든 스킬 폴더에서 삭제합니다. |

`--skill`에는 `skills/` 아래의 폴더 이름을 지정합니다. 지정한 폴더에 `SKILL.md`가 없으면 스크립트는 `스킬이 없다: <이름>`을 출력하고 파일을 쓰지 않은 채 종료 코드 2로 끝납니다.

## --check 결과 읽기

`--check`는 원본과 다른 복사본을 `다름:`, 스킬 폴더에 없는 복사본을 `없음:`으로 시작하는 줄로 출력하고 종료 코드 1로 끝납니다. 다음은 `skills/write/references/style-guide.md`를 직접 수정한 뒤 `--check`를 실행한 결과입니다.

```
$ python dev/sync_core.py --check
다름: skills/write/references/style-guide.md
core를 수정했으면 python dev/sync_core.py로 다시 복사한다. 복사본을 수정했으면 수정 내용을 core로 옮긴다.
```

`다름`이 나온 복사본은 원인에 따라 다르게 처리합니다. core 원본을 수정하고 복사하지 않았다면 `python dev/sync_core.py`를 실행합니다. 복사본을 직접 수정했다면 그 수정 내용을 core 원본으로 옮긴 뒤 `python dev/sync_core.py`를 실행합니다. 복사본의 수정 내용을 옮기지 않고 복사하면 그 복사본은 원본으로 덮어써지고 수정 내용은 사라집니다. `없음`은 core에 파일을 추가했거나 새 스킬 폴더를 만들고 아직 복사하지 않았을 때 나오므로 `python dev/sync_core.py`를 실행해 복사합니다.

`--check`는 core에 있는 파일의 복사본만 확인하므로 core에서 삭제한 파일의 복사본이 스킬 폴더에 남아 있어도 찾지 못합니다. 이 복사본은 아래 "삭제한 파일의 복사본 정리"에서 설명하는 `--remove`로 삭제합니다.

## core에 둘 수 없는 파일 이름

`SKILL.md`, `settings.md`, `genre.md`, `rubric.md`, `thresholds.json`은 스킬마다 따로 가지는 스킬 전용 파일입니다. 이 이름의 파일을 core에 두면 복사할 때 스킬의 파일을 덮어쓰게 되므로 스크립트는 core에서 이 이름을 허용하지 않습니다. core에서 이 이름의 파일을 찾으면 스크립트는 복사, 확인, 삭제를 모두 하지 않고 겹치는 이름을 출력한 뒤 종료 코드 2로 끝납니다.

```
$ python dev/sync_core.py
sync_core 오류: core에 스킬 파일과 이름이 같은 파일이 있다: rubric.md
```

이 오류가 나오면 core에서 그 파일의 이름을 바꾸거나 파일을 다른 곳으로 옮깁니다.

## 삭제한 파일의 복사본 정리

복사 명령은 스킬 폴더의 파일을 삭제하지 않으므로 core에서 파일을 삭제하거나 이름을 바꾸면 이전 이름의 복사본이 모든 스킬 폴더에 남습니다. 이 복사본은 `--remove`에 이전 파일 이름을 지정해 삭제합니다. `core/scripts/check_ko.py`의 이름을 `check.py`로 바꿨다면 다음 순서로 실행합니다.

1. `python dev/sync_core.py`를 실행해 `check.py`의 복사본을 만듭니다.
2. `python dev/sync_core.py --remove check_ko.py`를 실행해 이전 복사본을 삭제합니다. 스크립트는 삭제한 파일마다 경로를 `삭제:` 줄로 출력합니다.

```
$ python dev/sync_core.py --remove check_ko.py
삭제: skills/techblog/scripts/check_ko.py
삭제: skills/write/scripts/check_ko.py
```

`--remove`는 모든 스킬 폴더의 `references/`와 `scripts/`에서 지정한 이름의 파일을 삭제하고 그 파일을 스킬이 직접 만들었는지는 구분하지 않습니다. `--skill`이나 `--check`를 함께 지정해도 `--remove`는 두 옵션을 무시하고 모든 스킬 폴더에서 삭제합니다. 지정한 이름의 파일이 없으면 스크립트는 아무것도 출력하지 않고 종료 코드 0으로 끝납니다.

`--remove`는 다음 두 경우에 파일을 삭제하지 않고 종료 코드 2로 끝납니다.

- core에 아직 있는 파일 이름을 지정하면 스크립트는 `core에 아직 있는 파일이다`를 출력합니다. core에서 먼저 파일을 삭제한 뒤 다시 실행합니다.
- `scripts/check_ko.py`처럼 경로가 들어간 이름이나 스킬 전용 파일 이름을 지정하면 스크립트는 `삭제할 수 없는 이름`을 출력합니다. 폴더 없이 파일 이름만 지정합니다.

## 종료 코드와 오류 메시지

| 종료 코드 | 나오는 경우 |
| --- | --- |
| 0 | 복사, 확인, 삭제가 정상적으로 끝났습니다. `--check`에서는 모든 복사본이 원본과 같다는 뜻입니다. |
| 1 | `--check`가 원본과 다르거나 없는 복사본을 찾았습니다. |
| 2 | 잘못된 옵션, 없는 스킬 이름, core에 있는 스킬 전용 파일 이름, `--remove`에 쓸 수 없는 이름, 폴더나 파일을 읽거나 쓰지 못한 오류 중 하나가 있었습니다. |

종료 코드 2로 끝날 때 스크립트는 잘못된 옵션에는 사용법을, 없는 스킬에는 `스킬이 없다: <이름>`을, 그 밖의 오류에는 `sync_core 오류:`로 시작하는 메시지를 표준 오류로 출력합니다.
