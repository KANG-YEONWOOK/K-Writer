source.md와 스킬이 만든 세 파일을 읽는다. fact sheet(`article.facts.md`)의 "의미"와 용어 표, 6단계를 시작할 때 복사한 5단계 초안(`article.unrevised.md`), 최종 글(`article.md`)이다. 이 평가는 사람 글에서 한국어 표현이 정착한 영어 단어를 스킬이 사전의 대응어나 고유어로 옮기지 않는지 확인한다.

## 자료의 영어 단어

| 번호 | 자료 표현 | 자연스러운 한국어의 예 | 어색한 표현의 예 |
|---|---|---|---|
| P1 | the Python version, the Rust version | Python 버전, Rust 버전 | Python 판, Rust 판 |
| P2 | the old version, the new version, the previous version | 이전 버전, 새 버전, 기존 버전 | 옛 판, 새 판, 이전 판 |
| P3 | the installed version number | 설치된 버전 번호 | 설치된 판 번호 |
| P4 | the latest version, each patch version | 최신 버전, 패치 버전 | 최신판, 패치 판 |
| P5 | the second version (of the document) | 두 번째 버전, 2차 버전 | 두 번째 판 |
| P6 | the arXiv version, the published IEEE version | arXiv 버전, IEEE 출판본, IEEE 게재 버전 | arXiv판, IEEE판 |
| P7 | the version in the HEAD commit | HEAD 커밋의 버전 | HEAD 판 |
| P8 | tests, the test suite, tested | 테스트, 테스트 스위트, 테스트했다 | 시험, 시험 묶음, 시험했다 |
| P9 | bugs, the worst bug | 버그 | 결함 |
| P10 | a copy of the old binary | 복사본, 복제본, 이전 바이너리를 함께 둔다 | 사본 |
| P11 | words, two meanings, one meaning for each word | 단어, 의미 | 낱말, 뜻 |
| P12 | paired every term with a short definition | 용어마다 짧은 정의를 붙였다, 용어와 정의를 쌍으로 | 짝지었다(자연스러우면 OK), 짝 |
| P13 | Among the 12 libraries | 12개 중 | 12개 가운데 |
| P14 | the strength of the link | 상관의 강도, 상관계수 | 세기 |
| P15 | repeated this check, excluded the appendix, removed that section | 반복했다, 제외했다, 삭제했다 | 되풀이했다, 뺐다, 지웠다 |
| P16 | covers the rename path, do not cover network drives | 커버한다, 테스트한다, 포함한다 | 덮는다 |
| P17 | holds a lock | 락을 잡는다, 잠금을 건다, 락을 보유한다 | 락을 쥔다 |
| P18 | returns the latest version string | 반환한다 | 돌려준다 |
| P19 | emits one log line | 로그를 한 줄 출력한다, 남긴다 | 내보낸다 |
| P20 | measured | 측정했다 | 실측했다, 쟀다 |
| P21 | the response header | 헤더 | 머리말 |
| P22 | a hard limit of 8 open files, the remaining entries | 최대 8개, 남은 항목 | 상한(자연스러우면 OK), 잔여 |

## 판정

- 세 파일마다 P1~P22가 나온 부분의 표현을 그대로 인용하고, 자연스러우면 OK, 어색하면 AWKWARD로 적는다. 그 파일에 그 내용이 없으면 ABSENT로 적는다.
- 위 표에 없어도 사람이 쓴 한국어 기술 블로그 글에서 다른 표현으로 부르는 대상을 사전의 대응어나 고유어로 쓴 표현, 물건이나 몸동작에 빗댄 표현을 찾으면 파일과 문장을 함께 적는다.
- 음역으로 바꾸지 않았다는 이유만으로 감점하지 않는다. 오류, 목록, 잠금, 갱신처럼 사람 글에서 사용하는 단어는 OK다.
- 최종 글에 `lint_ko.py --tone default --facts article.facts.md`를 실행할 수 있으면 Gate, FAIL 수와 A6.version_pan, A5.plain_terms, A5.plain_terms_check, A6.metaphor_check로 검출된 줄을 적는다.

## 보고

파일마다 OK, AWKWARD, ABSENT 수를 표로 적고, AWKWARD는 문장을 인용한다. fact sheet에서 생긴 표현이 초안과 최종 글로 이어졌는지, 6단계에서 수정됐는지도 적는다.
