#!/usr/bin/env python3
"""K-Writer tone check: verifies that a tone-converted article differs from its Default draft only in sentence endings.

The source of this file is core/scripts/tone_check.py in the repo. dev/sync_core.py copies it to skills/<name>/scripts/ for each skill.

Usage
  python tone_check.py DEFAULT.md CONVERTED.md [--tone casual|plain|free] [--json]
  python tone_check.py --cleanup FILE [FILE ...]   # deletes only .facts.md, .draft.md, .unrevised.md, .repeats.md, .reader.md, .pre-fix.md, .audit.md, .answer.md work files

--tone names the tone of CONVERTED.md: casual ("해요체", the default), plain ("해라체"), or free (a tone the user described
in their own words; the ending class of the converted sentences is not checked).

Check order
  1. The order of block types (heading, paragraph, list, code, table, quote) is the same.
  2. Headings, code, tables, quotes, and noun-phrase list items are the same in both articles.
  3. Paragraphs and sentence-form list items have the same number of sentences.
  4. In each sentence, the numbers, Latin tokens, quotes, parenthesized content, and the count of negative expressions
     are the same, and the words match from the start and differ only within the last 2 words. WARN if the initial
     consonant of the first differing word does not carry over.
  5. Default sentences are "합니다체" and converted sentences are in the target tone. A Casual article has none of the
     banned endings ("~더라고요", "~네요", "~잖아요", "~답니다").

Exit codes: 0 pass, 1 mismatch, 2 usage or input error
"""

import argparse
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_ko as L  # noqa: E402

SKILL_NAME = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

K_TAIL = 2
FROZEN = ("heading", "code", "table", "blockquote", "html")
CONTRACTIONS = {
    "것은": ("건",), "것이": ("게",), "것을": ("걸",), "이것은": ("이건",), "그것은": ("그건",),
    "이것이": ("이게",), "그것이": ("그게",), "무엇을": ("뭘",), "무엇이": ("뭐가",),
}
CAUSE_RE = re.compile(r"(때문|므로|어서|아서|해서|니까|덕분|이유는)")
NEG_RE = re.compile(r"(않|없|못|아니|(?<![가-힣])안\s)")
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-+/#]*")
CHOSEONG = 588  # syllables per initial consonant (21 * 28)
# Target tone -> (ending classes a converted sentence may have, name used in messages). free has no fixed classes.
TARGETS = {"casual": (("HAEYO", "Q_KKAYO", "NOUN", "OTHER"), "해요체"),
           "plain": (("HAERA", "NOUN", "OTHER"), "해라체"),
           "free": (None, "직접 정한 어투")}


def _norm_ws(s):
    s = L.normalize_text(s)
    s = s.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def _choseong(word):
    out = []
    for ch in word:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(code // CHOSEONG)
        else:
            out.append(ch)
    return out


def _protected(s):
    toks = []
    toks += [k for k, _ in L.extract_numbers(s)]
    toks += re.findall(r"⟦[CURQ]⟧", s)
    toks += [t.lower() for t in LATIN_RE.findall(L.PH_RE.sub(" ", s))]
    toks += re.findall(r"\(([^()]*)\)", s)
    toks += re.findall(r"[“\"]([^”\"]+)[”\"]", s)
    return sorted(toks)


def _eq_word(d, c):
    return d == c or c in CONTRACTIONS.get(d, ())


def _is_sentence_item(text):
    clean, _, _ = L.clean_inline(text)
    word = L.last_word(clean)
    cls = L.classify_ending(word, clean.rstrip().endswith("?"))
    return cls in ("HAPNIDA", "HAEYO", "Q_KKAYO", "HAERA", "NOMINAL")


def _units(text):
    """List of comparison units: (kind, line number, source text, sentence list or None)."""
    units = []
    for b in L.parse_blocks(L.normalize_text(text)):
        if b.type in FROZEN:
            units.append((b.type + (str(b.level) if b.type == "heading" else ""), b.line, b.text, None))
        elif b.type == "list_item" and not _is_sentence_item(b.text):
            units.append(("list_noun", b.line, b.text, None))
        else:
            clean, _, _ = L.clean_inline(b.text)
            units.append((b.type, b.line, b.text, L.split_sentences(clean)))
    return units


def _issue(code, level, d_line, c_line, si, d, c, note=""):
    return {"code": code, "level": level, "d_line": d_line, "c_line": c_line, "sent": si,
            "default": d[:160], "casual": c[:160], "note": note}


def _default_ok(d, dword, dcls, allow):
    """True when a Default sentence is on-tone. With a skill's allow_imperative, the request "~해 주세요" counts as
    on-tone, and with allow_inga_question the question "~인가요?" does (the same exceptions as lint G4.off_tone)."""
    if dcls in ("HAPNIDA", "Q_KKAYO", "NOUN", "OTHER"):
        return True
    question = d.rstrip().endswith("?")
    if allow.get("allow_imperative") and not question and dword.rstrip(".!").endswith("세요"):
        return True
    return bool(allow.get("allow_inga_question") and question and dword.rstrip("?").endswith("인가요"))


def compare_sentence(d, c, d_line, c_line, si, tone="casual", allow=None):
    issues = []
    classes, tone_name = TARGETS[tone]
    dm, cm = L.mask_quotes(d), L.mask_quotes(c)
    if _protected(d) != _protected(c):
        issues.append(_issue("TOKEN", "FAIL", d_line, c_line, si, d, c, "수치, 영문, 괄호, 인용 토큰이 다르다"))
    if len(NEG_RE.findall(dm)) != len(NEG_RE.findall(cm)):
        issues.append(_issue("POLARITY", "FAIL", d_line, c_line, si, d, c, "부정 표현 수가 다르다"))
    dw = L.PH_RE.sub(" ", d).split()
    cw = L.PH_RE.sub(" ", c).split()
    p = 0
    while p < min(len(dw), len(cw)) and _eq_word(dw[p], cw[p]):
        p += 1
    rd, rc = len(dw) - p, len(cw) - p
    if rd > K_TAIL or rc > K_TAIL:
        issues.append(_issue("PREFIX", "FAIL", d_line, c_line, si, d, c,
                             f"마지막 {K_TAIL}어절 밖에서 달라졌다(D {rd}어절, C {rc}어절 남음)"))
    elif rd and rc:
        # Conjugation changes what follows the first syllable (썼습니다→썼어요, 둡니다→둬요). A different initial consonant in the first syllable means a different word.
        a, b = _choseong(dw[p]), _choseong(cw[p])
        if a[:1] != b[:1]:
            issues.append(_issue("STEM", "WARN", d_line, c_line, si, d, c, "바뀐 어절의 어간이 다르다"))
    dword, cword = L.last_word(d), L.last_word(c)
    dcls = L.classify_ending(dword, d.rstrip().endswith("?"))
    ccls = L.classify_ending(cword, c.rstrip().endswith("?"))
    if not _default_ok(d, dword, dcls, allow or {}):
        issues.append(_issue("D_TONE", "FAIL", d_line, c_line, si, d, c, f"Default 문장이 합니다체가 아니다({dcls})"))
    if tone == "casual" and cword.endswith(L.BANNED_ENDINGS):
        issues.append(_issue("BANNED", "FAIL", d_line, c_line, si, d, c, f"금지 어미 {cword}"))
    elif classes is not None and ccls not in classes:
        issues.append(_issue("C_TONE", "FAIL", d_line, c_line, si, d, c, f"변환한 문장이 {tone_name}가 아니다({ccls})"))
    if tone == "casual" and cword.endswith("거든요") and not CAUSE_RE.search(d):
        issues.append(_issue("GEUDEUN", "WARN", d_line, c_line, si, d, c, "Default 문장에 원인 표현이 없는데 ~거든요를 사용했다"))
    return issues


def check(default_text, casual_text, tone="casual", allow=None):
    """allow is the skill's merged thresholds (allow_imperative, allow_inga_question). None means no allowance."""
    du, cu = _units(default_text), _units(casual_text)
    issues = []
    pairs = 0
    dk = [u[0] for u in du]
    ck = [u[0] for u in cu]
    if dk != ck:
        sm = difflib.SequenceMatcher(a=dk, b=ck, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                dl = du[i1][1] if i1 < len(du) else (du[-1][1] if du else 0)
                cl = cu[j1][1] if j1 < len(cu) else (cu[-1][1] if cu else 0)
                issues.append(_issue("STRUCTURE", "FAIL", dl, cl, 0, " / ".join(dk[i1:i2]) or "(없음)",
                                     " / ".join(ck[j1:j2]) or "(없음)", "블록 구성이 다르다"))
                break
        return {"pairs": 0, "issues": issues}
    for (kind, dl, dtext, dsents), (_, cl, ctext, csents) in zip(du, cu):
        if dsents is None:
            if _norm_ws(dtext) != _norm_ws(ctext):
                issues.append(_issue("FROZEN", "FAIL", dl, cl, 0, dtext, ctext, f"{kind} 블록은 두 글에서 같아야 한다"))
            continue
        if len(dsents) != len(csents):
            issues.append(_issue("SENT_COUNT", "FAIL", dl, cl, 0, dtext, ctext,
                                 f"문장 수가 다르다(D {len(dsents)}, C {len(csents)})"))
            continue
        for si, (d, c) in enumerate(zip(dsents, csents), 1):
            pairs += 1
            issues.extend(compare_sentence(d, c, dl, cl, si, tone, allow))
    return {"pairs": pairs, "issues": issues}


WORK_SUFFIXES = (".facts.md", ".draft.md", ".unrevised.md", ".repeats.md", ".reader.md", ".pre-fix.md", ".audit.md",
                 ".answer.md")


def cleanup(paths):
    removed = []
    for p in paths:
        if not p.endswith(WORK_SUFFIXES):
            print(f"건너뜀(작업 파일이 아님): {p}", file=sys.stderr)
            continue
        if os.path.isfile(p):
            os.remove(p)
            removed.append(p)
    for p in removed:
        print(f"삭제: {p}")
    return 0


def main(argv=None):
    L.setup_stdio()
    ap = argparse.ArgumentParser(description=f"{SKILL_NAME} tone invariance check")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tone", choices=tuple(TARGETS), default="casual", help="Tone of the converted article")
    ap.add_argument("--cleanup", action="store_true", help="Delete the given work files (" + ", ".join(WORK_SUFFIXES) + ")")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.cleanup:
        return cleanup(args.files)
    if len(args.files) != 2:
        print("사용법: tone_check.py DEFAULT.md CONVERTED.md [--tone casual|plain|free]", file=sys.stderr)
        return 2
    for p in args.files:
        if not os.path.isfile(p):
            print(f"파일이 없습니다: {p}", file=sys.stderr)
            return 2
    res = check(L.read_text(args.files[0]), L.read_text(args.files[1]), args.tone, L.load_thresholds())
    fails = [i for i in res["issues"] if i["level"] == "FAIL"]
    warns = [i for i in res["issues"] if i["level"] == "WARN"]
    verdict = "PASS" if not fails else "FAIL"
    if args.json:
        print(json.dumps({"verdict": verdict, "pairs": res["pairs"], "fail": len(fails), "warn": len(warns),
                          "issues": res["issues"]}, ensure_ascii=False, indent=1))
    else:
        print(f"tone_check: {verdict} (문장 {res['pairs']}쌍, FAIL {len(fails)}, WARN {len(warns)})")
        for i in res["issues"]:
            print(f"{i['level']} {i['code']} D:L{i['d_line']}/C:L{i['c_line']} s{i['sent']} | {i['note']}")
            print(f"    D «{i['default']}»")
            print(f"    C «{i['casual']}»")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
