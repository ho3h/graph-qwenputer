#!/usr/bin/env python3
"""The same-setup host on D1m's questions: base Qwen, the same system text, worked turns and tool, one call, reflib prints the line. No machine.

    python exam/host.py --name nyc --out exam/results/nyc_host.jsonl --deadline-s S
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
ap.add_argument("--name", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=200)
ap.add_argument("--deadline-s", type=float, required=True)
a = ap.parse_args()
a.out = os.path.abspath(a.out)
import d1m  # noqa: E402
import flows as F  # noqa: E402  (chdirs to rvc)
sys.path[:0] = [os.path.join(X210, "t8", "fw")]
import noun as N  # noqa: E402
import worked as WK  # noqa: E402
import chain2 as C2  # noqa: E402
HT, reflib = F.HT, F.reflib
qs, _ = d1m.draw(a.name, a.n)
raw = json.load(open(d1m.base_of(a.name) + ".graph.json"))
g = N.with_noun(raw)
qwen = F.Qwen(path=os.path.expanduser("~/Models/x210/Qwen3.5-4B"), attn="sdpa")
tok = qwen.tok
print("loaded", qwen.load_seconds, flush=True)
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
system = HT.system_prompt(g) + C2.EXTRA + C2.TOLD
t00 = time.time()
done = {json.loads(x)["id"] for x in open(a.out)} if os.path.exists(a.out) else set()
with open(a.out, "a", encoding="utf-8", buffering=1) as f:
    for q in qs:
        if q["id"] in done:
            continue
        if time.time() - t00 > a.deadline_s:
            print("DEADLINE", flush=True)
            sys.exit(3)
        t0 = time.time()
        msgs = [{"role": "system", "content": system}] + WK.HISTORY + [{"role": "user", "content": q["text"]}]
        p = tok.apply_chat_template(msgs, tools=WK.TOOLS, add_generation_prompt=True, enable_thinking=False, tokenize=True)
        prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
        nxt, cache = qwen.forward(prompt, None)
        seg = []
        while True:
            seg.append(nxt)
            if nxt in stops or len(seg) >= 768:
                break
            nxt, cache = qwen.forward([nxt], cache)
        del cache
        call, inner, line = None, None, None
        if seg[-1] == qwen.TCC:
            tco = max((i for i, t in enumerate(seg) if t == qwen.TCO), default=-1)
            inner = tok.decode(seg[tco + 1:-1], skip_special_tokens=False)
            call = HT.parse_call(inner)
            line = HT.answer_call(reflib.Graph(g), call)
        f.write(json.dumps({"id": q["id"], "text": q["text"], "gold": q["answer_text"], "inner": inner, "fn": call and call["fn"], "args": call and call["args"], "result": line, "seg": seg, "prompt_tokens": len(prompt), "seconds": round(time.time() - t0, 2)}, ensure_ascii=False) + "\n")
        print(q["id"], line and line[:60], round(time.time() - t0, 1), flush=True)
        F.torch.mps.empty_cache()
print("done", round(time.time() - t00), flush=True)
