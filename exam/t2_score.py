#!/usr/bin/env python3
"""exam/AFTER.md T2, scored by the rule the stranger wrote before any run (results/after/t2/RULES.md), from saved rows. python3 exam/t2_score.py"""
import json
import os
import re
import sys

os.environ.update(T8_R1="1", T8_R2="1")
HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X, "lib"), os.path.join(X, "t8", "fw")]
import noun  # noqa: E402
import reflib  # noqa: E402

R = os.path.join(HERE, "results", "after", "t2")
spec = json.load(open(os.path.join(R, "spec.json")))
WRITES = {"close": "closed ", "reopen": "reopened ", "add_node": "added ", "link": "linked ", "unlink": "unlinked "}
NODE_ARGS = {"node", "from", "to", "start", "name"}


def took_effect(c):
    return c["fn"] in WRITES and any(ln.startswith(WRITES[c["fn"]]) for ln in (c.get("result") or "").split("\n"))


def resolve(labels, c, k):
    """An argument as the node it reaches: a handle, @h label, or the cleaner's 'name read as', otherwise the text."""
    v = str(c["args"].get(k, "")).strip()
    m = re.match(r"@(\d+)", v)
    if m and int(m.group(1)) < len(labels):
        return labels[int(m.group(1))]
    for ln in (c.get("result") or "").split("\n"):
        m = re.match(r"name read as @\d+ (.+)", ln)
        if m and v and (m.group(1) in v or v in m.group(1)):
            return m.group(1)
    return v


def matches(labels, got, want):
    if got["fn"] != want["fn"]:
        return False
    if got["fn"] != "add_node" and (got.get("result") or "").split("\n")[-1].startswith("NONE") and not (want.get("prints", "").startswith("NONE") or resolve(labels, got, "node" if "node" in want["args"] else "from") == str(want["args"].get("node", want["args"].get("from")))):   # the rule's misspelling; a listed call can itself print NONE, and each turn is scored alone
        return False
    if "direction" not in want["args"] and str(got["args"].get("direction", "out")).strip() != "out":   # the audit: no listed direction means out
        return False
    for k, v in want["args"].items():
        if k == "weight":
            if str(got["args"].get("weight", "")).strip() != str(v):
                return False
        elif k == "direction":
            if str(got["args"].get("direction", "out")).strip() != str(v):
                return False
        elif k in NODE_ARGS:
            if resolve(labels, got, k) != str(v):
                return False
        elif str(got["args"].get(k, "")).strip() != str(v):
            return False
    return True


def right(labels, calls, alts):
    for alt in alts:
        want_writes = [w for w in alt if w["fn"] in WRITES]
        if not all(any(matches(labels, g, w) for g in calls) for w in alt):
            continue
        if any(took_effect(g) and not any(matches(labels, g, w) for w in want_writes) for g in calls):
            continue
        order = [g["fn"] for g in calls]
        if "add_node" in order and "link" in order and any(w["fn"] == "link" for w in alt) and any(w["fn"] == "add_node" for w in alt) and order.index("add_node") > order.index("link"):
            continue
        return True
    return False


out = {"turns": [], "by": {}}
for c in spec["conversations"]:
    g = json.load(open(os.path.join(R, c["graph_file"]), encoding="utf-8"))
    labels = [n["label"] for n in g["nodes"]]
    G = reflib.Graph(noun.with_noun(g))
    r = json.loads(open(os.path.join(R, "rows", c["id"] + ".jsonl")).readline())
    for i, t in enumerate(c["turns"]):
        rt = r["turns"][i] if i < len(r["turns"]) else None
        calls = rt["calls"] if rt else []
        eq = sum(G.call(k["fn"], k["args"]) == k["result"] for k in calls)
        out["turns"].append({"conv": c["id"], "n": t["n"], "difficulty": t["difficulty"], "kinds": t.get("hard_kinds", []), "reached": rt is not None, "right": rt is not None and right(labels, calls, t["right"]), "calls": [[k["fn"], k["args"], k["result"]] for k in calls], "firmware_equal_reflib": eq, "n_calls": len(calls), "reply": (rt.get("reply") or "").strip() if rt else None, "status": r["status"]})
T = out["turns"]
for name, sel in (("all", T), ("hard", [t for t in T if t["difficulty"] == "hard"]), ("plain", [t for t in T if t["difficulty"] == "plain"])):
    out["by"][name] = {"turns": len(sel), "right": sum(t["right"] for t in sel), "reached": sum(t["reached"] for t in sel)}
kinds = sorted({k for t in T for k in t["kinds"]})
out["by_kind"] = {k: [sum(t["right"] for t in T if k in t["kinds"]), sum(k in t["kinds"] for t in T)] for k in kinds}
out["calls"], out["equal_reflib"] = sum(t["n_calls"] for t in T), sum(t["firmware_equal_reflib"] for t in T)
json.dump(out, open(os.path.join(R, "score.json"), "w"), indent=1, ensure_ascii=False)
print(out["by"], out["by_kind"], out["calls"], out["equal_reflib"])
