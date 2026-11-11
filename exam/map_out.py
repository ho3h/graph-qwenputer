#!/usr/bin/env python3
"""exam/AFTER.md M. T8_R1=1 T8_WRITES=1 T8_NOUN=on python t8/fw/tokrun.py ../exam/map_out.py"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "speed"), os.path.join(X210, "t8", "fw"), os.path.join(X210, "rvc")]
OUT = os.path.join(HERE, "results", "after", "map_out")
os.makedirs(OUT, exist_ok=True)
import d1m
import fast

fast.setup("writes")
g = fast.g
gr = g.graph_fn(json.load(open(d1m.base_of("nyc") + ".graph.json")))
ctx = fast.load_stock()
ec = ctx.ec
chat = ec.chat
T, torch = chat.T, g.torch
from chipformer.rv import hf

q = "Flooding has closed Bowling Green. Start at High St station. Ride the A train 1 stop northbound, then change to the 5 and ride the 5 train 3 stops southbound. One stop means the next station. At which station are you now? Answer with the station name only."
prompt = chat.prompt_ids([{"role": "system", "content": g.HT.system_prompt(gr) + g.C2.EXTRA + g.C2.TOLD}] + g.worked.HISTORY + [{"role": "user", "content": q}], tools=g.worked.TOOLS)
args = {"start": "High St", "legs": "A northbound 1; 5 southbound 3", "closed": "Bowling Green"}
m0, stream, own, ses = g.D.session_for(chat, gr, prompt, [("chase", args)], None)
image = bytes(m0.drom)
slots = hf.head_slots(chat.c)
r_ = chat.c.target.value_heads // chat.c.target.key_heads
names = {chat.c.nodes[ni].name: (L, j) for ni, (L, j) in slots.items()}


def read_drom(cache):
    W = g.S.DROM_WORDS
    nh = W >> 11
    per = W // nh
    words = np.zeros(W, dtype=np.uint32)
    for h in range(nh):
        L, j = names[f"drom{h}"]
        for x in range(2):
            rows = cache.layers[L].recurrent_states[0][0, j * r_ + x].detach().to(torch.float32).cpu().numpy()
            for wl in range(per // 2):
                pp, half, k = wl >> 4, wl >> 3 & 1, wl & 7
                rr = pp + 64 * half
                v = 0
                for b in range(4):
                    v |= int(round(float(rows[rr, 2 + 32 * half + 4 * k + b]))) << (8 * b)
                words[h * per + x * (per // 2) + wl] = v
    return words.tobytes()


def ram_state(cache):
    sys.argv = ["x"]
    import edit
    H = edit.Heads(ec)
    return edit.show(edit.durable(H.ram(cache)))


t0 = time.time()
out = chat._prefill(prompt)
cache = out.past_key_values
g.core.snapshot(chat.c, m0)
hf.inject(chat.c, cache)
pos = len(prompt)
ok = wrong = 0
with torch.no_grad():
    for i in range(len(stream) - 1):
        mid, want = g.D.to_model(chat, stream[i]), g.D.to_model(chat, stream[i + 1])
        chip = mid >= chat.v0
        hc, _ = chat._layers(mid, cache, None if chip else pos)
        if not chip:
            pos += 1
        if own[i]:
            if chat.circuit_token(hc) == want:
                ok += 1
            else:
                wrong += 1
        if i % 1000 == 0:
            print(i, len(stream), ok, wrong, round(time.time() - t0), flush=True)
b = read_drom(cache)
pad = image.ljust(len(b), b"\0")
diff = sum(x != y for x, y in zip(b, pad))
st = ram_state(cache)
open(os.path.join(OUT, "drom_from_weights.bin"), "wb").write(b)
res = {"args": args, "stream": len(stream), "owned_right": ok, "owned_wrong": wrong, "table_bytes": len(b), "image_bytes": len(image), "bytes_differing": diff, "state_after_run": st, "line": T.decode_bytes(ses.runs[-1]).decode("utf-8", "replace")[:200], "seconds": round(time.time() - t0)}
json.dump(res, open(os.path.join(OUT, "result.json"), "w"), indent=1, ensure_ascii=False, default=str)
print(json.dumps(res, ensure_ascii=False, default=str)[:900], flush=True)
print("map_out finished", flush=True)
