#!/usr/bin/env python3
"""The edit arm's report, from saved rows only. No model. Writes results/edit_score.json and results/edit_transcripts.md."""
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(X210, "t8")]
import arms as A  # noqa: E402

reflib = A.reflib
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "edit")
rows = [json.loads(l) for l in open(os.path.join(D, "all.jsonl"))]
GOOD = {"both": Counter(), "close": Counter(), "reopen": Counter(), "plain": Counter()}
for _k in ("close moves the answer", "close leaves the answer", "close, name", "close, name station", "reopen, name", "reopen, name station"):
    GOOD[_k] = Counter()
state = Counter()
words = Counter()
trans = []


def node_of(call, g):
    a = call.get("args") or {}
    return str(a.get("node", ""))


for r in rows:
    conv = bool(r["item"].get("label"))
    x = r["item"].get("node")
    seen = set()
    r["turns"] = [t for t in r["turns"] if not (t["user"] in seen or seen.add(t["user"]))]      # a turn stopped at its cap was logged twice by the runner
    for ti, t in enumerate(r["turns"]):
        kind = ("close" if ti == 0 else "reopen") if conv else "plain"
        tally = [GOOD[kind]]
        if conv and ti == 0:
            tally.append(GOOD["close moves the answer" if r["item"]["changed"] else "close leaves the answer"])
        if conv and r["item"].get("form"):
            tally.append(GOOD[kind + (", name station" if r["item"]["form"] == "station" else ", name")])
        c = Counter()
        c["turns"] += 1
        writes = [k for k in t["calls"] if k["fn"] in ("close", "reopen", "link", "unlink")]
        chases = [k for k in t["calls"] if k["fn"] == "chase"]
        last = None
        if chases:
            _, last = reflib.split_reading(chases[-1]["result"])
        o = A.outcome(last, t["gold"])
        c[o] += 1
        want = t.get("wants")
        if want:
            right = [k for k in writes if k["fn"] == want[0] and re.search(rf"@{want[1]}\b", k["result"])]
            c["right_write"] += bool(right)
            c["right_write_before_chase"] += bool(right) and bool(chases) and t["calls"].index(right[0]) < t["calls"].index(chases[-1])
            c["wrong_or_extra_writes"] += len(writes) - len(right[:1])
            c["no_write"] += not writes
            c["both_right"] += o == "right" and bool(right)
        else:
            c["unasked_writes"] += len(writes)
            c["questions_with_unasked_write"] += bool(writes)
        c["calls"] += len(t["calls"])
        c["reply_given"] += bool(t.get("reply")) and t.get("ended") == "own stop"
        if t.get("reply"):
            lab = last.split(" ", 1)[1] if last and last.startswith("@") else None
            gl = t["gold"].split(" ", 1)[1] if t["gold"].startswith("@") else None
            c["reply_names_gold"] += bool(gl and gl in t["reply"])
        c["write_read_a_name"] += sum("name read as" in k["result"] for k in writes)
        for x_ in tally:
            x_.update(c)
    if conv:
        st = r["states"]
        state["conversations"] += 1
        state["reference_equal_all_reads"] += all(s["reference_equal"] for s in st)
        cl = [s for s in st if s["at"].split(": ", 1)[-1].startswith("close")]
        state["closed_once"] += len(cl) == 1
        if cl:
            ch = cl[0].get("changed", {})
            xw, xb = x // 32, x % 32
            good = set(ch) == {"n_closed", "closed_bits"} and len(ch["closed_bits"]) == 1 and ch["closed_bits"][0][0] == xw and ch["closed_bits"][0][1] ^ ch["closed_bits"][0][2] == 1 << xb and ch["n_closed"][0][2] - ch["n_closed"][0][1] == 1
            state["close_changes_only_that_bit"] += good
        ro = [s for s in st if s["at"].split(": ", 1)[-1].startswith("reopen")]
        if ro:
            state["reopen_called"] += 1
        state["returned_word_for_word"] += r["returned_to_start"]
        state["closed_and_reopened_and_returned"] += bool(cl) and bool(ro) and r["returned_to_start"]
    state["ran_on_" + r["ran_on"]] += 1
    state["status_" + r["status"]] += 1
    state["stock_equal_all"] += all(s.get("stock_equal", True) for s in r["states"]) and r["ran_on"].startswith("stock")
out = {"n": len(rows), "by_turn": {k: dict(v) for k, v in GOOD.items()}, "state": dict(state)}
json.dump(out, open(os.path.join(HERE, "results", "edit_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False))
with open(os.path.join(HERE, "results", "edit_transcripts.md"), "w") as f:
    f.write("# Qwen writes the edit: every conversation, whole\n\nEach block says which ran where. State is read back from the heads of the machine named.\n")
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
            f.write(f"- {s['at']}: n_closed {e['n_closed']}, closed {e['closed']}, n_add {e['n_add']}, n_dead {e['n_dead']}, sha {e['sha']}" + (f"; stock heads sha {s['stock']['sha']}" if "stock" in s else "") + f"; changed {list(s.get('changed', {}))}\n")
        f.write(f"\nReturned word for word: {r['returned_to_start']}\n")
