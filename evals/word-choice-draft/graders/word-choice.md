source.md와 스킬이 만든 세 파일을 읽는다. fact sheet(`article.facts.md`)의 "의미"와 "한계" 항목, 6단계를 시작할 때 복사한 5단계 초안(`article.unrevised.md`), 최종 글(`article.md`)이다. 이 평가는 스킬이 6단계에서 수정하기 전에도 영어 비유 동사를 단어의 사전적 의미대로 옮기지 않는지(예방)와 최종 글에 그런 표현이 남지 않는지를 확인한다.

## 자료의 영어 동사

| 번호 | 자료 표현 | 자료가 설명하는 내용 | 자연스러운 한국어 서술어의 예 | 직역이나 내용이 틀린 예 |
|---|---|---|---|---|
| T1 | Index state lives in object storage | 상태가 object storage에 저장된다 | 저장된다, 있다 | 산다 |
| T2 | lag was dominated by queueing time, documents spent 70% of the lag waiting | 대기 시간이 지연의 70%를 차지한다 | 대부분을 차지했다, 70%가 대기 시간이었다 | 지배됐다, 시간을 보냈다 |
| T3 | The search infrastructure team owns the indexer | 그 팀이 맡는다 | 담당한다, 맡는다 | 소유한다 |
| T4 | Workers spend 60% of their CPU time decompressing | 압축 해제가 CPU 시간의 60%를 차지한다 | 차지한다 | 시간을 보낸다, 60%가 걸린다 |
| T5 | compressing a batch introduces about 3 ms of overhead | 문서마다 약 3 ms가 더 든다 | 오버헤드가 생긴다, 3 ms가 더 걸린다 | 오버헤드를 도입한다 |
| T6 | Batching opened up a new problem | 새 문제가 생겼다 | 생겼다, 발생했다 | 열렸다, 열었다 |
| T7 | it was closed after the fix landed in v4.1 | v4.1에 수정이 반영된 뒤 해결됐다 | 해결됐다, 수정이 반영됐다, 머지됐다 | 닫혔다, 착륙했다 |
| T8 | The team shipped v4.1 in June | 6월에 배포했다 | 배포했다, 출시했다 | 출하했다 |
| T9 | surfaces indexing errors to the seller | 판매자에게 오류를 보여 준다 | 보여 준다, 알린다 | 표면화한다 |
| T10 | unblocks the remaining migrations | 남은 마이그레이션을 진행할 수 있게 된다 | 진행할 수 있게 됐다 | 막힘을 풀었다, 블록을 해제했다 |
| T11 | SEARCH-327 was closed as won't fix | 고치지 않기로 하고 닫았다 | 고치지 않기로 했다 | 해결됐다, 닫혔다(이유 없이) |
| T12 | Batching closed most of the gap between the two clusters | 부산 클러스터의 지연이 9분에서 2분으로 줄어 차이가 크게 줄었다 | 크게 줄었다, 좁혀졌다 | 격차를 닫았다, 차이를 없앴다 |
| T13 | remains an open question | 아직 시험하지 않았다 | 아직 확인하지 않았다, 시험하지 않았다 | 열린 질문으로 남았다 |
| T14 | kept the option ... open | 가능성을 남겨 두었다 | 가능성을 열어 두었다, 여지를 남겼다 | (이 표현은 자연스러워서 수정하지 않아도 된다) |

## 판정

- 세 파일마다 T1~T13이 나온 부분의 서술어를 그대로 인용하고, 자연스럽고 자료의 내용과 같으면 OK, 영어 동사를 단어의 사전적 의미대로 옮겼으면 CALQUE, 내용이 자료와 다르면 WRONG으로 적는다. 그 파일에 그 내용이 없으면 ABSENT로 적는다.
- T14는 "가능성을 열어 두었다"를 수정했는지 적는다. 수정해도 감점하지 않지만 보고한다.
- 위 표에 없는 다른 서술어 직역이나 주어, 목적어와 어울리지 않는 서술어를 찾으면 파일과 문장을 함께 적는다.
- 최종 글에 `lint_ko.py --tone default --facts article.facts.md`를 실행할 수 있으면 Gate, FAIL 수와 A6.open_close, A6.open_close_check로 검출된 줄을 적는다.

## 보고

파일마다 OK, CALQUE, WRONG, ABSENT 수를 표로 적고, CALQUE와 WRONG은 문장을 인용한다. fact sheet에서 생긴 직역이 초안과 최종 글로 이어졌는지, 6단계에서 수정됐는지도 적는다.
