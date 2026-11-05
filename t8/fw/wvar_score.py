#!/usr/bin/env python3
"""Step V's score, from saved rows only, against the adoption rule in t8/REGISTRATION.md. Writes results/wvar_score.json."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
STOP = "did not finish"


def rows(d):
    p = os.path.join(R, d, "all.jsonl")
    return [json.loads(x) for x in open(p)] if os.path.exists(p) else []


def last(r):
    return ((r["calls"][-1].get("result") or "").strip().split("\n")[-1]) if r["calls"] else ""


def outcome(r):
    """As chain_score.py: right on the exact line; else a limit line on a wrong query, a clean wrong line, or loud."""
    f = last(r)
    if r["exact_reworded"] or f == r.get("gold_text_reworded"):
        return "right"
    if f.startswith("Stopped early") or f.startswith("END") or f.startswith("MULTI") or f.startswith("NOCHANGE"):
        return "limit"
    if re.match(r"@\d+ ", f) or re.match(r"\d+ steps:", f):
        return "silent"
    return "loud"


def tally(rs):
    c = {"n": len(rs), "right": 0, "loud": 0, "limit": 0, "silent": 0}
    for r in rs:
        c[outcome(r)] += 1
    return c


def edits(rs, d):
    by = {(c["graph"], c["id"], k): c for k in ("stated", "traps") for c in d[k]}
    o = {"stated_n": 0, "stated_closed_right": 0, "stated_line_right": 0, "stated_changing_right": 0, "traps_n": 0, "traps_false_close": 0, "traps_line_right": 0, "false_wordings": []}
    for r in rs:
        c = by[tuple(r["tag"])]
        wrote = [x["args"].get("closed") for x in r["calls"] if x.get("args", {}).get("closed")]
        line = last(r)
        if r["tag"][2] == "stated":
            o["stated_n"] += 1
            o["stated_closed_right"] += any(c["label"] in w for w in wrote)
            o["stated_line_right"] += line == c["gold"]
            o["stated_changing_right"] += c["changed"] and line == c["gold"]
        else:
            o["traps_n"] += 1
            o["traps_false_close"] += bool(wrote)
            o["traps_line_right"] += line == c["gold"]
            if wrote:
                o["false_wordings"].append(c["wording"])
    return o


def said_stopped(rs):
    g = [r for r in rs if (r.get("gold_text_reworded") or "").startswith("Stopped early")]
    return {"limit_golds": len(g), "said_stopped": sum(bool(re.search(r"stopped|did not finish|didn't finish|not finish|no further|\bNONE\b|no node|not found|does not exist|doesn't exist|unable|cannot|can't|error|not unique|ambiguous", r.get("final") or "", re.I)) for r in g)}


d = json.load(open(os.path.join(R, "wvar_draw.json")))
out = {"edits": {a: edits(rows(f"wvar/{a}_edits_print"), d) for a in ("base", "r")}}
base = {"hard1": "chainw_same_print_hard", "hard2": "chainw_print_hard", "easy1": "chainw_same_print_dev", "easy2": "chainw_print_dev"}
out["print"] = {p: {"base": tally(rows(b)), "r": tally(rows(f"wvar/r_{p}_print"))} for p, b in base.items()}
out["read"] = {p: {"base": {**tally(rows(b)), **said_stopped(rows(b))}, "r": {**tally(rows(f"wvar/r_{p}_read")), **said_stopped(rows(f"wvar/r_{p}_read"))}} for p, b in (("easy2", "chainw_read_dev"), ("hard2", "chainw_read_hard"))}
P = out["print"]
hb = sum(P[p]["base"]["right"] for p in ("hard1", "hard2"))
hr = sum(P[p]["r"]["right"] for p in ("hard1", "hard2"))
lb = sum(P[p]["base"]["limit"] + P[p]["base"]["silent"] for p in ("hard1", "hard2"))
lr = sum(P[p]["r"]["limit"] + P[p]["r"]["silent"] for p in ("hard1", "hard2"))
er = sum(P[p]["r"]["right"] for p in ("easy1", "easy2"))
E_ = out["edits"]
Rd = out["read"]["easy2"]
rule = {"1 hard right": [hr, hb, hr >= hb], "2 hard limit+silent": [lr, lb, lr <= lb], "3 easy right": [er, 198, er >= 198], "4 false closes": [E_["r"]["traps_false_close"], E_["base"]["traps_false_close"], E_["r"]["traps_false_close"] <= E_["base"]["traps_false_close"]],
        "5 closes": [E_["r"]["stated_closed_right"], E_["base"]["stated_closed_right"], E_["r"]["stated_closed_right"] >= E_["base"]["stated_closed_right"] - 1], "6 said stopped": [Rd["r"]["said_stopped"], Rd["base"]["said_stopped"], Rd["r"]["said_stopped"] >= Rd["base"]["said_stopped"]]}
out["rule"], out["adopt"] = rule, all(v[2] for v in rule.values())
json.dump(out, open(os.path.join(R, "wvar_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False))
