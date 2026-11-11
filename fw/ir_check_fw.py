"""rvc/ir_check.py on a fw/ build: every circuit-owned token of real bridge sessions against the IR evaluator, no weights.
The check function is imported unchanged. Added to its calls: chase, cheapest (now affordable), and a call the fast path refuses.

    python fw/ir_check_fw.py --firmware fw/graphlib.c --tag fw
"""

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rvc"))
import fwbox as F  # noqa: E402
import ir_check as IC  # noqa: E402

X = F.X


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--graphs", default="cities/c024,random/r001")
    a = ap.parse_args()
    F.set_firmware(a.tag, os.path.abspath(a.firmware))
    t0 = time.time()
    T = IC.BR.Text(X.tokenizer_json())
    c = IC.core.build(IC.target(), T)
    res = {"circuit": c.stats(), "elf_sha256": hashlib.sha256(open(X.ELF, "rb").read()).hexdigest(), "sessions": []}
    out = os.path.join(HERE, "results", f"ir_{a.tag}.json")
    for name in a.graphs.split(","):
        assert "heldout" not in name
        base = os.path.join(X.X210, "data", "dev", name)
        g = json.load(open(base + ".graph.json"))
        qs = json.load(open(base + ".questions.json"))["questions"]
        calls = []
        for x in qs:
            if sum(1 for f, _ in calls if f == x["call"]["fn"]) < 2:
                calls.append((x["call"]["fn"], x["call"]["args"]))
        calls = calls[:14]
        calls += [("find", {"name": g["nodes"][0]["label"]}), ("close", {"node": "@1"}), ("reopen", {"node": "@1"}),
                  ("link", {"from": "@0", "relation": g["relations"][0], "to": "@2", "weight": "3"}),
                  ("cheapest", {"from": "@0", "to": "@2"}),
                  ("unlink", {"from": "@0", "relation": g["relations"][0], "to": "@2"}),
                  ("nofunction", {"a": "b"}), ("find", {"name": "a<b"})]
        r = IC.check_session(c, T, g, calls)
        r["graph"], r["fns"] = name, sorted({f for f, _ in calls})
        res["sessions"].append(r)
        print(json.dumps(r), flush=True)
        json.dump(res, open(out, "w"), indent=1)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
