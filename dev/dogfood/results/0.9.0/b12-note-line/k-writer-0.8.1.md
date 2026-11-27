# API 레이트 리미터를 고정 윈도우에서 토큰 버킷으로 바꾼 기록 요약

API 레이트 리미터를 고정 윈도우에서 클라이언트별 토큰 버킷으로 바꾸자 게이트웨이 p99 지연이 1,850ms에서 420ms로 줄었습니다. 다만 토큰 버킷은 여러 클라이언트가 동시에 요청을 시작할 때의 몰림을 막지 못하며 배포 뒤에는 여전히 요청이 잠깐 몰립니다.

자료: Migrating the API rate limiter from fixed window to token bucket, 사내 엔지니어링 노트, 2026 (rate-limiter-note.md)
