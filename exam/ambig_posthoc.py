#!/usr/bin/env python3
"""After the exam, on saved rows, not a score: the 53 refused D1m calls. For each, the nodes sharing the start's label that have a step on the first leg's relation; if one, what the same legs give from it, against the gold. Would a start resolved by the first leg's line have answered? Also: who in the file's question set has an ambiguous start at all."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); X210 = os.path.dirname(HERE)
for p in ("rvc", "t8/fw", "tok", "exam"): sys.path.insert(0, os.path.join(X210, p))
import reflib
g = json.load(open(os.path.join(X210, "data/heldout/nyc/nyc.graph.json")))
R = [json.loads(l) for l in open(os.path.join(HERE, "results/nyc_d1m/all.jsonl"))]
G = reflib.Graph(g)
rels = g["relations"] if "relations" in g else None
out = {"refused": 0, "one_on_line": 0, "several_on_line": 0, "none_on_line": 0, "one_right": 0, "one_other": []}
lab = {}
for i, n in enumerate(g["nodes"]): lab.setdefault(n["label"], []).append(i)
print("labels", len(lab), "nodes", len(g["nodes"]), "shared labels", sum(len(v) > 1 for v in lab.values()), "nodes on shared", sum(len(v) for v in lab.values() if len(v) > 1))
for r in R:
    c = r["calls"][0]
    if not c["result"].startswith("AMBIGUOUS"): continue
    out["refused"] += 1
    a = c["args"]; first = a["legs"].split(";")[0].strip()
    ok = []
    for h in lab[a["start"]]:
        res = G.call("chase", {"start": f"@{h}", "legs": first.rsplit(" ", 1)[0] + " 1"})
        if res.startswith("@"): ok.append(h)
    k = "one_on_line" if len(ok) == 1 else "several_on_line" if ok else "none_on_line"
    out[k] += 1
    if len(ok) == 1:
        res = reflib.reword(G.call("chase", {"start": f"@{ok[0]}", "legs": a["legs"]}))
        if res == reflib.reword(r["gold_text"]): out["one_right"] += 1
        else: out["one_other"].append([r["id"], a, res, r["gold_text"]])
    elif ok:
        outs = {reflib.reword(G.call("chase", {"start": f"@{h}", "legs": a["legs"]})) for h in ok}
        out.setdefault("several", []).append([r["id"], a, ok, r["gold_text"], sorted(outs)])
print(json.dumps(out, ensure_ascii=False, indent=0))
json.dump(out, open(os.path.join(HERE, "results/nyc_d1m_ambig_posthoc.json"), "w"), ensure_ascii=False, indent=0)
