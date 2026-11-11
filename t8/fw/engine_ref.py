#!/usr/bin/env python3
"""The executor free-running against the reference machine, token by token, with cleaned names: chases, finds and writes on dev graphs, seeded. tok/test_ref.py's check, on the calls that reach the cleaner.

    python t8/fw/tokrun.py ../t8/fw/engine_ref.py --seed 6 --budget 2500000 --limit-s 1200 --out t8/fw/results/engine_ref.json
"""
import argparse
import glob
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/tok")
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from cexec import CExec  # noqa: E402
from speed import free_run  # noqa: E402
import copy  # noqa: E402

SUF = [" station", " station.", ".", ",", "!?", "  station", " Station", " stationx", ";", ":", " .", ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=6)
    ap.add_argument("--budget", type=int, default=2_500_000)
    ap.add_argument("--limit-s", type=float, default=1200)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    L = C.Lite(tokenizer=False)
    T = L.T
    rng = random.Random(a.seed)
    gs = sorted(p for p in glob.glob(os.path.join(C.X210, "data", "dev", "*", "*.graph.json")) if "heldout" not in p)
    ex = None
    t0 = time.time()
    tot = {"calls": 0, "chip": 0, "wrong": 0, "reads": 0, "none": 0, "flags": 0, "does_not_fit": 0}
    worst = []
    while time.time() - t0 < a.limit_s and tot["chip"] < a.budget:
        g = json.load(open(rng.choice(gs)))
        N = len(g["nodes"])
        lab = lambda: g["nodes"][rng.randrange(N)]["label"] + rng.choice(SUF)
        r = rng.choice(g["relations"])
        fn, args = rng.choice([("find", {"name": lab()}), ("chase", {"start": lab(), "legs": f"{r} 1"}), ("chase", {"start": lab(), "legs": f"{r} 2; {r} 1"}), ("follow", {"node": lab(), "relation": r, "steps": "2"}),
                               ("neighbours", {"node": lab(), "relation": r}), ("close", {"node": lab()}), ("reopen", {"node": lab()}), ("link", {"from": lab(), "relation": r, "to": lab()}), ("unlink", {"from": lab(), "relation": r, "to": lab()})])
        try:
            m = D.parked_machine(g, T, None)
        except Exception as e:
            if type(e).__name__ == "BootLimit":
                tot["does_not_fit"] += 1
                continue
            raise
        snap = copy.deepcopy(m)
        ses = BR.Session(T, m)
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, args)) + [T.TCC], max_records=400_000)
        line = T.decode_bytes(ses.runs[-1]).decode("utf-8", "replace")
        tot["reads"] += "name read as" in line
        tot["none"] += "NONE " in line
        core.snapshot(L.c, snap)
        if ex is None:
            ex = CExec(L.c, L.T)
        ex.clear()
        ex.load_init()
        ex.p.flags = 0
        s, nc, n, wrong = free_run(ex, ses.toks)
        tot["calls"] += 1
        tot["chip"] += nc
        tot["wrong"] += wrong
        tot["flags"] += bool(ex.p.flags)
        if (wrong or ex.p.flags) and len(worst) < 5:
            worst.append({"fn": fn, "args": args, "graph": g["name"], "wrong": wrong, "flags": ex.flags()})
        if tot["calls"] % 200 == 0:
            print(tot, f"{time.time() - t0:.0f}s", flush=True)
    res = {"totals": tot, "seconds": round(time.time() - t0, 1), "worst": worst}
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(res, flush=True)
    sys.exit(1 if tot["wrong"] or tot["flags"] else 0)


if __name__ == "__main__":
    main()
