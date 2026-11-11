"""The Phase D table under the measured factors. Arithmetic, no model. python3 phase_d.py

same-flow factor: S4, alternating, same tokens on 98 of 98: 5.80 against 21.53 tokens/s, shared GPU.
print-flow factor: S7, 10.0 s a question, same finals on 98 of 98, against 276.6 tokens a question at S4's slow 5.80 tokens/s = 47.7 s. Not alternated.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
b = json.load(open(os.path.join(HERE, "..", "d", "results", "budget.json")))
s4 = json.load(open(os.path.join(HERE, "results", "s4_replay.json")))["rounds"][:3]
sl = sum(r["slow"]["tokens"] for r in s4) / sum(r["slow"]["s"] for r in s4)
ba = sum(r["batched"]["tokens"] for r in s4) / sum(r["batched"]["s"] for r in s4)
s7 = json.load(open(os.path.join(HERE, "results", "s7_flow.json")))
same = ba / sl
slow_q = 27106 / 98 / sl
fast_q = s7["seconds"] / s7["n"]
pr = slow_q / fast_q
KIND = {"D1m": "print", "D1 chained": "same", "D2q": "print", "D3": "print", "D4q": "print", "Controls, merged": "print"}
rows = []
for r in b["qwen_rows"]:
    k = KIND.get(r["gate"], "host")
    f = pr if k == "print" else same
    rows.append({"gate": r["gate"], "old": r["hours"], "factor": round(f, 2), "basis": {"print": "measured on chain3's 98 chases", "same": "measured factor, chained flow itself not run", "host": "estimate: batching isn't built for base Qwen"}[k], "new": round(r["hours"] / f, 2)})
dropped = ("D3", "Host, D3 items")
t = {"same_flow_factor": round(same, 2), "print_flow_factor": round(pr, 2), "rows": rows, "old_total": round(sum(x["old"] for x in rows), 1), "new_total": round(sum(x["new"] for x in rows), 1),
     "old_without_D3": round(sum(x["old"] for x in rows if x["gate"] not in dropped), 1), "new_without_D3": round(sum(x["new"] for x in rows if x["gate"] not in dropped), 1), "same_tokens_only_total": round(sum(x["old"] for x in rows) / same, 1), "shared_gpu": True}
json.dump(t, open(os.path.join(HERE, "results", "phase_d.json"), "w"), indent=1)
print(json.dumps(t, indent=0))
