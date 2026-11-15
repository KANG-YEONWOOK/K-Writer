#!/usr/bin/env python3
"""K-Writer section reader: prints only the named sections of a reference document.

The source of this file is core/scripts/section.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.

A skill run reads the long reference documents (ai-patterns.md, korean-review.md, revision.md, tone.md, style-guide.md)
by section. This script prints a section without the agent having to find its line numbers first.

Usage
  python section.py DOC --list                 # prints the headings of DOC
  python section.py DOC "HEADING" ["HEADING" ...]

DOC is a file name in the skill's references/ folder (korean-review.md) or a path.
HEADING selects every section whose heading contains the text. A heading that starts with a label is also selected
by the label alone: "C" or "C." selects "### C. 주어, 목적어와 ...", and "A22" selects "### A22.heading_sentence. ...".
A section runs from its heading to the next heading of the same or a higher level, so it includes its subsections.

Exit codes: 0 printed, 1 a HEADING matched nothing (the headings are listed on stderr), 2 usage or input error
Uses only the standard library (Python 3.8 or later).
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFERENCES = os.path.join(os.path.dirname(HERE), "references")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def resolve(doc):
    if os.path.isfile(doc):
        return doc
    candidate = os.path.join(REFERENCES, doc if doc.endswith(".md") else doc + ".md")
    return candidate if os.path.isfile(candidate) else None


def headings(lines):
    """Returns [(line index, level, text)] for the headings outside code fences."""
    out, fence = [], None
    for i, line in enumerate(lines):
        m = FENCE_RE.match(line)
        if m:
            mark = m.group(1)[0]
            fence = None if fence == mark else (fence or mark)
            continue
        if fence:
            continue
        h = HEADING_RE.match(line)
        if h:
            out.append((i, len(h.group(1)), h.group(2)))
    return out


LABEL_QUERY_RE = re.compile(r"[A-Z]{1,2}\d{0,2}(?:\.[a-z_0-9]+)?\.?")


def leading_labels(text):
    """Labels a heading starts with: "C. 주어, ..." -> {"C"}, "A1, G8. 부정 대구" -> {"A1", "G8"},
    "A22.heading_sentence. 문장 ..." -> {"A22.heading_sentence", "A22"}."""
    head = text.split(". ", 1)[0] if ". " in text else text.split(" ", 1)[0]
    labels = set()
    for token in re.split(r"[,\s]+", head):
        token = token.strip().rstrip(".,")
        if token and LABEL_QUERY_RE.fullmatch(token):
            labels.add(token)
            labels.add(token.split(".", 1)[0])
    return labels


def matches(query, text):
    q = query.strip()
    if not q:
        return False
    if LABEL_QUERY_RE.fullmatch(q):
        # A short label such as "C" would also be a substring of unrelated headings, so it matches labels only.
        return q.rstrip(".") in leading_labels(text)
    return q in text


def select(lines, queries):
    """Returns (list of (start, end) line ranges in document order, list of queries that matched nothing)."""
    heads = headings(lines)
    ranges, missing = [], []
    for q in queries:
        found = False
        for k, (i, level, text) in enumerate(heads):
            if not matches(q, text):
                continue
            end = next((j for j, lv, _ in heads[k + 1:] if lv <= level), len(lines))
            ranges.append((i, end))
            found = True
        if not found:
            missing.append(q)
    merged = []
    for start, end in sorted(set(ranges)):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged, missing


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description="print sections of a K-Writer reference document")
    ap.add_argument("doc")
    ap.add_argument("heading", nargs="*")
    ap.add_argument("--list", action="store_true", help="print the headings of the document")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    path = resolve(args.doc)
    if not path:
        print(f"문서가 없습니다: {args.doc}", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    heads = headings(lines)
    if args.list or not args.heading:
        for _, level, text in heads:
            print("  " * (level - 1) + text)
        return 0
    ranges, missing = select(lines, args.heading)
    for start, end in ranges:
        print("\n".join(lines[start:end]).rstrip("\n"))
        print()
    if missing:
        print("찾지 못한 섹션: " + ", ".join(missing), file=sys.stderr)
        print("이 문서의 헤딩:", file=sys.stderr)
        for _, level, text in heads:
            print("  " * (level - 1) + text, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
