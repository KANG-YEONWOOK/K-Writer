---
type: regex
target: { source: file, path: notice.md }
pattern: '(습니다|입니다|합니다|됩니다|십시오)[.?!](\s|$)|더라고요|네요[.!]|잖아요'
flags: m
match: not_contains
---
