"""Checks plan_ko.py (the writing plan check, the key elements of a fact sheet, and the comparison of an article with
its plan), the comparisons that check_ko.py prints, and the lint items for links between sentences, topic words, and
noun runs (A23, A24)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "write", "scripts")
sys.path.insert(0, SCRIPTS)

import lint_ko as L  # noqa: E402
import plan_ko as P  # noqa: E402

PLAN = """# 설계

- 핵심 주제: 무효화 메시지의 배치 크기를 100에서 10으로 줄이자 p99 무효화 지연이 4.2초에서 0.8초로 줄었다는 것을 독자가 알게 된다.
- 분량: 500자 안팎

## 단위 1. 결과
- 형태: 제목과 첫 문단
- 전할 내용: 배치 크기를 줄인 뒤 무효화 지연이 줄었다.
- 전개: 결과 → 바꾼 설정

1. [결과] 쓰기 비율이 30% 미만인 서비스 12개에서 p99 무효화 지연이 4.2초에서 0.8초로 줄었다. (사실 1)
2. [방법] 김 등(2025)은 무효화 메시지의 배치 크기를 100에서 10으로 줄였다. (사실 2)

## 단위 2. 지연이 늘었던 원인
- 형태: 문단
- 전할 내용: 배치가 크면 메시지 하나가 실패했을 때 배치 전체를 다시 보내므로 지연이 늘었다.
- 전개: 현상 → 과정

1. [현상] 배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였다. (사실 3)
2. [과정] 배치 안의 메시지 하나가 실패하면 캐시 노드는 그 배치의 메시지 100개를 모두 다시 받는다. (사실 4)

## 제외한 사실
- write-through 캐시는 실험하지 않았다(분량 때문에 제외).
"""

ARTICLE = """# 배치 크기를 줄여 캐시 무효화 지연 단축

쓰기 비율이 30% 미만인 서비스 12개에서 p99 무효화 지연은 4.2초에서 0.8초로 줄었습니다. 김 등(2025)이 무효화 메시지의 배치 크기를 100에서 10으로 줄인 결과입니다.

배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였습니다. 배치에 든 메시지 하나가 실패하면 캐시 노드가 그 배치의 메시지 100개를 모두 다시 받아야 했기 때문입니다.
"""


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class PlanCheckTest(unittest.TestCase):
    def test_parse_reads_units_sentences_and_sources(self):
        plan = P.parse_plan(PLAN)
        self.assertTrue(plan["main"].startswith("무효화 메시지의 배치 크기"))
        self.assertEqual([u["n"] for u in plan["units"]], [1, 2])
        self.assertEqual(plan["units"][1]["point"][:6], "배치가 크면")
        sents = P.all_sentences(plan)
        self.assertEqual(len(sents), 4)
        self.assertEqual(sents[0]["role"], "결과")
        self.assertEqual(sents[0]["source"], "사실 1")
        self.assertTrue(sents[1]["text"].endswith("줄였다."))   # "(2025)" inside the sentence is not the source
        self.assertEqual(len(plan["excluded"]), 1)

    def test_long_source_and_title_line_are_not_flagged(self):
        """In the first runs a source that listed five fact sheet rows was read as part of the sentence, and the title
        line was reported as a plan line that is not a sentence. Both made the writer rewrite a correct plan."""
        text = PLAN.replace("(사실 3)", "(사실: 재전송 비율, 배치 크기 설정, 측정 기간, 측정 대상 서비스, 용어: 재전송(자료 2쪽))")
        text = text.replace("1. [결과] 쓰기 비율이", "- [제목] 배치 크기를 줄여 캐시 무효화 지연 단축\n1. [결과] 쓰기 비율이")
        text = text.replace("## 제외한 사실", "## 단위 3. 제목만 있는 단위\n- 형태: 제목\n- 전할 내용: 글의 제목을 정한다.\n\n"
                            "1. [제목] 캐시 무효화 지연 단축 (요청)\n\n## 제외한 사실")
        plan = P.parse_plan(text)
        sents = P.all_sentences(plan)
        self.assertEqual(len(sents), 4)
        self.assertTrue(sents[2]["text"].endswith("18%였다."))
        self.assertTrue(sents[2]["source"].startswith("사실: 재전송 비율"))
        self.assertEqual([b["kind"] for u in plan["units"] for b in u["blocks"]], ["제목", "제목"])
        res = P.check(plan)
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["candidates"], [])

    def test_bare_numbers_of_the_fact_sheet_are_not_listed(self):
        facts = "| 항목 | 값 | 자료 위치 |\n|---|---|---|\n| 재시도 간격 | 250ms | 13 |\n| 측정 연도 | 2025 | 28 |\n"
        self.assertEqual(P.check(P.parse_plan(PLAN), facts)["numbers"]["unassigned"], ["250ms"])

    def test_complete_plan_has_no_error_and_no_candidate(self):
        res = P.check(P.parse_plan(PLAN))
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["candidates"], [])
        self.assertEqual(res["stats"]["sentences"], 4)

    def test_missing_main_point_and_unit_point_are_errors(self):
        text = PLAN.replace("- 핵심 주제:", "- 주제:").replace("- 전할 내용: 배치 크기를 줄인 뒤 무효화 지연이 줄었다.\n", "")
        res = P.check(P.parse_plan(text))
        self.assertEqual(len(res["errors"]), 2)
        self.assertIn("핵심 주제", res["errors"][0])
        self.assertIn("단위 1", res["errors"][1])

    def test_keyword_line_line_without_source_and_offtopic_unit_are_candidates(self):
        text = PLAN.replace("1. [현상] 배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였다. (사실 3)",
                            "1. [현상] 재전송 비율")
        text = text.replace("## 제외한 사실", "## 단위 3. 연구팀\n- 형태: 문단\n- 전할 내용: 연구팀은 2019년에 설립됐다.\n\n"
                            "1. [배경] 연구팀은 2019년에 설립됐다.\n\n## 제외한 사실")
        kinds = [c["kind"] for c in P.check(P.parse_plan(text))["candidates"]]
        self.assertIn("서술어로 끝나지 않은 계획 문장", kinds)
        self.assertIn("근거가 없는 계획 문장", kinds)
        self.assertIn("핵심 주제와 겹치는 단어가 없는 단위", kinds)

    def test_sentence_planned_in_two_later_units_is_a_candidate(self):
        """The opening unit states the result that the later units explain, and two sentences with the same words
        but different values are two facts. In the 0.7.0 runs both were printed as sentences planned twice."""
        unit3 = ("## 단위 3. 남은 문제\n- 형태: 문단\n- 전할 내용: 배치 크기가 10인 설정에서도 재전송이 남았다.\n\n"
                 "{}\n\n## 제외한 사실")
        same = "1. [현상] 배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였다. (사실 3)"
        kinds = [c["kind"] for c in P.check(P.parse_plan(PLAN.replace("## 제외한 사실", unit3.format(same))))["candidates"]]
        self.assertEqual(kinds, ["두 단위에 겹치는 계획 문장"])
        other_value = "1. [현상] 배치 크기가 10이던 설정에서는 재전송이 전체 전송의 3%였다. (사실 5)"
        res = P.check(P.parse_plan(PLAN.replace("## 제외한 사실", unit3.format(other_value))))
        self.assertEqual(res["candidates"], [])
        opening = "1. [결과] 쓰기 비율이 30% 미만인 서비스 12개에서 p99 무효화 지연이 4.2초에서 0.8초로 줄었다. (사실 1)"
        kinds = [c["kind"] for c in P.check(P.parse_plan(PLAN.replace("## 제외한 사실", unit3.format(opening))))["candidates"]]
        self.assertNotIn("두 단위에 겹치는 계획 문장", kinds)

    def test_fact_sheet_numbers_are_matched_with_the_plan(self):
        facts = "# fact sheet\n\n| 항목 | 값 |\n|---|---|\n| p99 무효화 지연 | 4.2초에서 0.8초 |\n| 재시도 간격 | 250ms |\n"
        res = P.check(P.parse_plan(PLAN), facts)
        self.assertIn("250ms", res["numbers"]["unassigned"])
        self.assertNotIn("4.2초", " ".join(res["numbers"]["unassigned"]))
        self.assertTrue(any(n.startswith("18") for n in res["numbers"]["unknown"]))   # 18% is not in this fact sheet

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "a.plan.md")
            bad = os.path.join(tmp, "b.plan.md")
            write(good, PLAN)
            write(bad, "# 설계\n\n- 핵심 주제: 무엇이 바뀌었는지 독자가 알게 된다.\n")
            run = lambda *a: subprocess.run([sys.executable, os.path.join(SCRIPTS, "plan_ko.py"), *a],  # noqa: E731
                                            capture_output=True, text=True, encoding="utf-8")
            p = run("check", good)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("write plan | a.plan.md | 단위 2개", p.stdout)
            self.assertEqual(run("check", bad).returncode, 1)
            self.assertEqual(run("check", os.path.join(tmp, "none.plan.md")).returncode, 2)


class PlanCompareTest(unittest.TestCase):
    def test_article_that_follows_the_plan_has_nothing_to_report(self):
        res = P.compare(P.parse_plan(PLAN), ARTICLE)
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["unplanned"], [])
        self.assertEqual(res["lost_numbers"], [])

    def test_dropped_number_and_dropped_sentence_are_reported(self):
        text = ARTICLE.replace("재전송이 전체 전송의 18%였습니다", "재전송이 많았습니다")
        text = text.replace(" 김 등(2025)이 무효화 메시지의 배치 크기를 100에서 10으로 줄인 결과입니다.", "")
        res = P.compare(P.parse_plan(PLAN), text)
        self.assertIn("18%", [n["value"] for n in res["lost_numbers"]])
        self.assertEqual([m["id"] for m in res["missing"]], ["2"])

    def test_sentence_outside_the_plan_is_reported(self):
        text = ARTICLE.rstrip("\n") + " 이 연구는 학계에서 큰 주목을 받았습니다.\n"
        res = P.compare(P.parse_plan(PLAN), text)
        self.assertEqual(len(res["unplanned"]), 1)
        self.assertIn("주목", res["unplanned"][0]["text"])
        out = P.render_compare(res)
        self.assertIn("설계에 대응하는 문장이 없는 글의 문장 1개", out)


class CheckWithPlanTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "note.md")
        write(self.path, ARTICLE)
        write(os.path.join(self.dir, "note.plan.md"), PLAN)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_check(self, *args):
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_ko.py"), self.path, *args],
                           capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def test_first_run_prints_the_plan_comparison(self):
        _, out = self.run_check()
        self.assertIn("설계 대조: 설계는 단위 2개", out)
        self.assertIn("설계의 문장과 글의 문장이 모두 대응한다", out)

    def test_later_run_lists_unplanned_sentences_only_in_changed_lines(self):
        self.run_check()
        text = ARTICLE.rstrip("\n") + " 이 연구는 학계에서 큰 주목을 받았습니다.\n"
        write(self.path, text)
        _, out = self.run_check()
        self.assertIn("설계에 대응하는 문장이 없는 글의 문장 1개", out)
        _, out = self.run_check()       # nothing changed since the last run
        self.assertNotIn("설계에 대응하는 문장이 없는 글의 문장", out)

    def test_default_draft_uses_the_same_plan_file(self):
        self.assertEqual(P.plan_path("/tmp/note.draft.md"), "/tmp/note.plan.md")
        self.assertEqual(P.plan_path("/tmp/note.md"), "/tmp/note.plan.md")

    def test_without_plan_file_nothing_is_compared(self):
        os.remove(os.path.join(self.dir, "note.plan.md"))
        _, out = self.run_check()
        self.assertNotIn("설계 대조", out)


FACTS = """# fact sheet

- 핵심 주제: 무효화 메시지의 배치 크기를 100에서 10으로 줄이자 p99 무효화 지연이 4.2초에서 0.8초로 줄었다.
- 분량: 한 문단

| 사실 | 값과 조건 |
|---|---|
| 무효화 지연이 줄었다 | p99 4.2초에서 0.8초, 배치 크기 100에서 10 |
| 재전송 비율 | 18% |
| 처리량이 떨어졌다 | 쓰기 비율 30% 이상에서 15% |

## 핵심 요소

### 1차: 자료 전체 (요소 6개)
1. [결론] 무효화 메시지의 배치 크기를 100에서 10으로 줄이자 p99 무효화 지연이 4.2초에서 0.8초로 줄었다. | 키워드: 배치 크기, p99 무효화 지연, 4.2초, 0.8초 | 사실 1
2. [원인] 배치 안의 메시지 하나가 실패하면 캐시 노드는 그 배치의 메시지 100개를 모두 다시 받는다. | 키워드: 메시지 100개 | 사실 1
3. [근거] 배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였다. | 키워드: 재전송, 18% | 사실 2
4. [한계] 쓰기 비율이 30% 이상인 서비스에서는 처리량이 15% 떨어졌다. | 키워드: 쓰기 비율, 30%, 처리량, 15% | 사실 3
5. [한계] 실험은 서비스 12개에서만 했다. | 키워드: 서비스 12개 | 사실 1
6. [방법] 김 등(2025)은 운영 로그로 지연을 측정했다. | 키워드: 운영 로그 | 사실 1

### 2차: 한 문단 (요소 3개)
1. [결론] 무효화 메시지의 배치 크기를 100에서 10으로 줄이자 p99 무효화 지연이 4.2초에서 0.8초로 줄었다. | 키워드: 배치 크기, p99 무효화 지연, 4.2초, 0.8초 | 1차 1
2. [원인] 배치가 100이면 메시지 하나가 실패했을 때 100개를 모두 다시 받아 재전송이 전체 전송의 18%였다. | 키워드: 재전송, 18% | 1차 2+3
3. [한계] 쓰기 비율이 30% 이상인 서비스에서는 처리량이 15% 떨어졌다. | 키워드: 쓰기 비율, 30%, 처리량, 15% | 1차 4
- 제외: 1차 5, 6(실험 범위와 측정 방법은 결론을 바꾸지 않는다)

## 원문

본문
"""

SUMMARY = ("무효화 메시지의 배치 크기를 100에서 10으로 줄이자 p99 무효화 지연이 4.2초에서 0.8초로 줄었습니다. 배치 크기가 100일 "
           "때는 메시지 하나가 실패하면 100개를 모두 다시 받아 재전송이 전체 전송의 18%였습니다. 다만 쓰기 비율이 30% 이상인 "
           "서비스에서는 처리량이 15% 떨어졌습니다.\n")


class KeyElementsTest(unittest.TestCase):
    def test_parse_reads_rounds_keywords_and_dropped_elements(self):
        rounds = P.parse_elements(FACTS)
        self.assertEqual([(r["n"], len(r["elements"])) for r in rounds], [(1, 6), (2, 3)])
        self.assertEqual(rounds[0]["elements"][0]["keywords"], ["배치 크기", "p99 무효화 지연", "4.2초", "0.8초"])
        self.assertEqual(rounds[1]["elements"][1]["source"], "1차 2+3")
        self.assertEqual(len(rounds[1]["dropped"]), 1)
        self.assertEqual(P.parse_elements("# fact sheet\n\n| 사실 |\n|---|\n| 값 |\n"), [])
        # the section ends at the next heading of the same level
        self.assertNotIn("본문", [e["text"] for r in rounds for e in r["elements"]])

    def test_complete_elements_have_no_candidate(self):
        self.assertEqual(P.check_elements(P.parse_elements(FACTS)), [])

    def test_element_without_keywords_or_predicate_and_skipped_round_are_candidates(self):
        facts = FACTS.replace("5. [한계] 실험은 서비스 12개에서만 했다. | 키워드: 서비스 12개 | 사실 1", "5. [한계] 실험 범위")
        facts = facts.replace("| 키워드: 재전송, 18% | 1차 2+3", "| 키워드: 재전송, 18%, 캐시 노드 | 1차 2+3")
        facts = facts.replace("3. [한계] 쓰기 비율이 30% 이상인 서비스에서는 처리량이 15% 떨어졌다. | 키워드: 쓰기 비율, 30%, 처리량, 15% | 1차 4\n", "")
        kinds = [c["kind"] for c in P.check_elements(P.parse_elements(facts), limit=1)]
        self.assertIn("문장이 아닌 핵심 요소", kinds)
        self.assertIn("키워드가 없는 핵심 요소", kinds)
        self.assertIn("요소의 내용에 없는 키워드", kinds)                  # "캐시 노드" is not in the merged element
        self.assertIn("한 차수에서 절반 넘게 줄인 핵심 요소", kinds)        # 6 elements to 2
        self.assertIn("분량에 담을 수보다 많은 마지막 차수", kinds)        # 2 elements, room for 1

    def test_kept_elements_are_copied_and_paragraph_lines_are_read(self):
        # "= 1차 N" keeps an element as it is; "문단 N:" groups the last round of a text of several paragraphs.
        facts = FACTS.split("### 2차")[0] + (
            "### 2차: 자세히 (요소 4개)\n"
            "문단 1: 배치 크기를 줄이자 무효화 지연이 줄었다.\n"
            "1. = 1차 1\n"
            "2. [원인] 배치가 100이면 메시지 하나가 실패했을 때 100개를 모두 다시 받아 재전송이 전체 전송의 18%였다. "
            "| 키워드: 재전송, 18% | 1차 2+3\n"
            "문단 2: 결과의 한계\n"
            "3. = 1차 4\n"
            "4. = 1차 9\n"
            "- 제외: 1차 5, 6(실험 범위와 측정 방법은 결론을 바꾸지 않는다)\n")
        rounds = P.parse_elements(facts)
        last = rounds[-1]
        self.assertEqual([e["text"] for e in last["elements"]][0], rounds[0]["elements"][0]["text"])
        self.assertEqual(last["elements"][0]["keywords"], ["배치 크기", "p99 무효화 지연", "4.2초", "0.8초"])
        self.assertEqual([(e["id"], e["para"], e["source"]) for e in last["elements"]],
                         [("1", 1, "1차 1"), ("2", 1, "1차 2+3"), ("3", 2, "1차 4"), ("4", 2, "1차 9")])
        self.assertEqual([q["point"] for q in last["paras"]], ["배치 크기를 줄이자 무효화 지연이 줄었다.", "결과의 한계"])
        kinds = [c["kind"] for c in P.check_elements(rounds)]
        self.assertEqual(sorted(kinds), ["문장이 아닌 문단의 전할 내용", "앞 차수에 없는 요소"])
        # a paragraph line that joins two points, a paragraph of more than five elements, an element over 130 characters
        joined = facts.replace("문단 2: 결과의 한계", "문단 2: 처리량이 떨어졌고, 실험은 서비스 12개에서만 했다.")
        joined = joined.replace("4. = 1차 9\n", "4. = 1차 5\n5. = 1차 6\n6. = 1차 2\n7. = 1차 3\n8. = 1차 1\n")
        long = ("9. [근거] " + "배치 크기가 100이던 설정에서는 재전송이 전체 전송의 18%였고 " * 4 + "지연이 늘었다. | 키워드: 18% | 사실 2\n")
        joined = joined.replace("- 제외: 1차 5, 6(실험 범위와 측정 방법은 결론을 바꾸지 않는다)\n", long)
        kinds = [c["kind"] for c in P.check_elements(P.parse_elements(joined))]
        self.assertEqual(sorted(kinds), ["두 내용을 이은 문단의 전할 내용", "여러 내용을 담은 핵심 요소", "요소가 많은 문단"])
        out = P.render_element_check("note.facts.md", rounds, P.check_elements(rounds))
        self.assertIn("  문단 1: 배치 크기를 줄이자 무효화 지연이 줄었다.", out)
        self.assertIn("  1. [결론] 무효화 메시지의 배치 크기를 100에서 10으로 줄이자", out)       # the reference is filled in
        self.assertIn("  3. [한계] 쓰기 비율이 30% 이상인 서비스에서는 처리량이 15% 떨어졌다.", out)
        # the keywords of a kept element are looked up in the article like the others
        res = P.compare_elements(rounds, SUMMARY.replace("처리량이 15% 떨어졌습니다", "성능이 떨어졌습니다"))
        self.assertEqual([(m["id"], m["keywords"]) for m in res["missing"]], [("3", ["처리량", "15%"])])

    def test_keywords_of_the_last_round_are_looked_up_in_the_article(self):
        rounds = P.parse_elements(FACTS)
        res = P.compare_elements(rounds, SUMMARY)
        self.assertEqual((res["round"], res["elements"], res["keywords"], res["missing"]), (2, 3, 10, []))
        self.assertIn("키워드 10개가 글에 모두 있다", P.render_elements(res))
        self.assertEqual(P.render_elements(res, before=res), "")
        res = P.compare_elements(rounds, SUMMARY.replace("처리량이 15% 떨어졌습니다", "성능이 떨어졌습니다"))
        self.assertEqual([(m["id"], m["keywords"]) for m in res["missing"]], [("3", ["처리량", "15%"])])
        self.assertIn("2개를 글에서 찾지 못했다", P.render_elements(res))
        self.assertEqual(P.render_elements(res, before=res), "")           # nothing more was lost since the last check
        full = P.compare_elements(rounds, SUMMARY)
        self.assertIn("지난 검사 뒤에 글에서 빠진 키워드 2개", P.render_elements(res, before=full))
        # spaces, emphasis marks, and thousands separators do not hide a keyword
        self.assertIn(P.squash("p99 무효화 지연"), P.squash("**p99  무효화 지연**은 1,200건"))
        self.assertIn("1200건", P.squash("1,200건"))
        self.assertIsNone(P.compare_elements([], SUMMARY))

    def test_plan_check_reports_keywords_of_the_last_round_that_the_plan_lost(self):
        res = P.check(P.parse_plan(PLAN), FACTS)
        lost = [c for c in res["candidates"] if c["kind"] == "설계에 없는 핵심 요소의 키워드"]
        self.assertEqual(len(lost), 1)                                      # the plan has no line on the throughput
        self.assertIn("처리량", lost[0]["text"])

    def test_cli_and_check_ko_print_the_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            facts, article = os.path.join(tmp, "note.facts.md"), os.path.join(tmp, "note.draft.md")
            write(facts, FACTS)
            write(article, SUMMARY.replace("처리량이 15% 떨어졌습니다", "성능이 떨어졌습니다"))
            run = lambda script, *a: subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *a],  # noqa: E731
                                                    capture_output=True, text=True, encoding="utf-8")
            p = run("plan_ko.py", "elements", facts, "--max", "5")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("write elements | note.facts.md | 1차 6개 → 2차 3개", p.stdout)
            self.assertIn("점검 후보가 없다", p.stdout)
            self.assertIn("분량에 담을 수보다 많은 마지막 차수", run("plan_ko.py", "elements", facts, "--max", "2").stdout)
            write(os.path.join(tmp, "empty.facts.md"), "# fact sheet\n")
            self.assertEqual(run("plan_ko.py", "elements", os.path.join(tmp, "empty.facts.md")).returncode, 1)
            out = run("check_ko.py", article).stdout                     # the draft uses note.facts.md
            self.assertIn("핵심 요소 대조: 마지막 차수(2차)", out)
            self.assertIn("처리량, 15%", out)
            write(article, SUMMARY.replace("처리량이 15% 떨어졌습니다", "성능이 크게 떨어졌습니다"))
            out = run("check_ko.py", article).stdout                     # still missing, but not lost by this edit
            self.assertNotIn("핵심 요소 대조", out)
            write(article, SUMMARY.replace("재전송이 전체 전송의 18%였습니다", "재전송이 많았습니다"))
            out = run("check_ko.py", article).stdout.split("핵심 요소 대조", 1)[1]
            self.assertIn("지난 검사 뒤에 글에서 빠진 키워드 1개", out)       # only the keyword that this edit removed
            self.assertIn("18%", out)


FLOW_PARAS = [
    "캐시 무효화는 원본 데이터가 바뀌었을 때 캐시에 남은 예전 값을 삭제하는 일입니다. 무효화가 늦어지면 사용자는 예전 값을 "
    "읽습니다. 그래서 무효화 지연은 캐시를 사용하는 서비스가 관리하는 지표입니다.",
    "무효화 메시지는 배치로 묶어 캐시 노드에 보냅니다. 배치가 크면 메시지 하나가 실패했을 때 배치 전체를 다시 보냅니다. "
    "재전송이 늘면 무효화 지연도 늘어납니다.",
    "김 등(2025)은 배치 크기를 100에서 10으로 줄였습니다. 이 설정에서 무효화 지연은 4.2초에서 0.8초로 줄었습니다. "
    "재전송 비율도 18%에서 3%로 낮아졌습니다.",
]


def flow_of(paras, title="캐시 무효화 지연"):
    an = L.analyze(f"# {title}\n\n" + "\n\n".join(paras) + "\n")
    return an["metrics"]


class FlowLintTest(unittest.TestCase):
    def test_linked_sentences_are_not_flagged(self):
        m = flow_of(FLOW_PARAS)
        self.assertEqual(m["A23.unlinked"]["value"], 0)
        self.assertEqual(m["A23.offtopic_para"]["value"], 0)
        self.assertGreaterEqual(m["A23.topic_cover"]["value"], 0.8)
        self.assertIn("무효화", m["A23.topic_cover"]["extra"]["topic_words"])

    def test_sentence_without_link_is_a_candidate_with_the_previous_sentence(self):
        paras = list(FLOW_PARAS)
        paras[1] = paras[1] + " 스킬은 세 가지입니다."
        hits = flow_of(paras)["A23.unlinked"]["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["text"], "스킬은 세 가지입니다.")
        self.assertEqual(hits[0]["match"], "주제어 없음")
        self.assertTrue(hits[0]["previous"]["text"].startswith("재전송이 늘면"))

    def test_openers_and_reason_endings_count_as_links(self):
        for sentence in ("그러나 운영 비용은 다른 문제입니다.", "이 방식은 운영 비용이 듭니다.",
                         "운영자가 값을 직접 정했기 때문입니다."):
            paras = list(FLOW_PARAS)
            paras[1] = paras[1] + " " + sentence
            with self.subTest(sentence=sentence):
                self.assertEqual(flow_of(paras)["A23.unlinked"]["value"], 0)

    def test_paragraph_without_topic_word_is_a_candidate(self):
        paras = FLOW_PARAS + ["연구팀은 2019년에 설립됐습니다. 구성원은 열두 명입니다."]
        m = flow_of(paras)
        self.assertEqual(m["A23.offtopic_para"]["value"], 1)
        self.assertTrue(m["A23.offtopic_para"]["hits"][0]["text"].startswith("연구팀은"))

    def test_short_text_is_not_measured(self):
        m = flow_of(FLOW_PARAS[:1])
        self.assertEqual(m["A23.unlinked"]["value"], 0)
        self.assertEqual(m["A23.topic_cover"]["value"], 0)

    def test_noun_run(self):
        self.assertEqual(L.noun_run("캐시 무효화 지연 원인을 분석했습니다."), ["캐시", "무효화", "지연", "원인을"])
        self.assertEqual(L.noun_run("자동완성 API 응답 캐시 만료 시간을 늘렸습니다.")[-1], "시간을")
        for natural in ("캐시 무효화가 늦어지는 원인을 분석했습니다.", "사람이 쓴 기술 블로그 글과 비교했습니다.",
                        "공백 제외 500자 안팎으로 씁니다.", "문장 부호 사용 등을 다룹니다."):
            with self.subTest(sentence=natural):
                self.assertLess(len(L.noun_run(natural)), L.NOUN_RUN_MIN)
        m = flow_of(FLOW_PARAS + ["캐시 무효화 지연 원인 분석 결과를 팀에 공유했습니다. 무효화 지연은 다음 분기에도 측정합니다."])
        self.assertEqual(m["A24.noun_run"]["value"], 1)

    def test_new_items_are_candidates_or_reference_values(self):
        th = L.load_thresholds()
        kinds = {mid: th["metrics"][mid]["kind"] for mid in th["metrics"] if mid.startswith(("A23.", "A24."))}
        self.assertEqual(kinds, {"A23.unlinked": "check", "A23.unlinked_share": "info", "A23.offtopic_para": "check",
                                 "A23.topic_cover": "info", "A24.noun_run": "check"})
        paras = list(FLOW_PARAS)
        paras[1] = paras[1] + " 스킬은 세 가지입니다."
        text = "# 캐시 무효화 지연\n\n" + "\n\n".join(paras) + "\n"
        an = L.analyze(text)
        out = L.render_text("a.md", "default", an, L.evaluate(an, th, "default"))
        self.assertIn("문장 연결과 주제 점검 후보", out)
        self.assertIn("앞 문장 L5", out)


if __name__ == "__main__":
    unittest.main()
