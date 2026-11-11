---
type: regex
target: { source: file, path: report.md }
pattern: '(습니다|입니다|합니다|됩니다|어요|아요|해요|예요|에요|이죠)[.?!](\s|$)'
flags: m
match: not_contains
---
