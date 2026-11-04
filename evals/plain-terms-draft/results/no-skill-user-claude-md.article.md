# 사내 sync agent를 Python에서 Rust로 옮기는 과정과 측정 결과

> 이 글의 원본은 글쓰기 평가용으로 작성한 가상의 내부 노트입니다. 글에 나오는 수치와 사례를 실제 결과로 인용하면 안 됩니다.

사내 노트북 약 4,000대에서 동작하는 sync agent를 Python에서 Rust로 옮기고 있습니다. Rust 버전을 노트북 500대에서 2주 동안 측정한 결과, idle 메모리는 210 MB에서 38 MB로, startup time은 1.9초에서 0.3초로 줄었습니다. 반면 약 120대는 보안 도구가 Rust binary를 차단해 아직 Python 버전을 실행하고, network drive에서는 Rust 버전을 테스트하지 않았습니다.

이 글에서는 두 버전을 함께 배포한 방식, 테스트에서 찾은 버그, 측정 결과, 남은 문제를 정리합니다.

## Rust 버전을 만든 이유

Python 버전은 2023년부터 production에서 동작해 왔습니다. idle 상태에서 메모리를 210 MB 사용하고, 시작하는 데 1.9초가 걸렸습니다. 그래서 팀은 3월에 Rust 버전을 만들기 시작했습니다. 마이그레이션이 끝날 때까지 두 버전 모두 같은 팀이 담당합니다.

## 6주 동안 두 버전을 함께 배포한 방식

installer는 6주 동안 Python의 마지막 버전인 1.8과 Rust의 첫 버전인 2.0을 함께 배포했습니다. 두 버전은 같은 설정 파일을 읽습니다. 그래서 노트북을 Rust 버전으로 옮겼다가 Python 버전으로 되돌려도 설정이 사라지지 않습니다.

Rust 버전은 시작할 때 registry에서 설치된 버전 번호를 읽고, 그 버전이 1.6보다 오래되었으면 실행을 거부합니다.

installer는 이전 binary의 사본을 새 binary 옆에 보관합니다. 이전 버전으로 rollback하는 데는 40초가 걸리고, 다운로드는 필요하지 않습니다.

최신 버전은 항상 update server에 게시합니다. patch version은 2.0.3처럼 세 번째 숫자만 바꿉니다.

## 첫 Rust build에서 실패한 테스트 31개

test suite에는 테스트가 1,240개 있고, 첫 Rust build에서는 그중 31개가 실패했습니다. 9개는 Python 버전에서도 실패했으므로 regression이 아닙니다. 나머지 22개는 실제 버그였습니다.

가장 심각한 버그는 file watcher에 있었습니다. 사용자가 폴더 이름을 바꾸면 Rust 버전은 그 뒤로 폴더 안에서 일어나는 변경을 모두 놓쳤습니다. 이 버그는 2.0.3에서 수정했고, 지금은 test suite가 rename path도 검증합니다.

## sync agent의 동작 규칙

sync agent는 다음 규칙으로 동작합니다.

- **Lock**: sync가 실행되는 동안 agent는 database 파일의 lock을 보유합니다.
- **Update checker**: HTTP response header를 읽고 local cache를 갱신한 뒤 최신 버전 문자열을 반환합니다.
- **Worker**: worker 하나가 열 수 있는 파일 수의 hard limit은 8개입니다.
- **Crash 복구**: crash가 발생하면 queue에 남은 entry를 순서대로 replay합니다.

## 설계 문서에서 고친 내용

설계 문서의 첫 초안은 lock의 동작 방식을 잘못 설명했습니다. 그래서 두 번째 버전에서는 그 섹션을 삭제했습니다. reviewer는 문서의 현재 버전을 HEAD commit의 버전과 비교했습니다.

초안에서는 "sync"와 "commit" 같은 단어가 각각 두 가지 의미로 쓰였습니다. 저자들은 단어마다 의미를 하나만 남기고, 모든 용어에 짧은 정의를 붙였습니다. 이 점검은 부록을 제외한 모든 섹션에서 반복했습니다.

## file-watching 라이브러리 비교에 사용한 benchmark

팀은 file-watching 라이브러리를 비교할 때 Lee et al.(2024)의 benchmark를 사용했습니다. benchmark에 포함된 라이브러리 12개 중 Windows junction을 지원하는 라이브러리는 3개입니다. 논문은 watch count와 메모리 사용량의 correlation을 r = 0.91로 보고합니다.

이 논문은 arXiv 버전과 IEEE 출판본의 수식 번호가 서로 다릅니다. 팀의 내부 노트는 IEEE 출판본의 번호를 사용합니다.

## 노트북 500대에서 측정한 결과

Rust 버전을 노트북 500대에서 2주 동안 측정했습니다.

| 항목 | Python 버전 | Rust 버전 |
| --- | --- | --- |
| idle 메모리 | 210 MB | 38 MB |
| startup time | 1.9초 | 0.3초 |
| sync 1회당 로그 | 약 40줄 | 1줄 |

idle 메모리는 172 MB(약 82%), startup time은 1.6초(약 84%) 줄었습니다.

## 남은 문제

- **보안 도구의 차단**: 노트북 약 120대는 보안 도구가 Rust binary를 차단해 아직 Python 버전을 실행합니다.
- **network drive 미검증**: test suite에 network drive 테스트가 없고, network drive에서 직접 테스트한 사람도 없습니다. 그래서 Rust 버전이 network drive에서 Python 버전과 똑같이 동작하는지 아직 알 수 없습니다.
