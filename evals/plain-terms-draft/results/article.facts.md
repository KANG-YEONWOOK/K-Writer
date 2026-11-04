# fact sheet

핵심 주제: 동기화 에이전트를 Python에서 Rust로 옮기면서 두 버전을 함께 배포하고 되돌릴 수 있게 한 방법과, 노트북 500대에서 측정한 결과 및 아직 확인하지 않은 범위를 알게 된다.

독자: 소프트웨어 개발 지식이 충분하지 않거나 없을 수 있는 사람(기본값)

분량: 자료 크기에 맞춤(기본값). 자료가 짧은 노트 한 편이고 용어 설명이 필요하므로 공백 제외 3,000~5,000자를 계획 참고치로 삼는다. 상한으로 적용하지 않는다.

어투: Default(합니다체), 요청 인자 `default`

## 중심 대상

- 동기화 에이전트(sync agent): 노트북에 설치돼 파일 변경을 감지하고 동기화를 실행하는 프로그램. 회사 노트북 약 4,000대에서 실행된다. 정의 위치: 도입 첫 문단. 파일 변경 감지는 자료의 file watcher 설명에서 가져왔고, 에이전트와 동기화의 의미는 일반 지식이다. 동기화 대상과 목적지는 자료에 없다.
- Python 버전과 Rust 버전: 각 언어로 작성한 동기화 에이전트. 1.8 버전이 Python으로 작성한 마지막 버전이고 2.0 버전이 Rust로 작성한 첫 버전이다. 정의 위치: 도입 둘째 문단(언어 구분), 첫 절(버전 번호).

## 자료 정보

- 제목: Internal note: moving the sync agent from Python to Rust
- 저자나 기관: 자료에 없음(팀 내부 노트)
- 연도: 자료에 없음. "in March"에도 연도가 없으므로 연도를 붙이지 않는다.
- URL: 없음. 로컬 파일 input.md
- 자료의 성격: "This note is fictional material written for a writing evaluation. Do not cite it as a real result." 글의 도입과 참고자료에 가상 자료임을 밝힌다.

## 문제와 배경

- Python 버전은 유휴 상태에서 메모리를 210 MB 사용했고 시작하는 데 1.9초가 걸렸다. 그래서 담당 팀은 3월에 Rust 버전을 만들기 시작했다.
- 자료에 기존 방법의 다른 한계는 없다.

## 방법

- 설치 프로그램은 6주 동안 두 버전을 함께 배포했다.
- 두 버전은 같은 설정 파일을 읽어서 노트북이 설정을 잃지 않고 Rust 버전으로 옮겨 갔다가 돌아올 수 있었다.
- Rust 버전은 시작할 때 레지스트리에서 설치된 버전 번호를 읽고, 그 버전이 1.6보다 오래됐으면 실행을 거부한다.
- 설치 프로그램은 이전 바이너리의 복사본을 새 바이너리 옆에 남겨 둔다.
- 최신 버전은 항상 업데이트 서버에 공개되고, 패치 버전은 세 번째 숫자만 바꾼다.

## 수치

| 측정 대상 | 값 | 조건과 비교 대상 | 원문 표현 | 위치 |
|---|---|---|---|---|
| 동기화 에이전트가 실행되는 회사 노트북 수 | 약 4,000대 | 전체 규모 | runs on about 4,000 company laptops | Why we built |
| Python 버전의 운영 시작 연도 | 2023년 | - | in production since 2023 | Why we built |
| Python 버전의 유휴 상태 메모리 사용량 | 210 MB | Rust 버전 38 MB와 비교. 측정 노트북과 기간은 자료에 없음 | used 210 MB of memory at idle | Why we built, Results |
| Python 버전의 시작 시간 | 1.9초 | Rust 버전 0.3초와 비교 | took 1.9 seconds to start | Why we built, Results |
| Rust 버전 개발 시작 시점 | 3월 | 연도 표기 없음 | in March | Why we built |
| 두 버전을 함께 배포한 기간 | 6주 | 설치 프로그램 기준 | For six weeks the installer shipped both versions | Two versions |
| 마지막 Python 버전의 번호 | 1.8 | - | Version 1.8 was the last Python version | Two versions |
| 첫 Rust 버전의 번호 | 2.0 | - | version 2.0 was the first Rust version | Two versions |
| Rust 버전이 실행을 거부하는 기준 버전 | 1.6 | 설치된 버전이 이보다 오래됐을 때 | refuses to run if that version is older than 1.6 | Two versions |
| 이전 버전으로 되돌리는 시간 | 40초 | 다운로드 없음 | takes 40 seconds and needs no download | Two versions |
| 패치 버전의 예, 파일 감시 버그를 수정한 버전 | 2.0.3 | 세 번째 숫자만 바뀜 | for example 2.0.3, The fix shipped in version 2.0.3 | Two versions, Bugs |
| 테스트 스위트의 테스트 수 | 1,240개 | - | has 1,240 tests | Bugs |
| 첫 Rust 빌드에서 실패한 테스트 수 | 31개 | 1,240개 중 | On the first Rust build 31 tests failed | Bugs |
| 31개 중 Python 버전에서도 실패한 테스트 수 | 9개 | 회귀 버그가 아님 | Nine of those also failed on the old version, so they were not regressions | Bugs |
| 31개 중 실제 버그 수 | 22개 | 나머지 | The other 22 were real bugs | Bugs |
| worker마다 동시에 열 수 있는 파일 상한 | 8개 | 넘을 수 없는 상한 | hard limit of 8 open files | Bugs |
| 인용한 논문의 연도 | 2024년 | Lee et al. | Lee et al. (2024) | What the paper said |
| 벤치마크의 라이브러리 수 | 12개 | - | Among the 12 libraries | What the paper said |
| Windows junction을 지원하는 라이브러리 수 | 3개 | 12개 중 | three support Windows junctions | What the paper said |
| watch count와 메모리 사용량 사이 관계의 강도 | r = 0.91 | Lee et al.(2024)이 보고한 값. 동기화 에이전트의 측정값이 아님 | reports the strength of the link ... as r = 0.91 | What the paper said |
| Rust 버전을 측정한 노트북 수 | 500대 | 2주 동안 | on 500 laptops for two weeks | Results |
| Rust 버전을 측정한 기간 | 2주 | 500대 | for two weeks | Results |
| Rust 버전의 유휴 상태 메모리 사용량 | 38 MB | 노트북 500대, 2주. Python 버전 210 MB와 비교 | fell from 210 MB to 38 MB | Results |
| Rust 버전의 시작 시간 | 0.3초 | 노트북 500대, 2주. Python 버전 1.9초와 비교 | fell from 1.9 seconds to 0.3 seconds | Results |
| Rust 바이너리가 동기화 1회당 출력하는 로그 | 1줄 | Python 버전 약 40줄과 비교 | emits one log line per sync, down from about 40 | Results |
| Python 버전이 동기화 1회당 출력한 로그 | 약 40줄 | - | about 40 in the old version | Results |
| 아직 Python 버전을 실행하는 노트북 수 | 약 120대 | 보안 도구가 Rust 바이너리를 차단 | About 120 laptops still run the old version | Results |

### 계산한 값

| 값 | 계산 | 글에 쓸 표현 |
|---|---|---|
| 22 / 1,240 = 1.77% | 실제 버그로 분류한 테스트의 비율 | 약 1.8% |
| 38 / 210 = 18.1% | Python 버전 대비 Rust 버전의 유휴 상태 메모리 사용량 | Python 버전의 약 18% |
| 0.3 / 1.9 = 15.8% | Python 버전 대비 Rust 버전의 시작 시간 | Python 버전의 약 16% |
| 500 / 4,000 = 12.5% | 측정한 노트북의 비율(전체 수가 어림값) | 12.5% 정도 |
| 120 / 4,000 = 3% | Python 버전이 남은 노트북의 비율(둘 다 어림값) | 3% 정도 |

## 의미

- 동기화 에이전트를 맡은 팀은 마이그레이션이 끝날 때까지 Python 버전과 Rust 버전을 모두 담당한다. (원문: The team owns both versions until the migration ends.)
- 설치 프로그램은 6주 동안 두 버전을 함께 배포했다. (원문: the installer shipped both versions)
- 노트북은 설정을 잃지 않고 Rust 버전으로 옮겨 갔다가 Python 버전으로 돌아올 수 있었다. (원문: could move to the new version and back without losing settings)
- 이전 버전으로 되돌리는 데 40초가 걸리고 다운로드는 필요하지 않다. (원문: rolling back to the previous version takes 40 seconds and needs no download)
- 실패한 테스트 9개는 Python 버전에서도 실패했으므로 회귀 버그가 아니었다. 나머지 22개는 Python 버전에서는 실패하지 않았고 실제 버그였다. (원문: Nine of those also failed on the old version, so they were not regressions. The other 22 were real bugs. "실패하지 않았고"는 "also failed"가 9개에만 해당한다는 데서 끌어낸 내용이다)
- 가장 심각한 버그는 file watcher에서 발생했다. 사용자가 폴더 이름을 바꾸면 Rust 버전은 그 뒤 폴더 안에서 생긴 변경을 하나도 감지하지 못했다. (원문: missed every later change inside it)
- 이 버그는 2.0.3 버전에서 수정됐고 지금은 테스트 스위트가 폴더 이름을 바꾸는 경로를 커버한다. 테스트 스위트는 아직 네트워크 드라이브를 커버하지 않는다. (원문: The fix shipped in version 2.0.3 ... now covers the rename path ... still do not cover network drives)
- 동기화가 실행되는 동안 동기화 에이전트는 데이터베이스 파일의 락을 보유한다. (원문: holds a lock on the database file)
- update checker는 HTTP 응답 헤더를 읽고 로컬 캐시를 갱신한 뒤 최신 버전 문자열을 반환한다. (원문: reads the HTTP response header, updates the local cache, and returns the latest version string)
- worker마다 동시에 열어 둘 수 있는 파일은 최대 8개이고 이 상한은 넘을 수 없다. (원문: hard limit of 8 open files)
- 크래시 뒤에는 큐에 남은 항목이 순서대로 다시 처리된다. 무엇의 크래시인지, 항목을 무엇이 처리하는지, 전에 처리된 항목인지는 자료에 없다. (원문: the remaining entries in the queue are replayed in order)
- 설계 문서의 첫 초안은 락의 동작 방식을 잘못 설명했고, 그래서 문서의 두 번째 버전에서는 그 절을 삭제했다. 고쳐 쓴 것이 아니라 삭제했다. (원문: was wrong about how the lock works, so the second version removed that section)
- 리뷰어들은 문서의 현재 버전을 HEAD 커밋에 있는 버전과 비교했다. (원문: compared the current version of the document with the version in the HEAD commit)
- 초안에서 "sync"와 "commit" 같은 단어는 두 가지 의미로 사용됐다. 그래서 문서 작성자들은 단어마다 의미를 하나만 남기고 모든 용어에 짧은 정의를 붙였다. 이 점검은 절마다 반복했고 부록은 제외했다. 두 가지 의미가 무엇인지는 자료에 없다.
- 담당 팀은 파일 감시 라이브러리를 비교하려고 Lee et al.(2024)의 벤치마크를 사용했다.
- 논문의 arXiv 버전과 출판된 IEEE 버전은 수식 번호가 서로 달라서 이 노트는 출판된 버전의 번호를 사용한다.
- 약 120대의 노트북은 보안 도구가 Rust 바이너리를 차단해서 아직 Python 버전을 실행한다. (원문: a security tool blocks the new binary)

## 추정 표현

자료에 추정 단어(likely, may, suggest)는 없다. "about"은 "약"으로 쓴다. 글쓴이의 추론은 "~라면", "~수 있습니다"로 쓴다.

## 한계

- 담당 팀은 Rust 버전이 네트워크 드라이브에서도 같게 동작하는지 아직 모른다. 네트워크 드라이브에서 Rust 버전을 테스트한 사람이 아직 없다. (원문: We do not know yet whether the new version behaves the same on network drives, because nobody has tested it there.)
- 테스트 스위트는 아직 네트워크 드라이브를 커버하지 않는다.
- 측정 범위는 노트북 500대, 2주다.
- 약 120대는 아직 Python 버전을 실행한다.
- 자료에 없는 것(마치며에만 쓴다): Python 버전의 값을 같은 노트북 500대에서 측정했는지, Rust 버전의 38 MB와 0.3초가 500대의 평균인지 다른 값인지, 500대를 어떤 기준으로 선택했는지, 메모리 사용량과 시작 시간이 줄어든 원인, 실제 버그 22개가 모두 수정됐는지, 벤치마크에서 어떤 라이브러리를 선택했는지, 파일을 어디로 동기화하는지, 약 120대를 제외한 노트북이 모두 Rust 버전으로 전환했는지, 락, update checker, worker, 큐의 동작이 Python 버전과 Rust 버전 중 어느 쪽의 것인지. input.md 전체와 대조했다.

## 용어

| 원어 | 글에 쓸 표기 | 근거 | 쓰지 않을 표기 | 처음 나올 때 설명(근거) |
|---|---|---|---|---|
| sync agent | 동기화 에이전트(sync agent) | 동기화, 에이전트 모두 한국어 개발 문서에서 정착한 용어 | 싱크 에이전트 | 노트북에 설치돼 파일 변경을 감지하고 동기화를 실행하는 프로그램(자료의 file watcher 설명과 일반 지식) |
| sync | 동기화 | 한국어 개발 문서에서 정착한 용어. 설계 문서 초안의 단어를 가리킬 때만 따옴표로 "sync" | 싱크 | 여러 곳에 있는 데이터를 같은 상태로 맞추는 일(일반 지식, 소프트웨어 일반 용어, 웹 확인 안 함) |
| Python | Python | 제품명 원래 표기 | 파이썬 | 프로그램을 작성하는 언어(일반 지식: Python Tutorial, Whetting Your Appetite) |
| Rust | Rust | 제품명 원래 표기 | 러스트 | 프로그램을 작성하는 언어(일반 지식: The Rust Programming Language, Hello, World!) |
| source code | 소스 코드 | 한국어 개발 문서에서 정착한 용어 | 원시 코드 | 프로그램을 작성하는 언어로 사람이 읽을 수 있게 작성한 프로그램의 원본(일반 지식: Wikipedia, Source code) |
| code | 코드 | 한국어 개발 문서에서 정착한 용어 | - | 소스 코드를 줄인 말(일반 지식: Wikipedia, Source code, "source code, or simply code") |
| memory | 메모리 | 한국어 개발 문서에서 정착한 용어 | 기억 장치 | 컴퓨터가 실행 중인 프로그램과 그 데이터를 바로 사용할 수 있게 올려 두는 저장 공간(일반 지식: Wikipedia, Computer memory) |
| MB | MB(메가바이트) | 단위 기호 | - | 데이터의 크기를 나타내는 단위(일반 지식: Wikipedia, Megabyte) |
| deployment | 배포 | 한국어 개발 문서에서 정착한 용어 | 전개 | 프로그램을 사용자에게 제공해 사용할 수 있게 하는 일(일반 지식: Wikipedia, Software deployment) |
| installed version number | 설치된 동기화 에이전트의 버전 번호 | 자료의 표현 + 자료 맥락 | - | 자료는 "the installed version number"로만 쓴다. 자료에 나오는 버전 번호(1.8, 2.0, 2.0.3)가 모두 동기화 에이전트의 번호이므로 동기화 에이전트의 번호로 읽었다(자료 맥락) |
| old binary | 이전 버전인 Python 버전의 바이너리 | 자료의 표현 + 자료 맥락 | - | 자료는 old version을 Python 버전의 의미로 쓴다(자료 Two versions, Bugs and tests, Results) |
| new binary | 새 버전인 Rust 버전의 바이너리 | 자료의 표현 + 자료 맥락 | - | 자료는 new version을 Rust 버전의 의미로 쓰고, new binary도 Rust 바이너리의 의미로 쓴다(자료 Two versions, Results) |
| server | 서버 | 한국어 개발 문서에서 정착한 용어 | - | 네트워크로 연결된 다른 컴퓨터에 데이터나 기능을 제공하는 컴퓨터나 프로그램(일반 지식: Wikipedia, Server (computing)) |
| bug | 버그 | 한국어 개발 문서에서 정착한 용어 | - | 프로그램이 의도와 다르게 동작하게 만드는 결함(일반 지식: Wikipedia, Software bug) |
| code path | 코드 경로 | 한국어 개발 문서에서 쓰는 용어 | - | 어떤 상황에서 프로그램이 차례로 실행하는 코드의 순서(일반 지식: testRigor, What is Path Testing) |
| database | 데이터베이스 | 한국어 개발 문서에서 정착한 용어 | DB | 데이터를 체계적으로 정리해 모아 둔 것(일반 지식: Wikipedia, Database) |
| response | 응답 | 한국어 개발 문서에서 정착한 용어 | - | 서버가 요청을 받고 보내는 메시지(일반 지식: MDN, Overview of HTTP) |
| response body | 응답 본문 | 한국어 개발 문서에서 정착한 용어 | 응답 바디 | 응답 중 요청한 내용을 담은 부분(일반 지식: MDN, Overview of HTTP) |
| return | 반환 | style-guide 같은 대상을 부르는 말 | 리턴 | 구성 요소가 처리 결과를 자기를 실행한 코드에 돌려주는 일(일반 지식: Wikipedia, Return statement) |
| version | 버전 | 한국어 개발 문서에서 정착한 용어 | 판 | 설명하지 않음(일상어). Python 버전과 Rust 버전은 각 언어로 작성한 동기화 에이전트(자료) |
| idle | 유휴 상태 | 한국어 개발 문서에서 정착한 용어 | idle | 아무 작업도 하지 않고 대기하는 상태(일반 지식) |
| production | 운영 환경 | 한국어 개발 문서에서 정착한 용어 | 프로덕션 | 개발이나 테스트용 컴퓨터와 달리 실제 사용자가 프로그램을 사용하는 컴퓨터(일반 지식: Wikipedia, Deployment environment) |
| migration | 마이그레이션 | 한국어 개발 문서에서 정착한 용어 | 이주 | 사용하던 프로그램이나 데이터를 새로운 기술이나 장소로 옮기는 작업(일반 지식: SUSE, Application migration). 동기화 에이전트의 마이그레이션은 Python 버전을 사용하던 노트북을 Rust 버전으로 전환하는 작업(자료 맥락) |
| installer | 설치 프로그램 | 일상어 | 인스톨러 | 설명하지 않음(일상어) |
| configuration file | 설정 파일 | 일상어에 가까운 개발 용어 | 구성 파일 | 프로그램이 읽는 설정값을 저장한 파일(일반 지식) |
| registry | 레지스트리 | 한국어 Windows 문서에서 정착한 용어 | registry | Windows와 Windows에서 실행되는 프로그램에 필요한 데이터를 모아 저장하는 곳(일반 지식: Microsoft Learn, Structure of the Registry, "hierarchical database". 글의 데이터베이스 파일과 같은 대상으로 읽히지 않게 "데이터베이스"라고 부르지 않는다) |
| binary | 바이너리 | 한국어 개발 문서에서 정착한 용어 | 이진 파일 | 소스 코드를 컴퓨터가 바로 실행할 수 있는 형태로 변환한 프로그램 파일(일반 지식) |
| copy | 복사본 | style-guide 같은 대상을 부르는 말 | 사본 | 설명하지 않음(일상어) |
| update server | 업데이트 서버 | style-guide 같은 대상을 부르는 말 | 갱신 서버 | 프로그램의 새 버전을 제공하는 서버(자료 맥락). 최신 버전이 공개돼 있어서 다운로드할 수 있다(자료 "published"의 의미. 자동 설치 여부는 자료에 없음) |
| patch version | 패치 버전 | 한국어 개발 문서에서 정착한 용어 | 수정판 | 버그 수정 같은 작은 변경을 담은 버전이고 세 번째 숫자만 바뀐다(자료 + 일반 지식: semver.org) |
| test suite | 테스트 스위트 | 한국어 개발 문서에서 정착한 용어 | 시험 모음 | 프로그램이 예상대로 동작하는지 자동으로 확인하는 테스트 모음(일반 지식) |
| build | 빌드 | 한국어 개발 문서에서 정착한 용어 | - | 소스 코드를 바이너리로 변환하는 작업이나 그 결과물. 소스 코드가 바뀌면 빌드도 새로 만든다(일반 지식: Wikipedia, Software build) |
| regression | 회귀 버그(regression) | 한국어 개발 문서에서 정착한 용어 | 퇴행 | 전에 정상으로 동작하던 기능이 새 변경 때문에 동작하지 않게 된 버그(일반 지식) |
| file watcher | file watcher | 원어로 씀 | 파일 감시자 | 파일과 폴더의 변경을 감지하는 구성 요소(자료 맥락) |
| cover | 커버하다 | style-guide 같은 대상을 부르는 말 | 포괄하다 | 테스트를 실행할 때 그 코드 경로가 실행돼 결과를 확인한다는 의미(일반 지식) |
| network drive | 네트워크 드라이브 | 한국어 Windows 문서에서 정착한 용어 | - | 다른 컴퓨터나 서버의 저장 공간을 내 컴퓨터의 저장 장치처럼 연결한 것(일반 지식: Microsoft Support, File sharing over a network in Windows) |
| lock | 락(lock) | 한국어 개발 문서에서 정착한 용어 | 자물쇠, 잠금 | 한 프로그램이 파일 같은 자원을 사용하는 동안 다른 프로그램이 동시에 변경하지 못하게 막는 장치(일반 지식). 락을 보유한다는 것은 그동안 다른 프로그램이 그 파일을 변경하지 못하게 막고 있다는 의미(일반 지식: Wikipedia, File locking) |
| database file | 데이터베이스 파일 | 한국어 개발 문서에서 정착한 용어 | - | 데이터베이스의 내용을 저장한 파일(일반 지식: Microsoft Learn, Database Files and Filegroups) |
| update checker | update checker | 원어로 씀 | 업데이트 확인기 | 동기화 에이전트의 최신 버전을 확인하는 구성 요소(자료 맥락) |
| HTTP | HTTP(Hypertext Transfer Protocol) | 원어로 씀 | - | 웹에서 서버와 데이터를 주고받는 규칙(일반 지식: RFC 9110, MDN, Overview of HTTP) |
| response header | 응답 헤더 | style-guide 같은 대상을 부르는 말 | 응답 머리글 | 응답에 들어 있는 부가 정보(일반 지식: MDN, Overview of HTTP) |
| local cache | 로컬 캐시 | 한국어 개발 문서에서 정착한 용어 | - | 다른 곳에 있는 데이터를 다음에 더 빨리 읽으려고 노트북에 저장해 둔 복사본(일반 지식: Wikipedia, Cache (computing)). 이 캐시에 무엇이 저장되는지는 자료에 없음 |
| version string | 버전 문자열 | 한국어 개발 문서에서 정착한 용어 | - | 버전을 나타내는 글자와 숫자의 나열(일반 지식) |
| worker | worker | 원어로 씀 | 일꾼 | 프로그램이 할 일을 나눠 맡아 처리하는 구성 요소(일반 지식: Wikipedia, Thread pool) |
| queue | 큐(queue) | 한국어 개발 문서에서 정착한 용어 | 대기열 | 처리할 항목을 들어온 순서대로 쌓아 두고 먼저 들어온 항목부터 처리하는 목록(일반 지식: Wikipedia, Queue (abstract data type)) |
| crash | 크래시 | 한국어 개발 문서에서 정착한 용어 | 충돌 | 프로그램이 오류로 갑자기 종료되는 일(일반 지식) |
| design document | 설계 문서 | 한국어 개발 문서에서 정착한 용어 | 디자인 문서 | 프로그램의 구조와 동작 방식을 설명한 문서(일반 지식) |
| reviewer | 리뷰어 | 한국어 개발 문서에서 정착한 용어 | 검토자 | 문서나 코드를 검토하는 사람(일반 지식) |
| Git | Git | 제품명 원래 표기 | 깃 | 코드와 문서의 변경 이력을 관리하는 도구(일반 지식: git-scm.com 용어집) |
| commit | 커밋 | 한국어 개발 문서에서 정착한 용어. 설계 문서 초안의 단어를 가리킬 때만 따옴표로 "commit" | - | Git의 변경 이력에 기록된 한 시점의 상태(일반 지식: git-scm.com 용어집) |
| HEAD commit | HEAD 커밋 | 원어와 정착한 용어를 함께 씀 | - | HEAD는 Git의 변경 이력에서 지금 작업 중인 지점을 가리키는 이름이고 HEAD 커밋은 그 지점의 커밋(일반 지식: git-scm.com 용어집 "HEAD": "The current branch", "HEAD is a reference to one of the heads in your repository"). 설계 문서의 현재 버전이 커밋 전 사본인지는 자료에 없다 |
| library | 라이브러리 | 한국어 개발 문서에서 정착한 용어 | - | 다른 프로그램이 가져다 사용하는 코드 묶음(일반 지식) |
| benchmark | 벤치마크 | 한국어 개발 문서에서 정착한 용어 | - | 같은 기준으로 성능이나 기능을 측정해 비교하는 테스트(일반 지식) |
| Lee et al. | Lee et al.(2024) | 자료의 표기 | - | Lee를 포함한 저자들이 2024년에 발표한 논문(자료) |
| arXiv | arXiv | 제품명 원래 표기 | 아카이브 | 누구나 논문을 읽을 수 있는 연구 공유 사이트이고, arXiv 자체는 올라온 논문을 전문가 심사 없이 공개한다(일반 지식: arXiv about, "a curated research-sharing platform open to anyone", "Material is not peer-reviewed by arXiv") |
| IEEE | IEEE(Institute of Electrical and Electronics Engineers) | 기관명 원래 표기 | - | 학술지와 학회 논문집을 출판하는 전기전자공학 전문가 단체(일반 지식: Wikipedia, IEEE) |
| Windows junction | Windows junction | 원어로 씀 | 정션 | 한 폴더를 같은 컴퓨터의 다른 폴더에 연결하는 Windows 기능이고, 연결한 폴더를 열면 다른 폴더의 내용이 보인다(일반 지식: Microsoft Learn, Hard Links and Junctions) |
| watch count | watch count | 원어로 씀 | 감시 횟수 | 라이브러리가 감시하는 대상의 수(자료 맥락) |
| r | r | 원어로 씀 | - | 두 측정값이 함께 변하는 정도를 -1에서 1 사이의 수로 나타내는 상관계수. r의 값이 -1이나 1에 가까울수록 관계가 강하고, r이 양수이면 한쪽 측정값이 커질 때 다른 쪽 측정값도 커지는 경향이 있다(일반 지식: Wikipedia, Pearson correlation coefficient, "ranges from −1 to 1"). -1과 1은 측정값이 아니라 정의의 범위다 |
| log | 로그 | 한국어 개발 문서에서 정착한 용어 | - | 프로그램이 동작 내용을 남기는 기록(일반 지식) |
| security tool | 보안 도구 | 일상어 | - | 컴퓨터에 피해를 줄 수 있는 프로그램을 찾아 실행을 막는 프로그램(일반 지식: Wikipedia, Antivirus software). 이 사례의 보안 도구가 어떤 종류인지는 자료에 없음 |

"일반 지식"만 적은 행은 소프트웨어 개발의 기본 용어로, 이번 실행에서 웹으로 따로 확인하지 않았다. 확인한 곳은 괄호에 적었다.

## 인용할 문장

- "This note is fictional material written for a writing evaluation. Do not cite it as a real result." (자료 맨 위, 노트 자신의 설명)
