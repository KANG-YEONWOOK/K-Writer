# API 요청 수 제한 방식을 고정 윈도우에서 토큰 버킷으로 바꾼 노트 요약

공개 API의 요청 수 제한 방식을 고정 윈도우에서 클라이언트별 토큰 버킷으로 바꾸자 배포 2주 뒤 같은 트래픽 수준에서 게이트웨이의 p99 지연이 1,850ms에서 420ms로 줄었습니다. 대신 거부된 요청의 비율은 2.1%에서 2.6%로 늘었고 Redis의 CPU 사용률은 8%p 올랐습니다.

자료: Migrating the API rate limiter from fixed window to token bucket, 사내 엔지니어링 노트, 2026, rate-limiter-note.md
