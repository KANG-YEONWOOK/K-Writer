#!/usr/bin/env python3
"""K-Writer lint: counts the automatically measured items (G, A) defined by a skill's rubric in a Korean article.

Usage
  python lint_ko.py ARTICLE.md [--tone default|casual|plain|free|auto] [--facts FACTS.md]
                    [--short] [--thresholds PATH] [--json] [--all] [--max-hits N]

The source of this file is core/scripts/lint_ko.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/
for each skill. Thresholds are the merge of rules.json (core's rule definitions) and thresholds.json (values that skill
calibrated against its standard articles), both in the same folder (load_thresholds). The name in the output header is
the name of the skill folder that contains the script.

--tone names the tone the article must keep: default ("합니다체"), casual ("해요체"), plain ("해라체"), or free (a tone the
user described in their own words; the tone items G4 and T are not judged). auto picks the most frequent of the three
fixed tones.

--short applies the short profile (the "short" key of rules.json, or of the skill's thresholds.json when it has one)
for texts under 1,500 characters: distribution items that need many sentences are dropped and the listed per-1,000
rates are judged by count.

Exit codes: 0 pass, 1 threshold not met, 2 usage or input error
Uses only the standard library (Python 3.8 or later).
"""

import argparse
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_NAME = os.path.basename(os.path.dirname(HERE))
PATTERNS_PATH = os.path.join(HERE, "patterns_ko.json")
RULES_PATH = os.path.join(HERE, "rules.json")
THRESHOLDS_PATH = os.path.join(HERE, "thresholds.json")
LINT_SCHEMA = 1
# Calibration fields stored in a skill's thresholds.json. They are skill-side values only for metrics that are neither
# gate nor fixed. dev/baseline/<skill>/calibrate.py recomputes these fields from measurements on human articles.
CALIBRATED_FIELDS = ("by_tone", "human", "rate_per_1k", "pass_max", "warn_max", "pass_min", "warn_min",
                     "pass", "warn", "n", "n_eff", "exclude_sites")
# Limits a verdict needs. A metric without them has not yet been calibrated against that skill's standard articles.
LIMIT_FIELDS = {"poisson": ("rate_per_1k",), "upper": ("pass_max", "warn_max"),
                "lower": ("pass_min", "warn_min"), "range": ("pass", "warn")}
UNCALIBRATED_NOTE = "이 스킬의 기준 글로 보정한 기준치가 없어 판정하지 않음"
DEFAULT_STANDARD = "스킬이 정한 기준 글"


# ---------------------------------------------------------------- I/O

def setup_stdio():
    """Switches stdout and stderr to UTF-8 so Hangul is not garbled under the default Windows console encoding (cp949)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def normalize_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def read_text(path):
    with open(path, encoding="utf-8-sig") as f:
        return normalize_text(f.read())


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _dropped(mid, drops):
    """A drop entry that ends in "." refers to every metric starting with that prefix."""
    return any(mid.startswith(d) if d.endswith(".") else mid == d for d in drops)


def load_thresholds(path=None, rules_path=None):
    """Returns thresholds merged from core's rule definitions (rules.json) and the skill's calibrated values
    (thresholds.json).

    Metric order follows rules.json, and for each metric the skill's fields override the rules.json fields. Metrics not
    in rules.json are appended. The skill side also overrides top-level keys. Metrics listed in the skill file's drop
    (a metric ID or a prefix ending in ".") are excluded."""
    rules = load_json(rules_path or RULES_PATH)
    skill = load_json(path or THRESHOLDS_PATH)
    merged = {k: v for k, v in rules.items() if k != "metrics"}
    merged.update({k: v for k, v in skill.items() if k != "metrics"})
    own = skill.get("metrics") or {}
    metrics = {mid: dict(spec, **own.get(mid, {})) for mid, spec in (rules.get("metrics") or {}).items()}
    for mid, spec in own.items():
        if mid not in metrics:
            metrics[mid] = dict(spec)
    drops = merged.get("drop") or []
    merged["metrics"] = {mid: spec for mid, spec in metrics.items() if not _dropped(mid, drops)}
    return merged


def split_thresholds(merged, rules=None):
    """Inverse of load_thresholds. From merged thresholds, returns only the values that differ from rules.json, that is,
    the content that belongs in the skill's thresholds.json."""
    rules = load_json(RULES_PATH) if rules is None else rules
    base = rules.get("metrics") or {}
    out = {k: v for k, v in merged.items() if k != "metrics" and (k not in rules or rules[k] != v)}
    metrics = {}
    for mid, spec in (merged.get("metrics") or {}).items():
        diff = {k: v for k, v in spec.items() if mid not in base or k not in base[mid] or base[mid][k] != v}
        if diff:
            metrics[mid] = diff
    out["metrics"] = metrics
    return out


def standard_text(thresholds):
    """The standard articles named in the skill's thresholds.json. Used in output messages."""
    return (thresholds.get("skill") or {}).get("standard") or DEFAULT_STANDARD


# ---------------------------------------------------------------- markdown blocks

class Block:
    __slots__ = ("type", "text", "line", "level", "list_id", "depth")

    def __init__(self, type_, text, line, level=0, list_id=None, depth=0):
        self.type = type_
        self.text = text
        self.line = line
        self.level = level
        self.list_id = list_id
        self.depth = depth


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
HR_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
LIST_RE = re.compile(r"^([ \t]*)([-*+]|\d{1,3}[.)])[ \t]+(.*)$")
BQ_RE = re.compile(r"^ {0,3}>[ ]?(.*)$")
TABLE_DELIM_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$")
HTML_BLOCK_RE = re.compile(
    r"^ {0,3}</?(div|details|summary|table|thead|tbody|tr|td|th|figure|figcaption|iframe|video|"
    r"picture|source|section|aside|p|img|pre|ul|ol|li|hr|center|blockquote|script|style)\b", re.I)
HTML_COMMENT_RE = re.compile(r"^ {0,3}<!--")


def _is_block_start(line):
    return bool(FENCE_RE.match(line) or ATX_RE.match(line) or BQ_RE.match(line)
                or LIST_RE.match(line) or HR_RE.match(line) or HTML_BLOCK_RE.match(line))


def parse_blocks(text):
    """Splits markdown line by line into blocks (heading, paragraph, list_item, blockquote, code, table, html)."""
    lines = text.split("\n")
    n = len(lines)
    blocks = []
    i = 0
    if n and lines[0].strip() == "---":  # front matter
        for j in range(1, min(n, 300)):
            if lines[j].strip() in ("---", "..."):
                i = j + 1
                break
    para = []
    para_start = 0
    list_counter = 0
    cur_list = None  # [list_id, base_indent]

    def flush():
        nonlocal para
        if para:
            blocks.append(Block("paragraph", " ".join(p.strip() for p in para), para_start))
            para = []

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush()
            i += 1
            continue
        m = FENCE_RE.match(line)
        if m:
            flush()
            cur_list = None
            fence = m.group(1)
            close_re = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$")
            start = i
            i += 1
            body = []
            while i < n and not close_re.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(Block("code", "\n".join(body), start + 1))
            continue
        if HTML_COMMENT_RE.match(line):
            flush()
            start = i
            while i < n and "-->" not in lines[i]:
                i += 1
            i += 1
            blocks.append(Block("html", "", start + 1))
            continue
        m = ATX_RE.match(line)
        if m:
            flush()
            cur_list = None
            blocks.append(Block("heading", (m.group(2) or "").strip(), i + 1, level=len(m.group(1))))
            i += 1
            continue
        if para and SETEXT_RE.match(line):
            title = " ".join(p.strip() for p in para)
            blocks.append(Block("heading", title, para_start, level=1 if stripped.startswith("=") else 2))
            para = []
            i += 1
            continue
        if HR_RE.match(line):
            flush()
            cur_list = None
            i += 1
            continue
        if "|" in line and not para and i + 1 < n and TABLE_DELIM_RE.match(lines[i + 1]):
            cur_list = None
            start = i
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(lines[i])
                i += 1
            blocks.append(Block("table", "\n".join(rows), start + 1))
            continue
        m = BQ_RE.match(line)
        if m:
            flush()
            cur_list = None
            start = i
            parts = []
            while i < n:
                mm = BQ_RE.match(lines[i])
                if mm:
                    parts.append(mm.group(1).strip())
                elif lines[i].strip() and parts and parts[-1] and not _is_block_start(lines[i]):
                    parts.append(lines[i].strip())  # lazy continuation
                else:
                    break
                i += 1
            blocks.append(Block("blockquote", " ".join(p for p in parts if p), start + 1))
            continue
        m = LIST_RE.match(line)
        if m:
            flush()
            indent = len(m.group(1).replace("\t", "    "))
            if cur_list is None:
                list_counter += 1
                cur_list = [list_counter, indent]
            depth = 0 if indent <= cur_list[1] else 1 + (indent - cur_list[1]) // 2
            start = i
            parts = [m.group(3).strip()]
            i += 1
            while i < n:
                nxt = lines[i]
                if not nxt.strip() or _is_block_start(nxt):
                    break
                parts.append(nxt.strip())
                i += 1
            blocks.append(Block("list_item", " ".join(parts), start + 1, list_id=cur_list[0], depth=depth))
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j < n and LIST_RE.match(lines[j]):
                i = j
            elif j < n and lines[j].startswith(("  ", "\t")) and not FENCE_RE.match(lines[j]):
                # An indented paragraph is treated as continued content of the same list item.
                start2 = j
                parts2 = []
                while j < n and lines[j].strip() and not LIST_RE.match(lines[j]):
                    parts2.append(lines[j].strip())
                    j += 1
                blocks.append(Block("list_item", " ".join(parts2), start2 + 1, list_id=cur_list[0], depth=depth + 1))
                i = j
            else:
                cur_list = None
            continue
        if HTML_BLOCK_RE.match(line):
            flush()
            cur_list = None
            start = i
            while i < n and lines[i].strip():
                i += 1
            blocks.append(Block("html", "", start + 1))
            continue
        if not para and line.startswith(("    ", "\t")) and cur_list is None:
            start = i
            body = []
            while i < n and (lines[i].startswith(("    ", "\t")) or not lines[i].strip()):
                body.append(lines[i])
                i += 1
            blocks.append(Block("code", "\n".join(body), start + 1))
            continue
        if not para:
            para_start = i + 1
            cur_list = None
        para.append(line)
        i += 1
    flush()
    return blocks


# ---------------------------------------------------------------- inline cleanup

PH_CODE, PH_URL, PH_REF, PH_QUOTE = "⟦C⟧", "⟦U⟧", "⟦R⟧", "⟦Q⟧"
PH_RE = re.compile(r"⟦[CURQ]⟧")
INLINE_CODE_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)")
REFLINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
AUTOLINK_RE = re.compile(r"<(?:https?|ftp)://[^>\s]+>")
URL_RE = re.compile(r"https?://[^\s)>\]`\"'<]+")
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
CITE_RE = re.compile(r"\[\d+(?:\s*[,–\-]\s*\d+)*\]")
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>")
BOLD_RE = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
EM_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>])")


def clean_inline(s):
    """Returns the sentence text with inline markdown removed, the bold count, and the list of inline code spans."""
    codes = []

    def code_sub(m):
        codes.append(m.group(2))
        return PH_CODE

    s = INLINE_CODE_RE.sub(code_sub, s)
    s = IMAGE_RE.sub("", s)
    s = LINK_RE.sub(lambda m: m.group(1), s)
    s = REFLINK_RE.sub(lambda m: m.group(1), s)
    s = AUTOLINK_RE.sub(PH_URL, s)
    s = URL_RE.sub(PH_URL, s)
    s = FOOTNOTE_RE.sub("", s)
    s = CITE_RE.sub(PH_REF, s)
    s = HTML_TAG_RE.sub("", s)
    bold = len(BOLD_RE.findall(s))
    s = BOLD_RE.sub(lambda m: m.group(2), s)
    s = EM_RE.sub(lambda m: m.group(1), s)
    s = ESCAPE_RE.sub(r"\1", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s, bold, codes


QUOTE_PAIRS = (("“", "”"), ("「", "」"), ("『", "』"), ("‘", "’"))


def mask_quotes(s):
    """Masks text inside quotes with ⟦Q⟧. Quoted expressions from the source are excluded from pattern checks."""
    for a, b in QUOTE_PAIRS:
        s = re.sub(re.escape(a) + "[^" + re.escape(b) + r"\n]{0,200}" + re.escape(b), PH_QUOTE, s)
    s = re.sub(r"\"[^\"\n]{0,200}\"", PH_QUOTE, s)
    s = re.sub(r"'([^'\n]{1,60})'", lambda m: PH_QUOTE if re.search("[가-힣]", m.group(1)) else m.group(0), s)
    return s


PH_MATH = "⟦M⟧"
# Treats $...$ and $$...$$ without Hangul as math. Currency text such as "$5에서 $10으로" contains Hangul, so it is not
# masked.
MATH_RE = re.compile(r"\$\$[^$]+\$\$|\$[^$\n가-힣]+\$")


def mask_math(s):
    """Masks math with ⟦M⟧. Used only by the punctuation policy (G6) and post-number particle (G10) checks."""
    return MATH_RE.sub(PH_MATH, s)


def visible_chars(s):
    return len(re.sub(r"\s", "", PH_RE.sub("", s)))


# ---------------------------------------------------------------- sentence splitting

TERMINATORS = ".?!…"
CLOSERS = "\"'”’)]}」』"
DEPTH_OPEN = "(「『[{“‘"
DEPTH_CLOSE = ")」』]}”’"
ABBREVIATIONS = {"e.g", "i.e", "vs", "etc", "cf", "fig", "figs", "eq", "al", "approx", "ref", "sec",
                 "ch", "vol", "pp", "no", "mr", "dr", "jr", "sr", "inc", "ltd", "u.s", "ph.d"}


def _is_abbrev(text, i):
    m = re.search(r"([A-Za-z][A-Za-z.]{0,5})$", text[:i])
    if not m:
        return False
    tok = m.group(1).lower().rstrip(".")
    if tok in ABBREVIATIONS:
        return True
    return len(tok) == 1 and text[i - 1].isupper()  # initial (J. Smith)


def _split_flat(s):
    return [p.strip() for p in re.split(r"(?<=[.?!…])\s+", s) if p.strip()]


def split_sentences(text):
    """Splits at whitespace after a period, question mark, or exclamation mark. Does not split inside parentheses or
    quotes, in numbers (3.5), or in abbreviations (e.g.)."""
    sents = []
    start = 0
    depth = 0
    in_dq = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in DEPTH_OPEN:
            depth += 1
        elif ch in DEPTH_CLOSE:
            if depth > 0:
                depth -= 1
        elif ch == '"':
            in_dq = not in_dq
        elif ch in TERMINATORS and depth == 0 and not in_dq:
            j = i
            while j + 1 < n and text[j + 1] in TERMINATORS:
                j += 1
            k = j
            while k + 1 < n and text[k + 1] in CLOSERS and text[k + 1] != '"':
                k += 1
            if (k + 1 >= n or text[k + 1].isspace()) and not _is_abbrev(text, i):
                seg = text[start:k + 1].strip()
                if seg:
                    sents.append(seg)
                start = k + 1
                i = k + 1
                continue
            i = j
        i += 1
    tail = text[start:].strip()
    if tail:
        sents.append(tail)
    out = []
    for s in sents:
        out.extend(_split_flat(s) if len(s) > 400 else [s])
    return out


# ---------------------------------------------------------------- sentence-ending classification

HANGUL_RE = re.compile(r"[가-힣]")
JONG_B, JONG_SS = 17, 20  # final consonants ㅂ, ㅆ
NOUN_YO = ("필요", "중요", "주요", "수요", "개요", "강요", "소요", "요요")
HAERA_NOUNS = ("람다", "판다", "바다", "어젠다", "아젠다")
NOMINAL_RE = re.compile(r"(함|됨|했음|됐음|였음|었음|았음|있음|없음|같음|좋음|않음)$")
NOMINAL_EXCEPT = ("결함", "포함")
TRAIL_STRIP = " \t.?!…\"'”’)]}」』:;~*_,"
BANNED_ENDINGS = ("더라고요", "더군요", "네요", "잖아요", "답니다")
EXPERIENCE_ENDINGS = ("더라고요", "더군요", "네요")


def _jong(ch):
    code = ord(ch) - 0xAC00
    return code % 28 if 0 <= code < 11172 else -1


def _jung(ch):
    code = ord(ch) - 0xAC00
    return (code // 28) % 21 if 0 <= code < 11172 else -1


def last_word(sentence):
    s = PH_RE.sub(" ", sentence).strip()
    for _ in range(3):  # Ignores a parenthetical at the end of the sentence ("적용했습니다(그림 1).").
        s2 = re.sub(r"\s*[(\[][^()\[\]]*[)\]]\s*[.?!…]*\s*$", "", s)
        if s2 == s:
            break
        s = s2
    s = s.rstrip(TRAIL_STRIP)
    toks = s.split()
    return toks[-1] if toks else ""


def classify_ending(word, question=False):
    """Classifies a sentence ending by its last word: HAPNIDA, HAEYO, Q_KKAYO, HAERA, NOMINAL, NOUN, OTHER."""
    if not word or not HANGUL_RE.match(word[-1]):
        return "OTHER"
    if len(word) >= 3 and word.endswith(("니다", "니까")) and _jong(word[-3]) == JONG_B:
        return "HAPNIDA"
    if word.endswith("십시오") or (len(word) >= 3 and word.endswith("시다") and _jong(word[-3]) == JONG_B):
        return "HAPNIDA"
    if word.endswith(("요", "죠")):
        if word.endswith(NOUN_YO):
            return "NOUN"
        if word.endswith("까요"):
            return "Q_KKAYO"
        return "HAEYO"
    if word.endswith("다") and not word.endswith(HAERA_NOUNS):
        return "HAERA"
    if question and word.endswith(("까", "냐", "니", "가", "나")):
        return "HAERA"
    if NOMINAL_RE.search(word) and not word.endswith(NOMINAL_EXCEPT):
        return "NOMINAL"
    return "NOUN"


def ending_bucket(sentence, word, cls):
    """Finer classification used to count repeated endings and the ending distribution."""
    w = word
    tail = PH_RE.sub(" ", sentence).rstrip(TRAIL_STRIP)
    if cls == "HAPNIDA":
        if w.endswith("니까"):
            return "D_Q"
        if w.endswith("십시오") or w.endswith("시다"):
            return "D_IMP"
        if re.search(r"수\s*있습니다$", tail):
            return "D_CAN"
        if w.endswith("겠습니다"):
            return "D_FUT"
        if w.endswith(("있습니다", "없습니다")):
            return "D_EXIST"
        if w.endswith("것입니다"):
            return "D_GEOT"
        if w.endswith("입니다"):
            return "D_COP"
        if w.endswith("습니다") and len(w) >= 4 and _jong(w[-4]) == JONG_SS and w[-4] not in "있겠":
            return "D_PAST"
        if w.endswith("습니다"):
            return "D_S_PRES"
        return "D_B_PRES"
    if cls == "Q_KKAYO":
        return "Q_KKAYO"
    if cls == "HAEYO":
        for suf, name in (("더라고요", "C_DEORAGO"), ("더군요", "C_DEORAGO"), ("잖아요", "C_JANAYO"),
                          ("네요", "C_NEYO"), ("거든요", "C_GEUDEUN"), ("는데요", "C_NEUNDEYO"),
                          ("은데요", "C_NEUNDEYO"), ("인데요", "C_NEUNDEYO"), ("고요", "C_GOYO"),
                          ("게요", "C_WILL"), ("세요", "C_SEYO"), ("나요", "C_Q"), ("가요", "C_Q")):
            if w.endswith(suf):
                return name
        if w.endswith(("죠", "지요")):
            return "C_JYO"
        if re.search(r"수\s*있어요$", tail):
            return "C_CAN"
        if w.endswith(("있어요", "없어요")):
            return "C_EXIST"
        if w.endswith(("거예요", "거에요")):
            return "C_GEO"
        if w.endswith(("이에요", "예요", "이에요", "에요")):
            return "C_COP"
        if len(w) >= 3 and w.endswith(("어요", "아요")) and _jong(w[-3]) == JONG_SS and w[-3] not in "있겠":
            return "C_PAST"
        return "C_PRES"
    return cls


# ---------------------------------------------------------------- commas, enumerations

CONNECTIVE_SUFFIXES = ("면서도", "으면서", "면서", "지만", "는데", "은데", "인데", "던데", "으며", "며",
                       "니까", "므로", "도록", "더라도", "다가", "거나", "든지", "려고", "다면", "라면",
                       "으면", "면", "고서", "고", "서")
GO_STOP = ("참고", "최고", "보고", "경고", "광고", "사고", "재고", "창고", "원고", "신고", "라고", "다고",
           "자고", "냐고", "제고", "등고")
MYEON_STOP = ("측면", "반면", "화면", "표면", "전면", "단면", "국면", "방면", "장면", "정면", "평면", "이면",
              "내면", "지면", "대면", "직면", "수면", "후면", "앞면", "뒷면", "한편")
SEO_VOWELS = {0, 1, 4, 6, 9, 10, 14}  # ㅏ ㅐ ㅓ ㅕ ㅘ ㅙ ㅝ
SENT_ADVERBS = ("그리고", "그러나", "그런데", "그러므로", "하지만", "그래서", "따라서", "그러니까", "또한",
                "반면", "즉", "특히", "다만", "예를", "결과적으로", "한편", "게다가", "물론", "아울러", "덧붙여")
G7_ADVERBS = ("그리고", "그러나", "그런데", "그러므로", "하지만", "그래서", "따라서")


def is_connective(word):
    if len(word) < 2 or not HANGUL_RE.match(word[-1]):
        return False
    for suf in CONNECTIVE_SUFFIXES:
        if not word.endswith(suf):
            continue
        if suf == "고" and word.endswith(GO_STOP):
            return False
        if suf == "면" and word.endswith(MYEON_STOP):
            return False
        if suf == "서":
            if word.endswith(("에서", "께서")):
                return False
            prev = word[-2]
            if _jong(prev) != 0 or _jung(prev) not in SEO_VOWELS:
                return False
        return True
    return False


DIGIT_COMMA_RE = re.compile(r"(?<=\d),(?=\d{3})")


def comma_count(masked):
    return len(re.findall(r"[,，]", DIGIT_COMMA_RE.sub("", masked)))


TRIAD_DATA_RE = re.compile(r"[0-9A-Za-z⟦]")


def is_triad(masked):
    """Counts rhetorical triads ("빠르고, 안정적이고, 확장 가능한").
    Enumerations containing figures, English names, or quotes carry over data from the source, so they are not counted."""
    s = DIGIT_COMMA_RE.sub("", masked)
    parts = [p.strip() for p in re.split(r"[,，]", s)]
    if len(parts) < 3:
        return False
    if any(TRIAD_DATA_RE.search(p) for p in parts[1:-1]) or TRIAD_DATA_RE.search(parts[0].split()[-1] if parts[0].split() else ""):
        return False
    return all(1 <= len(p.split()) <= 4 for p in parts[1:-1])


# ---------------------------------------------------------------- figures

# Approximate quantity words written without digits, such as "수십만 명", "수천 개", "몇백 건"
KO_APPROX_RE = re.compile(r"(?<![가-힣])(?:수|몇)(?:십|백|천)?(?:만|억|조)?(?<=[십백천만억조])(?!큼)")
# "수만" in "요청 수만 줄였습니다" is "수" (a count) plus the particle "만". With a noun before it and no unit after it,
# it is not counted as an approximate quantity word.
KO_APPROX_UNIT_AFTER_RE = re.compile(
    r"\s?(?:[0-9A-Za-z]|(?:명|건|개|원|대|줄|번|회|곳|종|편|장|권|배|여|가지|시간|초|분|일|년|달|주|자|단어|토큰|행|쪽|바이트|달러)"
    r"(?:의|이|가|을|를|은|는|에|씩|도|만|과|와|으로|로)?(?![가-힣]))")


def ko_approx_hits(text):
    """Finds approximate quantity words in text. Excludes "수만" (count + particle "만") in the form noun + "수만" + verb."""
    hits = []
    for m in KO_APPROX_RE.finditer(text):
        if m.group(0) in ("수만", "몇만"):
            before, after = text[:m.start()], text[m.end():]
            if re.search(r"[가-힣]\s$", before) and not KO_APPROX_UNIT_AFTER_RE.match(after):
                continue
        hits.append(m.group(0))
    return hits


NUM_RE = re.compile(
    r"(?<![\w.\-])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"(\s*(?:%p|%|배|x|×|ms|초|분|시간|개|건|명|만|억|천|조|GB|MB|KB|TB|토큰|단어|문장|편|회|번|자|어절|쌍|년|점))?")


def extract_numbers(text):
    """List of (normalized value, original text). Single-digit integers without a unit are excluded (ordinal forms such
    as \"3단계\")."""
    out = []
    for m in NUM_RE.finditer(PH_RE.sub(" ", text)):
        ip, frac, unit = m.group(1), m.group(2), (m.group(3) or "").strip()
        key = ip.replace(",", "")
        if frac:
            frac = frac.rstrip("0")
            if frac:
                key += "." + frac
        if len(key) == 1 and not unit:
            continue
        out.append((key.lstrip("0") or "0", m.group(0).strip()))
    return out


def number_set(text):
    keys = set()
    for m in NUM_RE.finditer(text):
        ip, frac = m.group(1), m.group(2)
        key = ip.replace(",", "")
        if frac and frac.rstrip("0"):
            key += "." + frac.rstrip("0")
        keys.add(key.lstrip("0") or "0")
    return keys


# ---------------------------------------------------------------- analysis

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-⛿✀-➿⭐⭕‼⁉]")
# Punctuation policy (G6). Counts the em dash family, spaced hyphens used in place of a dash, the middle dot family, en
# dashes, and minus signs.
EMDASH_CHAR_RE = re.compile("[—―]")
SPACED_HYPHEN_RE = re.compile(r"[가-힣][)\]'\"”’]?\s+-{1,2}\s+\S|\S\s+-{1,2}\s+[가-힣]")
POLICY_CHAR_RE = re.compile("[·•‧∙・･–‒−]")
PAGE_RANGE_RE = re.compile(r"\d\s?[–‒—―−]\s?\d")
# Heading of a references section. A section counts as references only when the whole heading consists of words meaning
# references ("데이터 출처와 전처리" and "참고할 설정" are body sections).
REF_STRONG = r"(?:참고|레퍼런스|references?|bibliography|출처|각주|(?:더\s*)?읽을\s*거리)"
REF_HEADING_RE = re.compile(r"^\s*(?:\d+[.)]?\s*)?(?=.*" + REF_STRONG + r")"
                            r"(?:(?:" + REF_STRONG + r"|자료|문헌|링크|links?|및|and|&|/|,)\s*)+:?\s*$", re.I)
QUESTION_HEADING_RE = re.compile(r"(\?|을까|를까|할까|일까|될까|볼까|까요|나요|는가|인가)$")

# Particle after a number (G10). Chooses the particle that matches the final consonant of the last digit as read in
# Korean.
NUM_PARTICLE_RE = re.compile(
    r"(?<![\w.,\-/@])(\d[\d,]*(?:\.\d+)?)(%p|%)?"
    r"(?:(이에요|예요|이|가|을|를|은|는|과|와|으로|로)(?=[\s.,?!:;)\]」』”’\"']|$)|(였)(?=[가-힣]))")
# A number right after a word made only of Latin letters and digits is treated as a name or version read in English and
# is skipped (Llama 3, Windows 11).
LATIN_TOKEN_BEFORE_RE = re.compile(r"(?:^|\s)[A-Za-z][A-Za-z0-9.+\-]*\s$")
DIGIT_FINAL = {"0": "ㅇ", "1": "ㄹ", "2": "", "3": "ㅁ", "4": "", "5": "", "6": "ㄱ", "7": "ㄹ", "8": "ㄹ", "9": ""}
PARTICLE_ALT = {"이에요": "예요", "예요": "이에요", "이": "가", "가": "이", "을": "를", "를": "을", "은": "는",
                "는": "은", "과": "와", "와": "과", "으로": "로", "로": "으로", "였": "이었"}

# Paired terms (A19). Collects "Korean(original)" and "original(Korean)" pairs.
TERM_KE_RE = re.compile(r"((?:[가-힣]{1,12} )?[가-힣]{2,12}) ?\(([A-Za-z][A-Za-z0-9 .'\-]{0,40}[A-Za-z0-9.]|[A-Za-z])\)")
TERM_EK_RE = re.compile(r"(?<![A-Za-z0-9_\-])([A-Za-z][A-Za-z0-9.\-]*(?: [A-Za-z][A-Za-z0-9.\-]*){0,3})"
                        r" ?\(([가-힣]+(?: [가-힣]+)?)\)")
ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9]{1,6}s?$")
IDENTIFIER_RE = re.compile(r"[a-z][A-Z]|\d|_")  # Identifiers such as sessionID, Q10, max_tokens are not term pairs
GLOSS_PARTICLE_RE = re.compile(r"(을|를|은|는|이|가|의|에|로|와|과|하는|되는|한|된|여|고|서|며|면|게|어|아)$")
PHRASE_END_RE = re.compile(r"(에서도|에서|에는|에게|으로|까지|부터|처럼|하는|되는|하고|이고|[가-힣]{2}(?:은|는|을|를|이|가|의|에|와|과))$")
PAREN_RE = re.compile(r"\([^()]*\)")
KO_PARTICLES = r"(?:에서는|에서도|에서|에는|으로|처럼|보다|까지|부터|은|는|이|가|을|를|의|에|과|와|도|만|로)"

# Explanation of first-appearing terms (A20). Finds scientific names ("C. elegans", italic "*Cancer borealis*") and
# uppercase abbreviations.
SPECIES_ABBR_RE = re.compile(r"(?<![A-Za-z0-9_.])[A-Z]\.\s[a-z]{3,}(?![A-Za-z])")
SPECIES_ITALIC_RE = re.compile(r"(?<![*_A-Za-z0-9])[*_]([A-Z][a-z]+ [a-z]{3,})[*_](?![*_A-Za-z0-9])")
LATIN_PHRASES = frozenset(("In vivo", "In vitro", "In silico", "In situ", "Ex vivo", "De novo"))
ABBR_RE = re.compile(r"(?<![A-Za-z0-9_\-])[A-Z]{2}[A-Z0-9]{0,5}(?![A-Za-z0-9_\-])")
# Uppercase words not shown as candidates even without a full name on first appearance. The reader is not assumed to be
# a developer, so field abbreviations such as API, CPU, HTTP are not listed (a reader who may lack knowledge of the
# source's field does not know these abbreviations either).
# GENERAL_ABBR: abbreviations and company names that people who have not studied the field encounter in daily life and
# the news without explanation
GENERAL_ABBR = frozenset((
    "AI", "IT", "PC", "TV", "USB", "PDF", "DNA", "CEO", "SNS", "GPS", "ID", "OK", "ON", "OFF", "FAQ", "CCTV", "LED",
    "QR", "SMS", "MRI", "CT", "ATM", "VR", "GPT", "AMD", "IBM", "NVIDIA", "LG", "SK", "KT"))
# CODE_WORDS: words written in uppercase that are not abbreviations (SQL and HTTP keywords, log levels), storage units,
# time zones, Roman numerals
CODE_WORDS = frozenset((
    "ALTER", "AND", "AS", "ASC", "BY", "CREATE", "DELETE", "DESC", "DISTINCT", "DROP", "EXISTS", "FALSE", "FORCE",
    "FROM", "GET", "GROUP", "HAVING", "HEAD", "IN", "INDEX", "INNER", "INSERT", "INTO", "IS", "JOIN", "LEFT", "LIKE",
    "LIMIT", "NOT", "NULL", "OFFSET", "OPTIONS", "OR", "ORDER", "OUTER", "PATCH", "POST", "PUT", "RIGHT", "SELECT",
    "SET", "TABLE", "TEXT", "TRUE", "UNION", "UNIQUE", "UPDATE", "VALUES", "WHERE", "WITH",
    "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TODO",
    "KB", "MB", "GB", "TB", "PB", "KST", "UTC", "GMT",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"))
COMMON_ABBR = GENERAL_ABBR | CODE_WORDS
DESC_SKIP = ("-", "—", "없음")

# Subject that does not name its source (A18.bare_author). Checked only when the body cites two or more studies.
WORK_CITE_RE = re.compile(
    r"([A-Z][A-Za-z'’\-]+)(?:\s+(?:et\s+al\.|등|외)|\s*(?:&|and)\s*[A-Z][A-Za-z'’\-]+)?\s*\(\s*((?:19|20)\d{2})[a-z]?\s*\)"
    r"|([A-Z][A-Za-z'’\-]+)\s+et\s+al\."
    r"|([가-힣]{1,4})\s*(?:등|외)\s*\(\s*((?:19|20)\d{2})[a-z]?\s*\)")
# An author name followed by a particle ("Cornelia Bargmann과 Eve Marder는", "Marder는") also counts as naming the study.
NAMED_SOURCE_RE = re.compile(r"[A-Z][a-z]{2,}(?:\s+(?:et\s+al\.|등))?(?:은|는|이|가|과|와|의|도)(?=[\s,]|$)")
# "연구진", "연구팀", "이 연구", "이 논문", "원문" are checked only at the start of a sentence ("Facebook의 AI 연구팀이" has a
# name).
BARE_AUTHOR_RE = re.compile(r"(?:^|[\s(])((?:저자들?|세\s저자|두\s저자|네\s저자|같은\s연구|같은\s논문|같은\s글|두\s글)"
                            r"(?:은|는|이|가|도))\s|^((?:연구진|연구팀|이\s연구|이\s논문|원문)(?:은|는|이|가|도))\s")


class Sentence:
    __slots__ = ("text", "masked", "kind", "block", "para", "line", "first", "last",
                 "word", "cls", "bucket", "question", "in_refs")


def _compile_patterns(spec):
    compiled = {}
    for pid, p in spec["patterns"].items():
        compiled[pid] = {
            "title": p.get("title", pid),
            "scope": p.get("scope", "sentence"),
            "max_len": p.get("max_len"),
            "hint": p.get("hint", ""),
            "raw": bool(p.get("raw")),
            "headings": bool(p.get("headings")),
            "tables": bool(p.get("tables")),
            "regex": [re.compile(r) for r in p["regex"]],
        }
    return compiled


def _hit(sent, match=None):
    h = {"line": sent.line, "text": sent.text[:160]}
    if match is not None:
        h["match"] = match
    return h


def same_predicate_adjacent_hits(paragraphs):
    """Review candidates: adjacent declarative sentences in the same paragraph that end in the same last word.

    Compares surface words, not morphological analysis or the ending distribution (C_PRES etc.). So it also flags
    '점도 들어요' and '라고도 말해요', but does not judge verbs with different conjugations or repetition within a sentence.
    Two sentences separated by a question, command, noun phrase, or quote are not paired across it.
    """
    hits = []
    for sentences in paragraphs:
        previous, previous_word = None, None
        for sent in sentences:
            # Inline quotes, code, and link URLs do not count as predicates. Link display text and emphasis markers are
            # handled in clean_inline; this also strips a leftover opening marker of underscore emphasis.
            word = last_word(sent.masked).lstrip("*_~")
            cls = classify_ending(word, sent.question)
            declarative = (not sent.in_refs and not sent.question
                           and cls in ("HAPNIDA", "HAEYO", "HAERA")
                           and not word.endswith(("십시오", "세요", "시다", "니까"))
                           and bool(re.fullmatch(r"[가-힣]+", word)))
            if declarative and previous_word == word:
                hit = _hit(sent, word)
                hit["previous"] = _hit(previous)
                hits.append(hit)
            previous, previous_word = sent, word if declarative else None
    return hits


def _unit_hit(line, text, target, m):
    """A location found in a non-sentence unit (heading, table row, block). match includes eight characters on each side."""
    a, b = max(0, m.start() - 8), min(len(target), m.end() + 8)
    return {"line": line, "text": text[:160], "match": target[a:b].strip()}


def punct_hits(blocks):
    """Counts punctuation policy (G6) violations. Checks headings, paragraphs, lists, quotes, and table cells; excludes
    code, inline code, math, and URLs. In a references section only dashes between numbers (page ranges) are counted.
    Returns: (em dash family, middle dots with en dashes and minus signs)."""
    emdash, policy = [], []
    in_refs = False
    for b in blocks:
        if b.type == "heading":
            text = clean_inline(b.text)[0]
            in_refs = bool(REF_HEADING_RE.search(text)) and b.level >= 2
            units = [(b.line, text)]
        elif b.type in ("paragraph", "list_item", "blockquote"):
            units = [(b.line, clean_inline(b.text)[0])]
        elif b.type == "table":
            units = [(b.line + k, clean_inline(row)[0]) for k, row in enumerate(b.text.split("\n"))
                     if not TABLE_DELIM_RE.match(row)]
        else:
            continue
        for line, text in units:
            target = mask_math(text)
            if in_refs and b.type != "heading":
                policy += [_unit_hit(line, text, target, m) for m in PAGE_RANGE_RE.finditer(target)]
                continue
            emdash += [_unit_hit(line, text, target, m) for m in EMDASH_CHAR_RE.finditer(target)]
            emdash += [_unit_hit(line, text, target, m) for m in SPACED_HYPHEN_RE.finditer(target)]
            policy += [_unit_hit(line, text, target, m) for m in POLICY_CHAR_RE.finditer(target)]
    return emdash, policy


def particle_mismatch(final, particle):
    """final is the final consonant of the last sound ("" means none). True if the particle does not match it."""
    if particle in ("이에요", "이", "을", "은", "과"):
        return not final
    if particle in ("예요", "가", "를", "는", "와", "였"):
        return bool(final)
    if particle == "으로":
        return not final or final == "ㄹ"
    if particle == "로":
        return bool(final) and final != "ㄹ"
    return False


def num_particle_hits(units):
    """units: (line number, original text, sentence with quotes masked). Finds particles right after a number, %, or %p
    that do not match how the number is read."""
    hits = []
    for line, text, masked in units:
        target = mask_math(masked)
        for m in NUM_PARTICLE_RE.finditer(target):
            if LATIN_TOKEN_BEFORE_RE.search(target[:m.start()]):
                continue
            particle = m.group(3) or m.group(4)
            final = "" if m.group(2) else DIGIT_FINAL[m.group(1)[-1]]
            if particle_mismatch(final, particle):
                fix = m.group(1) + (m.group(2) or "") + PARTICLE_ALT[particle]
                hits.append({"line": line, "text": text[:160], "match": f"{m.group(0)} → {fix}"})
    return hits


def term_pairs(text):
    """Finds paired terms in one sentence. Returns: (form in the body, form in parentheses, whether the parenthesized
    form is English, position)."""
    out = []
    for m in TERM_KE_RE.finditer(text):
        ko, en = m.group(1), m.group(2).strip()
        words = ko.split(" ")
        if len(words) == 2 and GLOSS_PARTICLE_RE.search(words[0]):
            ko = words[1]  # In "이 글의 망막(retina)" the preceding word is not part of the term
        if ACRONYM_RE.match(en) or IDENTIFIER_RE.search(en) or len(en.split()) > 3 or PHRASE_END_RE.search(ko):
            continue  # Abbreviation definition ("다중 버전 동시성 제어(MVCC)"), identifier, original of a phrase ("시냅스 밖에서도(extrasynaptic)")
        out.append((ko, en, True, m.span()))
    for m in TERM_EK_RE.finditer(text):
        en, ko = m.group(1).strip(), m.group(2).strip()
        if ACRONYM_RE.match(en) or IDENTIFIER_RE.search(en) or any(GLOSS_PARTICLE_RE.search(w) for w in ko.split(" ")):
            continue  # Abbreviations, identifiers, and glosses ("attention(주의를 기울이는)") are not term pairs
        out.append((en, ko, False, m.span()))
    return out


def _latin_term_re(term):
    # Compounds with another English word (cache in "KV cache") are not counted separately.
    return re.compile(r"(?<![A-Za-z0-9_\-])(?<![A-Za-z0-9] )" + re.escape(term) + r"(?! ?[A-Za-z0-9_\-])", re.I)


def _hangul_term_re(term):
    # Counts only words followed by a particle or punctuation. Words placed before another noun, as in "흥분성 뉴런" and
    # "인접 행렬", may be compounds for a different concept, so they are not counted.
    return re.compile(r"(?<![가-힣])" + re.escape(term) + r"(?:" + KO_PARTICLES + r"|(?![가-힣])(?!\s[가-힣]))")


def term_mix_hits(units, max_hits=5):
    """units: (line number, original text, sentence with quotes masked). If both forms of a pair appear again outside the
    pairing (outside parentheses), shows them as a candidate for one concept written in two forms. Parenthesized text is
    an original term, abbreviation expansion, or unit conversion, so it is not counted."""
    pairs = []
    cleaned = []
    for line, text, masked in units:
        found = term_pairs(masked)
        pairs += [(main, alt, alt_latin, line) for main, alt, alt_latin, _ in found]
        cleaned.append((line, text, PAREN_RE.sub(" ", masked)))
    hits, seen = [], set()
    for main, alt, alt_latin, pair_line in pairs:
        key = (main.lower(), alt.lower())
        if key in seen:
            continue
        seen.add(key)
        rx_alt = _latin_term_re(alt) if alt_latin else _hangul_term_re(alt)
        rx_main = _hangul_term_re(main) if alt_latin else _latin_term_re(main)
        alt_where = [(line, text) for line, text, c in cleaned if rx_alt.search(c)]
        main_where = [line for line, _, c in cleaned if rx_main.search(c)]
        if alt_where and main_where:
            hits.append({"line": alt_where[0][0], "text": alt_where[0][1][:160],
                         "match": f"{main}({alt}) L{pair_line}: 괄호 밖에서 «{main}» {len(main_where)}문장, "
                                  f"«{alt}» {len(alt_where)}문장"})
        if len(hits) >= max_hits:
            break
    return hits


def avoid_terms(facts_text):
    """Collects words from the "쓰지 않을 표기" column of the fact sheet's term table. Empty list if there is no table."""
    terms = []
    lines = facts_text.split("\n")
    for i, ln in enumerate(lines):
        if "|" not in ln or "쓰지 않을" not in ln:
            continue
        header = [c.strip() for c in ln.strip().strip("|").split("|")]
        col = next(j for j, c in enumerate(header) if "쓰지 않을" in c)
        for row in lines[i + 1:]:
            if "|" not in row:
                break
            if TABLE_DELIM_RE.match(row):
                continue
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if col < len(cells):
                for t in re.split(r"[,，;]", cells[col]):
                    t = t.strip().strip("`\"'“”‘’ ")
                    if t and t not in ("-", "없음", "—") and (len(t) >= 2 or re.fullmatch(r"[A-Za-z]+", t)):
                        terms.append(t)
    return terms


def term_avoid_hits(units, terms, max_hits=10):
    """Places where a form the fact sheet decided not to use appears outside parentheses."""
    hits = []
    for term in terms:
        latin = re.fullmatch(r"[A-Za-z0-9 .'\-]+", term) is not None
        # Korean forms decided against are counted even inside compounds ("보고자 유전자").
        rx = _latin_term_re(term) if latin else re.compile(r"(?<![가-힣])" + re.escape(term))
        for line, text, masked in units:
            if rx.search(PAREN_RE.sub(" ", masked)):
                hits.append({"line": line, "text": text[:160], "match": term})
                break
        if len(hits) >= max_hits:
            break
    return hits


TERM_TABLE_HEADER = "글에 쓸 표기"
TERM_SPLIT_RE = re.compile(r"\s+/\s+|\s*[,，;]\s*")


def term_table_rows(facts_text):
    """Rows of the fact sheet's term table. Reads only tables whose header has "글에 쓸 표기" (excludes "글에 쓸 표현" in the
    estimate-phrase table). Returns: list of (fact sheet line number, header cells, row cells)."""
    rows = []
    lines = facts_text.split("\n")
    i = 0
    while i < len(lines):
        if "|" in lines[i] and TERM_TABLE_HEADER in lines[i]:
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            j = i + 1
            while j < len(lines) and "|" in lines[j]:
                if not TABLE_DELIM_RE.match(lines[j]):
                    rows.append((j + 1, header, [c.strip() for c in lines[j].strip().strip("|").split("|")]))
                j += 1
            i = j
        else:
            i += 1
    return rows


def _col(header, key):
    return next((j for j, c in enumerate(header) if key in c), None)


def _cell(cells, j):
    return cells[j] if j is not None and j < len(cells) else ""


def split_terms(cell):
    """Terms in a "글에 쓸 표기" cell. Removes parentheses ("C. elegans(예쁜꼬마선충)") and splits terms combined in one row
    ("수평 세포 / 양극 세포 / amacrine 세포", "tonic spiking, burst"). Excludes pieces longer than four words."""
    out = []
    for part in TERM_SPLIT_RE.split(PAREN_RE.sub("", cell)):
        part = part.strip().strip("`\"'“”‘’ ")
        if part and part not in DESC_SKIP and len(part.split()) <= 4 and part not in out:
            out.append(part)
    return out


def described_terms(facts_text):
    """Collects the "글에 쓸 표기" of terms that have an explanation in the "처음 나올 때 설명" column of the fact sheet's term
    table. Excludes terms in a table with no explanation column and terms marked "설명하지 않음"."""
    terms = []
    for _, header, cells in term_table_rows(facts_text):
        desc = _cell(cells, _col(header, "설명"))
        if not desc or desc in DESC_SKIP or desc.startswith("설명하지 않"):
            continue
        for term in split_terms(_cell(cells, _col(header, "글에 쓸"))):
            if term not in terms:
                terms.append(term)
    return terms


def combined_row_hits(facts_text):
    """Rows of the term table that combine several terms (A20.table_combined_row). A combined row cannot state different
    characteristics per term, and searching for the whole combined cell as one term finds nothing in the body. Line
    number 0 in a hit means the fact sheet."""
    hits = []
    for n, header, cells in term_table_rows(facts_text):
        cell = _cell(cells, _col(header, "글에 쓸"))
        if len(split_terms(cell)) > 1:
            hits.append({"line": 0, "text": f"fact sheet {n}줄: {cell}"[:160], "match": cell})
    return hits


def strip_general_knowledge(facts_text):
    """The fact sheet with explanation cells emptied where the term table's basis is "일반 지식". General-knowledge
    explanations do not use figures, so A15 does not treat figures in those cells as figures from the source."""
    lines = facts_text.split("\n")
    for n, header, cells in term_table_rows(facts_text):
        j = _col(header, "설명")
        if j is not None and j < len(cells) and "일반 지식" in cells[j]:
            cells = list(cells)
            cells[j] = ""
            lines[n - 1] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines)


def _term_re(term):
    if re.fullmatch(r"[A-Za-z0-9 .'\-]+", term):
        return _latin_term_re(term)
    if re.match(r"[A-Za-z]", term):
        # Occurrences attached to another English word, such as "amacrine 세포" in "starburst amacrine 세포", are not counted.
        return re.compile(r"(?<![A-Za-z0-9_\-])(?<![A-Za-z0-9] )" + re.escape(term), re.I)
    return re.compile(r"(?<![가-힣])" + re.escape(term))


def term_first_hits(units, terms):
    """units: (line number, original text, sentence with quotes masked). The sentence where a term with an explanation in
    the fact sheet first appears in the body. Whether an explanation is present can be known only by reading the sentence,
    so it is shown even with parentheses. Terms first appearing in the same sentence are combined on one line.
    The first version of this rule showed only the first 10 (and printed only 5 of those), so terms in later sections
    did not reach the check list."""
    first = {}
    for term in terms:
        rx = _term_re(term)
        for idx, (_, _, masked) in enumerate(units):
            if rx.search(masked):
                first.setdefault(idx, []).append(term)
                break
    return [{"line": units[idx][0], "text": units[idx][1][:160], "match": ", ".join(first[idx])}
            for idx in sorted(first)]


# Fragments of file names ("index.wasm") and LaTeX commands ("\mathbb") are not counted as English runs.
LATIN_RUN_RE = re.compile(r"(?<![A-Za-z0-9_\-'.\\])[A-Za-z][A-Za-z\-']*(?: [A-Za-z][A-Za-z\-']*)*"
                          r"(?![A-Za-z0-9_\-]|\.[A-Za-z0-9])")
# English runs are not counted in a sentence with more than three math symbols (math written without dollar signs).
MATH_SYMBOL_RE = re.compile(r"[=∼∣∑∏√≤≥∈⋅∥ϵθπρϕ^{}\\]")
LATIN_STOP = frozenset(("et al", "vs", "etc", "e.g", "i.e", "cf"))
LATIN_PHRASES_LOWER = frozenset(p.lower() for p in LATIN_PHRASES)


def latin_runs(masked, skip_names=()):
    """Runs of consecutive English words in a sentence (lowercased). Excludes parenthesized text, author (year) citations,
    scientific names, uppercase abbreviations, runs where every word starts with a capital such as person and organization
    names, and runs of two characters or fewer. skip_names: italic scientific names and names in the references section."""
    if len(MATH_SYMBOL_RE.findall(masked)) > 3:
        return []
    text = PAREN_RE.sub(" ", masked)
    text = WORK_CITE_RE.sub(" ", text)
    text = SPECIES_ABBR_RE.sub(" ", text)
    out = []
    for m in LATIN_RUN_RE.finditer(text):
        whole = m.group(0).strip(" -'")
        if whole in skip_names:
            continue
        # Splits runs at uppercase abbreviation words (PVC in "interneuron PVC"). A20.abbr_first checks abbreviations.
        groups, cur = [], []
        for w in whole.split():
            if re.fullmatch(r"[A-Z][A-Z0-9]+", w):
                groups.append(cur)
                cur = []
            else:
                cur.append(w)
        groups.append(cur)
        for words in groups:
            run = " ".join(words).strip(" -'")
            if (len(run) <= 2 or run.lower() in LATIN_STOP or run.lower() in LATIN_PHRASES_LOWER
                    or run in skip_names):
                continue
            if all(re.fullmatch(r"[A-Z][a-z]+", w) for w in words):
                continue
            if any(w in skip_names for w in words if w[:1].isupper()):
                continue
            out.append(run.lower())
    return out


def table_latin_vocab(facts_text):
    """English runs (lowercased) in the term table's "원어", "글에 쓸 표기", and "쓰지 않을 표기" cells, including parenthesized
    text. A20.untabled uses this to check whether English words in the body are in the term table."""
    vocab = set()
    for _, header, cells in term_table_rows(facts_text):
        for key in ("원어", "글에 쓸", "쓰지 않을"):
            cell = _cell(cells, _col(header, key))
            for part in TERM_SPLIT_RE.split(cell.replace("(", " / ").replace(")", " ")):
                for m in LATIN_RUN_RE.finditer(part):
                    run = m.group(0).strip(" -'").lower()
                    if run:
                        vocab.add(run)
                        vocab.add(run[:-1] if run.endswith("s") else run + "s")
    return vocab


def untabled_hits(units, facts_text, skip_names=(), min_count=2):
    """English words appearing min_count or more times in the body that are not in the fact sheet's term table
    (A20.untabled). For a word not in the term table, no decision has been made on whether to explain it."""
    vocab = table_latin_vocab(facts_text)
    count, first = {}, {}
    for line, text, masked in units:
        for run in latin_runs(masked, skip_names):
            count[run] = count.get(run, 0) + 1
            first.setdefault(run, (line, text))
    hits = [{"line": first[r][0], "text": first[r][1][:160], "match": r}
            for r in count if count[r] >= min_count and r not in vocab]
    hits.sort(key=lambda h: h["line"])
    return hits


LIST_PRED_END_RE = re.compile(r"(?:다|요|고|며|서|면|지만|는데|니다|든지|거나)$")
LIST_ADNOMINAL_RE = re.compile(r"(?:하는|되는|있는|없는|하던|되던|한|된|적인)$")


def list_item_spans(masked):
    """Positions (start, end) of items in a comma-separated enumeration of more than three. Treated as an enumeration when
    the middle pieces have four words or fewer and do not end in a predicate. For the first piece only the last four
    words count as the item, and for the last piece only the first four words. Enumerations with one comma, such as
    "A, B와 C", are not checked."""
    parts, pos = [], 0
    for seg in masked.split(","):
        parts.append((pos, pos + len(seg), [m.span() for m in re.finditer(r"\S+", seg)]))
        pos += len(seg) + 1

    def inner(k):
        start, end, toks = parts[k]
        return len(toks) <= 4 and not LIST_PRED_END_RE.search(masked[start:end].strip())
    spans, i = [], 0
    while i < len(parts):
        j = i + 1
        while j < len(parts) - 1 and inner(j):
            j += 1
        if j - i >= 2:
            start, end, toks = parts[i]
            spans.append((start + (toks[-4][0] if len(toks) >= 4 else 0), end))
            spans += [parts[k][:2] for k in range(i + 1, j)]
            start, end, toks = parts[j]
            spans.append((start, start + toks[4][0] if len(toks) > 4 else end))
            i = j
        else:
            i += 1
    return spans


def term_in_list_hits(units, terms):
    """Terms that first appear in a sentence enumerating several items, do not appear in the very next sentence (no
    explanation at that point), and later appear alone outside an enumeration (A20.term_in_list). A Skill-Techblog 0.8.0
    run article introduced amacrine cells with one sentence listing five classes of retinal cells, then used amacrine
    cells alone as the subject in three later sentences."""
    hits = []
    blank = [PAREN_RE.sub(lambda p: " " * len(p.group(0)), masked) for _, _, masked in units]
    spans = [list_item_spans(b) for b in blank]
    for term in terms:
        rx = _term_re(term)
        occ = []
        for idx, b in enumerate(blank):
            m = rx.search(b)
            if m:
                occ.append((idx, m.start()))
        if len(occ) < 2:
            continue
        idx0, pos0 = occ[0]
        if not any(a <= pos0 < e for a, e in spans[idx0]):
            continue
        if occ[1][0] == idx0 + 1:
            continue
        # An item with a modifier, even inside an enumeration ("접촉을 감지하는 머리와 꼬리의 기계감각 뉴런"), is treated as
        # explained at that point.
        before = blank[idx0][:pos0].rsplit(",", 1)[-1].split()[-4:]
        if any(LIST_ADNOMINAL_RE.search(w) for w in before):
            continue
        alone = [units[i][0] for i, p in occ[1:] if not any(a <= p < e for a, e in spans[i])]
        if alone:
            more = ", ".join(f"L{n}" for n in alone[:4]) + (f" 외 {len(alone) - 4}개 문장" if len(alone) > 4 else "")
            hits.append({"line": units[idx0][0], "text": units[idx0][1][:160],
                         "match": f"{term}: 목록 L{units[idx0][0]}, 단독 {more}"})
    hits.sort(key=lambda h: h["line"])
    return hits


def species_first_hits(units, italic_names, max_hits=5):
    """The sentence where a scientific name first appears in the body. Even with parentheses, as in
    "C. elegans(예쁜꼬마선충)", whether they explain what it is can be known only by reading, so the sentence is shown
    regardless of parentheses. italic_names are scientific names written in italics ("Cancer borealis")."""
    hits, seen = [], set()
    italic_rx = [(n, re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])")) for n in italic_names]
    for line, text, masked in units:
        found = [(m.start(), re.sub(r"\s+", " ", m.group(0))) for m in SPECIES_ABBR_RE.finditer(masked)]
        found += [(m.start(), n) for n, rx in italic_rx for m in rx.finditer(masked)]
        for _, name in sorted(found):
            key = name.replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            hits.append({"line": line, "text": text[:160], "match": name})
    return hits[:max_hits]


def cited_works(sentences):
    """Number of studies appearing in the body as author (year) or "author et al.". Studies by the same author from
    different years are counted separately."""
    with_year, without_year = set(), set()
    for s in sentences:
        for m in WORK_CITE_RE.finditer(s.text):
            if m.group(1):
                with_year.add((m.group(1).lower(), m.group(2)))
            elif m.group(3):
                without_year.add(m.group(3).lower())
            else:
                with_year.add((m.group(4), m.group(5)))
    return len(with_year) + len(without_year - {name for name, _ in with_year})


def bare_author_hits(blocks, sentences, max_hits=10):
    """Places where the body cites two or more studies, a subject such as "저자들은", "세 저자는", "같은 논문은" does not say
    which study, and neither that sentence nor the one right before it names a study. If the sentence right before was
    resolved the same way, the sentence counts as continuing from it. A sentence before a heading, table, or code block
    does not count as the sentence right before."""
    body = [s for s in sentences if not s.in_refs]
    if cited_works(body) < 2:
        return []
    hits, prev, prev_ok = [], None, False
    for s in body:
        if prev is not None and any(blocks[k].type not in ("paragraph", "list_item")
                                    for k in range(prev.block + 1, s.block)):
            prev, prev_ok = None, False
        named = bool(WORK_CITE_RE.search(s.text) or NAMED_SOURCE_RE.search(s.masked))
        m = BARE_AUTHOR_RE.search(s.masked.lstrip())
        if m and not named:
            if not prev_ok:
                hits.append(_hit(s, m.group(1) or m.group(2)))
        else:
            prev_ok = named
        prev = s
    return hits[:max_hits]


SSEUDA_RE = re.compile(r"(?<![가-힣])(?:씁니다|써요|썼|쓴다|쓰고|쓰는|쓴\s|쓸\s|쓰면|쓰지|써서|써야|써도|쓰게|쓰려|쓰며)")
SSEUDA_USE_RE = re.compile(r"(?:을|를)\s+(?:\S+\s+){0,2}(?:씁니다|써요|썼|쓴다|쓰고|쓰는|쓴\s|쓸\s|쓰면|쓰지|써서|써야|써도|쓰게|쓰려|쓰며)"
                           r"|(?<![가-힣])쓸\s+수\s|(?<![가-힣])쓰는\s+(?:방법|방식|곳|값|도구)")


def sseuda_senses_hits(sentences, quote_rxs):
    """Places in one article where "쓰다" is used in both senses, '사용하다' and '자료의 말을 옮기다'. The second sense is "쓰다" in
    a sentence that matches the quoting-verb patterns (quote_rxs) or has author (year). The '사용하다' sense is "쓰다" with an
    object ("~를 썼어요") or "쓸 수". When both senses are present, shows the line numbers per sense on one line."""
    use, said = [], []
    for s in sentences:
        if s.in_refs or not SSEUDA_RE.search(s.masked):
            continue
        if any(rx.search(s.masked) for rx in quote_rxs) or WORK_CITE_RE.search(s.text):
            said.append(s)
        elif SSEUDA_USE_RE.search(s.masked):
            use.append(s)
    if not use or not said:
        return []

    def lines(group):
        out = ", ".join(f"L{s.line}" for s in group[:6])
        return out + (f" 외 {len(group) - 6}개 문장" if len(group) > 6 else "")
    return [{"line": said[0].line, "text": said[0].text[:160],
             "match": f"'사용하다' {len(use)}개 문장({lines(use)}), '자료 인용' {len(said)}개 문장({lines(said)})"}]


# Verbs in informational writing (A5.native_verbs). 130 human articles in "합니다체" from the reference period (2018~2022)
# used Sino-Korean verbs more often for the same sense ("사용하다" 2.93 times per 1,000 characters vs "쓰다" 0.30, "측정하다"
# 0.05 vs "재다" 0; evidence memo for A5.native_verbs in rubric.md).
# Counts only pairs where the native verb is used at 1/10 or less of the Sino-Korean verb. "넣다" (1/4.2 of "추가하다"),
# "바꾸다" (1/3.3 of "변경하다"), and "나오다" (1/3.6 of "나타나다·발생하다") are also common in human articles, so they are not
# counted; the Korean review (type R) chooses by the meaning of the sentence.
# Counts only frames that can distinguish the sense. "쓰다" with "글", "코드", "기록", or "시간" and "쓰다" for writing data to
# memory, disk, or blocks are not counted.
NV_WRITE_OBJ = ("글", "문서", "코드", "테스트", "메시지", "리뷰", "주석", "논문", "에세이", "책", "편지", "답장", "일기", "보고서",
                "기사", "블로그", "아티클", "포스트", "이름", "답", "소설", "노트", "README", "문장", "후기", "회고",
                "칼럼", "원고", "글자", "숫자", "공식", "수식", "식", "로그", "파일", "레코드", "데이터", "기록", "시간",
                "신경", "힘", "애", "돈", "비용", "예산", "마음", "모자", "안경", "마스크", "누명", "억지", "떼", "손",
                "머리", "가면", "우산", "답안", "보고", "설명", "결론", "말", "매뉴얼", "가이드", "명세", "스펙", "PRD", "RFC",
                "ADR", "기획서", "제안서", "프롬프트", "편", "log", "페이지", "위키", "티켓", "이슈", "일지", "근거", "케이스",
                "나절", "하루", "며칠", "주일", "개월")
# Fixed expressions placed before the verb without an object marker ("CPU Bound를 신경 쓰며", "인프라를 신경 쓰지 않고")
NV_IDIOM = ("신경", "손", "애", "힘", "머리", "마음", "떼", "억지")
# If the subject of passive "쓰이다" is one of these words, the sense is not '사용' ("시간의 상당수가 검토에 쓰입니다", "장애일지는 성실하게 쓰였고")
NV_PASSIVE_SUBJ = ("시간", "비용", "돈", "예산", "노력", "글", "문서", "일지", "일기", "기사", "논문", "책", "편지", "보고서",
                   "원고", "소설", "매뉴얼", "가이드", "답장", "후기", "회고", "칼럼")
NV_SSEUDA = re.compile(r"(?:씁니다|써요|썼(?:습니다|어요|다|고|으며|는데|지만|던|을)?|쓴다|쓰고|쓰는|쓴|쓸|쓰면|쓰지|써서|"
                       r"써야|써도|쓰게|쓰려|쓰며)")
# A storage location before the object ("logical block에 새 KV cache를 쓰려 하면") means the '기록하다' sense.
NV_STORE_AT = re.compile(r"(?:블록|block|메모리|memory|디스크|disk|버퍼|buffer|파일|캐시|cache|테이블|table|레지스터|register|"
                         r"스토리지|storage|DB|슬롯|slot|페이지|page|셀|칸|필드|컬럼|로그)(?:\s+\d+)?에(?:\s|$)")
NV_EXPR_TO = re.compile(r"(?:식|함수|형태|꼴|기호|표기|약어|이름|말|표현|문장|단어|한국어|영어|숫자|글|코드)(?:으로|로)$")
NV_PATTERNS = (
    ("재다", re.compile(r"(?<![가-힣])(?:잽니다|재요|쟀(?:습니다|어요|다|고|던|으며|는데|지만)?|잰다|재는|잰|잴|재면|재서|재야|재지|재려|"
                       r"재며)(?![가-힣])")),
    ("두다", re.compile(r"(?:(?<![\w.])\d[\d,.]*\s*(?:%|[A-Za-z]{1,3}|초|분|시간|개|배|번|바이트|자|줄|건|회)?|값|상수|"
                       r"(?<![A-Za-z])(?:true|false|True|False|null|None))(?:으로|로)\s+(?:둡니다|둬요|두어요|뒀(?:습니다|어요|다|고)?|두었(?:습니다|어요|다|고)?|둔다|두고|두는|둔|두면|"
                       r"둬서|두어서|둬야|두어야|두려|두며)(?![가-힣])|가정을\s+(?:둡니다|둬요|뒀|두었|둔다|두고|두는|둔|두면)(?![가-힣])")),
    ("고치다", re.compile(r"(?<![가-힣])(?:고칩니다|고쳐요|고쳤(?:습니다|어요|다|고|으며|는데|지만|던)?|고친다|고치고|고치는|고친|"
                         r"고칠|고치면|고치지|고쳐서|고쳐야|고치려|고치며)(?![가-힣])")),
    ("돌리다", re.compile(r"(?:테스트|코드|모델|실험|시뮬레이션|배치|작업|잡|스크립트|프로그램|쿼리|학습|벤치마크|파이프라인|크론|"
                         r"서버|노트북|셀|루프|빌드|job|cron|CI)(?:을|를)?\s+(?:\S+\s+){0,2}?돌(?:립니다|려요|렸(?:습니다|어요|다|고)?|"
                         r"린다|리고|리는|린|릴|리면|리지|려서|려야|려도|리려|리며)(?![가-힣])")),
    ("고르다", re.compile(r"(?<![가-힣])(?:고릅니다|골라요|골랐(?:습니다|어요|다|고|으며|는데|지만|던)?|고른다|고르고|고르는|"
                         r"고른(?!\s+(?:성능|분포|품질|수준|결과|성적|발전|성장|비율|값))|"
                         r"고를|고르면|골라서|골라야|고르려|고르며)(?![가-힣])")),
)
NV_SSEUDA_EXTRA = (
    # "쓸 수 있다/없다" (excludes nouns such as "쓰기 비율" and "~로 쓸 수")
    re.compile(r"(?<![가-힣])(?<!식으로\s)(?<!함수로\s)(?<!형태로\s)(?<!기호로\s)(?<!말로\s)(?<!표현으로\s)(?<!문장으로\s)"
               r"(?<!한국어로\s)(?<!영어로\s)(?<!글로\s)(?<!숫자로\s)(?<!읽고\s)쓸\s+수\s+(?:있|없)"),
    re.compile(r"(?<![가-힣])(?<!을\s)(?<!를\s)(?<!글\s)(?<!코드\s)(?<!문서\s)쓰는\s+(?:방법|방식|도구|경우|이유|곳|쪽)(?![가-힣])"),
    # Passive "쓰이다": "널리 쓰입니다", "~에 쓰이는". Excludes "Go로 쓰였습니다" (the language it is written in) and
    # "~라고 쓰여 있다" (written text).
    re.compile(r"(?<![가-힣])(?<![A-Za-z]로\s)(?<![A-Za-z]으로\s)(?<!고\s)(?:쓰입니다|쓰여요|쓰였(?:습니다|어요|다|고|으며|는데|지만|던)?|"
               r"쓰인다|쓰이는|쓰이고|쓰이며|쓰이면|쓰이지|쓰일)(?![가-힣])"),
)


def _modifies_written_text(toks, i):
    """True when an adnominal "쓰다" right after a subject modifies something written, possibly through bare modifiers:
    "사람이 쓴 글", "AI가 쓴 한국어 글", "사람이 쓴 기술 블로그 글". An object earlier in the sentence then belongs to
    another clause: "표현을 세어 사람이 쓴 글"."""
    if toks[i] not in ("쓰는", "쓴", "쓸", "쓰던") or i == 0 or not re.search(r"[이가]$", toks[i - 1]):
        return False
    for tok in toks[i + 1:i + 4]:
        if any(tok.startswith(w) for w in NV_WRITE_OBJ):
            return True
        if re.search(r"[은는이가을를에의도만로]$", tok):
            return False
    return False


def native_verb_hits(sentences):
    """Native Korean verbs in informational writing where human articles more often use Sino-Korean verbs
    (A5.native_verbs). Counted once per sentence.
    The '사용' sense of "쓰다" is identified by the object frame ("이 방법을 씁니다"), "쓸 수 있다", "쓰는 방법", and passive "쓰이다"."""
    hits = []
    for s in sentences:
        if s.in_refs:
            continue
        toks = s.masked.split()
        found = []
        for i, tok in enumerate(toks):
            m = NV_SSEUDA.match(tok)
            if not m or m.end() != len(tok.rstrip(".,?!")):
                continue
            counted = False
            if i + 1 < len(toks) and toks[i + 1].startswith("읽"):
                continue                                   # "쓰고 읽힐 수 있어야" (writing and reading)
            if _modifies_written_text(toks, i):
                continue
            for j in range(i - 1, max(-1, i - 4), -1):
                if (re.search(r"(?:에|에서|에게|고|라고|다고)$", toks[j]) or NV_EXPR_TO.search(toks[j])
                        or toks[j] in NV_IDIOM):
                    break
                if re.search(r"[을를]$", toks[j]):
                    obj = toks[j][:-1]
                    if (not any(obj.endswith(w) for w in NV_WRITE_OBJ)
                            and not NV_STORE_AT.search(" ".join(toks[max(0, j - 3):j]))):
                        found.append(tok)
                        counted = True
                    break
            # Adnominal form after a subject ("Orca가 쓰는 스케줄링"). Not counted if the modified word is something written,
            # such as "글" or "코드" ("사람이 쓴 글").
            if (not counted and tok in ("쓰는", "쓴", "쓸", "쓰던") and i > 0 and re.search(r"[이가]$", toks[i - 1])
                    and i + 1 < len(toks) and not any(toks[i + 1].startswith(w) for w in NV_WRITE_OBJ)):
                found.append(tok)
        for k, rx in enumerate(NV_SSEUDA_EXTRA):
            m = rx.search(s.masked)
            if m:
                before = s.masked[:m.start()].split()
                # If the word right before is the object of "쓰다", the sense is not '사용' ("손을 쓸 수 없을", "신경 쓸 수 없는")
                prev = (before or [""])[-1]
                bare = prev[:-1] if prev.endswith(("을", "를")) else prev
                if bare and (bare in NV_WRITE_OBJ or (bare != prev and any(bare.endswith(w) for w in NV_WRITE_OBJ))):
                    continue
                if k == len(NV_SSEUDA_EXTRA) - 1 and any(
                        re.search(r"(?:은|는|이|가|의)$", t) and re.sub(r"(?:은|는|이|가|의)$", "", t).endswith(NV_PASSIVE_SUBJ)
                        for t in before[-6:]):
                    continue
                found.append(m.group(0))
        for name, rx in NV_PATTERNS:
            m = rx.search(s.masked)
            if m:
                found.append(m.group(0).split()[-1])
        if found:
            hits.append(_hit(s, ", ".join(dict.fromkeys(found))))
    return hits


# "~라고 봅니다" conveying a judgment (A7.see_judgment). Human articles use it 0.01~0.03 times per 1,000 characters;
# Skill-Techblog 0.8.0 run articles used it 0.45 times.
SEE_JUDGMENT_RES = (
    re.compile(r"(?:다고|라고)\s*(?:봅니다|봐요|봤(?:습니다|어요|다|고|으며|는데|지만|던)?|본다|보았(?:습니다|어요|다|고)?|"
               r"보고(?![가-힣])(?!\s+(?:했|하|합|한|할|된|됐|되|드))|보는\s|봐야|보며|보지)"),
    re.compile(r"것으로\s+(?:봅니다|봐요|봤(?:습니다|어요|다|고|으며|는데|지만|던)?|본다|보았(?:습니다|어요|다|고)?|"
               r"보고(?![가-힣])(?!\s+(?:했|하|합|한|할|된|됐|되|드)))"),
    re.compile(r"(?:을|를)\s+(?:\S+\s+){0,3}?[^\s]*[가-힣](?:으로|로)(?<!그래프로)(?<!차트로)(?<!화면으로)(?<!그림으로)(?<!사진으로)"
               r"(?<!영상으로)(?<!로그로)(?<!눈으로)(?<!예로)(?<!표로)(?<!현미경으로)(?<!대시보드로)(?<!코드로)(?<!숫자로)(?<!수치로)"
               r"(?<!기준으로)\s+(?:봅니다|봐요|봤(?:습니다|어요|다|고)?|본다|보았(?:습니다|어요|다|고)?|"
               r"보고(?![가-힣])(?!\s+(?:했|하|합|한|할|된|됐|되|드))|보는\s|봐야)"),
)
# Adverbs that occur in the Y position of "X를 Y로 봅니다" ("영역을 주로 봅니다", "변경을 바로 봐야")
SEE_ADVERB_RO = ("주로", "새로", "따로", "서로", "별로", "제대로", "그대로", "실제로", "대체로", "바로", "스스로", "이대로",
                 "저절로", "절대로", "정말로", "때로", "함부로", "억지로", "멋대로", "마음대로", "임의로")


def see_judgment_hits(sentences):
    hits = []
    for s in sentences:
        if s.in_refs:
            continue
        m = next((m for rx in SEE_JUDGMENT_RES for m in rx.finditer(s.masked) if not _see_adverb(m.group(0))), None)
        if m:
            hits.append(_hit(s, m.group(0)))
    return hits


def _see_adverb(match):
    # If the Y position is an adverb or "-적으로" ("전체적으로 봤을 때"), the phrase does not convey a judgment
    ro = [t for t in match.split() if t.endswith("로")]
    return bool(ro) and (ro[-1] in SEE_ADVERB_RO or ro[-1].endswith("적으로"))


def abbr_first_hits(units, exclude=(), min_count=3, max_hits=None):
    """Sentences where an uppercase abbreviation appearing min_count or more times in the body first appears without
    parentheses. Not counted if parentheses follow right after, as in "STG(stomatogastric ganglion)", or if it first
    appears inside parentheses, as in "stomatogastric ganglion(STG)". Common abbreviations (COMMON_ABBR) and exclude
    (terms in the term table) are not counted either.
    The count is not truncated. Output is reduced according to the compact setting in thresholds.json."""
    counts, first = {}, {}
    for line, text, masked in units:
        for m in ABBR_RE.finditer(masked):
            a = m.group(0)
            counts[a] = counts.get(a, 0) + 1
            if a not in first:
                before = masked[:m.start()]
                in_paren = before.count("(") > before.count(")")
                after_paren = masked[m.end():m.end() + 2].lstrip().startswith("(")
                first[a] = (line, text, in_paren or after_paren)
    skip = COMMON_ABBR | {e.upper() for e in exclude}
    hits = [{"line": first[a][0], "text": first[a][1][:160], "match": a}
            for a in first if counts[a] >= min_count and a not in skip and not first[a][2]]
    hits.sort(key=lambda h: h["line"])
    return hits if max_hits is None else hits[:max_hits]


def analyze(text, patterns_spec=None, facts_text=None):
    """Analyzes an article and returns raw metric values and evidence sentences. evaluate() makes the threshold verdict."""
    if patterns_spec is None:
        patterns_spec = load_json(PATTERNS_PATH)
    patterns = _compile_patterns(patterns_spec)
    text = normalize_text(text)
    blocks = parse_blocks(text)

    sentences = []
    headings = []
    list_items = []
    para_sents = []  # list of sentences per paragraph
    bold = 0
    prose_chars = 0
    list_chars = 0
    in_refs = False
    emoji_hits = []
    semicolon_hits = []
    # Headings and table rows: (line number, original text, text with quotes masked). Used by the patterns' headings and
    # tables options and by the Korean review items.
    heading_units = []
    table_units = []

    for bi, b in enumerate(blocks):
        if b.type == "heading":
            clean, bcount, _ = clean_inline(b.text)
            headings.append({"level": b.level, "text": clean, "line": b.line})
            in_refs = bool(REF_HEADING_RE.search(clean)) and b.level >= 2
            heading_units.append((b.line, clean, mask_quotes(clean)))
            if EMOJI_RE.search(clean):
                emoji_hits.append({"line": b.line, "text": clean[:160]})
            continue
        if b.type == "table" and not in_refs:
            for k, row in enumerate(b.text.split("\n")):
                if TABLE_DELIM_RE.match(row):
                    continue
                cells = [clean_inline(c)[0] for c in row.strip().strip("|").split("|")]
                row_text = " | ".join(c for c in cells if c)
                table_units.append((b.line + k, row_text, mask_quotes(row_text)))
            continue
        if b.type not in ("paragraph", "list_item"):
            continue
        clean, bcount, _ = clean_inline(b.text)
        if not clean:
            continue
        bold += bcount
        chars = visible_chars(clean)
        if b.type == "list_item":
            list_items.append({"line": b.line, "text": clean, "raw": b.text, "list_id": b.list_id,
                               "depth": b.depth})
            list_chars += chars
        prose_chars += chars
        if EMOJI_RE.search(clean):
            emoji_hits.append({"line": b.line, "text": clean[:160]})
        if not in_refs and ";" in PH_RE.sub("", clean):
            semicolon_hits.append({"line": b.line, "text": clean[:160]})
        parts = split_sentences(clean)
        block_sents = []
        for si, st in enumerate(parts):
            s = Sentence()
            s.text = st
            s.masked = mask_quotes(st)
            s.kind = b.type
            s.block = bi
            s.para = len(para_sents) if b.type == "paragraph" else None
            s.line = b.line
            s.first = si == 0
            s.last = si == len(parts) - 1
            s.question = st.rstrip(CLOSERS + " ").endswith("?") and not s.masked.rstrip(" .").endswith(PH_QUOTE)
            s.word = last_word(st)
            s.cls = classify_ending(s.word, s.question)
            s.bucket = ending_bucket(st, s.word, s.cls)
            s.in_refs = in_refs
            block_sents.append(s)
            sentences.append(s)
        if b.type == "paragraph":
            para_sents.append(block_sents)

    body = [s for s in sentences if s.kind == "paragraph" or s.cls not in ("NOUN", "OTHER")]
    metrics = {}

    def put(mid, value, hits=None, **extra):
        metrics[mid] = {"value": value, "hits": hits or []}
        if extra:
            metrics[mid]["extra"] = extra

    # Pattern-based metrics. Scope "all" means every sentence, including noun-phrase list items.
    # raw patterns apply to the sentence before quotes are masked. With the headings or tables option they also apply to
    # headings and table rows.
    for pid, p in patterns.items():
        hits = []
        if p["scope"] == "para_last":
            pool = [ps[-1] for ps in para_sents if ps]
        elif p["scope"] == "paragraph":
            pool = [s for s in body if s.kind == "paragraph"]
        elif p["scope"] == "all":
            pool = [s for s in sentences if not s.in_refs]
        else:
            pool = body
        for s in pool:
            if p["max_len"] and len(s.text) > p["max_len"]:
                continue
            target = (s.text if p["raw"] else s.masked).lstrip()
            for rx in p["regex"]:
                m = rx.search(target)
                if m:
                    hits.append(_hit(s, m.group(0)))
                    break
        units = (heading_units if p["headings"] else []) + (table_units if p["tables"] else [])
        for line, raw_text, masked in units:
            target = raw_text if p["raw"] else masked
            for rx in p["regex"]:
                m = rx.search(target)
                if m:
                    hits.append({"line": line, "text": raw_text[:160], "match": m.group(0)})
                    break
        metrics[pid] = {"value": len(hits), "hits": hits}

    # A5.plain_terms is judged by count; A5.plain_terms_check shows all flagged sentences even within the threshold.
    metrics["A5.plain_terms_check"] = dict(metrics["A5.plain_terms"])

    # A14: Sentences already flagged for a quoted English word ("\"likely\"라고 적었어요") are not counted again in the
    # quoting-verb items.
    quoted = {(h["line"], h["text"]) for h in metrics["A14.quoted_english_token"]["hits"]}
    for pid in ("A14.report_write", "A14.report_write_check"):
        kept = [h for h in metrics[pid]["hits"] if (h["line"], h["text"]) not in quoted]
        metrics[pid] = {"value": len(kept), "hits": kept}

    # A5: Terms the source uses are not penalized
    if facts_text:
        for pid in ("A5.style_words",):
            kept = []
            for h in metrics[pid]["hits"]:
                stem = re.sub(r"(인|으로|하는\s*바|하|합|해|한|할|했|점|니다|요)$", "", h.get("match", ""))
                if stem and stem in facts_text:
                    continue
                kept.append(h)
            metrics[pid] = {"value": len(kept), "hits": kept}

    # Headings and title
    title = next((h for h in headings if h["level"] == 1), headings[0] if headings else None)
    title_text = title["text"] if title else ""
    np_rx = [rx for pid in ("A1.np_anira", "A1.np_rather", "A1.np_geuchi", "A1.np_neomeo",
                            "A1.np_deoisang", "A1.np_simple") for rx in patterns[pid]["regex"]]
    g8_rx = patterns["G8.beyond_simple"]["regex"]
    np_title = [{"line": title["line"], "text": title_text}] if title and any(rx.search(mask_quotes(title_text)) for rx in np_rx) else []
    for h in headings:
        if any(rx.search(mask_quotes(h["text"])) for rx in g8_rx):
            metrics["G8.beyond_simple"]["hits"].append({"line": h["line"], "text": h["text"]})
    metrics["G8.beyond_simple"]["value"] = len(metrics["G8.beyond_simple"]["hits"])
    put("A1.np_title", len(np_title), np_title)

    # A1: Negative parallelism (once per sentence) + the split-sentence form "X가 아닙니다. Y입니다."
    np_sents = set()
    for pid in ("A1.np_anira", "A1.np_rather", "A1.np_geuchi", "A1.np_neomeo", "A1.np_deoisang", "A1.np_simple"):
        for h in metrics[pid]["hits"]:
            np_sents.add((h["line"], h["text"]))
    cross = []
    for ps in para_sents:
        for a, b2 in zip(ps, ps[1:]):
            if re.search(r"(아닙니다|아니에요|아니다|않습니다|않아요)[.]?$", a.masked) and len(b2.text.split()) <= 12:
                cross.append(_hit(a, "X가 아닙니다. Y입니다."))
                np_sents.add((a.line, a.text))
    np_hits = [{"line": l, "text": t} for (l, t) in sorted(np_sents)]
    put("A1.np", len(np_hits), np_hits, cross=len(cross))
    first_para = para_sents[0] if para_sents else []
    np_first = [_hit(s) for s in first_para if (s.line, s.text) in np_sents]
    put("A1.np_first_para", len(np_first), np_first)
    same_para = []
    for ps in para_sents:
        c = [s for s in ps if (s.line, s.text) in np_sents]
        if len(c) >= 2:
            same_para.append(_hit(c[0]))
    put("A1.np_same_para", len(same_para), same_para)

    # G6, G7
    put("G6.emoji", len(emoji_hits), emoji_hits)
    put("G6.semicolon", len(semicolon_hits), semicolon_hits)
    emdash_hits, policy_hits = punct_hits(blocks)
    put("G6.emdash", len(emdash_hits), emdash_hits)
    put("G6.punct_policy", len(policy_hits), policy_hits)

    # G10 particle after a number, A19 paired terms. Checks the title, headings, and sentences outside references sections.
    ko_units = heading_units + [(s.line, s.text, s.masked) for s in sentences if not s.in_refs]
    num_hits = num_particle_hits(ko_units)
    put("G10.num_particle", len(num_hits), num_hits)
    mix_hits = term_mix_hits(ko_units)
    put("A19.term_mix", len(mix_hits), mix_hits)
    if facts_text is not None:
        avoid_hits = term_avoid_hits(ko_units, avoid_terms(facts_text))
        put("A19.term_avoid", len(avoid_hits), avoid_hits)

    # A20 explanation of first-appearing terms. Finds first appearances in body sentences (including list items),
    # excluding the title and headings.
    body_units = [(s.line, s.text, s.masked) for s in sentences if not s.in_refs]
    italic_names = []
    for b in blocks:
        if b.type in ("paragraph", "list_item"):
            for m in SPECIES_ITALIC_RE.finditer(b.text):
                if m.group(1) not in italic_names and m.group(1) not in LATIN_PHRASES:
                    italic_names.append(m.group(1))
    species = species_first_hits(body_units, italic_names)
    put("A20.species_first", len(species), species)
    described = described_terms(facts_text) if facts_text is not None else []
    # Capitalized words in the references section (authors, journal names) and italic scientific names are names, not
    # terms. Terms in paper titles such as "TANGO-mapping" are not names, so only words with just the first letter
    # capitalized are collected.
    skip_names = set(italic_names)
    for s in sentences:
        if s.in_refs:
            skip_names.update(re.findall(r"(?<![A-Za-z\-])[A-Z][a-z]+(?![A-Za-z\-])", s.text))
    if facts_text is not None:
        firsts = term_first_hits(body_units, described)
        put("A20.term_first", sum(len(h["match"].split(", ")) for h in firsts), firsts, sentences=len(firsts))
        combined = combined_row_hits(facts_text)
        put("A20.table_combined_row", len(combined), combined)
        untabled = untabled_hits(body_units, facts_text, skip_names)
        put("A20.untabled", len(untabled), untabled)
    latin = {}
    for _, _, masked in body_units:
        for run in latin_runs(masked, skip_names):
            latin[run] = latin.get(run, 0) + 1
    # English runs ("amacrine") inside term-table terms ("amacrine 세포") are not counted separately.
    in_described = {m.group(0).lower() for d in described for m in LATIN_RUN_RE.finditer(d)}
    listed = term_in_list_hits(body_units, described + [r for r, c in latin.items() if c >= 2
                                                      and r not in in_described])
    put("A20.term_in_list", len(listed), listed)
    abbrs = abbr_first_hits(body_units, exclude=described)
    put("A20.abbr_first", len(abbrs), abbrs)

    # A18 subjects that do not name their source
    authors = bare_author_hits(blocks, sentences)
    put("A18.bare_author", len(authors), authors)

    # A21 "쓰다" used in two senses within one article
    quote_rxs = patterns["A14.report_write"]["regex"] + patterns["A14.report_write_check"]["regex"]
    senses = sseuda_senses_hits(sentences, quote_rxs)
    put("A21.sseuda_senses", len(senses), senses)

    # A5.native_verbs, A7.see_judgment verbs in informational writing
    nv = native_verb_hits(sentences)
    put("A5.native_verbs", len(nv), nv)
    sj = see_judgment_hits(sentences)
    put("A7.see_judgment", len(sj), sj)
    g7 = []
    adverb_comma = []
    for s in body:
        t = s.masked.lstrip()
        m = re.match(r"^(\S+?)\s*[,，]", t)
        if m and m.group(1) in G7_ADVERBS:
            g7.append(_hit(s, m.group(0)))
        elif m and m.group(1) in SENT_ADVERBS:
            adverb_comma.append(_hit(s, m.group(0)))
    put("G7.conj_comma", len(g7), g7)
    put("INFO.adverb_comma", len(adverb_comma), adverb_comma)

    # G2: Endings that claim direct experience
    exp = [_hit(s, s.word) for s in body if s.word.endswith(EXPERIENCE_ENDINGS)]
    put("G2.exp_ending", len(exp), exp)

    # A2 commas
    n_body = len(body) or 1
    commas = [comma_count(s.masked) for s in body]
    conn_total = conn_comma = 0
    conn_hits = []
    for s in body:
        toks = s.masked.split()
        for idx, tok in enumerate(toks[:-1]):
            has_comma = tok.endswith((",", "，"))
            base = tok.rstrip(",，").rstrip(CLOSERS)
            if idx == 0 and base in SENT_ADVERBS:
                continue
            if is_connective(base):
                conn_total += 1
                if has_comma:
                    conn_comma += 1
                    conn_hits.append(_hit(s, tok))
    put("A2.comma_per_sentence", round(sum(commas) / n_body, 3))
    put("A2.comma_sentence_ratio", round(sum(1 for c in commas if c) / n_body, 3))
    put("A2.connective_comma_ratio", round(conn_comma / conn_total, 3) if conn_total else 0.0,
        conn_hits, comma=conn_comma, total=conn_total)

    # A17 maximum repeat count of sentences that open with the same first two words ("표를 보면", "결론부터 말하면")
    openers = {}
    for s_ in body:
        toks = re.sub(r"^[^\w가-힣⟦]+", "", s_.masked).split()[:2]
        if len(toks) == 2:
            openers.setdefault(" ".join(toks), []).append(s_)
    top = max(openers.items(), key=lambda kv: len(kv[1])) if openers else None
    put("A17.opener_repeat", len(top[1]) if top else 0,
        [_hit(x, top[0]) for x in top[1]] if top and len(top[1]) > 1 else [])

    # A16 share of sentences that open with the source as the subject
    src_hits = metrics["A16.source_subject"]["hits"]
    put("A16.source_subject_share", round(len(src_hits) / n_body, 3), src_hits, count=len(src_hits))

    # A4 total of summary sentences and lesson sentences at paragraph ends
    para_end = metrics["A4.summary_start"]["hits"] + metrics["A4.lesson_end"]["hits"]
    put("A4.para_end", len(para_end), para_end)

    # A8 rhythm
    lens = [len(s.text) for s in body if s.kind == "paragraph"]
    if lens:
        mean = sum(lens) / len(lens)
        sd = math.sqrt(sum((x - mean) ** 2 for x in lens) / len(lens))
        put("A8.sent_len_mean", round(mean, 1))
        put("A8.sent_len_cv", round(sd / mean, 3) if mean else 0.0)
        put("A8.long_ratio", round(sum(1 for x in lens if x >= 80) / len(lens), 3))
    else:
        put("A8.sent_len_mean", 0.0)
        put("A8.sent_len_cv", 0.0)
        put("A8.long_ratio", 0.0)
    runs = []
    run_len = 1
    prev = None
    seq = [s for s in body if s.kind == "paragraph"]
    for s in seq:
        if prev is not None and s.bucket == prev.bucket and s.bucket not in ("NOUN", "OTHER"):
            run_len += 1
            if run_len == 4:
                runs.append(_hit(s, s.bucket))
        else:
            run_len = 1
        prev = s
    put("A8.ending_run4", len(runs), runs)
    same_predicates = same_predicate_adjacent_hits(para_sents)
    put("A8.same_predicate_adjacent", len(same_predicates), same_predicates)
    pred = [s_.bucket for s_ in body if s_.bucket not in ("NOUN", "OTHER")]
    if pred:
        top_bucket = max(set(pred), key=pred.count)
        put("A8.ending_top_share", round(pred.count(top_bucket) / len(pred), 3), [], bucket=top_bucket)
    else:
        put("A8.ending_top_share", 0.0)
    paras = [ps for ps in para_sents if ps]
    put("A8.sentences_per_para", round(sum(len(p) for p in paras) / len(paras), 2) if paras else 0.0)
    put("A8.single_para_ratio", round(sum(1 for p in paras if len(p) == 1) / len(paras), 3) if paras else 0.0)

    # A9 formatting
    per_k = 1000.0 / prose_chars if prose_chars else 0.0
    sub_heads = [h for h in headings if h["level"] >= 2]
    label_items = [li for li in list_items if re.match(r"^\s*(\*\*|__)[^*_]{1,40}(\*\*|__)\s*[:：]", li["raw"])
                   or re.match(r"^[^\s:：]{1,20}\s*[:：]\s", li["text"])]
    put("A9.bold_per_1k", round(bold * per_k, 2))
    put("A9.list_ratio", round(list_chars / prose_chars, 3) if prose_chars else 0.0)
    put("A9.label_list_ratio", round(len(label_items) / len(list_items), 3) if list_items else 0.0)
    put("A9.heading_per_1k", round(len(sub_heads) * per_k, 2))
    colon_heads = [h for h in sub_heads if re.search(r"[:：]", h["text"])]
    put("A9.heading_colon_ratio", round(len(colon_heads) / len(sub_heads), 3) if sub_heads else 0.0,
        [{"line": h["line"], "text": h["text"]} for h in colon_heads])

    # A10 triads
    triads = [_hit(s) for s in body if is_triad(s.masked)]
    lists_by_id = {}
    for li in list_items:
        if li["depth"] == 0:
            lists_by_id.setdefault(li["list_id"], []).append(li)
    triad_lists = [v[0] for v in lists_by_id.values() if len(v) == 3]
    triad_total = len(triads) + len(triad_lists)
    put("A10.triad_per_1k", round(triad_total * per_k, 2), triads + [{"line": t["line"], "text": t["text"][:160]} for t in triad_lists],
        sentences=len(triads), lists=len(triad_lists))
    tri_para = []
    for ps in para_sents:
        c = [s for s in ps if is_triad(s.masked)]
        if len(c) >= 2:
            tri_para.append(_hit(c[0]))
    put("A10.triad_same_para", len(tri_para), tri_para)

    # A11 questions
    qs = [_hit(s) for s in body if s.question]
    put("A11.body_questions", len(qs), qs)
    q_heads = [h for h in sub_heads if QUESTION_HEADING_RE.search(h["text"].rstrip())]
    put("A11.question_heading_ratio", round(len(q_heads) / len(sub_heads), 3) if sub_heads else 0.0,
        [{"line": h["line"], "text": h["text"]} for h in q_heads])

    # Patterns used as rates per 1,000 characters
    for pid in ("A5.style_words", "A5.policy_verbs", "A12.progressive", "A13.demonstrative_start",
                "A14.translationese"):
        metrics[pid + "_per_1k"] = {"value": round(metrics[pid]["value"] * per_k, 2), "hits": metrics[pid]["hits"]}
    word_counts = {}
    for h in metrics["A5.style_words"]["hits"]:
        key = re.sub(r"(인|으로|하는\s*바|하|합|해|한|할|했|점|니다|요)$", "", h.get("match", ""))
        word_counts[key] = word_counts.get(key, 0) + 1
    over = {k: v for k, v in word_counts.items() if v > 2}
    put("A5.word_max", max(word_counts.values()) if word_counts else 0,
        [{"line": 0, "text": f"{k} {v}회"} for k, v in over.items()])

    # A15 figures not in the fact sheet. Approximate quantity words such as "수십만" and "수천" must also appear in the fact
    # sheet in the same form.
    if facts_text is not None:
        # Figures in the term table's general-knowledge explanation cells (explanations taken from dictionaries or
        # textbooks) do not count as figures from the source.
        known = number_set(strip_general_knowledge(facts_text))
        facts_norm = re.sub(r"\s+", "", facts_text)
        unknown = []
        for s in sentences:
            for key, raw in extract_numbers(s.text):
                if key not in known:
                    unknown.append(_hit(s, raw))
            for word in ko_approx_hits(s.masked):
                if word not in facts_norm:
                    unknown.append(_hit(s, word))
        for h in headings:
            for key, raw in extract_numbers(h["text"]):
                if key not in known:
                    unknown.append({"line": h["line"], "text": h["text"][:160], "match": raw})
            for word in ko_approx_hits(h["text"]):
                if word not in facts_norm:
                    unknown.append({"line": h["line"], "text": h["text"][:160], "match": word})
        put("A15.unknown_numbers", len(unknown), unknown)

    # Ending distribution
    dist = {}
    for s in body:
        dist[s.bucket] = dist.get(s.bucket, 0) + 1
    cls_count = {}
    for s in body:
        cls_count[s.cls] = cls_count.get(s.cls, 0) + 1

    stats = {
        "chars": prose_chars,
        "sentences": len(body),
        "paragraphs": len(paras),
        "headings": len(sub_heads),
        "list_items": len(list_items),
        "title": title_text,
    }
    return {
        "stats": stats,
        "metrics": metrics,
        "endings": {"class": cls_count, "bucket": dist},
        "_sentences": body,
    }


# ---------------------------------------------------------------- tone verdict

TONE_CLASSES = {"default": ("HAPNIDA", "Q_KKAYO"), "casual": ("HAEYO", "Q_KKAYO"), "plain": ("HAERA",)}
TONES = tuple(TONE_CLASSES) + ("free",)


def detect_tone(analysis):
    c = analysis["endings"]["class"]
    hapnida, haeyo, haera = c.get("HAPNIDA", 0), c.get("HAEYO", 0), c.get("HAERA", 0)
    if haera > hapnida and haera > haeyo:
        return "plain"
    return "casual" if haeyo > hapnida else "default"


def tone_metrics(analysis, tone, imperative_ok=False, inga_ok=False):
    """G4 tone mixing and Casual allowed-variant ratios. Bibliography entries in a references section ("공개 URL 없음") are
    not sentences, so they are skipped.
    The tone "free" is a tone the user described in their own words, so no ending is off-tone or banned.
    With imperative_ok (a skill's allow_imperative), the request forms "~해 주세요" and "~하세요" in a Default article also
    count as on-tone.
    With inga_ok (a skill's allow_inga_question), the question "~인가요?" in a Default article also counts as on-tone
    (a question to the reader)."""
    off = []
    banned = []
    for s in analysis["_sentences"]:
        if tone == "free":
            break
        if s.cls in ("NOUN", "OTHER") or getattr(s, "in_refs", False):
            continue
        if s.word.endswith(BANNED_ENDINGS) and tone == "casual":
            banned.append(_hit(s, s.word))
            continue
        ok = TONE_CLASSES[tone]
        if s.cls == "NOMINAL" and s.kind != "paragraph":
            continue
        if imperative_ok and tone == "default" and s.word.rstrip(".!").endswith("세요") \
                and not s.text.rstrip().endswith("?"):
            continue                                    # Requests to the reader ("제출해 주세요")
        if inga_ok and tone == "default" and s.text.rstrip().endswith("?") and s.word.rstrip("?").endswith("인가요"):
            continue                                    # Question to the reader "~인가요?"
        if s.cls not in ok:
            off.append(_hit(s, f"{s.cls}:{s.word}"))
    n = sum(1 for s in analysis["_sentences"] if s.cls not in ("NOUN", "OTHER")) or 1
    b = analysis["endings"]["bucket"]
    out = {
        "G4.off_tone": {"value": len(off), "hits": off},
        "G4.banned_ending": {"value": len(banned), "hits": banned},
        "T.jyo_ratio": {"value": round(b.get("C_JYO", 0) / n, 3), "hits": []},
        "T.geudeun_ratio": {"value": round(b.get("C_GEUDEUN", 0) / n, 3), "hits": []},
        "T.kkayo_ratio": {"value": round(b.get("Q_KKAYO", 0) / n, 3), "hits": []},
        "T.neundeyo_ratio": {"value": round(b.get("C_NEUNDEYO", 0) / n, 3), "hits": []},
    }
    return out


# ---------------------------------------------------------------- threshold verdict

def poisson_ppf(q, lam):
    if lam <= 0:
        return 0
    k = 0
    p = math.exp(-lam)
    cdf = p
    while cdf < q and k < 100000:
        k += 1
        p *= lam / k
        cdf += p
    return k


def judge(value, spec, chars):
    """Decides PASS/WARN/FAIL/GATE/INFO according to the threshold kind."""
    kind = spec.get("kind", "info")
    if kind == "info":
        return "INFO", {}
    if kind == "check":
        # Check candidates: not included in the verdict; only the flagged sentences are shown
        return ("CHECK" if value > 0 else "PASS"), {}
    if kind == "gate":
        return ("GATE" if value > 0 else "PASS"), {"max": 0}
    if any(k not in spec for k in LIMIT_FIELDS.get(kind, ())):
        # If no value calibrated against standard articles exists yet, as with a new skill's distribution metrics, only the
        # value is reported
        return "INFO", {"note": UNCALIBRATED_NOTE}
    if kind == "poisson":
        lam = spec["rate_per_1k"] * chars / 1000.0
        floor = spec.get("_floor", 0)
        p = max(floor, poisson_ppf(spec.get("pass_q", 0.9), lam))
        w = max(floor, poisson_ppf(spec.get("warn_q", 0.975), lam))
        lim = {"pass_max": p, "warn_max": w, "basis": "poisson", "rate_per_1k": spec["rate_per_1k"]}
        return ("PASS" if value <= p else "WARN" if value <= w else "FAIL"), lim
    if kind == "upper":
        lim = {"pass_max": spec["pass_max"], "warn_max": spec["warn_max"]}
        return ("PASS" if value <= spec["pass_max"] else "WARN" if value <= spec["warn_max"] else "FAIL"), lim
    if kind == "lower":
        lim = {"pass_min": spec["pass_min"], "warn_min": spec["warn_min"]}
        return ("PASS" if value >= spec["pass_min"] else "WARN" if value >= spec["warn_min"] else "FAIL"), lim
    if kind == "range":
        lo, hi = spec["pass"]
        wlo, whi = spec["warn"]
        lim = {"pass": spec["pass"], "warn": spec["warn"]}
        return ("PASS" if lo <= value <= hi else "WARN" if wlo <= value <= whi else "FAIL"), lim
    return "INFO", {}


def evaluate(analysis, thresholds, tone, max_hits=5, patterns_spec=None):
    if patterns_spec is None:
        patterns_spec = load_json(PATTERNS_PATH)
    pmeta = patterns_spec.get("patterns", {})
    metrics = dict(analysis["metrics"])
    metrics.update(tone_metrics(analysis, tone, imperative_ok=bool(thresholds.get("allow_imperative")),
                                inga_ok=bool(thresholds.get("allow_inga_question"))))
    chars = analysis["stats"]["chars"]
    results = []
    for mid, spec in thresholds["metrics"].items():
        if mid not in metrics:
            continue
        if spec.get("tone") and spec["tone"] != tone:
            continue
        if "by_tone" in spec:
            spec = dict(spec, **spec["by_tone"].get(tone, {}))
        if thresholds.get("poisson_floor"):
            spec = dict(spec, _floor=thresholds["poisson_floor"])     # short profile: one occurrence is allowed
        m = metrics[mid]
        value = len(m["hits"]) if spec.get("count") else m["value"]
        status, lim = judge(value, spec, chars)
        if spec.get("min_chars") and chars < spec["min_chars"] and status not in ("GATE",):
            status, lim = "INFO", {"note": f"본문 {spec['min_chars']}자 미만이라 판정하지 않음"}
        base_id = mid[:-len("_per_1k")] if mid.endswith("_per_1k") else mid
        title = spec.get("title") or pmeta.get(base_id, {}).get("title", mid)
        hint = spec.get("hint") or pmeta.get(base_id, {}).get("hint", "")
        r = {"id": mid, "title": title, "value": value, "status": status, "limit": lim}
        if spec.get("group"):
            r["group"] = spec["group"]
        if m.get("extra"):
            r["extra"] = m["extra"]
        if status not in ("PASS", "INFO") or max_hits < 0:
            r["hits"] = m["hits"][:max_hits] if max_hits >= 0 else m["hits"]
            # compact items (term explanation check candidates) keep the line number and flagged expression of truncated
            # hits. The first version of this rule showed only the first 5, so terms in later sections did not reach the
            # check list of the draft review.
            if spec.get("compact") and 0 <= max_hits < len(m["hits"]):
                r["more"] = [{"line": h["line"], "match": h.get("match", "")} for h in m["hits"][max_hits:]]
        if hint and status not in ("PASS", "INFO"):
            r["hint"] = hint
        results.append(r)
    gate_fail = sum(1 for r in results if r["status"] == "GATE")
    fail = sum(1 for r in results if r["status"] == "FAIL")
    warn = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if gate_fail == 0 and fail == 0 and warn <= thresholds.get("max_warn", 2) else "FAIL"
    return {"results": results,
            "summary": {"gate_fail": gate_fail, "fail": fail, "warn": warn, "verdict": verdict}}


# ---------------------------------------------------------------- output

STATUS_ORDER = {"GATE": 0, "FAIL": 1, "WARN": 2, "CHECK": 3, "PASS": 4, "INFO": 5}


def _fmt_limit(lim):
    if not lim:
        return ""
    if "max" in lim:
        return "기준 0회"
    if "pass_max" in lim:
        return f"PASS ≤{lim['pass_max']}, WARN ≤{lim['warn_max']}"
    if "pass_min" in lim:
        return f"PASS ≥{lim['pass_min']}, WARN ≥{lim['warn_min']}"
    if "pass" in lim:
        return f"PASS {lim['pass'][0]}~{lim['pass'][1]}, WARN {lim['warn'][0]}~{lim['warn'][1]}"
    return ""


def render_text(path, tone, analysis, ev, show_all=False, standard=DEFAULT_STANDARD):
    st = analysis["stats"]
    sm = ev["summary"]
    lines = [
        f"{SKILL_NAME} lint | {os.path.basename(path)} | tone={tone} | {st['chars']:,}자, {st['sentences']}문장, "
        f"{st['paragraphs']}문단, 헤딩 {st['headings']}개",
        f"판정: {sm['verdict']} (Gate 위반 {sm['gate_fail']}, FAIL {sm['fail']}, WARN {sm['warn']})",
    ]
    checks = [r for r in ev["results"] if r["status"] == "CHECK"]
    for r in sorted(ev["results"], key=lambda r: STATUS_ORDER[r["status"]]):
        if r["status"] == "CHECK" or (r["status"] in ("PASS", "INFO") and not show_all):
            continue
        lines.append(f"[{r['status']}] {r['id']} {r['title']}: {r['value']} ({_fmt_limit(r['limit'])})")
        if r.get("hint"):
            lines.append(f"    수정 방향: {r['hint']}")
        for h in r.get("hits", []):
            m = f" «{h['match']}»" if h.get("match") else ""
            lines.append(f"    L{h['line']}{m}: {h['text']}")
    groups = (
        ([r for r in checks if r.get("group") not in ("ko", "term", "rhythm", "fact")], False,
         "단독 읽기 점검 후보 (판정에 반영되지 않음): 이 문장과 바로 앞 문장만 읽고 무엇에 대한 내용인지, "
         "누구의 말인지, 수치가 무엇을 측정한 값인지 알 수 있으면 그대로 둔다."),
        ([r for r in checks if r.get("group") == "rhythm"], True,
         "서술어 반복 점검 후보 (판정에 반영되지 않음): 인접한 두 문장을 함께 읽는다. 반복 때문에 읽는 흐름이 "
         "끊기고 의미와 조건을 더 명확하게 쓸 수 있을 때만 항목을 합치거나 근거와 결과를 연결한다. 자연스러운 반복과 "
         "필요한 주어, 목적어는 유지하고, 유지한 후보의 문맥과 이유를 기록한다."),
        ([r for r in checks if r.get("group") == "ko"], True,
         "한국어 점검 후보 (판정에 반영되지 않음): 검출된 표현이 references/ai-patterns.md의 \"과교정하지 않기\"에 "
         f"있는 용법이면 그대로 두고, 아니면 {standard}에서 사용하는 표현으로 수정한다."),
        ([r for r in checks if r.get("group") == "term"], True,
         "용어 설명 점검 후보 (판정에 반영되지 않음): 검출된 용어가 처음 나온 이 문장이나 바로 다음 문장에 그 용어가 "
         "무엇인지 설명하는 내용이 있으면 그대로 둔다. 이름을 번역한 표현이나 약어의 풀네임만 있으면 references/style-guide.md의 "
         "\"처음 나오는 용어와 중심 대상 설명\"에 따라 수정한다."),
        ([r for r in checks if r.get("group") == "fact"], True,
         "자료 대조 후보 (판정에 반영되지 않음): 검출된 문장이 말하는 경험이나 사실이 자료와 fact sheet에 있으면 그대로 두고, "
         "없으면 삭제하거나 자료에 있는 사실로 다시 쓴다."),
    )
    for group, show_match, header in groups:
        if not group:
            continue
        lines.append("")
        lines.append(header)
        for r in group:
            lines.append(f"[CHECK] {r['id']} {r['title']}: {r['value']}")
            if r.get("hint"):
                lines.append(f"    수정 방향: {r['hint']}")
            for h in r.get("hits", []):
                m = f" «{h['match']}»" if show_match and h.get("match") else ""
                where = f"L{h['line']}" if h["line"] else "fact sheet"
                if h.get("previous"):
                    p = h["previous"]
                    lines.append(f"    앞 문장 L{p['line']}: {p['text']}")
                lines.append(f"    {where}{m}: {h['text']}")
            more = r.get("more") or []
            if more:
                lines.append(f"    나머지 {len(more)}개 항목(줄 번호와 검출된 표현):")
                for k in range(0, len(more), 6):
                    lines.append("      " + ", ".join(
                        (f"L{h['line']}" if h["line"] else "fact sheet") + (f" «{h['match']}»" if h["match"] else "")
                        for h in more[k:k + 6]))
    return "\n".join(lines)


# ---------------------------------------------------------------- skill allowances and the short profile

def apply_profile(thresholds, patterns_spec, short=False):
    """Returns copies of (thresholds, patterns) with the skill's allowances applied, plus the short profile when short
    is set.

    Allowances are top-level keys of the merged thresholds: allow_patterns ({pattern ID: [regex, ...]} removes those
    regexes from the pattern), allow_imperative, and allow_inga_question. The short profile (the "short" key) can add
    more of the same, drops metrics (an entry that ends in "." excludes every metric starting with that prefix), and
    turns the per-1,000 rates listed under "count" into counts."""
    prof = (thresholds.get("short") or {}) if short else {}
    th = dict(thresholds)
    drops = prof.get("drop") or []
    th["metrics"] = {mid: spec for mid, spec in thresholds["metrics"].items() if not _dropped(mid, drops)}
    # Rates per 1,000 characters are not judged on short texts (min_chars), so the listed items are judged by count
    for mid, (pass_max, warn_max) in (prof.get("count") or {}).items():
        if mid in th["metrics"]:
            spec = th["metrics"][mid]
            title = re.sub(r"\(1,000자당\)", "", spec.get("title") or mid).strip()
            th["metrics"][mid] = {"kind": "upper", "pass_max": pass_max, "warn_max": warn_max, "count": True,
                                  "title": f"{title} (짧은 글: 개수)",
                                  **({"hint": spec["hint"]} if spec.get("hint") else {})}
    if "max_warn" in prof:
        th["max_warn"] = prof["max_warn"]
    for key in ("allow_imperative", "allow_inga_question"):
        th[key] = bool(thresholds.get(key) or prof.get(key))
    th["poisson_floor"] = prof.get("poisson_floor", 0)
    spec = json.loads(json.dumps(patterns_spec))
    for allowed_by in (thresholds.get("allow_patterns") or {}, prof.get("allow_patterns") or {}):
        for pid, allowed in allowed_by.items():
            if pid in spec["patterns"]:
                spec["patterns"][pid]["regex"] = [r for r in spec["patterns"][pid]["regex"] if r not in allowed]
    return th, spec


def run(path, tone="auto", facts=None, thresholds_path=None, as_json=False, show_all=False, max_hits=5,
        short=False):
    text = read_text(path)
    facts_text = read_text(facts) if facts else None
    thresholds, patterns_spec = apply_profile(load_thresholds(thresholds_path), load_json(PATTERNS_PATH), short)
    analysis = analyze(text, patterns_spec=patterns_spec, facts_text=facts_text)
    if tone == "auto":
        tone = detect_tone(analysis)
    ev = evaluate(analysis, thresholds, tone, max_hits=-1 if as_json else max_hits, patterns_spec=patterns_spec)
    if as_json:
        out = {"schema": LINT_SCHEMA, "file": path, "tone": tone, "stats": analysis["stats"],
               "endings": analysis["endings"], "results": ev["results"], "summary": ev["summary"]}
        return json.dumps(out, ensure_ascii=False, indent=1), ev["summary"]["verdict"]
    return render_text(path, tone, analysis, ev, show_all, standard_text(thresholds)), ev["summary"]["verdict"]


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description=f"{SKILL_NAME} Korean style lint")
    ap.add_argument("article")
    ap.add_argument("--tone", choices=TONES + ("auto",), default="auto")
    ap.add_argument("--facts", help="fact sheet path (A15 figure comparison)")
    ap.add_argument("--thresholds", help="thresholds JSON path (default: scripts/thresholds.json)")
    ap.add_argument("--json", action="store_true", help="output as JSON")
    ap.add_argument("--all", action="store_true", help="also output PASS items")
    ap.add_argument("--max-hits", type=int, default=5)
    ap.add_argument("--short", action="store_true", help="apply the short profile (texts under 1,500 characters)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    for p in [args.article] + [x for x in (args.facts,) if x]:
        if not os.path.isfile(p):
            print(f"파일이 없습니다: {p}", file=sys.stderr)
            return 2
    try:
        out, verdict = run(args.article, args.tone, args.facts, args.thresholds, args.json, args.all, args.max_hits,
                           short=args.short)
    except (OSError, ValueError, KeyError) as e:
        print(f"lint 실행 오류: {e}", file=sys.stderr)
        return 2
    print(out)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
