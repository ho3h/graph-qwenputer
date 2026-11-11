#!/usr/bin/env python3
"""exam/AFTER.md round 18: the two Qwen baselines of the post's chart, with Qwen's reasoning turned on. No tool, no machine.

Arm A: Qwen alone, no map, the question as exam/alone.py asks it. Arm M: X2.7's map lines in the prompt and the list-each-stop
instruction, as exam/mapped.py's M1 asks it. Arm P (the revision of 10 Nov): the same map lines and the question with no list instruction. The only change from those runs is enable_thinking=True and the token cap.
The same 100 two-train questions from New York's question file, in file order. Resumes from the rows it finds.

    python exam/think.py --arm A|M|P --out R.jsonl --deadline-s S [--cap 2048] [--limit N] [--chunk N] [--dry] [--decode D] [--dev]

--decode general|precise (the revision of 10 Nov): one sample a question with one of the model card's two settings for thinking
mode (exam/card_sample.py), seeded by the question's id. The default is greedy, as in the first attempt.
--dev: the two practice questions below in place of the exam's. They use real lines and are in no question file.
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
ap.add_argument("--arm", required=True, choices=["A", "M", "P"])
ap.add_argument("--out", required=True)
ap.add_argument("--deadline-s", type=float, required=True)
ap.add_argument("--cap", type=int, default=2048)
ap.add_argument("--limit", type=int, default=100)
ap.add_argument("--chunk", type=int, default=100, help="at most this many questions in this process; the queue restarts the process for the next chunk")
ap.add_argument("--dry", action="store_true", help="build the prompts with the tokenizer only, no model, and print the first one's end")
ap.add_argument("--decode", default="greedy", choices=["greedy", "general", "precise"], help="greedy, or one sample with the model card's settings of that name")
ap.add_argument("--dev", action="store_true", help="the two practice questions, which are in no exam")
a = ap.parse_args()
a.out = os.path.abspath(a.out)
MODEL = os.path.expanduser("~/Models/x210/Qwen3.5-4B")
ASK = " Answer with the station name only."
COT = " Before answering, list each stop you pass, numbered, one per line. Then give the final line as 'Answer: <station name>'."
THINK_END = 248069                                                  # </think>, one token in Qwen3.5-4B's tokenizer
maps = {q["id"]: q["map_list"] for q in json.load(open(os.path.join(X210, "..", "X2.7", "chases.json")))["questions"]}
F = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.questions.json")))["questions"]
items = [{"id": q["id"], "orig": q["orig_id"], "text": q["text"], "gold": q["answer_text"]} for q in F if q["orig_kind"] == "two"]
assert len(items) == 100 and all(ASK in x["text"] and x["orig"] in maps for x in items)


def content(x):
    """A: the question. M: the map lines and the list-each-stop instruction. P (10 Nov): the map lines and the question as it stands."""
    return x["text"] if a.arm == "A" else maps[x["orig"]] + "\n\n" + (x["text"] if a.arm == "P" else x["text"].replace(ASK, COT))


if a.dry:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    assert tok.convert_tokens_to_ids("</think>") == THINK_END

    def toks(x):
        p = tok.apply_chat_template([{"role": "user", "content": content(x)}], add_generation_prompt=True, enable_thinking=True, tokenize=True)
        return [int(v) for v in (p if isinstance(p, list) else p["input_ids"])]

    n = [len(toks(x)) for x in items]
    print(json.dumps({"arm": a.arm, "items": len(items), "first_id": items[0]["id"], "prompt_tokens_min_max": [min(n), max(n)], "first_prompt_end": tok.decode(toks(items[0])[-40:])}))
    sys.exit(0)

SEED = 18000                                                        # a question's seed is SEED + its id


def practice():
    """Two questions on the lines of exam questions 103 and 108, with other starts and counts. The answer is read off the map lines."""
    def line(m, name):
        return next(x.split(": ", 1)[1].split(", ") for x in m.split("\n") if x.startswith(name + ": "))
    out = []
    for qid, start, t1, d1, n1, t2, d2, n2 in ((-1, "Avenue H", "Q", "northbound", 8, "3", "southbound", 4), (-2, "79 St", "1", "southbound", 1, "3", "southbound", 3)):
        m = maps[{-1: 103, -2: 108}[qid]]
        a1, a2 = line(m, f"{t1} {d1}"), line(m, f"{t2} {d2}")
        mid = a1[a1.index(start) + n1]
        text = (f"Start at {start} station. Ride the {t1} train {n1} stop{'s' * (n1 > 1)} {d1}, then change to the {t2} and ride the {t2} train {n2} stops {d2}. "
                "One stop means the next station. At which station are you now?" + ASK)
        assert all(text != x["text"] for x in items) and a2.count(mid) == 1
        out.append({"id": qid, "orig": {-1: 103, -2: 108}[qid], "text": text, "gold": "@dev " + a2[a2.index(mid) + n2]})
    return out


def saved(path):
    """The rows already in the output file. A last line cut by a kill is dropped from the file. A row from another arm, cap, decoding or question set stops the run."""
    if not os.path.exists(path):
        return []
    good, lines = [], open(path, encoding="utf-8").read().split("\n")
    for line in lines:
        try:
            good.append(json.loads(line))
        except ValueError:
            pass
    if len(good) != sum(1 for x in lines if x.strip()):
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in good)
    for r in good:
        assert (r["arm"], r["cap"], r.get("decode", "greedy"), r["id"] < 0) == (a.arm, a.cap, a.decode, a.dev), ("a row from another run is in " + path, r["id"], r["arm"], r["cap"], r.get("decode"))
    assert len({r["id"] for r in good}) == len(good), "a question is in the file twice"
    return good


done = {r["id"] for r in saved(a.out)}
todo = [x for x in (practice() if a.dev else items) if x["id"] not in done][: max(0, min(a.chunk, a.limit - len(done)))]
if not todo:
    print("arm finished", flush=True)
    sys.exit(0)
import flows as FL  # noqa: E402  (chdirs to rvc)

from card_sample import pick  # noqa: E402

qwen = FL.Qwen(path=MODEL, attn="sdpa")
tok = qwen.tok
assert tok.convert_tokens_to_ids("</think>") == THINK_END
stops = {qwen.TCC, qwen.IM_END, qwen.EOS}


@FL.torch.no_grad()
def logits(ids, cache):
    """As Qwen.forward, but the logits over the tokenizer's ids come back in place of their argmax."""
    o = qwen.model(input_ids=FL.torch.tensor([ids], device=qwen.dev), past_key_values=cache, use_cache=True, logits_to_keep=1)
    return o.logits[0, -1, : qwen.nq], o.past_key_values


def reply(prompt, seed):
    """The new tokens, and whether Qwen stopped by itself. Greedy, or one sample with the card's settings named by --decode."""
    out = []
    if a.decode == "greedy":
        nxt, cache = qwen.forward(prompt, None)
        while len(out) < a.cap and nxt not in stops:
            out.append(int(nxt))
            nxt, cache = qwen.forward([nxt], cache)
    else:
        gen, seen = FL.torch.Generator().manual_seed(seed), set()
        z, cache = logits(prompt, None)
        nxt = pick(z, seen, gen, a.decode)
        while len(out) < a.cap and nxt not in stops:
            out.append(nxt)
            seen.add(nxt)
            z, cache = logits([nxt], cache)
            nxt = pick(z, seen, gen, a.decode)
    del cache
    FL.torch.mps.empty_cache()
    return out, nxt in stops


t00 = time.time()
os.makedirs(os.path.dirname(a.out), exist_ok=True)
with open(a.out, "a", encoding="utf-8", buffering=1) as f:
    for x in todo:
        if time.time() - t00 > a.deadline_s:
            print("DEADLINE", flush=True)
            sys.exit(3)
        t0 = time.time()
        print("start", x["id"], time.strftime("%T"), flush=True)
        p = tok.apply_chat_template([{"role": "user", "content": content(x)}], add_generation_prompt=True, enable_thinking=True, tokenize=True)
        prompt = [int(v) for v in (p if isinstance(p, list) else p["input_ids"])]
        out, stopped = reply(prompt, SEED + x["id"])
        k = out.index(THINK_END) if THINK_END in out else None
        after = tok.decode(out[k + 1:], skip_special_tokens=True) if k is not None else ""
        f.write(json.dumps({**x, "arm": a.arm, "cap": a.cap, "decode": a.decode, "seed": SEED + x["id"] if a.decode != "greedy" else None, "thought_tokens": k, "stopped": stopped, "new_tokens": len(out), "prompt_tokens": len(prompt),
                            "after_think": after, "thinking": tok.decode(out[:k] if k is not None else out, skip_special_tokens=True), "ids": out,
                            "seconds": round(time.time() - t0, 2)}, ensure_ascii=False) + "\n")
print("chunk done", round(time.time() - t00), flush=True)
