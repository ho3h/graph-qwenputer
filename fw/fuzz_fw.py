"""Tests aimed at the fw/ changes, beyond rvc/test_m1.py's parts: the same comparison (rvc/test_m1.py Tally: firmware echo
against host/tools.py parse_call + reflib, TOOLONG predicted) on inputs built to hit the new paths.

    python fw/fuzz_fw.py --firmware fw/graphlib.c --tag fw --seeds 40 [--define ...] [--workers 4]

parse:    Qwen's real call shapes with tokens replaced, deleted, inserted, repeated, or padded past the window
legs:     chase legs with odd separators, whitespace, digits, unknown relations, too many legs
cheapest: small graphs heavy in ties, zero weights, cycles and near-65,535 weights, nothing closed, then closed, then edited
spill:    a graph whose queue must spill (every key pushed before a pop), so the tight search hands over
Bounded: fixed seeds, fixed counts, 60 s alarm per call from Tally. Nothing reads data/heldout.
"""

import argparse
import json
import os
import random
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rvc"))
import fwbox as F  # noqa: E402
import test_m1 as M  # noqa: E402

X = F.X
CFG = os.environ.get("FW_TEST_CFG", "")
PARSE_PER_SEED, LEGS_PER_SEED = 400, 150
POOL = ["<", ">", "</", "\n", "\n\n", ">\n", "parameter", "function", "=", "=name", "=path", "=node", "</function>", "</parameter>",
        "<function=", "<parameter=", "x", " ", "@", "1", ";", "name", "from", "to", "frm", "Oak", "\t", "<|im_end|>"]


def init_worker():
    name, src, extra = CFG.split("|")
    F.set_firmware(name, src, [e for e in extra.split(",") if e])
    M.init_worker()


def small_graph(rng, n=8, zero=False):
    rels = ["r", "s t", "é"]
    edges = {}
    for _ in range(rng.randint(n, 4 * n)):
        a, r, b = rng.randrange(n), rng.randrange(3), rng.randrange(n)
        w = rng.choice([0, 0, 1, 1, 2, 3, 65535, 65534, 30000, 40000]) if zero else rng.randint(0, 9)
        edges[(a, r, b)] = w
    labels = [rng.choice(["Oak", "Elm", "Ash", f"N{i}", f"a b{i}"]) for i in range(n)]
    return M.g_of(n, [(a, r, b, w) for (a, r, b), w in edges.items()], rels=rels, splice=rng.sample(rels, rng.randint(0, 1)),
                  change=rng.choice(rels + [None]), labels=labels)


def task_parse(seed):
    rng = random.Random(seed)
    t = M.Tally("parse")
    g = small_graph(rng)
    N = len(g["nodes"])
    b, G = X.Box(g, M.T), M.reflib.Graph(g)
    pool_ids = [M.T.encode(s) for s in POOL]
    # single vocabulary tokens that hold template characters with something else, which encoding a string may never produce
    near = [[q] for q, b_ in enumerate(M.T.bytes) if 1 < len(b_) < 16 and (b_[:1] in (b">", b"<", b"=") or b_[:2] == b"</" or b_[:1] == b"\n" or b_[-1:] == b">" or b_[-1:] == b"<")]
    near = rng.sample(near, min(400, len(near)))
    pool_ids = pool_ids + near
    shapes = [("find", {"name": "Oak"}), ("find", {"name": "@1 Elm", "has": "r"}), ("follow", {"node": "@0", "relation": "r", "steps": "2"}),
              ("chase", {"start": "@1", "legs": "r 1; s t 2"}), ("neighbours", {"node": "@2", "relation": "r", "direction": "in"}),
              ("path", {"from": "@0", "to": f"@{N - 1}"}), ("cheapest", {"from": "@1", "to": "@2"}),
              ("nofn", {"a": "b"}), ("path", {"to": "@1"})]
    for i in range(PARSE_PER_SEED):
        fn, a = rng.choice(shapes)
        ids = M.enc(fn, a)
        for _ in range(rng.choice([0, 1, 1, 1, 2, 3])):
            k = rng.randrange(len(ids) + 1)
            op = rng.randrange(5)
            if op == 0 and ids:
                del ids[min(k, len(ids) - 1)]
            elif op == 1:
                ids[k:k] = rng.choice(pool_ids)
            elif op == 2 and ids:
                ids[min(k, len(ids) - 1):min(k, len(ids) - 1) + 1] = rng.choice(pool_ids)
            elif op == 3 and ids:
                j = rng.randrange(len(ids))
                ids[k:k] = ids[j:j + rng.randint(1, 12)]
            elif op == 4 and rng.random() < 0.15:
                ids[k:k] = M.T.encode("x " * rng.randint(30, 60))      # past the window
        if 188 in ids:                                                 # NUL token: a known divergence, as in test_m1
            continue
        t.run(b, G, ids, f"parse{seed}#{i} {M.HF.decode(ids)!r}", fn)
        if len(b.ses.toks) > 200000:                                   # keep memory flat: a fresh state now and then
            b, G = X.Box(g, M.T), M.reflib.Graph(g)
    return t.dump()


def task_legs(seed):
    rng = random.Random(10_000 + seed)
    t = M.Tally("legs")
    g = small_graph(rng)
    b, G = X.Box(g, M.T), M.reflib.Graph(g)
    rels = ["r", "s t", "é", "nope", "s  t", " r", "r\n"]
    seps = ["; ", ";", " ; ", ";;", "; ; ", ";\n", ";\t", "; ", "; "]
    nums = ["1", "2", "0", "255", "256", "007", "1_0", "+1", "-1", "99999999", "", "x", "٣", " 1", "1 "]
    for i in range(LEGS_PER_SEED):
        n = rng.choice([1, 1, 2, 2, 3, 4, 16, 17, 18])
        parts = []
        for _ in range(n):
            ws = rng.choice([" ", " ", " ", "  ", "\t", " ", "　", "", "\n"])
            parts.append(rng.choice(rels) + ws + rng.choice(nums[:3] if rng.random() < 0.7 else nums))
        s = ""
        for p in parts:
            s += p + rng.choice(seps)
        s = s[:-rng.randint(0, 2) or None]
        if i % 10 == 0:                                                # a bad relation first, then too many short parts: the leg count outranks it
            s = rng.choice(["nope 1", "r 1", "s t 1"]) + "".join(rng.choice([";x", "; x"]) for _ in range(rng.randint(15, 18)))
        ids = M.enc("chase", {"start": rng.choice(["@0", "@1", "Oak", "@99", "Nope"]), "legs": s})
        if 188 in ids:
            continue
        t.run(b, G, ids, f"legs{seed}#{i} {s!r}", "chase")
    return t.dump()


def task_cheapest(seed):
    rng = random.Random(20_000 + seed)
    t = M.Tally("cheapest")
    for gi in range(6):
        g = small_graph(rng, n=rng.randint(2, 40), zero=True)
        N = len(g["nodes"])
        b, G = X.Box(g, M.T), M.reflib.Graph(g)
        for i in range(24):
            if i in (12, 18):
                t.run(b, G, M.enc("close", {"node": f"@{rng.randrange(N)}"}), f"chp{seed}.{gi} close", "close")
            if i == 21:
                t.run(b, G, M.enc("link", {"from": f"@{rng.randrange(N)}", "relation": "r", "to": f"@{rng.randrange(N)}", "weight": "0"}),
                      f"chp{seed}.{gi} link", "link")
            a = {"from": f"@{rng.randrange(N)}", "to": f"@{rng.randrange(N)}"}
            t.run(b, G, M.enc("cheapest", a), f"chp{seed}.{gi}#{i} {a}", "cheapest")
    return t.dump()


def task_spill(_=None):
    """Hub 0 reaches every node over 4 relations with falling weights: every target improves 4 times before any pop."""
    t = M.Tally("spill")
    N = 900
    edges = []
    for r in range(4):
        for y in range(1, N):
            edges.append((0, r, y, 4000 - 1000 * r + y % 7))
    for y in range(1, N - 1):
        edges.append((y, 0, y + 1, y % 3))
    g = M.g_of(N, edges, rels=("a", "b", "c", "d"))
    b, G = X.Box(g, M.T), M.reflib.Graph(g)
    for a in ({"from": "@0", "to": f"@{N - 1}"}, {"from": "@0", "to": "@450"}, {"from": "@5", "to": "@0"}, {"from": "@0", "to": "@1"}):
        t.run(b, G, M.enc("cheapest", a), f"spill {a}", "cheapest")
    # costs past 2^20: a key would wrap without the saturation
    n = 40
    g = M.g_of(n, [(i, 0, i + 1, 65535) for i in range(n - 1)] + [(0, 1, n - 1, 65535), (5, 1, 7, 3)], rels=("a", "b"))
    b, G = X.Box(g, M.T), M.reflib.Graph(g)
    for a in ({"from": "@0", "to": f"@{n - 2}"}, {"from": "@0", "to": f"@{n - 1}"}, {"from": "@0", "to": "@1"}, {"from": "@0", "to": "@2"}, {"from": "@0", "to": "@19"}, {"from": "@5", "to": "@7"}):
        t.run(b, G, M.enc("cheapest", a), f"chain {a}", "cheapest")
    return t.dump()


def main():
    global CFG
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--define", action="append", default=[])
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--parts", default="parse,legs,cheapest,spill")
    a = ap.parse_args()
    extra = [f"-D{d}" for d in a.define]
    CFG = f"{a.tag}|{os.path.abspath(a.firmware)}|{','.join(extra)}"
    os.environ["FW_TEST_CFG"] = CFG
    F.set_firmware(a.tag, os.path.abspath(a.firmware), extra)
    jobs = []
    for s in range(a.seeds):
        if "parse" in a.parts:
            jobs.append((task_parse, s))
        if "legs" in a.parts:
            jobs.append((task_legs, s))
        if "cheapest" in a.parts:
            jobs.append((task_cheapest, s))
    if "spill" in a.parts:
        jobs.append((task_spill, None))
    t0 = time.time()
    tot, mism = {}, []
    with get_context("spawn").Pool(min(a.workers, 4), initializer=init_worker) as pool:
        for i, r in enumerate(pool.imap_unordered(M.call_job, jobs)):
            p = tot.setdefault(r["part"], {"checks": 0, "match": 0, "toolong": 0, "mismatches": 0})
            for k, v in (("checks", r["checks"]), ("match", r["match"]), ("toolong", r["toolong"]), ("mismatches", r["n_mismatches"])):
                p[k] += v
            mism += r["mismatches"]
            if (i + 1) % 20 == 0 or i + 1 == len(jobs):
                print(f"{time.time() - t0:.0f}s {i + 1}/{len(jobs)} {json.dumps(tot)}", flush=True)
    out = {"firmware": a.firmware, "defines": a.define, "seeds": a.seeds, "seconds": round(time.time() - t0, 1), "parts": tot, "mismatches": mism}
    json.dump(out, open(os.path.join(HERE, "results", f"fuzz_{a.tag}.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(tot), "first:", json.dumps(mism[:2], ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
