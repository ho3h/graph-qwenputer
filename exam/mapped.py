#!/usr/bin/env python3
"""exam/AFTER.md E: Qwen with X2.7's map in its prompt, step by step. No tool, no machine. Resumes from the rows it finds.

    python exam/mapped.py --arm M1|M2|M3 --out R.jsonl --limit 25 --deadline-s S
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "ctrl")]
ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True, choices=["M1", "M2", "M3", "M4"])
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=25)
ap.add_argument("--deadline-s", type=float, required=True)
a = ap.parse_args()
a.out = os.path.abspath(a.out)
ASK = " Answer with the station name only."
COT = " Before answering, list each stop you pass, numbered, one per line. Then give the final line as 'Answer: <station name>'."
X27 = json.load(open(os.path.join(X210, "..", "X2.7", "chases.json")))["questions"]
maps = {q["id"]: q["map_list"] for q in X27}
F = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.questions.json")))["questions"]
byid = {q["id"]: q for q in F}
if a.arm == "M4":
    items = [{"id": q["id"], "orig": q["orig_id"], "text": q["text"], "gold": q["answer_text"], "wording": q["wording"]} for q in json.load(open(os.path.join(HERE, "items", "nyc_wordings.json")))]
elif a.arm == "M1":
    items = [{"id": q["id"], "orig": q["orig_id"], "text": q["text"], "gold": q["answer_text"]} for q in F if q["orig_kind"] == "two"]
else:
    d = json.load(open(os.path.join(HERE, "results", "nyc_r1_edit_draw.json")))
    rows = d["conversations"] if a.arm == "M2" else d["plain"]
    items = [{"id": c["key"], "orig": byid[int(c["key"].split(":")[1])]["orig_id"], "text": c["turns"][0]["user"], "gold": c["turns"][0]["gold"], "on_route": c.get("on_route")} for c in rows]
assert all(ASK in x["text"] and x["orig"] in maps for x in items)
done = {json.loads(x)["id"] for x in open(a.out)} if os.path.exists(a.out) else set()
todo = [x for x in items if x["id"] not in done][: a.limit]
if not todo:
    print("arm finished", flush=True)
    sys.exit(0)
import flows as FL  # noqa: E402  (chdirs to rvc)

qwen = FL.Qwen(path=os.path.expanduser("~/Models/x210/Qwen3.5-4B"), attn="sdpa")
tok = qwen.tok
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
t00 = time.time()
with open(a.out, "a", encoding="utf-8", buffering=1) as f:
    for x in todo:
        if time.time() - t00 > a.deadline_s:
            print("DEADLINE", flush=True)
            sys.exit(3)
        t0 = time.time()
        p = tok.apply_chat_template([{"role": "user", "content": maps[x["orig"]] + "\n\n" + x["text"].replace(ASK, COT)}], add_generation_prompt=True, enable_thinking=False, tokenize=True)
        prompt = [int(v) for v in (p if isinstance(p, list) else p["input_ids"])]
        nxt, cache = qwen.forward(prompt, None)
        out = []
        while len(out) < 1024 and nxt not in stops:
            out.append(nxt)
            nxt, cache = qwen.forward([nxt], cache)
        del cache
        FL.torch.mps.empty_cache()
        text = tok.decode(out, skip_special_tokens=True)
        f.write(json.dumps({**x, "finished": "Answer:" in text and len(out) < 1024, "answer": text.rsplit("Answer:", 1)[1].strip() if "Answer:" in text else "", "text_out": text, "new_tokens": len(out), "prompt_tokens": len(prompt), "seconds": round(time.time() - t0, 2)}, ensure_ascii=False) + "\n")
print("chunk done", round(time.time() - t00), flush=True)
