"""A control for M3: base Qwen with the host tool (reflib), but the response delivered as the circuit delivers it: the
circuit's wrapping, printed one byte token at a time. No machine and no merged weights. If this arm moves away from the
host baseline, the cause is the wrapping and the byte tokens, not the machine.

    python wrap_control.py --graph cities/c024 --transcript ../../host/out/dev2/c024/sdpa.jsonl --out results/wrapctl/c024.jsonl

Same loop, stops and budgets as host/harness.py (a copy with one change, `forced`); host/ itself is untouched. Base Qwen
through host/model.py. --mode: "bytes" (circuit wrapping, byte tokens), "wrap" (circuit wrapping, normal tokens),
"template-bytes" (template wrapping, result as byte tokens), "im-bytes" (every token a byte or one of six specials: the
bridge's four plus <|im_start|> and <|im_end|>).
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X  # noqa: E402
import decode as D  # noqa: E402

import torch  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402
from model import Qwen  # noqa: E402  (host/model.py, unchanged)

HT = X.HT
MAX_CALLS, TURN, TOTAL = 12, 768, 3072


def forced_ids(result, tok, T, mode):
    body = result.encode()
    nl = T.printable[10]
    b = [T.printable[x] for x in body]
    ts, te = tok.convert_tokens_to_ids("<tool_response>"), tok.convert_tokens_to_ids("</tool_response>")
    tk, tke = tok.convert_tokens_to_ids("<think>"), tok.convert_tokens_to_ids("</think>")
    if mode == "bytes":                                   # exactly the machine's echo
        return [nl, ts, nl] + b + [nl, te, nl, tk, nl, nl, tke, nl, nl]
    if mode == "wrap":
        return tok.encode("\n<tool_response>\n" + result + "\n</tool_response>\n<think>\n\n</think>\n\n", add_special_tokens=False)
    if mode == "im-bytes":                                # what the machine could print with two more special tokens
        ims, ime = tok.convert_tokens_to_ids("<|im_start|>"), tok.convert_tokens_to_ids("<|im_end|>")
        by = lambda x: [T.printable[c] for c in x.encode()]
        return [ime, nl, ims] + by("user") + [nl, ts, nl] + b + [nl, te, ime, nl, ims] + by("assistant") + [nl, tk, nl, nl, tke, nl, nl]
    assert mode == "template-bytes"
    head = tok.encode("<|im_end|>\n<|im_start|>user\n<tool_response>\n", add_special_tokens=False)
    tail = tok.encode("\n</tool_response><|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", add_special_tokens=False)
    return head + b + tail


def run_question(qwen, T, g, q, mode, arm="base"):
    graph = reflib.Graph(g)
    for s in q.get("setup") or []:
        graph.call(s["fn"], s["args"])
    tok = qwen.tok
    msgs = [{"role": "system", "content": HT.system_prompt(g)}, {"role": "user", "content": q["text"]}]
    p = tok.apply_chat_template(msgs, tools=HT.tools_for(arm), add_generation_prompt=True, enable_thinking=False, tokenize=True)
    prompt = [int(x) for x in (p if isinstance(p, list) else p["input_ids"])]
    segments, calls = [{"by": "prompt", "ids": prompt}], []
    stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
    t0 = time.time()
    nxt, cache = qwen.forward(prompt, None)
    status, generated = None, 0
    while status is None:
        seg = []
        while True:
            seg.append(nxt)
            generated += 1
            if nxt in stops:
                break
            if len(seg) >= TURN or generated >= TOTAL:
                status = "budget"
                break
            nxt, cache = qwen.forward([nxt], cache)
        segments.append({"by": "qwen", "ids": seg})
        if status:
            break
        if seg[-1] != qwen.TCC:
            status = "answered"
            break
        if len(calls) == MAX_CALLS:
            status = "cap"
            break
        tco = max((i for i, t in enumerate(seg) if t == qwen.TCO), default=-1)
        inner = tok.decode(seg[tco + 1:-1], skip_special_tokens=False)
        call = HT.parse_call(inner)
        result = HT.answer_call(graph, call)
        forced = forced_ids(result, tok, T, mode)
        calls.append({"text": inner, "ids": seg[tco + 1:-1], "fn": call["fn"], "args": call["args"], "result": result,
                      "response_ids": forced})
        segments.append({"by": "tool", "ids": forced})
        nxt, cache = qwen.forward([qwen.TCC] + forced, cache)
    final = None
    if status == "answered":
        last = tok.decode(segments[-1]["ids"], skip_special_tokens=False)
        final = last.split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    del cache
    return {"id": q["id"], "kind": q.get("kind"), "status": status, "n_calls": len(calls), "calls": calls, "final": final,
            "correct": SC.score(final, q, graph.labels), "segments": segments, "generated_tokens": generated,
            "seconds": round(time.time() - t0, 2), "mode": mode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, help="JSON: [[graph, host transcript, out jsonl], ...]")
    ap.add_argument("--mode", default="bytes")
    ap.add_argument("--attn", default="sdpa")
    a = ap.parse_args()
    T = BR.Text(X.tokenizer_json())
    qwen = Qwen(attn=a.attn)
    print(f"loaded {qwen.load_seconds}s", flush=True)
    for gname, transcript, out in json.load(open(a.jobs)):
        gp, qp = D.graph_path(gname)
        g = json.load(open(gp))
        qs = {x["id"]: x for x in json.load(open(qp))["questions"]}
        ids = [json.loads(line)["id"] for line in open(transcript)]
        os.makedirs(os.path.dirname(out), exist_ok=True)
        done = {json.loads(line)["id"] for line in open(out)} if os.path.exists(out) else set()
        with open(out, "a", encoding="utf-8") as f:
            for i in ids:
                if i in done:
                    continue
                r = run_question(qwen, T, g, qs[i], a.mode)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print(f"{gname} q{i}: {r['status']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s", flush=True)
                torch.mps.empty_cache()


if __name__ == "__main__":
    main()
