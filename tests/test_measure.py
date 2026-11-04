"""dev/baseline/techblog/measure.py의 사이트별 parser, 기간과 그룹, 번역 글 필터, 저자 키.

실제 블로그 글의 문장은 쓰지 않고 짧은 합성 응답만 쓴다.
"""
import importlib.util
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location("measure", os.path.join(ROOT, "dev", "baseline", "techblog", "measure.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class PeriodAndGroupTest(unittest.TestCase):
    def test_period_boundaries(self):
        self.assertEqual(M.period(""), "pre2018")
        self.assertEqual(M.period("2017-12-31"), "pre2018")
        self.assertEqual(M.period("2018-01-01"), "base")
        self.assertEqual(M.period("2022-11-30"), "base")
        self.assertEqual(M.period("2022-12-01"), "mid")
        self.assertEqual(M.period("2024-12-31"), "mid")
        self.assertEqual(M.period("2025-01-01"), "drift")

    def test_group_name(self):
        self.assertEqual(M.group_name("default", "base"), "default")
        self.assertEqual(M.group_name("casual", "base"), "casual")
        self.assertEqual(M.group_name("default", "mid"), "mid-default")
        self.assertEqual(M.group_name("casual", "drift"), "drift-casual")


class FilterTest(unittest.TestCase):
    def test_translation_marker_near_start_or_end(self):
        head = "# 제목\n\n이 글은 외부 사이트에 공개된 글을 번역한 것입니다.\n\n" + "본문 문장입니다. " * 400
        tail = "본문 문장입니다. " * 400 + "\n\n원문: https://example.com/post\n"
        self.assertTrue(M.is_translation(head))
        self.assertTrue(M.is_translation(tail))

    def test_no_translation_marker(self):
        body = "# 제목\n\n캐시를 두 단계로 나눈 이유를 정리합니다.\n\n" + "본문 문장입니다. " * 400
        self.assertFalse(M.is_translation(body))
        quoted = "# 제목\n\n인용한 글의 요지입니다.\n\n👉 원문 보기\n\n" + "본문 문장입니다. " * 400
        listed = "본문 문장입니다. " * 400 + "\n\n- 각 문장을 확인할 수 있는 원문 링크와 인용\n"
        self.assertFalse(M.is_translation(quoted))
        self.assertFalse(M.is_translation(listed))

    def test_new_non_tech_titles(self):
        for title in ("DEVIEW 2020 세션 안내", "우아콘 2023 후기", "우아한테크코스 수료 이야기", "세미나 다시보기"):
            self.assertFalse(M.is_tech({"site": "woowahan", "title": title, "tags": []}), title)
        self.assertTrue(M.is_tech({"site": "d2", "title": "로그 수집 파이프라인 개선", "tags": []}))

    def test_skip_reason_needs_prose_paragraphs(self):
        entry = {"site": "kakao", "title": "로그 수집 파이프라인 개선", "tags": []}
        text = "본문 문장입니다. " * 300
        st = {"chars": 3000, "sentences": 60, "paragraphs": 12}
        self.assertIsNone(M.skip_reason(entry, text, st, "default", "base"))
        listed = dict(st, paragraphs=0)
        self.assertIn("산문 문단", M.skip_reason(entry, text, listed, "default", "base"))
        self.assertIn("어투 혼용", M.skip_reason(entry, text, st, "mixed", "base"))
        self.assertIn("2018년 이전", M.skip_reason(entry, text, st, "default", "pre2018"))

    def test_author_key(self):
        self.assertEqual(M.author_key({"site": "kakao", "author": "김가,이나"}), "김가")
        self.assertEqual(M.author_key({"site": "d2", "author": 471}), "471")
        self.assertEqual(M.author_key({"site": "woowahan", "author": "85"}), "")
        self.assertEqual(M.author_key({"site": "clova", "author": "clova-admin"}), "")


class ConverterTest(unittest.TestCase):
    def test_font_size_paragraph_becomes_heading(self):
        frag = ('<p><strong><span style="font-size: 24px;">첫 절 제목</span></strong></p>'
                '<p>본문에서 <strong>강조한 말</strong>입니다.</p>'
                '<p><span style="font-size: 14px;">작은 글씨 문단입니다.</span></p>')
        md = M.html_to_md(frag)
        self.assertIn("## 첫 절 제목", md)
        self.assertIn("**강조한 말**", md)
        self.assertNotIn("## 작은 글씨", md)

    def test_h_tags_unchanged(self):
        self.assertIn("## 소제목", M.html_to_md("<h2>소제목</h2><p>문단입니다.</p>"))


class ParserTest(unittest.TestCase):
    def test_kakao_sitemap(self):
        raw = ("<urlset><url><loc>https://tech.kakao.com/posts/844</loc><lastmod>2026-10-28</lastmod></url>"
               "<url><loc>https://tech.kakao.com/blog</loc></url>"
               "<url><loc>https://tech.kakao.com/posts/306</loc><lastmod>2014-05-28</lastmod></url></urlset>")
        self.assertEqual(M.kakao_sitemap_ids(raw), [(844, "2026-10-28"), (306, "2014-05-28")])

    def test_d2_entries_and_kst_date(self):
        # 2019-04-30T08:43:00Z는 한국 시간으로 2019-04-30 17:43이다. 2018-12-31T16:00:00Z는 2019-01-01 01:00이다.
        raw = json.dumps({"content": [
            {"postTitle": "A &amp; B", "postPublishedAt": "1556613780000", "url": "/helloworld/6204533"},
            {"postTitle": "소식", "postPublishedAt": "1546272000000", "url": "/news/0568192"},
            {"postTitle": "주소 없음", "postPublishedAt": "1546272000000", "url": ""},
        ]})
        self.assertEqual(M.d2_entries(raw), [("6204533", "helloworld", "2019-04-30", "A & B"),
                                             ("0568192", "news", "2019-01-01", "소식")])
        self.assertEqual(M.epoch_ms_date("not a number"), "")

    def test_woowahan_categories(self):
        def post(pid, date, cats):
            return {"id": pid, "date": date, "link": f"https://techblog.woowahan.com/{pid}/",
                    "title": {"rendered": "<b>제목</b> &amp; 부제"}, "categories": cats, "author": 85,
                    "content": {"rendered": "<p>본문</p>"}}
        entry, body = M.woowahan_entry(post(1, "2019-06-28T10:00:00", [11]))
        self.assertEqual((entry["id"], entry["date"], entry["title"], entry["author"]),
                         ("woowahan-1", "2019-06-28", "제목 & 부제", ""))
        self.assertNotIn("skipped", entry)
        self.assertEqual(body, "<p>본문</p>")
        self.assertEqual(M.woowahan_entry(post(2, "2019-06-28T10:00:00", [11, 12]))[0]["skipped"], "nontech-category")
        self.assertEqual(M.woowahan_entry(post(3, "2020-01-01T10:00:00", [286]))[0]["skipped"], "nontech-category")
        self.assertNotIn("skipped", M.woowahan_entry(post(4, "2020-01-01T10:00:00", [286, 11]))[0])
        self.assertEqual(M.woowahan_entry(post(5, "2017-05-01T10:00:00", [11]))[0]["skipped"], "pre2018")

    def test_next_data_and_clova_entry(self):
        props = {"post": {"language": {"code": "KO"}, "title": "제목", "date": "2025-03-04T10:00:00",
                          "tags": {"edges": [{"node": {"name": "AI Research"}}]},
                          "previousPost": {"slug": "이전-글"}, "content": "<p>본문</p>"}}
        raw = ('<html><script id="__NEXT_DATA__" type="application/json">'
               + json.dumps({"props": {"pageProps": props}}, ensure_ascii=False) + "</script></html>")
        pp = M.next_page_props(raw)
        entry = M.clova_entry("한국어-글", pp["post"])
        self.assertEqual((entry["site"], entry["date"], entry["title"], entry["tags"]),
                         ("clova", "2025-03-04", "제목", ["AI Research"]))
        self.assertTrue(entry["id"].startswith("clova-") and len(entry["id"]) == 18)
        self.assertIn("%ED%95%9C", entry["url"])
        self.assertIsNone(M.clova_entry("english", {"language": {"code": "EN"}}))
        self.assertIsNone(M.next_page_props("<html></html>"))


class TermStatsTest(unittest.TestCase):
    """dev/baseline/techblog/term_stats.py: plain-terms.md의 표를 만드는 정규식."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "term_stats", os.path.join(ROOT, "dev", "baseline", "techblog", "term_stats.py"))
        cls.T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.T)
        cls.rx = {label: re.compile(pattern) for label, pattern in cls.T.TERMS}

    def count(self, label, text):
        return len(self.rx[label].findall(self.T.clean(text)))

    def test_pan_counts_version_only(self):
        for text in ("Python 판과 비교합니다.", "arXiv판을 읽습니다.", "0.3.1판입니다."):
            self.assertEqual(self.count("판(영어, 숫자 뒤)", text), 1, text)
        self.assertEqual(self.count("판(수식어 뒤)", "이전 판으로 되돌립니다."), 1)
        self.assertEqual(self.count("판(N번째)", "두 번째 판을 씁니다."), 1)
        for text in ("개정판과 제2판을 읽습니다.", "버전을 판단합니다.", "CPU 판정입니다."):
            self.assertEqual(self.count("판(영어, 숫자 뒤)", text) + self.count("판(수식어 뒤)", text), 0, text)

    def test_clean_removes_code_and_quotes(self):
        self.assertEqual(self.count("낱말", '본문 `낱말` "낱말"\n\n```\n낱말\n```\n'), 0)
        self.assertEqual(self.count("낱말", "본문의 낱말"), 1)

    def test_natural_terms_are_listed(self):
        for label in ("버전", "단어", "의미", "쌍", "테스트", "버그", "복사본, 복제본", "중(N개 중, 이 중)", "인접한", "커버하다",
                      "출력하다", "반환하다", "삭제하다", "제외하다", "추가하다", "강도", "헤더", "반복"):
            self.assertIn(label, self.rx)


if __name__ == "__main__":
    unittest.main()
