"""Item 4: the one-tool flow on the reference machine. What a chase costs when the response is only the final node line, and how
long a query fits the 80-token capture.

    python fw/oneline.py        # writes results/oneline.json

Builds: rvc (today), fw (this pass), and each with -DFW_ONELINE (main prints the result and nothing around it; HALT's echo ends
the line). fw_off_line is fw/graphlib.c with every pass off, so its one-line figure is today's firmware without the wrapper.
Part real: Qwen's own calls from rb/results/printout_one and printout_one_retry. Part legs: generated chases that walk, by leg
count, checked against reflib. Part window: tokens of a call on every dev city's relations. Never reads data/heldout. Finite.
"""

import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwbox as F  # noqa: E402

X, BR, S = F.X, F.BR, F.S
sys.path.insert(0, os.path.join(F.X210, "lib"))
import reflib  # noqa: E402

GRAPHS = {"tiny": "host/test/tiny", "c024": "data/dev/cities/c024", "c025": "data/dev/cities/c025", "r001": "data/dev/random/r001"}
RB = os.path.join(F.X210, "rb", "results")
OFF = ["-DFW_NO_PARSE", "-DFW_NO_PUT", "-DFW_NO_LEGS", "-DFW_NO_CHEAPEST"]
RVC = os.path.join(F.X210, "rvc", "graphlib.c")
FW = os.path.join(HERE, "graphlib.c")
BUILDS = [("rvc", RVC, []), ("fw", FW, []), ("fw_off", FW, OFF), ("fw_off_line", FW, OFF + ["-DFW_ONELINE"]), ("fw_line", FW, ["-DFW_ONELINE"])]


def load(name):
    p = os.path.join(F.X210, GRAPHS[name])
    assert "heldout" not in p
    return json.load(open(p + ".graph.json")), json.load(open(p + ".questions.json"))["questions"]


def body_of(r, line):
    if not line:
        return r.result
    raw = r.raw.decode("utf-8", "surrogateescape")
    assert raw.endswith("\n"), repr(raw)
    return raw[:-1]


def mean(v):
    return round(sum(v) / max(len(v), 1), 1)


def part_real(T, name, src, extra):
    """Each question's first clean flow, the calls exactly as saved (text re-encoded: the file keeps text, the tokens are the template's)."""
    F.set_firmware(name, src, extra)
    line = "-DFW_ONELINE" in extra
    out = {"first_call_chip": [], "first_call_echo": [], "calls": 0, "mismatch": 0, "cap": [], "all_chip": [], "all_echo": []}
    for arm in ("printout_one", "printout_one_retry"):
        for g_name in GRAPHS:
            g, qs = load(g_name)
            byid = {q["id"]: q for q in qs}
            path = os.path.join(RB, arm, f"{g_name}.jsonl")
            for ln in open(path):
                rec = json.loads(ln)
                b, G = X.Box(g, T), reflib.Graph(g)
                for s in byid[rec["id"]].get("setup") or []:
                    b.call(T.encode(X.template_text(s["fn"], s["args"])))
                    G.call(s["fn"], s["args"])
                for i, c in enumerate(rec["calls"]):
                    ids = c.get("ids") or T.encode(c["text"])
                    r = b.call(ids)
                    want = X.reference(G, c["text"])
                    if X.capture_rule(ids, T):
                        want = X.TOOLONG
                    out["mismatch"] += body_of(r, line) != want
                    out["calls"] += 1
                    out["cap"].append(len(ids))
                    out["all_chip"].append(r.chip)
                    out["all_echo"].append(r.echo)
                    if i == 0:
                        out["first_call_chip"].append(r.chip)
                        out["first_call_echo"].append(r.echo)
    return {"calls": out["calls"], "questions": len(out["first_call_chip"]), "mismatches": out["mismatch"], "cap_mean": mean(out["cap"]), "cap_max": max(out["cap"]),
            "chip_mean": mean(out["all_chip"]), "chip_max": max(out["all_chip"]), "echo_mean": mean(out["all_echo"]),
            "first_call_chip_mean": mean(out["first_call_chip"]), "first_call_echo_mean": mean(out["first_call_echo"])}


def walks(g, nlegs, rng, count=12):
    """Chases of nlegs legs that reach a node on this graph, grown one leg at a time and checked by reflib (fixed bounds)."""
    G = reflib.Graph(g)
    N = len(g["nodes"])
    rels = [r for r in g["relations"] if r != g.get("change")]
    out = []
    for _ in range(3000):
        if len(out) == count:
            break
        s, legs = rng.randrange(N), []
        for _ in range(nlegs):
            for _ in range(60):
                cand = f"{rng.choice(rels)} {rng.randint(1, 3)}"
                if G.call("chase", {"start": f"@{s}", "legs": "; ".join(legs + [cand])}).startswith("@"):
                    legs.append(cand)
                    break
            else:
                break
        if len(legs) == nlegs:
            out.append({"start": f"@{s}", "legs": "; ".join(legs)})
    return out


def part_legs(T):
    g, _ = load("c024")
    rows = []
    sets = {n: walks(g, n, random.Random(100 + n)) for n in (1, 2, 3, 4, 5, 6, 7)}
    for name, src, extra in BUILDS:
        F.set_firmware(name, src, extra)
        line = "-DFW_ONELINE" in extra
        for n, calls in sets.items():
            ch, ec, cap, bad, longc = [], [], [], 0, 0
            b, G = X.Box(g, T), reflib.Graph(g)
            for a in calls:
                ids = T.encode(X.template_text("chase", a))
                r = b.call(ids)
                want = G.call("chase", a)
                if X.capture_rule(ids, T):
                    want = X.TOOLONG
                    longc += 1
                bad += body_of(r, line) != want
                ch.append(r.chip)
                ec.append(r.echo)
                cap.append(len(ids))
            rows.append({"build": name, "legs": n, "calls": len(calls), "cap_mean": mean(cap), "cap_max": max(cap) if cap else None, "chip_mean": mean(ch), "echo_mean": mean(ec), "toolong": longc, "mismatches": bad})
    return rows


def part_window(T):
    res = {"template_two_params_empty": len(T.encode(X.template_text("chase", {"start": "", "legs": ""})))}
    names = sorted(glob.glob(os.path.join(F.X210, "data", "dev", "cities", "*.graph.json")))
    per_city, per_leg = [], []
    rng = random.Random(7)
    worst = 0
    fit4, tot4 = 0, 0
    room = []
    label_tokens = []
    for p in names:
        assert "heldout" not in p
        g = json.load(open(p))
        rels = [r for r in g["relations"] if r != g.get("change")]
        toks_by_legs = {}
        for n in (1, 2, 3, 4, 5, 6, 7, 8):
            v = []
            for _ in range(40):
                legs = "; ".join(f"{rng.choice(rels)} {rng.randint(1, 9)}" for _ in range(n))
                v.append(len(T.encode(X.template_text("chase", {"start": "@123", "legs": legs}))))
            toks_by_legs[n] = v
        for x in toks_by_legs[4]:
            tot4 += 1
            fit4 += x <= 80
            room.append(80 - x)
            worst = max(worst, x)
        labs = [len(T.encode(n["label"])) for n in g["nodes"]]
        label_tokens.append(max(labs))
        per_city.append({"city": os.path.basename(p)[:4], "relations": len(rels), **{f"legs{n}_max": max(v) for n, v in toks_by_legs.items()}, "label_tokens_max": max(labs)})
        for n, v in toks_by_legs.items():
            per_leg.append((n, min(v), max(v)))
    res["four_legs_handle_start"] = {"calls": tot4, "fit": fit4, "tokens_max": worst, "room_min": min(room), "room_mean": mean(room)}
    res["label_tokens_max_over_cities"] = max(label_tokens)
    res["legs_summary"] = {n: {"min": min(a for m, a, _ in per_leg if m == n), "max": max(b for m, _, b in per_leg if m == n)} for n in (1, 2, 3, 4, 5, 6, 7, 8)}
    res["per_city"] = per_city
    # SPEC section 2's own example relation names, and one-letter names, by legs
    for key, rel in (("spec_style_A_northbound", "A northbound"), ("one_letter", "r"), ("spec_style_1_southbound", "1 southbound")):
        rows = {}
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            legs = "; ".join(f"{rel} {1 + i % 9}" for i in range(n))
            rows[n] = len(T.encode(X.template_text("chase", {"start": "@123", "legs": legs})))
        res[key] = rows
    for start in ("@123", "@123 Times Sq-42 St", "Times Sq-42 St", "Van Cortlandt Park-242 St"):
        res.setdefault("start_forms_tokens", {})[start] = len(T.encode(start))
    return res


def main():
    T = BR.Text(X.tokenizer_json())
    res = {"real": {}, "window": part_window(T)}
    print(json.dumps({k: v for k, v in res["window"].items() if k != "per_city"}), flush=True)
    for name, src, extra in BUILDS:
        res["real"][name] = part_real(T, name, src, extra)
        print(name, res["real"][name], flush=True)
    res["legs"] = part_legs(T)
    for r in res["legs"]:
        print(r, flush=True)
    json.dump(res, open(os.path.join(HERE, "results", "oneline.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
