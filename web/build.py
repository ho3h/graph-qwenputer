#!/usr/bin/env python3
"""The post's demos, from saved rows only. Run from X2.10: python3 web/build.py. Fills web/template.html's {{DATA}} into web/index.html."""
import collections
import glob
import gzip
import json
import os
import re

g = json.load(open("data/heldout/nyc/nyc.graph.json"))
x27 = json.load(open("../X2.7/graph.json"))["stations"]
names = g["relations"]
R6 = os.path.exists("exam/results/r6_all/READY")                   # exam/AFTER.md r6: the machine exam on the blocking rule, once all of it is in
it = json.load(open("exam/items/nyc_b_all.json" if R6 else "exam/items/nyc_all.json"))
Q = it["questions"]
lab = [n["label"] for n in g["nodes"]]
R = "exam/results/r6_all/" if R6 else "exam/results/mini/all/"
rows = lambda u: [json.loads(x) for x in gzip.open(f"{R}{u}.jsonl.gz", "rt", encoding="utf-8", errors="surrogateescape")]
COL = {**dict.fromkeys("123", "#EE352E"), **dict.fromkeys(["4", "5", "6", "6X"], "#00933C"), "7": "#B933AD", "7X": "#B933AD", **dict.fromkeys("ACE", "#0039A6"), **dict.fromkeys(["B", "D", "F", "FX", "M"], "#FF6319"), "G": "#6CBE45", **dict.fromkeys("JZ", "#996633"), "L": "#A7A9AC", **dict.fromkeys("NQRW", "#FCCC0A"), "SI": "#0078C6", "GS": "#808183", "FS": "#808183", "H": "#808183"}


def say(b):
    if b.startswith("@"):
        return b.split(" ", 1)[1]
    if b.startswith("Stopped"):
        m = re.search(r"at @\d+ (.+?)(?:, |$)", b)
        return "the trip stops early at " + m.group(1)
    if "AMBIGUOUS" in b:
        return "refused: that name is shared"
    return re.sub(r"@\d+ ", "", b.split("\n")[-1])[:70]


def trip(a):
    legs = [x.strip().rsplit(" ", 2) for x in a["legs"].split(";")]
    t = " then ".join(f"{l[0]} train {l[1]} {l[2]} stop" + ("" if l[2] == "1" else "s") for l in legs)
    return f"From {lab[int(a['start'][1:])]}: {t}"


nodes = []
for i, n in enumerate(g["nodes"]):
    s = x27[n["src"]]
    nodes.append({"n": n["label"], "x": round(s["lon"], 4), "y": round(s["lat"], 4)})
src2h = {n["src"]: i for i, n in enumerate(g["nodes"])}
ORDER = "123456 7 ACE BDFM G JZ L NQRW".replace(" ", "")
edges = []
for p in json.load(open("web/geometry.json")):
    rs = sorted(p["routes"], key=lambda r: (ORDER.find(r[0]) if r[0] in ORDER else 99, r))
    seen_c = []
    for r in rs:
        c = COL.get(r, "#808183")
        if c not in seen_c:
            seen_c.append(c)
    # geometry.json's points can run either way along a pair; draw them from a to b.
    A_, B_ = nodes[src2h[p["a"]]], nodes[src2h[p["b"]]]
    near = lambda q, n: ((q[0] - n["x"]) * .76) ** 2 + (q[1] - n["y"]) ** 2
    pts_ = p["pts"] if near(p["pts"][0], A_) + near(p["pts"][-1], B_) <= near(p["pts"][0], B_) + near(p["pts"][-1], A_) else p["pts"][::-1]
    edges.append([src2h[p["a"]], src2h[p["b"]], seen_c, pts_, rs])
transfers = sorted({(min(a, b_), max(a, b_)) for a, r, b_, w in g["edges"] if names[r] == "transfer"})
done = 0
for u in it["units"]:
    if u["kind"] != "close" or not os.path.exists(f"{R}{u['unit']}.json"):
        continue
    done += 1
    h = u["node"]
    ch = [(r["i"], Q[r["i"]]["base"], r["body"]) for r in rows(u["unit"]) if r["tag"] == "closed" and r["body"] != Q[r["i"]]["base"]]
    assert all(c[2] == u["closed_want"][c[0]] for c in ch), u["unit"]
    nodes[h]["c"] = len(ch)
    ch.sort(key=lambda c: (not (c[1].startswith("@") and c[2].startswith("@")), c[0]))
    if ch:
        nodes[h]["q"] = trip(Q[ch[0][0]]["args"])
        nodes[h]["a"] = say(ch[0][1])
        nodes[h]["b"] = say(ch[0][2])
        if nodes[h]["a"] == nodes[h]["b"]:
            nodes[h]["a"], nodes[h]["b"] = [re.sub(r"@\d+ ", "", re.sub(r"\. The journey did not finish\.|, no further step along this relation exists", "", x)) for x in ch[0][1:3]]
bo = rows("blackout")
order, steps, cur, ans = [], [], None, 0
ops = []
closed = 0
buf = []
for r in bo:
    if r["tag"] in ("close", "reopen"):
        if buf:
            ops.append({"closed": closed, "ok": sum(x["body"].startswith("@") for x in buf), "ex": say(buf[0]["body"]), "right": all(x["body"] == x["want"] for x in buf)})
            buf = []
        closed += 1 if r["tag"] == "close" else -1
        if r["tag"] == "close":
            order.append(int(re.search(r"@(\d+)", r["want"]).group(1)))
    elif r["tag"] == "during":
        buf.append(r)
if buf:
    ops.append({"closed": closed, "ok": sum(x["body"].startswith("@") for x in buf), "ex": say(buf[0]["body"]), "right": True})
stock = {r["key"]: r for r in map(json.loads, open("exam/results/nyc_r1_edit_stock/all.jsonl"))}
draw = json.load(open("exam/results/nyc_r1_edit_draw.json"))
game = []
seenw = set()
for c in draw["plain"]:
    if c["wording"] in seenw:
        continue
    seenw.add(c["wording"])
    t = stock[c["key"]]["turns"][0]
    closed_it = any("closed" in x["args"] for x in t["calls"])
    game.append({"s": c["wording"].format(X=c["label"]), "h": c["node"], "close": False, "qwen": closed_it})
fired = [g_ for g_ in game if g_["qwen"]][:3]
held = [g_ for g_ in game if not g_["qwen"]][:3]
true = []
for c in draw["conversations"][:40:13]:
    t = stock[c["key"]]["turns"][0]
    true.append({"s": c["wording"].format(X=c["label"]), "h": c["node"], "close": True, "qwen": any("closed" in x["args"] for x in t["calls"])})
true = true[:2]
game = [fired[0], true[0], held[0], fired[1], held[1], true[1], fired[2], held[2]]
step = {(a, names[r]): b_ for a, r, b_, w in g["edges"]}
trans = collections.defaultdict(set)
for a, r, b_, w in g["edges"]:
    if names[r] == "transfer":
        trans[a].add(b_)
        trans[b_].add(a)


def walk(start, legs):
    """The trip's stops from the map alone, for drawing. Checked against the saved answer where it's used."""
    ids = [start]
    for leg in legs.split(";"):
        line, d, n = leg.strip().rsplit(" ", 2)
        rel = f"{line} {d}"
        seen, q = {ids[-1]}, [ids[-1]]
        for x in q:
            for y in trans[x]:
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        at = next((x for x in q if (x, rel) in step), None)
        if at is None:
            return None
        if at != ids[-1]:
            ids.append(at)
        for _ in range(int(n)):
            if (ids[-1], rel) not in step:
                return None
            ids.append(step[(ids[-1], rel)])
    return ids


def walk_named(args, end):
    s = args["start"]
    starts = [int(s[1:])] if s.startswith("@") else [i for i, l in enumerate(lab) if l == s]
    for h in starts:
        ids = walk(h, args["legs"])
        if ids and ids[-1] == end:
            return ids
    return None


def named_in(text, skip):
    hit = [l for l in set(lab) if l in text and l != skip]
    return [i for i, l in enumerate(lab) if l == max(hit, key=len)][0] if hit else None


sample = []
for q in Q[::9]:
    m = re.match(r"@(\d+)", q["base"])
    if m and "legs" in q["args"]:
        ids = walk_named(q["args"], int(m.group(1)))
        if ids and len(ids) > 3:
            sample.append(ids)
sample = sample[:70]
alone = {r["id"]: r for r in map(json.loads, open("exam/results/after/alone.jsonl"))}
mapped = {r["id"]: r for r in map(json.loads, open("exam/results/after/mapped/M1.jsonl"))}
mach = {r["id"]: r for r in map(json.loads, open("exam/results/nyc_r1_d1m/all.jsonl"))}
think = {r["id"]: r for r in map(json.loads, open("exam/results/after/think2/P.jsonl"))}  # round 18: the map lines, reasoning on
file = {q["id"]: q for q in json.load(open("data/heldout/nyc/nyc.questions.json"))["questions"]}
ask = []
for i in range(100, 106):
    q = file[i]
    m = mapped[i]
    gold = int(re.match(r"@(\d+)", q["answer_text"]).group(1))
    a_, m_ = alone[i]["final"].strip(), (m["answer"].replace("*", "").strip() if m["finished"] else "")
    wrong = []
    for who, txt in (("Qwen alone, reasoning off", a_), ("Qwen with map, reasoning off", m_)):
        h = named_in(txt[:80], lab[gold]) if lab[gold] not in txt else None
        if h is not None:
            wrong.append({"who": who, "h": h})
    ids = walk_named(mach[i]["calls"][-1]["args"], gold)
    assert ids, i
    ask.append({"q": q["text"].split(" One stop means")[0], "right": say(q["answer_text"]), "alone": a_[:80], "map": m_[:80] or "(did not finish within 1,024 tokens)", "think": think[i]["after_think"].strip()[:80] if think[i]["stopped"] else "(did not finish within 8,192 tokens)", "machine": say(mach[i]["calls"][-1]["result"].split("\n")[-1]), "ids": ids, "wrong": wrong})
ch_rows = {r["key"]: r for r in map(json.loads, open("exam/results/after/choice/all.jsonl"))}
choice = []
for k, short in (("A:0", "71 St to Neck Rd"), ("C:0", "Capital of France?"), ("C:2", "17 times 23"), ("C:1", "A haiku"), ("D:0", "Paris to Lyon")):
    t = ch_rows[k]["turns"][-1]
    called = bool(t["calls"])
    line = t["calls"][-1]["result"].split("\n")[-1] if called else ""
    line = re.sub(r"@\d+ ", "", line)
    rep = re.sub(r"\s+", " ", (t["reply"] or "")).replace("**", "")
    ids_ = [int(x) for x in re.findall(r"@(\d+)", t["calls"][-1]["result"].split("\n")[-1])] if called else []
    choice.append({"short": short, "q": t["user"], "called": "Called the graph-qwenputer" if called else "Answered by itself", "line": line, "reply": rep, "ids": ids_ if len(ids_) > 1 else None})
LX, LY, K, S = -74.27, 40.93, .76, 2230
land = []
for rings in json.load(open("web/land.json"))["boroughs"].values():
    d = ""
    for r in rings:
        pts = [f"{(x - LX) * K * S:.1f} {(LY - y) * S:.1f}" for x, y in r]
        d += "M" + "L".join(pts) + "Z"
    land.append(d)
near = ""
for r in json.load(open("web/near.json"))["rings"]:
    near += "M" + "L".join(f"{(x - LX) * K * S:.0f} {(LY - y) * S:.0f}" for x, y in r) + "Z"
by = lambda l: [i for i, x in enumerate(lab) if x == l]
fx14 = next(i for i in by("14 St") if (i, "FX northbound") in step or (i, "FX southbound") in step)
jrn = []
JF = "exam/results/after/r6_journeys/all.jsonl" if os.path.exists("exam/results/after/r6_walk.done") or os.path.getsize("exam/results/after/r6_journeys/all.jsonl") > 0 else "exam/results/after/journeys/all.jsonl"
for r in map(json.loads, open(JF)):
    it_, ts = r["item"], r["turns"]
    assert ts[0]["calls"][-1]["result"] == it_["routes"][0], r["key"]
    e = {"short": f"{it_['from'].split('-')[0]} to {it_['to'].split('-')[0]}", "user": ts[0]["user"], "fn": f"path {it_['from']}\nto {it_['to']}", "ids": [int(x) for x in re.findall(r"@(\d+)", it_["routes"][0])], "ran": "the real weights" if str(r["ran_on"]).startswith("stock") else "the simulator"}
    if len(ts) > 1:
        assert ts[1]["calls"][-1]["result"] == it_["routes"][1], r["key"]
        e.update({"ids2": [int(x) for x in re.findall(r"@(\d+)", it_["routes"][1])], "closed": it_["closed"], "close2": ts[1]["user"], "fn2": f"close {lab[it_['closed']]}\npath {it_['from']}\nto {it_['to']}"})
    jrn.append(e)
FIRST = ("Astoria to Canarsie", "Far Rockaway to Wakefield", "Bedford Av to WTC Cortlandt")
jrn.sort(key=lambda e: FIRST.index(e["short"]) if e["short"] in FIRST else 9)
draw_w = json.load(open("exam/results/after/r6_walk_draw.json"))["conversations"][0]
WALK = next(map(json.loads, open("exam/results/after/r6_walk/all.jsonl")), None) if os.path.exists("exam/results/after/r6_walk/all.jsonl") else None
if WALK and WALK["status"] != "answered":                          # exam/AFTER.md r6e: a stopped conversation is reported, and never drawn as a finished one
    WALK = None
idsof = lambda s: [int(x) for x in re.findall(r"@(\d+)", s)]
walk_d = {"q": [t_["user"] for t_ in draw_w["turns"]], "r0": idsof(draw_w["routes"][0]), "r1": idsof(draw_w["routes"][1]), "closed": draw_w["closed"], "line": draw_w["turns"][0]["gold"], "alone": json.load(open("exam/results/after/r6_alone.json"))["reply"].strip()}
if WALK:
    assert WALK["ran_on"].startswith("stock") and not WALK["verify_mismatch"]
    assert [t_["calls"][-1]["result"].split("\n")[-1] for t_ in WALK["turns"]] == [t_["gold"] for t_ in WALK["turns"]]
    _wc = [c for t_ in WALK["turns"] for c in t_["calls"]]
    _ws = {i: s_ for i, s_ in enumerate(WALK["states"])}
    walk_d.update({"tok": [_wc[0]["chip"], _wc[1]["chip"], _wc[3]["chip"]], "reply": [t_["reply"].strip() for t_ in WALK["turns"]], "sha0": WALK["states"][0]["engine"]["sha"], "sha2": WALK["states"][-1]["engine"]["sha"]})
    assert walk_d["sha0"] == walk_d["sha2"], "fingerprint returns"
else:                                                              # the simulator's measured numbers, labelled as such, until the real-weights row exists
    _sim = json.load(open("exam/results/after/r6_walk_sim.json"))["calls"]
    assert idsof(_sim[1]["body"]) == walk_d["r0"] and idsof(_sim[3]["body"]) == walk_d["r1"] and _sim[5]["body"] == _sim[1]["body"]
    walk_d.update({"tok": [_sim[0]["chip"], _sim[1]["chip"], _sim[3]["chip"]], "reply": ["425 Pennsylvania Av"] * 4, "sha0": "(run in progress)", "sha2": "(run in progress)"})
dm = json.loads(open("exam/results/after/demo/all.jsonl").readline())
assert dm["ran_on"].startswith("stock") and not dm["verify_mismatch"] and dm["returned_to_start"]
assert [t_["calls"][-1]["result"].split("\n")[-1] for t_ in dm["turns"]] == [t_["gold"] for t_ in dm["turns"]]
d_ids = walk(223, "4 southbound 5; 3 southbound 5")
assert d_ids[-1] == 425
d_x = dm["item"]["node"]
d_i = d_ids.index(d_x)
d_c = d_ids[:d_i] + d_ids[d_i + 1:] + [step[(d_ids[-1], "3 southbound")]]
assert d_c[-1] == 473
sts = dm["states"]
demo = {"ids": d_ids, "idsc": d_c, "closed": d_x, "via": [d_ids[d_i - 1], d_x, d_ids[d_i + 1]], "tok": dm["turns"][0]["calls"][0]["chip"], "reply": dm["turns"][0]["reply"].strip(), "sha0": sts[0]["engine"]["sha"], "shac": sts[2]["engine"]["sha"]}
rt = collections.defaultdict(set)
for a_, r_, b_, w_ in g["edges"]:
    if names[r_] != "transfer":
        rt[a_].add(names[r_].split()[0])
        rt[b_].add(names[r_].split()[0])
okey = lambda r: (ORDER.find(r[0]) if r[0] in ORDER else 99, r)
for i, n in enumerate(nodes):
    n["r"] = sorted(rt[i], key=okey)
data = {"near": near, "demo": demo, "walk": walk_d, "col": COL, "land": land, "sample": sample, "jrn": jrn, "fulton": by("Fulton St"), "st14": by("14 St"), "st14fx": fx14, "times": by("Times Sq-42 St"), "st125": by("125 St"), "transfers": transfers, "choice": choice, "nodes": nodes, "edges": edges, "order": order, "ops": ops, "game": game, "ask": ask, "done": done}
import html as _html
_ls = {r["key"]: r for r in map(json.loads, open("exam/results/after/lines2/all.jsonl"))}["nyc-t2:1"]
_j = next(r for r in map(json.loads, open("exam/results/after/journeys/all.jsonl")) if r["item"]["from"] == "Bedford Av")
assert str(_ls["ran_on"]).startswith("stock") and str(_j["ran_on"]).startswith("stock")
_tc = [c for t_ in _ls["turns"] for c in t_["calls"]]
_show = [_j["turns"][0]["calls"][0], _j["turns"][1]["calls"][0], _j["turns"][1]["calls"][1], _tc[1], _tc[3], _tc[5], _tc[6]]
graphcalls = "\n".join(f'<span class="k">{c["fn"]}</span>(' + ", ".join(f'{k}="{_html.escape(v)}"' for k, v in c["args"].items()) + f')\n<span class="r">  {_html.escape(c["result"])}</span>' for c in _show)
_z = next(map(json.loads, open("exam/results/after/z3b/all.jsonl")))
_zl = _z["turns"][2]["calls"][-1]["result"]
_zi = [int(x) for x in re.findall(r"@(\d+)", _zl)]
_zk = _zi.index(496)
z3 = {"pre": _zi[:_zk], "post": _zi[_zk + 2:], "steps": int(_zl.split()[0]), "first": _z["turns"][0]["reply"].strip()}
assert _z["turns"][0]["calls"][-1]["result"] == "NOPATH" and z3["pre"][-1] == 269 and z3["post"][0] == 415
data["z3"] = z3
_zc = [json.loads(x) for x in open("exam/results/after/z3c/all.jsonl")] if os.path.exists("exam/results/after/z3c/all.jsonl") else []
_zok = _zc and _zc[0]["status"] == "answered" and str(_zc[0]["ran_on"]).startswith("stock") and not _zc[0].get("verify_mismatch") and _zc[0]["turns"][2]["calls"][-1]["result"] == _zl
Z3RAN = (f"One conversation ran whole on the real model, in about {round(_zc[0]['seconds'] / 60)} minutes, and all {_zc[0]['verified_positions']:,} tokens matched the simulator." if _zok else "Those ran Qwen on the real weights and the machine on the simulator, about a minute each. One of them, on the real weights, matched through its first two turns, 90,911 positions with none differing, and my time limit ran out before the final route.")
_r5 = 0
for _f in glob.glob("exam/results/mini/r5/r5_all/*.jsonl.gz"):
    for _l in gzip.open(_f, "rt", errors="surrogateescape"):
        _x = json.loads(_l)
        assert _x["body"] == _x["want"] and _x["same"]
        _r5 += 1
_rate = _zc[0]["seconds"] / _zc[0]["chip_tokens"]                   # the page's "nothing else running" rate: Z3c, the whole-model run with the Mac otherwise idle. r6e shared the Mac.
_chg = _same = 0
if R6:
    for u in it["units"]:
        if u["kind"] == "close":
            for r in rows(u["unit"]):
                if r["tag"] == "closed":
                    assert r["body"] == r["want"] and r["same"], u["unit"]
                    if r["body"] != Q[r["i"]]["base"]:
                        _chg += 1
                    else:
                        _same += 1
else:
    _chg, _same = 2186, 295414
_a1 = json.loads(open("exam/results/after/r6_walk_a1/all.jsonl").readline())
assert _a1["status"] == "walltime" and not _a1["verify_mismatch"] and [c_["chip"] for t_ in _a1["turns"] for c_ in t_["calls"]][:2] == walk_d["tok"][:2]
WALKLINE = (f"The whole conversation ran on the real model, start to finish. Every token matched a simulator, which is a program that does what the 11 layers do, much faster. The run took {round(WALK['seconds'] / 60)} minutes, with other jobs sharing the Mac. I chose the trip and the sentences for this post, so do not take the conversation as typical." if WALK else f"The real model has printed the first answer and the 10-step route, and all {_a1['verified_positions']:,} tokens matched the simulator. That run stopped on a time limit I set too low, during the route around the closure. A second run is in progress, so the reroute and the reopen here come from the simulator, a program that does what the 11 layers do much faster. I chose the trip and the sentences for this post, so do not take the conversation as typical.")
REOPENLINE = ("Qwen writes a reopen call, the square goes dark, and the old route returns. Before the flood and again after the repair, I took a fingerprint of the graph-qwenputer's record of edits. The record covers closures, added connections and removed connections, and the two fingerprints match. The route after the repair printed the same 10 steps in the same 39,584 tokens." if WALK else "In the simulator run I supply the reopen call, because Qwen's own reopen call on the real model is still in progress. The square goes dark, and the old route returns. A fingerprint covers the graph-qwenputer's record of edits, which means closures, added connections and removed connections, and on an earlier build the fingerprint returned to its start value after a reopen.")
PLAYNUMS = f"I closed each of the 496 stops in turn on the simulator, and {_chg:,} of {_chg:,} answers that should have changed did change, while {_same:,} of {_same:,} other answers stayed exactly the same. A reference machine agreed on every call. The reference machine is a second, separately built CPU that runs the same firmware. A separate Python library also gave the same answers."
PLAYRULE = "I changed the rule and ran the whole test again." if R6 else "I changed the rule and am running the whole test again. Until the test finishes, the stops you can tap and the numbers above show the earlier rule."
BOLINE = f"On the simulator, all {len(bo):,} calls were right, and at the end the 600 answers matched a fresh graph-qwenputer's answers." + ("" if R6 else f" The {len(bo):,} calls are from the earlier rule too.")
_jr = [json.loads(x) for x in open(JF)]
_jn = [r for r in _jr if len(r["turns"]) > 1]
_jc = [r for r in _jn if r["turns"][1]["calls"] and r["turns"][1]["calls"][-1]["result"] == r["item"]["routes"][1]]
_j1 = sum(r['turns'][0]['calls'][-1]['result'] == r['item']['routes'][0] for r in _jr)
assert _j1 == len(_jr) == 15 and len(_jc) == len(_jn) == 15, "the sentence below says all"
JOURNEYS = "The graph-qwenputer's route was right on all 15 trips. When I said that a stop on the route had closed, Qwen closed the stop and asked again in all 15 conversations, and the new route was right every time. Bay Ridge has no way around the closed stop, because the R is the only line there, and the graph-qwenputer says so. In the 15 trips, Qwen ran on the real model and the 11 layers ran on the simulator."
s = open("web/template.html").read().replace("{{TOK1}}", f"{walk_d['tok'][0]:,}").replace("{{TOK2}}", f"{walk_d['tok'][1]:,}").replace("{{MIN2}}", str(round(walk_d["tok"][1] * _rate / 60))).replace("{{WALKLINE}}", WALKLINE).replace("{{REOPENLINE}}", REOPENLINE).replace("{{PLAYNUMS}}", PLAYNUMS).replace("{{PLAYRULE}}", PLAYRULE).replace("{{BOLINE}}", BOLINE).replace("{{JOURNEYS}}", JOURNEYS).replace("{{Z3STEPS}}", str(z3["steps"])).replace("{{Z3RAN}}", Z3RAN).replace("{{R5EXAM}}", f"{_r5:,}").replace("{{GRAPHCALLS}}", graphcalls).replace("{{DATA}}", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
open("web/index.html", "w").write(s)
title = re.search(r"<title>.*?</title>", s, re.S).group(0)
style = re.search(r"<style>.*?</style>", s, re.S).group(0)
body = re.search(r"<body>(.*)</body>", s, re.S).group(1)
open(os.environ.get("PREVIEW", "<scratchpad>"), "w").write(title + '\n<meta name="claude:viewport-fit-sides" content="cover">\n' + style + body)
print("built", done, "closures", len(s), "bytes", len(ops), "checkpoints")
