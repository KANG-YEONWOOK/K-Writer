"""Checks check_ko.py: the first run lints the whole article and saves the checked copy, and later runs report only
the units changed since the checked copy, with unchanged units around them."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "techblog", "scripts")
sys.path.insert(0, SCRIPTS)

import check_ko as C  # noqa: E402

SENTS = [
    "우리 팀은 11월에 공개 API의 요청 제한 방식을 바꿨습니다.",
    "기존 방식은 클라이언트마다 60초에 600건을 허용했습니다.",
    "제한에 걸린 클라이언트는 구간이 시작할 때 동시에 다시 요청했습니다.",
    "구간의 첫 1초에는 초당 4,800건까지 요청이 몰렸습니다.",
    "평균 부하는 초당 900건이었습니다.",
    "이 요청 때문에 게이트웨이의 응답 시간이 길어졌습니다.",
    "새 방식은 클라이언트마다 토큰을 초당 10개씩 채웁니다.",
    "토큰이 없는 요청은 바로 거절합니다.",
    "변경 뒤 첫 1초의 요청은 초당 1,100건으로 줄었습니다.",
    "거절한 요청의 비율은 2.1%에서 2.6%로 늘었습니다.",
    "배포는 일주일 동안 단계별로 진행했습니다.",
    "다음 분기에는 클라이언트별 한도를 조정할 계획입니다.",
]


def article(sents, heading="요청 제한 방식 변경"):
    paras = [" ".join(sents[i:i + 3]) for i in range(0, len(sents), 3)]
    return f"# {heading}\n\n" + "\n\n".join(paras) + "\n"


class CheckKoTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "note.md")
        self.write(SENTS)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, sents, **kw):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(article(sents, **kw))

    def run_check(self, *args):
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_ko.py"), self.path, *args],
                           capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout, p.stderr

    def test_first_run_lints_everything_and_saves_checked_copy(self):
        code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("techblog lint | note.md", out)
        self.assertIn("짧은 글 기준", out)
        self.assertTrue(os.path.isfile(C.checked_path(self.path)))

    def test_later_run_reports_only_changed_units_with_context(self):
        self.run_check()
        edited = list(SENTS)
        edited[5] = "이 요청이 몰리면서 게이트웨이의 p99 응답 시간이 길어졌습니다."
        self.write(edited)
        code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("바뀐 부분 1곳", out)
        self.assertIn("  - L5 " + SENTS[5], out)
        self.assertIn("  + L5 " + edited[5], out)
        for k in (2, 3, 4, 6, 7, 8):  # three unchanged units on each side
            self.assertIn(SENTS[k], out)
        for k in (0, 1, 9, 10, 11):  # outside the window
            self.assertNotIn(SENTS[k], out)

    def test_checked_copy_advances_so_checked_text_is_not_reported_again(self):
        self.run_check()
        edited = list(SENTS)
        edited[1] = "기존 방식은 클라이언트마다 60초 구간에 600건을 허용했습니다."
        self.write(edited)
        _, out, _ = self.run_check()
        self.assertIn(edited[1], out)
        edited[10] = "배포는 11월 첫 주에 일주일 동안 단계별로 진행했습니다."
        self.write(edited)
        _, out, _ = self.run_check()
        self.assertIn(edited[10], out)
        self.assertNotIn(edited[1], out)
        _, out, _ = self.run_check()
        self.assertIn("바뀐 문장, 헤딩, 표의 행이 없다", out)

    def test_keep_does_not_advance(self):
        self.run_check()
        edited = list(SENTS)
        edited[1] = "기존 방식은 클라이언트마다 60초 구간에 600건을 허용했습니다."
        self.write(edited)
        self.run_check("--keep")
        _, out, _ = self.run_check()
        self.assertIn(edited[1], out)

    def test_gate_in_changed_sentence_fails_and_is_marked(self):
        self.run_check()
        edited = list(SENTS)
        edited[7] = "토큰이 없는 요청은 바로 거절합니다 — 예외는 없습니다."
        self.write(edited)
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("반드시 수정할 항목", out)
        self.assertIn("G6.emdash", out)
        self.assertIn("(이번에 바뀐 문장)", out)

    def test_sentence_heading_is_reported_when_heading_changes(self):
        self.run_check()
        self.write(SENTS, heading="요청 제한 방식을 바꿨습니다")
        code, out, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("A22.heading_sentence", out)
        self.assertIn("[헤딩] 요청 제한 방식을 바꿨습니다", out)

    def test_number_changes_are_listed(self):
        self.run_check()
        edited = list(SENTS)
        edited[8] = "변경 뒤 첫 1초의 요청은 초당 1,300건으로 줄었습니다."
        self.write(edited)
        _, out, _ = self.run_check()
        self.assertIn("지난 검사에만 있는 수치", out)
        self.assertIn("1,100", out)
        self.assertIn("새 수치", out)
        self.assertIn("1,300", out)

    def test_all_runs_full_lint_again(self):
        self.run_check()
        _, out, _ = self.run_check("--all")
        self.assertIn("techblog lint | note.md", out)

    def test_candidates_outside_changed_units_are_not_repeated(self):
        sents = list(SENTS)
        sents[0] = "우리 팀은 11월에 공개 API의 요청 제한 방식을 수정했습니다."
        self.write(sents)
        _, first, _ = self.run_check()
        self.assertIn("A18.category_change", first)
        edited = list(sents)
        edited[10] = "배포는 11월 첫 주에 일주일 동안 단계별로 진행했습니다."
        self.write(edited)
        _, out, _ = self.run_check()
        self.assertNotIn("A18.category_change", out)

    def test_work_folder_holds_the_checked_copy_and_the_plan(self):
        # A document written outside a skill run is checked with --work, so no work file is left next to it.
        work = os.path.join(self.dir, "작업 폴더")
        os.makedirs(work)
        with open(os.path.join(work, "note.plan.md"), "w", encoding="utf-8") as f:
            f.write("# 설계\n\n- 핵심 주제: 게이트웨이의 응답 시간이 길어진 원인을 설명한다.\n\n## 단위 1. 원인\n"
                    "- 형태: 문단\n- 전할 내용: 게이트웨이의 응답 시간이 길어진 원인을 설명한다.\n- 전개: 현상 → 원인\n\n"
                    "1. [현상] 금성 관측소의 망원경 예약은 3월 9일에 4,812건으로 늘었다.\n")
        code, out, err = self.run_check("--work", work)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(work, "note.checked.md")))
        self.assertFalse(os.path.isfile(C.checked_path(self.path)))
        self.assertIn("설계 대조", out)
        self.assertIn("4,812", out)
        code, out, err = self.run_check("--work", work)          # the second run finds the copy in the work folder
        self.assertIn("지난 검사 뒤에 바뀐 문장, 헤딩, 표의 행이 없다", out)
        self.assertEqual(sorted(os.listdir(self.dir)), ["note.md", "작업 폴더"])
        code, out, err = self.run_check("--work", os.path.join(self.dir, "없는 폴더"))
        self.assertEqual(code, 2)

    def test_refuses_checked_copy_as_article(self):
        self.run_check()
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_ko.py"), C.checked_path(self.path)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 2)

    def test_profile_follows_body_length(self):
        self.assertTrue(C.use_short(article(SENTS), None))
        self.assertFalse(C.use_short(article(SENTS * 8), None))
        self.assertFalse(C.use_short(article(SENTS), False))


if __name__ == "__main__":
    unittest.main()
