#!/usr/bin/env python3
"""The cost, exactly. The same call through tok's firmware (tok.elf) and the cleaner firmware, on the reference machine, comparing chip tokens, instructions and echoed tokens. Every call Qwen wrote in t8/results/base, chain3 and chain4_fresh, and all dev graphs' first 20 questions of each. Writes results/count.json.
Calls that match exactly must differ by nothing. NONE that stays NONE and a name read: the exact added count, per form.
"""
import collections
import glob
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwb as W  # noqa: E402

M, X = W.M, W.X
reflib = M.reflib
CLEAN = W.build()
M.init_worker()
W.O.set_text(M.T)
W.patch_box(False)
real_build = lambda p: (lambda: p)


def box(elf, g):
    X.build_elf = real_build(elf)
    return X.Box(g, M.T)


def one(elf, g, ids, setup=()):
    b = box(elf, g)
    for s in setup:
        b.call(M.enc(s["fn"], s["args"]))
    return b.call(ids)


calls = collections.defaultdict(list)
for p in glob.glob(os.path.join(W.X210, "t8", "results", "base", "*.jsonl")):
    for ln in open(p):
        r = json.loads(ln)
        if r["call"] and "smoke" not in p:
            calls[r["graph"]].append(("t8 " + os.path.basename(p), r["call"]["text"], ()))
for p in (os.path.join(W.X210, "rvc", "results", "chain3", "all.jsonl"), os.path.join(W.X210, "rvc", "results", "chain4_fresh", "all.jsonl")):
    for ln in open(p):
        r = json.loads(ln)
        for c in r["calls"]:
            calls[r.get("graph", "").split("/")[-1]].append(("chain", c["text"], ()))
for p in sorted(glob.glob(os.path.join(W.X210, "data", "dev", "*", "*.questions.json"))):
    name = os.path.basename(p).split(".")[0]
    for x in json.load(open(p))["questions"][:20]:
        calls[name].append(("dev", X.template_text(x["call"]["fn"], x["call"]["args"]), tuple(x.get("setup") or ())))
calls.pop("", None)
cat = collections.defaultdict(lambda: {"calls": 0, "same_chip": 0, "same_records": 0, "same_echo_tokens": 0, "same_text": 0, "dchip": [], "drec": []})
bad = []
extra = []
wrong_words = []
for name, cs in sorted(calls.items()):
    sub = "cities" if name.startswith("c") else "random"
    g0 = json.load(open(os.path.join(W.X210, "data", "dev", sub, f"{name}.graph.json")))
    g1 = W.NOUN.with_noun(g0)
    try:
        b0, b1 = box(W.TOK_ELF, g0), box(CLEAN, g1)
    except M.B.BootLimit:
        continue
    G0, G1 = W._Graph(g0), W._Graph(g1)
    for src, text, setup in cs:
        ids = M.T.encode(text)
        if setup:
            r0, r1 = one(W.TOK_ELF, g0, ids, setup), one(CLEAN, g1, ids, setup)
            run0, run1 = None, None
        else:
            if any(x in text for x in ("<function=close", "<function=reopen", "<function=link", "<function=unlink")):
                b0, b1 = box(W.TOK_ELF, g0), box(CLEAN, g1)
            r0, r1 = b0.call(ids), b1.call(ids)
            run0, run1 = b0.ses.runs[-1], b1.ses.runs[-1]
        if r1.result.startswith("Stopped early") or "\nStopped early" in r1.result:
            kind = "limit_line_read_too" if "name read as" in r1.result else "limit_line"
            if kind == "limit_line" and reflib.reword(r0.result) != r1.result:
                wrong_words.append({"graph": name, "text": text, "result": [r0.result, r1.result]})
        elif r1.result == r0.result:
            kind = "same_answer"
            if "NONE " in r0.result[:5] or r0.result.startswith("leg ") and " NONE " in r0.result[:20]:
                kind = "stays_NONE"
        else:
            kind = "read_a_name"
        c = cat[kind]
        c["calls"] += 1
        c["same_chip"] += r0.chip == r1.chip
        c["same_records"] += r0.records == r1.records
        c["same_echo_tokens"] += run0 == run1
        c["same_text"] += r0.result == r1.result
        c["dchip"].append(r1.chip - r0.chip)
        if kind == "read_a_name":                                  # against the same call with the label as written, same firmware, same state
            read = r1.result.split("\n")[0].split(" ", 5)[-1]
            h = int(r1.result.split("\n")[0].split("@")[1].split()[0])
            t2 = text.replace(f"<parameter={'start' if '=start' in text else 'name'}>\n", "@@").split("@@")
            if len(t2) == 2:
                rest = t2[1].split("\n", 1)[1]
                b2 = box(CLEAN, g1)
                r2 = b2.call(M.T.encode(t2[0] + f"<parameter={'start' if '=start' in text else 'name'}>\n" + g1["nodes"][h]["label"] + "\n" + rest))
                extra.append((r1.chip - r2.chip, r1.records - r2.records, r1.result.split("\n", 1)[1] == r2.result))
        c["drec"].append(r1.records - r0.records)
        if kind == "same_answer" and run0 is not None and run0 != run1:
            wrong_words.append({"graph": name, "text": text, "printed tokens differ": True})
        if kind == "same_answer" and (r0.chip != r1.chip or r0.records != r1.records) and len(bad) < 50:
            bad.append({"graph": name, "text": text, "result": r0.result, "chip": [r0.chip, r1.chip], "records": [r0.records, r1.records], "source": src})
out = {}
for k, c in cat.items():
    d = c.pop("dchip")
    r = c.pop("drec")
    out[k] = dict(c, added_chip_min=min(d), added_chip_mean=round(st.mean(d), 1), added_chip_max=max(d), added_records_min=min(r), added_records_max=max(r))
out["read_against_exact_name"] = {"calls": len(extra), "same_result": sum(x[2] for x in extra), "added_chip_min": min(x[0] for x in extra), "added_chip_mean": round(st.mean(x[0] for x in extra), 1), "added_chip_max": max(x[0] for x in extra), "added_records_min": min(x[1] for x in extra), "added_records_max": max(x[1] for x in extra)}
out["exact_differences"] = bad
out["wrong_words"] = wrong_words[:50]
out["wrong_words_n"] = len(wrong_words)
out["elf"] = {"tok": W.TOK_ELF, "clean": CLEAN}
json.dump(out, open(os.path.join(HERE, "results", "count_writes.json" if W.WRITES else "count.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=0, ensure_ascii=False)[:2500])
sys.exit(1 if wrong_words else 0)
