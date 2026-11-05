#!/usr/bin/env python3
"""exam/AFTER.md L and L2 from saved rows. python3 exam/score_lines.py DIR DRAW"""
import json
import os
import re
import sys
from collections import Counter

D, DR = sys.argv[1:3]
draw = {c["key"]: c for c in json.load(open(DR))["conversations"]}
c = Counter()
rows = []
def lab(g):
    m = re.search(r"at @\d+ (.+?)(?:, |$)", g) if g.startswith("Stopped") else None
    return m.group(1) if m else g.split(" ", 1)[1] if g.startswith("@") else g
for r in map(json.loads, open(os.path.join(D, "all.jsonl"))):
    k = draw[r["key"]]
    c["n"] += 1
    c["status_" + r["status"]] += 1
    t = r["turns"]
    if "b" in k.get("labels", {}):
        L = k["labels"]
    else:
        L = None
    want_links = k["turns"][0]["wants"][-1]
    if L is None:
        lb = k["labels"]
        want_links = [[lb["a"], lb["b"]], [lb["b"], lb["c"]], [lb["c"], lb["d"]]]
    cs = lambda i: t[i]["calls"] if i < len(t) else []
    adds = {x["args"].get("name") for x in cs(0) if x["fn"] == "add_node" and x["result"].startswith(("added", "closed")) or x["fn"] == "add_node" and "added" in x["result"]}
    links = {(x["args"].get("from"), x["args"].get("to")) for x in cs(0) if x["fn"] == "link" and "linked" in x["result"] and "T northbound" in str(x["args"].get("relation"))}
    new = k["turns"][0]["wants"][1] if k["turns"][0]["wants"][0] == "build" else []
    ok_adds = all(n in adds for n in new)
    ok_links = all(tuple(p) in links for p in want_links)
    c["adds_right"] += ok_adds and bool(new)
    c["links_right"] += ok_links
    out = {"key": r["key"], "status": r["status"], "adds": ok_adds, "links": ok_links}
    for i, nm in ((1, "ride"), (2, "next"), (4, "after")):
        if i >= len(t):
            continue
        g = k["turns"][i]["gold"]
        line = (cs(i)[-1]["result"].split("\n")[-1] if cs(i) else "")
        lineok = line == g
        replyok = lab(g) in (t[i]["reply"] or "")
        c[nm + "_reached"] += 1
        c[nm + "_line_right"] += lineok
        c[nm + "_reply_has_answer"] += replyok
        out[nm] = [lineok, replyok, (t[i]["reply"] or "")[:60]]
    if len(t) > 3:
        un = {(x["args"].get("from"), x["args"].get("to")) for x in cs(3) if x["fn"] == "unlink" and "unlinked" in x["result"]}
        ok = all(tuple(p) in un for p in want_links)
        c["removed_reached"] += 1
        c["removed_right"] += ok
        out["removed"] = ok
    s = r.get("states") or []
    out["ran_on"] = r["ran_on"][:10]
    rows.append(out)
json.dump({"counts": dict(c), "rows": rows}, open(os.path.join(D, "line_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(dict(c)))
for x in rows[:20]:
    print(x)
