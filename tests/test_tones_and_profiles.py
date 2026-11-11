"""Tones beyond Default and Casual, the short profile, and per-skill allowances.

- lint_ko.py --tone plain ("해라체") and --tone free (a tone the user described; no tone verdict).
- lint_ko.py --short: the short profile in rules.json, used by brief and by write for texts under 1,500 characters.
- Skill allowances in thresholds.json: write lets a text address its reader and turns the experience gates into
  check candidates, while techblog and brief keep the core gates.
- tone_check.py --tone plain|free.
- revise_ko.py check/audit --short judge with the same profile as lint_ko.py --short.
- Borrowed limits (dev/borrow_thresholds.py): write and brief judge expression items with techblog's limits.
The source comparison of the former techblog short mode (F items, --source, --terms) no longer exists.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "techblog", "scripts")
sys.path.insert(0, SCRIPTS)

import lint_ko as L  # noqa: E402


def skill_thresholds(skill):
    return os.path.join(ROOT, "skills", skill, "scripts", "thresholds.json")


def load_script(skill, name):
    path = os.path.join(ROOT, "skills", skill, "scripts", name)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(f"kw_{skill}_{name[:-3]}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(os.path.dirname(path))
    return mod


DEFAULT = """배치 크기를 10으로 줄인 설정에서 p99 무효화 지연은 4.2초에서 0.8초로 줄었습니다. 측정은 12개 서비스에서 했습니다.

쓰기 비율이 30%를 넘는 서비스에서는 처리량이 15% 떨어졌습니다. 어떤 설정이 지연을 줄였을까요? 기본 블록 크기는 16입니다.
"""
PLAIN = """배치 크기를 10으로 줄인 설정에서 p99 무효화 지연은 4.2초에서 0.8초로 줄었다. 측정은 12개 서비스에서 했다.

쓰기 비율이 30%를 넘는 서비스에서는 처리량이 15% 떨어졌다. 어떤 설정이 지연을 줄였을까? 기본 블록 크기는 16이다.
"""
BANMAL = """배치 크기를 10으로 줄인 설정에서 p99 무효화 지연은 4.2초에서 0.8초로 줄었어. 측정은 12개 서비스에서 했어.

쓰기 비율이 30%를 넘는 서비스에서는 처리량이 15% 떨어졌어. 어떤 설정이 지연을 줄였을까? 기본 블록 크기는 16이야.
"""
NOTICE = """11월 사내 스터디 참가 신청을 11월 20일까지 받습니다. 참가하려면 신청 양식에 이름을 적어 제출해 주세요.

직접 운영해 보니 6명이 넘으면 토론이 어려웠습니다. 궁금한 점이 있으면 운영 담당자에게 문의해 주세요.
"""
NOTICE_PLAIN = """11월 사내 스터디 참가 신청을 11월 20일까지 받는다. 참가하려면 신청 양식에 이름을 적어 제출하기 바란다.

직접 운영해 보니 6명이 넘으면 토론이 어려웠다. 궁금한 점이 있으면 운영 담당자에게 문의하기 바란다.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def lint(self, text, tone, skill="techblog", short=False):
        out, verdict = L.run(self.write("text.md", text), tone, thresholds_path=skill_thresholds(skill),
                             as_json=True, short=short)
        report = json.loads(out)
        return report, {r["id"]: r for r in report["results"]}, verdict


class PlainAndFreeToneTest(Base):
    def test_plain_text_is_on_tone_only_as_plain(self):
        _, rows, verdict = self.lint(PLAIN, "plain", short=True)
        self.assertEqual(rows["G4.off_tone"]["value"], 0)
        self.assertEqual(verdict, "PASS")
        _, rows, verdict = self.lint(PLAIN, "default", short=True)
        self.assertEqual(rows["G4.off_tone"]["value"], 5)
        self.assertEqual(verdict, "FAIL")

    def test_default_and_casual_endings_are_off_tone_in_a_plain_text(self):
        mixed = PLAIN.replace("측정은 12개 서비스에서 했다.", "측정은 12개 서비스에서 했습니다.") \
                     .replace("줄였을까?", "줄였을까요?")
        _, rows, _ = self.lint(mixed, "plain", short=True)
        self.assertEqual(rows["G4.off_tone"]["value"], 2)

    def test_auto_picks_the_most_frequent_tone(self):
        self.assertEqual(self.lint(PLAIN, "auto")[0]["tone"], "plain")
        self.assertEqual(self.lint(DEFAULT, "auto")[0]["tone"], "default")
        casual = DEFAULT.replace("줄었습니다", "줄었어요").replace("했습니다", "했어요") \
                        .replace("떨어졌습니다", "떨어졌어요").replace("16입니다", "16이에요")
        self.assertEqual(self.lint(casual, "auto")[0]["tone"], "casual")

    def test_free_tone_has_no_tone_verdict(self):
        _, rows, verdict = self.lint(BANMAL, "free", short=True)
        self.assertEqual(rows["G4.off_tone"]["value"], 0)
        self.assertEqual(rows["G4.banned_ending"]["value"], 0)
        self.assertEqual(verdict, "PASS")
        _, rows, _ = self.lint(BANMAL.replace("16이야.", "16이야ㅋ 🙂"), "free", short=True)
        self.assertEqual(rows["G6.emoji"]["status"], "GATE")        # the other gates still apply

    def test_the_cli_accepts_the_new_tones(self):
        script = os.path.join(SCRIPTS, "lint_ko.py")
        path = self.write("plain.md", PLAIN)
        for tone, code in (("plain", 0), ("free", 0), ("default", 1)):
            done = subprocess.run([sys.executable, script, path, "--tone", tone, "--short"], capture_output=True,
                                  text=True, encoding="utf-8")
            self.assertEqual(done.returncode, code, (tone, done.stdout))


class ShortProfileTest(Base):
    def test_core_rules_hold_the_profile_and_no_source_comparison(self):
        rules = L.load_json(L.RULES_PATH)
        self.assertEqual(rules["short"]["poisson_floor"], 1)
        self.assertEqual([m for m in rules["metrics"] if m.startswith("F")], [])
        for skill in ("techblog", "write", "brief"):
            own = L.load_json(skill_thresholds(skill))
            self.assertNotIn("short", own, skill)                    # every skill uses the core profile
        script = os.path.join(SCRIPTS, "lint_ko.py")
        path = self.write("text.md", DEFAULT)
        done = subprocess.run([sys.executable, script, path, "--short", "--source", path], capture_output=True,
                              text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 2)                         # --source went away with the short mode

    def test_a_short_summary_passes_in_brief(self):
        _, rows, verdict = self.lint(DEFAULT, "default", skill="brief", short=True)
        self.assertEqual(verdict, "PASS", {k: v["status"] for k, v in rows.items() if v["status"] != "PASS"})

    def test_ratio_items_that_need_many_sentences_are_dropped(self):
        text = "김 등(2025)은 로그 3억 건을 분석했습니다. 저자들은 지연이 배치 대기에서 생긴다고 추정합니다.\n"
        _, rows, _ = self.lint(text, "default", skill="brief")
        self.assertEqual(rows["A16.source_subject_share"]["status"], "FAIL")   # one of two sentences is over 6%
        _, rows, verdict = self.lint(text, "default", skill="brief", short=True)
        self.assertNotIn("A16.source_subject_share", rows)
        self.assertNotIn("T.kkayo_ratio", rows)
        self.assertEqual(verdict, "PASS")

    def test_rates_per_1k_are_judged_by_count(self):
        bad = DEFAULT.replace("측정은 12개 서비스에서 했습니다.",
                              "서비스는 12개 캐시 노드를 가지고 있습니다. 그것은 중요한 역할을 합니다.")
        _, rows, verdict = self.lint(bad, "default", skill="brief", short=True)
        self.assertGreaterEqual(rows["A14.translationese_per_1k"]["value"], 2)
        self.assertEqual(rows["A14.translationese_per_1k"]["status"], "FAIL")
        self.assertEqual(verdict, "FAIL")
        _, rows, _ = self.lint(bad, "default", skill="brief")
        self.assertEqual(rows["A14.translationese_per_1k"]["status"], "INFO")  # under 1,500 characters

    def test_fixed_items_still_fail_in_a_short_text(self):
        text = "이전 판은 실패했습니다. 새 판은 모든 테스트를 통과했습니다.\n"
        _, rows, verdict = self.lint(text, "default", skill="brief", short=True)
        self.assertEqual(rows["A6.version_pan"]["status"], "FAIL")
        self.assertEqual(verdict, "FAIL")
        _, _, verdict = self.lint(text.replace("판", "버전"), "default", skill="brief", short=True)
        self.assertEqual(verdict, "PASS")

    def test_one_rare_expression_is_allowed(self):
        once = DEFAULT + "\n결과 표는 Redis를 써서 만들었습니다.\n"
        _, rows, _ = self.lint(once, "default", skill="brief", short=True)
        self.assertEqual(rows["A5.native_verbs"]["status"], "PASS")
        twice = once + "\n로그는 Kafka를 써서 모았습니다.\n"
        _, rows, _ = self.lint(twice, "default", skill="brief", short=True)
        self.assertIn(rows["A5.native_verbs"]["status"], ("WARN", "FAIL"))

    def test_uncalibrated_skills_report_distribution_items_as_info(self):
        long_text = "\n\n".join([DEFAULT.strip()] * 20)                     # over 1,500 characters
        for skill in ("write", "brief"):
            _, rows, _ = self.lint(long_text, "default", skill=skill)
            self.assertEqual(rows["A2.comma_per_sentence"]["status"], "INFO", skill)
            self.assertEqual(rows["A2.comma_per_sentence"]["limit"], {"note": L.UNCALIBRATED_NOTE})


class SkillAllowanceTest(Base):
    def test_write_lets_a_text_address_its_reader(self):
        _, rows, verdict = self.lint(NOTICE, "default", skill="write", short=True)
        self.assertEqual(rows["G4.off_tone"]["value"], 0)
        self.assertEqual(rows["G3.chatbot"]["value"], 0)
        self.assertEqual(verdict, "PASS")

    def test_write_shows_experience_as_a_check_candidate(self):
        report, rows, _ = self.lint(NOTICE, "default", skill="write", short=True)
        self.assertEqual(rows["G2.experience"]["status"], "CHECK")
        self.assertEqual(rows["G2.experience"]["group"], "fact")
        self.assertEqual(report["summary"]["gate_fail"], 0)
        text, _ = L.run(self.write("notice.md", NOTICE), "default", thresholds_path=skill_thresholds("write"),
                        short=True)
        self.assertIn("자료 대조 후보", text)

    def test_techblog_and_brief_keep_the_core_gates(self):
        for skill in ("techblog", "brief"):
            _, rows, verdict = self.lint(NOTICE, "default", skill=skill, short=True)
            self.assertEqual(rows["G2.experience"]["status"], "GATE", skill)
            self.assertEqual(rows["G3.chatbot"]["status"], "GATE", skill)
            self.assertEqual(rows["G4.off_tone"]["status"], "GATE", skill)
            self.assertEqual(verdict, "FAIL")

    def test_write_still_rejects_chatbot_residue(self):
        _, rows, _ = self.lint("물론입니다. 요청하신 글을 아래에 정리했습니다.\n", "default", skill="write", short=True)
        self.assertEqual(rows["G3.chatbot"]["status"], "GATE")

    def test_allowed_regexes_exist_in_the_pattern_file(self):
        patterns = L.load_json(L.PATTERNS_PATH)["patterns"]
        allowed = L.load_json(skill_thresholds("write"))["allow_patterns"]
        for pid, regexes in allowed.items():
            for rx in regexes:
                self.assertIn(rx, patterns[pid]["regex"], (pid, rx))


class BorrowedLimitsTest(Base):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("kw_borrow", os.path.join(ROOT, "dev", "borrow_thresholds.py"))
        self.borrow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.borrow)

    def test_write_and_brief_hold_the_source_limits(self):
        self.assertEqual(self.borrow.borrowers(ROOT), ["brief", "write"])
        for skill in ("brief", "write"):
            self.assertEqual(self.borrow.differences(skill, ROOT), [], "python dev/borrow_thresholds.py를 실행한다")
            self.assertEqual(len(self.borrow.borrowed_limits(skill, ROOT)), 15)

    def test_only_expression_items_are_borrowed(self):
        """Distribution and format items differ by genre, so a skill without its own sample must not borrow them."""
        for skill in ("brief", "write"):
            for mid in L.load_json(skill_thresholds(skill))["borrowed"]["metrics"]:
                self.assertFalse(mid.startswith(("A8.", "A9.", "A10.", "A11.", "A16.", "A17.", "T.")), (skill, mid))
                self.assertNotEqual(mid, "A2.comma_per_sentence")

    def test_expression_items_are_judged(self):
        text = "\n\n".join(["캐시 문제가 아니라 배치 크기 문제입니다. 지연이 아니라 처리량이 원인입니다."] * 4) + "\n"
        for skill in ("brief", "write"):
            _, rows, verdict = self.lint(text, "default", skill=skill, short=True)
            self.assertEqual(rows["A1.np"]["status"], "FAIL", skill)
            self.assertEqual(rows["A1.np"]["limit"]["basis"], "poisson")
            self.assertEqual(verdict, "FAIL")


class ReviseShortProfileTest(Base):
    """revise_ko.py check and audit must agree with lint_ko.py --short. Without --short they judged short texts with
    the full profile: a summary that passed lint failed check with no edits, and a regression that lint caught
    passed check."""

    SUMMARY = ("배치 크기를 10으로 줄인 설정에서 p99 무효화 지연은 4.2초에서 0.8초로 줄었습니다. "
               "측정은 12개 서비스에서 했습니다. 저자들은 지연 대부분이 배치 대기에서 생긴다고 추정합니다. "
               "쓰기 비율이 30%를 넘는 서비스에서는 처리량이 15% 떨어졌습니다.\n")

    def revise(self, *args):
        script = os.path.join(ROOT, "skills", "brief", "scripts", "revise_ko.py")
        return subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True, encoding="utf-8")

    def test_an_unedited_summary_that_passes_lint_passes_check(self):
        draft = self.write("note.draft.md", self.SUMMARY)
        _, verdict = L.run(draft, "default", thresholds_path=skill_thresholds("brief"), short=True)
        self.assertEqual(verdict, "PASS")
        self.assertEqual(self.revise("start", draft).returncode, 0)
        self.assertEqual(self.revise("check", draft, "--short").returncode, 0)
        self.assertEqual(self.revise("audit", draft, "--short").returncode, 0)
        done = self.revise("check", draft)                          # the full profile judges one of four sentences
        self.assertEqual(done.returncode, 1)
        self.assertIn("A16.source_subject_share", done.stdout)

    def test_a_regression_lint_catches_fails_check(self):
        draft = self.write("note.draft.md", self.SUMMARY)
        self.assertEqual(self.revise("start", draft).returncode, 0)
        self.write("note.draft.md", self.SUMMARY.replace(
            "측정은 12개 서비스에서 했습니다.", "서비스는 12개 캐시 노드를 가지고 있습니다. 그것은 중요한 역할을 합니다."))
        _, verdict = L.run(draft, "default", thresholds_path=skill_thresholds("brief"), short=True)
        self.assertEqual(verdict, "FAIL")
        done = self.revise("check", draft, "--short")
        self.assertEqual(done.returncode, 1)
        self.assertIn("A14.translationese_per_1k", done.stdout)


class ToneCheckTargetTest(Base):
    def test_plain_and_free_targets(self):
        T = load_script("techblog", "tone_check.py")
        self.assertEqual([i for i in T.check(DEFAULT, PLAIN, "plain")["issues"] if i["level"] == "FAIL"], [])
        codes = {i["code"] for i in T.check(DEFAULT, PLAIN)["issues"]}       # the default target is Casual
        self.assertIn("C_TONE", codes)
        self.assertEqual([i for i in T.check(DEFAULT, BANMAL, "free")["issues"] if i["level"] == "FAIL"], [])
        codes = {i["code"] for i in T.check(DEFAULT, DEFAULT, "plain")["issues"]}   # left in "합니다체"
        self.assertIn("C_TONE", codes)

    def test_a_changed_number_fails_for_every_target(self):
        T = load_script("techblog", "tone_check.py")
        for tone, converted in (("plain", PLAIN), ("free", BANMAL)):
            codes = {i["code"] for i in T.check(DEFAULT, converted.replace("0.8초", "0.9초"), tone)["issues"]}
            self.assertIn("TOKEN", codes, tone)

    def test_requests_in_a_default_draft_follow_the_skill_allowance(self):
        T = load_script("write", "tone_check.py")
        allow = L.load_thresholds(skill_thresholds("write"))
        self.assertEqual([i for i in T.check(NOTICE, NOTICE_PLAIN, "plain", allow)["issues"] if i["level"] == "FAIL"], [])
        codes = [i["code"] for i in T.check(NOTICE, NOTICE_PLAIN, "plain")["issues"]]
        self.assertEqual(codes.count("D_TONE"), 2)                          # "제출해 주세요", "문의해 주세요"

    def test_the_cli_reads_the_allowance_of_its_own_skill(self):
        d, c = self.write("d.md", NOTICE), self.write("c.md", NOTICE_PLAIN)
        for skill, code in (("write", 0), ("techblog", 1)):
            script = os.path.join(ROOT, "skills", skill, "scripts", "tone_check.py")
            done = subprocess.run([sys.executable, script, d, c, "--tone", "plain"], capture_output=True, text=True,
                                  encoding="utf-8")
            self.assertEqual(done.returncode, code, (skill, done.stdout))

    def test_cleanup_deletes_the_answer_work_file(self):
        T = load_script("techblog", "tone_check.py")
        answer, article = self.write("note.answer.md", PLAIN), self.write("note.md", PLAIN)
        T.cleanup([answer, article])
        self.assertFalse(os.path.exists(answer))
        self.assertTrue(os.path.exists(article))


if __name__ == "__main__":
    unittest.main()
