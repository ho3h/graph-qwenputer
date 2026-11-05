#!/usr/bin/env python3
"""exam/AFTER.md B: Qwen alone, no tool, no machine, no map. T8_R1=1 for the new 100.

    python exam/alone.py --out R.jsonl --deadline-s S
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "ctrl")]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--deadline-s", type=float, required=True)
a = ap.parse_args()
a.out = os.path.abspath(a.out)
import d1m  # noqa: E402
import flows as F  # noqa: E402  (chdirs to rvc)

if os.environ.get("ALONE_MAP"):                                     # exam/AFTER.md S4: the first 100 of S2's draw, from the map's own file
    qs = [q for q in d1m.draw(os.environ["ALONE_MAP"], 200)[0] if int(q["id"]) < 900000][:100]
    assert len(qs) == 100
else:
    Q = json.load(open(d1m.base_of("nyc") + ".questions.json"))["questions"]
    qs = sorted(Q, key=lambda q: q["id"]) + [q for q in d1m.draw("nyc", 200)[0] if int(q["id"]) >= 900000]
    assert len(qs) == 600 and len({str(q["id"]) for q in qs}) == 600
qwen = F.Qwen(path=os.path.expanduser("~/Models/x210/Qwen3.5-4B"), attn="sdpa")
tok = qwen.tok
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
t00 = time.time()
done = {json.loads(x)["id"] for x in open(a.out)} if os.path.exists(a.out) else set()
with open(a.out, "a", encoding="utf-8", buffering=1) as f:
    for q in qs:
        if q["id"] in done:
            continue
        if time.time() - t00 > a.deadline_s:
            print("DEADLINE", flush=True)
            sys.exit(3)
        p = tok.apply_chat_template([{"role": "user", "content": q["text"]}], add_generation_prompt=True, enable_thinking=False, tokenize=True)
        prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
        nxt, cache = qwen.forward(prompt, None)
        out = []
        for _ in range(40):
            if nxt in stops:
                break
            out.append(nxt)
            nxt, cache = qwen.forward([nxt], cache)
        f.write(json.dumps({"id": q["id"], "text": q["text"], "gold_text": q["answer_text"], "source": "file" if int(q["id"]) < 900000 else "generated" if int(q["id"]) < 910000 else "shared", "final": tok.decode(out, skip_special_tokens=True)}, ensure_ascii=False) + "\n")
print("alone finished", time.time() - t00, flush=True)
