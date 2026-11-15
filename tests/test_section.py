"""Checks section.py: it prints the named sections of a reference document so a skill run does not read the whole file."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "techblog", "scripts")
sys.path.insert(0, SCRIPTS)

import section as S  # noqa: E402

DOC = """# 문서

머리말이다.

## 유형과 수정 방법

### C. 주어, 목적어와 어울리지 않는 서술어 (A6.calque_check)

C의 본문이다.

#### C의 하위 섹션

하위 본문이다.

### V. 짧은 선언형 문장

V의 본문이다.

```
## 코드 블록 안의 줄은 헤딩이 아니다
```

### A1, G8. 부정 대구

A1의 본문이다.

### A22.heading_sentence. 문장으로 끝난 제목과 헤딩

A22의 본문이다.

## Casual 종결

Casual의 본문이다.
"""


class SectionTest(unittest.TestCase):
    def pick(self, *queries):
        lines = DOC.split("\n")
        ranges, missing = S.select(lines, queries)
        return "\n".join("\n".join(lines[a:b]) for a, b in ranges), missing

    def test_label_selects_one_section_with_its_subsections(self):
        text, missing = self.pick("C")
        self.assertEqual(missing, [])
        self.assertIn("C의 본문이다.", text)
        self.assertIn("하위 본문이다.", text)
        self.assertNotIn("V의 본문이다.", text)
        self.assertNotIn("Casual의 본문이다.", text)       # "C" is a label, not a substring of "Casual"

    def test_labels_listed_together_and_item_ids(self):
        for query in ("A1", "G8", "G8."):
            with self.subTest(query=query):
                self.assertIn("A1의 본문이다.", self.pick(query)[0])
        for query in ("A22", "A22.heading_sentence"):
            with self.subTest(query=query):
                self.assertIn("A22의 본문이다.", self.pick(query)[0])

    def test_heading_text_and_several_queries(self):
        text, missing = self.pick("Casual 종결", "V")
        self.assertEqual(missing, [])
        self.assertIn("Casual의 본문이다.", text)
        self.assertIn("V의 본문이다.", text)
        self.assertNotIn("C의 본문이다.", text)

    def test_parent_section_includes_children_once(self):
        text, _ = self.pick("유형과 수정 방법", "C")
        self.assertEqual(text.count("C의 본문이다."), 1)
        self.assertIn("A22의 본문이다.", text)
        self.assertNotIn("Casual의 본문이다.", text)

    def test_code_fence_lines_are_not_headings(self):
        self.assertNotIn("코드 블록 안의 줄은 헤딩이 아니다", [t for _, _, t in S.headings(DOC.split("\n"))])

    def test_cli_resolves_reference_names_and_reports_missing_sections(self):
        run = [sys.executable, os.path.join(SCRIPTS, "section.py")]
        r = subprocess.run(run + ["korean-review.md", "X"], capture_output=True)
        self.assertEqual(r.returncode, 0)
        out = r.stdout.decode("utf-8")
        self.assertTrue(out.startswith("### X. 문장으로 끝난 제목과 헤딩"))
        self.assertNotIn("## 수정하지 않는 표현", out)
        r = subprocess.run(run + ["korean-review.md", "없는 섹션"], capture_output=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("유형 찾기", r.stderr.decode("utf-8"))
        r = subprocess.run(run + ["없는문서.md", "X"], capture_output=True)
        self.assertEqual(r.returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "doc.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(DOC)
            r = subprocess.run(run + [path, "--list"], capture_output=True)
            self.assertIn("    C. 주어, 목적어와 어울리지 않는 서술어 (A6.calque_check)", r.stdout.decode("utf-8"))

    def test_sections_named_in_the_workflow_documents_exist(self):
        # checking.md and the skills' work documents tell the agent to read these sections by name.
        refs = os.path.join(ROOT, "skills", "techblog", "references")
        for doc, queries in (("korean-review.md", ("유형 찾기", "바꾸지 않는 것", "수정하지 않는 표현", "C", "D", "F", "G",
                                                   "S", "T", "U", "V", "W", "X")),
                             ("ai-patterns.md", ("과교정하지 않기", "G6", "A22")),
                             ("tone.md", ("Default와 Casual 대응표", "Plain 종결(해라체)", "사용자가 직접 정한 어투",
                                          "숫자, 영어, 기호 뒤 조사")),
                             ("style-guide.md", ("제목과 헤딩", "단어 선택과 문법", "바꾼 일과 정한 값의 내용 쓰기",
                                                 "처음 나오는 용어와 중심 대상 설명")),
                             ("style-sources.md", ("영어 자료를 한국어로 옮기기", "자료의 말을 옮기는 문장",
                                                   "위치와 순서의 대응 보여 주기")),
                             ("checking.md", ("어투 적용하기", "작업 파일 정리하기"))):
            with open(os.path.join(refs, doc), encoding="utf-8") as f:
                lines = f.read().split("\n")
            _, missing = S.select(lines, queries)
            self.assertEqual(missing, [], doc)


if __name__ == "__main__":
    unittest.main()
