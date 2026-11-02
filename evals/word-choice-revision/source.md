# Internal note: moving the session cache to Redis

This note is fictional material written for a writing evaluation. Do not cite it as a real result.

## Background

Until January, each application server kept user sessions in its own memory. When a user's next request went to a different server, that server had no session, and the user was logged out. In February the team moved the session cache to a Redis cluster that all servers share. Session data now lives in Redis, and every server reads sessions from Redis over the network.

The platform team owns the Redis cluster. The application team owns the session code.

Each server returns its Redis connections to a connection pool instead of closing them after each request. Servers create a new session token every time a user logs in. Operators change the session TTL by editing the config file.

## What changed after the migration

The migration opened up a new problem. Invalidation messages between the Seoul and Tokyo regions arrived up to 4 seconds late, so users in Tokyo sometimes read stale sessions. This stale-read bug (issue #4182) was fixed in release 2.3, which sends invalidation messages through a dedicated queue. The dedicated queue also unlocked cross-region failover. The team shipped release 2.3 in March.

Right after the 2.3 rollout, a new error appeared: about 2% of requests returned HTTP 503 for 5 minutes, until the number of queue workers increased.

During the migration, the team held an incident review meeting every Tuesday.

Duplicate warm-up requests at server startup were also reported (issue #4377). The team closed issue #4377 as won't fix in March, because the extra load was below 1% of peak traffic.

## Serialization and retries

Serialization introduces about 0.4 ms of overhead per request. Profiling shed light on where the response time goes: application servers spend 40% of their response time in JSON serialization, and most of that serialization time is in the session encoder. Failed requests sit in the retry queue for up to 2 seconds before they are sent again.

## Results

After release 2.3, the p99 latency gap between the Seoul and Tokyo regions narrowed from 12% to 3%. Reducing the session TTL from 120 seconds to 30 seconds lowered the stale-read rate from 0.8% to 0.1%. Longer TTLs buy a lower cache miss rate at the cost of serving staler sessions. In May, the cache statistics API was opened to external developers.

## Open questions

Whether write-heavy tenants also benefit remains an open question; the team has not measured them. The cross-region replication strategy is still unresolved. The team kept the option of raising the TTL again open.
