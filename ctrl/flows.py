#!/usr/bin/env python3
"""X2.10 control arms: base Qwen, reflib as the tool, one tool on offer, no machine.

    flows.py --flow printout|readback --set chain3|rb50|rb17|fresh200 --tool chase|A [--told] [--extra] --delivery normal|bytes --out results/NAME --deadline SECONDS

printout: as rb/run.py. Qwen's first clean line ends the question; an error or limit line goes back for up to 2 retries; the last line stands.
readback: as rb/delivery.py told, with one tool. Every response goes back, Qwen goes on until it ends its own turn. Up to 3 calls, the same allowance as
printout; a 4th call is recorded, not run, and ends the question. Resumable, one JSON line per question, stops at the deadline with exit 3.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
os.chdir(ROOT / "rvc")
sys.path.insert(0, str(ROOT / "rvc"))
import wrap_control as W  # noqa: E402

import torch  # noqa: E402

HT, SC, reflib, Qwen, D, BR, X = W.HT, W.SC, W.reflib, W.Qwen, W.D, W.BR, W.X
assert Path(SC.__file__).parent.name == "host", SC.__file__
sys.path.insert(0, str(ROOT / "q1"))
import prompts as P  # noqa: E402
import qparse as Q  # noqa: E402

GRAPHS = {"tiny": "tiny", "c024": "cities/c024", "c025": "cities/c025", "r001": "random/r001"}
CHAIN3 = json.load(open(ROOT / "rvc" / "results" / "chain3" / "meta.json"))
EXTRA, TOLD = CHAIN3["extra"], CHAIN3["told"]
assert TOLD in open(ROOT / "rb" / "delivery.py").read()
CHASE = [t for t in HT.tools_for("base") if t["function"]["name"] == "chase"][0]
assert CHASE == CHAIN3["tool"]
ERROR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG|BADQUERY)\b")
RETRIES, MAX_CALLS = 2, 3
THINK_DONE = re.compile(r"^.*</think>", re.S)


def system(tool, g, told, extra):
    base = HT.system_prompt(g) + (EXTRA if extra else "") + (TOLD if told else "")
    return base + (P.TEXT["A"] if tool == "A" else "")


def answer(tool, graph, call):
    return Q.answer("A", graph, call) if tool == "A" else HT.answer_call(graph, call)


def forced(tok, T, line, delivery):
    if delivery in ("bytes", "template-bytes", "im-bytes"):
        return W.forced_ids(line, tok, T, delivery)               # bytes is exactly the machine's echo
    return tok.encode("<|im_end|>\n<|im_start|>user\n<tool_response>\n" + line + "\n</tool_response><|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", add_special_tokens=False)


def clean(text):
    return THINK_DONE.sub("", text).replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()


def question(qwen, T, g, q, a):
    graph = reflib.Graph(g)
    for s in q.get("setup") or []:
        graph.call(s["fn"], s["args"])
    tok = qwen.tok
    msgs = [{"role": "system", "content": system(a.tool, g, a.told, a.extra)}, {"role": "user", "content": q["text"]}]
    p = tok.apply_chat_template(msgs, tools=[P.tool("A") if a.tool == "A" else CHASE], add_generation_prompt=True, enable_thinking=False, tokenize=True)
    prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
    stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
    calls, turns, generated, status, cap_call = [], [], 0, None, None
    line, printed = None, None
    t0 = time.time()
    nxt, cache = qwen.forward(prompt, None)
    while status is None:
        seg = []
        while True:
            seg.append(nxt)
            generated += 1
            if nxt in stops or len(seg) >= W.TURN or generated >= W.TOTAL:
                break
            nxt, cache = qwen.forward([nxt], cache)
        text = tok.decode(seg, skip_special_tokens=False)
        turns.append(text)
        if seg[-1] != qwen.TCC:
            status = "stopped_self" if seg[-1] in (qwen.IM_END, qwen.EOS) else "token_cap"
            break
        tco = max((i for i, t in enumerate(seg) if t == qwen.TCO), default=-1)
        inner = tok.decode(seg[tco + 1:-1], skip_special_tokens=False)
        call = HT.parse_call(inner)
        if a.flow == "readback" and len(calls) == MAX_CALLS:
            status, cap_call = "call_cap", inner
            break
        line = answer(a.tool, graph, call)
        calls.append({"text": inner, "fn": call["fn"], "args": call["args"], "result": line, "tokens": len(seg) - tco - 2, "before_call": tco})
        is_err = bool(ERROR.match(line))
        if printed is None and not is_err:
            printed = line                                         # the first clean line: what printout would have taken
        if a.flow == "printout" and (not is_err or len(calls) == RETRIES + 1):
            status = "answered"
            break
        nxt, cache = qwen.forward([qwen.TCC] + forced(tok, T, line, a.delivery), cache)
    del cache
    if printed is None:
        printed = line                                             # no clean line: the last line, as in printout
    final_text = clean(turns[-1]) if status == "stopped_self" else None
    return {"graph": q["_graph"], "id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"), "status": status, "n_calls": len(calls), "calls": calls,
            "line": printed, "last_line": line, "turns": turns, "final_text": final_text, "cap_call": cap_call, "prompt_tokens": len(prompt), "generated_tokens": generated,
            "stop_token": tok.decode([seg[-1]]), "seconds": round(time.time() - t0, 2)}


def question_set(name):
    if name == "chain3":
        path = ROOT / "rvc" / "results" / "chain3_draw.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest().startswith("701a642e")
        keys = [tuple(k) for k in json.load(open(path))["draw"]]
    elif name in ("rb50", "rb17"):
        keys = []
        for short, gname in GRAPHS.items():
            qs = {x["id"]: x for x in json.load(open(D.graph_path(gname)[1]))["questions"]}
            for ln in open(ROOT / "host" / "out" / "dev2" / short / "sdpa.jsonl"):
                i = json.loads(ln)["id"]
                if name == "rb50" or qs[i].get("kind") == "chase":
                    keys.append((gname, i))
    else:
        keys = [tuple(k) for k in json.load(open(HERE / "results" / "arm4_draw.json"))["draw"]]
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flow", required=True, choices=["printout", "readback"])
    ap.add_argument("--set", required=True, choices=["chain3", "rb50", "rb17", "fresh200"])
    ap.add_argument("--tool", required=True, choices=["chase", "A"])
    ap.add_argument("--told", action="store_true")
    ap.add_argument("--extra", action="store_true")
    ap.add_argument("--delivery", required=True, choices=["normal", "bytes", "template-bytes", "im-bytes"])
    ap.add_argument("--model", default="", help="model folder, instead of host/model.py's default on the LaCie")
    ap.add_argument("--out", required=True)
    ap.add_argument("--deadline", type=float, required=True, help="seconds from start, model load included")
    a = ap.parse_args()
    t0 = time.time()
    keys = question_set(a.set)
    assert not any("heldout" in k[0] for k in keys)
    T = BR.Text(os.path.join(a.model, "tokenizer.json") if a.model else X.tokenizer_json())
    qwen = Qwen(path=a.model, attn="sdpa") if a.model else Qwen(attn="sdpa")
    print(f"loaded {qwen.load_seconds}s, {len(keys)} questions", flush=True)
    out = HERE / a.out
    out.mkdir(parents=True, exist_ok=True)
    json.dump({**vars(a), "model": qwen.path, "load_seconds": qwen.load_seconds, "extra_text": EXTRA, "told_text": TOLD, "turn": W.TURN, "total": W.TOTAL, "retries": RETRIES, "max_calls": MAX_CALLS,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "env": qwen.env}, open(out / "meta.json", "w"), indent=1, ensure_ascii=False)
    path = out / "all.jsonl"
    done = {(json.loads(ln)["graph"], json.loads(ln)["id"]) for ln in open(path)} if path.exists() else set()
    cache = {}
    with open(path, "a", encoding="utf-8") as f:
        for gname, i in keys:
            if (gname, i) in done:
                continue
            if time.time() - t0 > a.deadline:
                print(f"DEADLINE at {time.time() - t0:.0f}s, before {gname} {i}", flush=True)
                sys.exit(3)
            if gname not in cache:
                gp, qp = D.graph_path(gname)
                cache = {gname: (json.load(open(gp)), {x["id"]: x for x in json.load(open(qp))["questions"]})}
            g, qs = cache[gname]
            q = dict(qs[i], _graph=gname)
            r = question(qwen, T, g, q, a)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(gname, i, r["kind"], r["status"], r["n_calls"], r["seconds"], repr((r["line"] or "")[:50]), repr((r["final_text"] or "")[-60:]), flush=True)
            torch.mps.empty_cache()
    print(f"done {time.time() - t0:.0f}s peak_driver {qwen.peak_driver / 2**30:.2f} GiB", flush=True)


if __name__ == "__main__":
    main()
