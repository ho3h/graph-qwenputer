"""Held-out set 4: counterfactual NYC (nyc-cf) and relabelled NYC (nyc-relabelled), from xseries/X2.7/graph.json.

    build_nyc_variants.py

Both are built in X2.7's station format first (kept as <name>.x27.json), then converted exactly like NYC
(common.transit_graph). Chases come from X2.7's own generator (xseries/X2.7/x27_chases.py, imported read-only), so
they have NYC's shapes: 25 one-leg chases for each k in 1-4, 100 two-leg chases, and the 200 leg splits. Answers come
from reflib and are checked against the generator's own answers.

Counterfactual rules (numpy default_rng(2710), applied in this order; the resolved choices go to nyc-cf.rules.json):
  0. Eligible routes: at least 10 stations, not an express variant (6X, 7X, FX), northbound links one simple path and
     southbound exactly its reverse.
  1. Remove 2 routes: rng.choice(eligible, 2, replace=False); all their links are deleted.
  2. Reroute 3 routes: take the routes of rng.permutation(eligible minus removed) in order and reroute the first 3
     that admit a detour (a route with none after 1,000 draws is skipped and recorded). For a route R with
     northbound chain c: draw i = rng.integers(0, len(c) - 2) and span = rng.integers(2, 7), j = min(i + span,
     len(c) - 1); keep the draw if j - i >= 2 and a detour exists: the shortest path from c[i] to c[j] in the
     undirected track graph of all other current routes' links, minus the links joining consecutive stations of
     c[i..j] and avoiding R's stations outside c[i..j], with at least 2 links and at most 12 (BFS, neighbours in ascending station id). Up to 1,000 draws. R's chain becomes
     c[:i] + detour + c[j+1:] northbound and its reverse southbound; new links get share 1.0.
  3. Swap 20 station pairs: rng.choice over stations that are still served by a route and are alone in their
     complex (sorted ids), 40 without replacement, paired in draw order (1st with 2nd, ...). Each pair exchanges
     positions: every link at one station's position now attaches to the other station. Names stay real.
  Stations left unserved stay in the graph as nodes without route links. Chase seed 2710.

Relabelled rules (numpy default_rng(2711)): every distinct station name maps to a distinct invented name (a
bijection on names, so stations that shared a name still share one), never a name in NYC or the synthetic cities;
station ids become x000-x495 in a random order, complex ids follow their stations. Links are unchanged, so the
graph is isomorphic to NYC; nyc-relabelled.mapping.json holds the bijection and the builder checks it. Chase seed 2711.
"""
import collections
import importlib
import json
import os
import sys
import tempfile

import numpy as np

from common import DATA, REPO, reflib, sha256_file, transit_graph, transit_questions, questions_file, write

X27 = os.path.join(REPO, "xseries", "X2.7")
sys.path.insert(0, X27)
x27_chases = importlib.import_module("x27_chases")
OUT = os.path.join(DATA, "heldout")
NO_Q = {"6X", "7X", "FX"}


def chains(edges):
    by = collections.defaultdict(dict)
    for e in edges:
        by[(e["route"], e["dir"])][e["from"]] = e["to"]
    return by


def simple_chain(succ):
    heads = sorted(set(succ) - set(succ.values()))
    if len(heads) != 1 or max(collections.Counter(succ.values()).values()) > 1:
        return None
    c = heads
    while c[-1] in succ:
        c.append(succ[c[-1]])
    return c


def bfs(adj, a, b, avoid):
    prev, level = {a: None}, [a]
    while level and b not in prev:
        nxt = []
        for x in level:
            for y in sorted(adj.get(x, ())):
                if y not in prev and y not in avoid:
                    prev[y] = x
                    nxt.append(y)
        level = nxt
    if b not in prev:
        return None
    p = [b]
    while prev[p[-1]] is not None:
        p.append(prev[p[-1]])
    return p[::-1]


def counterfactual(src):
    rng = np.random.default_rng(2710)
    S = src["stations"]
    edges = [dict(e) for e in src["edges"]]
    by = chains(edges)
    routes = sorted({e["route"] for e in edges})
    eligible = []
    for r in routes:
        c = simple_chain(by[(r, "N")])
        if (r not in NO_Q and c and len(c) >= 10
                and {b: a for a, b in by[(r, "N")].items()} == by[(r, "S")]):
            eligible.append(r)
    removed = [str(x) for x in rng.choice(eligible, 2, replace=False)]
    edges = [e for e in edges if e["route"] not in removed]
    rest = [r for r in eligible if r not in removed]
    order = [str(x) for x in rng.permutation(rest)]
    rerouted, no_detour = [], []
    for r in order:
        if len(rerouted) == 3:
            break
        c = simple_chain(chains(edges)[(r, "N")])
        adj = collections.defaultdict(set)
        for e in edges:
            if e["route"] != r:
                adj[e["from"]].add(e["to"])
                adj[e["to"]].add(e["from"])
        for draw in range(1000):
            i = int(rng.integers(0, len(c) - 2))
            j = min(i + int(rng.integers(2, 7)), len(c) - 1)
            if j - i < 2:
                continue
            seg = {frozenset(x) for x in zip(c[i:j], c[i + 1:j + 1])}
            sub = {x: {y for y in ys if frozenset((x, y)) not in seg} for x, ys in adj.items()}
            p = bfs(sub, c[i], c[j], set(c[:i]) | set(c[j + 1:]))
            if p and 2 <= len(p) - 1 <= 12 and p != c[i:j + 1]:
                break
        else:
            no_detour.append(r)
            continue
        new = c[:i] + p + c[j + 1:]
        assert len(set(new)) == len(new)
        edges = [e for e in edges if e["route"] != r]
        for a, b in zip(new, new[1:]):
            edges.append({"from": a, "route": r, "dir": "N", "to": b, "share": 1.0, "trips": 0})
            edges.append({"from": b, "route": r, "dir": "S", "to": a, "share": 1.0, "trips": 0})
        rerouted.append({"route": r, "draws": draw + 1, "from": c[i], "to": c[j],
                         "old_segment": c[i:j + 1], "new_segment": p,
                         "old_names": [S[x]["name"] for x in c[i:j + 1]], "new_names": [S[x]["name"] for x in p]})
    served = sorted({e["from"] for e in edges} | {e["to"] for e in edges})
    size = collections.Counter(v["complex"] for v in S.values())
    cand = [s for s in served if size[S[s]["complex"]] == 1]
    pick = [str(x) for x in rng.choice(cand, 40, replace=False)]
    pairs = [(pick[k], pick[k + 1]) for k in range(0, 40, 2)]
    pi = {}
    for a, b in pairs:
        pi[a], pi[b] = b, a
    edges = [{**e, "from": pi.get(e["from"], e["from"]), "to": pi.get(e["to"], e["to"])} for e in edges]
    edges.sort(key=lambda e: (e["from"], e["route"], e["dir"]))
    stations = {s: {"name": v["name"], "complex": v["complex"]} for s, v in S.items()}
    rules = {"seed": 2710, "eligible": eligible, "removed": removed, "reroute_order": order,
             "no_detour": no_detour, "rerouted": rerouted,
             "swapped": [{"a": a, "b": b, "a_name": S[a]["name"], "b_name": S[b]["name"]} for a, b in pairs],
             "unserved_after": sorted(set(S) - {e["from"] for e in edges} - {e["to"] for e in edges})}
    return {"stations": stations, "edges": edges}, rules


C, V = "bdfgklmnprstvz", "aeiou"
SUF = ["St", "Av", "Sq", "Rd", "Pkwy", "Blvd", "Pl", "Park", "Hts", "Junction"]


def invented(rng):
    w = lambda: "".join(C[rng.integers(len(C))] + V[rng.integers(len(V))] + ["", "n", "r", "l"][rng.integers(4)]
                        for _ in range(int(rng.integers(2, 4)))).capitalize()
    n = f"{w()} {SUF[rng.integers(len(SUF))]}"
    if rng.random() < 0.3:
        n = f"{w()}-{n}"
    return n


def relabelled(src, forbidden):
    rng = np.random.default_rng(2711)
    S = src["stations"]
    old_names = sorted({v["name"] for v in S.values()})
    fresh, used = {}, set(forbidden)
    for nm in old_names:
        while True:
            x = invented(rng)
            if x not in used:
                break
        used.add(x)
        fresh[nm] = x
    ids = sorted(S)
    perm = rng.permutation(len(ids))
    new_id = {s: f"x{int(perm[k]):03d}" for k, s in enumerate(ids)}
    stations = {new_id[s]: {"name": fresh[S[s]["name"]], "complex": new_id[S[s]["complex"]]
                            if S[s]["complex"] in new_id else S[s]["complex"]} for s in ids}
    edges = [{**e, "from": new_id[e["from"]], "to": new_id[e["to"]]} for e in src["edges"]]
    edges = [{k: e[k] for k in ("from", "route", "dir", "to", "share", "trips")} for e in edges]
    edges.sort(key=lambda e: (e["from"], e["route"], e["dir"]))
    mapping = {"seed": 2711, "station": {new_id[s]: s for s in ids}, "name": {fresh[n]: n for n in old_names}}
    return {"stations": dict(sorted(stations.items())), "edges": edges}, mapping


def chases(x27_path, seed):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "chases.json")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as log:
            x27_chases.main(type("A", (), {"graph": x27_path, "out": out, "seed": seed})())
        return json.load(open(out)), log.getvalue().strip()


def build(name, src, seed, extra_name, extra):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    x27_path = os.path.join(d, f"{name}.x27.json")
    with open(x27_path, "w") as f:
        json.dump(src, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(d, extra_name), "w") as f:
        json.dump(extra, f, indent=1, ensure_ascii=False)
        f.write("\n")
    ch, log = chases(x27_path, seed)
    meta = {"source": f"data/heldout/{name}/{name}.x27.json (from xseries/X2.7/graph.json)",
            "source_sha256": sha256_file(x27_path), "rules": f"data/heldout/{name}/{extra_name}",
            "chase_seed": seed, "chase_generator": "xseries/X2.7/x27_chases.py",
            "weights": "route edges 1 (one stop); transfer 0"}
    g, hmap = transit_graph(src, name, meta)
    gsha = write(os.path.join(d, f"{name}.graph.json"), g)
    G = reflib.Graph(g)
    qs, bad = transit_questions(G, ch["questions"], hmap)
    write(os.path.join(d, f"{name}.questions.json"), questions_file(name, gsha, qs))
    with open(os.path.join(d, "mismatches.json"), "w") as f:
        json.dump(bad, f, indent=1, ensure_ascii=False)
        f.write("\n")
    kinds = collections.Counter(q["orig_kind"] for q in qs)
    print(name, "nodes", len(g["nodes"]), "edges", len(g["edges"]), "relations", len(g["relations"]),
          "questions", len(qs), dict(kinds), "generator:", log, "| mismatches", len(bad))
    return g, hmap


if __name__ == "__main__":
    nyc = json.load(open(os.path.join(X27, "graph.json")))
    cf, rules = counterfactual(nyc)
    rules["source_sha256"] = sha256_file(os.path.join(X27, "graph.json"))
    build("nyc-cf", cf, 2710, "nyc-cf.rules.json", rules)
    print(" removed", rules["removed"], "rerouted", [(r["route"], r["old_names"], r["new_names"])
                                                    for r in rules["rerouted"]])
    forbidden = {v["name"] for v in nyc["stations"].values()}
    cities = os.path.join(DATA, "dev", "cities")
    for f in sorted(os.listdir(cities)):
        if f.endswith(".graph.json"):
            forbidden |= {n["label"] for n in json.load(open(os.path.join(cities, f)))["nodes"]}
    rl, mapping = relabelled(nyc, forbidden)
    mapping["source_sha256"] = rules["source_sha256"]
    g_rl, _ = build("nyc-relabelled", rl, 2711, "nyc-relabelled.mapping.json", mapping)
    # isomorphism check: map the relabelled x210 graph back through the bijection and compare with real NYC's
    g_nyc = json.load(open(os.path.join(OUT, "nyc", "nyc.graph.json")))
    assert g_rl["relations"] == g_nyc["relations"]
    back = {h: mapping["station"][n["src"]] for h, n in enumerate(g_rl["nodes"])}
    nyc_h = {n["src"]: h for h, n in enumerate(g_nyc["nodes"])}
    rl_e = sorted([nyc_h[back[a]], r, nyc_h[back[b]], w] for a, r, b, w in g_rl["edges"])
    assert rl_e == g_nyc["edges"], "relabelled graph is not isomorphic to NYC"
    assert all(mapping["name"][g_rl["nodes"][h]["label"]] == g_nyc["nodes"][nyc_h[back[h]]]["label"]
               for h in range(len(g_rl["nodes"])))
    print("relabelled: isomorphism to nyc.graph.json verified (edges, relations, name bijection)")
