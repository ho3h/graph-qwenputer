#!/usr/bin/env python3
"""The cleaner's own checks: firmware on the reference machine against lib/reflib.py, call by call, plus the expected reading where a test knows it. Nothing reads data/heldout.

    python t8/fw/test_clean.py --part labels|awkward|fuzz|fuzzfw [--workers 4] [--seeds 40]

labels   every label of every dev graph: the name, and 4 cleaned or near-miss forms in rotation; 5 chases per graph with a cleaned start
awkward  hand-made names: really ending in the noun, internal full stops, a noun-only start, near-misses, shared names, closed nodes, all ten functions, four noun settings
fuzz     seeded random names, nouns and suffixes in random graphs, with closes, reopens and links in between
fuzzfw   fw/fuzz_fw.py's parse, legs, cheapest and spill, unchanged, through this firmware with the noun on
"""
import argparse
import copy
import glob
import json
import os
import random
import sys
import time
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwb as W  # noqa: E402

M, X, F = W.M, W.X, W.F
reflib = M.reflib
DEV = os.path.join(X.X210, "data", "dev")
OUT = os.path.join(HERE, "results", "r1") if os.environ.get("T8_R1") == "1" else os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
_init = M.init_worker
ROT = ["{} station station", "{},", "{}!?", "{} .", "{}  station", "{}\tstation", "{} Station", "Out of {}", "{}s", "{} stationx", "station {}", "{} station,.", "{}. station"]


def init():
    W.build()
    _init()
    W.O.set_text(M.T)
    W.noun_mode(True)
    W.patch_box(True)


def task_stops(_=None):
    """SPEC 3's limit lines against the old lines: every limit answer in data/dev's goldens, through reflib.reword, against the firmware on the field-bearing graph."""
    t = M.Tally("stops")
    n = 0
    for p in sorted(glob.glob(os.path.join(DEV, "*", "*.questions.json"))):
        gp = p.replace(".questions.json", ".graph.json")
        g = json.load(open(gp))
        qs = [x for x in json.load(open(p))["questions"] if not x.get("setup") and x["call"]["fn"] in ("chase", "follow") and x["answer_text"][:3] in ("leg", "END", "MUL", "NOC")][:40]
        if not qs:
            continue
        try:
            b = X.Box(g, M.T, track=True)
        except M.B.BootLimit:
            continue
        G = reflib.Graph(g)
        for x in qs:
            r = t.run(b, G, M.enc(x["call"]["fn"], x["call"]["args"]), f"{os.path.basename(p)}#{x['id']}", x["call"]["fn"])
            want = reflib.reword(x["answer_text"])
            if r is None or r.result != want or not want.startswith("Stopped early"):
                t.mism.append({"where": f"{os.path.basename(p)}#{x['id']} gold", "want": want, "got": r.result if r else None})
            n += 1
    t.notes.append({"stops": n})
    return t.dump()


def task_writes(seed):
    """chase with closed and reopened, firmware against reflib, on one persistent state: dev graphs, cleaned names, repeats, refusals."""
    rng = random.Random(40_000 + seed)
    t = M.Tally("writes")
    gs = sorted(p for p in glob.glob(os.path.join(DEV, "*", "*.graph.json")) if "heldout" not in p)
    g = json.load(open(rng.choice(gs)))
    try:
        b = X.Box(g, M.T, track=True)
    except M.B.BootLimit:
        return t.dump()
    G = reflib.Graph(g)
    N = len(g["nodes"])

    def name():
        return g["nodes"][rng.randrange(N)]["label"] + rng.choice(["", "", " station", " station.", ".", " Station", "x"])

    for i in range(120):
        kw = {"start": name(), "legs": f"{rng.choice(g['relations'])} {rng.randint(1, 3)}"}
        if rng.random() < .8:
            kw["closed"] = "; ".join(name() for _ in range(rng.choice([1, 1, 1, 2])))
        if rng.random() < .4:
            kw["reopened"] = rng.choice([name(), name() + ";" + name(), ""])
        ids = M.enc("chase", kw)
        # a call past the capture window gets TOOLONG and changes nothing on the machine; reflib must not apply its writes either
        t.run(b, copy.deepcopy(G) if X.capture_rule(ids, M.T) else G, ids, f"writes{seed}#{i} {kw!r}", "chase")
    return t.dump()


def task_r1(seed):
    """exam/R1.md: a dev graph with labels made to repeat, as the practice maps' never do. chase by a shared name against reflib: one, several or none on the first leg's relation, closures in the same call and before it."""
    rng = random.Random(50_000 + seed)
    t = M.Tally("r1")
    gs = sorted(p for p in glob.glob(os.path.join(DEV, "*", "*.graph.json")) if "heldout" not in p)
    g = json.load(open(rng.choice(gs)))
    N = len(g["nodes"])
    groups = []
    for _ in range(max(2, N // 12)):
        grp = rng.sample(range(N), rng.choice([2, 2, 3, 4, 6]))
        for h in grp[1:]:
            g["nodes"][h]["label"] = g["nodes"][grp[0]]["label"]
        groups.append(grp)
    try:
        b = X.Box(g, M.T, track=True)
    except M.B.BootLimit:
        return t.dump()
    G = reflib.Graph(g)
    at = {}
    for a, r, c, *_ in g["edges"]:
        at.setdefault(a, set()).add(r)
    for i in range(120):
        grp = rng.choice(groups)
        h = rng.choice(grp)
        rs = sorted(at.get(h, ())) or [0]
        rel = g["relations"][rng.choice(rs)] if rng.random() < .85 else rng.choice(g["relations"])
        kw = {"start": g["nodes"][h]["label"] + rng.choice(["", "", " station"]), "legs": f"{rel} {rng.randint(1, 3)}"}
        if rng.random() < .3:
            kw["legs"] += f"; {rng.choice(g['relations'])} {rng.randint(1, 2)}"
        if rng.random() < .3:
            kw["closed"] = f"@{rng.choice(grp)}"
        elif rng.random() < .3:
            kw["reopened"] = f"@{rng.choice(grp)}"
        ids = M.enc("chase", kw)
        t.run(b, copy.deepcopy(G) if X.capture_rule(ids, M.T) else G, ids, f"r1 {seed}#{i} {kw!r}", "chase")
    return t.dump()


def want_reading(t, r, where, h, label):
    if r is not None and not r.result.startswith(f"name read as @{h} {label}\n"):
        t.mism.append({"where": where, "want": f"a reading of @{h}", "got": r.result})


def want_none(t, r, where, written):
    if r is not None and r.result != f"NONE {written}":
        t.mism.append({"where": where, "want": f"NONE {written}", "got": r.result})


def task_labels(path):
    t = M.Tally("labels")
    g = json.load(open(path))
    base = os.path.basename(path)
    try:
        b = X.Box(g, M.T, track=True)
    except M.B.BootLimit as e:
        t.notes.append({"does_not_fit": base, "why": str(e), "labels": len(g["nodes"])})
        return t.dump()
    t.notes.append({"fits": base, "labels": len(g["nodes"])})
    G = reflib.Graph(g)
    transit = g.get("domain") == "transit"
    for h, n in enumerate(g["nodes"]):
        lab = n["label"]
        one = len(G.by_label[reflib.norm(lab)]) == 1
        r = t.run(b, G, M.enc("find", {"name": lab}), f"{base} {h} exact", "find")
        if one and r is not None and r.result != f"@{h} {lab}":
            t.mism.append({"where": f"{base} {h} exact", "want": f"@{h} {lab}", "got": r.result})
        r = t.run(b, G, M.enc("find", {"name": lab + "."}), f"{base} {h} stop", "find")
        if one:
            want_reading(t, r, f"{base} {h} stop", h, lab)
        s = lab + " station"
        r = t.run(b, G, M.enc("find", {"name": s}), f"{base} {h} noun", "find")
        if one and transit:
            want_reading(t, r, f"{base} {h} noun", h, lab)
        elif not transit and s not in G.by_label:
            want_none(t, r, f"{base} {h} noun", s)
        s = lab + " station."
        r = t.run(b, G, M.enc("find", {"name": s}), f"{base} {h} noun stop", "find")
        if one and transit:
            want_reading(t, r, f"{base} {h} noun stop", h, lab)
        s = ROT[h % len(ROT)].format(lab)
        t.run(b, G, M.enc("find", {"name": s}), f"{base} {h} rot {s!r}", "find")
    q = json.load(open(path.replace(".graph.json", ".questions.json")))["questions"]
    for x in [x for x in q if x.get("kind") == "chase" and not x.get("setup") and x["call"]["args"]["start"].startswith("@")][:5]:
        h = int(x["call"]["args"]["start"][1:])
        a = dict(x["call"]["args"], start=g["nodes"][h]["label"] + (" station." if transit else "."))
        t.run(b, G, M.enc("chase", a), f"{base} q{x['id']} chase", "chase")
    return t.dump()


AWK = ["Penn station", "Penn", "St. Marks Pl", "St.", "station", "Foo station station", "Foo station", "Foo", "Bar!", "Bar", "Dup", "Dup", "Dup two station", "x. y", "A,B", "Ōtaki", "Q (6 St)", "Solo", "a station b", "Near", "bus stop", "Stop bus stop", "Stop", "9"]


def task_awkward(_=None):
    t = M.Tally("awkward")
    N = len(AWK)
    edges = [(i, 0, (i + 1) % N, 1) for i in range(N)] + [(i, 1, (i + 3) % N, 2) for i in range(0, N, 2)]
    args = ["Penn station", "Penn station.", "Penn", "Penn.", "Penn. station", "Penn  station", "Penn\tstation", "Penn station ", "Penn　station", "Penn station.", "Penn Station", "St. Marks Pl", "St. Marks Pl.", "St. Marks Pl station", "St. Marks", "St.", "St", "St station", "St. station",
            "station", "station.", "station station", " station", ".", "..", "?!", " . ", "Foo station station", "Foo station station.", "Foo station station station", "Foo station", "Foo.", "Bar!", "Bar!!", "Bar", "Bar?", "Bar! station", "Dup", "Dup.", "Dup station", "Dup two", "Dup two station", "x. y", "x. y.", "x.", "A,B", "A,B,", "A", "Ōtaki", "Ōtaki station.", "Ōtaki.",
            "Q (6 St)", "Q (6 St).", "Q (6 St", "Solo", "Solo;", "Solo:", "Solo:;", "Solo station", "Solo station;", "Solo,station", "Solo-station", "solo", "SOLO station", "The Solo", "Out of Solo", "Solo St", "Sol", "a station b", "a station", "Near", "Nears", "Nea", "bus stop", "Stop bus stop", "Stop bus stop.", "Stop", "Stop stop", "9", "9.", "9 station", "@0", "@0.", "@0 Penn station", "@0 Penn station.", "@1 Penn.", "@1 Penn", "@99.", "@99 station", "@", "@ station"]
    for noun in ("station", "bus stop", None, "ABSENT", "stop", "St."):
        g = M.g_of(N, edges, rels=("r", "s"), change="s", labels=AWK)
        if noun != "ABSENT":
            g = dict(g, noun=noun)
        else:
            g.pop("noun", None)
        b = X.Box.__new__(X.Box)                            # the field exactly as set here, on both sides: patch_box's rule must not add one
        W._box_init(b, g, M.T, track=True)
        b.head, b.tail = W.HEAD, W.TAIL
        G = W._Graph(g)
        if noun == "ABSENT":                                 # the firmware always prints SPEC 3's words; reflib on a file with no field keeps the old lines
            G.call = lambda fn, kw, _c=G.call: reflib.reword(_c(fn, kw))
        for a in args:
            w = f"{noun} {a!r}"
            t.run(b, G, M.enc("find", {"name": a}), f"find {w}", "find")
            t.run(b, G, M.enc("find", {"name": a, "has": "s"}), f"find has {w}", "find")
            t.run(b, G, M.enc("chase", {"start": a, "legs": "r 2; s 1"}), f"chase {w}", "chase")
            t.run(b, G, M.enc("chase", {"start": a, "legs": "nope 2"}), f"chase badrel {w}", "chase")
            t.run(b, G, M.enc("follow", {"node": a, "relation": "r", "steps": "3"}), f"follow {w}", "follow")
            t.run(b, G, M.enc("neighbours", {"node": a, "relation": "r", "direction": "in"}), f"neighbours {w}", "neighbours")
            t.run(b, G, M.enc("path", {"from": a, "to": "Solo station."}), f"path {w}", "path")
            t.run(b, G, M.enc("cheapest", {"from": "Near.", "to": a}), f"cheapest {w}", "cheapest")
        rng = random.Random(1)
        for i in range(120):                                # writes through cleaned names, in one persistent state
            a, c = rng.choice(args), rng.choice(args)
            fn, kw = rng.choice([("close", {"node": a}), ("reopen", {"node": a}), ("reopen", {"node": a}), ("link", {"from": a, "relation": "s", "to": c, "weight": "3"}), ("unlink", {"from": a, "relation": "r", "to": c}), ("find", {"name": a}), ("path", {"from": a, "to": c})])
            t.run(b, G, M.enc(fn, kw), f"writes {noun} {i} {fn} {kw}", fn)
    # known readings, by hand, under noun = station
    g = dict(M.g_of(N, edges, rels=("r", "s"), change="s", labels=AWK), noun="station")
    G = W._Graph(g)
    lab = {x: i for i, x in enumerate(AWK)}
    hand = {"Penn station": f"@{lab['Penn station']} Penn station", "Penn station.": f"name read as @{lab['Penn station']} Penn station\n@{lab['Penn station']} Penn station", "Penn.": f"name read as @{lab['Penn']} Penn\n@{lab['Penn']} Penn",
            "Foo station station": f"@{lab['Foo station station']} Foo station station", "Foo station station station": f"name read as @{lab['Foo station station']} Foo station station\n@{lab['Foo station station']} Foo station station",
            "St. Marks Pl.": f"name read as @{lab['St. Marks Pl']} St. Marks Pl\n@{lab['St. Marks Pl']} St. Marks Pl", "St. station": "NONE St. station", "St": "NONE St",
            "station": f"@{lab['station']} station", "station.": f"name read as @{lab['station']} station\n@{lab['station']} station", "Dup.": "NONE Dup.", "Dup station": "NONE Dup station", "Penn Station": "NONE Penn Station", "Out of Solo": "NONE Out of Solo", "Solo St": "NONE Solo St", ".": "NONE .", "@1 Penn.": "NONE @1 Penn.", "@99.": "NONE @99."}
    b = X.Box(g, M.T, track=True)
    for a, want in hand.items():
        got = G.call("find", {"name": a})
        r = t.run(b, G, M.enc("find", {"name": a}), f"hand {a!r}", "find")
        if got != want:
            t.mism.append({"where": f"hand reflib {a!r}", "want": want, "got": got})
        if r is not None and r.result != want:
            t.mism.append({"where": f"hand firmware {a!r}", "want": want, "got": r.result})
    return t.dump()


WORDS = ["Oak", "Elm", "St", "St.", "Av", "station", "Station", "stop", "bus", "x.", ",y", "!", "Ō", "é", "1", "22", "(6", "St)", "a-b", "c/d", "North"]
TAILS = ["", "", ".", ",", ";", ":", "!", "?", "..", " .", ". ", "!?", " station", " station.", " stop", " bus stop", "  station", "\tstation", " Station", " stationx", " station", "　.", " ", " st", "\n", ".\n"]
HEADS = ["", "", "", "", " ", "The ", "Out of ", "station ", "."]


def task_fuzz(seed):
    rng = random.Random(30_000 + seed)
    t = M.Tally("fuzz")
    n = rng.randint(4, 40)
    labels = [" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 3))) for _ in range(n)]
    labels = [lab if rng.random() > .1 else lab + rng.choice([" station", ".", " stop", "!"]) for lab in labels]
    edges = {}
    for _ in range(3 * n):
        edges[(rng.randrange(n), rng.randrange(2), rng.randrange(n))] = rng.randint(0, 9)
    g = M.g_of(n, [(a, r, b_, w) for (a, r, b_), w in edges.items()], rels=("r", "s t"), splice=rng.sample(["r", "s t"], rng.randint(0, 1)), change=rng.choice(["r", "s t", None]), labels=labels)
    g["noun"] = rng.choice(["station", "station", "stop", "bus stop", "St.", None, "x"])
    b, G = X.Box(g, M.T, track=True), W._Graph(g)

    def name():
        return rng.choice(HEADS) + rng.choice(labels) + rng.choice(TAILS)

    for i in range(300):
        fn, kw = rng.choice([("find", {"name": name()}), ("find", {"name": name()}), ("find", {"name": name(), "has": "r"}), ("chase", {"start": name(), "legs": "r 1; s t 1"}), ("chase", {"start": name(), "legs": "r 2"}),
                             ("follow", {"node": name(), "relation": "r", "steps": "2"}), ("neighbours", {"node": name(), "relation": "s t"}), ("path", {"from": name(), "to": name()}), ("cheapest", {"from": name(), "to": name()}),
                             ("close", {"node": name()}), ("reopen", {"node": name()}), ("reopen", {"node": name()}), ("link", {"from": name(), "relation": "r", "to": name()}), ("unlink", {"from": name(), "relation": "r", "to": name()})])
        ids = M.enc(fn, kw)
        if 188 in ids:
            continue
        t.run(b, G, ids, f"fuzz{seed}#{i} noun={g['noun']!r} {fn} {kw!r}", fn)
    return t.dump()


def fzp(j):
    import fuzz_fw as FZ
    return M.call_job((getattr(FZ, j[0]), j[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["labels", "awkward", "fuzz", "fuzzfw", "stops", "writes", "r1"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=40)
    a = ap.parse_args()
    W.build()
    if a.part == "labels":
        fn, jobs = task_labels, sorted(p for p in glob.glob(os.path.join(DEV, "*", "*.graph.json")) if "heldout" not in p)
    elif a.part == "awkward":
        fn, jobs = task_awkward, [None]
    elif a.part == "writes":
        fn, jobs = task_writes, list(range(a.seeds))
    elif a.part == "r1":
        fn, jobs = task_r1, list(range(a.seeds))
    elif a.part == "stops":
        fn, jobs = task_stops, [None]
    elif a.part == "fuzz":
        fn, jobs = task_fuzz, list(range(a.seeds))
    t0 = time.time()
    tot, mism, notes, stats = {}, [], [], {"labels_fit": 0, "labels_not_fit": 0}
    with get_context("spawn").Pool(a.workers, initializer=init, maxtasksperchild=40) as pool:
        if a.part == "fuzzfw":
            work = [("task_parse", s) for s in range(a.seeds)] + [("task_legs", s) for s in range(a.seeds)] + [("task_cheapest", s) for s in range(a.seeds)] + [("task_spill", None)]
            it = pool.imap_unordered(fzp, work)
            total = len(work)
        else:
            it = pool.imap_unordered(M.call_job, [(fn, j) for j in jobs])
            total = len(jobs)
        for i, r in enumerate(it):
            p = tot.setdefault(r["part"], {"checks": 0, "match": 0, "toolong": 0, "mismatches": 0})
            for k, v in (("checks", r["checks"]), ("match", r["match"]), ("toolong", r["toolong"]), ("mismatches", r["n_mismatches"])):
                p[k] += v
            mism += r["mismatches"]
            notes += r.get("notes", [])
            if (i + 1) % 10 == 0 or i + 1 == total:
                print(f"{time.time() - t0:.0f}s {i + 1}/{total} {json.dumps(tot)}", flush=True)
                json.dump({"part": a.part, "done": i + 1, "of": total, "parts": tot, "mismatches": mism[:200]}, open(os.path.join(OUT, f"{'writes' if W.WRITES else 'clean'}_{a.part}.partial.json"), "w"), ensure_ascii=False)
    out = {"part": a.part, "seconds": round(time.time() - t0, 1), "parts": tot, "mismatches_n": len(mism), "mismatches": mism[:200], "not_fit": [n for n in notes if "does_not_fit" in n], "fit_graphs": sum("fits" in n for n in notes), "labels": sum(n.get("labels", 0) for n in notes if "fits" in n)}
    json.dump(out, open(os.path.join(OUT, f"{'writes' if W.WRITES else 'clean'}_{a.part}.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != "mismatches"}, ensure_ascii=False)[:1200], "first:", json.dumps(mism[:3], ensure_ascii=False)[:1500])
    sys.exit(1 if mism else 0)


if __name__ == "__main__":
    main()
