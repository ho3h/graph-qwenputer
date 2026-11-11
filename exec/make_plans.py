"""The acceptance streams, chosen before any executor result: plan_accept.json. Graphs are dev graphs (data/dev, host/test/tiny) and rvc/test_m1's
hand-built limit graphs (never data/heldout). Prints each call's chip tokens on the reference machine, so the plan's stock cost is known first.

    python make_plans.py --out ../exec/plan_accept.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402


def g_of(N, edges, rels=("r",), splice=(), change=None, labels=None):
    """rvc/test_m1.g_of."""
    return {"format": "x210-graph/1", "name": "lim", "domain": "test",
            "nodes": [{"label": labels[i] if labels else f"N{i}"} for i in range(N)], "relations": list(rels),
            "edges": sorted(map(list, edges)), "splice": list(splice), "change": change, "meta": {}}


LINES = g_of(9, [(0, 0, 1, 2), (1, 0, 2, 2), (2, 0, 3, 2), (2, 0, 4, 7), (3, 1, 5, 1), (5, 2, 6, 3), (6, 1, 7, 3), (3, 1, 6, 1), (0, 1, 8, 65535), (8, 1, 7, 1)],
             rels=("a", "t", "b"), splice=("a",), change="t", labels=["Oak", "Elm", "Ash", "Fir", "Yew", "Oak", "Elm", "Bay", "Lone"])
BOUNDS = g_of(6, [(0, 0, 1, 40000), (1, 0, 2, 25535), (2, 0, 3, 1), (0, 1, 4, 65535), (4, 1, 5, 0), (5, 1, 0, 3)], rels=("a", "b"), change="b")
FULLG = g_of(40, [])
FULL_SETUP = [{"fn": "link", "args": {"from": f"@{x}", "relation": "r", "to": f"@{y}"}} for x in range(40) for y in range(40)][:256]

CANDIDATES = [
    {"name": "lim-lines", "graph": LINES, "calls": [
        ["find", {"name": "Oak"}], ["find", {"name": "Nope"}], ["find", {"name": "Oak", "has": "zz"}],
        ["follow", {"node": "@0", "relation": "a", "steps": "2"}], ["follow", {"node": "@3", "relation": "a", "steps": "3"}],
        ["follow", {"node": "@0", "relation": "zz", "steps": "1"}], ["follow", {"node": "@0", "relation": "a", "steps": "x"}],
        ["chase", {"start": "@0", "legs": "a 1; b 1"}], ["chase", {"start": "@0", "legs": "nosep"}],
        ["neighbours", {"node": "@2", "relation": "a", "direction": "in"}], ["neighbours", {"node": "@7", "relation": "a"}],
        ["path", {"from": "@7", "to": "@0"}], ["path", {"from": "@0", "to": "@0"}], ["cheapest", {"from": "@7", "to": "@0"}],
        ["close", {"node": "@1"}], ["close", {"node": "@1"}], ["follow", {"node": "@1", "relation": "a", "steps": "1"}],
        ["reopen", {"node": "@1"}], ["reopen", {"node": "@1"}], ["reopen", {"node": "Nope"}],
        ["link", {"from": "@7", "relation": "a", "to": "@0"}], ["link", {"from": "@7", "relation": "a", "to": "@1", "weight": "65536"}],
        ["unlink", {"from": "@7", "relation": "a", "to": "@0"}], ["unlink", {"from": "@7", "relation": "a", "to": "@0"}],
        ["nofn", {"a": "b"}], ["path", {"to": "@1"}], ["close", {"node": "@1", "extra": "1"}]]},
    {"name": "lim-bounds", "graph": BOUNDS, "calls": [
        ["cheapest", {"from": "@0", "to": "@2"}], ["cheapest", {"from": "@0", "to": "@3"}],
        ["follow", {"node": "@0", "relation": "b", "steps": "255"}], ["follow", {"node": "@0", "relation": "b", "steps": "256"}],
        ["chase", {"start": "@0", "legs": "; ".join(["b 1"] * 8)}], ["chase", {"start": "@0", "legs": "; ".join(["b 1"] * 17)}]]},
    {"name": "lim-full", "graph": FULLG, "setup": FULL_SETUP, "calls": [["link", {"from": "@39", "relation": "r", "to": "@39"}]]},
    {"name": "lim-collide", "graph": None, "calls": []},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    L = C.Lite(tokenizer=False)
    T = L.T
    import boot as B
    from collections import defaultdict
    byh = defaultdict(list)
    for i in range(30000):
        byh[B.ghash(f"n{i}".encode())].append(f"n{i}")
    col = max(byh.values(), key=len)[:3]
    CANDIDATES[3].update(graph=g_of(5, [], labels=col + ["x", "y"]), calls=[["find", {"name": col[1]}], ["find", {"name": col[2]}], ["find", {"name": "n"}]])
    for job in CANDIDATES:
        t0 = time.time()
        m = D.parked_machine(job["graph"], T, job.get("setup"))
        ses = BR.Session(T, m)
        tot = 0
        for fn, args in job["calls"]:
            k = len(ses.toks)
            ses.qwen([T.TCO] + D.enc(L, fn, args) if False else [T.TCO] + T.encode(X.template_text(fn, args)) + [T.TCC])
            n = sum(t < C.S.VOCAB for t in ses.toks[k:])
            r = T.decode_bytes(ses.runs[-1]).decode("utf-8", "replace").split("\n")[2][:50]
            print(f"{job['name']}: {fn} {json.dumps(args)[:70]} chip={n} -> {r!r}", flush=True)
            tot += n
        print(f"== {job['name']}: chip {tot} total positions {len(ses.toks)} {time.time() - t0:.1f}s", flush=True)
    if a.out:
        json.dump(CANDIDATES, open(a.out, "w"), indent=0)


if __name__ == "__main__":
    main()
