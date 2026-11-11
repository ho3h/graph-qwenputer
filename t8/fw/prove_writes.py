#!/usr/bin/env python3
"""One arm of the proof on writes.elf: prove_clean.py's method, same 32 questions. python prove_writes.py --flow print-one --part 0 --path fast --stock 0 --out DIR"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(X210, "speed"))
import fast
ap = argparse.ArgumentParser()
ap.add_argument("--flow", required=True)
ap.add_argument("--part", type=int, required=True)
ap.add_argument("--path", required=True, choices=["fast", "slow"])
ap.add_argument("--stock", type=int, default=0)
ap.add_argument("--out", required=True)
a = ap.parse_args()
g = fast.setup("writes")
assert os.environ.get("T8_R1") == "1" or g.elf_sha == "bcf1a1dcd1973b7eba67b8249a3be1a3b31944aa412ad9110a404323a7e946a0", g.elf_sha
cities = json.load(open(os.path.join(X210, "ctrl/results/arm4_draw.json")))["draw"][:16]
lim = [["random/r067", 21], ["random/r075", 23], ["random/r055", 23], ["random/r065", 22], ["random/r084", 21], ["random/r008", 23], ["random/r034", 21], ["random/r019", 46]]
its = fast.items([tuple(x) for x in cities + lim])
for q in json.load(open(os.path.join(X210, "t8/results/panels.json")))["hard"][:8]:
    sub = "cities" if q["graph"].startswith("c") else "random"
    gr = json.load(open(os.path.join(X210, "data", "dev", sub, q["graph"] + ".graph.json")))
    i = int(q["key"].split(":")[1])
    qq = {"id": i, "kind": "chase", "text": q["text"], "call": {"fn": "chase", "args": {"start": q["start"], "legs": "; ".join(f"{r} {k}" for r, k in q["legs"])}}, "answer": [int(q["gold_line"].split()[0][1:])] if q["gold_line"].startswith("@") else [], "answer_text": q["gold_line"]}
    its.append((gr, qq, (f"{sub}/{q['graph']}", 1000000 + i)))
# the write path: 8 stated closures, spent in W2, first turns only, as one-question items
for c in json.load(open(os.path.join(X210, "t8/fw/results/edit3_draw.json")))["conversations"][:8]:
    gr = json.load(open(os.path.join(X210, "data", "dev", c["graph"] + ".graph.json")))
    i = int(c["key"].split(":")[1])
    qq = {"id": i, "kind": "chase", "text": c["turns"][0]["user"], "answer": [int(c["turns"][0]["gold"].split()[0][1:])] if c["turns"][0]["gold"].startswith("@") else [], "answer_text": c["turns"][0]["gold"]}
    its.append((gr, qq, (c["graph"], 2000000 + i)))
# alternate parts mix the kinds
part = its[a.part::2]
m = fast.run(part, fast.flow(a.flow), a.out, rows=8, stock=a.stock, stock_limit_s=900, force=a.path)
print(json.dumps({k: m.get(k) for k in ("path", "load_seconds", "stats", "tokens", "bad")}, default=str), flush=True)
sys.exit(3 if m["bad"] else 0)
