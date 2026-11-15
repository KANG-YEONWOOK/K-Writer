# How we moved the public API rate limiter from a fixed window to a token bucket, and what changed

Our team changed the rate limiter on our public API from a fixed window to a token bucket. A fixed window limits how many requests a client can send in each time window of a set length. A token bucket accepts a request only while a token is left, and it refills the tokens at a steady rate. Two weeks after we rolled out the token bucket, at the same traffic level as before the change, the gateway's p99 latency had dropped from 1,850 ms to 420 ms.

Before the change, each client could send up to 600 requests in every 60-second window. Every time a new window started, the clients whose requests had been rejected all retried at the same moment. The average load was 900 requests per second, but in the first second of a window as many as 4,800 requests per second arrived, and these bursts pushed the gateway's p99 latency up to 1,850 ms.

With the token bucket, each client has one bucket. Each request uses one token from that bucket, and a request is rejected when the bucket has no tokens. A bucket holds up to 100 tokens and is refilled at 10 tokens per second, so the long-run limit is 600 requests per minute, the same as before the change.

The state of each bucket is stored in Redis, and a Lua script checks whether a token is left and takes one away as a single atomic operation. As a result, two gateway instances can never use the same token. When a request is rejected, the response includes a Retry-After header, and its value is calculated from the time left until the next token is added.

We compared the results two weeks after rolling out the token bucket, at the same traffic level as before the change. The peak load in any one second dropped from 4,800 to 1,400 requests per second, and the gateway's p99 latency dropped from 1,850 ms to 420 ms.

Under the same conditions, the share of rejected requests rose from 2.1% to 2.6%. This is because, with the fixed window, a client could send more requests than the limit around the moment one window ended and the next began, and with the token bucket it no longer can. Redis CPU usage also rose, by 8 percentage points.

The token bucket does not help when many different clients start sending requests at the same moment, so we still see short bursts right after deployments. Clients that ignore the Retry-After header still retry immediately when a request is rejected. Our team has not tested the token bucket design with more than 50,000 active clients.
