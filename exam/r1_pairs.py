#!/usr/bin/env python3
"""exam/R1.md: every shared name of New York's with every line one of its nodes has, one leg, on the executor with the reference machine beside it, against reflib under the same rule. Through tokrun, T8_WRITES=1 T8_R1=1. Exit 1 on any difference."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mach as M
import noun as N
import items as I
import reflib
assert os.environ.get("T8_R1") == "1"
out = sys.argv[sys.argv.index("--out") + 1]
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
gp, _ = I.load("nyc")
raw = json.load(open(gp))
g = N.with_noun(raw)
G = reflib.Graph(g)
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
at = {}
for a, r, b, *_ in g["edges"]:
    at.setdefault(a, set()).add(r)
pairs = sorted({(g["nodes"][h]["label"], r) for lab, hs in G.by_label.items() if len(hs) > 1 for h in hs for r in at.get(h, ())})
t0 = time.time()
c = {"pairs": len(pairs), "same_engines": 0, "same_reflib": 0, "narrowed": 0, "ambiguous": 0}
bad = []
for lab, r in pairs:
    kw = {"start": lab, "legs": f"{g['relations'][r]} 1"}
    ids = T.encode(M.CV.X.template_text("chase", kw))
    pair.fresh()
    x = pair.call(ids)
    want = reflib.reword(G.chase(**kw))
    c["same_engines"] += x["same"]
    c["same_reflib"] += x["body"] == want
    c["ambiguous"] += want.startswith("AMBIGUOUS")
    c["narrowed"] += not want.startswith("AMBIGUOUS")
    if not x["same"] or x["body"] != want:
        bad.append([kw, x["body"], x["ref_body"], want])
c["seconds"] = round(time.time() - t0)
c["bad"] = bad[:50]
c["elf"] = os.environ["CHIP_FIRMWARE"]
json.dump(c, open(out, "w"), ensure_ascii=False, indent=0)
print(json.dumps({k: v for k, v in c.items() if k != "bad"}), "bad", len(bad), bad[:2], flush=True)
sys.exit(1 if bad else 0)
