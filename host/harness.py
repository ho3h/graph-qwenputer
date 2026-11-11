"""The host-tool baseline loop: base Qwen 3.5 calls the real reference tool (reflib's Graph.call).

One question is one token stream with one cache, decoded greedily:
1. the prompt is the chat template with the eight SPEC tools (`tools=`) and a system and a user message;
2. Qwen writes until '</tool_call>' (a call), '<|im_end|>' or '<|endoftext|>' (its final answer), or a budget;
3. at '</tool_call>' the call is parsed, run by reflib, and the tool response is forced into the stream in the
   template's exact format (tools.forced_text); Qwen then continues from its next generation prompt;
4. a 13th call (more than MAX_CALLS) stops the question as a failure ("cap").

A question's `setup` calls run on the host before the prompt: the text states them as already done ("After close
@4: ..."), and Qwen sees only the text. Repeating one is harmless (it answers "already closed" and the like).

The forced tokens are fed as one chunk after '</tool_call>', as qwenputer's base benchmark does; Qwen's own
tokens are fed one at a time.
"""

import copy
import gc
import time

import torch

import score as SC
import tools as T
from model import mem

MAX_CALLS = 12


def run_question(qwen, gjson: dict, q: dict, think: bool = False, arm: str = "base", turn_budget: int = 768,
                 total_budget: int = 3072) -> dict:
    graph = T.Graph(gjson)                       # fresh state (nothing closed) for every question
    setup, setup_mismatch = q.get("setup") or [], []
    for step in setup:                           # the state the question's text describes as already done
        got = graph.call(step["fn"], step["args"])
        if "result" in step and got != step["result"]:
            setup_mismatch.append({"call": step, "got": got})
    replay = copy.deepcopy(graph)                # the canonical call on the same state: is the stored gold current?
    for step in q.get("gold_setup") or []:       # calls the question asks Qwen itself to make
        replay.call(step["fn"], step["args"])
    gold_replay = replay.call(q["call"]["fn"], q["call"]["args"]) if q.get("call") else None
    tok = qwen.tok
    messages = [{"role": "system", "content": T.system_prompt(gjson)}, {"role": "user", "content": q["text"]}]
    prompt = tok.apply_chat_template(messages, tools=T.tools_for(arm), add_generation_prompt=True, enable_thinking=think,
                                     tokenize=True)
    prompt = [int(x) for x in (prompt if isinstance(prompt, list) else prompt["input_ids"])]
    stream, segments, calls = list(prompt), [{"by": "prompt", "ids": list(prompt)}], []
    stops = {qwen.TCC, qwen.IM_END, qwen.EOS}
    gc.collect()
    torch.mps.empty_cache() if qwen.dev == "mps" else None
    qwen.peak_driver = 0
    t0 = time.time()
    nxt, cache = qwen.forward(prompt, None)
    prefill_s = time.time() - t0
    status, generated = None, 0
    while status is None:
        seg = []
        while True:
            seg.append(nxt)
            generated += 1
            if nxt in stops:
                break
            if len(seg) >= turn_budget or generated >= total_budget:
                status = "budget"
                break
            nxt, cache = qwen.forward([nxt], cache)
        stream += seg
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
        call = T.parse_call(inner)
        if tco < 0:
            call["error"] = (call["error"] + "; " if call["error"] else "") + "no <tool_call> in this turn"
        result = T.answer_call(graph, call)
        forced = tok.encode(T.forced_text(result, think), add_special_tokens=False)
        calls.append({"text": inner, "ids": seg[tco + 1:-1], "fn": call["fn"], "raw": call["raw"], "args": call["args"],
                      "parse_error": call["error"], "result": result, "response_ids": forced})
        stream += forced
        segments.append({"by": "tool", "ids": forced})
        nxt, cache = qwen.forward([qwen.TCC] + forced, cache)
    seconds = time.time() - t0
    last = tok.decode(segments[-1]["ids"], skip_special_tokens=False)
    final = None
    if status == "answered":
        final = last.split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    labels = graph.labels
    correct = SC.score(final, q, labels)
    del cache
    return {
        "id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"),
        "gold_text": q.get("answer_text"), "case": q.get("case"), "gold_replay": gold_replay,
        "gold_stale": gold_replay is not None and gold_replay != q.get("answer_text"),
        "setup_mismatch": setup_mismatch, "attn": qwen.attn, "think": think, "arm": arm,
        "status": status, "n_calls": len(calls), "calls": calls, "final": final, "correct": correct,
        "stream_ids": stream, "stream_text": tok.decode(stream, skip_special_tokens=False),
        "segments": segments, "prompt_tokens": len(prompt), "generated_tokens": generated,
        "seconds": round(seconds, 2), "prefill_seconds": round(prefill_s, 2),
        "peak_driver_bytes": qwen.peak_driver, "end_mem": mem(),
    }
