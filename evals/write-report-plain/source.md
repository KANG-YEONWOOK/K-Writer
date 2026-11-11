# Incident notes: checkout API latency (2026-11-07)

- 13:50 Deployed a config change raising the DB connection pool max from 50 to 200 per instance (12 instances).
- 14:10 p99 latency of the checkout API rose from 180 ms to 2,400 ms. Alerts fired.
- 14:25 On-call engineer (Mina Park) found the database at its 2,000-connection limit; new connections were being refused.
- 14:58 Rolled the config back to 50.
- 15:02 p99 latency back to 190 ms.
- Impact: 52 minutes of degraded checkout. 3.8% of checkout requests failed during the window (normally 0.2%).
- Root cause: 12 instances x 200 = 2,400 connections exceeded the database limit of 2,000. The change was not load-tested in staging because staging runs only 2 instances.
- Follow-ups: (1) Add a deploy check that pool max x instance count stays under 80% of the DB limit. Owner: Jisoo Han, due 2026-11-21. (2) Whether to raise the DB connection limit is still open; to be discussed on 2026-11-14.
