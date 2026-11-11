"""The M3 sample against the host baseline and against the byte-delivery control, question by question."""
import json
import os

import compare as C

def L(p):
    return C.load(p)

GR = ("tiny", "c024", "c025", "r001")
res, rows = {}, []
circ, ctrl, host = {}, {}, {}
for g in GR:
    circ.update({(g, i): r for i, r in L(f"results/m3_compact/{g}.jsonl").items()})
    ctrl.update({(g, i): r for i, r in L(f"results/wrapctl_bytes/{g}.jsonl").items()})
    host.update({(g, i): r for i, r in L(f"../host/out/dev2/{g}/sdpa.jsonl").items()})
keys = sorted(circ)
res["n"] = len(keys)
res["merged"] = C.acc([circ[k] for k in keys])
res["control_bytes_on_same"] = C.acc([ctrl[k] for k in keys])
res["host_on_same"] = C.acc([host[k] for k in keys])
res["merged_vs_control"] = C.summary([(g, i, circ[g, i], ctrl[g, i]) for g, i in keys])
res["merged_vs_host"] = C.summary([(g, i, circ[g, i], host[g, i]) for g, i in keys])
m = dict(chip=0, echo=0, qwen=0, chip_s=0.0, text_s=0.0, calls=0, same_as_reflib=0, lock=0, head=0, own_ok=0, seconds=0.0, max_cap=0)
for k in keys:
    r = circ[k]
    m["chip"] += r["chip_tokens"]; m["echo"] += r["echo_tokens"]; m["qwen"] += r["qwen_tokens"]
    m["chip_s"] += r["chip_seconds"]; m["text_s"] += r["text_seconds"]; m["seconds"] += r["seconds"]
    m["lock"] += r["lock_error"] is not None; m["head"] += r["head_mismatch"]; m["own_ok"] += r["own_ok"]
    for c in r["calls"]:
        m["calls"] += 1; m["same_as_reflib"] += c["same_as_host"]; m["max_cap"] = max(m["max_cap"], c["cap"])
    rows.append({"q": k, "merged": [r["status"], r["n_calls"], r["correct"]], "control": [ctrl[k]["status"], ctrl[k]["n_calls"], ctrl[k]["correct"]],
                 "host": [host[k]["status"], host[k]["n_calls"], host[k]["correct"]],
                 "same_calls_as_control": C.seq(r) == C.seq(ctrl[k]), "same_calls_as_host": C.seq(r) == C.seq(host[k])})
m["chip_per_s"] = round(m["chip"] / m["chip_s"], 2)
m["text_per_s"] = round((m["qwen"] + m["echo"]) / m["text_s"], 2)
res["machine"], res["rows"] = m, rows
json.dump(res, open("results/m3_sample_compare.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: res[k] for k in res if k != "rows"}, indent=0, ensure_ascii=False)[:3500])
for r in rows:
    print(r)
