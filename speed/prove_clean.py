#!/usr/bin/env python3
"""S18: one arm of the proof on t8's final firmware. python prove_clean.py --flow print-one --part 0 --path fast --stock 0 --out DIR"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fast
ap = argparse.ArgumentParser()
ap.add_argument("--flow", required=True)
ap.add_argument("--part", type=int, required=True)
ap.add_argument("--path", required=True, choices=["fast", "slow"])
ap.add_argument("--stock", type=int, default=0)
ap.add_argument("--out", required=True)
a = ap.parse_args()
g = fast.setup("clean")
assert g.elf_sha == "278e96aa06f53686d4a7d0c75f6030012527efb9b0ecbc00f7a80f1764ce5581", g.elf_sha
cities = json.load(open(os.path.join(X210, "ctrl/results/arm4_draw.json")))["draw"][:16]
lim = [["random/r067", 21], ["random/r075", 23], ["random/r055", 23], ["random/r065", 22], ["random/r084", 21], ["random/r008", 23], ["random/r034", 21], ["random/r019", 46]]
its = fast.items([tuple(x) for x in cities + lim])
for q in json.load(open(os.path.join(X210, "t8/results/panels.json")))["hard"][:8]:
    sub = "cities" if q["graph"].startswith("c") else "random"
    gr = json.load(open(os.path.join(X210, "data", "dev", sub, q["graph"] + ".graph.json")))
    i = int(q["key"].split(":")[1])
    qq = {"id": i, "kind": "chase", "text": q["text"], "call": {"fn": "chase", "args": {"start": q["start"], "legs": "; ".join(f"{r} {k}" for r, k in q["legs"])}}, "answer": [int(q["gold_line"].split()[0][1:])] if q["gold_line"].startswith("@") else [], "answer_text": q["gold_line"]}
    its.append((gr, qq, (f"{sub}/{q['graph']}", 1000000 + i)))
# alternate parts mix the three kinds
part = its[a.part::2]
m = fast.run(part, fast.flow(a.flow), a.out, rows=8, stock=a.stock, stock_limit_s=900, force=a.path)
print(json.dumps({k: m.get(k) for k in ("path", "load_seconds", "stats", "tokens", "bad")}, default=str), flush=True)
sys.exit(3 if m["bad"] else 0)
