#!/usr/bin/env python3
"""Z3: writes.elf with the worked turns against clean.elf, the same questions, print. From saved rows. Writes results/z3_paired.json."""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(HERE)), "t8")]
import arms as A  # noqa: E402

reflib = A.reflib


def rows(n):
    return {str(json.loads(l)["tag"]): json.loads(l) for l in open(os.path.join(HERE, "results", n, "all.jsonl"))}


def line(r):
    res = r["calls"][-1].get("result") if r["calls"] else None
    return reflib.split_reading(res)[1].split("\n")[-1] if res is not None else None


out = {}
for s in ("dev", "hard"):
    a, b = rows(f"chain_print_{s}"), rows(f"chainw_same_print_{s}")
    gained, lost, ex, unasked = [], [], [], []
    ca = cb = 0
    tok = [0, 0]
    prompt = [0, 0]
    for k, ra in a.items():
        rb = b[k]
        g = reflib.reword(ra["gold_text"])
        oa, ob = A.outcome(line(ra), g), A.outcome(line(rb), g)
        ca += oa == "right"
        cb += ob == "right"
        if ob == "right" and oa != "right":
            gained.append(ra["text"][:70])
        if oa == "right" and ob != "right":
            lost.append({"text": ra["text"][:110], "clean": ra["calls"][0].get("args"), "writes": rb["calls"][0].get("args"), "line": rb["calls"][-1].get("result")})
        tok[0] += ra["qwen_tokens"]
        tok[1] += rb["qwen_tokens"]
        prompt[0] += ra["prompt_tokens"]
        prompt[1] += rb["prompt_tokens"]
        for c in rb["calls"]:
            ar = c.get("args") or {}
            if ("closed" in ar or "reopened" in ar) and not re.search(r"(?i)clos|shut|reopen", rb["text"]):
                unasked.append({"text": rb["text"][:120], "args": ar, "result": c.get("result")})
    n, k = len(gained), len(lost)
    p = min(1.0, 2 * sum(math.comb(n + k, i) for i in range(min(n, k) + 1)) / 2 ** (n + k)) if n + k else 1.0
    out[s] = {"clean_right": ca, "writes_right": cb, "gained": n, "lost": k, "p": round(p, 4), "lost_rows": lost, "gained_rows": gained, "qwen_tokens_per_q": [t / len(a) for t in tok], "prompt_tokens_per_q": [t / len(a) for t in prompt], "unasked_writes": unasked}
json.dump(out, open(os.path.join(HERE, "results", "z3_paired.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False)[:3000])
