---
type: llm
focus: { source: file, path: summary.md }
---

아래는 요약한 자료에 있는 수치 전부다: 600건, 60초, 1초(window의 첫 1초, 1초 동안의 최대 부하), 4,800 requests/s, 900 requests/s, 1,850 ms, 100 tokens, 초당 10 tokens, 분당 600, 2주, 1,400 requests/s, 420 ms, 2.1%, 2.6%, 8 percentage points, 50,000 active clients, 2026년.

요약의 수치가 위 목록의 값인지, 위 목록의 값만으로 사칙연산해서 나오는 값인지 하나씩 확인한다. 계산 값에는 차이, 비율, 배수, 감소율과 그 반올림이 포함된다. "p99"의 99는 수치로 간주하지 않는다.

PASS: 모든 수치가 목록의 값이거나 목록의 값으로 계산되는 값이다.
FAIL: 목록의 값으로 계산되지 않는 수치가 하나라도 있다.
