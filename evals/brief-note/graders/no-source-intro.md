---
type: regex
target: { source: file, path: summary.md }
pattern: '^(이 (문서|노트|글|자료)(는|은|에서는)|(한|어느) (조직|회사|팀)의 [^.\n]{0,30}(문서|노트)에 따르면|내부 (기술 )?(문서|노트)에 따르면)'
flags: m
match: not_contains
---
