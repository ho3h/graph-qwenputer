"""A1 development test: the C library (graph-op build, graph-op build with EXPAND unindexed, NO_GRAPH_OPS build)
against reflib byte for byte, plus reflib against networkx. Development evidence only; no gate.

    python test_a1_dev.py [--quick] [--workers 4]

Parts (each counted separately; every mismatch is logged in results/a1_dev.json, nothing is relaxed):
  dev       every question of data/dev/{random,cities} (setups applied on a fresh machine), and every label
            resolved by find (this is also the C/Python hash agreement check)
  random    own random graphs (adversarial names, whitespace, relations with digits, self-loops, cycles) with
            random call sequences, close / reopen interleaved on one persistent state
  limits    DEGREE, the EXPAND / set envelopes, N = 4096, boot limits, FULL, OVERFLOW, argument bounds, hash
            collisions
  nx        reflib's neighbours / path / cheapest against networkx on the effective graph (closures included)
"""

import argparse
import json
import os
import random
import signal
import sys
import time
import traceback
import zlib
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(X210, "lib"))
import run_call as RC  # noqa: E402  (sets the vendored path)
import reflib  # noqa: E402
import boot as B  # noqa: E402
import cop_ref as CR  # noqa: E402

DEV = os.path.join(X210, "data", "dev")
BUILDS = [("gop", True), ("gop-cursor", False), ("sw", True)]
SW_SKIPPED = []


def runners(g, builds=BUILDS):
    out = {}
    for name, index in builds:
        v = "sw" if name == "sw" else "gop"
        try:
            out[name] = RC.Runner(g, v, index=index)
        except B.BootLimit as e:
            if v != "sw":  # only the software image may be too small (COPROCESSOR.md: it runs within core memory)
                raise
            SW_SKIPPED.append({"graph": g["name"], "why": str(e)})
    return out


CALL_LIMIT_S = 60


class CallTimeout(Exception):
    pass


def _alarm(*_):
    raise CallTimeout(f"no answer within {CALL_LIMIT_S} s")


def limited(f, *a, **k):
    """Every single call (reflib or machine) has a wall limit, so nothing can hang a worker silently."""
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(CALL_LIMIT_S)
    try:
        return f(*a, **k)
    finally:
        signal.alarm(0)


def ref_call(G, fn, args):
    try:
        return limited(G.call, fn, dict(args))
    except Exception as e:  # reflib itself failing or hanging is a mismatch, never hidden
        return f"<reflib {type(e).__name__}: {e}>"


class Tally:
    def __init__(self):
        self.calls, self.match, self.mism, self.notes = 0, 0, [], []
        self.by_fn = {}

    def check(self, where, fn, args, ref, got):
        for b, (text, toks, instr) in got.items():
            self.calls += 1
            k = self.by_fn.setdefault(f"{fn}/{b}", [0, 0])
            k[0] += 1
            if text == ref:
                self.match += 1
                k[1] += 1
            else:
                self.mism.append({"where": where, "build": b, "fn": fn, "args": args, "ref": ref, "got": text})

    def dump(self):
        return {"calls": self.calls, "match": self.match, "mismatches": self.mism, "notes": self.notes,
                "by_fn": self.by_fn}


def run_all(rs, fn, args):
    out = {}
    for b, r in rs.items():
        try:
            out[b] = limited(r.call, fn, args)
        except Exception as e:
            out[b] = (f"<machine {type(e).__name__}: {e}>", 0, 0)
    return out


# ---------------------------------------------------------------------------------------------------------- dev
def task_dev(path):
    T = Tally()
    q = json.load(open(path))
    gpath = path.replace(".questions.json", ".graph.json")
    g = json.load(open(gpath))
    base = os.path.basename(gpath)
    shared, G0 = runners(g), reflib.Graph(g)
    if "sw" not in shared:
        T.notes.append({"sw_does_not_fit": SW_SKIPPED[-1]})
    for x in q["questions"]:
        call = x["call"]
        fresh = bool(x.get("setup")) or call["fn"] in ("close", "reopen", "link", "unlink")
        if fresh:
            rs, G = runners(g), reflib.Graph(g)
            for s in x.get("setup", []):
                ref = ref_call(G, s["fn"], s["args"])
                if ref != s.get("result", ref):
                    T.notes.append({"where": base, "id": x["id"], "setup_data_vs_reflib": [s["result"], ref]})
                T.check(f"{base}#{x['id']} setup", s["fn"], s["args"], ref, run_all(rs, s["fn"], s["args"]))
        else:
            rs, G = shared, G0
        ref = ref_call(G, call["fn"], call["args"])
        if ref != x["answer_text"]:
            T.notes.append({"where": base, "id": x["id"], "data_vs_reflib": [x["answer_text"], ref]})
        T.check(f"{base}#{x['id']}", call["fn"], call["args"], ref, run_all(rs, call["fn"], call["args"]))
    # every label (hash agreement): all labels on small graphs, a fixed sample of 64 on larger ones
    labels = sorted({n["label"] for n in g["nodes"]})
    if len(labels) > 200:
        labels = random.Random(0).sample(labels, 64)
    for lab in labels:
        args = {"name": lab}
        T.check(f"{base} label", "find", args, ref_call(G0, "find", args), run_all(shared, "find", args))
    return T.dump()


# ------------------------------------------------------------------------------------------------------- random
SYL = ["ka", "lo", "mi", "ner", "sto", "vu", "zan", "qui", "dor", "el"]
UNI = ["Café", "Zürich", "東京駅", "Ñandú", "Ærø", "São Paulo", "Δέλτα"]
WS = [" ", "\t", " ", "　", " ", " ", " ", "\x1f", "\u0085"]
RELS = ["r", "line 2", "7 express", "B 12", "transfer", "x-y", "südwärts", "Q 3 north", "semi;colon", "e"]


def rand_label(rng):
    u = rng.random()
    if u < 0.08:
        return rng.choice(UNI)
    if u < 0.14:
        return rng.choice(WS) + rng.choice(SYL).title() + rng.choice(["", rng.choice(WS)])
    if u < 0.16:
        return rng.choice(["", " ", "@12", "a\nb"])
    return " ".join(rng.choice(SYL).title() + rng.choice(SYL) for _ in range(rng.randint(1, 2)))


def rand_graph(seed, n_lo=3, n_hi=30, deg=2.5, wmax=999, zero=None):
    rng = random.Random(seed)
    zero = seed % 2 == 0 if zero is None else zero
    N = rng.randint(n_lo, n_hi)
    pool = [rand_label(rng) for _ in range(max(2, N * 2 // 3))]
    nodes = [{"label": rng.choice(pool), "prop": rng.randrange(65536), "src": f"n{i}"} for i in range(N)]
    R = rng.randint(1, 6)
    rels = rng.sample(RELS, R)
    edges = set()
    for _ in range(int(N * deg)):
        a, b = rng.randrange(N), rng.randrange(N)
        if a == b and rng.random() < 0.5:
            continue
        edges.add((a, rng.randrange(R), b))
    w = lambda: 0 if zero and rng.random() < 0.3 else (rng.randint(1, wmax) if rng.random() < 0.97 else
                                                       rng.randint(20000, 65535))
    edges = sorted([a, r, b, w()] for a, r, b in edges)
    splice = [r for r in rels if rng.random() < 0.4]
    change = rng.choice(rels) if rng.random() < 0.7 else None
    return {"format": "x210-graph/1", "name": f"t{seed}", "domain": "test", "nodes": nodes, "relations": rels,
            "edges": edges, "splice": splice, "change": change, "meta": {"seed": seed}}


def rand_node(rng, g):
    N, labs = len(g["nodes"]), [n["label"] for n in g["nodes"]]
    u = rng.random()
    if u < 0.4:
        return f"@{rng.randrange(N)}"
    if u < 0.5:
        h = rng.randrange(N)
        return f"@{h} {labs[h]}"
    if u < 0.75:
        return rng.choice(labs)
    if u < 0.82:
        return rng.choice(WS) + rng.choice(labs).strip() + rng.choice(WS)
    h = rng.randrange(N)
    return rng.choice([f"@{N + rng.randrange(5)}", f"@00{rng.randrange(N)}", "@", "@-1", "Nowhere", "", "@ 1",
                       f"@{h} ", f"@{h} {labs[h]}", f"@{h} {labs[h]}", f"@{h}  {labs[h].strip()}",
                       f"@{h}\t{labs[h]} ", f"@{h}\u00a0{labs[h]}", f"@{h} {labs[h]}x", f"@{h} {rng.choice(labs)}",
                       f"@{h}{labs[h]}", f"@{h}\n{labs[h]}", f"@{h} a\nb", f"@{N + 1} {labs[h]}"])


def rand_rel(rng, g):
    u = rng.random()
    if u < 0.8:
        return rng.choice(g["relations"])
    if u < 0.9:
        return " " + rng.choice(g["relations"]) + " "
    return rng.choice(["nope", "", "LINE 2", "line  2"])


def rand_steps(rng):
    return rng.choice(["1", "2", "3", "5", "1", "2", str(rng.randint(1, 20)), "255", "256", "0", "-1", " 3 ", "+2",
                       "1_0", "1__0", "_1", "abc", "", "3 ", "007", "4.0"])


def rand_legs(rng, g):
    n = rng.choice([1, 1, 2, 2, 3, 4, 8, 16, 17])
    parts = []
    for _ in range(n):
        r = rand_rel(rng, g) if rng.random() < 0.9 else rng.choice(g["relations"])
        s = rng.choice(["1", "2", "3", "1", str(rng.randint(1, 6)), "255", "256", "0", "x"])
        sep = rng.choice([" ", " ", " ", "  ", "\t", "　", "", "\n"])
        parts.append(r + sep + s)
    legs = rng.choice(["; ", ";", " ; "]).join(parts)
    if rng.random() < 0.1:
        legs = rng.choice([legs + ";", ";" + legs, legs.replace(";", ";;", 1), "", "  ;  "])
    return legs


def rand_call(rng, g):
    fn = rng.choice(["find", "find", "follow", "follow", "chase", "chase", "chase", "neighbours", "path", "path",
                     "cheapest", "cheapest", "close", "reopen", "reopen", "link", "unlink"])
    a = {}
    if fn == "find":
        a["name"] = rand_node(rng, g)
        if rng.random() < 0.3:
            a["has"] = rand_rel(rng, g)
    elif fn == "follow":
        a = {"node": rand_node(rng, g), "relation": rand_rel(rng, g), "steps": rand_steps(rng)}
    elif fn == "chase":
        a = {"start": rand_node(rng, g), "legs": rand_legs(rng, g)}
    elif fn == "neighbours":
        a = {"node": rand_node(rng, g), "relation": rand_rel(rng, g)}
        if rng.random() < 0.4:
            a["direction"] = rng.choice(["in", "out", "in", "IN", " in", "both"])
    elif fn in ("path", "cheapest"):
        a = {"from" if rng.random() < 0.95 else "frm": rand_node(rng, g), "to": rand_node(rng, g)}
    elif fn in ("link", "unlink"):
        a = {"from": rand_node(rng, g), "relation": rand_rel(rng, g), "to": rand_node(rng, g)}
        if fn == "link" and rng.random() < 0.7:
            a["weight"] = rng.choice(["0", "1", "5", "900", "65535", "65536", "-1", "-0", "+3", " 7 ", "1_0", "abc",
                                      "", "007"])
    else:
        a = {"node": rand_node(rng, g)}
    u = rng.random()
    if u < 0.02:
        a["extra"] = "1"
    elif u < 0.04 and a:
        a.pop(next(iter(a)))
    elif u < 0.05:
        fn = rng.choice(["Find", "bfs", "", "path "]) or "x"
    return fn, a


def task_random(seed, n_calls=80, **kw):
    T = Tally()
    g = rand_graph(seed, **kw)
    rng = random.Random(10_000 + seed)
    rs, G = runners(g), reflib.Graph(g)
    for i in range(n_calls):
        fn, a = rand_call(rng, g)
        T.check(f"rand{seed}#{i}", fn, a, ref_call(G, fn, a), run_all(rs, fn, a))
    return T.dump()


def task_medium(seed):
    """Larger random graphs: path / cheapest with closures, through EXPAND and the cursor search."""
    T = Tally()
    rng = random.Random(seed)
    g = rand_graph(seed, n_lo=150, n_hi=1024, deg=rng.choice([1.1, 1.5, 3.0]))
    N = len(g["nodes"])
    rs, G = runners(g), reflib.Graph(g)
    for i in range(24):
        if i in (8, 16):
            for _ in range(rng.randint(1, 6)):
                a = {"node": f"@{rng.randrange(N)}"}
                T.check(f"med{seed} close", "close", a, ref_call(G, "close", a), run_all(rs, "close", a))
        fn = rng.choice(["path", "path", "cheapest", "chase", "neighbours", "link", "unlink"])
        if fn in ("link", "unlink"):
            if fn == "unlink" and g["edges"] and rng.random() < 0.8:
                e = rng.choice(g["edges"])
                a = {"from": f"@{e[0]}", "relation": g["relations"][e[1]], "to": f"@{e[2]}"}
            else:
                a = {"from": f"@{rng.randrange(N)}", "relation": rng.choice(g["relations"]),
                     "to": f"@{rng.randrange(N)}"}
                if fn == "link":
                    a["weight"] = str(rng.randint(0, 900))
        elif fn == "chase":
            fn, a = "chase", {"start": f"@{rng.randrange(N)}", "legs": rand_legs(rng, g)}
        elif fn == "neighbours":
            a = {"node": f"@{rng.randrange(N)}", "relation": rng.choice(g["relations"]),
                 "direction": rng.choice(["in", "out"])}
        else:
            a = {"from": f"@{rng.randrange(N)}", "to": f"@{rng.randrange(N)}"}
        T.check(f"med{seed}#{i}", fn, a, ref_call(G, fn, a), run_all(rs, fn, a))
    return T.dump()


# ------------------------------------------------------------------------------------------------------- limits
def g_of(N, edges, rels=("r",), splice=(), change=None, labels=None):
    return {"format": "x210-graph/1", "name": "lim", "domain": "test",
            "nodes": [{"label": labels[i] if labels else f"N{i}"} for i in range(N)], "relations": list(rels),
            "edges": sorted(map(list, edges)), "splice": list(splice), "change": change, "meta": {}}


def task_limits(_=None):
    T = Tally()

    def cmp(where, g, calls, builds=BUILDS):
        rs, G = runners(g, builds), reflib.Graph(g)
        for fn, a in calls:
            T.check(where, fn, a, ref_call(G, fn, a), run_all(rs, fn, a))
        return rs

    # DEGREE: 300 nodes feed one hub; a level of 300 sums to 300 > DEGREE_MAX at the hub
    K = 300
    edges = [(0, 0, i, 1) for i in range(1, K + 1)] + [(i, 0, K + 1, 1) for i in range(1, K + 1)] + \
            [(K + 1, 0, K + 2, 1)]
    g = g_of(K + 3, edges)
    rs = cmp("degree", g, [("path", {"from": "@0", "to": f"@{K + 2}"}), ("path", {"from": "@5", "to": f"@{K + 2}"}),
                           ("cheapest", {"from": "@0", "to": f"@{K + 2}"}),
                           ("neighbours", {"node": f"@{K + 1}", "relation": "r", "direction": "in"})])
    m = rs["gop"].m
    cop = rs["gop"].cop
    cop.sets[0] = set(range(1, K + 1))
    T.notes.append({"degree_direct": cop.exec("EXPAND", 0 | 2 << 2 | 0 << 4 | 0 << 10, 0) == CR.DEGREE})
    del m

    # N beyond the EXPAND / set envelope (1,500 nodes, gop only: the software image holds N <= 1,024)
    rng = random.Random(7)
    N = 1500
    edges = {(i, 0, i + 1, rng.randint(1, 9)) for i in range(N - 1)} | \
            {(rng.randrange(N), 0, rng.randrange(N), rng.randint(1, 9)) for _ in range(400)}
    edges = {e for e in edges if e[0] != e[2]}
    uniq = {}
    for a, r, b, w in sorted(edges):
        uniq[(a, r, b)] = w
    g = g_of(N, [(a, r, b, w) for (a, r, b), w in uniq.items()])
    cmp("N1500", g, [("path", {"from": "@0", "to": "@1499"}), ("path", {"from": "@700", "to": "@3"}),
                     ("close", {"node": "@10"}), ("path", {"from": "@0", "to": "@1499"}),
                     ("cheapest", {"from": "@0", "to": "@1499"}), ("reopen", {"node": "@10"}),
                     ("find", {"name": "N1499"})], builds=[("gop", True)])

    # the full node envelope: N = 4,096 boots and answers; 4,097 is refused
    N = 4096
    g = g_of(N, [(i, 0, i + 1, 1) for i in range(N - 1)])
    cmp("N4096", g, [("follow", {"node": "@4000", "relation": "r", "steps": "95"}),
                     ("follow", {"node": "@4000", "relation": "r", "steps": "96"}),
                     ("find", {"name": "N4095"}), ("path", {"from": "@4090", "to": "@4095"})],
        builds=[("gop", True)])
    for what, gg in (("N4097", g_of(4097, [])), ("label65", g_of(2, [], labels=["x" * 65, "y"])),
                     ("labelNFD", g_of(2, [], labels=["Café", "y"])),
                     ("E16385", g_of(4096, [(i % 4096, i // 4096, (i * 7 + 1) % 4096, 1) for i in range(16385)],
                                       rels=("a", "b", "c", "d", "e")))):
        try:
            B.boot(gg, b"", software=False)
            T.notes.append({"boot_limit": what, "raised": False})
            T.mism.append({"where": "boot", "what": what, "error": "accepted beyond its envelope"})
        except (B.BootLimit, CR.CopError) as e:
            T.notes.append({"boot_limit": what, "raised": str(e)[:80]})
    # FULL from GADD at the row bound, then a GDEL frees a row again
    cop = CR.Cop()
    for i in range(2):
        cop.add_node(b"n")
    rows = [cop.gadd(0, i % 64, 1, 1) for i in range(CR.E_ROWS)]
    full = cop.exec("GADD", 0 | 5 << 12, 1 | 3 << 16)
    cop.exec("GDEL", rows[17], 0)
    again = cop.exec("GADD", 0 | 5 << 12, 1 | 3 << 16)
    T.notes.append({"FULL": full == CR.FULL, "reuse_after_GDEL": again == rows[17]})
    if full != CR.FULL or again != rows[17]:
        T.mism.append({"where": "FULL", "full": full, "again": again})

    # OVERFLOW, step and leg bounds
    g = g_of(6, [(0, 0, 1, 40000), (1, 0, 2, 25535), (2, 0, 3, 1), (0, 1, 4, 65535), (4, 1, 5, 0), (5, 1, 0, 3)],
             rels=("a", "b"), change="b")
    cmp("bounds", g, [("cheapest", {"from": "@0", "to": "@2"}), ("cheapest", {"from": "@0", "to": "@3"}),
                      ("cheapest", {"from": "@0", "to": "@5"}), ("cheapest", {"from": "@4", "to": "@3"}),
                      ("follow", {"node": "@0", "relation": "b", "steps": "255"}),
                      ("follow", {"node": "@0", "relation": "b", "steps": "256"}),
                      ("chase", {"start": "@0", "legs": "; ".join(["b 1"] * 16)}),
                      ("chase", {"start": "@0", "legs": "; ".join(["b 1"] * 17)}),
                      ("chase", {"start": "@0", "legs": "a 1; a 1; a 1"})])
    # edits: link / unlink through every route, EXPAND's index kept current, closures across edits
    g = g_of(8, [(0, 0, 1, 2), (1, 0, 2, 2), (2, 0, 3, 2), (3, 1, 4, 1), (5, 1, 5, 7)], rels=("a", "b"),
             splice=("a",), change="b")
    cmp("edits", g, [("path", {"from": "@0", "to": "@4"}), ("link", {"from": "@0", "relation": "a", "to": "@7"}),
                     ("link", {"from": "@0", "relation": "a", "to": "@7", "weight": "9"}),
                     ("link", {"from": "@0", "relation": "a", "to": "@2", "weight": "1"}),
                     ("neighbours", {"node": "@0", "relation": "a"}), ("cheapest", {"from": "@0", "to": "@3"}),
                     ("link", {"from": "@7", "relation": "b", "to": "@4", "weight": "65535"}),
                     ("path", {"from": "@0", "to": "@4"}), ("cheapest", {"from": "@0", "to": "@4"}),
                     ("unlink", {"from": "@0", "relation": "a", "to": "@2"}),
                     ("unlink", {"from": "@0", "relation": "a", "to": "@2"}), ("path", {"from": "@0", "to": "@4"}),
                     ("unlink", {"from": "@0", "relation": "a", "to": "@1"}), ("path", {"from": "@0", "to": "@3"}),
                     ("link", {"from": "@0", "relation": "a", "to": "@1", "weight": "4"}),
                     ("close", {"node": "@1"}), ("link", {"from": "@0", "relation": "a", "to": "@1"}),
                     ("unlink", {"from": "@1", "relation": "a", "to": "@2"}), ("cheapest", {"from": "@0", "to": "@3"}),
                     ("reopen", {"node": "@1"}), ("follow", {"node": "@5", "relation": "b", "steps": "9"}),
                     ("unlink", {"from": "@5", "relation": "b", "to": "@5"}),
                     ("follow", {"node": "@5", "relation": "b", "steps": "9"}),
                     ("link", {"from": "@6", "relation": "b", "to": "@6"}), ("find", {"name": "N6", "has": "b"}),
                     ("link", {"from": "@0", "relation": "zz", "to": "@1"}),
                     ("link", {"from": "@0", "relation": "a", "to": "@1", "weight": "x"}),
                     ("link", {"from": "@0", "relation": "a"}), ("unlink", {"from": "@0", "to": "@1"})])
    # FULL at the row bound through link (gop), and at the software overlay's bound (sw): reflib has no such limit,
    # so these are compared with the explicit expected text, not reflib
    N = 4096
    g = g_of(N, [(i % N, i // N, (i * 7 + 1) % N, 1) for i in range(CR.E_ROWS)], rels=("a", "b", "c", "d"))
    r = RC.Runner(g, "gop")
    args = {"from": "@0", "relation": "a", "to": "@5"}
    t1 = r.call("link", args)[0]
    t2 = r.call("unlink", {"from": "@0", "relation": "a", "to": "@1"})[0]
    t3 = r.call("link", args)[0]
    want = ("FULL", "unlinked @0 N0 > a > @1 N1", "linked @0 N0 > a > @5 N5")
    T.notes.append({"FULL_via_link": (t1, t2, t3)})
    if (t1, t2, t3) != want:
        T.mism.append({"where": "FULL_via_link", "got": (t1, t2, t3), "want": want})
    g = g_of(40, [])
    r = RC.Runner(g, "sw")
    texts = [r.call("link", {"from": f"@{i % 40}", "relation": "r", "to": f"@{i // 40}"})[0] for i in range(257)]
    T.notes.append({"sw_overlay_full_at": next((i for i, t in enumerate(texts) if t == "FULL"), None)})
    # a hub of out-degree 3,000 (no library limit below the envelope), weights falling with the handle so the
    # queue's dropped keys are the smallest ones; also through a closed hub on a splice relation
    N = 4096
    hub = [(0, 0, i, 4000 - i) for i in range(1, 3001)] + [(i, 1, 3500, 1) for i in range(1, 3001)]
    g = g_of(N, hub, rels=("r", "s"), splice=("r",), change="r")
    cmp("hub3000", g, [("follow", {"node": "@0", "relation": "r", "steps": "1"}),
                       ("find", {"name": "N0", "has": "r"}), ("neighbours", {"node": "@3500", "relation": "s",
                                                                              "direction": "in"}),
                       ("path", {"from": "@0", "to": "@3500"}), ("cheapest", {"from": "@0", "to": "@3500"}),
                       ("chase", {"start": "@3500", "legs": "s 1"}), ("chase", {"start": "@0", "legs": "s 1; s 1"}),
                       ("link", {"from": "@3", "relation": "r", "to": "@0"}), ("close", {"node": "@0"}),
                       ("follow", {"node": "@3", "relation": "r", "steps": "1"}),
                       ("neighbours", {"node": "@3", "relation": "r"}), ("cheapest", {"from": "@3", "to": "@3000"}),
                       ("cheapest", {"from": "@3", "to": "@3500"}), ("path", {"from": "@3", "to": "@3000"})],
        builds=[("gop", True)])
    g = g_of(1024, [(0, 0, i, 1) for i in range(1, 1001)])
    cmp("hub1000", g, [("neighbours", {"node": "@0", "relation": "r"}), ("follow", {"node": "@0", "relation": "r",
                                                                                     "steps": "1"}),
                       ("cheapest", {"from": "@0", "to": "@999"}), ("path", {"from": "@0", "to": "@999"})])
    # the "@h label" form, every outcome, on find / close / reopen / path
    g = g_of(4, [(0, 0, 1, 1), (1, 0, 2, 1)], labels=["A b", "A b", "C", "\u3000D\u3000"])
    cmp("@label", g, [("find", {"name": "@0 A b"}), ("find", {"name": "@1  A b "}), ("find", {"name": "@2 A b"}),
                      ("find", {"name": "@9 A b"}), ("find", {"name": "@3 D"}), ("find", {"name": "@3\u3000D"}),
                      ("find", {"name": "@3 \u3000D\u3000"}), ("find", {"name": "@0A b"}),
                      ("find", {"name": "@0 A\nb"}), ("find", {"name": "@0\nA b"}), ("path", {"from": "@0 A b", "to": "@2 C"}),
                      ("close", {"node": "@1 A b"}), ("find", {"name": "@1 A b"}), ("close", {"node": "@1 A b"}),
                      ("close", {"node": "@1 C"}), ("reopen", {"node": "@1 C"}), ("reopen", {"node": "@9 A b"}),
                      ("reopen", {"node": "@0 A b"}), ("reopen", {"node": "@1 A b"}),
                      ("link", {"from": "@2 C", "relation": "r", "to": "@3 D"}),
                      ("unlink", {"from": "@2 C", "relation": "r", "to": "@3 x"})])
    # weights through adjacent closed nodes are minimal whatever the handle order
    g = g_of(4, [(0, 0, 2, 10), (0, 0, 1, 1), (1, 0, 2, 1), (2, 0, 3, 1)], splice=("r",))
    cmp("seen-order", g, [("close", {"node": "@1"}), ("close", {"node": "@2"}), ("cheapest", {"from": "@0", "to": "@3"}),
                          ("neighbours", {"node": "@0", "relation": "r"}), ("path", {"from": "@0", "to": "@3"}),
                          ("neighbours", {"node": "@3", "relation": "r", "direction": "in"})])
    # labels that collide in the 12-bit hash, plus whitespace-only and empty labels
    seen, coll = {}, None
    for i in range(100000):
        s = f"Coll{i}"
        h = B.ghash(s.encode())
        if h in seen:
            coll = (seen[h], s)
            break
        seen[h] = s
    labs = [coll[0], coll[1], coll[0], "", "  ", "　x　", "x"]
    g = g_of(len(labs), [(0, 0, 1, 1), (1, 0, 2, 1)], labels=labs)
    cmp("collide", g, [("find", {"name": coll[0]}), ("find", {"name": coll[1]}), ("find", {"name": coll[0], "has": "r"}),
                       ("find", {"name": ""}), ("find", {"name": "x"}), ("find", {"name": " x "}),
                       ("close", {"node": coll[1]}), ("find", {"name": coll[1]}), ("reopen", {"node": coll[1]}),
                       ("reopen", {"node": coll[0]}), ("close", {"node": coll[0]}), ("close", {"node": "@0"}),
                       ("close", {"node": "@2"}), ("reopen", {"node": coll[0]}), ("reopen", {"node": "@99"})])
    T.notes.append({"hash_collision": coll, "hash": B.ghash(coll[0].encode())})
    return T.dump()


# ----------------------------------------------------------------------------------------------------------- nx
def eff_true(G, h, r, d):
    """Effective edges with true minimum weights (Dijkstra through closed interiors), independent of reflib."""
    import heapq
    raw = G.out if d == "out" else G.inn
    best, dist, pq = {}, {}, [(w, y) for y, w in raw.get((h, r), [])]
    heapq.heapify(pq)
    while pq:
        w, y = heapq.heappop(pq)
        if y not in G.closed:
            if y not in best or w < best[y]:
                best[y] = w
            continue
        if r not in G.splice or y in dist:
            continue
        dist[y] = w
        for z, v in raw.get((y, r), []):
            heapq.heappush(pq, (w + v, z))
    return best


def task_nx(spec):
    import heapq
    import networkx as nx
    T = Tally()
    kind, arg = spec
    if kind == "file":
        g = json.load(open(arg))
        where = os.path.basename(arg)
    elif kind == "quirk":
        g = g_of(4, [(0, 0, 2, 10), (0, 0, 1, 1), (1, 0, 2, 1), (2, 0, 3, 1)], splice=("r",))
        where = "quirk"
    else:
        g = rand_graph(arg, n_lo=5, n_hi=60)
        where = f"rand{arg}"
    rng = random.Random(zlib.crc32(where.encode()))
    G = reflib.Graph(g)
    N = len(G.labels)

    def one_state(tag):
        D = nx.DiGraph()
        D.add_nodes_from(h for h in range(N) if h not in G.closed)
        per = {}
        for r in range(len(G.rels)):
            for h in range(N):
                if h in G.closed:
                    continue
                for d in ("out", "in"):
                    t = eff_true(G, h, r, d)
                    per[(h, r, d)] = t
                    if d == "out":
                        for y, w in t.items():
                            if not D.has_edge(h, y) or w < D[h][y]["weight"]:
                                D.add_edge(h, y, weight=w)
                    mine = dict(G.eff(h, r, d))
                    T.calls += 1
                    if set(mine) != set(t):
                        T.mism.append({"where": f"{where}/{tag}", "fn": "eff-set", "h": h, "r": r, "d": d})
                    elif mine != t:
                        T.notes.append({"where": f"{where}/{tag}", "reflib_eff_weight_vs_true_min": [h, r, d,
                                        sorted(mine.items()), sorted(t.items())]})
                        T.match += 1
                    else:
                        T.match += 1
        # neighbours vs networkx (per-relation DiGraph of the effective edges)
        for _ in range(20):
            h, r, d = rng.randrange(N), rng.randrange(len(G.rels)), rng.choice(["out", "in"])
            if h in G.closed:
                continue
            Dr = nx.DiGraph()
            for (x, rr, dd), t in per.items():
                if rr == r and dd == "out":
                    Dr.add_edges_from((x, y) for y in t)
            Dr.add_node(h)
            ys = sorted(Dr.successors(h) if d == "out" else Dr.predecessors(h))
            want = "\n".join(G.fmt(y) for y in ys) if ys else "NONE"
            got = limited(G.neighbours, f"@{h}", G.rels[r], d)
            T.calls += 1
            T.match += got == want
            if got != want:
                T.mism.append({"where": f"{where}/{tag}", "fn": "neighbours", "h": h, "r": r, "d": d,
                               "nx": want, "reflib": got})
        # path: hop count = nx; canonical = lowest-handle predecessor at distance k - 1 (nx distances)
        for _ in range(25):
            a, b = rng.randrange(N), rng.randrange(N)
            if a in G.closed or b in G.closed:
                continue
            try:
                got = limited(G.path, f"@{a}", f"@{b}")
            except CallTimeout as e:
                got = f"<reflib CallTimeout: {e}>"
            T.calls += 1
            if not nx.has_path(D, a, b):
                ok, want = got == "NOPATH", "NOPATH"
            else:
                dist = nx.single_source_shortest_path_length(D, a)
                seq, y = [b], b
                while y != a:
                    y = min(x for x in D.predecessors(y) if dist.get(x) == dist[y] - 1)
                    seq.append(y)
                want = f"{dist[b]} steps: " + " > ".join(G.fmt(h) for h in reversed(seq))
                ok = got == want
            T.match += ok
            if not ok:
                T.mism.append({"where": f"{where}/{tag}", "fn": "path", "a": a, "b": b, "nx": want, "reflib": got})
        # cheapest: cost = nx Dijkstra; canonical pred (SPEC 5) = lowest x finalised before y with d(x) + w = d(y)
        for _ in range(25):
            a, b = rng.randrange(N), rng.randrange(N)
            if a in G.closed or b in G.closed:
                continue
            try:
                got = limited(G.cheapest, f"@{a}", f"@{b}")
            except Exception as e:
                got = f"<reflib {type(e).__name__}: {e}>"
            T.calls += 1
            if not nx.has_path(D, a, b):
                want = "NOPATH"
            else:
                dist = nx.single_source_dijkstra_path_length(D, a)
                if dist[b] > 65535:
                    want = "OVERFLOW"
                else:
                    # the finalisation order, from nx's distances: among nodes already reached from a finalised
                    # node, lowest (cost, handle) next (zero-weight edges can reveal a lower handle late)
                    pred, fin, reached, pq = {a: None}, set(), {a}, [(0, a)]
                    while pq:
                        _, x = heapq.heappop(pq)
                        if x in fin:
                            continue
                        fin.add(x)
                        for y in D.successors(x):
                            if y in fin or dist[x] + D[x][y]["weight"] != dist[y]:
                                continue
                            if y not in pred or x < pred[y]:
                                pred[y] = x
                            if y not in reached:
                                reached.add(y)
                                heapq.heappush(pq, (dist[y], y))
                    seq, y = [b], b
                    while pred[y] is not None:
                        y = pred[y]
                        seq.append(y)
                    want = f"cost {dist[b]}: " + " > ".join(G.fmt(h) for h in reversed(seq))
            T.match += got == want
            if got != want:
                T.mism.append({"where": f"{where}/{tag}", "fn": "cheapest", "a": a, "b": b, "nx": want,
                               "reflib": got})

    one_state("open")
    for h in ([1, 2] if kind == "quirk" else rng.sample(range(N), min(N, max(1, N // 8)))):
        G.closed.add(h)
    one_state("closed")
    if kind != "quirk":  # edits, then the same checks again
        for _ in range(max(2, N // 6)):
            a, b, r = rng.randrange(N), rng.randrange(N), rng.choice(G.rels)
            G.closed.discard(a), G.closed.discard(b)
            if rng.random() < 0.5:
                G.link(f"@{a}", r, f"@{b}", str(rng.randint(0, 500)))
            elif g["edges"]:
                e = rng.choice(g["edges"])
                G.closed.discard(e[0]), G.closed.discard(e[2])
                G.unlink(f"@{e[0]}", G.rels[e[1]], f"@{e[2]}")
        one_state("edited")
    return T.dump()


def task_zero(_=None):
    """Zero-weight edges (SPEC 1 allows them): every pair of each hand-built tie case, C against reflib."""
    T = Tally()
    cases = {"zero-cycle-at-source": g_of(3, [(0, 0, 1, 0), (1, 0, 0, 0), (1, 0, 2, 5)]),
             "zero-tie-later-pred": g_of(4, [(0, 0, 2, 1), (0, 0, 3, 1), (3, 0, 1, 0), (2, 0, 1, 1), (1, 0, 3, 0)]),
             "zero-done-node-repred": g_of(4, [(0, 0, 3, 0), (3, 0, 1, 1), (0, 0, 2, 1), (2, 0, 1, 0)]),
             "zero-pred-cycle": g_of(4, [(0, 0, 3, 1), (3, 0, 1, 0), (1, 0, 2, 0), (2, 0, 1, 0)])}
    for name, g in cases.items():
        rs, G = runners(g), reflib.Graph(g)
        for a in range(len(g["nodes"])):
          for b in range(len(g["nodes"])):
            args = {"from": f"@{a}", "to": f"@{b}"}
            ref = ref_call(G, "cheapest", args)
            T.check(f"zero/{name}", "cheapest", args, ref, run_all(rs, "cheapest", args))
    return T.dump()


# --------------------------------------------------------------------------------------------------------- main
def dispatch(job):
    kind, arg = job
    t0 = time.time()
    try:
        out = {"dev": task_dev, "random": task_random, "medium": task_medium, "limits": task_limits,
               "nx": task_nx, "zero": task_zero}[kind](arg)
    except Exception:
        out = {"calls": 0, "match": 0, "mismatches": [{"crash": traceback.format_exc()}], "notes": [], "by_fn": {}}
    out["job"], out["secs"] = [kind, str(arg)], round(time.time() - t0, 1)
    return kind, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "a1_dev.json"))
    args = ap.parse_args()
    RC.build_elf("gop"), RC.build_elf("sw")
    qs = sorted(os.path.join(DEV, d, f) for d in ("random", "cities") if os.path.isdir(os.path.join(DEV, d))
                for f in os.listdir(os.path.join(DEV, d)) if f.endswith(".questions.json"))
    gs = sorted(os.path.join(DEV, d, f) for d in ("random", "cities") if os.path.isdir(os.path.join(DEV, d))
                for f in os.listdir(os.path.join(DEV, d)) if f.endswith(".graph.json"))
    if args.quick:
        qs = qs[:6] + [q for q in qs if "cities" in q][:1]
    jobs = [("limits", None), ("zero", None)] + [("dev", q) for q in qs]
    jobs += [("random", s) for s in range(20 if args.quick else 300)]
    jobs += [("medium", s) for s in range(2 if args.quick else 16)]
    jobs += [("nx", ("file", g)) for g in (gs[:4] if args.quick else gs)]
    jobs += [("nx", ("rand", s)) for s in range(5 if args.quick else 100)] + [("nx", ("quirk", 0))]
    if args.only:
        jobs = [j for j in jobs if j[0] in args.only.split(",")]
    t0 = time.time()
    agg = {}
    with Pool(args.workers) as p:
        for done, (kind, out) in enumerate(p.imap_unordered(dispatch, jobs), 1):
            print(f"{time.strftime('%H:%M:%S')} {done}/{len(jobs)} {kind} {out['job'][1][-40:]} checks {out['calls']} "
                  f"match {out['match']} mismatches {len(out['mismatches'])} {out['secs']}s", flush=True)
            a = agg.setdefault(kind, {"jobs": 0, "calls": 0, "match": 0, "mismatches": [], "notes": [], "by_fn": {},
                                      "secs": 0})
            a["jobs"] += 1
            a["calls"] += out["calls"]
            a["match"] += out["match"]
            a["secs"] += out["secs"]
            a["mismatches"] += [dict(m, job=out["job"]) for m in out["mismatches"]]
            a["notes"] += out["notes"]
            for k, (n, ok) in out["by_fn"].items():
                c = a["by_fn"].setdefault(k, [0, 0])
                c[0] += n
                c[1] += ok
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"wall_secs": round(time.time() - t0, 1), "parts": agg}, open(args.out, "w"), indent=1,
              ensure_ascii=False)
    for kind, a in agg.items():
        print(f"{kind:7s} jobs {a['jobs']:4d}  checks {a['calls']:7d}  match {a['match']:7d}  "
              f"mismatches {len(a['mismatches'])}  notes {len(a['notes'])}  cpu {a['secs']:.0f}s")
    print("wall", round(time.time() - t0, 1), "s ->", args.out, flush=True)


if __name__ == "__main__":
    main()
