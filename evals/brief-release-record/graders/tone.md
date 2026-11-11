---
type: regex
target: { source: file, path: summary.md }
pattern: '((?<!필)(?<!중)(?<!주)(?<!개)(?<!수)(?<!강)(?<!소)요|죠)[.!](\s|$)'
flags: m
match: not_contains
---
