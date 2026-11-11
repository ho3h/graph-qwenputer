"""Development cost evidence for A4: trace tokens per call, graph ops against the NO_GRAPH_OPS software build, on the
dev graphs of 64-1,024 nodes. A4's predictions: path by EXPAND <= 1/10 of the software BFS's tokens, chase <= 1/5.
Not the gate (A4 is measured on NYC-scale graphs at the frozen run); every number here is a dev measurement.

    python cost_dev.py [--workers 4] [--per 12]
"""

import argparse
import json
import os
import random
import statistics as st
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(X210, "lib"))
import run_call as RC  # noqa: E402
import reflib  # noqa: E402

DEV = os.path.join(X210, "data", "dev")


def measure(path, per):
    g = json.load(open(path))
    N = len(g["nodes"])
    G = reflib.Graph(g)
    try:
        sw = RC.Runner(g, "sw")
    except RC.B.BootLimit as e:  # the software image lives within core memory: no baseline, so no ratio
        return [{"graph": g["name"], "N": N, "E": len(g["edges"]), "R": len(g["relations"]), "fn": "nofit",
                 "why": str(e)}]
    rs = {"gop": RC.Runner(g, "gop"), "gop-cursor": RC.Runner(g, "gop", index=False), "sw": sw}
    rng = random.Random(len(g["edges"]) * 7919 + N)
    rows = []

    def one(fn, args, extra):
        ref = G.call(fn, dict(args))
        row = {"graph": g["name"], "N": N, "E": len(g["edges"]), "R": len(g["relations"]), "fn": fn, "args": args,
               "ref": ref[:60], **extra}
        for b, r in rs.items():
            if fn == "chase" and b == "gop-cursor":
                continue
            text, toks, instr = r.call(fn, args)
            assert text == ref, (b, fn, args, text, ref)
            row[b] = [toks, instr, r.search_tokens]
        rows.append(row)

    pairs = 0
    while pairs < per:
        a, b = rng.randrange(N), rng.randrange(N)
        if a == b:
            continue
        ref = G.path(f"@{a}", f"@{b}")
        D = int(ref.split()[0]) if ref[0].isdigit() else None
        one("path", {"from": f"@{a}", "to": f"@{b}"}, {"D": D})
        pairs += 1
    q = json.load(open(path.replace(".graph.json", ".questions.json")))
    chases = [x for x in q["questions"] if x["call"]["fn"] == "chase" and not x.get("setup")]
    for x in rng.sample(chases, min(per, len(chases))):
        legs = x["call"]["args"]["legs"]
        steps = sum(int(p.split()[-1]) for p in legs.split(";") if p.strip() and p.split()[-1].isdigit())
        one("chase", x["call"]["args"], {"steps": steps, "case": x.get("case")})
    for _ in range(3):  # the fixed per-call cost (parse, resolve, print) for scale
        one("find", {"name": rng.choice(g["nodes"])["label"]}, {})
    return rows


def summarise(rows, fn, b="gop", base="sw", by=None):
    rs = [r for r in rows if r["fn"] == fn and b in r]
    if not rs:
        return None
    ratios = [r[b][0] / r[base][0] for r in rs]
    out = {"calls": len(rs), "tokens_" + b: sum(r[b][0] for r in rs), "tokens_" + base: sum(r[base][0] for r in rs),
           "ratio_of_totals": round(sum(r[b][0] for r in rs) / sum(r[base][0] for r in rs), 4),
           "median_ratio": round(st.median(ratios), 4), "max_ratio": round(max(ratios), 4),
           "min_ratio": round(min(ratios), 4),
           "mean_tokens_" + b: round(st.mean(r[b][0] for r in rs)), "mean_tokens_" + base: round(st.mean(r[base][0] for r in rs))}
    return out


def bucket_n(n):
    return "64-127" if n < 128 else "128-255" if n < 256 else "256-511" if n < 512 else "512-1024"


def bucket_d(d):
    return "NOPATH" if d is None else "1-2" if d <= 2 else "3-5" if d <= 5 else "6-10" if d <= 10 else \
        "11-20" if d <= 20 else "21+"


def grid_probe():
    """How path's cost scales with D: v0 keeps no levels (four sets), so the rebuild recomputes them (O(D^2) records).
    A 22 x 22 grid has NYC's size (484 nodes, 1,848 edges, 26 relations), and longer shortest paths than dev cities."""
    n, rels = 22, [f"line {i}" for i in range(26)]
    edges = []
    for i in range(n):
        for j in range(n):
            h = i * n + j
            if j + 1 < n:
                edges += [[h, i % 26, h + 1, 1], [h + 1, i % 26, h, 1]]
            if i + 1 < n:
                edges += [[h, (22 + j % 4), h + n, 1], [h + n, (22 + j % 4), h, 1]]
    g = {"format": "x210-graph/1", "name": "grid22", "domain": "test", "nodes": [{"label": f"G{h}"} for h in range(n * n)],
         "relations": rels, "edges": sorted(edges), "splice": [], "change": None, "meta": {}}
    G, gop, sw, cur = reflib.Graph(g), RC.Runner(g, "gop"), RC.Runner(g, "sw"), RC.Runner(g, "gop", index=False)
    out = []
    for i, j in ((0, 2), (0, 5), (5, 5), (10, 10), (15, 15), (21, 21)):  # from the corner, D = i + j
        args = {"from": "@0", "to": f"@{i * n + j}"}
        ref = G.call("path", dict(args))
        rows = {"D": i + j}
        for name, r in (("gop", gop), ("gop-cursor", cur), ("sw", sw)):
            text, toks, instr = r.call("path", args)
            assert text == ref, (name, text, ref)
            rows[name] = toks
            rows[name + "_search"] = r.search_tokens
        rows["ratio"] = round(rows["gop"] / rows["sw"], 4)
        rows["search_ratio"] = round(rows["gop_search"] / rows["sw_search"], 4)
        out.append(rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--per", type=int, default=12)
    ap.add_argument("--out", default=os.path.join(HERE, "results", "cost_dev.json"))
    args = ap.parse_args()
    RC.build_elf("gop"), RC.build_elf("sw")
    gs = []
    for d in ("random", "cities"):
        for f in sorted(os.listdir(os.path.join(DEV, d))):
            if f.endswith(".graph.json"):
                p = os.path.join(DEV, d, f)
                n = len(json.load(open(p))["nodes"])
                if 64 <= n <= 1024:
                    gs.append(p)
    t0 = time.time()
    rows = []
    with Pool(args.workers) as pool:
        for r in pool.starmap(measure, [(p, args.per) for p in gs]):
            rows += r
    summ = {"graphs": len(gs), "wall_secs": round(time.time() - t0, 1),
            "no_baseline_graph_too_large": [(r["graph"], r["N"], r["E"], r["why"]) for r in rows if r["fn"] == "nofit"]}
    for fn, pred in (("path", 0.1), ("chase", 0.2), ("find", None)):
        s = summarise(rows, fn)
        if s:
            rs = [r for r in rows if r["fn"] == fn]
            if pred:
                s["prediction"] = pred
                s["calls_within_prediction"] = sum(r["gop"][0] / r["sw"][0] <= pred for r in rs)
            s["by_N"] = {k: summarise([r for r in rs if bucket_n(r["N"]) == k], fn)
                         for k in ("64-127", "128-255", "256-511", "512-1024")}
            if fn == "path":
                s["by_D"] = {k: summarise([r for r in rs if bucket_d(r["D"]) == k], fn)
                             for k in ("NOPATH", "1-2", "3-5", "6-10", "11-20", "21+")}
                s["cursor_vs_sw"] = summarise(rs, fn, "gop-cursor")
                s["search_only_ratio_of_totals"] = round(sum(r["gop"][2] for r in rs) / sum(r["sw"][2] for r in rs), 4)
                s["by_domain"] = {dom: summarise([r for r in rs if r["graph"].startswith(dom)], fn) for dom in "rc"}
            if fn == "chase":
                s["by_domain"] = {dom: summarise([r for r in rs if r["graph"].startswith(dom)], fn) for dom in "rc"}
            summ[fn] = s
    summ["grid_probe"] = grid_probe()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"summary": summ, "rows": rows}, open(args.out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
