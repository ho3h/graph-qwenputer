#!/usr/bin/env python3
"""The machine exams' items, deterministic, seed 20261103. D2m: 20 closures x 600 chases (the file's chases, up to 400, then generated). D4m: 500 ordered pairs, path by handles. Every expected line three ways: reflib, edits2's oracle reworded, and for path networkx and d/dlib's BFS; any disagreement stops the build. New York is read only after exam/FROZEN exists.

    T8_WRITES=1 python t8/fw/tokrun.py ../exam/items.py --name c024 --n-file 400 --out exam/items/c024.json
"""
import argparse
import glob
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
for p in ("d", "edits2", "rvc"):
    sys.path.append(os.path.join(X210, p))
sys.path.insert(0, os.path.join(X210, "t8", "fw"))
import noun as N  # noqa: E402
import box as X  # noqa: E402
X.MODEL = os.path.expanduser("~/Models/x210/Qwen3.5-4B")
import reflib  # noqa: E402
import dlib  # noqa: E402
import oracle as O  # noqa: E402
import tools as HT  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

SEED = 20261103
USER = "Answer with the graph tools."


def load(name):
    if name == "nyc":
        assert os.path.exists(os.path.join(HERE, "FROZEN")), "New York opens only after the freeze commit"
        base = os.path.join(X210, "data", "heldout", "nyc", "nyc")
    else:
        assert "heldout" not in name
        base = os.path.join(X210, "data", "dev", "cities" if name[0] == "c" else "random", name)
    return base + ".graph.json", base + ".questions.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--n-file", type=int, default=400)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gp, qp = load(a.name)
    raw = json.load(open(gp))
    g = N.with_noun(raw)
    Q = json.load(open(qp))["questions"]
    T = BR.Text(X.tokenizer_json())
    hf = AutoTokenizer.from_pretrained(X.MODEL)
    G = reflib.Graph(g)
    net = O.Net(g)
    base = net.state()
    rng = random.Random(f"{SEED}:{a.name}")
    # checks on the file: its golds, reworded, against reflib on the noun-bearing graph
    gold_bad = []
    for q in Q:
        if q.get("setup"):
            continue
        got = G.call(q["call"]["fn"], q["call"]["args"])
        if got != reflib.reword(q["answer_text"]):
            gold_bad.append([q["id"], q["answer_text"], got])
    chases = [q["call"]["args"] for q in Q if q.get("kind") == "chase" and not q.get("setup") and not X.capture_rule(T.encode(X.template_text("chase", q["call"]["args"])), T)][: a.n_file]
    file_n = len(chases)
    file_dropped = sum(q.get("kind") == "chase" and not q.get("setup") for q in Q) - file_n
    seen = {(c["start"], c["legs"]) for c in chases}
    names = g["relations"]
    ch = net.change
    rels = [r for r in range(len(names)) if r != ch]
    on = {r: sorted({e[0] for e in g["edges"] if e[1] == r}) for r in rels}
    rels = [r for r in rels if on[r]]
    guard = 0
    while len(chases) < 600 and guard < 200000:
        guard += 1
        r = rng.choice(rels)
        h = rng.choice(on[r])
        legs = []
        at = h
        for _ in range(rng.choice((2, 2, 3, 4))):
            k = rng.randint(1, 3)
            legs.append(f"{names[r]} {k}")
            vis = []
            base.chase(f"@{at}", f"{names[r]} {k}", visits=vis)
            at = vis[-1] if vis else at
            nxt = sorted({e[1] for e in g["edges"] if e[0] == at and e[1] in rels and e[1] != r})
            if nxt:
                r = rng.choice(nxt)
        c = {"start": f"@{h}", "legs": "; ".join(legs)}
        if (c["start"], c["legs"]) in seen or X.capture_rule(T.encode(X.template_text("chase", c)), T):
            continue
        seen.add((c["start"], c["legs"]))
        chases.append(c)
    assert len(chases) == 600, len(chases)
    # closures: the ten nodes most stepped on by the 600, ties by handle; ten more by seed
    visits = {}
    for c in chases:
        v = []
        base.chase(c["start"], c["legs"], visits=v)
        for h in set(v):
            visits[h] = visits.get(h, 0) + 1
    hubs = [h for h, _ in sorted(visits.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    pool = [h for h in range(len(g["nodes"])) if h not in hubs and h in visits]
    pool2 = [h for h in range(len(g["nodes"])) if h not in hubs and h not in visits]
    others = rng.sample(pool, min(7, len(pool))) + rng.sample(pool2, min(3, len(pool2)))
    others += rng.sample([h for h in pool if h not in others], 10 - len(others)) if len(others) < 10 else []
    closures = hubs + others
    assert len(set(closures)) == 20
    disagree = []

    def want(fn, args, closed=()):
        Gx = reflib.Graph(g)
        for h in closed:
            Gx.close(f"@{h}")
        got = Gx.call(fn, args)
        o = reflib.reword(net.state(closed).call({"fn": fn, "args": args}))
        if got != o:
            disagree.append([fn, args, list(closed), got, o])
        return got

    qs = [{"args": c, "ids": T.encode(X.template_text("chase", c)), "base": want("chase", c)} for c in chases]
    units = []
    for k, h in enumerate(closures):
        units.append({"unit": f"close{k:02d}", "node": h, "why": "most stepped on" if h in hubs else "by seed", "close_ids": T.encode(X.template_text("close", {"node": f"@{h}"})), "reopen_ids": T.encode(X.template_text("reopen", {"node": f"@{h}"})),
                      "closed_want": [want("chase", c, (h,)) for c in chases], "close_want": f"closed @{h} {g['nodes'][h]['label']}", "reopen_want": f"reopened @{h} {g['nodes'][h]['label']}"})
    n = len(g["nodes"])
    picks = rng.sample(range(n * n), min(500, n * n))
    adj = dlib.adjacency(g)
    pairs = []
    for x in picks:
        s, t = x // n, x % n
        args = {"from": f"@{s}", "to": f"@{t}"}
        w = want("path", args)
        nxp = base.nx_path(f"@{s}", f"@{t}")
        cb = dlib.canon_path(g, s, t, adj)
        if not (w == cb):
            disagree.append(["path-bfs", args, w, cb])
        if nxp is not None and (nxp.split(" steps")[0] != w.split(" steps")[0]):
            disagree.append(["path-nx", args, w, nxp])
        pairs.append({"args": args, "ids": T.encode(X.template_text("path", args)), "want": w})
    p = hf.apply_chat_template([{"role": "system", "content": HT.system_prompt(g)}, {"role": "user", "content": USER}], tools=HT.tools_for("base"), add_generation_prompt=True, enable_thinking=False, tokenize=True)
    prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
    out = {"format": "x210-exam-items/1", "name": a.name, "seed": SEED, "graph_sha256": hashlib.sha256(open(gp, "rb").read()).hexdigest(), "reflib_sha256": hashlib.sha256(open(reflib.__file__, "rb").read()).hexdigest(), "n": n, "e": len(g["edges"]), "r": len(g["relations"]),
           "file_chases": file_n, "file_dropped_by_window": file_dropped, "generated_chases": len(chases) - file_n, "prompt_ids": prompt, "between_ids": T.encode(" "), "questions": qs, "units": units, "pairs": pairs, "gold_bad": gold_bad[:50], "gold_bad_n": len(gold_bad), "disagree": disagree[:50], "disagree_n": len(disagree), "closures": closures}
    json.dump(out, open(a.out, "w"), ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ("name", "n", "e", "r", "file_chases", "file_dropped_by_window", "generated_chases", "gold_bad_n", "disagree_n", "closures")}), "first bad", json.dumps(gold_bad[:2] + disagree[:2], ensure_ascii=False)[:800], "affected per closure", [sum(u["closed_want"][i] != qs[i]["base"] for i in range(len(qs))) for u in units], flush=True)
    sys.exit(1 if disagree or gold_bad else 0)


if __name__ == "__main__":
    main()
