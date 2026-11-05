#!/usr/bin/env python3
"""Same-tokens proofs for fast.py. Standard library only; it compares saved records and writes speed/proofs.json. No model.

    prove.py pairs-t6 OUT.json                  question list from tok's finished T6 records
    prove.py pairs-draw FILE N OFFSET OUT.json  from a draw file ({'draw': [...]}), N questions from OFFSET
    prove.py compare FAST_DIR[,..] --ref DIR[,..] | --ref-t6 | --ref-chain3 | --ref-chain4 [--first-lines] [--add NAME] --out RESULT.json

--first-lines: the fast flow has flags on, so compare only each call both have, and the final line.
--add writes a proof entry, only if every question is the same and each fast run's stock sample passed (or --stock-from names runs that did).
"""
import argparse, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
T6 = {"tiny": "tiny", "c024": "cities/c024", "c025": "cities/c025", "r001": "random/r001"}


def recs(dirs):
    out = {}
    for d in dirs:
        for ln in open(os.path.join(d, "all.jsonl")):
            r = json.loads(ln)
            out[(r["tag"][0], r["tag"][1])] = r
    return out


def ref_t6():
    out = {}
    for p in glob.glob(os.path.join(X210, "tok", "results", "t6", "*.jsonl")):
        name = T6[os.path.basename(p)[:-6]]
        for ln in open(p):
            r = json.loads(ln)
            out[(name, r["id"])] = r
    return out


def ref_file(path):
    out = {}
    for ln in open(path):
        r = json.loads(ln)
        out[(r["graph"], r["id"])] = r
    return out


def same(a, b, first_lines):
    d = {"ids": all(x["ids"] == y["ids"] for x, y in zip(a["calls"], b["calls"])), "lines": all(x.get("result") == y.get("result") for x, y in zip(a["calls"], b["calls"])), "responses": all(x.get("response_ids") == y.get("response_ids") for x, y in zip(a["calls"], b["calls"])), "final": a["final"] == b["final"], "correct": a["correct"] == b["correct"]}
    if not first_lines:
        d.update(n_calls=len(a["calls"]) == len(b["calls"]), status=a["status"] == b["status"], qwen=a["qwen_tokens"] == b["qwen_tokens"], echo=a["echo_tokens"] == b["echo_tokens"], chip=a["chip_tokens"] == b["chip_tokens"])
        if "segments" in a and "segments" in b:
            d["segments"] = a["segments"] == b["segments"]
        if "no_call_text" in a and "no_call_text" in b:
            d["prose"] = a["no_call_text"] == b["no_call_text"]
    return d


def main():
    cmd = sys.argv[1]
    if cmd == "pairs-t6":
        json.dump([list(k) for k in ref_t6()], open(sys.argv[2], "w"))
        return print(len(ref_t6()))
    if cmd == "pairs-draw":
        q = json.load(open(sys.argv[2]))
        d = q["draw"] if isinstance(q, dict) else q
        n, o = int(sys.argv[3]), int(sys.argv[4])
        return json.dump(d[o:o + n], open(sys.argv[5], "w"))
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("fast")
    ap.add_argument("--ref")
    ap.add_argument("--ref-t6", action="store_true")
    ap.add_argument("--ref-chain3", action="store_true")
    ap.add_argument("--ref-chain4", action="store_true")
    ap.add_argument("--first-lines", action="store_true")
    ap.add_argument("--add")
    ap.add_argument("--stock-from")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dirs = a.fast.split(",")
    F = recs(dirs)
    R = ref_t6() if a.ref_t6 else ref_file(os.path.join(X210, "rvc/results/chain3/all.jsonl")) if a.ref_chain3 else ref_file(os.path.join(X210, "rvc/results/chain4_fresh/all.jsonl")) if a.ref_chain4 else recs(a.ref.split(","))
    rows = []
    for k, r in F.items():
        if k in R:
            d = same(R[k], r, a.first_lines)
            rows.append({"key": k, "same": all(d.values()), "differ": [x for x, v in d.items() if not v]})
    meta = [json.load(open(os.path.join(d, "meta.json"))) for d in dirs]
    keys = {m["flow_key"] for m in meta}
    shas = {m["firmware_sha256"] for m in meta}
    assert len(keys) == 1 and len(shas) == 1, (keys, shas)
    stock = [m.get("stock_sample") for m in ([json.load(open(os.path.join(d, "meta.json"))) for d in a.stock_from.split(",")] if a.stock_from else meta) if m.get("stock_sample")]
    sp = sum(s["positions"] for s in stock)
    st_ok = bool(stock) and all(s["passed"] for s in stock)
    tokens = sum(m["stats"].get("row_steps", 0) for m in meta)
    secs = sum(m["stats"]["seconds"] for m in meta)
    res = {"flow": keys.pop(), "elf_sha256": shas.pop(), "machine": meta[0]["machine"], "questions_compared": len(rows), "same": sum(r["same"] for r in rows), "differ": [r for r in rows if not r["same"]], "fast_seconds": round(secs, 1), "gpu_text_steps": tokens, "stock_questions": sum(len(s["questions"]) for s in stock), "stock_positions": sp, "stock_passed": st_ok, "reference": a.ref or ("t6" if a.ref_t6 else "chain3" if a.ref_chain3 else "chain4_fresh"), "first_lines_only": a.first_lines, "shared_gpu": True}
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "differ"}), [r["key"] for r in res["differ"]][:10])
    if a.add:
        if not rows or res["same"] != len(rows) or not st_ok:
            sys.exit("no proof entry: not all the same, or no passing stock sample")
        p = os.path.join(HERE, "proofs.json")
        t = json.load(open(p)) if os.path.exists(p) else []
        t = [e for e in t if not (e["elf_sha256"] == res["elf_sha256"] and e["flow"] == res["flow"])]
        t.append({"elf_sha256": res["elf_sha256"], "flow": res["flow"], "machine": res["machine"], "name": a.add, "questions": len(rows), "reference": res["reference"], "stock_questions": res["stock_questions"], "stock_positions": sp, "result": os.path.relpath(a.out, HERE)})
        json.dump(t, open(p, "w"), indent=1)
        print("proof added")


main()
