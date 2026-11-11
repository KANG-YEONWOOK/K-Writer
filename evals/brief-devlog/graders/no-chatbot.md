---
type: regex
target: { source: file, path: summary.md }
pattern: '제공된 자료|주어진 (자료|글|문서)|도움이 되셨|물론입니다|궁금한 점이 있으면|원하시면|요청하신|요약해 드리|다음과 같이 요약'
match: not_contains
---
