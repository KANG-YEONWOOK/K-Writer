# K-Writer 0.5.0 write, brief 스킬 추가와 short 모드 삭제 요약

K-Writer 0.5.0은 사용자의 요청에 따라 write와 brief 스킬을 추가했고 techblog의 short 모드를 삭제해 짧은 글은 brief로 쓰기로 했습니다. write는 문체를 미리 정하지 않고 사용자에게 받은 자료나 주제, 목적, 분량, 어투에 맞춰 글을 쓰는 스킬입니다. brief는 사용자가 요약을 요청한 자료나 내용을 한국어로 요약하는 스킬입니다. 변경을 마친 뒤 `python -m unittest discover -s tests`로 실행한 단위 테스트 210개가 통과했습니다. `dev/sync_core.py --check`, `dev/borrow_thresholds.py --check`, `claude plugin validate .` 검사도 통과했습니다. 다만 `claude plugin eval`과 dogfood는 실행하지 않았고 write와 brief로 쓴 글을 스킬 없이 쓴 글이나 사람이 쓴 글과 비교한 결과도 없습니다.

write는 자료나 주제가 없으면 대화에서 먼저 요청하고 목적(설명, 설득, 안내, 기록, 직접 입력), 분량, 어투 중 요청에 없는 값을 한 번에 묻습니다. write는 본문이 공백 제외 1,500자 이상이면 독립 점검 네 가지를 모두 subagent에게 맡기고 1,500자 미만이면 독자 점검과 한국어 문장 점검만 맡깁니다. brief는 분량(한 줄, 한 문단, 자세히)과 어투만 묻고 요약으로 답하며 `-o`가 있으면 그 경로의 파일에도 요약을 저장합니다.

core의 어투에는 해라체(Plain)와 사용자가 직접 정한 어투를 추가했고 `lint_ko.py --tone`과 `tone_check.py --tone`은 `plain`과 `free` 값을 받습니다. 어느 어투로 쓰는 글이든 합니다체 초안의 종결부만 바꿔서 만듭니다. write와 brief에는 기준 글 표본이 없고 표본이 없으면 부정 대구나 번역투도 판정할 수 없습니다. 그래서 특정 표현의 빈도를 세는 항목 15개의 기준치를 techblog에서 가져왔고 문장 길이, 문단, 목록 비중 같은 분포 항목은 가져오지 않았습니다.

techblog의 short 모드와 함께 short 인자와 `short.md`, `thresholds.json`의 short 설정을 삭제했습니다. lint의 `--source`와 `--terms`, 원문 대조 항목 F1~F8과 테스트 파일 `tests/test_short_mode.py`도 함께 삭제했습니다. 예시 글, eval 글, 평가 기록의 글 34개 파일에 lint를 `--tone default`와 `--tone casual`로 실행한 출력 68개는 short 모드 코드를 삭제하기 전의 출력과 비교했습니다. 이 출력에서 달라진 부분은 문구를 바꾼 G4.off_tone의 수정 방향 한 줄뿐이었고 항목의 값과 판정은 모두 같았습니다. 감사를 맡은 subagent는 `revise_ko.py`의 `check`와 `audit`가 core의 `rules.json`에 둔 짧은 글 기준을 적용하지 않아서 `lint_ko.py --short`와 판정이 다르다는 것을 찾았습니다. 그래서 `check`와 `audit`에도 짧은 글 기준을 적용하는 `--short`를 추가했습니다.

테스트 실행에서는 스킬 문서를 작성하지 않은 subagent에게 스킬 문서만 주고 사용자 요청을 실행하게 했고 1차 실행 뒤 문서를 수정해 2차 실행을 했습니다. 영어 엔지니어링 노트를 한 문단으로 요약한 brief의 요약은 1차 실행의 590자에서 2차 실행의 296자로 줄었습니다. 1차 실행의 요약이 길어진 원인 하나는 brief의 기본 독자를 techblog처럼 "자료 분야의 지식이 없을 수 있는 사람"으로 정해서 용어마다 설명이 붙은 것이었습니다. 그래서 brief의 기본 독자를 "자료가 대상으로 삼은 독자와 같은 수준의 사람"으로 바꿨습니다. 다른 원인은 독립 점검 단계에서 독자 점검이 낸 질문마다 요약에 설명을 추가한 것이었습니다. brief의 독립 점검은 요약만 읽는 subagent가 읽다가 멈춘 부분을 보고하고 상위 agent가 분량 안에서 수정하는 방식으로 바꿨습니다.

write 2차 실행의 글에서는 어투 변환이 합니다체 초안의 종결부만 바꾸기 때문에 "저희"와 해라체가 함께 쓰인 문장이 6개 나왔습니다. 조직을 주어로 쓸 때는 "저희" 대신 "우리 팀은"이나 조직의 이름을 쓰도록 genre.md, drafting.md, tone.md를 수정했습니다. 다만 테스트 실행은 설정마다 한 번이었고 2차 실행 뒤에 수정한 이 "저희" 규칙과 사실 표의 열, brief의 출력 파일 조립은 다시 실행해 확인하지 않았습니다. 테스트 실행은 subagent 안에서 했고 AskUserQuestion으로 설정을 묻는 흐름과 대화에서 자료나 주제를 요청하는 흐름은 실행해 보지 못했습니다.

자료: K-Writer 0.5.0 write, brief 스킬 추가와 short 모드 삭제 (2026-11-10), source.md
