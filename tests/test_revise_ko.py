import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "techblog", "scripts")
sys.path.insert(0, SCRIPTS)

import revise_ko as R  # noqa: E402


TABLE_ARTICLE = """# 토큰 버킷으로 바꾼 rate limiter

## 롤아웃 전후 지표

롤아웃 전과 후의 지표는 아래 표와 같습니다.

| 지표 | 롤아웃 전 | 롤아웃 후 |
|---|---|---|
| p99 지연 | 1,850ms | 420ms |
| 거절 비율 | 2.1% | 2.6% |

거절 비율은 0.5%p 올랐습니다. Redis CPU 사용량은 8%p 늘었습니다.

p99 무효화 지연은 4.2초에서 0.8초로 줄었습니다. vLLM의 처리량은 Orca의 1.67배였습니다.

burst 때문에 gateway의 p99 latency가 1,850ms까지 올랐습니다.
"""

BASELINE_ARTICLE = """# LLM 응답으로 모델 계열 맞히기

## 분류 정확도

GPT 계열 응답의 5-way 분류 정확도는 무작위 추측 정확도 20%보다 65.5%p 높았습니다. Claude 계열은 무작위 추측 정확도 20%보다 70.1%p 높았습니다.

Gemini 계열의 분류 정확도도 무작위 추측 정확도 20%보다 60.2%p 높았습니다.

## 서빙 처리량

vLLM의 처리량은 Orca (Oracle)보다 높았습니다. 긴 프롬프트에서도 vLLM은 Orca (Oracle)보다 높았습니다.

짧은 프롬프트에서도 Orca (Oracle)보다 높았습니다. beam search에서도 Orca (Oracle)보다 높았습니다.
"""

FRAME_ARTICLE = """# 저자들의 해석

## 해석

저자들은 지연 대부분이 배치 대기에서 생긴다고 봅니다. 저자들은 처리량 손실이 쓰기 비율에 따라 커진다고 봅니다.

이 측정은 12개 서비스에서 했습니다. 저자들은 write-through 캐시에서도 같은 경향이 나올 수 있다고 봅니다.

## 동작

vLLM은 KV cache를 고정 크기의 블록 단위로 나눠서 GPU 메모리에 둡니다. vLLM은 블록 테이블로 요청마다 논리 블록과 물리 블록을 잇습니다. vLLM은 요청이 토큰을 생성해서 블록이 찰 때만 새 블록을 할당합니다.

블록 크기는 16입니다. 블록은 고정 크기입니다. 표는 GPU에 있습니다. 매핑은 CPU가 합니다.
"""


class TestHelpers(unittest.TestCase):
    def test_strip_particle(self):
        self.assertEqual(R.strip_particle("정확도는"), "정확도")
        self.assertEqual(R.strip_particle("20%보다"), "20%")
        self.assertEqual(R.strip_particle("차이"), "차이")  # removing the particle would leave one character
        self.assertEqual(R.strip_particle("서버에서는"), "서버")

    def test_paths(self):
        self.assertEqual(R.stem_of(os.path.join("x", "a.draft.md")), os.path.join("x", "a"))
        self.assertEqual(R.snapshot_path("a.md"), "a.unrevised.md")
        self.assertEqual(R.snapshot_path("a.draft.md"), "a.unrevised.md")
        self.assertEqual(R.facts_path("a.draft.md"), "a.facts.md")
        self.assertEqual(R.repeats_path("a.draft.md"), "a.repeats.md")
        self.assertEqual(R.mark_path("a.draft.md"), "a.pre-fix.md")


class TestRepeats(unittest.TestCase):
    def ids(self, text, rid):
        return [c for c in R.find_repeats(text)["candidates"] if c["id"] == rid]

    def test_r7_keeps_adjacent_context_and_paragraph_boundaries(self):
        text = "첫 이유를 듭니다. 다른 이유도 듭니다.\n\n새 이유를 듭니다."
        candidates = self.ids(text, "R7")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["predicate"], "듭니다")
        self.assertEqual(candidates[0]["previous"]["text"], "첫 이유를 듭니다.")
        self.assertIn("다른 이유도 듭니다.", R.render_repeats("a.md", R.find_repeats(text)))

    def test_check_exposes_untruncated_review_candidates(self):
        text = "연구팀은 첫 이유를 듭니다. 연구팀은 다른 이유도 듭니다."
        result = R.compare(text, text)
        self.assertEqual(len(result["predicate_candidates"]), 1)
        self.assertNotIn("A8.same_predicate_adjacent", [r["id"] for r in result["gate_fail"]])
        self.assertIn("자동 수정 아님", R.render_check("a.unrevised.md", "a.md", result))

    def test_r6_change_without_baseline(self):
        texts = [c["text"] for c in self.ids(TABLE_ARTICLE, "R6")]
        self.assertIn("거절 비율은 0.5%p 올랐습니다.", texts)
        self.assertIn("Redis CPU 사용량은 8%p 늘었습니다.", texts)
        after = [c for c in self.ids(TABLE_ARTICLE, "R6") if c["text"].startswith("거절")][0]
        self.assertTrue(after["after"])  # right after the table
        self.assertNotIn("p99 무효화 지연은 4.2초에서 0.8초로 줄었습니다.", texts)
        self.assertNotIn("vLLM의 처리량은 Orca의 1.67배였습니다.", texts)
        self.assertFalse(any("1,850ms까지" in t for t in texts))  # the value after the change

    def test_r1_numeric_baseline(self):
        r1 = self.ids(BASELINE_ARTICLE, "R1")
        self.assertEqual(len(r1), 1)
        self.assertEqual(r1[0]["key"], "추측 정확도 20%")
        self.assertEqual(r1[0]["count"], 3)
        self.assertEqual(r1[0]["adjacent"], 2)

    def test_r1_ignores_named_baseline(self):
        self.assertFalse(any("oracle" in c["key"] for c in self.ids(BASELINE_ARTICLE, "R1")))

    def test_r4_frame(self):
        labels = [c["label"] for c in self.ids(FRAME_ARTICLE, "R4")]
        self.assertTrue(any("저자들은 … 봅니다" in x for x in labels), labels)

    def test_r3_same_subject(self):
        r3 = self.ids(FRAME_ARTICLE, "R3")
        self.assertTrue(any("vLLM은" in c["label"] and c["count"] == 3 for c in r3), r3)

    def test_r5_short_run(self):
        r5 = self.ids(FRAME_ARTICLE, "R5")
        self.assertTrue(any(c["count"] == 4 for c in r5), r5)

    def test_render_limits_lines(self):
        res = {"sentences": 10, "candidates": [{"id": "R5", "item": 3, "lines": [i], "label": "x", "text": "y"}
                                               for i in range(12)]}
        out = R.render_repeats("a.md", res)
        self.assertEqual(sum(1 for line in out.splitlines() if line.startswith("[R5]")), R.MAX_LINES)
        self.assertIn("+4개", out)


DRAFT = """# 토큰 버킷으로 바꾼 rate limiter

## 배경

공개 API는 클라이언트마다 60초 윈도에 600건을 허용했습니다. 윈도가 열리는 첫 1초에 최대 4,800 requests/s가 몰렸습니다.

## 결과

Redis CPU 사용량은 롤아웃 전보다 8%p 늘었습니다. 거절 비율은 2.1%에서 2.6%로 올랐습니다.
"""

FACTS = "600건, 60초, 첫 1초, 4,800 requests/s, 8 percentage points, 2.1%, 2.6%, 1,850 ms, 420 ms\n"


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "revise_ko.py")] + list(args), capture_output=True,
                           env=env)
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.art = os.path.join(self.tmp.name, "article.md")
        with open(self.art, "w", encoding="utf-8") as f:
            f.write(DRAFT)
        with open(os.path.join(self.tmp.name, "article.facts.md"), "w", encoding="utf-8") as f:
            f.write(FACTS)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.art, "w", encoding="utf-8") as f:
            f.write(text)

    def test_start_refuses_overwrite(self):
        code, out, _ = self.run_cli("start", self.art)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "article.unrevised.md")))
        with open(os.path.join(self.tmp.name, "article.repeats.md"), encoding="utf-8") as f:
            self.assertIn("techblog repeats", f.read())
        code, _, err = self.run_cli("start", self.art)
        self.assertEqual(code, 2)
        self.assertIn("--force", err)
        self.assertEqual(self.run_cli("start", self.art, "--force")[0], 0)

    def test_check_requires_snapshot(self):
        code, _, err = self.run_cli("check", self.art)
        self.assertEqual(code, 2)
        self.assertIn("start", err)

    def test_check_reports_lost_and_new_numbers(self):
        self.run_cli("start", self.art)
        self.write(DRAFT.replace(" Redis CPU 사용량은 롤아웃 전보다 8%p 늘었습니다.", "")
                   .replace("Redis CPU 사용량은 롤아웃 전보다 8%p 늘었습니다. ", "")
                   + "\np99 지연은 1,850ms에서 420ms로 줄었고 평균 지연은 120ms였습니다.\n")
        code, out, _ = self.run_cli("check", self.art, "--json")
        res = json.loads(out)
        self.assertIn("8", [x["value"] for x in res["lost_numbers"]])
        new = {x["value"]: x["in_facts"] for x in res["new_numbers"]}
        self.assertTrue(new["1850"])
        self.assertFalse(new["120"])
        self.assertEqual(code, 1)  # 120ms, not in the fact sheet, is an A15 FAIL

    def test_check_flags_ai_pattern_and_long_sentence(self):
        self.run_cli("start", self.art)
        self.write(DRAFT + "\n이 설계는 단순한 rate limiter를 넘어 트래픽을 고르게 만드는 장치이고 요청을 나누며 재시도를 늦추고 "
                           "부하를 줄입니다.\n")
        code, out, _ = self.run_cli("check", self.art)
        self.assertEqual(code, 1)
        self.assertIn("G8.beyond_simple", out)
        self.assertIn("연결어미가 3개 이상인 새 문장 1개", out)

    def test_check_passes_clean_edit(self):
        self.run_cli("start", self.art)
        self.write(DRAFT.replace("Redis CPU 사용량은 롤아웃 전보다 8%p 늘었습니다.", "Redis CPU 사용량은 8%p 늘었습니다."))
        code, out, _ = self.run_cli("check", self.art)
        self.assertEqual(code, 0, out)
        self.assertIn("1문장 수정하거나 삭제", out)
        self.assertIn("판정: 수정할 항목 없음", out)

    def test_rejects_work_file_argument(self):
        code, _, err = self.run_cli("repeats", os.path.join(self.tmp.name, "article.facts.md"))
        self.assertEqual(code, 2)
        code, _, err = self.run_cli("audit", os.path.join(self.tmp.name, "article.pre-fix.md"))
        self.assertEqual(code, 2)

    def test_mark_and_audit(self):
        code, _, err = self.run_cli("audit", self.art)
        self.assertEqual(code, 2)
        self.assertIn("mark", err)
        self.assertEqual(self.run_cli("mark", self.art)[0], 0)
        mark = os.path.join(self.tmp.name, "article.pre-fix.md")
        self.assertTrue(os.path.exists(mark))
        self.write(DRAFT.replace("거절 비율은 2.1%에서 2.6%로 올랐습니다.",
                                 "이때 거절 비율은 2.1%에서 2.6%로 올라서 재시도도 늘었습니다."))
        code, out, _ = self.run_cli("audit", self.art)
        self.assertIn("article.pre-fix.md", out.splitlines()[0])  # the copy made by mark is the default comparison target
        self.assertIn("지시어: «이때»", out)
        self.assertIn("이유·목적: «올라서»", out)
        self.assertIn("수치 2.1%", out)
        self.assertIn("fact sheet 1줄", out)
        dest = os.path.join(self.tmp.name, "audit.txt")
        code, out, _ = self.run_cli("audit", self.art, "--out", dest)
        self.assertIn("바뀌거나 새로 쓴 단위 1개", out)
        with open(dest, encoding="utf-8") as f:
            self.assertIn("techblog audit", f.read())
        self.assertEqual(self.run_cli("audit", self.art, "--out", self.art)[0], 2)
        # Restarting post-processing deletes the previous pre-fix copy, so audit compares against the draft copy.
        self.assertEqual(self.run_cli("start", self.art, "--force")[0], 0)
        self.assertFalse(os.path.exists(mark))
        code, out, _ = self.run_cli("audit", self.art)
        self.assertIn("article.unrevised.md", out.splitlines()[0])


class TestAudit(unittest.TestCase):
    def toks(self, s):
        return R.tokens(R.L.mask_quotes(s))

    def test_deictics(self):
        self.assertEqual(R.deictics_in(self.toks("이때 이 값은 기존 기준보다 컸습니다.")), ["이때", "이", "기존"])
        self.assertEqual(R.deictics_in(self.toks("글을 모은 뒤 600편을 측정했습니다.")), [])  # order of actions
        self.assertEqual(R.deictics_in(self.toks("앞 절에서 본 두 값을 비교합니다.")), ["앞", "두"])
        self.assertEqual(R.deictics_in(self.toks("프로그램 세 개와 결과는 다음과 같습니다.")), ["다음과"])
        self.assertEqual(R.deictics_in(self.toks("\"이번\" 같은 말은 세지 않습니다.")), [])  # inside quotes

    def test_causal_and_scope(self):
        toks = self.toks("측정한 글이 늘어서 기준치를 다시 계산했습니다.")
        self.assertEqual(R.causal_in(R.L.mask_quotes("측정한 글이 늘어서 기준치를 다시 계산했습니다."), toks), ["늘어서"])
        self.assertEqual(R.causal_in("기술 글이면서 길이가 긴 글에서 측정했습니다.",
                                     self.toks("기술 글이면서 길이가 긴 글에서 측정했습니다.")), [])
        self.assertEqual(R.scope_in(self.toks("같은 저자의 셋째 글부터처럼 모든 글을 뺐습니다.")), ["글부터처럼", "모든"])

    def test_coordinated_subjects(self):
        found = R.coordinated(self.toks("쉼표가 붙은 것의 비율과 지시어로 여는 문장의 수가 기준 기간 글보다 많았습니다."))
        self.assertEqual([(c["first"], c["head"], c["predicate"]) for c in found], [("비율과", "수가", "많았습니다")])
        self.assertEqual(R.coordinated(self.toks("측정 결과와 비교해 보면 차이가 컸습니다.")), [])  # "결과" is a noun

    def test_name_overlaps(self):
        text = ("AI 문체 연구가 지목한 항목(부정 대구, 굵은 글씨)의 기준치는 기준 기간 글로 계산합니다.\n\n"
                "수정 때문에 AI 문체 항목(분포가 아닌 자동 측정 항목)의 판정이 나빠지면 안 됩니다.\n\n"
                "AI 문체 연구가 지목한 항목(부정 대구, 굵은 글씨)은 위와 같습니다.\n")
        units = R.audit_units(text)
        found = R.name_overlaps(units, 0)
        self.assertEqual([x["line"] for x in found], [3])  # line 5, whose parenthetical text is the same, is excluded
        self.assertTrue(found[0]["other"].endswith("ai 문체 항목"), found)

    def test_leftover_wording_and_split(self):
        before = "## skill 본문\n\nskill 본문은 6,000바이트 이하입니다. 이 값은 시험이 확인합니다.\n"
        after = "## skill 본문\n\nSKILL.md는 6,000바이트 이하입니다. 이 값은 시험이 확인합니다.\n"
        res = R.audit(before, after)
        self.assertEqual(len(res["groups"]), 1)
        left = res["groups"][0]["leftover"]
        self.assertIn({"phrase": "skill 본문", "where": [{"line": 1, "kind": "헤딩"}]}, left)
        res = R.audit("검사는 600편을 측정한 뒤 기준치를 계산했고 holdout으로 확인했습니다.\n",
                      "검사는 600편을 측정한 뒤 기준치를 계산했습니다. holdout으로 확인했습니다.\n")
        items = res["groups"][0]["items"]
        self.assertEqual([it["split"] for it in items], [False, True])

    def test_numbers_and_fact_candidates(self):
        facts = ("- 측정 600편, 뺀 글 239편(자료 22~35줄 표)\n"
                 "- 이전 판은 README 239줄에 있다\n"
                 "- K-Writer 0.2.0에서 고쳤다\n")
        before = "사람 글을 모았습니다.\n\n측정한 글은 600편입니다.\n"
        after = "사람 글 239편을 뺐습니다. K-Writer 0.2.0의 측정입니다.\n\n측정한 글은 600편입니다.\n"
        res = R.audit(before, after, facts)
        items = [it for g in res["groups"] for it in g["items"]]
        first = items[0]
        self.assertEqual([(x["value"], x["facts"]) for x in first["numbers"]], [("239", [1])])  # the source location "239줄" is left out of the count
        self.assertEqual(first["facts"][0]["line"], 1)
        self.assertEqual(items[1]["numbers"], [])  # a version number is not a figure

    def test_object_verbs_and_list_items(self):
        s = "상위 agent는 검토 결과를 수정한 뒤 앞 문장, 다른 줄, 근거 후보 줄을 모아 목록을 만듭니다."
        u = R.audit_units(s + "\n")[0]
        pairs = [(o["object"], o["verb"]) for o in R.object_verbs(u["toks_main"])]
        self.assertIn(("검토 결과를", "수정한"), pairs)
        self.assertIn(("목록을", "만듭니다"), pairs)
        self.assertEqual(R.list_items(u["raw_main"]), 3)
        u = R.audit_units("값이 늘었고, 기준치를 다시 계산했습니다.\n")[0]
        self.assertEqual(R.list_items(u["raw_main"]), 0)  # one comma after a connective ending is not a list

    def test_first_mentions_and_section_refs(self):
        text = ("## 만든 방법\n\n기준치는 사람 글의 95%가 넘지 않는 값으로 정합니다. 이 값을 측정했습니다.\n\n"
                "## 결과\n\n기준치는 \"만든 방법\" 절의 가중치와 경계로 다시 측정한 값입니다.\n")
        units = R.audit_units(text)
        idx = next(i for i, u in enumerate(units) if "경계" in u["text"])
        self.assertEqual(R.first_mentions(units, idx), ["가중치", "경계"])  # "측정한" is the same word as the earlier "측정했습니다"
        refs = R.section_refs(units, idx)
        self.assertEqual(refs[0]["lines"], [1, 3])
        self.assertEqual(refs[0]["missing"], ["가중치", "경계"])
        units = R.audit_units("## 결과\n\n자세한 기록은 \"없는 절\" 절에 있습니다.\n")
        self.assertIsNone(R.section_refs(units, 1)[0]["lines"])

    def test_render_audit(self):
        res = R.audit("값은 3.2%였습니다.\n", "이 값은 3.2%였고 다른 서버보다 높았습니다.\n", "- 3.2%\n")
        out = R.render_audit("a.pre-fix.md", "a.md", res)
        self.assertIn("확인할 것(판정 아님)", out)
        self.assertIn("[1] 수정: 기준 L1의 1단위 → 1단위", out)
        self.assertIn("근거 후보 fact sheet 1줄", out)
        self.assertIn("lint: 기준", out)


if __name__ == "__main__":
    unittest.main()
