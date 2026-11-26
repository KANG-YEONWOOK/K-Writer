#!/usr/bin/env python3
"""Measure how sentences and paragraphs connect in the reference corpora (uses kiwipiepy).

Usage: python -I measure_flow.py <cache> <repo> <out.json>
Writes flow-stats.json. kiwipiepy 0.25.1 was used on 2026-11-26.
"""
import collections
import json
import re
import statistics
import sys

from kiwipiepy import Kiwi

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus as C  # noqa: E402

NOUN_TAGS = {"NNG", "NNP", "SL", "SH"}
STOP = {"경우", "때문", "이후", "이전", "사이", "가지", "정도", "하나", "다음", "이상", "이하", "동안", "가운데",
        "당시", "오늘", "최근", "자신", "우리", "여러분", "가운데", "모두", "사실", "그동안"}
CONJ = re.compile(r"^(?:그러나|하지만|그런데|그리고|또한|또|따라서|그러므로|그래서|그러면|그럼에도|그렇지만|반면|반대로|"
                  r"한편|즉|곧|다시 말해|요컨대|예를 들어|예를 들면|예컨대|가령|이를테면|특히|물론|다만|단|오히려|결국|"
                  r"더욱이|게다가|나아가|아울러|우선|먼저|다음으로|마지막으로|끝으로|첫째|둘째|셋째|넷째|왜냐하면|"
                  r"그렇다면|그러자|그 결과|이에 따라|이로 인해|이 때문에|그 때문에|이와 달리|이와 같이|이처럼|이같이|"
                  r"이렇게|이렇듯|그러다|그럼|더구나|뿐만 아니라|그뿐 아니라)(?=[\s,])")
DEMO = re.compile(r"^(?:이런|그런|이러한|그러한|이와 같은|이 같은|이것|그것|이들|그들|이때|그때|이처럼|이같이|이렇게|"
                  r"그렇게|이렇듯|여기서|여기에|이곳|그곳|이로써|이로부터|이로 인해|이에 따라|이 때문에|그 때문에|"
                  r"이 중|그중|이 가운데|그 가운데|그 결과|그 후|그 뒤|이후|이에|이는|이를|이와|그와|이로|"
                  r"(?:이|그) (?=[가-힣A-Za-z0-9‘“]))")
DEMO_TOKENS = {("이", "MM"), ("그", "MM"), ("저", "MM"), ("이런", "MM"), ("그런", "MM"), ("이", "NP"), ("그", "NP"),
               ("이것", "NP"), ("그것", "NP"), ("이들", "NP"), ("그들", "NP"), ("여기", "NP"), ("거기", "NP"),
               ("이곳", "NP"), ("그곳", "NP"), ("이러", "VA"), ("그러", "VA"), ("이렇", "VA"), ("그렇", "VA"),
               ("이러하", "VA"), ("그러하", "VA"), ("이때", "NNG"), ("그때", "NNG"), ("이후", "NNG")}


def is_demo(sent):
    """True if the sentence opens with a demonstrative that points back to earlier text."""
    toks = sent["tokens"]
    if toks and (toks[0].form, toks[0].tag) in DEMO_TOKENS:
        return True
    return bool(DEMO.match(sent["text"])) and not CONJ.match(sent["text"])


GROUPS = {
    "example": re.compile(r"예를 들어|예를 들면|예컨대|가령|이를테면|한 예로|일례로"),
    "reason_end": re.compile(r"때문이다|때문입니다|까닭이다|이유에서다|때문이었다"),
    "contrast": re.compile(r"^(?:그러나|하지만|그런데|반면|반대로|그렇지만|이와 달리|그와 달리|그럼에도)"),
    "result": re.compile(r"^(?:따라서|그러므로|그래서|그 결과|이에 따라|이로 인해|이 때문에|결국|그리하여)"),
    "restate": re.compile(r"^(?:즉|곧|다시 말해|요컨대|말하자면|바꿔 말하면)|[가-힣],? (?:즉|곧) "),
    "addition": re.compile(r"^(?:또한|또|그리고|아울러|나아가|더욱이|게다가|뿐만 아니라)"),
    "order": re.compile(r"^(?:첫째|둘째|셋째|넷째|먼저|우선|다음으로|마지막으로|끝으로)"),
    "define": re.compile(r"(?:이란|란|은|는) [^.]{2,80}(?:을|를) (?:말한다|뜻한다|의미한다|가리킨다|일컫는다)|"
                         r"(?:을|를|이것을|이를) [^.]{1,40}(?:이라고|라고|이라|라) (?:한다|부른다|일컫는다|불린다)|"
                         r"(?:이라고|라고|이라|라) (?:한다|부른다|일컫는다|불린다)\."),
    "question": re.compile(r"\?[”’\"']?$"),
}


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def summarize(xs, nd=2):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"n": len(xs), "mean": round(statistics.fmean(xs), nd), "p25": round(pct(xs, .25), nd),
            "median": round(statistics.median(xs), nd), "p75": round(pct(xs, .75), nd), "p90": round(pct(xs, .9), nd)}


def nouns_of(tokens):
    out = []
    for i, t in enumerate(tokens):
        if t.tag in NOUN_TAGS and len(t.form) >= 2 and t.form not in STOP:
            out.append((t.form, i))
    return out


def clause_count(tokens):
    n = 1
    for i, t in enumerate(tokens):
        if t.tag == "EC":
            nxt = tokens[i + 1].tag if i + 1 < len(tokens) else ""
            if nxt not in ("VX", "VCP", "SF", "SP", "EC"):
                n += 1
    return n


def noun_chain_max(tokens):
    best = run = 0
    for t in tokens:
        if t.tag in ("NNG", "NNP", "SL"):
            run += 1
            best = max(best, run)
        elif t.tag in ("XSN", "SN", "NR") and run:
            continue
        else:
            run = 0
    return best


def ending_class(text, tokens):
    s = text.rstrip(" ”’\"')]")
    if s.endswith("?"):
        return "question"
    if not re.search(r"[다요죠까][.!]?$", s):
        return "nominal"
    tail = s[-14:]
    for name, pat in (("because", r"때문(?:이다|입니다|이었다|이에요)\.?$"), ("can", r"수 (?:있|없)[^ ]*\.?$"),
                      ("geot", r"것(?:이다|입니다|이었다)\.?$"), ("copula", r"(?:이다|입니다|이었다|였다|였습니다)\.?$"),
                      ("exist", r"(?:있다|없다|있습니다|없습니다|있었다|없었다)\.?$")):
        if re.search(pat, tail):
            return name
    past = any(t.tag == "EP" and t.form in ("었", "았", "였", "ᆻ") for t in tokens[-4:])
    return "past" if past else "present"


def analyze_doc(doc, kiwi):
    paras = []
    for p in doc["paragraphs"]:
        sents = kiwi.split_into_sents(p, return_tokens=True)
        rows = []
        for s in sents:
            text = s.text.strip()
            if len(text) < 5:
                continue
            toks = s.tokens
            ns = nouns_of(toks)
            rows.append({"text": text, "len": len(text), "tokens": toks, "nouns": ns,
                         "nounset": {n for n, _ in ns}, "ntok": len(toks)})
        if rows:
            paras.append(rows)
    return paras


def measure(docs, kiwi, name):
    S = collections.defaultdict(list)       # per-sentence values
    D = collections.defaultdict(list)       # per-document values
    cnt = collections.Counter()
    endings = collections.Counter()
    groups = collections.Counter()
    first_roles = collections.Counter()
    for doc in docs:
        paras = analyze_doc(doc, kiwi)
        if not paras:
            continue
        sents = [s for p in paras for s in p]
        chars = sum(s["len"] for s in sents)
        cnt["docs"] += 1
        cnt["sents"] += len(sents)
        cnt["chars"] += chars
        # document topic nouns: nouns ranked by the number of sentences that contain them
        df = collections.Counter(n for s in sents for n in s["nounset"])
        top = [n for n, c in df.most_common(8) if c >= 2]
        top3, top5 = set(top[:3]), set(top[:5])
        if top3:
            D["sent_with_top3"].append(sum(1 for s in sents if s["nounset"] & top3) / len(sents))
            D["sent_with_top5"].append(sum(1 for s in sents if s["nounset"] & top5) / len(sents))
            D["top1_in_first_sentence"].append(1.0 if top[0] in sents[0]["nounset"] else 0.0)
            first_para = set().union(*[s["nounset"] for s in paras[0]])
            D["top1_in_first_para"].append(1.0 if top[0] in first_para else 0.0)
            D["top3_in_first_para"].append(len(top3 & first_para) / len(top3))
        if doc.get("para_ok") and len(paras) >= 2:
            cnt["docs_para"] += 1
            D["paras"].append(len(paras))
            for k, p in enumerate(paras):
                cnt["paras"] += 1
                S["para_sents"].append(len(p))
                S["para_chars"].append(sum(s["len"] for s in p))
                pdf = collections.Counter(n for s in p for n in s["nounset"])
                ptop = [n for n, c in pdf.most_common(3) if c >= 2]
                if len(p) >= 3 and ptop:
                    cnt["para_with_topic"] += 1
                    cnt["para_topic_in_first"] += 1 if ptop[0] in p[0]["nounset"] else 0
                    cnt["para_topic_in_last"] += 1 if ptop[0] in p[-1]["nounset"] else 0
                    S["para_topic_cover"].append(sum(1 for s in p if s["nounset"] & set(ptop[:2])) / len(p))
                if top3:
                    cnt["para_any"] += 1
                    pn = set().union(*[s["nounset"] for s in p])
                    cnt["para_has_top3"] += 1 if pn & top3 else 0
                    cnt["para_has_top5"] += 1 if pn & top5 else 0
                if k:
                    prev = paras[k - 1]
                    prev_all = set().union(*[s["nounset"] for s in prev])
                    first = p[0]
                    cnt["pfirst"] += 1
                    ov_last = bool(first["nounset"] & prev[-1]["nounset"])
                    ov_any = bool(first["nounset"] & prev_all)
                    demo = is_demo(first)
                    conj = bool(CONJ.match(first["text"]))
                    cnt["pfirst_overlap_last"] += ov_last
                    cnt["pfirst_overlap_prevpara"] += ov_any
                    cnt["pfirst_demo"] += demo
                    cnt["pfirst_conj"] += conj
                    cnt["pfirst_none"] += not (ov_any or demo or conj)
                    cnt["pfirst_top5"] += bool(first["nounset"] & top5)
        seen = set()
        n_all = len(sents)
        idx = 0
        for p in paras:
            for j, s in enumerate(p):
                idx += 1
                S["sent_len"].append(s["len"])
                S["clauses"].append(clause_count(s["tokens"]))
                tags = collections.Counter(t.tag[0] if t.tag[0] in "JNVE" else t.tag for t in s["tokens"])
                nn = sum(1 for t in s["tokens"] if t.tag in ("NNG", "NNP", "SL", "NNB", "NR", "NP"))
                jj = sum(1 for t in s["tokens"] if t.tag.startswith("J"))
                vv = sum(1 for t in s["tokens"] if t.tag in ("VV", "VA", "VX", "VCP", "VCN", "XSV", "XSA"))
                cnt["tok_noun"] += nn
                cnt["tok_josa"] += jj
                cnt["tok_pred"] += vv
                chain = noun_chain_max(s["tokens"])
                cnt["chain3"] += chain >= 3
                cnt["chain4"] += chain >= 4
                cnt["paren"] += s["text"].count("(")
                e = ending_class(s["text"], s["tokens"])
                endings[e] += 1
                for g, pat in GROUPS.items():
                    if pat.search(s["text"]):
                        groups[g] += 1
                conj = bool(CONJ.match(s["text"]))
                demo = is_demo(s)
                cnt["start_conj"] += conj
                cnt["start_demo"] += demo
                head = s["tokens"][:8]
                topic = any(t.tag == "JX" and t.form in ("은", "는", "ᆫ") for t in head)
                cnt["topic_head"] += topic
                new = [n for n in s["nounset"] if n not in seen]
                if s["nounset"]:
                    decile = min(9, int(10 * (idx - 1) / n_all))
                    S[f"new_rate_d{decile}"].append(len(new) / len(s["nounset"]))
                seen |= s["nounset"]
                if j:
                    prev = p[j - 1]
                    cnt["inner"] += 1
                    ov1 = s["nounset"] & prev["nounset"]
                    ov2 = ov1 or (j >= 2 and s["nounset"] & p[j - 2]["nounset"])
                    cnt["inner_overlap1"] += bool(ov1)
                    cnt["inner_overlap2"] += bool(ov2)
                    cnt["inner_demo"] += demo
                    cnt["inner_conj"] += conj
                    cnt["inner_none1"] += not (ov1 or demo or conj)
                    cnt["inner_none2"] += not (ov2 or demo or conj)
                    cnt["inner_none2_top5"] += (not (ov2 or demo or conj)) and bool(s["nounset"] & top5)
                    if ov1:
                        pos = min(i for n, i in s["nouns"] if n in ov1) / max(1, s["ntok"])
                        S["given_pos"].append(pos)
                        last_prev = max(i for n, i in prev["nouns"] if n in ov1) / max(1, prev["ntok"])
                        S["given_prev_pos"].append(last_prev)
                else:
                    first_roles["conj" if conj else "demo" if demo else "plain"] += 1
    n = max(1, cnt["sents"])
    res = {
        "corpus": name, "docs": cnt["docs"], "sentences": cnt["sents"], "chars": cnt["chars"],
        "docs_with_paragraphs": cnt["docs_para"], "paragraphs": cnt["paras"],
        "sentence_length": summarize(S["sent_len"], 1),
        "clauses_per_sentence": summarize(S["clauses"], 2),
        "paragraph_sentences": summarize(S["para_sents"], 1),
        "paragraph_chars": summarize(S["para_chars"], 0),
        "paragraphs_per_doc": summarize(D["paras"], 1),
        "start_conjunctive_share": round(cnt["start_conj"] / n, 3),
        "start_demonstrative_share": round(cnt["start_demo"] / n, 3),
        "topic_marker_in_head_share": round(cnt["topic_head"] / n, 3),
        "josa_per_noun": round(cnt["tok_josa"] / max(1, cnt["tok_noun"]), 3),
        "predicate_per_noun": round(cnt["tok_pred"] / max(1, cnt["tok_noun"]), 3),
        "noun_chain3_sentence_share": round(cnt["chain3"] / n, 3),
        "noun_chain4_sentence_share": round(cnt["chain4"] / n, 3),
        "paren_per_1k_chars": round(1000 * cnt["paren"] / max(1, cnt["chars"]), 2),
        "endings": {k: round(v / n, 3) for k, v in endings.most_common()},
        "markers_per_100_sentences": {k: round(100 * v / n, 2) for k, v in groups.most_common()},
        "within_paragraph_links": {
            "pairs": cnt["inner"],
            "noun_overlap_prev": round(cnt["inner_overlap1"] / max(1, cnt["inner"]), 3),
            "noun_overlap_prev2": round(cnt["inner_overlap2"] / max(1, cnt["inner"]), 3),
            "demonstrative": round(cnt["inner_demo"] / max(1, cnt["inner"]), 3),
            "conjunctive": round(cnt["inner_conj"] / max(1, cnt["inner"]), 3),
            "no_link_prev": round(cnt["inner_none1"] / max(1, cnt["inner"]), 3),
            "no_link_prev2": round(cnt["inner_none2"] / max(1, cnt["inner"]), 3),
            "no_link_prev2_but_doc_topic": round(cnt["inner_none2_top5"] / max(1, cnt["inner_none2"]), 3),
            "given_noun_position_in_sentence": summarize(S["given_pos"], 2),
            "given_noun_position_in_previous": summarize(S["given_prev_pos"], 2),
        },
        "paragraph_first_sentence_links": {
            "paragraphs": cnt["pfirst"],
            "noun_overlap_prev_last_sentence": round(cnt["pfirst_overlap_last"] / max(1, cnt["pfirst"]), 3),
            "noun_overlap_prev_paragraph": round(cnt["pfirst_overlap_prevpara"] / max(1, cnt["pfirst"]), 3),
            "demonstrative": round(cnt["pfirst_demo"] / max(1, cnt["pfirst"]), 3),
            "conjunctive": round(cnt["pfirst_conj"] / max(1, cnt["pfirst"]), 3),
            "no_link": round(cnt["pfirst_none"] / max(1, cnt["pfirst"]), 3),
            "has_doc_top5_noun": round(cnt["pfirst_top5"] / max(1, cnt["pfirst"]), 3),
        },
        "paragraph_topic": {
            "paragraphs_3plus_sentences": cnt["para_with_topic"],
            "top_noun_in_first_sentence": round(cnt["para_topic_in_first"] / max(1, cnt["para_with_topic"]), 3),
            "top_noun_in_last_sentence": round(cnt["para_topic_in_last"] / max(1, cnt["para_with_topic"]), 3),
            "sentences_with_top2_nouns": summarize(S["para_topic_cover"], 2),
            "paragraph_has_doc_top3": round(cnt["para_has_top3"] / max(1, cnt["para_any"]), 3),
            "paragraph_has_doc_top5": round(cnt["para_has_top5"] / max(1, cnt["para_any"]), 3),
        },
        "document_topic": {
            "sentences_with_top3_nouns": summarize(D["sent_with_top3"], 2),
            "sentences_with_top5_nouns": summarize(D["sent_with_top5"], 2),
            "top1_in_first_sentence": round(statistics.fmean(D["top1_in_first_sentence"]), 3) if D["top1_in_first_sentence"] else None,
            "top1_in_first_paragraph": round(statistics.fmean(D["top1_in_first_para"]), 3) if D["top1_in_first_para"] else None,
            "top3_in_first_paragraph": round(statistics.fmean(D["top3_in_first_para"]), 3) if D["top3_in_first_para"] else None,
        },
        "new_noun_rate_by_decile": [round(statistics.fmean(S[f"new_rate_d{d}"]), 2) if S[f"new_rate_d{d}"] else None
                                    for d in range(10)],
        "paragraph_first_sentence_start": {k: round(v / max(1, sum(first_roles.values())), 3)
                                           for k, v in first_roles.most_common()},
    }
    return res


def main():
    cache, repo, out = sys.argv[1], sys.argv[2], sys.argv[3]
    kiwi = Kiwi()
    corpora = C.load_all(cache, repo)
    results = {}
    for name, docs in corpora.items():
        results[name] = measure(docs, kiwi, name)
        if name == "csat":
            results["csat_paragraph_ok"] = measure([d for d in docs if d["para_ok"]], kiwi, "csat_paragraph_ok")
        print(name, "done", results[name]["sentences"], flush=True)
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
