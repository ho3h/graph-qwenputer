"""Item 2, the edit side of the law: what live added edges cost a call on the C build (the overlay is scanned per list).

    python fw/overlay_cost.py     # writes results/overlay_cost.json

c024, the rvc firmware. k random link calls, then the same chase, neighbours and cheapest calls, checked against reflib.
"""

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwbox as F  # noqa: E402

X, BR = F.X, F.BR
sys.path.insert(0, os.path.join(F.X210, "lib"))
import reflib  # noqa: E402


def main():
    F.set_firmware("rvc", os.path.join(F.X210, "rvc", "graphlib.c"))
    T = BR.Text(X.tokenizer_json())
    g = json.load(open(os.path.join(F.X210, "data", "dev", "cities", "c024.graph.json")))
    q = json.load(open(os.path.join(F.X210, "data", "dev", "cities", "c024.questions.json")))
    chases = [x["call"] for x in q["questions"] if x["call"]["fn"] == "chase" and not x.get("setup")][:8]
    N, R = len(g["nodes"]), g["relations"]
    out = []
    for k in (0, 16, 64, 128, 256):
        b, G = X.Box(g, T, max_records=10_000_000), reflib.Graph(g)
        rng = random.Random(k)
        added = 0
        for _ in range(4 * k + 1):                                     # bounded: each attempt is one call
            if added == k:
                break
            a = {"from": f"@{rng.randrange(N)}", "relation": rng.choice(R), "to": f"@{rng.randrange(N)}", "weight": str(rng.randint(1, 9))}
            r = b.call(T.encode(X.template_text("link", a)))
            assert r.result == G.call("link", a)
            added += r.result.startswith("linked")
        row = {"added": added, "tokens": {}}
        calls = chases + [{"fn": "cheapest", "args": {"from": "@1", "to": f"@{N - 2}"}},
                          {"fn": "neighbours", "args": {"node": "@3", "relation": R[0]}}]
        for c in calls:
            try:
                r = b.call(T.encode(X.template_text(c["fn"], c["args"])))
            except RuntimeError:                                       # past the 10M record bound: recorded, and this row ends
                row["tokens"].setdefault(c["fn"] + " over 10M records", []).append(0)
                break
            want = G.call(c["fn"], c["args"])
            assert r.result == want, (r.result, want)
            row["tokens"].setdefault(c["fn"], []).append(r.chip)
        row["mean"] = {f: round(sum(v) / len(v), 1) for f, v in row["tokens"].items()}
        out.append(row)
        print(added, row["mean"], flush=True)
    json.dump(out, open(os.path.join(HERE, "results", "overlay_cost.json"), "w"), indent=0)


if __name__ == "__main__":
    main()
