"""Criterion 3: decoding with the executor against a stock run on the same questions: Qwen's tokens, the machine's echoed tokens, each call's chip count, the final text, the status.

    python same_tokens.py --exec results/drive_exec/tiny.jsonl --stock ../rvc/results/m3_stock/tiny.jsonl --out results/same_tokens_tiny.json
"""
import argparse
import json


def load(p):
    return {json.loads(x)["id"]: json.loads(x) for x in open(p)}


ap = argparse.ArgumentParser()
ap.add_argument("--exec", required=True, dest="ex")
ap.add_argument("--stock", required=True)
ap.add_argument("--stock-label", default="stock")
ap.add_argument("--out", required=True)
a = ap.parse_args()
E, St = load(a.ex), load(a.stock)
rows = []
for i in sorted(set(E) & set(St)):
    e, s = E[i], St[i]
    same_seg = e["segments"] == s["segments"]
    first = None
    if not same_seg:
        for k, (x, y) in enumerate(zip(e["segments"], s["segments"])):
            if x != y:
                j = next((n for n, (p, q) in enumerate(zip(x["ids"], y["ids"])) if p != q), min(len(x["ids"]), len(y["ids"])))
                first = {"segment": k, "by": x["by"], "token": j}
                break
    rows.append({"id": i, "exec_on": e.get("ran_on"), "stock_on": s.get("ran_on", a.stock_label), "all_segments_identical": same_seg, "first_difference": first, "segments": len(e["segments"]), "tokens_in_segments": sum(len(x["ids"]) for x in e["segments"]),
                 "chip_tokens": [e["chip_tokens"], s["chip_tokens"]], "qwen_tokens": [e["qwen_tokens"], s["qwen_tokens"]], "echo_tokens": [e["echo_tokens"], s["echo_tokens"]], "same_chip_per_call": [c["chip"] for c in e["calls"]] == [c["chip"] for c in s["calls"]],
                 "same_final": e["final"] == s["final"], "same_status": e["status"] == s["status"], "lock_error": [e["lock_error"], s["lock_error"]], "head_mismatch": [e["head_mismatch"], s["head_mismatch"]], "seconds": [e["seconds"], s["seconds"]], "chip_seconds": [e["chip_seconds"], s["chip_seconds"]], "text_seconds": [e["text_seconds"], s["text_seconds"]],
                 "exec_chip_per_s": round(e["chip_tokens"] / max(e["chip_seconds"], 1e-9), 1), "stock_chip_per_s": round(s["chip_tokens"] / max(s["chip_seconds"], 1e-9), 1)})
res = {"compared": len(rows), "identical": sum(r["all_segments_identical"] and r["same_final"] and r["same_status"] and r["same_chip_per_call"] for r in rows), "stock_file": a.stock, "stock_label": a.stock_label, "rows": rows}
print(json.dumps(res, indent=0)[:3000])
json.dump(res, open(a.out, "w"), indent=1)
