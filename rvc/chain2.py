"""The follow-up chain: rb's told sentence and a handle rule, on the same 17 chase questions, chip side on exec/'s engine.

    python chain2.py --out results/chain2 --verify c024:1,c025:200      # from the vendored folder, under tools/memguard.py
    python chain2.py --ir-check results/chain2_ir.json                  # a runner line on the circuit's IR, no weights

A copy of chain.py's loop with exec/drive.py's per-position path. The handle rule lives here, in the runner, not in the firmware: its line
is fed as text tokens after </tool_call>, the machine does not run, and the lock takes those tokens as history. Questions in --verify run stock
and executor together, stock driving, every position compared bit for bit over the whole residual; a mismatch or an engine flag stops the run.
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
import box as X  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402

HT = X.HT
GRAPHS = {"tiny": "tiny", "c024": "cities/c024", "c025": "cities/c025", "r001": "random/r001"}
RETRIES, TURN = 2, 768
EXTRA = "\nMake exactly one tool call that answers the question. Its result is shown to the user as your answer."
TOLD = " Tool responses arrive spelled out one character at a time; read them as ordinary text."
RULE = " Use a handle in start only if a tool response has already printed it; otherwise give the node's exact name."
RULE_Q = " Use a handle in start only if the question gives it or a tool response has already printed it; otherwise give the node's exact name."
ERROR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG)\b")
HEAD, TAIL = b"\n<tool_response>\n", b"\n</tool_response>\n<think>\n\n</think>\n\n"


class Stop(Exception):
    pass


def chase_tool(rule=RULE):
    t = copy.deepcopy([x for x in HT.tools_for("base") if x["function"]["name"] == "chase"][0])
    t["function"]["description"] += rule
    return t


def echo_ids(T, line):
    """Exactly the machine's echo of a line: the wrapping, and one token per byte."""
    nl = T.printable[10]
    ts, te, tk, tke = T.printable[256:260]
    return [nl, ts, nl] + [T.printable[b] for b in line.encode()] + [nl, te, nl, tk, nl, nl, tke, nl, nl]


def rule_line(args, printed, allowed_extra=frozenset()):
    """The runner's line for an unprinted handle in start, or None when the machine should run."""
    s = str(args.get("start", "")).strip()
    if not s.startswith("@"):
        return None
    m = re.match(r"@(\d+)", s)
    if m and (int(m.group(1)) in printed or int(m.group(1)) in allowed_extra):
        return None
    return f"NONE {s}"


@torch.no_grad()
def run_question(ec, g, q, nq, limit_s, tool, verify=False, question_handles=False, told=True, rule=True):
    chat, cx = ec.chat, ec.cx
    T, tok = chat.T, chat.tok
    stops = {T.TCC, tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}
    graph = reflib.Graph(g)
    setup = q.get("setup") or []
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)
    msgs = [{"role": "system", "content": HT.system_prompt(g) + EXTRA + (TOLD if told else "")}, {"role": "user", "content": q["text"]}]
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
    extra = frozenset(int(x) for x in re.findall(r"@(\d+)", q["text"])) if question_handles else frozenset()
    printed = set()
    t_chip = t_text = t_stock = 0.0
    n_chip = n_qwen = n_echo = n_forced = head_bad = own_ok = fired_forced = verified = 0
    calls, seg, echo, expect, forced = [], [], [], [], []
    feeding = False
    answer, status, lock_error, attempt, mismatch, no_call_text = None, None, None, 0, None, None
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if feeding:                                       # the runner's line
            n_forced += 1
            if not forced:                                # its last token: back to Qwen after this position
                attempt += 1
                seg, echo = [], []
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
                c = calls[-1]
                c.update(result=res, wrapped=wrapped, same_as_host=res == c["host_result"], response_ids=echo, echo=len(echo))
                printed |= {int(x) for x in re.findall(r"@(\d+)", res)}
                answer = res
                if not ERROR.match(res) or attempt == RETRIES:
                    status = "answered"
                    break
                attempt += 1
                seg, echo = [], []
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
                inner = tok.decode(ids, skip_special_tokens=False)
                call = HT.parse_call(inner)
                host = HT.answer_call(graph, call)
                line = rule_line(call["args"], printed, extra) if rule else None
                rec = {"text": inner, "ids": ids, "fn": call["fn"], "args": call["args"], "no_tco": tco < 0, "host_result": host,
                       "cap": len(ids), "machine_ran": line is None}
                calls.append(rec)
                if line is None:
                    k = len(lock.toks)
                    lock.qwen([nxt])
                    expect = list(lock.toks[k + 1:])
                    rec["chip"] = sum(t < S.VOCAB for t in expect)
                else:
                    rec.update(result=line, chip=0, same_as_host=None)
                    answer = line
                    if attempt == RETRIES:
                        status = "answered"
                        break
                    forced = echo_ids(T, line)
                    lock.history([nxt])
                    lock.history(forced)
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
            status = "walltime"
            break
        chip_in = nxt >= chat.v0
        just_tcc = nxt == T.TCC
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
                if ct is not None and top != ct and not forced:
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
            if ct is not None and top != ct and not forced:
                head_bad += 1
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
            t_text += time.perf_counter() - ts
        if cx.p.flags:
            mismatch = {"engine_flags": cx.flags(), "at_call": len(calls)}
            status = "engine_flag"
            break
        if forced:                                        # the runner overrides the next token
            if ct is not None and not just_tcc:
                fired_forced += 1
            nxt, feeding = forced.pop(0), True
        else:
            if feeding and ct is not None:
                fired_forced += 1
            feeding = False
    state = ec.state_diff(cache) if verify and status != "verify_mismatch" else None
    if state and state["big"]:
        mismatch, status = {"state": state}, "verify_mismatch"
    del cache
    return {"id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"),
            "status": status, "n_calls": len(calls), "calls": calls, "final": answer,
            "correct": SC.score(answer, q, graph.labels) if answer is not None else False, "no_call_text": no_call_text,
            "prompt_tokens": len(prompt), "lock_error": lock_error, "head_mismatch": head_bad, "own_ok": own_ok, "chip_tokens": n_chip,
            "qwen_tokens": n_qwen, "echo_tokens": n_echo, "runner_line_tokens": n_forced, "owner_fired_on_runner_line": fired_forced,
            "chip_seconds": round(t_chip, 3), "text_seconds": round(t_text, 2), "stock_seconds": round(t_stock, 2),
            "seconds": round(time.time() - t0, 2), "ran_on": "stock+executor lockstep" if verify else "executor",
            "verified_positions": verified, "verify_mismatch": mismatch, "end_state_diff": state, "engine": cx.lib_hash, **D.mem()}


def tally(out):
    rs = {}
    for name in GRAPHS:
        p = os.path.join(out, f"{name}.jsonl")
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                rs[name, r["id"]] = r
    v = list(rs.values())
    calls = [c for r in v for c in r["calls"]]
    machine = [c for c in calls if c["machine_ran"]]
    first_error = [k for k, r in rs.items() if r["calls"] and ERROR.match(r["calls"][0].get("result", ""))]
    silent = [k for k, r in rs.items() if r["final"] is not None and not ERROR.match(r["final"]) and not r["correct"]]
    t = {"questions": len(v), "correct": sum(bool(r["correct"]) for r in v), "status": {}, "calls": len(calls),
         "machine_calls": len(machine), "runner_lines": len(calls) - len(machine),
         "machine_lines_equal_host_tool": sum(bool(c.get("same_as_host")) for c in machine),
         "first_line_error": len(first_error), "rescued": sum(bool(rs[k]["correct"]) for k in first_error),
         "correct_on_first_line": sum(1 for k, r in rs.items() if r["calls"] and k not in first_error and r["correct"]),
         "silent_wrong": [list(k) for k in silent], "lock_errors": sum(r["lock_error"] is not None for r in v),
         "head_mismatch": sum(r["head_mismatch"] for r in v), "own_ok": sum(r["own_ok"] for r in v),
         "owner_fired_on_runner_line": sum(r["owner_fired_on_runner_line"] for r in v),
         "chip_tokens": sum(r["chip_tokens"] for r in v), "qwen_tokens": sum(r["qwen_tokens"] for r in v), "echo_tokens": sum(r["echo_tokens"] for r in v),
         "runner_line_tokens": sum(r["runner_line_tokens"] for r in v), "seconds": round(sum(r["seconds"] for r in v), 1),
         "chip_seconds": round(sum(r["chip_seconds"] for r in v), 1), "text_seconds": round(sum(r["text_seconds"] for r in v), 1),
         "verified_positions": sum(r["verified_positions"] for r in v), "max_cap": max((c["cap"] for c in calls), default=0),
         "per_question": [[k[0], k[1], r["ran_on"], r["status"], r["n_calls"], r["correct"], r["seconds"],
                           [(c["args"].get("start"), c["result"][:36], c["machine_ran"]) for c in r["calls"] if "result" in c]] for k, r in rs.items()]}
    for r in v:
        t["status"][r["status"]] = t["status"].get(r["status"], 0) + 1
    json.dump(t, open(os.path.join(out, "tally.json"), "w"), indent=1, ensure_ascii=False)
    return t


def ir_check(path):
    """On the circuit's IR: a machine call, then a runner line (</tool_call> and no GO), then machine calls. Everything owned must still be exact."""
    import ir_check as IC
    from chipformer.q35 import ir
    T = BR.Text(X.tokenizer_json())
    c = core.build(IC.target(), T)
    g = json.load(open(D.graph_path("tiny")[0]))
    m, m2 = X.machine_for(g), X.machine_for(g)
    core.snapshot(c, m2)
    ses = BR.Session(T, m)
    skip = set()
    def real(fn, a):
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, a)) + [T.TCC])
    def runner(fn, a, line):
        ses.history([T.TCO] + T.encode(X.template_text(fn, a)) + [T.TCC])
        skip.add(len(ses.toks) - 1)
        ses.history(echo_ids(T, line))
    real("find", {"name": "Eastgate"})
    runner("chase", {"start": "@109", "legs": "red eastbound 1"}, "NONE @109")
    real("chase", {"start": "@3", "legs": "red westbound 1"})
    runner("chase", {"start": "@7", "legs": "blue southbound 1"}, "NONE @7")
    real("find", {"name": "Ōtaki"})
    st = ses.toks
    carry, mats = {}, []
    t0 = time.time()
    for a in range(0, len(st), 2048):
        mats.append(ir.evaluate(c, st[a:a + 2048], carry=carry))
    mat = np.concatenate(mats)
    pred = core.predictions(c, mat)
    own = np.rint(ir.ev(c.owner, mat)).astype(int)
    bad_own = [x for x in range(len(st)) if own[x] != int(ses.own[x])]
    bad = [x for x in range(len(st) - 1) if ses.own[x] and x not in skip and pred[x] != st[x + 1]]
    res = {"positions": len(st), "owned": int(sum(ses.own)) - len(skip), "wrong_predictions": len(bad), "owner_mismatch": len(bad_own),
           "first_wrong": bad[:3], "first_owner": bad_own[:3], "runner_lines": len(skip), "seconds": round(time.time() - t0, 1),
           "results": [T.decode_bytes(e).decode("utf-8", "replace") for e in ses.runs]}
    json.dump(res, open(path, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--verify", default="", help="graph:id,graph:id run stock and executor together")
    ap.add_argument("--question-limit-s", type=float, default=1200)
    ap.add_argument("--ir-check")
    ap.add_argument("--only", default="", help="graph:id,graph:id, instead of all 17")
    ap.add_argument("--question-handles", action="store_true", help="handles named in the question's text also count as printed")
    ap.add_argument("--no-told", action="store_true", help="arm: without the told sentence")
    ap.add_argument("--no-rule", action="store_true", help="arm: without the handle rule, in the description or the runner")
    a = ap.parse_args()
    if a.ir_check:
        return ir_check(a.ir_check)
    assert TOLD in open(os.path.join(X.X210, "rb", "delivery.py")).read()
    assert repr(EXTRA)[1:-1].replace("'", "") in open(os.path.join(X.X210, "rb", "run.py")).read().replace("'", "")
    sys.path.append(os.path.join(X.X210, "exec"))
    from chat import ExecChat
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    t0 = time.time()
    ec = ExecChat(D.CKPT)
    load_s = round(time.time() - t0, 1)
    tool = chase_tool("" if a.no_rule else (RULE_Q if a.question_handles else RULE))
    os.makedirs(a.out, exist_ok=True)
    verify = set(a.verify.split(",")) if a.verify else set()
    only = set(a.only.split(",")) if a.only else None
    json.dump({"ckpt": D.CKPT, "chip_side": "exec/ C engine; prefill and Qwen's layers stock on MPS", "engine": ec.cx.lib_hash, "verify": sorted(verify),
               "load_seconds": load_s, "extra": EXTRA, "told": TOLD, "rule_in_tool_description": RULE, "tool": tool, "question_handles": a.question_handles, "told_on": not a.no_told, "rule_on": not a.no_rule, "attn": ec.chat.model.config._attn_implementation,
               "elf_sha256": __import__("hashlib").sha256(open(X.build_elf(), "rb").read()).hexdigest(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              open(os.path.join(a.out, "meta.json"), "w"), indent=1, ensure_ascii=False)
    print(f"loaded {load_s}s {D.mem()} engine {ec.cx.lib_hash}", flush=True)
    for name, gname in GRAPHS.items():
        gp, qp = D.graph_path(gname)
        g = json.load(open(gp))
        qs = {x["id"]: x for x in json.load(open(qp))["questions"]}
        ids = [json.loads(line)["id"] for line in open(os.path.join(X.X210, "host", "out", "dev2", name, "sdpa.jsonl"))]
        path = os.path.join(a.out, f"{name}.jsonl")
        done = {json.loads(line)["id"] for line in open(path)} if os.path.exists(path) else set()
        with open(path, "a", encoding="utf-8") as f:
            for i in ids:
                if i in done or qs[i].get("kind") != "chase" or (only and f"{name}:{i}" not in only):
                    continue
                r = run_question(ec, g, qs[i], nq, a.question_limit_s, tool, verify=f"{name}:{i}" in verify, question_handles=a.question_handles, told=not a.no_told, rule=not a.no_rule)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print(f"{name} q{i}: {r['status']} on {r['ran_on']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s chip={r['chip_tokens']} "
                      f"qwen={r['qwen_tokens']} echo={r['echo_tokens']} line={r['runner_line_tokens']} fired={r['owner_fired_on_runner_line']} head_bad={r['head_mismatch']} lock={r['lock_error']} "
                      f"verified={r['verified_positions']} mismatch={r['verify_mismatch']} | {[(c['args'].get('start'), c.get('result', '')[:30]) for c in r['calls']]}", flush=True)
                torch.mps.empty_cache()
                tally(a.out)
                if r["status"] in ("verify_mismatch", "engine_flag"):
                    print("STOP: the executor disagreed; this run's results do not count until explained", flush=True)
                    sys.exit(3)
    print(json.dumps({k: v for k, v in tally(a.out).items() if k != "per_question"}), flush=True)


if __name__ == "__main__":
    main()
