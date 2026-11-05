"""Qwen drives the machine with the chip layers on the executor: a copy of rvc/drive.py's run_question with the per-position path changed (recorded in DEVLOG). Harness rules, prompts, stops and budgets are unchanged, and each record says what it ran on.

    python drive.py --graph tiny --transcript ../../host/out/dev2/tiny/sdpa.jsonl --only 0,1 --out results/drive/tiny.jsonl --verify seed:7:10000:3600

--verify seed:S:MIN_OWNED:MAX_S  Before the run the seed fixes an order of the questions. They run in that order, and they go through stock chip layers in lockstep with the executor, every position compared dim by dim (bit patterns of the
                                  whole residual), until MIN_OWNED owned positions are verified or MAX_S seconds have been spent; the rest run on the executor alone. The sample's choice is saved first.
--verify all                      every position of every question.
Any mismatch, or the engine leaving its exact range (flags), stops the run: exit code 3, the record says where, and the run's results do not count until explained. The reference lock stays on in every mode.
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402
from chat import ExecChat, seeded_order  # noqa: E402
import fragments as FR  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402  (host/score.py, unchanged)

HT = X.HT
MAX_CALLS, TURN, TOTAL = 12, 768, 3072


class Stop(Exception):
    pass


@torch.no_grad()
def run_question(ec, g, q, nq, arm="base", limit_s=None, verify=False):
    chat = ec.chat
    cx = ec.cx
    T, tok = chat.T, chat.tok
    TCO, TCC = T.TCO, T.TCC
    IM_END, EOS = tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")
    stops = {TCC, IM_END, EOS}
    setup = q.get("setup") or []
    graph = reflib.Graph(g)
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)
    msgs = [{"role": "system", "content": HT.system_prompt(g)}, {"role": "user", "content": q["text"]}]
    prompt = chat.prompt_ids(msgs, tools=HT.tools_for(arm))
    lock = BR.Session(T, __import__("copy").deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    out = chat._prefill(prompt)
    prefill_s = time.time() - t0
    cache = out.past_key_values
    ts = time.time()
    core.snapshot(chat.c, m)
    cx.p.flags = 0
    ec.start(prompt)
    if verify:
        hf.inject(chat.c, cache)
    snap_s = time.time() - ts
    pos = len(prompt)
    nxt = int(torch.argmax(out.logits[0, -1, :nq]))
    t_chip = t_text = t_stock = 0.0
    n_chip = n_text_q = n_echo = 0
    head_bad = 0
    calls, segments = [], []
    seg, gen = [], 0
    expect, lock_error, status = [], None, None
    own_ok = 0
    verified = verified_owned = 0
    verify_mismatch = None
    not_bf16 = 0
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if expect:
            e = expect.pop(0)
            if st != e:
                lock_error = {"want": S.name(e) if e < S.VOCAB else tok.decode([e - S.TEXT_TOKEN]), "got": S.name(st) if st < S.VOCAB else tok.decode([nxt]), "at_call": len(calls), "left": len(expect)}
                status = "lock"
                break
            own_ok += 1
            if nxt < chat.v0:
                n_echo += 1
        elif st < S.VOCAB:
            lock_error = {"got": S.name(st), "want": "text", "at_call": len(calls)}
            status = "lock"
            break
        else:
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
                head, tail = FR.HEAD.encode(), FR.TAIL.encode()
                wrapped = raw.startswith(head) and raw.endswith(tail)
                res = (raw[len(head):-len(tail)] if wrapped else raw).decode("utf-8", "replace")
                chip_run = sum(t < S.VOCAB for t in expect)
                calls.append({"text": inner, "ids": inner_ids, "fn": call["fn"], "args": call["args"], "raw": call["raw"], "parse_error": call["error"], "result": res, "host_result": ref, "same_as_host": res == ref,
                              "wrapped": wrapped, "chip": chip_run, "echo": len(expect) - chip_run, "cap": len(inner_ids), "response_ids": lock.runs[nruns] if len(lock.runs) > nruns else []})
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
        owned_here = bool(expect)                     # the next token comes from the circuit
        if verify:
            # both paths at every position: stock drives, the executor is compared, bit pattern by bit pattern over the whole residual
            tv = time.perf_counter()
            hc, logits = chat._layers(nxt, cache, None if chip_in else pos)
            hcu = hc.detach().cpu().view(torch.uint16).numpy()
            t_stock += time.perf_counter() - tv
            tv = time.perf_counter()
            keep = cx.step(st).copy()
            bits, exact = ec.exec_bits(nxt, keep)
            t_chip += time.perf_counter() - tv
            not_bf16 += not exact
            verified += 1
            verified_owned += owned_here
            if not np.array_equal(hcu, bits):
                dd = np.nonzero(hcu != bits)[0]
                verify_mismatch = {"at_call": len(calls), "mid": nxt, "dims": [{"dim": int(d), "stock": hex(int(hcu[d])), "exec": hex(int(bits[d]))} for d in dd[:16]], "n_dims": int(len(dd))}
                status = "verify_mismatch"
                break
            ct = chat.circuit_token(hc)
            if chip_in:
                n_chip += 1
                if ct is None:
                    lock_error = {"got": "owner off", "want": "a chip position", "at_call": len(calls)}
                    status = "lock"
                    break
                nxt = ct
            else:
                pos += 1
                q_tok = int(torch.argmax(logits))
                if ct is not None and q_tok != ct:
                    head_bad += 1
                nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
        elif chip_in:
            # a chip token: a burst on the engine, as far as the reference says the run goes, with the lock checked on the whole burst
            ts = time.perf_counter()
            limit = sum(1 for _ in expect) + 1
            stname, t_next, n, rec = cx.burst(st, limit, record=True)
            t_chip += time.perf_counter() - ts
            n_chip += n
            if stname == "owner_off":
                lock_error = {"got": "owner off", "want": "a chip position", "at_call": len(calls)}
                status = "lock"
                break
            if stname == "decode":
                lock_error = {"got": "a code naming no token", "at_call": len(calls)}
                status = "lock"
                break
            chain = rec[: n - 1]                          # the next token after the last step is t_next: the top of the loop checks it
            want = np.array(expect[: n - 1], np.int32)
            if len(want) != len(chain) or not np.array_equal(want, chain):
                j = next((i for i in range(min(len(want), len(chain))) if want[i] != chain[i]), min(len(want), len(chain)))
                lock_error = {"want": S.name(int(want[j])) if j < len(want) and want[j] < S.VOCAB else "text or end", "got": S.name(int(chain[j])) if j < len(chain) and chain[j] < S.VOCAB else "text or end", "at_call": len(calls), "left": len(expect) - j}
                status = "lock"
                break
            del expect[: n - 1]
            own_ok += n - 1
            nxt = chat.v0 + t_next if t_next < S.VOCAB else t_next - S.TEXT_TOKEN
        else:
            ts = time.perf_counter()
            keep = cx.step(st).copy()
            hc = ec.hc(nxt, keep)
            logits = chat._qwen_step(hc, cache, pos)
            ct = ec.code_token(keep)
            pos += 1
            q_tok = int(torch.argmax(logits))
            if ct is not None and q_tok != ct:
                head_bad += 1
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
            t_text += time.perf_counter() - ts
        if cx.p.flags:
            verify_mismatch = {"engine_flags": cx.flags(), "at_call": len(calls)}
            status = "engine_flag"
            break
    state = ec.state_diff(cache) if verify and status != "verify_mismatch" else None
    if state and state["big"]:
        verify_mismatch = {"state": state, "at_call": len(calls)}
        status = "verify_mismatch"
    final = None
    if status == "answered":
        last = tok.decode(segments[-1]["ids"], skip_special_tokens=False)
        final = last.split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    correct = SC.score(final, q, graph.labels)
    r = {"id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"), "status": status, "n_calls": len(calls), "calls": calls, "final": final, "correct": correct,
         "segments": segments, "prompt_ids": prompt, "prompt_tokens": len(prompt), "generated_tokens": gen, "seconds": round(time.time() - t0, 2), "prefill_seconds": round(prefill_s, 2), "snapshot_seconds": round(snap_s, 3), "lock_error": lock_error,
         "head_mismatch": head_bad, "own_ok": own_ok, "chip_tokens": n_chip, "qwen_tokens": n_text_q, "echo_tokens": n_echo, "chip_seconds": round(t_chip, 3), "text_seconds": round(t_text, 2), "stock_seconds": round(t_stock, 2),
         "ran_on": "stock+executor lockstep" if verify else "executor", "verified_positions": verified, "verified_owned": verified_owned, "verify_mismatch": verify_mismatch, "end_state_diff": state, "kept_not_bf16": not_bf16, "engine": cx.lib_hash, "engine_flags": cx.flags(), **D.mem()}
    del cache
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--transcript", required=True, help="host transcript whose question ids are reused")
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", default="base")
    ap.add_argument("--question-limit-s", type=float, default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ckpt", default=C.CKPT)
    ap.add_argument("--verify", default=None, help="all | seed:S:MIN_OWNED:MAX_S")
    ap.add_argument("--negative", default=None, help="a saved control: before the run, a JSON corruption (check_trace.apply_corruption's form) on a second engine, verified on the first question; the mode must stop it. Written to this path.")
    a = ap.parse_args()
    gp, qp = D.graph_path(a.graph)
    g = json.load(open(gp))
    qs = {x["id"]: x for x in json.load(open(qp))["questions"]}
    ids = [json.loads(line)["id"] for line in open(a.transcript)]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        ids = [i for i in ids if i in keep]
    if a.limit is not None:
        ids = ids[: a.limit]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(line)["id"] for line in open(a.out)}
    vmode, min_owned, max_s, seed = None, 0, 0, None
    if a.verify == "all":
        vmode = "all"
    elif a.verify:
        _, s_, o_, m_ = a.verify.split(":")
        vmode, seed, min_owned, max_s = "sample", int(s_), int(o_), float(m_)
        ids = seeded_order(ids, seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    if vmode:
        json.dump({"verify": a.verify, "order": ids, "time": time.strftime("%Y-%m-%d %H:%M:%S")}, open(a.out + ".verify.json", "w"))
    t0 = time.time()
    ec = ExecChat(a.ckpt)
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    print(f"loaded {time.time() - t0:.0f}s {D.mem()} engine {ec.cx.lib_hash} verify {a.verify}", flush=True)
    if a.negative:
        from cexec import CExec
        good = ec.cx
        mut = {"table": "tw", "u": 0.8988382879679935, "how": "plus_bit"}       # caught at position 128 of tiny-ten in results/negative_tables_dev.json
        def corrupt(A):
            i = int(mut["u"] * len(A[mut["table"]]))
            mut["index"], mut["old"] = i, float(A[mut["table"]][i])
            A[mut["table"]][i] = mut["old"] * (1 + 1 / 128)
            mut["new"] = float(A[mut["table"]][i])
        ec.cx = CExec(ec.chat.c, ec.chat.T, corrupt=corrupt)
        r = run_question(ec, g, qs[ids[0]], nq, a.arm, a.question_limit_s, verify=True)
        ec.cx = good
        json.dump({"corruption": mut, "question": ids[0], "status": r["status"], "stopped": r["status"] == "verify_mismatch", "verify_mismatch": r["verify_mismatch"], "verified_positions": r["verified_positions"], "engine": r["engine"]}, open(a.negative, "w"), indent=1)
        print(f"negative control: status {r['status']} after {r['verified_positions']} positions: {r['verify_mismatch']}", flush=True)
        torch.mps.empty_cache()
    v_owned = v_seconds = 0
    with open(a.out, "a", encoding="utf-8") as f:
        for i in ids:
            if i in done:
                continue
            verify = vmode == "all" or (vmode == "sample" and v_owned < min_owned and v_seconds < max_s)
            r = run_question(ec, g, qs[i], nq, a.arm, a.question_limit_s, verify=verify)
            if verify:
                v_owned += r["verified_owned"]
                v_seconds += r["seconds"]
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"q{i}: {r['status']} on {r['ran_on']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s chip={r['chip_tokens']} ({r['chip_tokens'] / max(r['chip_seconds'], 1e-9):.0f}/s) qwen={r['qwen_tokens']} echo={r['echo_tokens']} head_bad={r['head_mismatch']} lock={r['lock_error']} verified_owned={r['verified_owned']} mismatch={r['verify_mismatch']} driver={r['mps_driver_gib']} | {(r['final'] or '')[:60]!r}", flush=True)
            torch.mps.empty_cache()
            if r["status"] in ("verify_mismatch", "engine_flag"):
                print("STOP: the executor disagreed; this run's results do not count until explained", flush=True)
                sys.exit(3)
    if vmode == "sample":
        print(f"verified {v_owned} owned positions in {v_seconds:.0f}s (asked for {min_owned}, at most {max_s:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
