"""The whole chain on the merged weights: the dev2 chase questions, `chase` as the only tool, rb/run.py's added sentence, the
machine's line as the answer, up to 2 retries when that line is an error, the error delivered as the circuit delivers it.

    python chain.py --out results/chain [--compact]          # from the vendored folder, under tools/memguard.py

The answer is read from the tokens the circuit itself generated. Each of them is also locked to the reference machine, and
each call's result is compared with the host tool. Scored by host/score.py. One JSON line per question; a restart skips
finished questions. A question over --question-limit-s is recorded as "walltime", and a whole run is bounded by `timeout`.
"""

import argparse
import json
import os
import re
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

import copy  # noqa: E402

import reflib  # noqa: E402
import score as SC  # noqa: E402

HT = X.HT
GRAPHS = {"tiny": "tiny", "c024": "cities/c024", "c025": "cities/c025", "r001": "random/r001"}
RETRIES, TURN = 2, 768
# rb/run.py's sentence and error pattern, checked against that file at start; TOOLONG is the firmware's added limit line
EXTRA = "\nMake exactly one tool call that answers the question. Its result is shown to the user as your answer."
ERROR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG)\b")
HEAD, TAIL = b"\n<tool_response>\n", b"\n</tool_response>\n<think>\n\n</think>\n\n"


@torch.no_grad()
def run_question(chat, g, q, nq, retries, limit_s, chase_tool):
    T, tok = chat.T, chat.tok
    stops = {T.TCC, tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}
    setup = q.get("setup") or []
    graph = reflib.Graph(g)
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)
    msgs = [{"role": "system", "content": HT.system_prompt(g) + EXTRA}, {"role": "user", "content": q["text"]}]
    prompt = chat.prompt_ids(msgs, tools=[chase_tool])
    lock = BR.Session(T, copy.deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    out = chat._prefill(prompt)
    cache = out.past_key_values
    core.snapshot(chat.c, m)
    hf.inject(chat.c, cache)
    pos = len(prompt)
    nxt = int(torch.argmax(out.logits[0, -1, :nq]))
    t_chip = t_text = 0.0
    n_chip = n_qwen = n_echo = head_bad = own_ok = 0
    calls, seg, echo, expect = [], [], [], []
    answer, status, lock_error, attempt = None, None, None, 0
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if expect:                                        # a position of the machine's run
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
            if not expect:                                # the run ended: the circuit's own line
                raw = T.decode_bytes(echo)
                wrapped = raw.startswith(HEAD) and raw.endswith(TAIL)
                res = (raw[len(HEAD):-len(TAIL)] if wrapped else raw).decode("utf-8", "replace")
                c = calls[-1]
                c.update(result=res, wrapped=wrapped, same_as_host=res == c["host_result"], response_ids=echo, echo=len(echo))
                answer = res
                if not ERROR.match(res) or attempt == retries:
                    status = "answered"
                    break
                attempt += 1
                seg, echo = [], []
        elif st < S.VOCAB:
            lock_error = {"got": S.name(st), "want": "text", "at_call": len(calls)}
            status = "lock"
            break
        else:                                             # Qwen's own token
            seg.append(nxt)
            n_qwen += 1
            if nxt in stops or len(seg) >= TURN:
                if nxt != T.TCC:
                    status = "no_call"
                    calls_tail = tok.decode(seg, skip_special_tokens=False)
                    break
                tco = max((i for i, t in enumerate(seg) if t == T.TCO), default=-1)
                ids = seg[tco + 1:-1]
                inner = tok.decode(ids, skip_special_tokens=False)
                call = HT.parse_call(inner)
                k = len(lock.toks)
                lock.qwen([nxt])
                expect = list(lock.toks[k + 1:])
                chip = sum(t < S.VOCAB for t in expect)
                calls.append({"text": inner, "ids": ids, "fn": call["fn"], "args": call["args"], "no_tco": tco < 0,
                              "host_result": HT.answer_call(graph, call), "chip": chip, "cap": len(ids)})
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
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
            top = int(torch.argmax(logits))
            if ct is not None and top != ct:
                head_bad += 1
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
            t_text += time.perf_counter() - ts
    del cache
    return {"id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"),
            "status": status, "n_calls": len(calls), "calls": calls, "final": answer,
            "correct": SC.score(answer, q, graph.labels) if answer is not None else False,
            "no_call_text": calls_tail if status == "no_call" else None, "prompt_tokens": len(prompt), "lock_error": lock_error,
            "head_mismatch": head_bad, "own_ok": own_ok, "chip_tokens": n_chip, "qwen_tokens": n_qwen, "echo_tokens": n_echo,
            "chip_seconds": round(t_chip, 2), "text_seconds": round(t_text, 2), "seconds": round(time.time() - t0, 2), **D.mem()}


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
    first_error = [k for k, r in rs.items() if r["calls"] and ERROR.match(r["calls"][0].get("result", ""))]
    rescued = [k for k in first_error if rs[k]["correct"]]
    t = {"questions": len(v), "correct": sum(bool(r["correct"]) for r in v), "status": {}, "calls": len(calls),
         "calls_equal_host_tool": sum(bool(c.get("same_as_host")) for c in calls), "lock_errors": sum(r["lock_error"] is not None for r in v),
         "head_mismatch": sum(r["head_mismatch"] for r in v), "own_ok": sum(r["own_ok"] for r in v),
         "chip_tokens": sum(r["chip_tokens"] for r in v), "qwen_tokens": sum(r["qwen_tokens"] for r in v),
         "echo_tokens": sum(r["echo_tokens"] for r in v), "seconds": round(sum(r["seconds"] for r in v), 1),
         "chip_seconds": round(sum(r["chip_seconds"] for r in v), 1), "text_seconds": round(sum(r["text_seconds"] for r in v), 1),
         "first_line_error": len(first_error), "rescued_by_retry": len(rescued), "max_cap": max((c["cap"] for c in calls), default=0),
         "per_question": [[k[0], k[1], r["status"], r["n_calls"], r["correct"], r["seconds"], (r["final"] or "")[:60]] for k, r in rs.items()]}
    for r in v:
        t["status"][r["status"]] = t["status"].get(r["status"], 0) + 1
    t["correct_on_first_line"] = sum(1 for k, r in rs.items() if r["calls"] and k not in first_error and r["correct"])
    t["chip_per_s"] = round(t["chip_tokens"] / max(t["chip_seconds"], 1e-9), 2)
    t["text_per_s"] = round((t["qwen_tokens"] + t["echo_tokens"]) / max(t["text_seconds"], 1e-9), 2)
    json.dump(t, open(os.path.join(out, "tally.json"), "w"), indent=1, ensure_ascii=False)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--retries", type=int, default=RETRIES)
    ap.add_argument("--question-limit-s", type=float, default=2400)
    a = ap.parse_args()
    src = open(os.path.join(X.X210, "rb", "run.py")).read()
    assert repr(EXTRA)[1:-1].replace("'", "") in src.replace("'", ""), "EXTRA differs from rb/run.py"
    chase = [t for t in HT.tools_for("base") if t["function"]["name"] == "chase"][0]
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    chat, load_s = D.load_chat(D.CKPT, compact=a.compact)
    os.makedirs(a.out, exist_ok=True)
    json.dump({"ckpt": D.CKPT, "compact": a.compact, "load_seconds": load_s, "attn": chat.model.config._attn_implementation,
               "extra": EXTRA, "retries": a.retries, "nq": nq, "question_limit_s": a.question_limit_s,
               "elf_sha256": __import__("hashlib").sha256(open(X.build_elf(), "rb").read()).hexdigest(),
               "env": {k: os.environ.get(k) for k in ("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "PYTORCH_MPS_LOW_WATERMARK_RATIO")},
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    print(f"loaded in {load_s}s {D.mem()}, compact {a.compact}", flush=True)
    for name, gname in GRAPHS.items():
        gp, qp = D.graph_path(gname)
        g = json.load(open(gp))
        qs = {x["id"]: x for x in json.load(open(qp))["questions"]}
        ids = [json.loads(line)["id"] for line in open(os.path.join(X.X210, "host", "out", "dev2", name, "sdpa.jsonl"))]
        path = os.path.join(a.out, f"{name}.jsonl")
        done = {json.loads(line)["id"] for line in open(path)} if os.path.exists(path) else set()
        with open(path, "a", encoding="utf-8") as f:
            for i in ids:
                if i in done or qs[i].get("kind") != "chase":
                    continue
                r = run_question(chat, g, qs[i], nq, a.retries, a.question_limit_s, chase)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print(f"{name} q{i}: {r['status']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s chip={r['chip_tokens']} "
                      f"qwen={r['qwen_tokens']} echo={r['echo_tokens']} head_bad={r['head_mismatch']} lock={r['lock_error']} | "
                      f"{[c.get('result', '')[:40] for c in r['calls']]}", flush=True)
                torch.mps.empty_cache()
                tally(a.out)
    print(json.dumps({k: v for k, v in tally(a.out).items() if k != "per_question"}), flush=True)


if __name__ == "__main__":
    main()
