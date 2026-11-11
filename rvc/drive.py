"""M3: Qwen drives the machine. Greedy decoding on the merged checkpoint, in lockstep with the reference machine, with the
host harness's prompt, stops and budgets (host/harness.py: 12 calls, 768 tokens per turn, 3,072 in all).

    python drive.py --graph cities/c024 --ids-from ../../host/out/dev2/c024/sdpa.jsonl --out results/m3/c024.jsonl

Every run token the circuit predicts must equal the reference (lock), and each call's result is also compared with the
host tool (reflib) on the same call text. One JSON line per question, flushed; finished ids are skipped on a restart.
Bounded: --question-limit-s stops a question and records it as status "walltime" (a finding, not a score).
"""

import argparse
import copy
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
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402  (host/score.py, unchanged)

HT = X.HT
MAX_CALLS, TURN, TOTAL = 12, 768, 3072


@torch.no_grad()
def run_question(chat, g, q, nq, arm="base", limit_s=None):
    T, tok = chat.T, chat.tok
    TCO, TCC = T.TCO, T.TCC
    IM_END, EOS = tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")
    stops = {TCC, IM_END, EOS}
    setup = q.get("setup") or []
    graph = reflib.Graph(g)
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)                 # the setup is applied on the reference, then snapshotted
    msgs = [{"role": "system", "content": HT.system_prompt(g)}, {"role": "user", "content": q["text"]}]
    prompt = chat.prompt_ids(msgs, tools=HT.tools_for(arm))
    lock = BR.Session(T, copy.deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    out = chat._prefill(prompt)
    prefill_s = time.time() - t0
    cache = out.past_key_values
    core.snapshot(chat.c, m)
    hf.inject(chat.c, cache)
    pos = len(prompt)
    nxt = int(torch.argmax(out.logits[0, -1, :nq]))
    t_chip = t_text = 0.0
    n_chip = n_text_q = n_echo = 0
    head_bad = 0
    calls, segments = [], []
    seg, gen = [], 0
    expect, lock_error, status = [], None, None
    own_ok = 0
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if expect:                                      # a position of the machine's run: the circuit must equal the lock
            e = expect.pop(0)
            if st != e:
                lock_error = {"want": S.name(e) if e < S.VOCAB else tok.decode([e - S.TEXT_TOKEN]),
                              "got": S.name(st) if st < S.VOCAB else tok.decode([nxt]), "at_call": len(calls),
                              "left": len(expect)}
                status = "lock"
                break
            own_ok += 1
            if nxt < chat.v0:
                n_echo += 1
        elif st < S.VOCAB:
            lock_error = {"got": S.name(st), "want": "text", "at_call": len(calls)}
            status = "lock"
            break
        else:                                           # Qwen's own token
            seg.append(nxt)
            gen += 1
            n_text_q += 1
            if nxt in stops:
                segments.append({"by": "qwen", "ids": seg})
                if nxt != TCC:
                    status = "answered"
                    break
                if len(calls) == MAX_CALLS:
                    status = "cap"
                    break
                tco = max((i for i, t in enumerate(seg) if t == TCO), default=-1)
                inner_ids = seg[tco + 1:-1]
                inner = tok.decode(inner_ids, skip_special_tokens=False)
                call = HT.parse_call(inner)
                if tco < 0:
                    call["error"] = (call["error"] + "; " if call["error"] else "") + "no <tool_call> in this turn"
                ref = HT.answer_call(graph, call)
                k = len(lock.toks)
                nruns = len(lock.runs)
                lock.qwen([nxt])
                expect = list(lock.toks[k + 1:])
                raw = T.decode_bytes(lock.runs[nruns]) if len(lock.runs) > nruns else b""
                head, tail = b"\n<tool_response>\n", b"\n</tool_response>\n<think>\n\n</think>\n\n"
                wrapped = raw.startswith(head) and raw.endswith(tail)
                res = (raw[len(head):-len(tail)] if wrapped else raw).decode("utf-8", "replace")
                chip_run = sum(t < S.VOCAB for t in expect)
                calls.append({"text": inner, "ids": inner_ids, "fn": call["fn"], "args": call["args"], "raw": call["raw"],
                              "parse_error": call["error"], "result": res, "host_result": ref, "same_as_host": res == ref,
                              "wrapped": wrapped, "chip": chip_run, "echo": len(expect) - chip_run, "cap": len(inner_ids),
                              "response_ids": lock.runs[nruns] if len(lock.runs) > nruns else []})
                segments.append({"by": "tool", "ids": lock.runs[nruns] if len(lock.runs) > nruns else []})
                seg = []
            elif len(seg) >= TURN or gen >= TOTAL:
                segments.append({"by": "qwen", "ids": seg})
                status = "budget"
                break
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
            segments.append({"by": "qwen", "ids": seg})
            status = "walltime"
            break
        chip_in = nxt >= chat.v0
        ts = time.perf_counter()
        hc, logits = chat._layers(nxt, cache, None if chip_in else pos)
        ct = chat.circuit_token(hc)
        if chip_in:
            n_chip += 1
            if ct is None:
                lock_error = {"got": "owner off", "want": "a chip position", "at_call": len(calls)}
                status = "lock"
                break
            nxt = ct
            t_chip += time.perf_counter() - ts
        else:
            pos += 1
            q_tok = int(torch.argmax(logits))
            if ct is not None and q_tok != ct:
                head_bad += 1
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
            t_text += time.perf_counter() - ts
    final = None
    if status == "answered":
        last = tok.decode(segments[-1]["ids"], skip_special_tokens=False)
        final = last.split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    labels = graph.labels
    correct = SC.score(final, q, labels)
    r = {"id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"),
         "status": status, "n_calls": len(calls), "calls": calls, "final": final, "correct": correct,
         "segments": segments, "prompt_ids": prompt, "prompt_tokens": len(prompt), "generated_tokens": gen,
         "seconds": round(time.time() - t0, 2), "prefill_seconds": round(prefill_s, 2), "lock_error": lock_error,
         "head_mismatch": head_bad, "own_ok": own_ok, "chip_tokens": n_chip, "qwen_tokens": n_text_q, "echo_tokens": n_echo,
         "chip_seconds": round(t_chip, 2), "text_seconds": round(t_text, 2), **D.mem()}
    del cache
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--transcript", required=True, help="host transcript whose question ids and order are reused")
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", default="base")
    ap.add_argument("--question-limit-s", type=float, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    ap.add_argument("--ckpt", default=D.CKPT)
    ap.add_argument("--compact", action="store_true", help="chip layers compacted (decode.load_chat); recorded in meta")
    a = ap.parse_args()
    gp, qp = D.graph_path(a.graph)
    g = json.load(open(gp))
    qs = {x["id"]: x for x in json.load(open(qp))["questions"]}
    ids = [json.loads(line)["id"] for line in open(a.transcript)]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        ids = [i for i in ids if i in keep]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(line)["id"] for line in open(a.out)}
    chat, load_s = D.load_chat(a.ckpt, compact=a.compact)
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))  # host/model.py's nq: the base tokenizer's length
    print(f"loaded in {load_s}s {D.mem()}, attn {chat.model.config._attn_implementation}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "a", encoding="utf-8") as f:
        for n, i in enumerate(ids):
            if a.limit is not None and n >= a.limit:
                break
            if i in done:
                continue
            r = run_question(chat, g, qs[i], nq, a.arm, a.question_limit_s)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"q{i}: {r['status']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s chip={r['chip_tokens']} "
                  f"qwen={r['qwen_tokens']} echo={r['echo_tokens']} head_bad={r['head_mismatch']} lock={r['lock_error']} "
                  f"driver={r['mps_driver_gib']} | {(r['final'] or '')[:80]!r}", flush=True)
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
