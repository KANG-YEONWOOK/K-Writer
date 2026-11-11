---
type: llm
focus: { source: file, path: summary.md }
---

자료(엔지니어링 노트)가 말한 내용은 다음과 같다. fixed window 방식에서는 window가 시작할 때 제한에 걸렸던 클라이언트가 동시에 재시도해서 window의 첫 1초에 부하가 몰렸다(첫 1초에 초당 최대 4,800건, 평균 부하는 초당 900건). 클라이언트마다 token bucket(최대 100 tokens, 초당 10 tokens 충전)을 두는 방식으로 바꿨다. 버킷 상태는 Redis에 저장하고 Lua script가 확인과 차감을 한 번에 처리한다. 거절한 요청의 응답에는 Retry-After 헤더를 넣는다. 배포 2주 뒤 같은 트래픽에서 1초 동안의 최대 부하(4,800건에서 1,400건)와 gateway p99 latency(1,850 ms에서 420 ms)가 줄었고 거절된 요청의 비율은 2.1%에서 2.6%로 늘었으며 Redis CPU 사용률은 8 percentage points 늘었다. 자료는 거절 비율이 늘어난 이유를 클라이언트가 window 경계에서 제한을 넘을 수 없게 됐기 때문이라고 적었다. 한계는 세 가지다. 여러 클라이언트가 같은 순간에 시작하면 효과가 없어서 배포 직후에는 요청이 짧게 몰리고, 활성 클라이언트 50,000개가 넘는 경우는 테스트하지 않았으며, Retry-After를 무시하는 클라이언트는 여전히 바로 재시도한다.

요약의 문장을 하나씩 읽고 자료에 근거가 있는지 확인한다. 자료 전문은 이 문서의 맨 아래 "자료 전문"에 있다. 위 요지에 없는 세부 사실(예: 클라이언트마다 60초에 600건을 허용했다)은 자료 전문에서 찾는다. 제목 줄과 "자료:"로 시작하는 줄은 판정하지 않는다.

PASS: 모든 문장이 자료의 내용이다. 자료에 없는 평가("효과적인 방법입니다"), 조언("도입을 검토해야 합니다"), 전망, 일반론이 없다.
FAIL: 자료에 없는 평가, 조언, 전망, 원인, 사례를 쓴 문장이 하나라도 있다. 또는 자료의 내용과 다르게 쓴 문장이 있다(예: 거절된 요청의 비율이 줄었다고 씀). 판정 근거로 해당 문장을 인용한다.

## 자료 전문

> # Migrating the API rate limiter from fixed window to token bucket (internal engineering note, 2026)
>
> ## Background
> Our public API used a fixed-window rate limiter: each client could send 600 requests per 60-second window. At the start of every window, clients that had been throttled retried at the same moment. We measured bursts of up to 4,800 requests per second in the first second of a window, while the average load was 900 requests per second. These bursts pushed the p99 latency of the gateway to 1,850 ms.
>
> ## What we changed
> We replaced the fixed window with a token bucket per client. Each bucket holds up to 100 tokens and refills at 10 tokens per second, which keeps the long-run limit at 600 requests per minute. Bucket state lives in Redis; a Lua script performs the check-and-decrement atomically, so two gateway instances cannot spend the same token. When a request is rejected, the response includes a Retry-After header computed from the time until the next token.
>
> ## Results (two weeks after rollout, same traffic level)
> - Peak load in any one second dropped from 4,800 to 1,400 requests per second.
> - Gateway p99 latency dropped from 1,850 ms to 420 ms.
> - The share of rejected requests rose from 2.1% to 2.6%, because clients can no longer exceed the limit at window edges.
> - Redis CPU usage increased by 8 percentage points.
>
> ## Limitations
> The token bucket does not help when many different clients start at the same moment; we still see short bursts after deployments. We have not tested the design with more than 50,000 active clients. Clients that ignore Retry-After still retry immediately.
