#!/usr/bin/env python3
"""Every figure in web/index.html against the saved rows and the map file. python3 web/check_figures.py. Exit 1 on any failure."""
import glob
import json
import math
import os
import re

s = open("web/index.html").read()
_readme = "release/README.md" if os.path.exists("release/README.md") else "README.md"  # the repo, or the public bundle
s2 = s + open(_readme).read()                          # figures that moved from the post to the README stay checked
D = json.loads(re.search(r"const D=(\{.*?\});\nconst NS", s, re.S).group(1))
g = json.load(open("data/heldout/nyc/nyc.graph.json"))
names, lab = g["relations"], [n["label"] for n in g["nodes"]]
N = D["nodes"]
fails, checks = [], 0


def ok(c, msg):
    global checks
    checks += 1
    if not c:
        fails.append(msg)


edge = {(a, b) for a, r, b, w in g["edges"]}
und = edge | {(b, a) for a, b in edge}
tr = {(a, b) for a, r, b, w in g["edges"] if names[r] == "transfer"}
tr |= {(b, a) for a, b in tr}
drawn = {(e[0], e[1]) for e in D["edges"]} | {(e[1], e[0]) for e in D["edges"]}
trs = {tuple(x) for x in D["transfers"]} | {(b, a) for a, b in D["transfers"]}
dist = lambda a, b: math.hypot((N[a]["x"] - N[b]["x"]) * .76, N[a]["y"] - N[b]["y"]) * 111


def hops(ids, what, closed=()):
    """Each hop is a real connection, drawn as track or a transfer, or it steps over one closed stop."""
    for a, b in zip(ids, ids[1:]):
        if (a, b) in drawn or (a, b) in trs:
            ok(True, "")
            continue
        via = [c for c in closed if (a, c) in drawn and (c, b) in drawn]
        ok(via, f"{what}: hop {lab[a]} > {lab[b]} has no track, {dist(a, b):.2f} km")


# Track: every drawn pair is a real connection, its line starts and ends at its stops, and isn't a wild detour.
X, Y = lambda p: p[0] * .76, lambda p: p[1]
for a, b, cs, pts, rs in D["edges"]:
    ok((a, b) in und, f"edge {lab[a]}-{lab[b]} isn't in the map")
    d0 = math.hypot((pts[0][0] - N[a]["x"]) * .76, pts[0][1] - N[a]["y"]) * 111
    d1 = math.hypot((pts[-1][0] - N[b]["x"]) * .76, pts[-1][1] - N[b]["y"]) * 111
    ok(d0 < .35 and d1 < .35, f"track {lab[a]}-{lab[b]} ends {d0:.2f}/{d1:.2f} km from its stops")
    L = sum(math.hypot((p[0] - q[0]) * .76, p[1] - q[1]) * 111 for p, q in zip(pts, pts[1:]))
    ok(L < 3 * max(dist(a, b), .5), f"track {lab[a]}-{lab[b]} is {L:.1f} km for {dist(a, b):.1f} km")
missing = {e for e in edge if e not in drawn and e not in trs and e not in tr}
ok(not missing, f"{len(missing)} map connections not drawn: {[(lab[a], lab[b]) for a, b in list(missing)[:8]]}")

# Colours follow the MTA's.
C = D["col"]
for a, b, cs, pts, rs in D["edges"]:
    ok(set(cs) == {C.get(r, "#808183") for r in rs}, f"colors {lab[a]}-{lab[b]}")
ok(C["A"] == "#0039A6" and C["1"] == "#EE352E" and C["4"] == "#00933C" and C["7"] == "#B933AD" and C["F"] == "#FF6319" and C["G"] == "#6CBE45" and C["J"] == "#996633" and C["L"] == "#A7A9AC" and C["N"] == "#FCCC0A", "official colours")

# Walkthrough, from the real-weights row on the blocking map (exam/AFTER.md r6e).
W = D["walk"]
draw = json.load(open("exam/results/after/r6_walk_draw.json"))["conversations"][0]
ids = lambda t: [int(x) for x in re.findall(r"@(\d+)", t)]
step = {(a, names[r]): b for a, r, b, w in g["edges"]}
hops(W["r0"], "walkthrough")
hops(W["r1"], "walkthrough around the closure")
ok(lab[W["r0"][0]] == "Bowling Green" and lab[W["r0"][-1]] == "Pennsylvania Av" and W["r1"][-1] == W["r0"][-1], "walkthrough ends")
ok(lab[W["closed"]] == "Saratoga Av" and W["closed"] in W["r0"] and W["closed"] not in W["r1"], "the route really goes around")
ok(step[(W["r0"][0], "4 southbound")] == W["r0"][1], "first hop is the 4")
ok(W["alone"] == json.load(open("exam/results/after/r6_alone.json"))["reply"].strip() and W["alone"] not in lab, "Qwen alone names a stop the map doesn't have")
ok(f"Qwen says {W['alone']}." in s, "Qwen alone text")
import os
_sim = json.load(open("exam/results/after/r6_walk_sim.json"))["calls"]
ok(ids(_sim[1]["body"]) == W["r0"] and ids(_sim[3]["body"]) == W["r1"] and _sim[5]["body"] == _sim[1]["body"], "walkthrough routes on the simulator")
ok(W["tok"] == [_sim[0]["chip"], _sim[1]["chip"], _sim[3]["chip"]], f"walkthrough tokens {W['tok']}")
if os.path.exists("exam/results/after/r6_walk/all.jsonl") and os.path.getsize("exam/results/after/r6_walk/all.jsonl"):
    wr = json.loads(open("exam/results/after/r6_walk/all.jsonl").readline())
    wc = [c_ for t_ in wr["turns"] for c_ in t_["calls"]]
    ok(wr["status"] == "answered" or "is running on the real model" in s, "a stopped walkthrough is labelled")
    if wr["status"] == "answered":
        pass
    ok(str(wr["ran_on"]).startswith("stock") and not wr["verify_mismatch"], "walkthrough on the real weights")
    ok([c_["fn"] for c_ in wc] == ["chase", "path", "close", "path", "reopen", "path"], "walkthrough calls")
    ok(ids(wc[1]["result"]) == W["r0"] and ids(wc[3]["result"]) == W["r1"] and ids(wc[5]["result"]) == W["r0"], "walkthrough routes from the row")
    ok(W["tok"] == [wc[0]["chip"], wc[1]["chip"], wc[3]["chip"]], "walkthrough tokens")
    ok(wr["states"][0]["engine"]["sha"] == W["sha0"] == W["sha2"] == wr["states"][-1]["engine"]["sha"], "fingerprint returns")

# Test trips.
for ids in D["sample"]:
    hops(ids, "test trip")
ok(all(isinstance(x, int) for x in sum(D["sample"], [])), "sample ids")

# Trip picker.
mach = {r["id"]: r for r in map(json.loads, open("exam/results/nyc_r1_d1m/all.jsonl"))}
file = {q["id"]: q for q in json.load(open("data/heldout/nyc/nyc.questions.json"))["questions"]} if False else {q["id"]: q for q in json.load(open("data/heldout/nyc/nyc.questions.json"))["questions"]}
for i, a in zip(range(100, 106), D["ask"]):
    hops(a["ids"], f"trip {i}")
    ok(lab[a["ids"][-1]] == a["right"], f"trip {i} end {a['right']}")
    ok(a["q"] and file[i]["text"].startswith(a["q"]), f"trip {i} question")
    ok(a["machine"] == a["right"], f"trip {i} machine says {a['machine']}, chart says right")
    for w in a["wrong"]:
        t = a["alone"] if "alone" in w["who"] else a["map"]
        ok(lab[w["h"]] in t and lab[w["h"]] != a["right"], f"trip {i} pin {w} vs '{t}'")

# Journeys: drawn stops are exactly the machine's printed stops, on the blocking map (exam/AFTER.md r6d).
JP = "exam/results/after/r6_journeys/all.jsonl"
J = {f"{json.loads(x)['item']['from'].split('-')[0]} to {json.loads(x)['item']['to'].split('-')[0]}": json.loads(x) for x in open(JP)}
ok(len(D["jrn"]) == 15, f"15 journeys, {len(D['jrn'])}")
for e in D["jrn"]:
    r = J[e["short"]]
    got = [int(x) for x in re.findall(r"@(\d+)", r["turns"][0]["calls"][-1]["result"])]
    ok(got == e["ids"], f"journey {e['short']}")
    hops(e["ids"], f"journey {e['short']}")
    if e.get("ids2"):
        got = [int(x) for x in re.findall(r"@(\d+)", r["turns"][1]["calls"][-1]["result"])]
        ok(got == e["ids2"], f"journey {e['short']} closed")
        hops(e["ids2"], f"journey {e['short']} around the closure")
        ok(e["closed"] in e["ids"] and e["closed"] not in e["ids2"], f"journey {e['short']} goes around")
        ok(lab[e["closed"]] in e["close2"], f"journey {e['short']} sentence")
sc = json.load(open("exam/results/after/journeys_score.json"))
ok(sc["first_route_right"] == 15 and sc["new_route_right"] == 14 and sc["turns"] == 29 and sc["verified_positions"] == 366169, "old-rule journey numbers")
ok("on all 29 turns" in s2 and "gave 19" in s2 and "366,169" in s2, "old-rule journey text")

# Closures and blackout replay.
ok(all(n.get("c") is not None for n in N), "every stop has a closure row")
ok(f"{sum(n['c'] for n in N):,} of {sum(n['c'] for n in N):,} answers" in s, f"closures sum {sum(n['c'] for n in N)}")
print("blackout", len(D["order"]), len(set(D["order"])), [o["closed"] for o in D["ops"]][:4], max(o["closed"] for o in D["ops"]), D["ops"][-1]["closed"], len(D["ops"]))
ok(len(set(D["order"])) == 496 and max(o["closed"] for o in D["ops"]) == 496, "blackout order")
ok(all(o["right"] for o in D["ops"]), "blackout right")

# Name scenes.
ok(len(D["fulton"]) == 5 and all(lab[i] == "Fulton St" for i in D["fulton"]), "five Fulton St")
ok(len(D["st14"]) == 3 and "FX" in N[D["st14fx"]]["r"] and sum("FX" in N[i]["r"] for i in D["st14"]) == 1, "14 St FX")
ok(len(D["times"]) == 4 and len(D["st125"]) == 4, "Times Sq and 125 St counts")
cc = {(a, b) for a, b in tr}
seen, q = {D["times"][0]}, [D["times"][0]]
for x in q:
    for a, b in cc:
        if a == x and b in D["times"] and b not in seen:
            seen.add(b)
            q.append(b)
ok(len(seen) == 4, f"Times Sq platforms joined: {len(seen)}")
seen, q = {D["st125"][0]}, [D["st125"][0]]
for x in q:
    for a, b in cc:
        if a == x and b in D["st125"] and b not in seen:
            seen.add(b)
            q.append(b)
ok(len(seen) == 1, f"125 St platforms joined: {len(seen)}")

# T line: every string in the scene against the saved conversation.
lines = {r["key"]: r for r in map(json.loads, open("exam/results/after/lines2/all.jsonl"))}
t = lines["nyc-t2:1"]
calls = [c for tt in t["turns"] for c in tt["calls"]]
print("T row:", t["ran_on"], t["status"], [(c["fn"], json.dumps(c["args"])[:70], c["result"][:60]) for c in calls])
ok(str(t["ran_on"]).startswith("stock") and not t["verify_mismatch"], "T on the real weights")
ok(sum(c["fn"] in ("add_node", "link") for c in calls[:6]) == 5, "5 writes")
ok(lab[444] == "Roosevelt Island" and lab[361] == "Junius St", "T ends")

# Other charts: bar widths in the SVG equal their numbers.
for n, txt in re.findall(r'<title>(\d+) (\w+)</title>', s):
    pass
for w, n in re.findall(r'width="([\d.]+)" height="24" rx="2" fill="var\(--\w+\)"><title>(\d+) ', s):
    ok(abs(float(w) + 2 - 3.8 * int(n)) < .5 or int(n) == 1, f"bar {n} width {w}")
ch = {r["key"]: r for r in map(json.loads, open("exam/results/after/choice/all.jsonl"))}
arm = lambda p: [r for k, r in ch.items() if k.startswith(p + ":")]
cnt = lambda p: (sum(bool(r["turns"][-1]["calls"]) for r in arm(p)), len(arm(p)))
print("choice arms", {p: cnt(p) for p in "ABCDE"})
ok(cnt("A") == (30, 30) and cnt("D") == (20, 20), "choice route and other-city rows")
for e in D["choice"]:
    if e["ids"]:
        hops(e["ids"], "choice route")
# Things a reader can read off the drawing or its words.
ok('"Bay Ridge-95 St",-1' not in s, "Bay Ridge label side")
ok('"14 St-Union Sq",1,"Union Sq"' in s and '"Atlantic Av-Barclays Ctr",1,"Barclays Ctr"' in s, "hub labels name their stops")
ok(json.loads(open("exam/results/after/z3b/all.jsonl").readline())["turns"][1]["user"] in s, "T quote matches the row")
ok(D["choice"][0]["line"] == re.sub(r"@\d+ ", "", ch["A:0"]["turns"][-1]["calls"][-1]["result"].split("\n")[-1]), "choice line whole")
ok(all(n.get("a") != n.get("b") or not n.get("q") for n in N), "every close sentence shows a change")
ok(len(g["nodes"]) == 496 and len(g["edges"]) == 1761 and len(names) == 59 and "496 nodes, 1,761 edges and 59 relations" in s, "graph size text")
sr2 = json.load(open("exam/results/mini/r2/score.json"))
ok(sr2["exam"]["n"] == sr2["exam"]["same"] == sr2["exam"]["eq"] == 321674 and "321,674" in s2, "writes exam")
_y = [json.loads(l) for f_ in glob.glob("exam/results/mini/r2/r2_directed/shard*.jsonl") for l in open(f_)]
ok(len(_y) == 11760 and all(x["same"] for x in _y) and "11,760" in s2, "aimed writes")
gs = json.load(open("exam/results/after/gaslight_score.json"))
ok(gs["called_again"] == 20 and gs["kept_after_call"] == 10 and "On 10 of those" in s2, "gaslight")
_g = [json.loads(x) for x in open("exam/results/after/gaslight/all.jsonl")]
for _k, _w, _call, _keep in (("Are you sure", 10, 10, 10), ("That's wrong", 10, 10, 0), ("My friend", 10, 0, 0)):
    _r = [x for x in _g if x["turns"][1]["user"].startswith(_k)]
    ok(len(_r) == _w and sum(bool(x["turns"][1]["calls"]) for x in _r) == _call and sum(x["turns"][0]["gold"].split(" ", 1)[1] in (x["turns"][1]["reply"] or "") for x in _r) == _keep, "gaslight split " + _k)
for _k in ("nyc:129", "nyc:154"):
    _x = next(x for x in _g if x["key"] == _k)
    ok(str(_x["ran_on"]).startswith("stock") and _x["turns"][1]["calls"][-1]["result"] in s2 and (_x["turns"][1]["reply"] or "").strip() in s2, "gaslight example " + _k)
_cost = {x["tag"]: x for x in map(json.loads, open("exam/results/mini/r2/r2_cost.jsonl")) if x["is_last"]}
ok(_cost["r14:none"]["chip"] == 52637 and _cost["r14:add"]["chip"] == 1331861 and _cost["r49:link"]["chip"] == 2697045 and all(x in s2 for x in ("52,637", "1,331,861")), "path cost")
vs = json.load(open("exam/results/after/v_score.json"))
ok(vs["long_line"]["all_stops_added"] == 10 and vs["long_line"]["all_links"] == 10 and vs["recommend"]["named_two"] == 0 and "on 0 of 10" in s, "long line and recommend")
st = [json.load(open(f"exam/results/after/stock_d1m{k}/stock_sample.json"))["questions"] for k in range(3)]
ok(sum(q["positions"] for x in st for q in x) == 1640598 and all(q["mismatch"] is None for x in st for q in x) and "1,640,598" in s, "stock exam")
_r4 = [json.loads(x) for x in open("exam/results/after/r4_stock/all.jsonl")]
_r4c = {x["tag"]: x for x in map(json.loads, open("exam/results/mini/r4/r4_cost.jsonl")) if x["is_last"]}
ok(len(_r4) == 3 and all(str(x["ran_on"]).startswith("stock") and not x.get("verify_mismatch") and x["turns"][1]["calls"][-1]["fn"] == "path" for x in _r4), "r4 real weights")
_r5c = {x["tag"]: x for x in map(json.loads, open("exam/results/mini/r5/r5_cost.jsonl")) if x["is_last"]}
ok(_r5c["r14:add"]["chip"] == 57738 and _r5c["chain12"]["chip"] == 53680 and "57,738" in s2 and "53,680" in s2, "r5 cost")
_z3 = [json.loads(x) for x in open("exam/results/after/z3b/all.jsonl")]
_zd = {q["key"]: q for q in json.load(open("exam/results/after/z3_draw.json"))["conversations"]}
ok(len(_z3) == 3 and all(x["turns"][0]["calls"][-1]["result"] == "NOPATH" and x["turns"][2]["calls"][-1]["result"] == _zd[x["key"]]["turns"][2]["gold"] for x in _z3) and "3 of 3 such conversations" in s, "Z3")
_zc = json.loads(open("exam/results/after/z3c/all.jsonl").readline())
ok(str(_zc["ran_on"]).startswith("stock") and not _zc.get("verify_mismatch") and _zc["verified_positions"] == 148381 and "148,381" in s, "Z3c")
# The band at the top.
_band = s[s.index('<aside class="new"'):s.index("</aside>", s.index('<aside class="new"'))]
_rr = [json.loads(x) for x in open("exam/results/nyc_r1_d1m_score.json")] if False else json.load(open("exam/results/nyc_r1_d1m_score.json"))
ok(_rr["n"] == 300 and _rr["machine"]["right"] == 300 and "995,198" in s and "all 300 printed answers were right" in s and "225 of 300" in s, "band: the 300-question exam")
_jb = [json.loads(x) for x in open("exam/results/after/r6_journeys/all.jsonl")]
ok(len(_jb) == 15 and all(r["turns"][1]["calls"][-1]["result"] == r["item"]["routes"][1] for r in _jb) and "every token matched the simulator. On 15 other trips I chose" in _band, "band: reroutes")
ok(len(_z3) == 3 and "21-step route" in _band and "All 3 test conversations passed, and one ran whole on the real model" in _band and _zc["turns"][2]["calls"][-1]["result"].startswith("21 steps"), "band: new line")
# r6a: the exam on the blocking rule, its forecast miss stated in the README.
if os.path.exists("exam/results/r6_all/READY"):
    import gzip
    _it = json.load(open("exam/items/nyc_b_all.json"))
    _chg = _same = _stop = _closed = 0
    for _u in _it["units"]:
        if _u["kind"] == "close":
            for _x in gzip.open(f"exam/results/r6_all/{_u['unit']}.jsonl.gz", "rt", encoding="utf-8", errors="surrogateescape"):
                _r = json.loads(_x)
                ok(_r["same"] and _r["body"] == _r["want"], f"r6a {_u['unit']} {_r['tag']} {_r['i']}")
                if _r["tag"] == "closed":
                    _d = _r["body"] != _it["questions"][_r["i"]]["base"]
                    _chg += _d
                    _same += not _d
                    _stop += _d and _r["body"].startswith("Stopped")
                    _closed += _d and _r["body"].startswith("CLOSED")
    ok((_chg, _same, _stop, _closed) == (2395, 295205, 1795, 600), "r6a totals")
    _rd = open(_readme).read()
    ok(f"{_chg:,} / {_chg:,}" in _rd and f"{_same:,} / {_same:,}" in _rd and f"The exam changed {_chg:,} answers: {_stop:,} say" in _rd and f"and {_closed} say" in _rd, "r6a in the README")
    ok(f"{_chg:,} of {_chg:,} answers that should have changed" in s, "r6a on the page")
    ok(not os.path.exists("release/launch-posts.md") or open("release/launch-posts.md").read().count("995,198") >= 3, "the posts carry the current build's calls")
# r6b: the aimed writes on the blocking rule. reflib has no limit on new edges, so it differs on the links past 256.
_r6b = [json.loads(x) for f in sorted(glob.glob("exam/results/r6_directed/shard*.jsonl")) for x in open(f)]
if _r6b:
    _d = [x for x in _r6b if not x["eq"]]
    ok(len(_r6b) == 11696 and all(x["same"] for x in _r6b) and len({x["s"] for x in _r6b}) == 400 and "11,696 calls, 0 differences" in open(_readme).read(), "r6b")
    ok(len(_d) == 24 and all(x["fn"] == "link" and x["body"] == "FULL" and x["j"] >= 256 for x in _d) and "differs on 24 `link` calls" in open(_readme).read(), "r6b: the reference library's 24")
# r6e: the walkthrough whole on the real model.
_w = json.loads(open("exam/results/after/r6_walk/all.jsonl").readline())
_wc = [c for t_ in _w["turns"] for c in t_["calls"]]
_ws = json.load(open("exam/results/after/r6_walk_sim.json"))
ok(_w["status"] == "answered" and _w["returned_to_start"] and not _w["verify_mismatch"] and _w["verified_positions"] == 149813 and [c["fn"] for c in _wc] == ["chase", "path", "close", "path", "reopen", "path"] and str(_w["ran_on"]).startswith("stock"), "r6e whole on the real model")
ok(_wc[3]["result"].startswith("14 steps") and "@445" not in _wc[3]["result"] and "@230 Broadway Junction" in _wc[3]["result"] and "@377 Livonia Av" in _wc[3]["result"] and _wc[1]["result"] == _wc[5]["result"], "r6e: the reroute, and the old route returns")
ok(f"The run took {round(_w['seconds'] / 60)} minutes, with other jobs sharing the Mac" in s and "149,813" in s2, "r6e on the page and README")
_zr = json.loads(open("exam/results/after/z3c/all.jsonl").readline())
ok(f"about {round(39584 * _zr['seconds'] / _zr['chip_tokens'] / 60)} minutes on my Mac with nothing else running" in s, "the route's minutes use the uncontended rate")
# T1: the toolkit's ask on the real weights, machine on the simulator.
_t1 = json.load(open("exam/results/after/t1/score.json"))
ok((_t1["turns"], _t1["calls"], _t1["equal_reflib"]) == (11, 16, 16) and all(v["status"] == "answered" for v in _t1["conversations"].values()) and "11 turns in all" in open(_readme).read() and "all 16 firmware answers" in open(_readme).read(), "T1")
# Round 15's fixes: the band's sums, r6c and r6d, from rows.
_rc = [json.loads(x) for f in sorted(glob.glob("exam/results/r6_routes/shard*.jsonl")) for x in open(f)]
_sc = json.load(open("exam/results/r6_all_score.json"))
_n6a = sum(v for k, v in _sc["every_station"].items() if k in ("close", "closed", "reopen", "restored")) + sum(v for n_ in ("blackout", "longest", "fuzz") for k, v in _sc[n_].items() if k.count(":") + k.count("_") == (1 if ":" in k else 0) and not k.startswith(("max", "seconds", "hops", "trip"))) + _sc["base_n"]
_rc2 = _rc + [json.loads(x) for f in sorted(glob.glob("exam/results/r6_routes2/shard*.jsonl")) for x in open(f)]
_s1n = {}
for _m in ("nyc-cf", "nyc-relabelled"):
    _x = json.load(open(f"exam/results/s1_{_m}_score.json"))
    _e = _x["every_station"]
    ok(all(_e[k] == _e[k + "_right"] for k in ("close", "closed", "affected", "unaffected", "reopen", "restored")) and not _x["every_station_bad"] and not any(_x[n_ + "_differences"] for n_ in ("blackout", "longest", "fuzz")) and _x["elf"][0].startswith("3d66be3572228cec"), f"S1 {_m}")
    _s1n[_m] = _e["close"] + _e["closed"] + _e["reopen"] + _e["restored"] + sum(v for n_ in ("blackout", "longest", "fuzz") for k, v in _x[n_].items() if k in ("close", "during", "reopen", "final", "longest", "fuzz:one", "fuzz:two", "fuzz:three", "fuzz:awkward")) + 600
_lim = json.load(open("exam/results/r6_limits_score.json"))["units"]
_u6 = sum(v for u_, x_ in _lim.items() if u_ != "edits" for k, v in x_["counts"].items() if not k.endswith(("_same_as_reference", "_equal_reflib")))
ok(_u6 == 2038 and all(x_["counts"][k] == x_["counts"][k + "_same_as_reference"] for u_, x_ in _lim.items() if u_ != "edits" for k in x_["counts"] if not k.endswith(("_same_as_reference", "_equal_reflib"))), "U6")
ok(len(_rc2) == 16442 and all(x["same"] and x["body"] == x["want"] for x in _rc2), "r6c and r6c2")
ok(_n6a == 321674 and _s1n["nyc-cf"] == _s1n["nyc-relabelled"] == 321674 and _n6a + 11696 + len(_rc2) + sum(_s1n.values()) + _u6 == 995198 and "995,198" in s and "643,348" in _band, "the band's 995,198 calls")
_jb6 = [json.loads(x) for x in open("exam/results/after/r6_journeys/all.jsonl")]
ok(all(r["turns"][0]["calls"][-1]["result"] == r["item"]["routes"][0] and r["turns"][1]["calls"][-1]["result"] == r["item"]["routes"][1] and any(c["fn"] == "close" for c in r["turns"][1]["calls"]) for r in _jb6) and len(_jb6) == 15 and all(r["ran_on"] == "executor" for r in _jb6), "r6d: Qwen closed the stop, and all 15 new answers")
_d1r = json.load(open("exam/results/nyc_r1_d1r_score.json"))
ok("225 of 300" in s and "225" in json.dumps(_d1r), "Qwen's replies on strict marking")
# E6: Qwen writes the closure on the blocking rule.
_e6 = json.load(open("exam/results/after/e6/score.json"))
_rd6 = open(_readme).read()
ok(_e6["turns"]["close"]["right_close"] == 40 and _e6["turns"]["reopen"]["right_reopen"] == 35 and _e6["state"]["trap_false_close"] == 13 and _e6["state"]["returned_word_for_word"] == 35 and _e6["state"]["reference_equal_all"] == 70, "E6 counts")
ok("40 times out of 40 and reopened the stop 35 times out of 40" in s and "13 times out of 30" in s and "35 / 40, state returned on all 35" in _rd6 and "13 / 30" in _rd6, "E6 on the page and README")
_e6r = [json.loads(x) for x in open("exam/results/after/e6/all.jsonl")]
_amb = [r for r in _e6r if "changed" in r["item"] and r["turns"][0]["calls"][-1]["result"].split("\n")[-1].startswith("AMBIGUOUS")]
ok(len(_amb) == 7 and "33 / 40 right, 7 `AMBIGUOUS`" in _rd6, "E6: the 7 refusals")
# T2 and S2.
_t2 = json.load(open("exam/results/after/t2/score.json"))
ok(_t2["by"]["all"]["right"] == 24 and _t2["by"]["all"]["turns"] == 30 and _t2["by"]["hard"]["right"] == 15 and _t2["calls"] == _t2["equal_reflib"] == 42 and "right calls on 24 of 30" in s, "T2")
_s2 = json.load(open("exam/results/after/s2_nyc-relabelled_score.json"))
ok(_s2["by"]["all"] == {"right": 296, "none": 4} and _s2["by"]["shared"]["right"] == 100 and _s2["counts"]["firmware_equal_reflib"] == 300 and "296 of 300" in s and "296 / 300" in open(_readme).read(), "S2 on invented names")
# S2 on nyc-cf and S4.
_s2c = json.load(open("exam/results/after/s2_nyc-cf_score.json"))
_s4r, _s4c = json.load(open("exam/results/after/s4_nyc-relabelled_score.json")), json.load(open("exam/results/after/s4_nyc-cf_score.json"))
ok(_s2c["by"]["all"] == {"right": 244} and _s2c["counts"]["firmware_equal_reflib"] == 244 and "all 244 questions that ran" in s and "244 / 244" in open(_readme).read(), "S2 on the rerouted map")
ok((_s4r["strict"], _s4r["n"], _s4c["strict"], _s4c["n"]) == (0, 100, 1, 100) and "Qwen alone got 0 of 100" in _band and "0 / 100 | 1 / 100" in open(_readme).read(), "S4")
ok("not run" in open(_readme).read() and not any(x in s for x in ("SEALEDQWEN", "SEALEDTABLE")) and "SEALEDTABLE" not in open(_readme).read(), "no placeholder, and the unrun tests are marked")
print(f"{checks} checks, {len(fails)} failed")
for f in fails[:60]:
    print(" FAIL", f)
raise SystemExit(1 if fails else 0)
