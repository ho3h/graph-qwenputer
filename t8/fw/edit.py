#!/usr/bin/env python3
"""Qwen writes the edit itself. chase, close and reopen on offer, Qwen goes on after each response and ends its own turn; a second user turn on the same machine. tok/drive.py's single-row loop with those changes. Executor for chip tokens, or stock and executor in lockstep with --verify-first N conversations.

The machine's durable state is read back from the heads at the start and after every machine call: n_closed, closed_bits, n_add, n_dead, n_edits, the overlay lists, from the engine's heads, from the reference machine, and in lockstep also from the stock weights' heads.

    python t8/fw/tokrun.py ../t8/fw/edit.py --out t8/fw/results/edit --verify-first 3 --deadline-s S
"""
import argparse
import copy
import hashlib
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/tok")
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402
from chat import ExecChat  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
import reflib  # noqa: E402

HT = X.HT
MAX_CALLS, TURN, TOTAL = 6, 320, 1536
RULE = os.environ.get("T8_EDIT_RULE", "")
TOOLS = [t for t in HT.tools_for("base") if t["function"]["name"] in ("chase", "close", "reopen")]
assert [t["function"]["name"] for t in TOOLS] == ["chase", "close", "reopen"]
HISTORY = []
if os.environ.get("T8_WRITES") == "1":                             # Qwen works out the edit: worked.py, one tool with two more fields, and the worked turns
    import worked as _W
    TOOLS, HISTORY = _W.TOOLS, _W.HISTORY
HERE = os.path.dirname(os.path.abspath(__file__))


def symbols(path):
    b = open(path, "rb").read()
    shoff = struct.unpack_from("<I", b, 0x20)[0]
    shentsize, shnum = struct.unpack_from("<HH", b, 0x2E)
    secs = [struct.unpack_from("<10I", b, shoff + i * shentsize) for i in range(shnum)]
    out = {}
    for s in secs:
        if s[1] == 2:
            strs = secs[s[6]]
            for k in range(s[5] // 16):
                name, value, size, info, _, _ = struct.unpack_from("<IIIBBH", b, s[4] + k * 16)
                e = b.index(b"\0", strs[4] + name)
                if info & 15 == 1:
                    out[b[strs[4] + name:e].decode()] = (value, size)
    return out


SYM = symbols(C.X.build_elf())
DURABLE = ("n_closed", "closed_bits", "n_add", "n_dead", "n_edits", "add_a", "add_b", "add_r", "add_w", "dead_")


def durable(ram):
    """{name: words} from a RAM word list."""
    return {n: [int(ram[w]) for w in range(SYM[n][0] >> 2, (SYM[n][0] + SYM[n][1] + 3) >> 2)] for n in DURABLE}


def show(d):
    def bits(ws):
        return [i * 32 + b for i, w in enumerate(ws) for b in range(32) if w >> b & 1]
    return {"n_closed": d["n_closed"][0], "closed": bits(d["closed_bits"]), "n_add": d["n_add"][0], "n_dead": d["n_dead"][0], "n_edits": d["n_edits"][0], "dead": bits(d["dead_"]),
            "sha": hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]}


class Heads:
    def __init__(self, ec):
        self.ec = ec
        c = ec.chat.c
        self.vh, j = {}, 0
        for n in ec.cx.heads:
            for x in range(len(n.vheads())):
                self.vh[(n.name, x)] = j
                j += 1
        self.slots = {id(c.nodes[ni]): s for ni, s in hf.head_slots(c).items()}
        self.r_ = c.target.value_heads // c.target.key_heads
        self.byname = {n.name: n for n in ec.cx.heads}

    def rows(self, name, x, cache):
        if cache is None:
            return self.ec.cx.S[self.vh[(name, x)]]
        L, h = self.slots[id(self.byname[name])]
        return cache.layers[L].recurrent_states[0][0, h * self.r_ + x].detach().to(torch.float32).cpu().numpy()

    def ram(self, cache=None):
        """RAM words back from the heads, by core.snapshot's layout in reverse (edits2/machine.py). cache: the stock weights' heads; None: the engine's."""
        ram = [0] * S.RAM_WORDS
        for h in range(S.RAM_WORDS >> 8):
            low, hi = h & 15, h >> 4
            for x in range(2):
                rows = self.rows(f"ram{h}", x, cache)
                for r in np.nonzero(rows.any(axis=1))[0]:
                    bits = (rows[r, 2:34] > 0) | (rows[r, 34:66] > 0)
                    ram[low | x << 4 | int(r) << 5 | hi << 12] = int(sum(1 << i for i in np.nonzero(bits)[0]))
        return ram


@torch.no_grad()
def conversation(ec, H, g, item, nq, verify, limit_s):
    chat, cx = ec.chat, ec.cx
    T, tok = chat.T, chat.tok
    TCO, TCC = T.TCO, T.TCC
    IM_END, EOS = tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")
    stops = {TCC, IM_END, EOS}
    graph = reflib.Graph(g)
    m = D.parked_machine(g, T, None)
    turns = item["turns"]
    msgs = [{"role": "system", "content": HT.system_prompt(g) + RULE}] + HISTORY + [{"role": "user", "content": turns[0]["user"]}]
    prompt = chat.prompt_ids(msgs, tools=TOOLS)
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
    states, turn_log, calls = [], [], []

    def snap(at):
        e = durable(H.ram())
        rf = durable(lock.m.ram)
        rec = {"at": at, "engine": show(e), "reference_equal": e == rf}
        if verify:
            st = durable(H.ram(cache))
            rec["stock"] = show(st)
            rec["stock_equal"] = st == e
        states.append(rec)
        rec["_raw"] = e

    snap("before")
    seg, gen, expect, status, feed, now, lock_error, n_chip, n_echo, n_qwen, head_bad, verified, mismatch = [], 0, [], None, [], 0, None, 0, 0, 0, 0, 0, None
    want_state = None
    turn_calls = []
    while status is None:
        st_ = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if want_state and not expect:
            snap(want_state)
            want_state = None
        if expect:
            e = expect.pop(0)
            if st_ != e:
                lock_error, status = {"at_call": len(calls), "want": int(e), "got": int(st_)}, "lock"
                break
            n_echo += nxt < chat.v0
        elif feed is not None and feed:
            lock.qwen([nxt])
            feed = feed
        elif st_ < S.VOCAB:
            lock_error, status = {"got": S.name(st_), "want": "text", "at_call": len(calls)}, "lock"
            break
        else:
            seg.append(nxt)
            gen += 1
            n_qwen += 1
            if nxt in stops:
                if nxt != TCC:
                    text = tok.decode(seg, skip_special_tokens=False).split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
                    turn_log.append({"user": turns[now]["user"], "calls": turn_calls, "reply": text, "gold": turns[now]["gold"], "wants": turns[now]["wants"], "ended": "own stop"})
                    turn_calls, seg = [], []
                    now += 1
                    if now == len(turns):
                        status = "answered"
                        break
                    lock.qwen([nxt])
                    forced = tok.encode(f"\n<|im_start|>user\n{turns[now]['user']}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", add_special_tokens=False)
                    feed = list(forced)
                else:
                    if len(calls) == MAX_CALLS:
                        status = "cap"
                        break
                    tco = max((i for i, t in enumerate(seg) if t == TCO), default=-1)
                    inner = tok.decode(seg[tco + 1:-1], skip_special_tokens=False)
                    call = HT.parse_call(inner)
                    ref = HT.answer_call(graph, call)
                    k, nruns = len(lock.toks), len(lock.runs)
                    lock.qwen([nxt])
                    expect = list(lock.toks[k + 1:])
                    raw = T.decode_bytes(lock.runs[nruns]) if len(lock.runs) > nruns else b""
                    import fragments as FR
                    h_, t_ = FR.HEAD.encode(), FR.TAIL.encode()
                    res = (raw[len(h_):-len(t_)] if raw.startswith(h_) and raw.endswith(t_) else raw).decode("utf-8", "replace")
                    c = {"text": inner, "before": tok.decode(seg[:tco + 1], skip_special_tokens=False) if tco > 0 else "", "fn": call["fn"], "args": call["args"], "result": res, "host_result": ref, "same_as_host": res == ref, "chip": sum(t < S.VOCAB for t in expect)}
                    calls.append(c)
                    turn_calls.append(c)
                    seg = []
                    want_state = f"after call {len(calls)}: {call['fn']} {json.dumps(call['args'], ensure_ascii=False)}"
            elif len(seg) >= TURN or gen >= TOTAL:
                turn_log.append({"user": turns[now]["user"], "calls": turn_calls, "reply": tok.decode(seg, skip_special_tokens=False), "gold": turns[now]["gold"], "wants": turns[now]["wants"], "ended": "cap"})
                status = "budget"
                break
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
            status = "walltime"
            break
        chip_in = nxt >= chat.v0
        if verify:
            hc, logits = chat._layers(nxt, cache, None if chip_in else pos)
            hcu = hc.detach().cpu().view(torch.uint16).numpy()
            keep = cx.step(st_).copy()
            bits, _ = ec.exec_bits(nxt, keep)
            verified += 1
            if not np.array_equal(hcu, bits):
                dd = np.nonzero(hcu != bits)[0]
                mismatch, status = {"at_call": len(calls), "mid": nxt, "n_dims": len(dd)}, "verify_mismatch"
                break
            ct = chat.circuit_token(hc)
            if chip_in:
                n_chip += 1
                if ct is None:
                    lock_error, status = {"got": "owner off", "at_call": len(calls)}, "lock"
                    break
                nxt = ct
            else:
                pos += 1
                q_tok = int(torch.argmax(logits))
                head_bad += ct is not None and q_tok != ct
                nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
        elif chip_in:
            limit = len(expect) + 1
            stname, t_next, n, rec = cx.burst(st_, limit, record=True)
            n_chip += n
            if stname in ("owner_off", "decode"):
                lock_error, status = {"got": stname, "at_call": len(calls)}, "lock"
                break
            chain = rec[: n - 1]
            want = np.array(expect[: n - 1], np.int32)
            if len(want) != len(chain) or not np.array_equal(want, chain):
                lock_error, status = {"burst differs at call": len(calls)}, "lock"
                break
            del expect[: n - 1]
            nxt = chat.v0 + t_next if t_next < S.VOCAB else t_next - S.TEXT_TOKEN
        else:
            keep = cx.step(st_).copy()
            hc = ec.hc(nxt, keep)
            logits = chat._qwen_step(hc, cache, pos)
            ct = ec.code_token(keep)
            pos += 1
            q_tok = int(torch.argmax(logits))
            head_bad += ct is not None and q_tok != ct
            nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
        if feed:
            nxt = feed.pop(0)
            if not feed:
                feed = None
                lock.qwen([nxt])                                    # the last forced token: Qwen's turn starts on the next prediction
                # step it, as the top of the loop steps a forced token; then it is Qwen's
                st2 = BR.text_token(nxt)
                if verify:
                    hc, logits = chat._layers(nxt, cache, pos)
                    keep = cx.step(st2).copy()
                    bits, _ = ec.exec_bits(nxt, keep)
                    if not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                        mismatch, status = {"at": "forced"}, "verify_mismatch"
                else:
                    keep = cx.step(st2).copy()
                    logits = chat._qwen_step(ec.hc(nxt, keep), cache, pos)
                pos += 1
                ct = ec.code_token(keep)
                nxt = ct if ct is not None else int(torch.argmax(logits[:nq]))
                feed = []
        if cx.p.flags:
            mismatch, status = {"engine_flags": cx.flags()}, "engine_flag"
            break
    if want_state and not expect:
        snap(want_state)
    state = ec.state_diff(cache) if verify and status != "verify_mismatch" else None
    if state and state["big"]:
        mismatch, status = {"state": state}, "verify_mismatch"
    if status != "answered" and status != "budget" and len(turn_log) < len(turns) and seg:
        turn_log.append({"user": turns[now]["user"], "calls": turn_calls, "reply": tok.decode(seg, skip_special_tokens=False), "gold": turns[now]["gold"], "wants": turns[now]["wants"], "ended": status})
    raw = [s.pop("_raw") for s in states]
    # what changed, word by word, between consecutive reads
    for a, b, s in zip(raw, raw[1:], states[1:]):
        s["changed"] = {n: [[i, x, y] for i, (x, y) in enumerate(zip(a[n], b[n])) if x != y] for n in DURABLE if a[n] != b[n]}
    r = {"key": item["key"], "graph": item["graph"], "item": {k: v for k, v in item.items() if k != "turns"}, "status": status, "turns": turn_log, "states": states, "returned_to_start": raw[0] == raw[-1], "n_calls": len(calls), "lock_error": lock_error, "verify_mismatch": mismatch, "head_mismatch": head_bad,
         "ran_on": "stock and executor in lockstep" if verify else "executor", "verified_positions": verified, "end_state_diff": state, "chip_tokens": n_chip, "qwen_tokens": n_qwen, "echo_tokens": n_echo, "prompt_tokens": len(prompt), "seconds": round(time.time() - t0, 1), "firmware_sha256": hashlib.sha256(open(C.X.build_elf(), "rb").read()).hexdigest()}
    del cache
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", default="both", choices=["both", "conversations", "plain"])
    ap.add_argument("--verify-first", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--deadline-s", type=float, required=True)
    ap.add_argument("--question-limit-s", type=float, default=1800)
    ap.add_argument("--draw", default=os.path.join(HERE, "results", "edit_draw.json"))
    a = ap.parse_args()
    draw = json.load(open(a.draw))
    t0 = time.time()
    ec = ExecChat(C.CKPT)
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    H = Heads(ec)
    print(f"loaded {time.time() - t0:.0f}s engine {ec.cx.lib_hash}", flush=True)
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "all.jsonl")
    done = {json.loads(ln)["key"] for ln in open(p)} if os.path.exists(p) else set()
    items = (draw["conversations"] if a.set in ("both", "conversations") else []) + (draw["plain"] if a.set in ("both", "plain") else [])
    if a.limit:
        items = items[:a.limit]
    v = 0
    with open(p, "a", encoding="utf-8") as f:
        for it in items:
            verify = v < a.verify_first
            v += 1
            if it["key"] in done:
                continue
            if time.time() - t0 > a.deadline_s:
                print("DEADLINE", flush=True)
                sys.exit(3)
            g = json.load(open(D.graph_path(it["graph"])[0]))
            r = conversation(ec, H, g, it, nq, verify, a.question_limit_s)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(it["key"], r["status"], r["ran_on"], "calls", r["n_calls"], [c["fn"] for t in r["turns"] for c in t["calls"]], "returned", r["returned_to_start"], r["seconds"], flush=True)
            if r["status"] in ("lock", "engine_flag", "verify_mismatch"):
                print("STOP:", r["lock_error"], r["verify_mismatch"], flush=True)
                sys.exit(4)
            torch.mps.empty_cache()
    print(f"done {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
