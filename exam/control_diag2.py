#!/usr/bin/env python3
"""K1's point of failure, diagnostic only, no result: free-run one question and compare each token with the right stream, on the same model and memory as control_diag.py."""
import json
import os
import sys

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
m0, stream, own, ses = g.D.session_for(chat, gr, prompt, [("chase", rec["calls"][0]["args"])], None)
want = [g.D.to_model(chat, t) for t in stream]
name = lambda i: (f"chip:{i - chat.v0}" if i >= chat.v0 else repr(tok.decode([i])))
out = chat._prefill(prompt)
cache = out.past_key_values
g.core.snapshot(chat.c, m0)
hf.inject(chat.c, cache)
logits = out.logits[0, -1]
nxt = int(torch.argmax(logits))
print("first free", name(nxt), "| stream starts", [name(x) for x in want[:4]], flush=True)
gen = []
offset = None
with torch.no_grad():
    for i in range(160):
        gen.append(nxt)
        hc, logits = chat._layers(nxt, cache, len(prompt) + len(gen) - 1)
        ct = chat.circuit_token(hc)
        v, ix = torch.topk(logits, 3)
        top = int(ix[0])
        if i >= 44 and i <= 112:
            print(i, "in", name(nxt), "| circuit", ct and name(ct), "| top", [(name(int(a)), round(float(b), 1)) for a, b in zip(ix, v)], flush=True)
        nxt = top
        if nxt in {tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}:
            print("stopped at", i, flush=True)
            break
j = next((k for k in range(min(len(gen), len(want))) if gen[k] != want[k]), None)
print("gen", len(gen), "first difference from stream at", j, j is not None and (name(gen[j]), name(want[j]), own[j]), flush=True)
print("stream around", [name(x) for x in want[44:60]], flush=True)
