#!/usr/bin/env python3
"""exam/AFTER.md N: Qwen given the map, the same push. python exam/gaslight_map.py OUT DEADLINE"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "ctrl")]
out, lim = os.path.abspath(sys.argv[1]), float(sys.argv[2])
ASK = " Answer with the station name only."
COT = " Before answering, list each stop you pass, numbered, one per line. Then give the final line as 'Answer: <station name>'."
maps = {q["id"]: q["map_list"] for q in json.load(open(os.path.join(X210, "..", "X2.7", "chases.json")))["questions"]}
draw = json.load(open(os.path.join(HERE, "results", "after", "gaslight_draw.json")))["conversations"]
import flows as FL

qwen = FL.Qwen(path=os.path.expanduser("~/Models/x210/Qwen3.5-4B"), attn="sdpa")
tok = qwen.tok
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}


def say(msgs, cap):
    p = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, tokenize=True)
    ids = [int(v) for v in (p if isinstance(p, list) else p["input_ids"])]
    nxt, cache = qwen.forward(ids, None)
    o = []
    while len(o) < cap and nxt not in stops:
        o.append(nxt)
        nxt, cache = qwen.forward([nxt], cache)
    del cache
    FL.torch.mps.empty_cache()
    return tok.decode(o, skip_special_tokens=True)


t0 = time.time()
with open(out, "a", buffering=1) as f:
    for c in draw:
        if time.time() - t0 > lim:
            print("DEADLINE", flush=True)
            break
        u1 = maps[c["orig"]] + "\n\n" + c["turns"][0]["user"].replace(ASK, COT)
        a1 = say([{"role": "user", "content": u1}], 1024)
        a2 = say([{"role": "user", "content": u1}, {"role": "assistant", "content": a1}, {"role": "user", "content": c["turns"][1]["user"]}], 200)
        f.write(json.dumps({"key": c["key"], "right": c["right"], "wrong": c["wrong"], "first": a1.rsplit("Answer:", 1)[-1].strip()[:100], "second": a2.strip()[:200]}, ensure_ascii=False) + "\n")
print("gaslight map finished", flush=True)
