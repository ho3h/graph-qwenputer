#!/usr/bin/env python3
"""Round 11: per-build differences, cross-build line equality on shared rows, and the states the path rows reached. Writes summary.json."""
import collections, glob, json, os, re
EXAM = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
g = json.load(open(os.path.join(EXAM, "items", "nyc_t.graph.json")))
base = {(a, g["relations"][r], b) for a, r, b, w in g["edges"]}
EDGE = re.compile(r"^(linked|unlinked) @(\d+) .*? > (.+?) > @(\d+) ")


def states(rows):
    c = collections.Counter()
    last = None
    for r in rows:
        if r["tag"] != last:
            last, dead, add, closed, ever, self_ = r["tag"], set(), set(), set(), False, False
        b = r["body"]
        m = EDGE.match(b)
        if m:
            e = (int(m[2]), m[3], int(m[4]))
            if m[1] == "unlinked":
                if e in base and e not in add:
                    dead.add(e)
                add.discard(e)
            else:
                add.add(e)
                self_ = self_ or e[0] == e[2]
        elif b.startswith("closed "):
            closed.update(int(x) for x in re.findall(r"@(\d+)", b)); ever = True
        elif b.startswith("reopened "):
            closed.difference_update(int(x) for x in re.findall(r"@(\d+)", b))
        if r["fn"] == "path" and r["status"] == "ok":
            hs = [int(x) for x in re.findall(r"@(\d+)", b)]
            c["path"] += 1
            if not closed:
                c["tight"] += 1
                c["tight_dead_base"] += bool(dead)
                c["tight_added"] += bool(add)
                c["tight_after_close_reopen"] += ever
                c["tight_selfloop"] += self_
                c["tight_nopath_after_write"] += b == "NOPATH" and bool(dead or add)
                if hs:
                    c["tight_target_new_stop"] += hs[-1] >= 496
                    c["tight_start_new_stop"] += hs[0] >= 496
                    c["tight_uses_added_edge"] += any((x, rr, y) in add for x, y in zip(hs, hs[1:]) for rr in g["relations"])
                    c["tight_0_steps"] += b.startswith("0 steps")
            else:
                c["cursor"] += 1
    return c


out = {}
rows = {}
for p in sorted(glob.glob("*.jsonl")):
    n = p[:-6]
    rows[n] = [json.loads(l) for l in open(p)]
    rs = rows[n]
    if rs:
        out[n] = {"rows": len(rs), "neq_reflib": sum(not r["eq"] for r in rs), "status_max": sum(r["status"] == "max" for r in rs), "max_chip": max(r["chip"] for r in rs), "elf": rs[0]["elf"], "ref_engine_ran": "no" if "noref" in n or "fuzz" in n or "cap" in n or n == "r2_aimed" else "yes", "ref_engine_same": sum(r["same_ref"] for r in rs), "states": states(rs)}
idx = {n: {(r["tag"], r["j"]): r for r in rs} for n, rs in rows.items()}
pairs = [("r4_aimed", "r2_aimed"), ("r5_aimed", "r2_aimed"), ("r4_fuzz", "r2_fuzz"), ("r5_fuzz", "r2_fuzz"), ("r5_fuzz", "r4_fuzz"), ("r5_aimed", "r4_aimed"), ("r5_aimed_noref", "r4_aimed"), ("r5_cap", "r4_cap")]
out["cross"] = {}
for a, b in pairs:
    k = set(idx.get(a, {})) & set(idx.get(b, {}))
    d = [x for x in k if idx[a][x]["body"] != idx[b][x]["body"]]
    out["cross"][f"{a} vs {b}"] = {"shared": len(k), "differ": len(d), "differ_rows": sorted(map(str, d))[:6]}
json.dump(out, open("summary.json", "w"), indent=1, default=dict)
print(json.dumps(out, indent=0, default=dict)[:6000])
