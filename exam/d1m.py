#!/usr/bin/env python3
"""D1m, New York only: 200 two-leg chases from the file, seed 20261103. Qwen writes one chase call; the machine prints the line. Frozen flow print-writes on writes.elf, standard runner, stock sample of 4 whole questions.

    python exam/d1m.py --name nyc --out exam/results/nyc_d1m --deadline-s S
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)


def base_of(name):
    if name in ("nyc-cf", "nyc-relabelled"):                       # exam/AFTER.md, the sealed maps
        return os.path.join(X210, "data", "heldout", name, name)
    if name == "nyc":
        assert os.path.exists(os.path.join(HERE, "FROZEN")), "New York opens only after the freeze commit"
        return os.path.join(X210, "data", "heldout", "nyc", "nyc")
    return os.path.join(X210, "data", "dev", "cities", name)


def generate(name, g, Q, rng, need):
    """More two-leg chases in the file's own wording, seeded: a start with a unique label, one route and direction, another line at the stop reached or one change away. Gold from reflib on the noun-bearing graph, as every line is. No model sees this before the run."""
    sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
    import noun as N
    import reflib
    ng = N.with_noun(g)
    G = reflib.Graph(ng)
    names = g["relations"]
    ch = names.index(g["change"]) if g.get("change") else None
    routes = [i for i, r in enumerate(names) if i != ch and re.fullmatch(r"\S+ (northbound|southbound)", r)]
    at = {}
    for a, r, b, w in g["edges"]:
        at.setdefault(a, {}).setdefault(r, []).append(b)
    uniq = [i for i, n in enumerate(g["nodes"]) if len(G.by_label[n["label"]]) == 1 and any(r in routes for r in at.get(i, {}))]
    uniq.sort()
    seen = {(q["call"]["args"]["start"], q["call"]["args"]["legs"]) for q in Q if q.get("kind") == "chase"}
    out, tries = [], 0
    while len(out) < need and tries < 500000:
        tries += 1
        s = rng.choice(uniq)
        r1 = rng.choice([r for r in at[s] if r in routes])
        k1 = rng.randint(1, 4)
        h, ok = s, True
        for _ in range(k1):
            nx = at.get(h, {}).get(r1, [])
            if len(nx) != 1:
                ok = False
                break
            h = nx[0]
        if not ok:
            continue
        rs = {r for r in at.get(h, {}) if r in routes and names[r].split()[0] != names[r1].split()[0]}     # another line at this node, or one change away (SPEC 3)
        if ch is not None:
            for y in at.get(h, {}).get(ch, []):
                rs |= {r for r in at.get(y, {}) if r in routes and names[r].split()[0] != names[r1].split()[0]}
        if not rs:
            continue
        r2 = rng.choice(sorted(rs))
        k2 = rng.randint(1, 4)
        a1, d1 = names[r1].split()
        a2, d2 = names[r2].split()
        args = {"start": f"@{s}", "legs": f"{names[r1]} {k1}; {names[r2]} {k2}"}
        if (args["start"], args["legs"]) in seen:
            continue
        seen.add((args["start"], args["legs"]))
        pl = lambda k: "stop" if k == 1 else "stops"
        text = f"Start at {g['nodes'][s]['label']} station. Ride the {a1} train {k1} {pl(k1)} {d1}, then change to the {a2} and ride the {a2} train {k2} {pl(k2)} {d2}. One stop means the next station. At which station are you now? Answer with the station name only."
        line = G.chase(args["start"], args["legs"])
        m = re.match(r"@(\d+) ", line)
        out.append({"id": 900000 + len(out), "kind": "chase", "text": text, "call": {"fn": "chase", "args": args}, "answer": [int(m.group(1))] if m else [], "answer_text": line, "generated": True})
    return out


def generate_shared(name, g, Q, rng, need):
    """exam/R1.md: the same wording, but the start's name is shared, and exactly one node with it has the first leg's relation. Handle-based gold from reflib, as `generate`. Questions this model hasn't seen; the rule was chosen after seeing New York."""
    sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
    import noun as N
    import reflib
    G = reflib.Graph(N.with_noun(g))
    names = g["relations"]
    ch = names.index(g["change"]) if g.get("change") else None
    routes = [i for i, r in enumerate(names) if i != ch and re.fullmatch(r"\S+ (northbound|southbound)", r)]
    at = {}
    for a, r, b, w in g["edges"]:
        at.setdefault(a, {}).setdefault(r, []).append(b)
    pool = sorted(i for i, n in enumerate(g["nodes"]) if len(G.by_label[n["label"]]) > 1 and any(r in routes for r in at.get(i, {})))
    seen = {(q["text"]) for q in Q}
    out, tries = [], 0
    while len(out) < need and tries < 500000:
        tries += 1
        s = rng.choice(pool)
        r1 = rng.choice([r for r in at[s] if r in routes])
        if sum(r1 in at.get(x, {}) for x in G.by_label[g["nodes"][s]["label"]]) != 1:
            continue
        k1 = rng.randint(1, 4)
        h, ok = s, True
        for _ in range(k1):
            nx = at.get(h, {}).get(r1, [])
            if len(nx) != 1:
                ok = False
                break
            h = nx[0]
        if not ok:
            continue
        rs = {r for r in at.get(h, {}) if r in routes and names[r].split()[0] != names[r1].split()[0]}
        if ch is not None:
            for y in at.get(h, {}).get(ch, []):
                rs |= {r for r in at.get(y, {}) if r in routes and names[r].split()[0] != names[r1].split()[0]}
        if not rs:
            continue
        r2 = rng.choice(sorted(rs))
        k2 = rng.randint(1, 4)
        a1, d1 = names[r1].split()
        a2, d2 = names[r2].split()
        pl = lambda k: "stop" if k == 1 else "stops"
        text = f"Start at {g['nodes'][s]['label']} station. Ride the {a1} train {k1} {pl(k1)} {d1}, then change to the {a2} and ride the {a2} train {k2} {pl(k2)} {d2}. One stop means the next station. At which station are you now? Answer with the station name only."
        if text in seen:
            continue
        seen.add(text)
        args = {"start": f"@{s}", "legs": f"{names[r1]} {k1}; {names[r2]} {k2}"}
        line = G.chase(args["start"], args["legs"])
        m = re.match(r"@(\d+) ", line)
        out.append({"id": 910000 + len(out), "kind": "chase", "text": text, "call": {"fn": "chase", "args": args}, "answer": [int(m.group(1))] if m else [], "answer_text": line, "generated": True, "shared_start": True})
    return out


def draw(name, n=200):
    """The file's two-leg chases, all of them up to n, then seeded generated ones in the same wording to make n."""
    Q = json.load(open(base_of(name) + ".questions.json"))["questions"]
    g = json.load(open(base_of(name) + ".graph.json"))
    two = [q for q in Q if q.get("kind") == "chase" and not q.get("setup") and q["call"]["args"]["legs"].count(";") == 1]
    two.sort(key=lambda q: q["id"])
    rng = random.Random(f"20261103:{name}:d1m")
    take = rng.sample(two, min(n, len(two)))
    if len(take) < n:
        take += generate(name, g, Q, rng, n - len(take))
    assert len(take) == n, (len(take), n)
    if os.environ.get("T8_R1") == "1":
        take += generate_shared(name, g, Q + take, random.Random(f"20261103:{name}:r1"), 100)
        assert len(take) == n + 100
    return take, len(two)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--stock", type=int, default=4)
    ap.add_argument("--stock-limit-s", type=float, default=3000)
    ap.add_argument("--flow", default="print-writes", choices=["print-writes", "read-writes"])
    ap.add_argument("--deadline-s", type=float, required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(X210, "speed"))
    import fast  # noqa: E402
    if a.name == "nyc":
        sc = json.load(open(os.path.join(HERE, "results", "nyc_r1_score.json" if os.environ.get("T8_R1") == "1" else "nyc_score.json")))
        assert sc["D2m_pass"] and sc["D4m_pass"], "the machine exams come first"
    fast.setup("writes")
    qs, pool = draw(a.name, a.n)
    gr = json.load(open(base_of(a.name) + ".graph.json"))
    its = [(gr, q, (a.name, q["id"])) for q in qs]
    fl = fast.flow(a.flow)
    assert fast.proof(fl), "the frozen flow has its proof"
    m = fast.run(its, fl, a.out, rows=8, stock=a.stock, stock_seed=20261103, stock_limit_s=a.stock_limit_s, deadline_s=a.deadline_s)
    print({k: m.get(k) for k in ("path", "ran_on", "firmware_sha256", "flow_key", "bad", "tokens")}, "pool", pool, flush=True)
