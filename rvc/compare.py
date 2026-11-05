"""M3 comparison: the circuit's transcripts (results/m3/) against the host baseline's (host/out/dev2/).

    python compare.py results/m3 --host ../host/out/dev2 --attn sdpa --out results/m3_compare.json

Agreement is on what Qwen wrote: the tool responses cannot be token-identical, because the circuit prints bytes. A
question agrees when every Qwen segment is token-identical. The eager/sdpa pair of the host baseline is measured the
same way, as the floor to read this against.
"""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

GRAPHS = ("tiny", "c024", "c025", "r001")


def load(path):
    return {json.loads(line)["id"]: json.loads(line) for line in open(path)} if os.path.exists(path) else {}


def qwen_segs(r):
    return [s["ids"] for s in r["segments"] if s["by"] == "qwen"]


def agree(a, b):
    """Token-identical Qwen segments, and where they first differ (segment index, token index, generated tokens before)."""
    sa, sb = qwen_segs(a), qwen_segs(b)
    gen = 0
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            j = next((k for k, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
            return False, {"segment": i, "token": j, "generated_before": gen + j}
        gen += len(x)
    if len(sa) != len(sb):
        return False, {"segment": min(len(sa), len(sb)), "token": 0, "generated_before": gen}
    return True, None


def seq(r):
    return [(c["fn"], json.dumps(c["args"], sort_keys=True, ensure_ascii=False)) for c in r["calls"]]


def summary(pairs):
    """pairs: list of (graph, id, a, b)."""
    t = Counter()
    diffs = []
    for g, i, a, b in pairs:
        t["n"] += 1
        same, where = agree(a, b)
        t["identical_qwen_tokens"] += same
        t["same_calls"] += seq(a) == seq(b)
        t["same_final"] += a["final"] == b["final"]
        t["same_score"] += a["correct"] == b["correct"]
        t["same_status"] += a["status"] == b["status"]
        if not same:
            diffs.append({"graph": g, "id": i, **where, "a_correct": a["correct"], "b_correct": b["correct"],
                          "a_status": a["status"], "b_status": b["status"], "a_calls": a["n_calls"], "b_calls": b["n_calls"]})
    return dict(t), diffs


def acc(rs):
    scored = [r for r in rs if r["correct"] is not None]
    by = {}
    for r in scored:
        k = by.setdefault(r["kind"], [0, 0])
        k[0] += bool(r["correct"])
        k[1] += 1
    return {"n": len(rs), "scored": len(scored), "correct": sum(bool(r["correct"]) for r in scored),
            "by_kind": by, "status": dict(Counter(r["status"] for r in rs)), "calls": sum(r["n_calls"] for r in rs),
            "fns": dict(Counter(c["fn"] for r in rs for c in r["calls"]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--host", default="../host/out/dev2")
    ap.add_argument("--attn", default="sdpa")
    ap.add_argument("--out")
    a = ap.parse_args()
    a.host = str(Path(a.host).resolve())
    run, host = Path(a.run), Path(a.host)
    circ, base, other = {}, {}, {}
    for g in GRAPHS:
        for i, r in load(run / f"{g}.jsonl").items():
            circ[g, i] = r
        base.update({(g, i): r for i, r in load(host / g / f"{a.attn}.jsonl").items()})
        other.update({(g, i): r for i, r in load(host / g / "eager.jsonl").items()})
    keys = [k for k in base if k in circ]
    pairs = [(g, i, circ[g, i], base[g, i]) for g, i in keys]
    floor = [(g, i, other[g, i], base[g, i]) for g, i in keys if (g, i) in other]
    m = Counter()
    bad_calls, wrap = [], Counter()
    for k in keys:
        r = circ[k]
        if "lock_error" not in r:                         # wrap_control.py's records: no machine ran
            continue
        m["lock_errors"] += r["lock_error"] is not None
        m["head_mismatch"] += r["head_mismatch"]
        m["own_ok"] += r["own_ok"]
        m["chip_tokens"] += r["chip_tokens"]
        m["echo_tokens"] += r["echo_tokens"]
        m["qwen_tokens"] += r["qwen_tokens"]
        m["chip_seconds"] += r["chip_seconds"]
        m["text_seconds"] += r["text_seconds"]
        m["seconds"] += r["seconds"]
        for c in r["calls"]:
            m["calls"] += 1
            m["calls_same_as_reflib"] += c["same_as_host"]
            m["calls_unwrapped"] += not c["wrapped"]
            m["max_cap"] = max(m["max_cap"], c["cap"])
            if not c["same_as_host"]:
                bad_calls.append({"q": k, "text": c["text"], "machine": c["result"], "host": c["host_result"]})
    ch = Counter()
    for k in keys:
        for c, h in zip(circ[k]["calls"], base[k]["calls"]):
            ch["paired_calls"] += 1
            ch["same_call_text"] += c["text"] == h["text"]
            ch["same_result"] += c["result"] == h["result"]
            ch["host_response_tokens"] += len(h["response_ids"])
            ch["circuit_response_tokens"] += len(c["response_ids"])
    res = {"n_compared": len(keys), "circuit": acc([circ[k] for k in keys]), "host": acc([base[k] for k in keys]),
           "host_other_attn": acc([other[k] for k in keys if k in other]), "machine": dict(m), "calls_not_equal_reflib": bad_calls[:50],
           "agreement": summary(pairs)[0], "floor_eager_vs_sdpa": summary(floor)[0], "first_diffs": summary(pairs)[1],
           "paired_calls": dict(ch)}
    print(json.dumps({k: v for k, v in res.items() if k != "first_diffs"}, indent=1, ensure_ascii=False))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
