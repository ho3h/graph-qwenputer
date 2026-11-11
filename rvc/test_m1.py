"""M1: the bridge firmware on bridge.Session / ref.Machine against reflib, byte for byte. Development; no gate.

    python test_m1.py [--workers 6] [--quick]       # run from the vendored folder, under tools/memguard.py

A check is one tool call: Qwen tokens go through <tool_call> .. </tool_call>, the run's echoed tokens are compared
byte for byte with the wrapping of SPEC 6 around the host tool's result. Every call has a 60 s alarm and a bound on
records; a hit counts as a mismatch. Expected TOOLONG (the capture window) is counted apart from matches.

Parts: dev (all data/dev questions, setups, labels), real (every call Qwen wrote in host/out transcripts, its own
token ids), random (cop's generator: adversarial names and arguments, one persistent state per graph), medium (150 to
1,024 nodes, closures and edits), limits, framing (malformed tool calls), capture (chase legs against the window),
fit (DROM, RAM and stack).
"""

import argparse
import glob
import json
import os
import random
import signal
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402

import reflib  # noqa: E402
import boot as B  # noqa: E402

DEV = os.path.join(X.X210, "data", "dev")
HOST_OUT = os.path.join(X.X210, "host", "out")
OUT = os.path.join(HERE, "results")
CALL_LIMIT_S = 60
T = None
HF = None


def init_worker():
    global T, HF
    from transformers import AutoTokenizer
    T = BR.Text(X.tokenizer_json())
    HF = AutoTokenizer.from_pretrained(X.MODEL)                      # the decode the host harness uses


class CallTimeout(Exception):
    pass


def _alarm(*_):
    raise CallTimeout(f"no answer within {CALL_LIMIT_S} s")


def limited(f, *a, **k):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(CALL_LIMIT_S)
    try:
        return f(*a, **k)
    finally:
        signal.alarm(0)


class Tally:
    def __init__(self, part):
        self.part = part
        self.checks = self.match = self.toolong = 0
        self.mism, self.notes = [], []
        self.by_fn = defaultdict(lambda: {"calls": 0, "chip": [], "echo": [], "records": [], "cap": []})
        self.max_cap, self.min_sp = 0, X.S.SP_INIT

    def run(self, box, G, ids, where, fn=None, record=None):
        """One call through both sides. `record`: the result text a transcript recorded, also compared."""
        text = HF.decode(ids, skip_special_tokens=False)
        try:
            want = limited(X.reference, G, text)
        except Exception as e:
            want = f"<reflib {type(e).__name__}: {e}>"
        expect_long = X.capture_rule(ids, T)
        if expect_long:
            want = X.TOOLONG
        self.checks += 1
        try:
            r = limited(box.call, ids)
        except Exception as e:
            self.mism.append({"where": where, "fn": fn, "text": text, "want": want, "got": f"<{type(e).__name__}: {e}>"})
            return None
        self.max_cap = max(self.max_cap, len(ids))
        self.min_sp = min(self.min_sp, getattr(box.m, "min_sp", X.S.SP_INIT))
        k = self.by_fn[fn or "?"]
        k["calls"] += 1
        k["chip"].append(r.chip)
        k["echo"].append(r.echo)
        k["records"].append(r.records)
        k["cap"].append(len(ids))
        if r.ok_wrap and r.result == want and (record is None or expect_long or want == record):
            if expect_long:
                self.toolong += 1
            else:
                self.match += 1
        else:
            self.mism.append({"where": where, "fn": fn, "text": text, "want": want, "got": r.result, "wrap": r.ok_wrap,
                              "recorded": record, "cap": len(ids)})
        return r

    def dump(self):
        by = {}
        for fn, k in self.by_fn.items():
            by[fn] = {"calls": k["calls"], "chip_total": sum(k["chip"]), "echo_total": sum(k["echo"]),
                      "records_total": sum(k["records"]), "chip_max": max(k["chip"]), "echo_max": max(k["echo"]),
                      "cap_max": max(k["cap"]), "cap_total": sum(k["cap"])}
        return {"part": self.part, "checks": self.checks, "match": self.match, "toolong": self.toolong,
                "mismatches": self.mism[:200], "n_mismatches": len(self.mism), "notes": self.notes, "by_fn": by,
                "max_cap": self.max_cap, "min_sp": self.min_sp}


def enc(fn, args):
    return T.encode(X.template_text(fn, args))


# ---------------------------------------------------------------------------------------------------------- dev
def task_dev(path):
    t = Tally("dev")
    gpath = path.replace(".questions.json", ".graph.json")
    g = json.load(open(gpath))
    base = os.path.basename(gpath)
    q = json.load(open(path))
    try:
        shared = X.Box(g, T, track=True)
    except B.BootLimit as e:
        t.notes.append({"does_not_fit": base, "why": str(e), "N": len(g["nodes"]), "E": len(g["edges"]),
                        "questions": len(q["questions"])})
        return t.dump()
    t.notes.append({"fits": base, "drom": shared.drom_bytes, "N": len(g["nodes"]), "E": len(g["edges"]), "R": len(g["relations"])})
    G0 = reflib.Graph(g)
    for x in q["questions"]:
        call = x["call"]
        fresh = bool(x.get("setup")) or call["fn"] in ("close", "reopen", "link", "unlink")
        if fresh:
            b, G = X.Box(g, T, track=True), reflib.Graph(g)
            for s in x.get("setup", []):
                t.run(b, G, enc(s["fn"], s["args"]), f"{base}#{x['id']} setup", s["fn"])
        else:
            b, G = shared, G0
        t.run(b, G, enc(call["fn"], call["args"]), f"{base}#{x['id']}", call["fn"])
    labels = sorted({n["label"] for n in g["nodes"]})
    if len(labels) > 200:
        labels = random.Random(0).sample(labels, 64)
    for lab in labels:
        t.run(shared, G0, enc("find", {"name": lab}), f"{base} label", "find")
    return t.dump()


# ------------------------------------------------------------------------------------------------------- real
def task_real(jpath):
    """Every call Qwen wrote in one host transcript file: its own ids, the question's setup, one state per question."""
    t = Tally("real")
    meta = json.load(open(os.path.join(os.path.dirname(jpath), "meta.json")))
    g = json.load(open(meta["graph"]))
    qs = {x["id"]: x for x in json.load(open(meta["questions"]))["questions"]}
    # dev1 ran on an older reflib (no "@h label"): its recorded results are not comparable, so only reflib decides there
    recorded_ok = "/dev1/" not in jpath
    for line in open(jpath):
        r = json.loads(line)
        b, G = X.Box(g, T, track=True), reflib.Graph(g)
        for s in qs[r["id"]].get("setup") or []:
            b.call(enc(s["fn"], s["args"]))
            G.call(s["fn"], s["args"])
        for i, c in enumerate(r["calls"]):
            if c.get("parse_error") and "no <tool_call>" in c["parse_error"]:
                t.notes.append({"no_tco_call": f"{jpath}#{r['id']}.{i}"})
            t.run(b, G, c["ids"], f"{os.path.relpath(jpath, HOST_OUT)}#{r['id']}.{i}", c["fn"],
                  record=c["result"] if recorded_ok else None)
    return t.dump()


# ------------------------------------------------------------------------------------------------------- random
def task_random(seed):
    import test_a1_dev as TA
    t = Tally("random")
    g = TA.rand_graph(seed)
    rng = random.Random(10_000 + seed)
    try:
        b, G = X.Box(g, T, track=True), reflib.Graph(g)
    except B.BootLimit as e:
        t.notes.append({"does_not_fit": g["name"], "why": str(e)})
        return t.dump()
    for i in range(80):
        fn, a = TA.rand_call(rng, g)
        ids = enc(fn, a)
        if 188 in ids:   # the NUL token ends the capture: known divergence, no generator produces it
            continue
        t.run(b, G, ids, f"rand{seed}#{i} {fn} {a!r}", fn)
    return t.dump()


def task_medium(seed):
    import test_a1_dev as TA
    t = Tally("medium")
    rng = random.Random(seed)
    g = TA.rand_graph(seed, n_lo=150, n_hi=1024, deg=rng.choice([1.1, 1.5, 3.0]))
    N = len(g["nodes"])
    try:
        b, G = X.Box(g, T, track=True), reflib.Graph(g)
    except B.BootLimit as e:
        t.notes.append({"does_not_fit": g["name"], "N": N, "E": len(g["edges"]), "why": str(e)})
        return t.dump()
    for i in range(24):
        if i in (8, 16):
            for _ in range(rng.randint(1, 6)):
                a = {"node": f"@{rng.randrange(N)}"}
                t.run(b, G, enc("close", a), f"med{seed} close", "close")
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
            a = {"start": f"@{rng.randrange(N)}", "legs": TA.rand_legs(rng, g)}
        elif fn == "neighbours":
            a = {"node": f"@{rng.randrange(N)}", "relation": rng.choice(g["relations"]),
                 "direction": rng.choice(["in", "out"])}
        else:
            a = {"from": f"@{rng.randrange(N)}", "to": f"@{rng.randrange(N)}"}
        t.run(b, G, enc(fn, a), f"med{seed}#{i}", fn)
    return t.dump()


# ------------------------------------------------------------------------------------------------------- limits
def g_of(N, edges, rels=("r",), splice=(), change=None, labels=None):
    return {"format": "x210-graph/1", "name": "lim", "domain": "test",
            "nodes": [{"label": labels[i] if labels else f"N{i}"} for i in range(N)], "relations": list(rels),
            "edges": sorted(map(list, edges)), "splice": list(splice), "change": change, "meta": {}}


def task_limits(_=None):
    t = Tally("limits")

    def cmp(where, g, calls):
        b, G = X.Box(g, T, track=True), reflib.Graph(g)
        for fn, a in calls:
            t.run(b, G, enc(fn, a), where, fn)
        return b, G

    # every result line of SPEC 3, on a graph with branching, a closed splice node, a change relation, label sharing
    g = g_of(9, [(0, 0, 1, 2), (1, 0, 2, 2), (2, 0, 3, 2), (2, 0, 4, 7), (3, 1, 5, 1), (5, 2, 6, 3), (6, 1, 7, 3),
                 (3, 1, 6, 1), (0, 1, 8, 65535), (8, 1, 7, 1)], rels=("a", "t", "b"), splice=("a",), change="t",
             labels=["Oak", "Elm", "Ash", "Fir", "Yew", "Oak", "Elm", "Bay", "Lone"])
    cmp("lines", g, [
        ("find", {"name": "Oak"}), ("find", {"name": "Ash"}), ("find", {"name": "Nope"}),
        ("find", {"name": "Oak", "has": "a"}), ("find", {"name": "Oak", "has": "zz"}),
        ("follow", {"node": "@0", "relation": "a", "steps": "1"}), ("follow", {"node": "@0", "relation": "a", "steps": "2"}),
        ("follow", {"node": "@0", "relation": "a", "steps": "3"}), ("follow", {"node": "@3", "relation": "a", "steps": "3"}),
        ("follow", {"node": "@0", "relation": "zz", "steps": "1"}), ("follow", {"node": "@0", "relation": "a", "steps": "0"}),
        ("follow", {"node": "@0", "relation": "a", "steps": "x"}), ("follow", {"node": "Oak", "relation": "a", "steps": "1"}),
        ("chase", {"start": "@0", "legs": "a 1"}), ("chase", {"start": "@0", "legs": "a 1; b 1"}),
        ("chase", {"start": "@3", "legs": "t 1; b 1"}), ("chase", {"start": "@1", "legs": "a 1; a 1; b 1"}),
        ("chase", {"start": "@7", "legs": "a 1"}), ("chase", {"start": "@7", "legs": "b 1; a 1"}),
        ("chase", {"start": "@0", "legs": "nosep"}), ("chase", {"start": "@0", "legs": ""}),
        ("neighbours", {"node": "@2", "relation": "a"}), ("neighbours", {"node": "@2", "relation": "a", "direction": "in"}),
        ("neighbours", {"node": "@7", "relation": "a"}), ("neighbours", {"node": "@2", "relation": "a", "direction": "both"}),
        ("path", {"from": "@0", "to": "@7"}), ("path", {"from": "@7", "to": "@0"}), ("path", {"from": "@0", "to": "@0"}),
        ("cheapest", {"from": "@0", "to": "@7"}), ("cheapest", {"from": "@7", "to": "@0"}),
        ("close", {"node": "@1"}), ("close", {"node": "@1"}), ("find", {"name": "@1"}),
        ("follow", {"node": "@1", "relation": "a", "steps": "1"}), ("follow", {"node": "@0", "relation": "a", "steps": "1"}),
        ("cheapest", {"from": "@0", "to": "@2"}), ("path", {"from": "@0", "to": "@2"}), ("reopen", {"node": "@1"}),
        ("reopen", {"node": "@1"}), ("reopen", {"node": "Oak"}), ("reopen", {"node": "Nope"}),
        ("link", {"from": "@7", "relation": "a", "to": "@0", "weight": "9"}),
        ("link", {"from": "@7", "relation": "a", "to": "@0"}), ("link", {"from": "@7", "relation": "a", "to": "@0", "weight": "x"}),
        ("link", {"from": "@7", "relation": "a", "to": "@1", "weight": "65536"}),
        ("unlink", {"from": "@7", "relation": "a", "to": "@0"}), ("unlink", {"from": "@7", "relation": "a", "to": "@0"}),
        ("nofn", {"a": "b"}), ("path", {"to": "@1"}), ("close", {"node": "@1", "extra": "1"}),
    ])
    # OVERFLOW, step bounds, leg bounds (within what the window can carry), hubs and hash collisions
    g = g_of(6, [(0, 0, 1, 40000), (1, 0, 2, 25535), (2, 0, 3, 1), (0, 1, 4, 65535), (4, 1, 5, 0), (5, 1, 0, 3)],
             rels=("a", "b"), change="b")
    cmp("bounds", g, [("cheapest", {"from": "@0", "to": "@2"}), ("cheapest", {"from": "@0", "to": "@3"}),
                      ("cheapest", {"from": "@0", "to": "@5"}), ("cheapest", {"from": "@4", "to": "@3"}),
                      ("follow", {"node": "@0", "relation": "b", "steps": "255"}),
                      ("follow", {"node": "@0", "relation": "b", "steps": "256"}),
                      ("chase", {"start": "@0", "legs": "; ".join(["b 1"] * 8)}),
                      ("chase", {"start": "@0", "legs": "; ".join(["b 1"] * 16)}),
                      ("chase", {"start": "@0", "legs": "; ".join(["b 1"] * 17)}),
                      ("chase", {"start": "@0", "legs": "a 1; a 1; a 1"})])
    K = 1000
    cmp("hub", g_of(K + 2, [(0, 0, i, 1) for i in range(1, K + 1)] + [(i, 0, K + 1, 1) for i in range(1, K + 1)]),
        [("path", {"from": "@0", "to": f"@{K + 1}"}), ("cheapest", {"from": "@0", "to": f"@{K + 1}"}),
         ("follow", {"node": "@0", "relation": "r", "steps": "1"}), ("close", {"node": "@5"}),
         ("path", {"from": "@0", "to": f"@{K + 1}"})])
    cmp("hubsplice", g_of(5, [(0, 0, 1, 1), (1, 0, 2, 1), (1, 0, 3, 1), (2, 0, 4, 1), (3, 0, 4, 1)], splice=("r",)),
        [("close", {"node": "@1"}), ("neighbours", {"node": "@0", "relation": "r"}),
         ("follow", {"node": "@0", "relation": "r", "steps": "1"}), ("cheapest", {"from": "@0", "to": "@4"}),
         ("path", {"from": "@0", "to": "@4"})])
    # the same 12-bit hash bucket
    byh = defaultdict(list)
    for i in range(30000):
        byh[B.ghash(f"n{i}".encode())].append(f"n{i}")
    col = max(byh.values(), key=len)[:5]
    cmp("collide", g_of(5, [], labels=col), [("find", {"name": s}) for s in col] + [("find", {"name": "n"})])
    # FULL: the software image's overlay holds 256 added edges; reflib has no such bound (a known divergence in cop/DEVLOG)
    g = g_of(40, [])
    b, G = X.Box(g, T, track=True), reflib.Graph(g)
    added, full_at = 0, None
    for x in range(40):
        for y in range(40):
            a = {"from": f"@{x}", "relation": "r", "to": f"@{y}"}
            r = limited(b.call, enc("link", a))
            if r.result == "FULL":
                full_at = added
                break
            added += 1
            want = G.call("link", a)
            t.checks += 1
            if r.result == want:
                t.match += 1
            else:
                t.mism.append({"where": "overlay", "want": want, "got": r.result})
        if full_at is not None:
            break
    t.notes.append({"overlay_FULL_after_added_edges": full_at})
    # boot limits of the image: what cop/boot.py refuses
    for what, gg in (("N1024", g_of(1024, [])), ("N1025", g_of(1025, [])), ("label64", g_of(2, [], labels=["x" * 64, "y"])),
                     ("label65", g_of(2, [], labels=["x" * 65, "y"])), ("labelNFD", g_of(2, [], labels=["Café", "y"])),
                     ("R64", g_of(2, [], rels=tuple(f"r{i}" for i in range(64)))),
                     ("R65", g_of(2, [], rels=tuple(f"r{i}" for i in range(65))))):
        try:
            d = X.Box(gg, T).drom_bytes
            t.notes.append({"boot": what, "accepted_drom": d})
        except Exception as e:
            t.notes.append({"boot": what, "refused": f"{type(e).__name__}: {e}"[:90]})
    return t.dump()


# ------------------------------------------------------------------------------------------------------ framing
def task_framing(_=None):
    """Malformed and unusual tool-call text: the firmware's parser against host/tools.py parse_call."""
    t = Tally("framing")
    g = g_of(4, [(0, 0, 1, 1), (1, 0, 2, 1), (2, 0, 3, 1)], labels=["Oak", "Elm", "Ash", "a<b>c"])
    cases = [
        "", "\n", "no function here", "<function=path>", "<function=path>\n</function>\n",
        "<function=>\n</function>\n", "<function=find\n>", "<function=find", "x<function=find>\n<parameter=name>\nOak\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name>\nOak\n</parameter>\n",                 # no </function>
        "<function=find>\n<parameter=name>\nOak\n",                                # no </parameter>
        "<function=find>\n<parameter=name>Oak</parameter>\n</function>\n",         # no template newlines
        "<function=find>\n<parameter=name>\n\nOak\n\n</parameter>\n</function>\n", # two newlines
        "<function=find>\n<parameter=name>\n\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name>\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name></parameter>\n</function>\n",
        "<function=find>\n<parameter=>\nOak\n</parameter>\n</function>\n",          # empty parameter name
        "<function=find>\n<parameter=name\n>\nOak\n</parameter>\n</function>\n",   # newline in the name
        "<function=find>\n<parameter=name>\nOak\n</parameter>\n<parameter=name>\nElm\n</parameter>\n</function>\n",  # repeated
        "<function=find>\n<parameter=nope>\nOak\n</parameter>\n</function>\n",
        "<function=path>\n<parameter=from>\n@0\n</parameter>\n<parameter=frm>\n@1\n</parameter>\n<parameter=to>\n@3\n</parameter>\n</function>\n",
        "<function=path>\n<parameter=frm>\n@0\n</parameter>\n<parameter=to>\n@3\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name>\nOak\n</function>\n<parameter=name>\nElm\n</parameter>\n",
        "<function=find>\n</function>\n<parameter=name>\nOak\n</parameter>\n",
        "<function=find>\n<parameter=name>\na<b>c\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name>\n<parameter=name>\nOak\n</parameter>\n</function>\n",
        "<function=path><function=find>\n<parameter=name>\nOak\n</parameter>\n</function>\n",
        "<function=find>\n<parameter=name>\nOak\n</parameter>\ntrailing words\n</function>\n",
        "<function=find>\n<parameter=name>\nOak\n</parameter></function>",
        "  <function=find>\n<parameter=name>\nOak\n</parameter>\n</function>",
    ]
    for c in cases:
        b, G = X.Box(g, T, track=True), reflib.Graph(g)
        t.run(b, G, T.encode(c), f"framing {c!r}", "framing")
    # a real tool call whose tokens exceed one row, or the window
    b, G = X.Box(g, T, track=True), reflib.Graph(g)
    for name, s in (("16-byte token", "----------------"), ("17+ byte token", "--------------------------------"),
                    ("long arg", "Oak " * 60)):
        t.run(b, G, T.encode(X.template_text("find", {"name": s})), f"row {name}", "framing")
    return t.dump()


# ------------------------------------------------------------------------------------------------------ capture
def task_capture(_=None):
    """Tokens of a call as legs grow, on real relation names of the dev cities and short ones."""
    out = {}
    rng = random.Random(1)
    g = json.load(open(os.path.join(DEV, "cities", "c024.graph.json")))
    routes = [r for r in g["relations"] if r != g.get("change")]
    gs = g_of(3, [(0, 0, 1, 1), (1, 0, 0, 1)], rels=("r",))
    for name, gg, rels in (("c024 relations", g, routes), ("one-letter relation", gs, ["r"])):
        rows = []
        for n in range(1, 17):
            samples = []
            for _ in range(20):
                legs = "; ".join(f"{rng.choice(rels)} {rng.randint(1, 9)}" for _ in range(n))
                ids = T.encode(X.template_text("chase", {"start": "@123", "legs": legs}))
                samples.append(len(ids))
            rows.append({"legs": n, "tokens_min": min(samples), "tokens_max": max(samples), "fits_all": max(samples) <= 80,
                         "fits_any": min(samples) <= 80})
            b, G = X.Box(gg, T), reflib.Graph(gg)
            r = b.call(ids)
            rows[-1]["last_result"] = r.result[:60]
        out[name] = rows
    return {"part": "capture", "capture": out}


# ---------------------------------------------------------------------------------------------------------- fit
def task_fit(_=None):
    """The image's capacity: exact DROM bytes for a graph of (N, E, mean label bytes, R), real boots at the edge."""
    prog = X.elf.program(X.build_elf())
    res = {"part": "fit", "rom_words": len(prog.text), "rom_bytes": 4 * len(prog.text), "rodata_bytes": len(prog.rodata),
           "ram_image_bytes": len(prog.data) + prog.data_base, "drom_limit": B.DROM_SIZE, "boot_off": B.BOOT_OFF}

    def edges(N, E, R=4):
        rng, seen, out = random.Random(N * 100_003 + E), set(), []
        for _ in range(20 * E + 1000):                            # bounded: small N may not hold E distinct triples
            if len(out) == E:
                return out
            a, b, r = rng.randrange(N), rng.randrange(N), rng.randrange(R)
            if (a, r, b) not in seen:
                seen.add((a, r, b))
                out.append([a, r, b, 1])
        raise RuntimeError(f"no {E} distinct edges on {N} nodes")

    def size(N, E, lab=16, R=4):
        g = g_of(N, edges(N, E, R), rels=tuple(f"line {i}" for i in range(R)),
                 labels=[("%0*d" % (lab, i))[:lab] for i in range(N)])
        try:
            _, drom = B.boot(g, prog.rodata, software=True)
            return len(drom)
        except B.BootLimit as e:
            return str(e)

    res["sizes"] = [{"N": N, "E": E, "label_bytes": 16, "R": 4, "drom": size(N, E)}
                    for N, E in ((500, 1800), (1024, 2000), (1024, 4000), (1024, 6000), (1024, 7000), (1024, 7400), (1024, 7500),
                                 (2000, 4000))]
    # the largest E per N that boots, at 16-byte labels and R = 4
    frontier = []
    for N in (64, 128, 256, 512, 768, 1024):
        lo, hi = 0, 11000
        while hi - lo > 1:
            m = (lo + hi) // 2
            if isinstance(size(N, m), int):
                lo = m
            else:
                hi = m
        frontier.append({"N": N, "max_E": lo, "drom_at_max": size(N, lo)})
    res["frontier_label16_R4"] = frontier
    # run calls at the edge: the largest graph, real calls equal reflib
    N, E = 1024, frontier[-1]["max_E"]
    g = g_of(N, edges(N, E), rels=tuple(f"line {i}" for i in range(4)), labels=[("%0*d" % (16, i))[:16] for i in range(N)])
    b, G = X.Box(g, T, track=True), reflib.Graph(g)
    t = Tally("edge")
    for fn, a in (("path", {"from": "@0", "to": "@1023"}), ("cheapest", {"from": "@0", "to": "@1023"}),
                  ("neighbours", {"node": "@7", "relation": "line 3"}), ("find", {"name": "0000000000001023"}),
                  ("close", {"node": "@9"}), ("path", {"from": "@0", "to": "@1023"}), ("cheapest", {"from": "@0", "to": "@1023"})):
        t.run(b, G, enc(fn, a), f"edge {fn}", fn)
    res["edge"] = t.dump()
    return res


# ------------------------------------------------------------------------------------------------------- driver
def real_files():
    out = []
    for run in ("dev1", "dev2", "dev2-repeat", "dev3-clear"):
        for f in sorted(glob.glob(os.path.join(HOST_OUT, run, "*", "*.jsonl"))):
            if os.path.exists(os.path.join(os.path.dirname(f), "meta.json")):
                out.append(f)
    return out


def guard(paths):
    assert not any("heldout" in p for p in paths)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--parts", default="dev,real,random,medium,limits,framing,capture,fit")
    a = ap.parse_args()
    parts = a.parts.split(",")
    os.makedirs(OUT, exist_ok=True)
    q = guard(sorted(glob.glob(os.path.join(DEV, "*", "*.questions.json"))))
    r = guard(real_files())
    jobs = []
    if "limits" in parts:
        jobs.append((task_limits, None))
    if "framing" in parts:
        jobs.append((task_framing, None))
    if "capture" in parts:
        jobs.append((task_capture, None))
    if "fit" in parts:
        jobs.append((task_fit, None))
    if "real" in parts:
        jobs += [(task_real, p) for p in (r[:1] if a.quick else r)]
    if "dev" in parts:
        jobs += [(task_dev, p) for p in (q[:4] if a.quick else q)]
    if "random" in parts:
        jobs += [(task_random, s) for s in range(4 if a.quick else 300)]
    if "medium" in parts:
        jobs += [(task_medium, s) for s in range(1 if a.quick else 16)]
    t0 = time.time()
    results = []
    with get_context("spawn").Pool(a.workers, initializer=init_worker, maxtasksperchild=40) as pool:
        for i, res in enumerate(pool.imap_unordered(call_job, jobs)):
            results.append(res)
            print(f"{time.time() - t0:.0f}s {i + 1}/{len(jobs)} {res['part']} checks={res.get('checks')} "
                  f"bad={res.get('n_mismatches')}", flush=True)
    summary = summarize(results)
    summary["seconds"] = round(time.time() - t0, 1)
    tag = "quick" if a.quick else ("full" if len(parts) == 8 else "+".join(parts))
    path = os.path.join(OUT, f"m1_{tag}.json")
    json.dump({"summary": summary, "results": results}, open(path, "w"), indent=0, ensure_ascii=False)
    json.dump(summary, open(path.replace(".json", ".summary.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:6000])


def call_job(j):
    f, x = j
    try:
        return f(x)
    except Exception as e:
        import traceback
        return {"part": f.__name__, "checks": 1, "match": 0, "toolong": 0, "n_mismatches": 1,
                "mismatches": [{"where": repr(x), "crash": traceback.format_exc()[-1500:]}], "notes": [], "by_fn": {},
                "max_cap": 0, "min_sp": X.S.SP_INIT, "crash": str(e)}


def summarize(results):
    by = defaultdict(lambda: {"jobs": 0, "checks": 0, "match": 0, "toolong": 0, "mismatches": 0, "max_cap": 0})
    fn = defaultdict(lambda: defaultdict(int))
    notes, min_sp = [], X.S.SP_INIT
    extra = {}
    for r in results:
        if r["part"] in ("capture", "fit"):
            extra[r["part"]] = r
            if r["part"] == "fit":
                min_sp = min(min_sp, r["edge"]["min_sp"])
            continue
        p = by[r["part"]]
        p["jobs"] += 1
        p["checks"] += r["checks"]
        p["match"] += r["match"]
        p["toolong"] += r["toolong"]
        p["mismatches"] += r["n_mismatches"]
        p["max_cap"] = max(p["max_cap"], r["max_cap"])
        min_sp = min(min_sp, r["min_sp"])
        notes += [dict(n, part=r["part"]) for n in r["notes"]]
        for f, k in r["by_fn"].items():
            for x, v in k.items():
                fn[f"{r['part']}/{f}"][x] = max(fn[f"{r['part']}/{f}"][x], v) if x.endswith("_max") else fn[f"{r['part']}/{f}"][x] + v
    tokens = {}
    for f, k in fn.items():
        tokens[f] = {"calls": k["calls"], "chip_mean": round(k["chip_total"] / k["calls"], 1), "chip_max": k["chip_max"],
                     "echo_mean": round(k["echo_total"] / k["calls"], 1), "echo_max": k["echo_max"],
                     "instr_mean": round(k["records_total"] / k["calls"], 1), "cap_mean": round(k["cap_total"] / k["calls"], 1),
                     "cap_max": k["cap_max"]}
    fits = [n for n in notes if "fits" in n]
    no = [n for n in notes if "does_not_fit" in n]
    return {"parts": dict(by), "min_sp": hex(min_sp), "tokens_per_call": tokens,
            "graphs_fit": len(fits), "graphs_not_fit": no, "drom_max_fit": max((n["drom"] for n in fits), default=0),
            "notes": [n for n in notes if "fits" not in n and "does_not_fit" not in n], "capture": extra.get("capture"),
            "fit": {k: v for k, v in (extra.get("fit") or {}).items()}}


if __name__ == "__main__":
    main()
