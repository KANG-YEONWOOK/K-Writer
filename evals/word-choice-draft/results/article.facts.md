# article fact sheet

핵심 주제: 상품 글 검색 indexer가 문서를 하나씩 object storage에 쓰던 방식을 문서 최대 200개를 한 번에 쓰는 배치 방식으로 바꾸자 부산 클러스터의 index lag가 9분에서 2분으로 줄었고, 배치 때문에 새로 생긴 문제는 어떻게 처리했으며 무엇을 아직 확인하지 않았는지 알게 된다.

- 독자: 검색 시스템 지식이 충분하지 않거나 없을 수 있는 사람(기본값)
- 분량: 자료 크기에 맞춤(기본값). 자료가 영어 약 300단어의 짧은 내부 메모라서 공백 제외 2,500~4,000자를 계획 참고치로 둔다. 상한으로 적용하지 않는다.
- 어투: Default(합니다체, 기본값)

## 중심 대상

| 대상 | 정의 | 정의할 위치 |
|---|---|---|
| 검색 indexer | 판매자가 올린 상품 글을 검색 인덱스의 항목으로 바꾸는 프로그램(자료 1절). 4월까지는 문서를 한 번에 하나씩 처리했다. | 도입 둘째 문단(구체 장면 바로 뒤) |
| index lag | 판매자가 상품 글을 올린 때부터 그 상품 글을 검색할 수 있게 된 때까지 걸리는 시간(자료 1절) | 도입 둘째 문단(구체 장면 바로 뒤) |
| 배치 방식 | 문서를 최대 200개까지 묶어 object storage에 한 번의 쓰기 요청으로 보내는 방식(자료 2절) | "최대 200개씩 묶어 쓰는 배치 방식" 절의 첫 문단 |

## 자료 정보

- 제목: Internal note: batching in the search indexer
- 저자나 기관: 밝히지 않음. 자료는 검색 인프라 팀이 indexer를 관리한다고만 밝혔다.
- 연도: 밝히지 않음(월만 나옴: 4월, 6월)
- URL: 없음(로컬 파일 source.md)
- 자료의 성격: 자료 첫 문단이 글쓰기 평가용으로 만든 가상 자료이고 실제 결과로 인용하지 말라고 밝혔다. 원문: "This note is fictional material written for a writing evaluation. Do not cite it as a real result." 글의 참고자료 절에 가상 자료임을 적는다.

## 문제와 배경

- 판매자가 상품 글을 올리면 검색 indexer가 상품 글 하나하나를 검색 인덱스의 항목으로 바꾼다. 원문: "Sellers upload product listings, and the search indexer turns each listing into an entry in the search index."
- 4월까지 indexer는 문서를 한 번에 하나씩 처리했다. 원문: "Until April, the indexer processed one document at a time."
- 검색 인덱스의 데이터는 object storage에 저장돼 있고, 문서 하나를 처리할 때마다 object storage에 쓰기 요청을 따로 보내야 했다. 원문: "Index state lives in object storage, and every document required a separate write to object storage."
- 배치 도입 전에는 큐 대기 시간이 index lag의 대부분을 차지했다. 문서가 큐에서 차례를 기다린 시간이 index lag의 70%를 차지했다. 원문: "Index lag, the time between an upload and the moment the listing becomes searchable, was dominated by queueing time: documents spent 70% of the lag waiting in the queue."
- indexer는 검색 인프라 팀이 맡고, 업로드 클라이언트는 listing 팀이 맡는다. 원문: "The search infrastructure team owns the indexer. The listing team owns the upload client."

## 방법

- 핵심 아이디어: 문서를 최대 200개까지 묶어 한 번의 쓰기 요청으로 보낸다. 원문: "The team grouped up to 200 documents into one write." 원문의 "The team"이 두 팀 가운데 어느 팀인지는 밝히지 않았다. 글에서는 팀을 주어로 쓰지 않고 배치 방식과 indexer를 주어로 쓴다.
- 압축 비용: 문서 압축 해제가 worker CPU 시간의 60%를 차지한다. 배치를 압축하면 문서 하나당 약 3 ms의 overhead가 생긴다. 원문: "Workers spend 60% of their CPU time decompressing documents, and compressing a batch introduces about 3 ms of overhead per document." 60%는 압축 해제(decompressing), 3 ms는 배치 압축(compressing a batch)의 값이다. 3 ms는 배치 하나가 아니라 문서 하나당 값이다.
- 실험 설정: 자료는 실험 설정(측정 기간, 측정 방법, 트래픽 규모)을 밝히지 않았다. 결과로는 부산 클러스터와 서울 클러스터의 index lag, object storage 쓰기 요청의 최대치를 보고했다. 팀이 배치 방식을 시험한 상품 글은 이미지가 없는 상품 글뿐이다(자료 4절). 이 시험과 3절 결과의 측정이 같은 것인지, 부산 클러스터의 측정에 이미지가 있는 상품 글이 들어 있었는지는 자료가 밝히지 않았다(6단계 후처리에서 정정: 초안 마치며의 "9분에서 2분으로 줄어든 결과는 이미지가 없는 상품 글로만 시험해서 얻은 것"은 자료에 없는 연결이라 고쳤다).

## 수치

| 무엇을 잰 값 | 값 | 단위 | 조건 | 비교 대상 | 원문 표현 | 바꾼 값 |
|---|---|---|---|---|---|---|
| index lag 가운데 문서가 큐에서 기다린 시간의 비율 | 70 | % | 배치 도입 전(자료 1절, 과거형) | index lag 전체 | documents spent 70% of the lag waiting in the queue | - |
| 쓰기 요청 한 번에 묶는 문서 수의 상한 | 200 | 개 | 배치 도입 후 | - | grouped up to 200 documents into one write | 최대 200개 |
| worker의 CPU 시간 가운데 문서 압축 해제에 쓰는 비율 | 60 | % | 시점을 밝히지 않음(현재형) | worker의 CPU 시간 전체 | Workers spend 60% of their CPU time decompressing documents | - |
| 배치를 압축할 때 생기는 overhead | 약 3 | ms, 문서 하나당 | 배치를 압축할 때 | - | compressing a batch introduces about 3 ms of overhead per document | 약 0.003초. 문서 200개가 든 배치라면 약 600 ms(0.6초)(계산값: 3 ms x 200) |
| 문서를 하나씩 처리한 기간 | 4월까지 | - | 연도를 밝히지 않음 | - | Until April, the indexer processed one document at a time. | - |
| v4.1 배포 시점 | 6월 | - | 연도를 밝히지 않음 | - | The team shipped v4.1 in June. | - |
| 중복 문서가 나타난 검색 요청의 비율 | 0.01 미만 | % | SEARCH-327을 고치지 않기로 한 근거 | 전체 검색 요청 | duplicates appeared in fewer than 0.01% of queries | 검색 요청 1만 건 가운데 1건 미만 |
| 부산 클러스터의 index lag | 9에서 2로 | 분 | 배치 도입 전에서 후로 | 서울 클러스터 1.5분 | index lag in the Busan cluster fell from 9 minutes to 2 minutes | 7분 줄었다(계산값). 줄어든 비율은 약 78%(7/9=0.78) |
| 서울 클러스터의 index lag | 1.5(변화 없음) | 분 | 배치 도입 전과 후 | - | while the Seoul cluster stayed at 1.5 minutes | 90초 |
| 두 클러스터의 index lag 차이 | 7.5에서 0.5로 | 분 | 계산값(부산 값에서 서울 값을 뺌) | - | Batching closed most of the gap between the two clusters | 7.5분에서 0.5분(30초)으로. 차이의 약 93%(7/7.5=0.93)가 줄었다 |
| object storage 쓰기 요청의 최대치 | 85 감소 | % | 배치 도입 전에서 후로 | 배치 도입 전의 최대치 | Peak write requests to object storage fell by 85%. | 배치 도입 전 최대치의 15%. "85% 줄었다"이지 "85%로 줄었다"가 아니다 |
| 아직 확인하지 않은 이미지 크기 | 5 | MB | 5 MB보다 큰 이미지가 있는 상품 글 | - | listings with images larger than 5 MB | - |

- 버전 이름: v4.1. 무엇의 버전인지는 밝히지 않았다(문맥상 indexer 쪽 변경). SEARCH-311의 수정과 schema registry가 v4.1에 들어갔다.

### 계산값(글에서 분석에 쓰는 값)

| 계산값 | 식 | 근거 수치 |
|---|---|---|
| index lag에서 큐 대기를 뺀 나머지 30% | 100% - 70% = 30% | 큐 대기 70% |
| 큐 대기 시간은 나머지 시간을 합친 것의 2배가 넘음(약 2.3배) | 70 / 30 = 2.33 | 큐 대기 70% |
| 같은 배치에서 함께 거부될 수 있던 다른 문서 최대 199개 | 200 - 1 = 199 | 배치 하나에 문서 최대 200개 |
| 문서 200개를 담은 배치의 압축 overhead 약 600 ms(0.6초) | 3 ms x 200 = 600 ms | 문서 하나당 약 3 ms |
| 부산 클러스터의 index lag 감소폭 7분 | 9 - 2 = 7 | 9분, 2분 |
| 두 클러스터의 차이 7.5분에서 0.5분(30초)으로, 약 93% 줄어듦 | 9 - 1.5 = 7.5, 2 - 1.5 = 0.5, (7.5 - 0.5) / 7.5 = 0.93 | 9분, 2분, 1.5분 |
| 쓰기 요청의 최대치가 배치 도입 전의 15%로 줄어듦 | 100% - 85% = 15% | 85% 감소 |
| 0.01%는 검색 요청 1만 건 가운데 1건 | 0.01 / 100 = 1 / 10,000 | 0.01% 미만 |

### 설명용 예시

- 가정: 저장할 문서가 200개 있다.
- 입력과 계산: 문서마다 쓰기 요청을 따로 보내던 방식은 쓰기 요청이 200번 필요하다. 배치 방식은 문서 200개를 배치 하나에 담아 쓰기 요청 한 번으로 저장한다(배치 하나의 상한이 200개이므로).
- 결과: 같은 문서 200개를 저장하는 데 필요한 쓰기 요청이 200번에서 1번이 된다. 이 값은 자료가 측정한 값이 아니라 배치 방식의 동작(최대 200개를 한 번에 씀)에서 계산한 설명용 값이다. 자료가 측정한 값은 쓰기 요청 최대치 85% 감소다.

## 뜻

| 원문 표현 | 뜻(초안은 이 칸에서 쓴다) |
|---|---|
| the search indexer turns each listing into an entry in the search index | 검색 indexer는 상품 글 하나하나를 검색 인덱스의 항목으로 바꾼다. |
| Until April, the indexer processed one document at a time. | 4월까지 indexer는 문서를 한 번에 하나씩 처리했다. |
| Index state lives in object storage | 검색 인덱스의 데이터는 object storage에 저장돼 있다. |
| every document required a separate write to object storage | indexer는 문서 하나를 처리할 때마다 object storage에 쓰기 요청을 따로 보내야 했다. |
| was dominated by queueing time: documents spent 70% of the lag waiting in the queue | 배치 도입 전에는 큐 대기 시간이 index lag의 대부분을 차지했다. 문서가 큐에서 차례를 기다린 시간이 index lag의 70%를 차지했다. |
| The search infrastructure team owns the indexer. The listing team owns the upload client. | indexer는 검색 인프라 팀이 맡고, 업로드 클라이언트는 listing 팀이 맡는다. |
| grouped up to 200 documents into one write | 배치 방식에서 indexer는 문서를 최대 200개까지 묶어 쓰기 요청 한 번으로 object storage에 저장한다. |
| Workers spend 60% of their CPU time decompressing documents | 문서의 압축을 해제하는 일이 worker CPU 시간의 60%를 차지한다. |
| compressing a batch introduces about 3 ms of overhead per document | 배치를 압축하면 문서 하나당 약 3 ms의 overhead가 생긴다. |
| Batching opened up a new problem: when one document in a batch failed validation, the whole batch was rejected. | 배치 방식을 도입하자 새 문제가 생겼다. 배치 안의 문서 하나가 검증을 통과하지 못하면 배치 전체가 거부됐다. |
| Ticket SEARCH-311 tracked this problem, and it was closed after the fix landed in v4.1. | 이 문제는 SEARCH-311 티켓에 기록됐다. 수정 사항이 v4.1에 반영된 뒤 문제가 해결됐고 SEARCH-311 티켓도 닫혔다. |
| The fix retries only the failed document. | 수정한 뒤 indexer는 검증에 실패한 문서만 다시 처리한다. |
| The team shipped v4.1 in June. | v4.1은 6월에 배포됐다. |
| The new upload client surfaces indexing errors to the seller, so a seller sees which listing failed and why. | 새 업로드 클라이언트는 인덱싱 오류를 판매자에게 보여 준다. 판매자는 어느 상품 글이 실패했고 왜 실패했는지 알 수 있다. |
| The schema registry added in v4.1 also unblocks the remaining migrations of older listing formats. | v4.1에 schema registry가 추가되면서, 예전 형식의 상품 글을 옮기는 남은 마이그레이션을 진행할 수 있게 됐다. 마이그레이션이 끝났다는 뜻은 아니다. |
| A report of duplicate documents in the index (SEARCH-327) was closed as won't fix, because duplicates appeared in fewer than 0.01% of queries and the next full reindex removes them. | 검색 인덱스에 중복 문서가 있다는 보고(SEARCH-327)는 수정하지 않기로 결정됐고 티켓은 won't fix로 닫혔다. 중복 문서가 나타난 검색 요청은 전체의 0.01% 미만이었고, 다음 full reindex가 중복 문서를 지우기 때문이다. 해결된 것이 아니다. |
| Batching closed most of the gap between the two clusters | 배치 방식을 도입한 뒤 두 클러스터의 index lag 차이가 대부분 줄었다. 차이는 7.5분에서 0.5분이 됐다(계산값). |
| index lag in the Busan cluster fell from 9 minutes to 2 minutes, while the Seoul cluster stayed at 1.5 minutes | 부산 클러스터의 index lag는 9분에서 2분으로 줄었고, 서울 클러스터의 index lag는 1.5분 그대로였다. |
| Peak write requests to object storage fell by 85%. | object storage로 가는 쓰기 요청의 최대치는 85% 줄었다. |
| Whether the approach works for listings with images larger than 5 MB remains an open question | 5 MB보다 큰 이미지가 있는 상품 글에도 배치 방식을 적용할 수 있는지는 아직 답이 없다. ("통하는지"는 오류 없이 동작하는지와 같은 효과를 내는지 가운데 어느 쪽인지 정해지지 않아 6단계에서 바꿨다) |
| the team has only tested listings without images | 배치 방식은 이미지가 없는 상품 글로만 시험했다. |
| The team kept the option of a smaller batch size for urgent listings open. | 급한 상품 글에 배치 크기를 더 작게 설정하는 방안은 아직 결정되지 않았고 선택지로 남아 있다. |

## 추정 표현

자료에 추정 낱말(likely, may, suggest)은 없다. 어림하거나 범위를 정한 표현만 있고, 글에는 아래 한국어 표현으로 쓴다.

| 원문 | 글에 쓸 표현 |
|---|---|
| about 3 ms | 약 3 ms |
| fewer than 0.01% | 0.01% 미만 |
| up to 200 | 최대 200개 |
| most of the gap | 차이의 대부분 |
| dominated by | 대부분을 차지했다 |

## 한계

- 5 MB보다 큰 이미지가 있는 상품 글에서 배치 방식이 통하는지는 아직 확인하지 않았다(아직 답이 없는 문제).
- 배치 방식은 이미지가 없는 상품 글로만 시험했다. 5 MB 이하의 이미지가 있는 상품 글도 시험하지 않았다.
- 급한 상품 글에 더 작은 배치 크기를 설정할지는 아직 결정하지 않았다.
- 자료가 밝히지 않은 것(글에서 사실처럼 채우지 않는다): 서울 클러스터의 index lag가 왜 그대로였는지, 서울 클러스터에도 배치 방식을 적용했는지, 배치 도입 후 큐 대기 시간의 비율, 측정 기간과 연도, 다음 full reindex의 시점, 60%가 배치 도입 전과 후 가운데 어느 때의 값인지, 검증이 무엇을 확인하는지, 급한 상품 글의 기준.

## 용어

- 확인 범위: 이번 실행은 평가 조건상 웹 검색을 하지 않았다. 아래 "일반 지식(…)"의 괄호는 그런 설명이 실리는 문헌의 종류이고, 이번 실행에서 그 문헌을 직접 열어 확인하지 않았다. 일반 지식 설명에는 수치, 연구 결과, 연도, 인물을 넣지 않았다.

| 원어 | 글에 쓸 표기 | 근거 | 쓰지 않을 표기 | 처음 나올 때 설명(근거) |
|---|---|---|---|---|
| search indexer | 검색 indexer | 원어로 씀(indexer의 굳은 한국어 표기를 확인하지 못함) | 인덱서, 색인기 | 판매자가 올린 상품 글을 검색 인덱스의 항목으로 바꾸는 프로그램(자료 1절). 이름은 '인덱스를 만드는 것'이라는 뜻(일반 지식: 영어 사전) |
| search index | 검색 인덱스 | 한국어 개발 문서에서 굳은 말(인덱스) | search index | 검색어로 원하는 항목을 빨리 찾을 수 있게 미리 정리해 둔 데이터(일반 지식: 데이터베이스 교과서의 인덱스 설명) |
| entry | 항목 | 일상에서 쓰는 말 | 엔트리 | 설명하지 않음(일상어) |
| product listing | 상품 글 | 일상에서 쓰는 말(쇼핑, 중고 거래 서비스의 판매 글) | 리스팅, 상품 목록 | 판매자가 팔 상품을 소개하려고 올리는 글(자료 1절 문맥과 일반 지식: 쇼핑 서비스의 판매 글) |
| seller | 판매자 | 일상에서 쓰는 말 | 셀러 | 설명하지 않음(일상어) |
| upload | 올리다 | 일상에서 쓰는 말 | - | 설명하지 않음(일상어) |
| document | 문서 | 검색 엔진의 한국어 문서에서 굳은 말 | 도큐먼트 | 검색 인덱스에 넣으려고 처리하는 데이터 한 건(일반 지식: 검색 엔진 문서의 document 설명). 이 자료에서 검색 indexer가 처리하는 문서는 판매자가 올린 상품 글의 데이터다(자료 1~2절 문맥: indexer가 상품 글을 검색 인덱스의 항목으로 바꾸고, 문서가 실패하면 판매자가 어느 상품 글이 실패했는지 본다). 상품 글 하나와 문서 하나가 일대일인지는 쓰지 않는다 |
| object storage | object storage(객체 스토리지) | 원어로 씀. 괄호의 한국어 이름은 클라우드 서비스의 한국어 문서에서 쓰는 말 | 오브젝트 스토리지, 객체 저장소 | 데이터를 파일 같은 객체 단위로 저장하고 네트워크로 요청을 보내 읽고 쓰는 저장소(일반 지식: 클라우드 저장소 문서) |
| write | 쓰기 요청 | 한국어 개발 문서에서 굳은 말(쓰기) | 라이트 | 저장소에 데이터를 저장해 달라고 보내는 요청(일반 지식: 저장소 문서의 읽기와 쓰기 설명) |
| index lag | index lag | 원어로 씀(자료가 붙인 이름, 굳은 한국어 표기 없음) | 인덱스 지연, 색인 지연 | 판매자가 상품 글을 올린 때부터 그 상품 글을 검색할 수 있게 된 때까지 걸리는 시간(자료 1절). 이름의 lag는 '뒤처짐'이라는 뜻(일반 지식: 영어 사전) |
| queue | 큐 | 자료구조 교과서와 한국어 개발 문서에서 굳은 말 | queue | 처리할 작업이 들어온 순서대로 차례를 기다리는 대기열(일반 지식: 자료구조 교과서) |
| queueing time | 큐 대기 시간 | 일상어 조합 | 큐잉 시간 | 문서가 큐에서 처리 차례를 기다린 시간(자료 1절 "waiting in the queue") |
| batch | 배치 | 한국어 개발 문서에서 굳은 말(배치 처리) | batch | 여러 문서를 하나로 묶은 단위(일반 지식: 배치 처리 설명) |
| batching | 배치 방식 | 일상어 조합 | 배칭 | 문서를 최대 200개까지 묶어 object storage에 한 번의 쓰기 요청으로 보내는 방식(자료 2절) |
| batch size | 배치 크기 | 한국어 개발 문서에서 굳은 말 | 배치 사이즈 | 배치 하나에 넣는 문서 수(일반 지식: 배치 처리 설명) |
| worker | worker | 원어로 씀 | 워커, 작업자 | 대기 중인 작업을 받아 실제로 처리하는 프로그램(일반 지식: 분산 처리 시스템 문서). 이 시스템의 worker는 문서를 처리한다(자료 2절 "Workers ... decompressing documents"). 검색 indexer 안의 프로그램인지는 자료에 없다 |
| CPU | CPU(중앙 처리 장치) | 원어로 씀(약어) | - | 컴퓨터에서 계산을 맡는 부품(일반 지식: 표준국어대사전 '중앙 처리 장치') |
| CPU time | CPU 시간 | 한국어 개발 문서에서 굳은 말 | CPU 타임 | 프로그램이 CPU를 실제로 사용한 시간(일반 지식: 운영체제 교과서) |
| compression | 압축 | 일상에서 쓰는 말(파일 압축) | 컴프레션 | 설명하지 않음(일상어) |
| decompression | 압축 해제 | 일상에서 쓰는 말(파일 압축 해제) | 디컴프레션 | 설명하지 않음(일상어) |
| overhead | overhead | 원어로 씀 | 오버헤드 | 본래 하려는 일 외에 추가로 드는 처리 시간(일반 지식: 컴퓨터 공학 용어) |
| ms | ms(밀리초) | 단위 | - | 설명하지 않음(단위, 괄호의 밀리초로 충분) |
| validation | 검증 | 한국어 개발 문서에서 굳은 말 | 밸리데이션, 유효성 검사 | 문서가 정해진 형식과 규칙에 맞는지 확인하는 단계(일반 지식: 소프트웨어 개발 용어). 무엇을 확인하는지는 자료에 없다 |
| reject | 거부 | 일상에서 쓰는 말 | 리젝트, 반려 | 설명하지 않음(일상어) |
| ticket | 티켓 | 한국어 개발 문서에서 굳은 말(이슈 관리 도구의 티켓) | 이슈 | 해야 할 일이나 발견한 문제를 한 건씩 기록하고 처리 상태를 관리하는 항목(일반 지식: 이슈 관리 도구 문서) |
| SEARCH-311 | SEARCH-311 | 자료의 티켓 번호 | - | 배치 전체가 거부되는 문제를 기록한 티켓(자료 2절) |
| SEARCH-327 | SEARCH-327 | 자료의 티켓 번호 | - | 검색 인덱스에 중복 문서가 있다는 보고를 기록한 티켓(자료 2절) |
| fix | 수정 | 일상에서 쓰는 말 | 픽스 | 설명하지 않음(일상어) |
| retry | 다시 처리 | 일상에서 쓰는 말 | 리트라이 | 설명하지 않음(일상어) |
| v4.1 | v4.1 | 자료의 버전 표기 | - | 6월에 배포한 버전의 이름(자료 2절). 이름의 v는 version(버전)의 머리글자(일반 지식) |
| ship | 배포 | 한국어 개발 문서에서 굳은 말 | 출시, 출하 | 새 버전을 실제 서비스에 적용하는 일(일반 지식: 소프트웨어 개발 용어) |
| upload client | 업로드 클라이언트 | 한국어 개발 문서에서 굳은 말(클라이언트) | 업로드 앱 | 판매자가 상품 글을 올릴 때 사용하는 프로그램(자료 1~2절 문맥). 클라이언트는 서버에 요청을 보내는 쪽 프로그램을 뜻한다(일반 지식: 네트워크 교과서) |
| indexing | 인덱싱 | 한국어 개발 문서에서 굳은 말 | 색인 작업 | 상품 글을 검색 인덱스에 넣는 작업(일반 지식: 검색 엔진 문서) |
| indexing error | 인덱싱 오류 | 일상어 조합 | 인덱싱 에러 | 상품 글을 검색 인덱스에 넣는 과정에서 생긴 오류(자료 2절) |
| schema registry | schema registry | 원어로 씀(기능 이름, 굳은 한국어 표기 없음) | 스키마 레지스트리, 스키마 저장소 | 데이터 형식의 정의를 한곳에 등록해 두고 여러 프로그램이 같은 정의를 쓰게 하는 저장소(일반 지식: 데이터 플랫폼 문서). 이름은 schema(데이터 구조의 정의)를 등록해 두는 곳(registry)이라는 뜻(일반 지식: 영어 사전) |
| migration | 마이그레이션 | 한국어 개발 문서에서 굳은 말 | 이관 | 데이터를 예전 형식에서 새 형식으로 옮기는 작업(일반 지식: 데이터베이스 운영 문서) |
| listing format | 상품 글 형식 | 일상어 조합 | 리스팅 포맷 | 상품 글 데이터를 담는 형식(자료 2절 "older listing formats") |
| duplicate document | 중복 문서 | 일상어 조합 | - | 검색 인덱스에 같은 문서가 두 번 이상 들어간 것(일반 지식: 데이터 중복의 뜻) |
| query | 검색 요청 | 일상어 조합 | 쿼리 | 사용자가 검색어를 넣어 결과를 받는 요청 한 번(일반 지식: 검색 엔진 문서) |
| won't fix | won't fix(수정하지 않음) | 원어로 씀(이슈 관리 도구의 종료 사유 이름) | - | 문제를 확인했지만 수정하지 않기로 하고 티켓을 닫을 때 붙이는 종료 사유(일반 지식: 이슈 관리 도구 문서) |
| full reindex | full reindex | 원어로 씀(굳은 한국어 표기를 확인하지 못함) | 전체 재색인, 리인덱싱 | 검색 인덱스 전체를 처음부터 다시 만드는 작업(일반 지식: 검색 엔진 문서) |
| cluster | 클러스터 | 한국어 개발 문서에서 굳은 말 | 군집 | 여러 서버를 묶어 하나의 시스템처럼 운영하는 단위(일반 지식: 분산 시스템 문서) |
| Busan cluster | 부산 클러스터 | 자료의 이름을 한국어로 씀 | - | 설명하지 않음(클러스터를 설명한 뒤 지역 이름으로 구분) |
| Seoul cluster | 서울 클러스터 | 자료의 이름을 한국어로 씀 | - | 설명하지 않음(클러스터를 설명한 뒤 지역 이름으로 구분) |
| peak write requests | 쓰기 요청의 최대치 | 일상어 조합 | 피크 | 쓰기 요청이 가장 많이 몰린 때의 요청 수(자료 3절 "Peak write requests") |
| MB | MB | 단위 | - | 설명하지 않음(생활에서 쓰는 용량 단위) |
| image | 이미지 | 일상에서 쓰는 말 | - | 설명하지 않음(일상어) |
| urgent listing | 급한 상품 글 | 일상어 조합 | - | 자료가 urgent listings라고 부른 상품 글. 무엇을 급한 상품 글로 보는지는 자료에 없다(자료 4절) |
| search infrastructure team | 검색 인프라 팀 | 팀 이름을 한국어로 씀 | - | indexer를 맡은 팀(자료 1절) |
| listing team | listing 팀 | 원어로 씀(팀 이름) | 리스팅 팀 | 업로드 클라이언트를 맡은 팀(자료 1절). 이름의 listing은 메모에서 상품 글을 가리키는 영어 낱말(자료 1절 "product listings") |
| internal note | 메모 | 일상에서 쓰는 말 | 노트 | 설명하지 않음(일상어). 글에서 자료를 가리키는 이름으로 쓴다 |
| server | 서버 | 한국어 개발 문서에서 굳은 말 | - | 설명하지 않음(괄호에 '컴퓨터'를 함께 써서 클러스터 설명 안에서 풀이) |

## 개요(3단계)

- 제목: 검색 indexer의 배치 방식: 부산 클러스터의 index lag를 9분에서 2분으로 줄인 변경
- 도입: 상품 글을 올렸는데 한동안 검색되지 않는 상황 → 바로 뒤에 검색 indexer, 검색 인덱스, index lag 정의 → 메모 소개(가상 자료, 저자와 연도 없음) → 이 글에서 정리할 것(index lag가 어떻게 달라졌고 새로 생긴 문제를 어떻게 처리했는지)
- H2 1 "문서마다 쓰기 요청을 따로 보내던 검색 indexer": 배경과 문제. 문서, object storage, 쓰기 요청, 큐 정의. 큐 대기 70%, 나머지 30%와 2배 넘는 차이
- H2 2 "문서 최대 200개를 쓰기 요청 한 번으로 저장하는 배치 방식": 중심 대상 배치 방식 정의(첫 문단). 배치, 배치 크기 정의. 설명용 예시(200번에서 1번). 압축 overhead 약 3 ms와 600 ms 계산값, worker CPU 시간 60%
- H2 3 "부산 클러스터와 서울 클러스터의 index lag": 클러스터 정의, 표(도입 전과 후), 차이 7.5분에서 0.5분, 쓰기 요청 최대치 85% 감소와 15%
- H2 4 "배치 전체가 거부되던 문제와 v4.1의 수정": 새 문제, 검증 정의, 최대 199개 계산값, SEARCH-311, 티켓 정의, 실패한 문서만 다시 처리, v4.1 6월 배포, schema registry와 마이그레이션
- H2 5 "판매자에게 인덱싱 오류를 보여 주는 업로드 클라이언트": 업로드 클라이언트 정의, 인덱싱 오류, 맡은 팀
- H2 6 "고치지 않기로 한 중복 문서 문제": SEARCH-327, won't fix, 0.01% 미만(1만 건 가운데 1건 미만), full reindex 정의, full reindex를 드물게 실행하는 시스템이라면(추론)
- H2 7 "이미지가 있는 상품 글에 적용한다면": 이미지 없는 상품 글로만 시험, 5 MB 질문, 5 MB 이하도 범위 밖, 급한 상품 글의 배치 크기 미결정
- 마치며: 결론이 성립하는 조건(이미지 없는 상품 글, 부산 클러스터), 배치 방식을 도입할 때 문서 하나의 실패 처리, SEARCH-327 판단의 두 조건, 남은 질문
- 참고자료: 메모 하나(가상 자료임을 적음)

## 인용할 문장

- 글에서 원문을 직접 인용하지 않는다. 자료는 연구 하나(내부 메모 하나)이고 저자 이름이 없다.
- 자료의 성격을 밝힌 문장(자료 첫 문단, 자료의 성격 정의): "This note is fictional material written for a writing evaluation. Do not cite it as a real result." 참고자료 절에 반영한다.
