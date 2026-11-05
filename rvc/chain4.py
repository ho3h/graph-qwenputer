"""Can retries rescue a wrong name? chain3's setup (told, no rule, chase only, fw firmware, exec engine), the first attempt unchanged, and a changed retry turn.

    python chain4.py --arm both --questions wrong27 --out results/chain4/both [--stock c006:192]
    python chain4.py --arm both --questions results/chain4_draw.json --out results/chain4_fresh       # a draw file's questions and stock sample
    python chain4.py --ir-check results/chain4_ir.json

What may change, and only after a line the query itself got wrong (QUERY_ERRORS; END, MULTI, NOCHANGE and the like are results and keep chain3's flow):
- prefill: the retry turn starts with <tool_call>, so it cannot open with prose. Inside the call Qwen writes everything.
- note: one fixed sentence, printed by this runner after the machine's echo, in byte tokens, on a NONE line only. A real machine would need firmware to print it, and could
  print it inside the response; here it follows </think>. No line names, no stripping of any word, no change to what the machine is asked.
Every machine token stays locked to bridge.Session; runner tokens go to the lock as history.
"""
import argparse
import copy
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chain3 as C3  # noqa: E402  (points rvc/box.py at fw/build/fw.elf)
import box as X  # noqa: E402
import chain2 as C2  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402

HT, ERROR, HEAD, TAIL, RETRIES, TURN = X.HT, C2.ERROR, C2.HEAD, C2.TAIL, C2.RETRIES, C2.TURN
QUERY_ERRORS = {"NONE", "NORELATION", "AMBIGUOUS", "BADARG", "NOFUNCTION", "TOOLONG"}
NOTE_G = "No node has exactly that name; call again with only the node's name, without any word that just describes it."
NOTE_Q = "No node has exactly that name; use the name as written in the question."
ARMS = {"prefill": (True, None), "note": (False, NOTE_G), "both": (True, NOTE_G), "both_q": (True, NOTE_Q), "baseline": (False, None)}


def byte_ids(T, s):
    return [T.printable[b] for b in s.encode()]


@torch.no_grad()
def run_question(ec, g, q, nq, limit_s, tool, prefill, note, verify=False, readback=0):
    chat, cx = ec.chat, ec.cx
    T, tok = chat.T, chat.tok
    stops = {T.TCC, tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}
    graph = reflib.Graph(g)
    setup = q.get("setup") or []
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)
    msgs = [{"role": "system", "content": HT.system_prompt(g) + C2.EXTRA + C2.TOLD}, {"role": "user", "content": q["text"]}]
    prompt = chat.prompt_ids(msgs, tools=[tool])
    lock = BR.Session(T, copy.deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    out = chat._prefill(prompt)
    cache = out.past_key_values
    core.snapshot(chat.c, m)
    cx.p.flags = 0
    ec.start(prompt)
    if verify:
        hf.inject(chat.c, cache)
    pos = len(prompt)
    nxt = int(torch.argmax(out.logits[0, -1, :nq]))
    t_chip = t_text = t_stock = 0.0
    n_chip = n_qwen = n_echo = n_forced = head_bad = own_ok = fired_forced = verified = 0
    calls, seg, echo, expect, forced = [], [], [], [], []
    feeding = seed_tco = False
    answer, status, lock_error, attempt, mismatch, no_call_text = None, None, None, 0, None, None
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if feeding:                                       # the runner's tokens
            n_forced += 1
            if not forced:
                seg = [T.TCO] if seed_tco else []
        elif expect:
            e = expect.pop(0)
            if st != e:
                lock_error = {"want": S.name(e) if e < S.VOCAB else tok.decode([e - S.TEXT_TOKEN]),
                              "got": S.name(st) if st < S.VOCAB else tok.decode([nxt]), "at_call": len(calls)}
                status = "lock"
                break
            own_ok += 1
            if nxt < chat.v0:
                n_echo += 1
                echo.append(nxt)
            if not expect:
                raw = T.decode_bytes(echo)
                wrapped = raw.startswith(HEAD) and raw.endswith(TAIL)
                res = (raw[len(HEAD):-len(TAIL)] if wrapped else raw).decode("utf-8", "replace")
                calls[-1].update(result=res, wrapped=wrapped, same_as_host=res == calls[-1]["host_result"], response_ids=echo, echo=len(echo))
                answer = res
                em = ERROR.match(res)
                if not em or attempt == RETRIES:
                    status = "answered"
                    break
                attempt += 1
                seg, echo = [], []
                word = em.group(1)
                seed_tco = prefill and word in QUERY_ERRORS
                forced = []
                if note and word == "NONE":
                    forced += byte_ids(T, note) + [T.printable[10]] * 2
                if seed_tco:
                    forced.append(T.TCO)
                if forced:
                    lock.history(forced)
        elif st < S.VOCAB:
            lock_error = {"got": S.name(st), "want": "text", "at_call": len(calls)}
            status = "lock"
            break
        else:
            seg.append(nxt)
            n_qwen += 1
            if nxt in stops or len(seg) >= TURN:
                if nxt != T.TCC:
                    status = "no_call"
                    no_call_text = tok.decode(seg, skip_special_tokens=False)
                    break
                tco = max((i for i, t in enumerate(seg) if t == T.TCO), default=-1)
                ids = seg[tco + 1:-1]
                call = HT.parse_call(tok.decode(ids, skip_special_tokens=False))
                k = len(lock.toks)
                lock.qwen([nxt])
                expect = list(lock.toks[k + 1:])
                calls.append({"text": tok.decode(ids, skip_special_tokens=False), "ids": ids, "fn": call["fn"], "args": call["args"], "no_tco": tco < 0,
                              "host_result": HT.answer_call(graph, call), "cap": len(ids), "chip": sum(t < S.VOCAB for t in expect), "machine_ran": True})
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
            status = "walltime"
            break
        chip_in = nxt >= chat.v0
        if verify:
            tv = time.perf_counter()
            hc, logits = chat._layers(nxt, cache, None if chip_in else pos)
            hcu = hc.detach().cpu().view(torch.uint16).numpy()
            t_stock += time.perf_counter() - tv
            tv = time.perf_counter()
            keep = cx.step(st).copy()
            bits, _ = ec.exec_bits(nxt, keep)
            t_chip += time.perf_counter() - tv
            verified += 1
            if not np.array_equal(hcu, bits):
                dd = np.nonzero(hcu != bits)[0]
                mismatch = {"at_call": len(calls), "mid": nxt, "n_dims": int(len(dd)), "dims": [int(d) for d in dd[:16]]}
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
                top = int(torch.argmax(logits))
                if ct is not None and top != ct:
                    head_bad += 1
                nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
        elif chip_in:
            ts = time.perf_counter()
            stname, t_next, n, rec_ = cx.burst(st, len(expect) + 1, record=True)
            t_chip += time.perf_counter() - ts
            n_chip += n
            if stname in ("owner_off", "decode"):
                lock_error = {"got": stname, "want": "a chip position", "at_call": len(calls)}
                status = "lock"
                break
            chain = rec_[: n - 1]
            want = np.array(expect[: n - 1], np.int32)
            if len(want) != len(chain) or not np.array_equal(want, chain):
                lock_error = {"got": "burst differs from the reference", "at_call": len(calls)}
                status = "lock"
                break
            del expect[: n - 1]
            own_ok += n - 1
            nxt = chat.v0 + t_next if t_next < S.VOCAB else t_next - S.TEXT_TOKEN
            ct = None
        else:
            ts = time.perf_counter()
            keep = cx.step(st).copy()
            logits = chat._qwen_step(ec.hc(nxt, keep), cache, pos)
            ct = ec.code_token(keep)
            pos += 1
            top = int(torch.argmax(logits))
            if ct is not None and top != ct:
                head_bad += 1
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
            t_text += time.perf_counter() - ts
        if cx.p.flags:
            mismatch = {"engine_flags": cx.flags(), "at_call": len(calls)}
            status = "engine_flag"
            break
        if forced:                                        # the runner sets the next token, and the circuit must not be claiming it
            if ct is not None:
                fired_forced += 1
            nxt, feeding = forced.pop(0), True
        else:
            if feeding and ct is not None:
                fired_forced += 1
            feeding = False
    rb_ids, rb_end, t_rb = [], None, 0.0
    if readback and status == "answered":             # after the graded line: Qwen's own words, kept apart. The answer is already fixed
        t1 = time.time()
        rb_end = "cap"
        for _ in range(readback):
            st = BR.text_token(nxt)
            if verify:
                hc, logits = chat._layers(nxt, cache, pos)
                hcu = hc.detach().cpu().view(torch.uint16).numpy()
                keep = cx.step(st).copy()
                bits, _ = ec.exec_bits(nxt, keep)
                verified += 1
                if not np.array_equal(hcu, bits):
                    mismatch, status = {"at": "readback", "n_dims": int((hcu != bits).sum())}, "verify_mismatch"
                    break
                ct = chat.circuit_token(hc)
            else:
                keep = cx.step(st).copy()
                logits = chat._qwen_step(ec.hc(nxt, keep), cache, pos)
                ct = ec.code_token(keep)
            pos += 1
            if ct is not None:
                fired_forced += 1
            nxt = int(torch.argmax(logits[:nq]))
            if nxt in stops or nxt == T.TCO:
                rb_end = "tool_call" if nxt == T.TCO else "stop"
                break
            rb_ids.append(nxt)
        t_rb = time.time() - t1
    state = ec.state_diff(cache) if verify and status != "verify_mismatch" else None
    if state and state["big"]:
        mismatch, status = {"state": state}, "verify_mismatch"
    del cache
    return {"id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"),
            "status": status, "n_calls": len(calls), "calls": calls, "final": answer,
            "correct": SC.score(answer, q, graph.labels) if answer is not None else False, "no_call_text": no_call_text,
            "prompt_tokens": len(prompt), "lock_error": lock_error, "head_mismatch": head_bad, "own_ok": own_ok, "chip_tokens": n_chip,
            "qwen_tokens": n_qwen, "echo_tokens": n_echo, "runner_tokens": n_forced, "owner_fired_on_runner_tokens": fired_forced,
            "chip_seconds": round(t_chip, 3), "text_seconds": round(t_text, 2), "stock_seconds": round(t_stock, 2),
            "seconds": round(time.time() - t0, 2), "ran_on": "stock+executor lockstep" if verify else "executor",
            "verified_positions": verified, "verify_mismatch": mismatch, "end_state_diff": state, "engine": cx.lib_hash,
            "readback_text": tok.decode(rb_ids, skip_special_tokens=False) if rb_end else None, "readback_tokens": len(rb_ids), "readback_end": rb_end,
            "readback_seconds": round(t_rb, 2), **D.mem()}


def after_error(r):
    """What Qwen did after its first error line."""
    c = r["calls"]
    if len(c) == 1:
        return "no call: " + ("budget" if r["qwen_tokens"] >= 600 else "short text")
    starts = [str(x["args"].get("start", "")).strip() for x in c]
    if all(s == starts[0] for s in starts):
        return "repeated the same start"
    return "changed the start"


def tally(out, baseline=None):
    t = C3.tally(out, None)
    rs = [json.loads(line) for line in open(os.path.join(out, "all.jsonl"))]
    wrong = [r for r in rs if r["outcome"]["first_error"] and not r["outcome"]["first_correct"]]
    limit = [r for r in rs if r["outcome"]["first_error"] and r["outcome"]["first_correct"]]
    t["after_first_wrong_line"] = {}
    for r in wrong:
        k = after_error(r)
        t["after_first_wrong_line"][k] = t["after_first_wrong_line"].get(k, 0) + 1
    t["silent_detail"] = [[r["graph"], r["id"], [(c["args"].get("start"), c["args"].get("legs"), c.get("result", "")[:40]) for c in r["calls"]], r["gold_text"][:50], r["outcome"]["kind"]]
                          for r in rs if r["outcome"]["outcome"] == "silent"]
    t["limit_line_questions"] = {"first_correct": len(limit), "retry_calls": sum(r["n_calls"] - 1 for r in limit), "stayed_correct": sum(r["outcome"]["outcome"] == "correct" for r in limit),
                                 "extra_chip": sum(c.get("chip", 0) for r in limit for c in r["calls"][1:]), "budget_prose": sum(r["status"] == "no_call" and r["qwen_tokens"] >= 600 for r in limit)}
    t["first_attempt_same_as_chain3"] = [sum(bool(r.get("first_same")) for r in rs), sum(r.get("first_same") is not None for r in rs)]
    t["runner_tokens"] = sum(r["runner_tokens"] for r in rs)
    t["owner_fired_on_runner_tokens"] = sum(r["owner_fired_on_runner_tokens"] for r in rs)
    json.dump(t, open(os.path.join(out, "tally.json"), "w"), indent=1, ensure_ascii=False)
    return t


def ir_check(path):
    """On the circuit's IR: a NONE, then a note and a forced <tool_call>, then Qwen's tokens and a real run. Owned positions and the owner bit must stay exact."""
    import ir_check as IC
    from chipformer.q35 import ir
    T = BR.Text(X.tokenizer_json())
    c = core.build(IC.target(), T)
    g = json.load(open(D.graph_path("tiny")[0]))
    m, m2 = X.machine_for(g), X.machine_for(g)
    core.snapshot(c, m2)
    ses = BR.Session(T, m)
    ses.qwen([T.TCO] + T.encode(X.template_text("chase", {"start": "Eastgate station", "legs": "red westbound 1"})) + [T.TCC])
    ses.history(byte_ids(T, NOTE_G) + [T.printable[10]] * 2 + [T.TCO])
    ses.qwen(T.encode(X.template_text("chase", {"start": "Eastgate", "legs": "red westbound 1"})) + [T.TCC])
    ses.history([T.TCO])
    ses.qwen(T.encode(X.template_text("find", {"name": "Ōtaki"})) + [T.TCC])
    st = ses.toks
    carry, mats = {}, []
    t0 = time.time()
    for a in range(0, len(st), 2048):
        mats.append(ir.evaluate(c, st[a:a + 2048], carry=carry))
    mat = np.concatenate(mats)
    pred = core.predictions(c, mat)
    own = np.rint(ir.ev(c.owner, mat)).astype(int)
    bad_own = [x for x in range(len(st)) if own[x] != int(ses.own[x])]
    bad = [x for x in range(len(st) - 1) if ses.own[x] and pred[x] != st[x + 1]]
    res = {"firmware_sha256": __import__("hashlib").sha256(open(X.build_elf(), "rb").read()).hexdigest(), "positions": len(st), "owned": int(sum(ses.own)), "wrong_predictions": len(bad), "owner_mismatch": len(bad_own),
           "first_wrong": bad[:3], "first_owner": bad_own[:3], "seconds": round(time.time() - t0, 1), "results": [T.decode_bytes(e).decode("utf-8", "replace") for e in ses.runs]}
    json.dump(res, open(path, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--questions", help="wrong27, or a draw file")
    ap.add_argument("--out")
    ap.add_argument("--stock", default="", help="graph:id,... stock and executor together; a draw file's stock_sample is added")
    ap.add_argument("--question-limit-s", type=float, default=1800)
    ap.add_argument("--ir-check")
    ap.add_argument("--readback", type=int, default=0, help="after the graded line, let Qwen write up to this many tokens, kept apart")
    a = ap.parse_args()
    if a.ir_check:
        return ir_check(a.ir_check)
    prefill, note = ARMS[a.arm]
    ch3 = {(r["graph"], r["id"]): r for r in map(json.loads, open(os.path.join(HERE, "results", "chain3", "all.jsonl")))}
    stock = {tuple(x.rsplit(":", 1)) for x in a.stock.split(",") if x}
    stock = {(g, int(i)) for g, i in stock}
    if a.questions == "wrong27":
        keys = [k for k, r in ch3.items() if r["outcome"]["first_error"] and not r["outcome"]["first_correct"]]
        assert len(keys) == 27
    else:
        d = json.load(open(a.questions))
        keys = [tuple(k) for k in d["draw"]]
        stock |= {tuple(k) for k in d["stock_sample"]}
        assert not set(keys) & set(ch3), "the draw overlaps chain3"
        assert hashlib_of(X.build_elf()) == d["firmware_sha256"]
    sys.path.append(os.path.join(X.X210, "exec"))
    from chat import ExecChat
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    t0 = time.time()
    ec = ExecChat(D.CKPT)
    load_s = round(time.time() - t0, 1)
    tool = C2.chase_tool("")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "all.jsonl")
    done = {(json.loads(line)["graph"], json.loads(line)["id"]) for line in open(path)} if os.path.exists(path) else set()
    json.dump({"arm": a.arm, "prefill": prefill, "note": note, "query_errors": sorted(QUERY_ERRORS), "questions": a.questions, "stock": sorted(map(list, stock)), "ckpt": D.CKPT,
               "firmware_sha256": hashlib_of(X.build_elf()), "engine": ec.cx.lib_hash, "told": C2.TOLD, "extra": C2.EXTRA, "tool": tool, "retries": RETRIES, "turn": TURN,
               "load_seconds": load_s, "question_limit_s": a.question_limit_s, "readback": a.readback, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "attn": ec.chat.model.config._attn_implementation},
              open(os.path.join(a.out, "meta.json"), "w"), indent=1, ensure_ascii=False)
    print(f"loaded {load_s}s {D.mem()} engine {ec.cx.lib_hash} arm {a.arm}", flush=True)
    with open(path, "a", encoding="utf-8") as f:
        for gname, i in keys:
            if (gname, i) in done:
                continue
            gp, qp = D.graph_path(gname)
            g = json.load(open(gp))
            q = {x["id"]: x for x in json.load(open(qp))["questions"]}[i]
            r = run_question(ec, g, q, nq, a.question_limit_s, tool, prefill, note, verify=(gname, i) in stock, readback=a.readback)
            r["graph"] = gname
            r["outcome"] = C3.classify(g, q, r)
            if (gname, i) in ch3:
                r["first_same"] = bool(r["calls"]) and r["calls"][0]["ids"] == ch3[gname, i]["calls"][0]["ids"]
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{gname} q{i}: {r['outcome']['outcome']} {r['outcome']['kind']} on {r['ran_on']} status={r['status']} calls={r['n_calls']} {r['seconds']}s chip={r['chip_tokens']} qwen={r['qwen_tokens']} echo={r['echo_tokens']} "
                  f"first_same={r.get('first_same')} lock={r['lock_error']} head_bad={r['head_mismatch']} fired={r['owner_fired_on_runner_tokens']} verified={r['verified_positions']} mismatch={r['verify_mismatch']} | "
                  f"{[(c['args'].get('start'), c.get('result', '')[:28]) for c in r['calls']]}", flush=True)
            torch.mps.empty_cache()
            tally(a.out)
            if r["status"] in ("verify_mismatch", "engine_flag"):
                print("STOP: the executor disagreed; this run's results do not count until explained", flush=True)
                sys.exit(3)
    print(json.dumps({k: v for k, v in tally(a.out).items() if k not in ("by_case",)}, ensure_ascii=False), flush=True)


def hashlib_of(path):
    return __import__("hashlib").sha256(open(path, "rb").read()).hexdigest()


if __name__ == "__main__":
    main()
