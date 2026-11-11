#!/usr/bin/env python3
"""exam/AFTER.md K1, K2. T8_R1=1 T8_WRITES=1 T8_NOUN=on. controls.py plain|zeroed --out R.jsonl --deadline-s S"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "speed")]
import d1m  # noqa: E402
import fast  # noqa: E402

mode = sys.argv[1]
a = sys.argv
out, lim = a[a.index("--out") + 1], float(a[a.index("--deadline-s") + 1])
fast.setup("writes")
g = fast.g
qs, _ = d1m.draw("nyc", 200)
order = list(range(300))
random.Random("20261106:nyc:i").shuffle(order)
qs = [qs[i] for i in order]
if mode == "plaine":                                                 # exam/AFTER.md K1e: a write
    draw = {c["key"]: c for c in json.load(open(os.path.join(HERE, "results", "nyc_r1_edit_draw.json")))["conversations"] if c.get("changed")}
    saved = {r["key"]: r for r in map(json.loads, open(os.path.join(HERE, "results", "nyc_r1_edit", "all.jsonl")))}
    qs = []
    for k in list(draw)[:3]:
        t0_ = saved[k]["turns"][0]
        qs.append({"id": k, "text": t0_["user"], "answer_text": t0_["gold"], "args": t0_["calls"][0]["args"]})
gr0 = json.load(open(d1m.base_of("nyc") + ".graph.json"))
gr = g.graph_fn(gr0)
ctx = fast.load_stock()
chat = ctx.ec.chat
T, tok, torch = chat.T, chat.tok, g.torch
from chipformer.rv import hf  # noqa: E402

fl = fast.flow("print-writes")
stops = {tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}
system = g.HT.system_prompt(gr) + g.C2.EXTRA + g.C2.TOLD
if mode == "zeroed":
    with torch.no_grad():
        for i in range(chat.n_chip):
            for p in chat.lm.layers[i].parameters():
                p.zero_()
t0 = time.time()
f = open(out, "a", encoding="utf-8", buffering=1)
for k, q in enumerate(qs[: 1 if mode == "plaind" else 3 if mode in ("plain", "plainb", "plainc", "plaine") else 20]):
    if time.time() - t0 > lim:
        print("DEADLINE", flush=True)
        break
    t1 = time.time()
    prompt = chat.prompt_ids([{"role": "system", "content": system}] + g.worked.HISTORY + [{"role": "user", "content": q["text"]}], tools=g.worked.TOOLS)
    with torch.no_grad():
        o = chat._prefill(prompt)
        cache = o.past_key_values
        if mode in ("plain", "plainb", "plainc", "plaind", "plaine"):
            g.core.snapshot(chat.c, g.D.parked_machine(gr, T, []))
            hf.inject(chat.c, cache)
        logits = o.logits[0, -1]
        cap, gen = (12000, []) if mode in ("plain", "plainb", "plainc", "plaind", "plaine") else (256, [])
        if mode in ("plainc", "plaind", "plaine"):
            cap = 300 + len(g.D.session_for(chat, gr, prompt, [("chase", q["args"] if "args" in q else json.loads(next(x for x in open(os.path.join(HERE, "results", "nyc_r1_d1m", "all.jsonl")) if str(json.loads(x)["id"]) == str(q["id"])))["calls"][0]["args"])], None)[1])
        vocab = logits.shape[-1] if mode in ("plain", "plainb", "plainc", "plaind", "plaine") else chat.v0
        nxt = int(torch.argmax(logits[:vocab]))
        while len(gen) < cap and (mode in ("plainc", "plaind", "plaine") or nxt not in stops) and time.time() - t0 < lim:
            gen.append(nxt)
            if mode in ("plainb", "plainc", "plaine"):
                _, lg = chat._layers(nxt, cache, len(prompt) + len(gen) - 1)
                nxt = int(torch.argmax(lg))
                continue
            o = chat.model(input_ids=torch.tensor([[nxt]], device=chat.dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = o.past_key_values
            nxt = int(torch.argmax(o.logits[0, -1, :vocab]))
    want = [g.D.to_model(chat, t) for t in g.D.session_for(chat, gr, prompt, [("chase", q["call"]["args"])] if False else [("chase", q["args"] if "args" in q else json.loads(next(x for x in open(os.path.join(HERE, "results", "nyc_r1_d1m", "all.jsonl")) if str(json.loads(x)["id"]) == str(q["id"])))["calls"][0]["args"])], None)[1]]
    diff = next((j for j in range(min(len(gen), len(want))) if gen[j] != want[j]), None)
    text = tok.decode([t for t in gen if t < chat.v0], skip_special_tokens=False)
    chip = sum(t >= chat.v0 for t in gen)
    gold = q["answer_text"].split("\n")[-1]
    f.write(json.dumps({"id": q["id"], "text": q["text"], "gold": gold, "gold_in_text": gold in text, "label_in_text": gold.split(" ", 1)[-1] in text, "chip_tokens": chip, "total": len(gen), "stopped": nxt in stops, "out": text[:2500], "stream_len": len(want), "first_difference": diff, "gen_hash": __import__("hashlib").sha256(json.dumps(gen).encode()).hexdigest()[:16], "seconds": round(time.time() - t1, 1)}, ensure_ascii=False) + "\n")
    print(q["id"], gold in text, chip, len(gen), round(time.time() - t1), flush=True)
    del cache, o
    torch.mps.empty_cache()
