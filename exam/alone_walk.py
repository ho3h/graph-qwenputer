#!/usr/bin/env python3
"""exam/AFTER.md r6f: Qwen alone on the walkthrough's question, exam/alone.py's arm. python exam/alone_walk.py --out R.json"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "ctrl")]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()
a.out = os.path.abspath(a.out)
import flows as F  # noqa: E402  (chdirs to rvc)

Q = json.load(open(os.path.join(HERE, "results", "after", "r6_walk_draw.json")))["conversations"][0]["turns"][0]["user"]
qwen = F.Qwen(path=os.path.expanduser("~/Models/x210/Qwen3.5-4B"), attn="sdpa")
tok = qwen.tok
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
p = tok.apply_chat_template([{"role": "user", "content": Q}], add_generation_prompt=True, enable_thinking=False, tokenize=True)
prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
nxt, cache = qwen.forward(prompt, None)
out = []
for _ in range(40):
    if nxt in stops:
        break
    out.append(nxt)
    nxt, cache = qwen.forward([nxt], cache)
json.dump({"text": Q, "reply": tok.decode(out), "tokens": len(out)}, open(a.out, "w"), ensure_ascii=False)
print("alone walk finished", tok.decode(out), flush=True)
