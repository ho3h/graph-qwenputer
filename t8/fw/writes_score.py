#!/usr/bin/env python3
"""The report on Qwen working out the edit, from saved rows only. No model. Writes results/writes_score.json and results/writes_transcripts.md."""
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(X210, "t8")]
import arms as A  # noqa: E402

rows = [json.loads(l) for l in open(os.path.join(HERE, "results", sys.argv[1] if len(sys.argv) > 1 else "writes", "all.jsonl"))]
T = {k: Counter() for k in ("close", "close, answer moves", "close, answer stays", "reopen", "trap")}
S = Counter()
wordings = {}
bad = []
for r in rows:
    it = r["item"]
    conv = "changed" in it
    x = it["node"]
    for ti, t in enumerate(r["turns"]):
        kinds = (["close", "close, answer moves" if it["changed"] else "close, answer stays"] if ti == 0 else ["reopen"]) if conv else ["trap"]
        c = Counter()
        c["turns"] += 1
        lines = [l for k in t["calls"] for l in (k.get("result") or "").split("\n")]
        last = (t["calls"][-1].get("result") or "").split("\n")[-1] if t["calls"] else None
        o = A.outcome(last, t["gold"])
        c[o] += 1
        closes = [l for l in lines if l.startswith("closed @")]
        reopens = [l for l in lines if l.startswith("reopened @")]
        refusals = [l for l in lines if l.startswith("not closed @") or l.startswith("already closed @")]
        rightc = [l for l in closes if l.startswith(f"closed @{x} ")]
        rightr = [l for l in reopens if l.startswith(f"reopened @{x} ")]
        c["closes"] += len(closes)
        c["reopens"] += len(reopens)
        c["not_closed_or_already"] += len(refusals)
        c["right_close"] += bool(rightc)
        c["right_reopen"] += bool(rightr)
        c["other_node_written"] += len(closes) - len(rightc) + len(reopens) - len(rightr)
        c["name_read"] += sum(l.startswith("name read as") for l in lines)
        c["toolong"] += sum(l == "TOOLONG" for l in lines)
        c["calls"] += len(t["calls"])
        c["reply_given"] += bool(t.get("reply")) and t.get("ended") == "own stop"
        gl = t["gold"].split(" ", 1)[1] if t["gold"].startswith("@") else None
        c["reply_names_gold"] += bool(gl and t.get("reply") and gl in t["reply"])
        for k in kinds:
            T[k].update(c)
        w = it.get("wording") if (not conv or ti == 0) else it.get("reopen_wording")
        d = wordings.setdefault(w, Counter())
        d["n"] += 1
        d["wrote"] += bool(rightc) if ti == 0 or not conv else bool(rightr)
        if not conv:
            d["wrote"] += 0
    st = r["states"]
    S["status_" + r["status"]] += 1
    S["ran_on_" + r["ran_on"]] += 1
    S["reference_equal_all"] += all(s["reference_equal"] for s in st)
    S["stock_equal_all"] += r["ran_on"].startswith("stock") and all(s.get("stock_equal") for s in st)
    for s in st[1:]:
        ch = s.get("changed", {})
        if "closed\": \"" in s["at"] or '"closed":' in s["at"]:
            pass
    if conv:
        S["conversations"] += 1
        wrote_c = [s for s in st[1:] if s.get("changed", {}).get("n_closed") and s["changed"]["n_closed"][0][2] > s["changed"]["n_closed"][0][1]]
        wrote_r = [s for s in st[1:] if s.get("changed", {}).get("n_closed") and s["changed"]["n_closed"][0][2] < s["changed"]["n_closed"][0][1]]
        S["closed_state_changed"] += bool(wrote_c)
        S["reopened_state_changed"] += bool(wrote_r)
        for s in wrote_c:
            ch = s["changed"]
            xw, xb = x // 32, x % 32
            good = set(ch) == {"n_closed", "closed_bits"} and len(ch["closed_bits"]) == 1 and ch["closed_bits"][0][0] == xw and ch["closed_bits"][0][1] ^ ch["closed_bits"][0][2] == 1 << xb
            S["close_changed_only_that_bit"] += good
            if not good:
                bad.append({"key": r["key"], "changed": ch})
        S["closed_and_reopened"] += bool(wrote_c) and bool(wrote_r)
        S["closed_and_reopened_and_returned"] += bool(wrote_c) and bool(wrote_r) and r["returned_to_start"]
        S["returned_word_for_word"] += r["returned_to_start"]
    else:
        S["traps"] += 1
        S["trap_state_changed"] += not r["returned_to_start"]
        S["trap_false_close"] += any(l.startswith("closed @") for t in r["turns"] for k in t["calls"] for l in (k.get("result") or "").split("\n"))
out = {"n": len(rows), "turns": {k: dict(v) for k, v in T.items()}, "state": dict(S), "by_wording": {str(k): dict(v) for k, v in wordings.items()}, "state_not_only_that_bit": bad}
json.dump(out, open(os.path.join(HERE, "results", "writes_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if k != "by_wording"}, ensure_ascii=False))
with open(os.path.join(HERE, "results", "writes_transcripts.md"), "w") as f:
    f.write("# Qwen works out the edit: every conversation, whole\n\nEach block says which ran where. State is read back from the heads named. Worked turns in the prompt aren't shown; they're in `edit.py`.\n")
    for r in rows:
        f.write(f"\n## {r['key']} ({r['ran_on']}; {r['status']})\n")
        for t in r["turns"]:
            f.write(f"\n**User:** {t['user']}\n\n")
            for k in t["calls"]:
                f.write(f"**Qwen calls** `{k['fn']} {json.dumps(k['args'], ensure_ascii=False)}`\n\n**Machine:** `{json.dumps(k['result'], ensure_ascii=False)}`\n\n")
            f.write(f"**Qwen:** {t.get('reply')}\n\nRight answer: `{t['gold']}`\n")
        f.write("\n**State read from the heads:**\n")
        for s in r["states"]:
            e = s["engine"]
            f.write(f"- {s['at']}: n_closed {e['n_closed']}, closed {e['closed']}, sha {e['sha']}" + (f"; stock heads sha {s['stock']['sha']}" if "stock" in s else "") + f"; changed {list(s.get('changed', {}))}\n")
        f.write(f"\nReturned word for word: {r['returned_to_start']}\n")
