#!/usr/bin/env python3
"""Round 11 critic: sequences aimed at r4's touched bitmaps, tight path and iterators, against reflib; run on r4 and r2 with the same seeds.
Through tokrun: attack.py --out FILE --aimed | --fuzz N --seed S --limit-s T [--no-ref]"""
import hashlib, json, os, random, sys, time
EXAM = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, EXAM)
import mach as M
import noun as N
import reflib
import box as XX

a = sys.argv
out = a[a.index("--out") + 1]
lim = float(a[a.index("--limit-s") + 1]) if "--limit-s" in a else 1e9
elf = hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()[:8]
it = json.load(open(os.path.join(EXAM, "items", "nyc.json")))
gj = json.load(open(os.path.join(EXAM, "items", "nyc_t.graph.json")))
g = N.with_noun(gj)
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
if "--no-ref" in a:
    pair._ref = lambda ids, first: ("", "")
T = pair.T
f = open(out, "a", buffering=1)
G0 = reflib.Graph(g)
RELS = G0.rels
LAB = G0.labels
uniq = sorted(l for l, v in G0.by_label.items() if len(v) == 1)
shared = sorted(l for l, v in G0.by_label.items() if len(v) > 1 and G0._station(l))
t0 = time.time()
stats = {"calls": 0, "diff": 0}


ONLY = a[a.index("--only") + 1].split(",") if "--only" in a else None


def seq(tag, calls):
    if ONLY and tag.split(":")[0] not in ONLY:
        return
    pair.fresh()
    G = reflib.Graph(g)
    for j, (fn, x) in enumerate(calls):
        x = {k: str(v) for k, v in x.items()}
        ids = T.encode(XX.template_text(fn, x))
        if XX.capture_rule(ids, T):
            continue
        r = pair.call(ids)
        w = G.call(fn, x)
        eq = r["body"] == w
        stats["calls"] += 1
        stats["diff"] += not eq
        f.write(json.dumps({"tag": tag, "j": j, "fn": fn, "args": x, "body": r["body"], "status": r["status"], "chip": r["chip"], "same_ref": bool(r["same"]), "want": w, "eq": eq, "elf": elf}) + "\n")


def path(x, y): return ("path", {"from": x, "to": y})
def link(x, r, y, w=None): return ("link", dict({"from": x, "relation": r, "to": y}, **({} if w is None else {"weight": w})))
def unlink(x, r, y): return ("unlink", {"from": x, "relation": r, "to": y})
def nb(x, r, d="out"): return ("neighbours", {"node": x, "relation": r, "direction": d})
def add(n): return ("add_node", {"name": n})
def close(n): return ("close", {"node": n})
def reopen(n): return ("reopen", {"node": n})
def cheap(x, y): return ("cheapest", {"from": x, "to": y})
def H(h): return f"@{h}"


def edge_route():
    """A real shortest route's base edges, by a fixed BFS over reflib."""
    return [e for e in gj["edges"]]


def aimed():
    rng = random.Random("round11:aimed")
    E = gj["edges"]
    route = ("Roosevelt Island", "Junius St")
    gg = reflib.Graph(g)
    base = gg.path(*route)
    hops = [int(s.split()[0][1:]) for s in base.split(": ", 1)[1].split(" > ")]
    # every base edge on the route, unlinked one at a time: dead_ and touched_ both ways, then relink and route again
    for i in range(min(len(hops) - 1, 14)):
        x, y = hops[i], hops[i + 1]
        rs = [RELS[r] for a_, r, b, w in E if a_ == x and b == y]
        s = []
        for r in rs:
            s += [unlink(H(x), r, H(y)), path(H(hops[0]), H(hops[-1])), path(H(x), H(y)), path(H(y), H(x)), nb(H(x), r), nb(H(y), r, "in")]
        s += [link(H(x), rs[0], H(y), 3), path(H(hops[0]), H(hops[-1])), cheap(H(hops[0]), H(hops[-1])), nb(H(x), rs[0]), nb(H(y), rs[0], "in")]
        s += [unlink(H(x), rs[0], H(y)), path(H(hops[0]), H(hops[-1]))]
        seq(f"unlink_base:{i}", s)
    # all out edges / all in edges of a stop dead: touched and empty
    for x in rng.sample(range(496), 8):
        outs = [(RELS[r], b) for a_, r, b, w in E if a_ == x]
        ins = [(a_, RELS[r]) for a_, r, b, w in E if b == x]
        tgt = rng.randrange(496)
        s = [path(H(tgt), H(x)), path(H(x), H(tgt))]
        for r, b in outs:
            s += [unlink(H(x), r, H(b))]
        s += [path(H(x), H(tgt)), path(H(tgt), H(x))]
        for a_, r in ins:
            s += [unlink(H(a_), r, H(x))]
        s += [path(H(tgt), H(x)), path(H(x), H(tgt)), add("Moss Pk"), link(H(x), "T northbound", "Moss Pk"), path(H(x), "Moss Pk"), path("Moss Pk", H(x))]
        seq(f"isolate:{x}", s)
    # swap-remove: several added edges, remove the first, the swapped-in one must still route, both ways
    for k in range(6):
        st = rng.sample(uniq, 7)
        s = [add(f"Sw{i} Rd") for i in range(5)]
        ed = [(st[0], "T northbound", "Sw0 Rd"), ("Sw0 Rd", "T northbound", "Sw1 Rd"), ("Sw1 Rd", "T southbound", "Sw2 Rd"), ("Sw2 Rd", "T northbound", st[1]), (st[0], "T northbound", "Sw3 Rd"), ("Sw3 Rd", "T northbound", "Sw2 Rd")]
        s += [link(*e) for e in ed]
        s += [path(st[0], st[1])]
        for e in rng.sample(ed, len(ed)):
            s += [unlink(*e), path(st[0], st[1]), path(st[0], "Sw2 Rd"), nb("Sw2 Rd", "T northbound", "in"), nb(st[0], "T northbound"), ("chase", {"start": st[0], "legs": "T northbound 2"})]
        s += [link(*e) for e in ed] + [path(st[0], st[1])]
        seq(f"swap:{k}", s)
    # walk back: an added edge gives the target a lower-handle predecessor on the same level; a higher one must not win
    for k in range(16):
        x, y = rng.sample(range(496), 2)
        p = gg.path(H(x), H(y))
        if p == "NOPATH" or p.startswith("0 "):
            continue
        hop = [int(s.split()[0][1:]) for s in p.split(": ", 1)[1].split(" > ")]
        if len(hop) < 3:
            continue
        s = [path(H(x), H(y))]
        for pick in rng.sample(range(496), 6):
            s += [link(H(pick), "T northbound", H(y)), path(H(x), H(y)), link(H(x), "T southbound", H(pick)), path(H(x), H(y)), cheap(H(x), H(y))]
        seq(f"walkback:{k}", s)
    # new stops both ways, target a base stop only via new stops, self-loops, start = target
    for k in range(6):
        st = rng.sample(uniq, 5)
        s = [add("N1 St"), add("N2 St"), add("N3 St")]
        s += [link("N1 St", "T northbound", "N1 St"), path("N1 St", "N1 St"), path("N1 St", "N2 St")]
        s += [link(st[0], "T northbound", "N1 St"), link("N1 St", "T northbound", "N2 St"), link("N2 St", "T southbound", st[1]), link("N3 St", "T northbound", "N2 St")]
        s += [path(st[0], st[1]), path("N3 St", st[1]), path(st[1], "N3 St"), path("N2 St", "N3 St"), path(st[0], st[0]), link(st[0], "T northbound", st[0]), link(st[1], "T northbound", st[1]), path(st[0], st[1]), path(st[0], st[0]), nb(st[0], "T northbound"), nb(st[0], "T northbound", "in"), unlink(st[0], "T northbound", st[0]), path(st[0], st[1]), link(st[1], "transfer", "N3 St"), path(st[0], "N3 St"), cheap(st[0], st[1]), cheap("N1 St", st[1])]
        seq(f"newstops:{k}", s)
    # close, writes, route; reopen, route: n_closed back to 0, stale closed bits, tight path
    for k in range(12):
        x, y, c, d = rng.sample(range(496), 4)
        pp = gg.path(H(x), H(y))
        mids = [int(s.split()[0][1:]) for s in pp.split(": ", 1)[1].split(" > ")][1:-1] if " > " in pp else []
        if mids:
            c = mids[len(mids) // 2]
        s = [add("Cl1 St"), close(H(c)), path(H(x), H(y)), link(H(x), "T northbound", "Cl1 St"), link("Cl1 St", "T northbound", H(y)), path(H(x), H(y)), close("Cl1 St"), path(H(x), H(y)), cheap(H(x), H(y)), link(H(c), "T northbound", H(d)), unlink(H(x), "T northbound", "Cl1 St"), path(H(x), H(y)), reopen("Cl1 St"), path(H(x), H(y)), reopen(H(c)), path(H(x), H(y)), path(H(c), H(d)), link(H(x), "T northbound", "Cl1 St"), path(H(x), H(y)), close(H(c)), reopen(H(c)), close("Cl1 St"), reopen("Cl1 St"), path(H(x), H(y)), ("chase", {"start": H(x), "legs": "T northbound 1", "closed": H(c), "reopened": ""}), path(H(x), H(y)), ("chase", {"start": H(x), "legs": "T northbound 1", "closed": "", "reopened": H(c)}), path(H(x), H(y)), nb(H(y), "T northbound", "in")]
        seq(f"closewrite:{k}", s)
    # stations: one-station names, path_multi, transfers cut and restored, close and reopen by name after writes
    for k, nm in enumerate(rng.sample(shared, min(10, len(shared)))):
        hs = G0.by_label[nm]
        o = rng.choice(uniq)
        s = [path(nm, o), path(o, nm), close(nm), path(o, nm), reopen(nm), add("St9 Rd"), link(o, "T northbound", "St9 Rd"), link("St9 Rd", "T northbound", H(hs[-1])), path(o, nm), path(nm, "St9 Rd"), path(o, H(hs[0])), path(nm, nm)]
        s += [unlink(H(hs[0]), "transfer", H(hs[1])), path(o, nm), close(nm), reopen(nm), path(nm, o), link(H(hs[0]), "transfer", H(hs[1])), path(o, nm), close(nm), reopen(nm), path(o, nm)]
        s += [unlink(H(hs[1]), "transfer", H(hs[0])), path(o, nm), close(H(hs[0])), path(o, nm), close(nm), reopen(nm), reopen(H(hs[0])), path(o, nm)]
        seq(f"station:{k}", s)
    # stale touched: writes all undone, then base behaviour, with fresh edits on other stops; every read kind
    for k in range(6):
        st = rng.sample(uniq, 6)
        e1 = (st[0], "T northbound", st[1])
        s = [link(*e1), path(st[0], st[1]), unlink(*e1), path(st[0], st[1]), cheap(st[0], st[1]), nb(st[0], "T northbound"), nb(st[1], "T northbound", "in"), ("follow", {"node": st[0], "relation": "T northbound", "steps": 1}), add("St0 Av"), path(st[0], st[1]), link(st[2], "T southbound", st[3]), path(st[0], st[1]), cheap(st[0], st[1]), link(*e1, 9), cheap(st[0], st[1]), path(st[0], st[1]), ("find", {"name": st[0], "has": "T northbound"}), ("follow", {"node": st[0], "relation": "T northbound", "steps": 2})]
        seq(f"stale:{k}", s)


W1 = ["Moss", "Fern", "Wren", "Lark", "Quay", "Ash", "Vale", "Heron", "Sable", "Tamar", "Ivy", "Oak"]
W2 = ["Pk", "St", "Sq", "Av", "Rd"]


def fuzz(s, seed):
    rng = random.Random(f"{seed}:{s}")
    G = reflib.Graph(g)
    # a hot neighbourhood, by BFS from a random stop: reads and writes on it interact
    seed_h = rng.randrange(496)
    hot, q = [seed_h], [seed_h]
    adj = {}
    for a_, r, b, w in gj["edges"]:
        adj.setdefault(a_, []).append(b)
        adj.setdefault(b, []).append(a_)
    size = rng.choice([8, 16, 32, 64])
    while q and len(hot) < size:
        x = q.pop(0)
        for y in adj.get(x, []):
            if y not in hot:
                hot.append(y); q.append(y)
    hot = hot[:size]
    new, added = [], []
    calls, closed = [], []
    nm = lambda h: (LAB[h] if rng.random() < .5 and len(G0.by_label[reflib.norm(LAB[h])]) == 1 else H(h)) if isinstance(h, int) else h
    rels = rng.sample(RELS, 3) + ["transfer", "T northbound"]
    base = [(a_, RELS[r], b) for a_, r, b, w in gj["edges"] if a_ in hot and b in hot]
    pick = lambda: rng.choice(hot + new) if new and rng.random() < .3 else rng.choice(hot)
    count = rng.randint(15, 45)
    pc = rng.random()
    for _ in range(count):
        u = rng.random()
        if u < .10 and len(new) < 16:
            while True:
                n = f"{rng.choice(W1)} {rng.choice(W2)}"
                if n not in new:
                    break
            new.append(n); calls.append(add(n))
        elif u < .30:
            e = (pick(), rng.choice(rels), pick())
            added.append(e); calls.append(link(nm(e[0]), e[1], nm(e[2]), rng.choice([None, 0, 1, 2, 5, 65535])))
        elif u < .38 and added:
            e = added.pop(rng.randrange(len(added))); calls.append(unlink(nm(e[0]), e[1], nm(e[2])))
        elif u < .46 and base:
            e = base.pop(rng.randrange(len(base))); calls.append(unlink(nm(e[0]), e[1], nm(e[2]))); added.append(e) if rng.random() < .3 else None
        elif u < .46 + .10 * pc:
            h = pick(); closed.append(h); calls.append(close(nm(h)))
        elif u < .46 + .22 * pc and closed:
            calls.append(reopen(nm(closed.pop(rng.randrange(len(closed))))))
        elif u < .80:
            calls.append(path(nm(pick()), nm(pick())))
        elif u < .85:
            calls.append(cheap(nm(pick()), nm(pick())))
        elif u < .91:
            calls.append(nb(nm(pick()), rng.choice(rels), rng.choice(["in", "out"])))
        elif u < .95:
            calls.append(("chase", {"start": nm(pick()), "legs": f"{rng.choice(rels)} {rng.randint(1, 3)}"}))
        elif u < .98:
            calls.append(("follow", {"node": nm(pick()), "relation": rng.choice(rels), "steps": rng.randint(1, 3)}))
        else:
            n = pick()
            calls.append(("find", {"name": LAB[n] if isinstance(n, int) else n, "has": rng.choice(rels)}))
    seq(f"fuzz:{s}", calls)


def cap():
    """The edit table nearly full, the long route's stops touched, base edges dead: cost and lines at the limit."""
    gg = reflib.Graph(g)
    for tag, (x, y), n in (("cap49", ("Far Rockaway-Mott Av", "Wakefield-241 St"), 240), ("cap14", ("Roosevelt Island", "Junius St"), 240), ("cap49s", ("Far Rockaway-Mott Av", "Wakefield-241 St"), 60)):
        p = gg.path(x, y)
        hop = [int(t.split()[0][1:]) for t in p.split(": ", 1)[1].split(" > ")]
        rng = random.Random("round11:cap:" + tag)
        s = [path(x, y)]
        pairs = [(a_, b) for a_ in hop for b in rng.sample(range(496), 8) if b not in hop]
        rng.shuffle(pairs)
        for i, (a_, b) in enumerate(pairs[:n]):
            s.append(link(H(a_), "T southbound", H(b)))
            s.append(link(H(b), "T northbound", H(hop[(hop.index(a_) + 1) % len(hop)]))) if len(s) < n else None
        s = s[:n + 1]
        s += [path(x, y), path(y, x), add("Capz St"), link(H(hop[-2]), "T northbound", "Capz St"), path(x, "Capz St")]
        seq(tag, s)


def capclosed():
    """A closure sends the route down path_cursor: the fix doesn't apply. New-stop chain, then near-full table, then one unrelated stop closed."""
    names = [f"Capstop {i:02d}" for i in range(14)]
    c = [add(n) for n in names]
    prev = "Roosevelt Island"
    for n in names:
        c.append(link(prev, "T northbound", n)); prev = n
    c += [path("Roosevelt Island", names[-1]), close("Junius St"), path("Roosevelt Island", names[-1]), reopen("Junius St"), path("Roosevelt Island", names[-1])]
    seq("chain14closed", c)
    gg = reflib.Graph(g)
    x, y = "Far Rockaway-Mott Av", "Wakefield-241 St"
    hop = [int(t.split()[0][1:]) for t in gg.path(x, y).split(": ", 1)[1].split(" > ")]
    rng = random.Random("round11:capclosed")
    pairs = [(a_, b) for a_ in hop for b in rng.sample(range(496), 8) if b not in hop]
    rng.shuffle(pairs)
    other = next(h for h in range(496) if h not in hop)
    s = [link(H(a_), "T southbound", H(b)) for a_, b in pairs[:240]]
    s += [path(x, y), close(H(other)), path(x, y), path(H(hop[0]), H(hop[len(hop) // 2])), reopen(H(other)), path(x, y)]
    seq("cap49closed", s)


if "--capclosed" in a:
    capclosed()
if "--cap" in a:
    cap()
if "--aimed" in a:
    aimed()
if "--fuzz" in a:
    n = int(a[a.index("--fuzz") + 1])
    seed = a[a.index("--seed") + 1]
    for s in range(n):
        if time.time() - t0 > lim:
            print("deadline at", s, flush=True)
            break
        fuzz(s, seed)
print(json.dumps(stats), round(time.time() - t0, 1), "finished", flush=True)
