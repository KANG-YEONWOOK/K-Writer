#!/usr/bin/env python3
"""Aggregate the structure annotations into counts.

Usage: python -I aggregate_annot.py <cache>/annot/out <out.json>
Writes structure-stats.json. The annotation files hold a model's labels for every paragraph and sentence.
"""
import collections
import glob
import json
import os
import sys

src, out = sys.argv[1], sys.argv[2]
C = collections.Counter


def top(counter, n=40):
    total = sum(counter.values())
    return [[k, v, round(100 * v / total, 1)] for k, v in counter.most_common(n)] if total else []


def csat(files):
    docs = [d for f in files for d in json.load(open(f, encoding="utf-8")) if d["id"] not in ("csat-2023-082", "csat-2023-083")]
    dev, pfunc, pfunc_first, pfunc_last, pfunc_seq = C(), C(), C(), C(), C()
    tpos, plink, role, relation, link, link_first = C(), C(), C(), C(), C(), C()
    role_first, role_last, role_bigram, role_by_func = C(), C(), C(), collections.defaultdict(C)
    attach = C()
    after = collections.defaultdict(C)
    n_par = n_sent = gaps = off = terms = 0
    para_len = C()
    doc_first_role, doc_last_role = C(), C()
    seq_by_func = collections.defaultdict(C)
    for d in docs:
        for x in d.get("development", [])[:1]:
            dev[x] += 1
        gaps += len(d.get("gaps", []))
        off += len(d.get("off_point", []))
        terms += len(d.get("terms", []))
        paras = d["paragraphs"]
        pfunc_seq[" → ".join(p["function"] for p in paras)] += 1
        for i, p in enumerate(paras):
            n_par += 1
            pfunc[p["function"]] += 1
            if i == 0:
                pfunc_first[p["function"]] += 1
            if i == len(paras) - 1:
                pfunc_last[p["function"]] += 1
            else:
                pass
            if len(p["sentences"]) >= 2:
                tpos[p.get("topic_sentence_position", "none")] += 1
            if i:
                plink[p.get("link_to_prev", "없음")] += 1
            ss = p["sentences"]
            para_len[min(len(ss), 9)] += 1
            seq_by_func[p["function"]][" → ".join(s["role"] for s in ss[:4])] += 1
            for j, s in enumerate(ss):
                n_sent += 1
                role[s["role"]] += 1
                role_by_func[p["function"]][s["role"]] += 1
                relation[s.get("relation", "")] += 1
                first_link = (s.get("link") or ["없음"])[0]
                if j == 0:
                    role_first[s["role"]] += 1
                    if i:
                        link_first[first_link] += 1
                else:
                    link[first_link] += 1
                    role_bigram[ss[j - 1]["role"] + " → " + s["role"]] += 1
                    after[ss[j - 1]["role"]][s["role"]] += 1
                    a = s.get("attaches_to", 0)
                    attach["바로 앞 문장" if a == ss[j - 1]["s"] else "새 내용 시작" if not a else "그보다 앞 문장"] += 1
                if j == len(ss) - 1 and len(ss) >= 2:
                    role_last[s["role"]] += 1
        doc_first_role[paras[0]["sentences"][0]["role"]] += 1
        doc_last_role[paras[-1]["sentences"][-1]["role"]] += 1
    return {
        "passages": len(docs), "paragraphs": n_par, "sentences": n_sent, "terms": terms, "gaps": gaps, "off_point": off,
        "development": top(dev), "paragraph_function": top(pfunc), "first_paragraph_function": top(pfunc_first),
        "last_paragraph_function": top(pfunc_last), "paragraph_function_sequences": top(pfunc_seq, 12),
        "topic_sentence_position": top(tpos), "paragraph_link_to_prev": top(plink),
        "sentence_role": top(role), "paragraph_first_sentence_role": top(role_first),
        "paragraph_last_sentence_role": top(role_last), "passage_first_sentence_role": top(doc_first_role),
        "passage_last_sentence_role": top(doc_last_role), "relation": top(relation),
        "link_inside_paragraph": top(link), "link_paragraph_first_sentence": top(link_first),
        "attaches_to": top(attach), "role_bigram": top(role_bigram, 40),
        "what_follows": {k: top(v, 6) for k, v in after.items() if sum(v.values()) >= 15},
        "role_by_paragraph_function": {k: top(v, 6) for k, v in role_by_func.items()},
        "opening_roles_by_function": {k: top(v, 5) for k, v in seq_by_func.items() if sum(v.values()) >= 6},
        "paragraph_sentence_count": sorted(para_len.items()),
    }


def genre(path):
    docs = json.load(open(path, encoding="utf-8"))
    move, first, last, relation, link, bigram, expr = C(), C(), C(), C(), C(), C(), collections.defaultdict(C)
    pos = collections.defaultdict(list)
    n = 0
    for d in docs:
        ss = d["sentences"]
        for j, s in enumerate(ss):
            n += 1
            mv = s["move"].replace("(리드)", "")
            move[mv] += 1
            pos[mv].append(j / max(1, len(ss) - 1))
            relation[s.get("relation", "")] += 1
            if j:
                link[(s.get("link") or ["없음"])[0]] += 1
                bigram[ss[j - 1]["move"].replace("(리드)", "") + " → " + mv] += 1
        first[ss[0]["move"].replace("(리드)", "")] += 1
        last[ss[-1]["move"].replace("(리드)", "")] += 1
        for e in d.get("expressions", []):
            expr[e["move"]][e["phrase"]] += 1
    return {"texts": len(docs), "sentences": n, "move": top(move), "first_sentence_move": top(first),
            "last_sentence_move": top(last), "relation": top(relation), "link": top(link),
            "move_bigram": top(bigram, 25),
            "move_mean_position": sorted(((k, round(sum(v) / len(v), 2), len(v)) for k, v in pos.items()), key=lambda x: x[1]),
            "expressions": {k: [p for p, _ in v.most_common(14)] for k, v in expr.items()}}


res = {}
files = sorted(glob.glob(os.path.join(src, "csat_batch*.json")))
if files:
    res["csat"] = csat(files)
for g in ("news", "abstract", "speech"):
    p = os.path.join(src, f"{g}_batch.json")
    if os.path.isfile(p):
        res[g] = genre(p)
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: (v.get("passages") or v.get("texts"), v["sentences"]) for k, v in res.items()})
