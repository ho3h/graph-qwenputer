"""T3 B: rvc/ir_check.py's session check on tok/'s firmware, the circuit from tok/core.py. The check function is imported unchanged.

    python tok/ir_tok.py --out tok/results/t3_ir.json
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
sys.path.insert(0, C.RVC)
import ir_check as IC  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--graphs", default="cities/c024,random/r001")
    a = ap.parse_args()
    t0 = time.time()
    X = C.X
    T = IC.BR.Text(X.tokenizer_json())
    C.O.set_text(T)
    IC.CONFIG = os.path.join(X.MODEL, "config.json")
    c = IC.core.build(IC.target(), T)
    assert IC.core.__file__.startswith(HERE), IC.core.__file__
    res = {"circuit": c.stats(), "elf_sha256": hashlib.sha256(open(X.build_elf(), "rb").read()).hexdigest(), "sessions": []}
    for name in a.graphs.split(","):
        assert "heldout" not in name
        base = os.path.join(C.X210, "data", "dev", name)
        g = json.load(open(base + ".graph.json"))
        qs = json.load(open(base + ".questions.json"))["questions"]
        calls = []
        for x in qs:
            k = x["call"]["fn"]
            if sum(1 for f, _ in calls if f == k) < 2 and k != "cheapest":
                calls.append((k, x["call"]["args"]))
        calls = calls[:8] + [("find", {"name": g["nodes"][0]["label"]}), ("find", {"name": "no such node"}), ("close", {"node": "@1"}), ("reopen", {"node": "@1"}),
                             ("link", {"from": "@0", "relation": g["relations"][0], "to": "@2", "weight": "3"}),
                             ("unlink", {"from": "@0", "relation": g["relations"][0], "to": "@2"}), ("nofunction", {"a": "b"})]
        r = IC.check_session(c, T, g, calls)
        r["graph"], r["fns"] = name, sorted({f for f, _ in calls})
        res["sessions"].append(r)
        print(json.dumps(r), flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
