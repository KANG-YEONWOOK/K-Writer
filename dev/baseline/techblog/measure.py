#!/usr/bin/env python3
"""Collect Korean tech blog articles (Toss, Kakao, Daangn, NAVER D2, Woowahan, CLOVA) and measure them with
lint_ko.analyze().

Source text is stored only in the --cache folder and is not committed. The repo keeps only the URL list (urls.json) and
the measurements (stats.json).

Periods
  - pre2018: before 2018-01-01. Bodies are not fetched; only the exclusion reason is recorded.
  - base: 2018-01-01~2022-11-30. Articles from before ChatGPT's release (2022-11-30); the main basis of threshold
    calculation.
  - mid: 2022-12-01~2024-12-31. Included in threshold calculation with a lower weight (calibrate.py).
  - drift: from 2025-01-01. Used only for comparison.
Group names: default/casual for base, mid-default/mid-casual for mid, drift-default/drift-casual for drift.

Usage
  python -I -X utf8 dev/baseline/techblog/measure.py collect --cache DIR [--only d2 woowahan ...]
  python -I -X utf8 dev/baseline/techblog/measure.py measure --cache DIR [--out dev/baseline/techblog/stats.json] [--urls dev/baseline/techblog/urls.json]
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "skills", "techblog", "scripts"))
import lint_ko as L  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (K-Writer baseline measurement; github.com/KANG-YEONWOOK/K-Writer)"}
BASE_START = "2018-01-01"      # start of the base period
CUTOFF = "2022-12-01"          # articles before this date predate ChatGPT's release (2022-11-30)
DRIFT_START = "2025-01-01"     # the mid period runs from CUTOFF up to this date
KST = timezone(timedelta(hours=9))
# Sites whose posting account differs from the author (Woowahan WP author, CLOVA clova-admin) are exempt from the
# per-author cap.
AUTHOR_CAP_EXEMPT_SITES = ("woowahan", "clova")
# Woowahan WP category IDs: culture 12, education 14, woowa-tech-seminar 269, "우아한테크캠프" 275,
# "우아한스터디" 319, notice 681, "우아콘" 686. A post with any of these is not a tech article.
WOOWA_NONTECH_CATS = {12, 14, 269, 275, 319, 681, 686}
# pm 286, design 479. A post with only these categories is excluded, like Toss categories other than Engineering.
WOOWA_PRODUCT_CATS = {286, 479}
# Markers of a translated article. "원문 보기" and "원문 링크" also appear in quoted articles and feature descriptions
# (Kakao, Toss articles), so only "원문:" at the start of a line counts.
TRANSLATION_RE = re.compile(r"(이 글은[^.\n]{0,120}번역|번역(한|했|하였|본|된) (글|것)|번역문|^\s*원문\s*[:：]"
                            r"|원저자|translated (by|from)|original (post|article))", re.I | re.M)
DAANGN_TAGS = [
    "backend", "frontend", "android", "ios", "data", "machine-learning", "mlops", "kubernetes", "devops",
    "sre", "infrastructure", "search", "recommendation-system", "ai", "llm", "react", "kotlin", "swift",
    "flutter", "golang", "go", "database", "mysql", "kafka", "aws", "platform", "web", "javascript",
    "typescript", "data-engineering", "analytics", "security", "observability", "monitoring", "spring",
    "nodejs", "graphql", "microservices", "architecture", "testing", "design-system", "data-science",
    "ab-testing", "experiment", "elasticsearch", "redis", "mongodb", "cloud", "network", "performance",
    "engineering", "software-development", "programming", "development", "tech", "daangn", "karrot",
]
NON_TECH_RE = re.compile(r"(채용|모집|인터뷰|Ka-reer|ka-reer|컨퍼런스|행사|밋업|meetup|SLASH|모닥불|"
                         r"합류|입사|신입|인턴십|career|hiring|recruit|팀을 소개|팀 소개|소개합니다|웨비나|"
                         r"이벤트|챌린지|해커톤|발표\s*영상|세션\s*영상|문화|DEVIEW|HACKDAY|CAMPUS|ENGINEERING DAY|"
                         r"테크코스|테크캠프|우아콘|WOOWACON|다시보기)", re.I)
KAKAO_SKIP_TAGS = ("career", "recruit", "new-krew", "krew", "event", "conference", "if-kakao", "ifkakao",
                   "culture", "interview", "hiring", "채용", "행사", "인터뷰", "문화")


# ---------------------------------------------------------------- HTML → markdown

class MDConverter(HTMLParser):
    """Convert body HTML into the markdown that lint_ko reads. Preserves bold, headings, lists, quotes, code, and tables."""
    SKIP = {"style", "script", "noscript", "svg", "figcaption", "button", "nav", "footer", "iframe",
            "select", "option", "template", "header"}
    BLOCK = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote",
             "table", "tr", "figure", "ul", "ol", "dl", "dt", "dd", "hr", "article", "aside"}

    def __init__(self, skip_header=True):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.buf = []
        self.skip = 0
        self.lists = []
        self.ctx = []          # open block tags
        self.pre = 0
        self.bq = 0
        self.row = None
        self.rows = None
        self.cell = None
        if not skip_header:
            self.SKIP = self.SKIP - {"header"}

    def _kind(self):
        for t in reversed(self.ctx):
            if t in ("h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd"):
                return t
        return "p"

    def flush(self):
        if self.pre:
            return
        text = "".join(self.buf)
        self.buf = []
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\*\*\s*\*\*", "", text)
        if not text or text in ("**",):
            return
        kind = self._kind()
        prefix = "> " if self.bq else ""
        if kind.startswith("h"):
            level = int(kind[1])
            self.blocks.append("#" * level + " " + text.replace("**", ""))
        elif kind == "li":
            depth = max(0, len(self.lists) - 1)
            marker = "1." if self.lists and self.lists[-1] == "ol" else "-"
            self.blocks.append(prefix + "  " * depth + marker + " " + text)
        else:
            self.blocks.append(prefix + text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if self.rows is not None and tag in ("td", "th"):
            self.cell = []
            return
        if self.rows is not None and tag == "tr":
            self.row = []
            return
        if tag == "table":
            self.flush()
            self.rows = []
            return
        if tag == "pre":
            self.flush()
            self.pre += 1
            self.buf = []
            return
        if self.pre:
            return
        if tag in self.BLOCK:
            self.flush()
            if tag in ("ul", "ol"):
                self.lists.append(tag)
            elif tag == "blockquote":
                self.bq += 1
            elif tag != "hr":
                self.ctx.append(tag)
            return
        if tag in ("strong", "b"):
            self._add("**")
        elif tag == "code":
            self._add("`")
        elif tag == "br":
            self._add(" ")
        elif tag == "img":
            pass

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if self.rows is not None:
            if tag in ("td", "th") and self.cell is not None and self.row is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "/"))
                self.cell = None
                return
            if tag == "tr" and self.row is not None:
                self.rows.append(self.row)
                self.row = None
                return
            if tag == "table":
                if self.rows:
                    width = max(len(r) for r in self.rows)
                    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in self.rows]
                    lines.insert(1, "|" + "---|" * width)
                    self.blocks.append("\n".join(lines))
                self.rows = None
                return
            return
        if tag == "pre":
            self.pre = max(0, self.pre - 1)
            code = "".join(self.buf).strip("\n")
            self.buf = []
            self.blocks.append("```\n" + code + "\n```")
            return
        if self.pre:
            return
        if tag in self.BLOCK:
            self.flush()
            if tag in ("ul", "ol"):
                if self.lists:
                    self.lists.pop()
            elif tag == "blockquote":
                self.bq = max(0, self.bq - 1)
            elif tag != "hr" and tag in self.ctx:
                while self.ctx and self.ctx.pop() != tag:
                    pass
            return
        if tag in ("strong", "b"):
            self._add("**")
        elif tag == "code":
            self._add("`")

    def _add(self, s):
        if self.cell is not None:
            self.cell.append(s.replace("**", "").replace("`", ""))
        else:
            self.buf.append(s)

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
            return
        self.buf.append(data)

    def result(self):
        self.flush()
        return "\n\n".join(self.blocks) + "\n"


TAIL_MARKERS = re.compile(r"(님의 다른 글|재미있게 읽으셨나요|좋았던 점, 아쉬웠던 점|함께 읽으면 좋은 글|was originally published in)")


def trim_tail(md, cta=None):
    """Remove the hiring button and the author's list of other articles that follow the body."""
    out = []
    for ln in md.split("\n"):
        s = ln.strip().lstrip("#").strip()
        if TAIL_MARKERS.search(s):
            break
        if cta and s == cta.strip():
            continue
        out.append(ln)
    return "\n".join(out).rstrip() + "\n"


FONT_HEADING_RE = re.compile(
    r"<p[^>]*>\s*(?:<strong>\s*)?<span style=\"font-size:\s*(\d+)px;?\">\s*(?:<strong>\s*)?(.*?)"
    r"\s*(?:</strong>\s*)?</span>\s*(?:</strong>\s*)?</p>", re.S)


def normalize_headings(fragment):
    """Convert paragraphs that mark a heading only by font size (20px or larger, CLOVA) into <h2>. Sites that use h tags
    are not affected."""
    return FONT_HEADING_RE.sub(lambda m: f"<h2>{m.group(2)}</h2>" if int(m.group(1)) >= 20 else m.group(0),
                               fragment)


def html_to_md(fragment, title=None, cta=None):
    conv = MDConverter()
    conv.feed(normalize_headings(fragment))
    body = conv.result()
    # Restore the space between sentences that was lost at a tag boundary: "있습니다.`code`" -> "있습니다. `code`"
    body = re.sub(r"([다요죠][.!?])(?=[`가-힣A-Za-z\"“])", r"\1 ", body)
    body = trim_tail(body, cta)
    if title:
        body = "# " + title.strip() + "\n\n" + body
    return body


# ---------------------------------------------------------------- collection

def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 410):
                return None
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def collect_toss(cache, meta):
    lst = []
    page = 1
    while True:
        raw = fetch(f"https://api-public.toss.im/api-public/v3/ipd-thor/api/v1/workspaces/15/posts?page={page}&size=100")
        if not raw:
            break
        d = json.loads(raw)["success"]
        lst += d["results"]
        if not d.get("next"):
            break
        page += 1
        time.sleep(1)
    for p in lst:
        if p.get("category") != "Engineering":
            continue
        date = (p.get("publishedTime") or "")[:10]
        if not date:
            continue
        key = p["key"]
        aid = f"toss-{key}"
        url = f"https://toss.tech/article/{key}"
        editor = (p.get("editor") or {}).get("name") if isinstance(p.get("editor"), dict) else None
        entry = {"id": aid, "site": "toss", "url": url, "date": date, "title": p.get("title", ""),
                 "author": editor or "", "tags": [c.get("name") for c in p.get("categories") or []]}
        path = os.path.join(cache, "md", aid + ".md")
        if not os.path.exists(path):
            page_html = fetch(url)
            time.sleep(1)
            if not page_html:
                entry["error"] = "fetch"
                meta[aid] = entry
                continue
            i = page_html.find("<article")
            j = page_html.find("</article>", i)
            frag = page_html[i:j] if i >= 0 and j > i else ""
            cta = (p.get("bottomButtonConfig") or {}).get("ctaName") or None
            if cta:
                entry["cta"] = cta
            save_body(path, frag, entry["title"], cta)
        meta[aid] = entry


def write_md(path, md):
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)


def save_body(path, fragment, title, cta=None):
    """Store the fetched body HTML in cache/raw and write the markdown to cache/md.
    After a converter change, the reconvert command rebuilds only the markdown without fetching again."""
    raw_dir = os.path.join(os.path.dirname(os.path.dirname(path)), "raw")
    os.makedirs(raw_dir, exist_ok=True)
    with open(os.path.join(raw_dir, os.path.basename(path)[:-3] + ".html"), "w", encoding="utf-8") as f:
        f.write(fragment or "")
    write_md(path, html_to_md(fragment or "", title, cta))


def done(meta, aid, path):
    """True if the article was already fetched (its body file exists, or its body was deliberately not fetched)."""
    return aid in meta and (os.path.exists(path) or bool(meta[aid].get("skipped")))


def kakao_sitemap_ids(raw):
    """Read (article ID, lastmod) from Kakao's sitemap.xml. lastmod equals the article's publication date."""
    return [(int(m.group(1)), (m.group(2) or "")[:10]) for m in
            re.finditer(r"<loc>https://tech\.kakao\.com/posts/(\d+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", raw or "")]


def collect_kakao(cache, meta):
    """Request the article API with the article IDs from the sitemap. Bodies of articles before 2018 are not fetched."""
    for pid, lastmod in kakao_sitemap_ids(fetch("https://tech.kakao.com/sitemap.xml")):
        aid = f"kakao-{pid}"
        path = os.path.join(cache, "md", aid + ".md")
        if done(meta, aid, path):
            continue
        entry = {"id": aid, "site": "kakao", "url": f"https://tech.kakao.com/posts/{pid}", "date": lastmod,
                 "title": "", "author": "", "tags": []}
        if lastmod and lastmod < BASE_START:
            entry["skipped"] = "pre2018"
            meta[aid] = entry
            continue
        raw = fetch(f"https://tech.kakao.com/api/v1/posts/{pid}")
        time.sleep(1)
        try:
            d = json.loads(raw) if raw else None
        except ValueError:
            d = None
        if not d:
            entry["error"] = "fetch"
            meta[aid] = entry
            continue
        rd = (d.get("releaseDate") or "").replace(".", "-")[:10]
        tags = [t.get("name", "") for t in d.get("tags") or []]
        authors = [a.get("name", "") for a in d.get("authors") or []]
        cats = [c.get("code", "") for c in d.get("categories") or []]
        entry.update(date=rd or lastmod, title=d.get("title", ""), author=",".join(authors), tags=tags + cats)
        save_body(path, d.get("content") or "", entry["title"])
        meta[aid] = entry


def epoch_ms_date(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, KST).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def d2_entries(raw):
    """Read (article ID, kind, date, title) from a D2 list API response. kind is helloworld or news."""
    out = []
    for it in (json.loads(raw).get("content") or []) if raw else []:
        kind, _, pid = (it.get("url") or "").strip("/").partition("/")
        if pid:
            out.append((pid, kind, epoch_ms_date(it.get("postPublishedAt")), html.unescape(it.get("postTitle") or "")))
    return out


def collect_d2(cache, meta):
    """NAVER D2: one list API call returns the articles and publication dates, and only hello world articles are fetched
    from the body API. news holds event, hiring, and video notices, so its bodies are not fetched. Article pages render
    only with JS, so the API is used."""
    for pid, kind, date, title in d2_entries(fetch("https://d2.naver.com/api/v1/contents?categoryId=&page=0&size=1000")):
        aid = f"d2-{pid}"
        path = os.path.join(cache, "md", aid + ".md")
        if done(meta, aid, path):
            continue
        entry = {"id": aid, "site": "d2", "url": f"https://d2.naver.com/{kind}/{pid}", "date": date,
                 "title": title, "author": "", "tags": [kind]}
        if kind != "helloworld":
            entry["skipped"] = "nontech-category"
        elif date < BASE_START:
            entry["skipped"] = "pre2018"
        else:
            raw = fetch(f"https://d2.naver.com/api/v1/contents/{pid}")
            time.sleep(1)
            try:
                d = json.loads(raw) if raw else None
            except ValueError:
                d = None
            if not d:
                entry["error"] = "fetch"
            else:
                entry["author"] = ",".join(a.get("name", "") for a in d.get("authors") or [])
                entry["tags"] += [t.get("name", "") for t in d.get("postTags") or []]
                entry["editor"] = d.get("editorType") or ""
                save_body(path, d.get("postHtml") or "", title)
        meta[aid] = entry


def woowahan_entry(p):
    """Convert one post from the Woowahan WP REST API into (entry, body HTML). Sets skipped on a post to exclude."""
    cats = set(p.get("categories") or [])
    title = html.unescape(re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered", "")))
    entry = {"id": f"woowahan-{p['id']}", "site": "woowahan", "url": p.get("link", ""),
             "date": (p.get("date") or "")[:10], "title": title, "author": "", "tags": sorted(str(c) for c in cats)}
    if cats & WOOWA_NONTECH_CATS or (cats and cats <= WOOWA_PRODUCT_CATS):
        entry["skipped"] = "nontech-category"
    elif entry["date"] < BASE_START:
        entry["skipped"] = "pre2018"
    return entry, (p.get("content") or {}).get("rendered", "")


def collect_woowahan(cache, meta):
    """Woowahan: the WordPress REST API post list includes the bodies (100 posts per page)."""
    page = 1
    while True:
        raw = fetch("https://techblog.woowahan.com/wp-json/wp/v2/posts?per_page=100&page=%d"
                    "&_fields=id,date,link,title,categories,author,content" % page)
        time.sleep(1)
        try:
            posts = json.loads(raw) if raw else []
        except ValueError:
            posts = []
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            entry, body = woowahan_entry(p)
            path = os.path.join(cache, "md", entry["id"] + ".md")
            if not entry.get("skipped") and not os.path.exists(path):
                save_body(path, body, entry["title"])
            meta[entry["id"]] = entry
        if len(posts) < 100:
            break
        page += 1


NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def next_page_props(raw):
    m = NEXT_DATA_RE.search(raw or "")
    try:
        return json.loads(m.group(1))["props"]["pageProps"] if m else None
    except (ValueError, KeyError):
        return None


def clova_entry(slug, post):
    """Convert the post from a CLOVA article page into an entry. None if the article is not in Korean."""
    if not post or (post.get("language") or {}).get("code") != "KO":
        return None
    url = "https://clova.ai/tech-blog/" + urllib.parse.quote(slug)
    tags = [e.get("node", {}).get("name", "") for e in ((post.get("tags") or {}).get("edges") or [])]
    return {"id": "clova-" + hashlib.sha1(slug.encode("utf-8")).hexdigest()[:12], "site": "clova", "url": url,
            "date": (post.get("date") or "")[:10], "title": html.unescape(post.get("title") or ""),
            "author": "", "tags": tags}


def edge_slugs(listing):
    return [e["node"]["slug"] for e in ((listing or {}).get("edges") or []) if e.get("node", {}).get("slug")]


def collect_clova(cache, meta):
    """CLOVA: start from the articles on the list page, then follow previousPost, nextPost, and tag pages from each article
    page. previousPost and nextPost are not in date order, so both are followed. A tag page shows all articles with that
    tag. robots.txt blocks /api, so only __NEXT_DATA__ from article and tag pages is read. Only Korean articles are saved."""
    pp = next_page_props(fetch("https://clova.ai/tech-blog")) or {}
    queue = edge_slugs(pp.get("posts")) + edge_slugs(pp.get("stickyPost"))
    seen, seen_tags = set(), set()
    while queue:
        slug = queue.pop(0)
        if slug in seen:
            continue
        seen.add(slug)
        page = next_page_props(fetch("https://clova.ai/tech-blog/" + urllib.parse.quote(slug)))
        time.sleep(1)
        post = (page or {}).get("post") or {}
        for key in ("previousPost", "nextPost"):
            other = (post.get(key) or {}).get("slug")
            if other and other not in seen:
                queue.append(other)
        for e in ((post.get("tags") or {}).get("edges") or []):
            tag = e.get("node", {}).get("slug")
            if tag and tag not in seen_tags:
                seen_tags.add(tag)
                tp = next_page_props(fetch("https://clova.ai/tech-blog/tag/" + urllib.parse.quote(tag)))
                time.sleep(1)
                queue += [s for s in edge_slugs((tp or {}).get("posts")) if s not in seen]
        entry = clova_entry(slug, post)
        if not entry:
            continue
        path = os.path.join(cache, "md", entry["id"] + ".md")
        if not os.path.exists(path):
            save_body(path, post.get("content") or "", entry["title"])
        meta[entry["id"]] = entry


def collect_daangn(cache, meta):
    """Daangn: Medium RSS (the main feed and per-tag feeds). Each feed returns only recent articles.
    Medium blocks HTML, archive, and sitemap requests with Cloudflare, and its robots.txt rejects AI crawlers, so only RSS
    is used."""
    seen = set()
    feeds = ["https://medium.com/feed/daangn"] + [f"https://medium.com/feed/daangn/tagged/{t}" for t in DAANGN_TAGS]
    for feed in feeds:
        raw = fetch(feed)
        time.sleep(1)
        if not raw:
            continue
        for it in re.findall(r"<item>(.*?)</item>", raw, re.S):
            link = re.search(r"<link>(.*?)</link>", it)
            guid = re.search(r"<guid[^>]*>(.*?)</guid>", it)
            pid = (guid.group(1) if guid else link.group(1)).rstrip("/").split("/")[-1]
            pid = re.sub(r"[^0-9a-zA-Z]", "", pid)[-12:]
            aid = f"daangn-{pid}"
            if aid in seen:
                continue
            seen.add(aid)
            title = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", it, re.S)
            pub = re.search(r"<pubDate>(.*?)</pubDate>", it)
            creator = re.search(r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>", it)
            cats = re.findall(r"<category><!\[CDATA\[(.*?)\]\]></category>", it)
            content = re.search(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>", it, re.S)
            date = parsedate_to_datetime(pub.group(1)).strftime("%Y-%m-%d") if pub else ""
            entry = {"id": aid, "site": "daangn", "url": (link.group(1) if link else "").split("?")[0],
                     "date": date, "title": html.unescape(title.group(1)) if title else "",
                     "author": creator.group(1) if creator else "", "tags": cats}
            path = os.path.join(cache, "md", aid + ".md")
            if content and not os.path.exists(path):
                save_body(path, content.group(1), entry["title"])
            meta[aid] = entry


def cmd_reconvert(args):
    """Rebuild cache/md from the body HTML in cache/raw. Does not request the sites again."""
    meta = json.load(open(os.path.join(args.cache, "meta.json"), encoding="utf-8"))
    n = 0
    for aid, e in meta.items():
        raw = os.path.join(args.cache, "raw", aid + ".html")
        if os.path.exists(raw):
            write_md(os.path.join(args.cache, "md", aid + ".md"),
                     html_to_md(open(raw, encoding="utf-8").read(), e.get("title"), e.get("cta")))
            n += 1
    print(f"[reconvert] {n} files")


def cmd_collect(args):
    os.makedirs(os.path.join(args.cache, "md"), exist_ok=True)
    meta_path = os.path.join(args.cache, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    collectors = (("daangn", collect_daangn), ("toss", collect_toss), ("kakao", collect_kakao),
                  ("d2", collect_d2), ("woowahan", collect_woowahan), ("clova", collect_clova))
    for name, fn in collectors:
        if args.only and name not in args.only:
            continue
        print(f"[collect] {name} ...", flush=True)
        try:
            fn(args.cache, meta)
        finally:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
        n = sum(1 for e in meta.values() if e.get("site") == name)
        print(f"[collect] {name} done: {n} entries, total {len(meta)}", flush=True)


# ---------------------------------------------------------------- measurement

def tone_group(analysis):
    c = analysis["endings"]["class"]
    hap = c.get("HAPNIDA", 0)
    hae = c.get("HAEYO", 0) + c.get("Q_KKAYO", 0) * 0  # "~할까요?" occurs in both tones, so it is excluded from the verdict
    hra = c.get("HAERA", 0)
    pred = hap + hae + hra
    if pred == 0:
        return "unknown", 0.0
    if hap / pred >= 0.9:
        return "default", round(hap / pred, 3)
    if hae / pred >= 0.9:
        return "casual", round(hae / pred, 3)
    # "해라체" articles (most of NAVER D2) use a tone this skill does not use, so they are left out of threshold
    # calculation and used only for tone-independent analysis of writing style (structure_stats.py) and site comparison.
    if hra / pred >= 0.9:
        return "haera", round(hra / pred, 3)
    return "mixed", round(max(hap, hae, hra) / pred, 3)


def period(date):
    """pre2018, base(2018-01-01~2022-11-30), mid(2022-12-01~2024-12-31), drift(2025-01-01~)."""
    if not date or date < BASE_START:
        return "pre2018"
    if date < CUTOFF:
        return "base"
    if date < DRIFT_START:
        return "mid"
    return "drift"


def group_name(tone, per):
    """Build the group name from the period and tone. base has no prefix: default, casual."""
    return tone if per == "base" else f"{per}-{tone}"


def is_translation(text):
    """True if the first or last 1,500 characters of the body hold a translated-article marker."""
    return bool(TRANSLATION_RE.search(text[:1500]) or TRANSLATION_RE.search(text[-1500:]))


def author_key(entry):
    """Author name used for the per-author cap. An empty string for sites whose posting account differs from the author."""
    if entry.get("site") in AUTHOR_CAP_EXEMPT_SITES:
        return ""
    return str(entry.get("author") or "").split(",")[0].strip()


SKIP_REASONS = {"pre2018": "기준 기간 이전(2018년 이전, 본문을 받지 않음)",
                "nontech-category": "기술 글 아님(사이트 분류가 행사·교육·문화·공지·기획·디자인)"}


def holdout(aid):
    return int(hashlib.sha1(aid.encode()).hexdigest(), 16) % 5 == 0  # 20%


def is_tech(entry):
    if NON_TECH_RE.search(entry.get("title", "")):
        return False
    tags = " ".join(entry.get("tags") or []).lower()
    if entry["site"] == "kakao" and any(t in tags for t in KAKAO_SKIP_TAGS):
        return False
    return True


MIN_PARAGRAPHS = 5  # paragraph metrics (A8) are ratios of prose paragraphs, meaningless for articles of only lists and code


def skip_reason(entry, text, st, grp, per):
    """Reason to exclude a measured article from the baseline. None if it is included. cmd_measure checks the per-author
    cap separately."""
    hangul = len(re.findall(r"[가-힣]", text))
    if per == "pre2018":
        return SKIP_REASONS["pre2018"]
    if not is_tech(entry):
        return "기술 글 아님(채용·행사·인터뷰·팀 소개)"
    if hangul < 300:
        return "본문 없음(영상·발표 요약, 짧은 공지)"
    if hangul < 1000:
        return "영어 글이거나 한국어 본문 1,000자 미만"
    if is_translation(text):
        return "번역 글"
    if st["chars"] < 1500 or st["sentences"] < 30:
        return "본문 1,500자·30문장 미만"
    if st["paragraphs"] < MIN_PARAGRAPHS:
        return f"산문 문단 {MIN_PARAGRAPHS}개 미만(목록과 코드 위주)"
    if grp in ("mixed", "unknown"):
        return "어투 혼용(한쪽 어투 90% 미만)"
    return None


def cmd_measure(args):
    meta = json.load(open(os.path.join(args.cache, "meta.json"), encoding="utf-8"))
    patterns = L.load_json(L.PATTERNS_PATH)
    rows = []
    per_author = {}
    for aid, e in sorted(meta.items(), key=lambda kv: (kv[1].get("date", ""), kv[0])):
        rec = {k: e.get(k) for k in ("id", "site", "url", "date", "title", "author")}
        path = os.path.join(args.cache, "md", aid + ".md")
        if e.get("skipped"):
            rec.pop("author", None)
            rec.update(included=False, reason=SKIP_REASONS.get(e["skipped"], e["skipped"]),
                       period=period(e.get("date") or ""))
            rows.append(rec)
            continue
        if e.get("error") or not os.path.exists(path):
            rec.pop("author", None)
            rec.update(included=False, reason="본문 없음")
            rows.append(rec)
            continue
        text = L.read_text(path)
        a = L.analyze(text, patterns)
        st = a["stats"]
        grp, share = tone_group(a)
        rec.update(chars=st["chars"], sentences=st["sentences"], tone=grp, tone_share=share,
                   period=period(e.get("date") or ""))
        reason = skip_reason(e, text, st, grp, rec["period"])
        if reason is None:
            key = (grp, rec["period"], author_key(e))
            per_author[key] = per_author.get(key, 0) + 1
            if key[2] and per_author[key] > 2:
                reason = "저자당 2편 초과"
        if reason:
            rec.pop("author", None)
            rec.update(included=False, reason=reason)
            rows.append(rec)
            continue
        rec.pop("author", None)  # author names are not kept in the repo
        ev_metrics = dict(a["metrics"])
        if grp != "haera":
            ev_metrics.update(L.tone_metrics(a, grp))
        rec.update(included=True, group=group_name(grp, rec["period"]),
                   holdout=holdout(aid),
                   metrics={k: v["value"] for k, v in ev_metrics.items()},
                   endings=a["endings"]["bucket"])
        rows.append(rec)
    inc = [r for r in rows if r.get("included")]
    summary = {}
    for r in inc:
        summary.setdefault(r["group"], {"n": 0, "holdout": 0, "sites": {}})
        g = summary[r["group"]]
        g["n"] += 1
        g["holdout"] += int(r["holdout"])
        g["sites"][r["site"]] = g["sites"].get(r["site"], 0) + 1
    out = {"schema": 1, "generated_at": time.strftime("%Y-%m-%d"), "lint_schema": L.LINT_SCHEMA,
           "groups": summary, "articles": inc}
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    urls = [{k: r.get(k) for k in ("id", "site", "url", "date", "period", "title", "group", "included", "reason",
                                    "holdout", "tone", "tone_share", "chars")} for r in rows]
    with open(args.urls, "w", encoding="utf-8", newline="\n") as f:
        json.dump(urls, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    reasons = {}
    for r in rows:
        if not r.get("included"):
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    print("제외 사유:", json.dumps(reasons, ensure_ascii=False))


def main():
    L.setup_stdio()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--cache", required=True)
    c.add_argument("--only", nargs="*")
    m = sub.add_parser("measure")
    m.add_argument("--cache", required=True)
    m.add_argument("--out", default=os.path.join(ROOT, "dev", "baseline", "techblog", "stats.json"))
    m.add_argument("--urls", default=os.path.join(ROOT, "dev", "baseline", "techblog", "urls.json"))
    r = sub.add_parser("reconvert")
    r.add_argument("--cache", required=True)
    args = ap.parse_args()
    {"collect": cmd_collect, "measure": cmd_measure, "reconvert": cmd_reconvert}[args.cmd](args)


if __name__ == "__main__":
    main()
