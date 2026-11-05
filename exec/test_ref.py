"""Long runs at machine level, beyond what stock can reach here: the engine free-running against the reference machine (bridge.Session), token by token, on dev questions across graphs and one 1,000-node hub. This is not criterion 1 (it does not touch the weights); it asks whether the engine stays on the reference and stays inside its exact range over millions of tokens.

    python test_ref.py --seed 5 --budget 3000000 --limit-s 1200 --out results/test_ref.json
"""
import argparse
import glob
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from cexec import CExec  # noqa: E402
import speed as _s  # noqa: E402,F401  (only for its free_run; its main() is guarded below)
from speed import free_run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--budget", type=int, default=3_000_000, help="stop after this many chip tokens")
    ap.add_argument("--limit-s", type=float, default=1200)
    ap.add_argument("--max-call", type=int, default=400_000)
    ap.add_argument("--hub", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    L = C.Lite(tokenizer=False)
    T = L.T
    qfiles = sorted(glob.glob(os.path.join(C.X210, "data", "dev", "*", "*.questions.json")))
    assert not any("heldout" in q for q in qfiles)
    rng = random.Random(a.seed)
    items = []
    for qf in qfiles:
        for x in json.load(open(qf))["questions"]:
            items.append((qf, x))
    rng.shuffle(items)
    # one call per kind first, so all functions are present whatever the budget does
    seen, first = set(), []
    for it in items:
        if it[1]["call"]["fn"] not in seen:
            seen.add(it[1]["call"]["fn"])
            first.append(it)
    items = first + items
    ex = None
    t0 = time.time()
    tot = {"calls": 0, "chip": 0, "text": 0, "wrong": 0, "seconds_engine": 0.0, "skipped_too_long": 0, "does_not_fit": 0}
    per_fn = {}
    flags = []
    graphs = {}
    worst = None

    def run(g, setup, fn, args, where):
        nonlocal ex, worst
        m = D.parked_machine(g, T, setup)
        snap = __import__("copy").deepcopy(m)
        ses = BR.Session(T, m)
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, args)) + [T.TCC], max_records=a.max_call)
        st = ses.toks
        core.snapshot(L.c, snap)
        if ex is None:
            ex = CExec(L.c, L.T)
        ex.clear()
        ex.load_init()
        ex.p.flags = 0
        s, nc, n, wrong = free_run(ex, st)
        tot["calls"] += 1
        tot["chip"] += nc
        tot["text"] += n - nc
        tot["wrong"] += wrong
        tot["seconds_engine"] += s
        d = per_fn.setdefault(fn, {"calls": 0, "chip": 0, "max_chip": 0})
        d["calls"] += 1
        d["chip"] += nc
        d["max_chip"] = max(d["max_chip"], nc)
        if ex.p.flags:
            flags.append({"where": where, "fn": fn, "flags": ex.flags()})
        if wrong and worst is None:
            worst = {"where": where, "fn": fn, "args": args}

    if a.hub:
        K = 1000
        g = {"format": "x210-graph/1", "name": "hub", "domain": "test", "nodes": [{"label": f"N{i}"} for i in range(K + 2)], "relations": ["r"],
             "edges": sorted([[0, 0, i, 1] for i in range(1, K + 1)] + [[i, 0, K + 1, 1] for i in range(1, K + 1)]), "splice": [], "change": None, "meta": {}}
        run(g, None, "cheapest", {"from": "@0", "to": f"@{K + 1}"}, "hub1000")
        print("hub", per_fn, f"{time.time() - t0:.0f}s", flush=True)
    for qf, x in items:
        if time.time() - t0 > a.limit_s or tot["chip"] > a.budget:
            break
        gp = qf.replace(".questions.json", ".graph.json")
        g = graphs.setdefault(gp, json.load(open(gp)))
        try:
            run(g, x.get("setup"), x["call"]["fn"], x["call"]["args"], os.path.basename(qf) + f"#{x['id']}")
        except RuntimeError as e:                      # the reference run is over --max-call
            tot["skipped_too_long"] += 1
        except Exception as e:
            if type(e).__name__ == "BootLimit":
                tot["does_not_fit"] += 1
            else:
                raise
        if tot["calls"] % 25 == 0:
            print(f"{tot['calls']} calls {tot['chip']} chip wrong {tot['wrong']} flags {len(flags)} {tot['chip'] / max(tot['seconds_engine'], 1e-9):.0f}/s {time.time() - t0:.0f}s", flush=True)
    res = {"totals": {**tot, "chip_per_s_engine": round(tot["chip"] / max(tot["seconds_engine"], 1e-9), 1), "wall_s": round(time.time() - t0, 1)}, "per_fn": per_fn, "flags": flags[:20], "n_flags": len(flags), "first_wrong": worst, "engine": ex.lib_hash, "load_after": _s.load()}
    print(json.dumps({k: v for k, v in res.items() if k != "load_after"}), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
