"""The clang-built firmware on the circuit's IR, before any weights: every circuit-owned token of real bridge sessions
must equal the IR evaluator's prediction, and the owner bit must agree with the reference at every position.

    python ir_check.py [--calls 12]      # from the vendored folder, under tools/memguard.py

Same check as vendored chat.replay, without a model: the prompt is prefilled history, then Qwen's tokens and the runs.
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.q35 import ir  # noqa: E402
from chipformer.q35.ir import Target  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402

CONFIG = os.path.join(X.MODEL, "config.json")
OUT = os.path.join(HERE, "results", "m1_ir.json")


def target():
    tc = json.load(open(CONFIG))["text_config"]
    return Target(tc["linear_num_key_heads"], tc["linear_num_value_heads"], tc["intermediate_size"])


def check_session(c, T, g, calls, max_tokens=None):
    """calls: list of (fn, args). Returns the counts for the whole stream."""
    m = X.machine_for(g)
    m2 = X.machine_for(g)
    core.snapshot(c, m2)                                  # the snapshot in the circuit's tables, as at decoding
    ses = BR.Session(T, m)
    for fn, args in calls:
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, args)) + [T.TCC])
        ses.qwen([T.encode("x")[0]])                     # a Qwen token between calls, as in a transcript
    st = ses.toks
    carry, mats = {}, []
    t0 = time.time()
    for a in range(0, len(st), 2048):
        mats.append(ir.evaluate(c, st[a:a + 2048], carry=carry))
    mat = np.concatenate(mats)
    pred = core.predictions(c, mat)
    own = np.rint(ir.ev(c.owner, mat)).astype(int)
    bad_own = [x for x in range(len(st)) if own[x] != int(ses.own[x])]
    bad = [x for x in range(len(st) - 1) if ses.own[x] and pred[x] != st[x + 1]]
    return {"positions": len(st), "owned": int(sum(ses.own)), "wrong_predictions": len(bad), "owner_mismatch": len(bad_own),
            "first_wrong": bad[:3], "first_owner": bad_own[:3], "runs": len(ses.runs), "seconds": round(time.time() - t0, 1),
            "halted": m.halted, "fault": m.fault}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphs", default="cities/c024,random/r001")
    ap.add_argument("--calls", type=int, default=8)
    a = ap.parse_args()
    t0 = time.time()
    T = BR.Text(X.tokenizer_json())
    c = core.build(target(), T)
    print(f"core built in {time.time() - t0:.0f}s: {c.stats()}", flush=True)
    res = {"circuit": c.stats(), "elf_sha256": __import__("hashlib").sha256(open(X.build_elf(), "rb").read()).hexdigest(),
           "sessions": []}
    for name in a.graphs.split(","):
        assert "heldout" not in name
        base = os.path.join(X.X210, "data", "dev", name)
        g = json.load(open(base + ".graph.json"))
        qs = json.load(open(base + ".questions.json"))["questions"]
        seen, calls = set(), []
        for x in qs:                                      # the question functions first, cheapest ones last (cost)
            k = x["call"]["fn"]
            if sum(1 for f, _ in calls if f == k) < 2 and k != "cheapest":
                calls.append((k, x["call"]["args"]))
        calls = calls[: a.calls]
        calls += [("find", {"name": g["nodes"][0]["label"]}), ("close", {"node": "@1"}), ("reopen", {"node": "@1"}),
                  ("link", {"from": "@0", "relation": g["relations"][0], "to": "@2", "weight": "3"}),
                  ("unlink", {"from": "@0", "relation": g["relations"][0], "to": "@2"}),
                  ("nofunction", {"a": "b"})]
        r = check_session(c, T, g, calls)
        r["graph"], r["fns"] = name, sorted({f for f, _ in calls})
        res["sessions"].append(r)
        print(json.dumps(r), flush=True)
        json.dump(res, open(OUT, "w"), indent=1)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
