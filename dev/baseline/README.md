# 사람 글 baseline

skill마다 기준 글(그 skill의 글이 읽혀야 하는 사람 글) 표본을 하나 두고, 그 표본을 `lint_ko.py`로 측정한 값으로 그 skill의 기준치를 보정한다. 표본의 URL 목록, 측정값, 측정 도구는 `dev/baseline/<skill 이름>/`에 둔다.

| skill | 기준 글 | 폴더 | 보정하는 파일 |
|---|---|---|---|
| techblog | 토스, 카카오, 당근, 네이버 D2, 우아한형제들, NAVER CLOVA 기술 블로그 글 600편(2026-11-02 측정) | [techblog/](techblog/README.md) | `skills/techblog/scripts/thresholds.json` |

## 기준치를 나눠 두는 곳

- `core/scripts/rules.json`: 모든 skill이 쓰는 검사 항목의 정의(종류, 제목, 고치는 방향), Gate와 policy, 고정 기준(fixed)이다. skill마다 같으므로 표본으로 보정하지 않는다.
- `skills/<skill>/scripts/thresholds.json`: 그 skill의 기준 글로 보정한 값이다. gate도 fixed도 아닌 항목의 PASS, WARN 경계(`pass_max`, `warn_max`, `pass_min`, `warn_min`, `rate_per_1k`, `by_tone`)와 사람 글 분포(`human`, `n`, `n_eff`), 보정에서 뺄 사이트(`exclude_sites`)를 담는다. 그 skill에 맞지 않는 항목은 `drop`으로 제외하고, 다르게 판정할 항목은 필드를 덮어쓴다.
- `lint_ko.py`는 두 파일을 합친 값으로 판정한다(`load_thresholds`). 보정값이 없는 분포 지표는 판정하지 않고 값만 보고한다(INFO).

## 새 skill의 표본을 만들 때

1. 기준 글을 정한다. 그 skill의 글이 실릴 곳에서 사람이 쓴 글이고, 어투가 그 skill의 선택지(Default 합니다체, Casual 해요체)와 같은 글이다.
2. `dev/baseline/<skill>/`에 수집 도구와 URL 목록을 둔다. 원문은 저장소에 두지 않고 gitignore된 `docs/` 아래 cache에 둔다. 원문은 신뢰하지 않는 데이터라서 원문을 읽는 Python은 `-I`로 실행한다.
3. 측정값(`stats.json`)으로 `skills/<skill>/scripts/thresholds.json`의 보정값을 계산한다. techblog의 `calibrate.py`(기간 가중치, 사이트 상한, holdout)를 다른 표본에도 쓰도록 일반화하는 일은 두 번째 표본을 만들 때 한다.
4. holdout 사람 글로 통과율을 확인하고 결과를 그 폴더의 README.md에 적는다.

표본이 없는 동안에는 `thresholds.json`에 `skill.standard`(기준 글 이름)만 두고 core의 Gate, policy, 고정 기준으로 검사한다.
