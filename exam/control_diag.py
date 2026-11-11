#!/usr/bin/env python3
"""exam/AFTER.md K1's point of failure. Same model and memory, teacher-forced along the right token stream through every layer. At each position: the circuit's token, and the head's argmax over the whole vocabulary."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "speed")]
import d1m
import fast

fast.setup("writes")
g = fast.g
qs, _ = d1m.draw("nyc", 200)
q = next(x for x in qs if str(x["id"]) == "900053")
gr = g.graph_fn(json.load(open(d1m.base_of("nyc") + ".graph.json")))
ctx = fast.load_stock()
chat = ctx.ec.chat
T, tok, torch = chat.T, chat.tok, g.torch
from chipformer.rv import hf

prompt = chat.prompt_ids([{"role": "system", "content": g.HT.system_prompt(gr) + g.C2.EXTRA + g.C2.TOLD}] + g.worked.HISTORY + [{"role": "user", "content": q["text"]}], tools=g.worked.TOOLS)
rec = next(json.loads(l) for l in open(os.path.join(HERE, "results", "nyc_r1_d1m", "all.jsonl")) if str(json.loads(l)["id"]) == "900053")
args = rec["calls"][0]["args"]
m0, stream, own, ses = g.D.session_for(chat, gr, prompt, [("chase", args)], None)
print("stream", len(stream), flush=True)
out = chat._prefill(prompt)
cache = out.past_key_values
g.core.snapshot(chat.c, m0)
hf.inject(chat.c, cache)
pos = len(prompt)
res = {"stream": len(stream), "rows": []}
agree = bad_head = bad_circuit = 0
first = None
t0 = time.time()
to_id = g.D.to_model
name = lambda i: (f"chip:{i - chat.v0}" if i >= chat.v0 else tok.decode([i]))
with torch.no_grad():
    for i in range(min(len(stream) - 1, 900)):
        mid, want = to_id(chat, stream[i]), to_id(chat, stream[i + 1])
        hc, logits = chat._layers(mid, cache, pos)
        pos += 1
        ct = chat.circuit_token(hc)
        v, ix = torch.topk(logits, 3)
        top = int(ix[0])
        if own[i]:
            bad_circuit += ct != want
            if top == want:
                agree += 1
            else:
                bad_head += 1
                if first is None:
                    first = {"i": i, "input": name(mid), "want": name(want), "circuit": ct and name(ct), "top3": [[name(int(a)), round(float(b), 2)] for a, b in zip(ix, v)], "want_logit": round(float(logits[want]), 2), "own_i": bool(own[i])}
                    print(first, flush=True)
        if i % 200 == 0:
            print(i, "owned head-right", agree, "head-wrong", bad_head, "circuit-wrong", bad_circuit, round(time.time() - t0), flush=True)
res.update(first_head_miss=first, owned_head_right=agree, owned_head_wrong=bad_head, owned_circuit_wrong=bad_circuit, seconds=round(time.time() - t0))
json.dump(res, open(os.path.join(HERE, "results", "after", "control_diag.json"), "w"), indent=1, ensure_ascii=False)
print(res, flush=True)
