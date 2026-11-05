"""Chain3's flow, several questions at once: one GPU step per position for every row, with each row's bits as a row of its own would have.

What runs in batch: Qwen's linear maps, norms, the conv windows, the delta rule. What runs row by row, to keep a batch of 1's kernel where S3 found a difference: the head, and each row's attention (rows have different key lengths).

run_question is rvc/chain2.py's run_question as a generator (told on, rule off, no verify, no forced lines): same lock, same retries, same stops. It yields a request and is sent the answer:
    ("prefill", prompt)            -> the first token's logits argmax
    ("text", hc_bits, pos, need)   -> argmax over Qwen's rows, or None when need is False

Flags that change the flow, all off for the same-tokens replay:
    limit_stop   a limit line (END, MULTI, NOCHANGE, CLOSED, NOPATH) ends the turn, as d/PLAN.md proposes
    cap          an attempt that has not reached </tool_call> after cap tokens ends as no_call
    lazy_echo    the machine's echo goes through the chip side only; Qwen's layers see it only if a retry follows
"""
import copy
import json
import re
import time

import numpy as np
import torch
import torch.nn.functional as F

import textlib as TL
from chipformer.rv import bridge as BR, core
from chipformer.rv import spec as S
from transformers.models.qwen3_5 import modeling_qwen3_5 as M
from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS

C2, D, X = TL.C2, TL.D, TL.X
LIMIT = re.compile(r"^(?:leg \d+: )?(END|MULTI|NOCHANGE|CLOSED|NOPATH)\b")


def hc_bits(ec, nxt, keep):
    """A text token's residual as bf16 bit patterns: as ExecChat.hc, on the CPU."""
    bits, _ = ec.exec_bits(nxt, keep)
    return bits


def run_question(ctx, ex, g, q, nq, tool, limit_s=1800, limit_stop=False, cap=None, lazy_echo=False):
    """A generator: chain2.run_question(told=True, rule=False, verify=False) with Qwen's steps asked of the driver. ex is this row's own CExec."""
    ec = ctx.ec
    chat = ec.chat
    T, tok = chat.T, chat.tok
    stops = {T.TCC, tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}
    TURN = C2.TURN if cap is None else cap
    graph = TL.reflib.Graph(g)
    setup = q.get("setup") or []
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = D.parked_machine(g, T, setup)
    msgs = [{"role": "system", "content": X.HT.system_prompt(g) + C2.EXTRA + C2.TOLD}, {"role": "user", "content": q["text"]}]
    prompt = chat.prompt_ids(msgs, tools=[tool])
    lock = BR.Session(T, copy.deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    core.snapshot(chat.c, m)
    ex.p.flags = 0
    ex.start([ec.stream(i) for i in prompt])
    ts = time.perf_counter()
    nxt = yield ("prefill", prompt)
    t_prefill = time.perf_counter() - ts
    pos = len(prompt)
    t_chip = t_text = 0.0
    n_chip = n_qwen = n_echo = own_ok = 0
    n_gpu = n_deferred = n_skipped = 0
    calls, seg, echo, expect, deferred = [], [], [], [], []
    answer, status, lock_error, attempt, mismatch, no_call_text = None, None, None, 0, None, None
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if expect:
            e = expect.pop(0)
            if st != e:
                lock_error = {"want": S.name(e) if e < S.VOCAB else tok.decode([e - S.TEXT_TOKEN]), "got": S.name(st) if st < S.VOCAB else tok.decode([nxt]), "at_call": len(calls)}
                status = "lock"
                break
            own_ok += 1
            if nxt < chat.v0:
                n_echo += 1
                echo.append(nxt)
            if not expect:
                raw = T.decode_bytes(echo)
                wrapped = raw.startswith(C2.HEAD) and raw.endswith(C2.TAIL)
                res = (raw[len(C2.HEAD):-len(C2.TAIL)] if wrapped else raw).decode("utf-8", "replace")
                c = calls[-1]
                c.update(result=res, wrapped=wrapped, same_as_host=res == c["host_result"], response_ids=echo, echo=len(echo))
                answer = res
                ended = not C2.ERROR.match(res) or attempt == C2.RETRIES or (limit_stop and LIMIT.match(res))
                if ended:
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
                call = X.HT.parse_call(inner)
                host = X.HT.answer_call(graph, call)
                rec = {"text": inner, "ids": ids, "fn": call["fn"], "args": call["args"], "no_tco": tco < 0, "host_result": host, "cap": len(ids), "machine_ran": True}
                calls.append(rec)
                k = len(lock.toks)
                lock.qwen([nxt])
                expect = list(lock.toks[k + 1:])
                rec["chip"] = sum(t < S.VOCAB for t in expect)
            else:
                lock.qwen([nxt])
        if limit_s and time.time() - t0 > limit_s:
            status = "walltime"
            break
        chip_in = nxt >= chat.v0
        if chip_in:
            ts = time.perf_counter()
            stname, t_next, n, rec_ = ex.burst(st, len(expect) + 1, record=True)
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
        else:
            ts = time.perf_counter()
            keep = ex.step(st).copy()
            ct = ec.code_token(keep)
            bits = hc_bits(ec, nxt, keep)
            if lazy_echo and ct is not None:                # Qwen's layers can wait: the circuit owns the next token, and if the turn ends here they never run
                deferred.append((bits, pos))
                pos += 1
                nxt = ct
                t_chip += time.perf_counter() - ts
            else:
                for b, p_ in deferred:
                    yield ("text", b, p_, False)
                    n_gpu += 1
                    n_deferred += 1
                deferred = []
                top = yield ("text", bits, pos, ct is None)
                n_gpu += 1
                pos += 1
                nxt = ct if ct is not None else top
                t_text += time.perf_counter() - ts
        if ex.p.flags:
            mismatch = {"engine_flags": ex.flags(), "at_call": len(calls)}
            status = "engine_flag"
            break
    n_skipped = len(deferred)
    yield ("done", {"id": q["id"], "kind": q.get("kind"), "status": status, "n_calls": len(calls), "calls": calls, "final": answer, "correct": TL.SC.score(answer, q, graph.labels) if answer is not None else False, "no_call_text": no_call_text,
                    "prompt_tokens": len(prompt), "lock_error": lock_error, "own_ok": own_ok, "chip_tokens": n_chip, "qwen_tokens": n_qwen, "echo_tokens": n_echo, "gpu_text_steps": n_gpu, "deferred_ran": n_deferred, "deferred_never_ran": n_skipped,
                    "chip_seconds": round(t_chip, 3), "text_seconds": round(t_text, 2), "prefill_seconds": round(t_prefill, 3), "seconds": round(time.time() - t0, 2), "ran_on": "executor, batched text", "verify_mismatch": mismatch, "engine": ex.lib_hash})


def rms_rows(norm, x):
    """Qwen3_5RMSNorm with the mean over the residual taken row by row: S5 finds a batched mean over 3,968 dims differs from a row alone's in about a quarter of rows; a row-by-row mean keeps the bits."""
    x32 = x.float()
    sq = x32.pow(2)
    B = x.shape[0]
    var = sq.mean(-1, keepdim=True) if B == 1 else torch.cat([sq[j:j + 1].mean(-1, keepdim=True) for j in range(B)])
    out = x32 * torch.rsqrt(var + norm.eps)
    return (out * (1.0 + norm.weight.float())).type_as(x)


class Slots:
    """B rows of Qwen's state: linear layers as one tensor per layer, attention keys per row."""

    def __init__(self, ctx, B, tau, layers, head):
        self.ctx, self.B = ctx, B
        self.chat = ctx.ec.chat
        self.n_chip = self.chat.n_chip
        self.layers = layers                               # Qwen's layers, in order
        self.head = head                                   # bf16 block: Qwen's rows on dims 0..tau
        self.tau = tau
        self.types = self.chat.model.config.layer_types
        self.linear = {}
        self.kv = {}
        self.rows = [None] * B                             # which question is in the row
        self.cache = None

    def install(self, row, cache):
        """Put one question's cache, after its prefill, in a row."""
        for i in range(self.n_chip, len(self.chat.lm.layers)):
            lay = cache.layers[i]
            if hasattr(lay, "recurrent_states"):
                if i not in self.linear:
                    self.linear[i] = (torch.zeros(self.B, *lay.conv_states[0].shape[1:], dtype=lay.conv_states[0].dtype, device="mps"), torch.zeros(self.B, *lay.recurrent_states[0].shape[1:], dtype=lay.recurrent_states[0].dtype, device="mps"))
                self.linear[i][0][row] = lay.conv_states[0][0]
                self.linear[i][1][row] = lay.recurrent_states[0][0]
            else:
                self.kv.setdefault(i, [None] * self.B)[row] = (lay.keys, lay.values)

    @torch.no_grad()
    def step(self, rows, bits, pos, need):
        """One position for each listed row. bits: n x 3968 uint16 numpy; pos: list. Returns argmax per row or None."""
        chat = self.chat
        n = len(rows)
        whole = n == self.B
        idx = None if whole else torch.tensor(rows, device="mps")
        h = torch.from_numpy(bits).to("mps").view(torch.bfloat16).unsqueeze(1)
        tp = torch.tensor(pos, device="mps", dtype=torch.long).view(n, 1)
        pe = chat.lm.rotary_emb(h, tp.unsqueeze(0).expand(3, -1, -1))
        for lay, i in zip(self.layers, range(self.n_chip, len(chat.lm.layers))):
            if self.types[i] == "linear_attention":
                h = self._linear(lay, i, h, idx)
            else:
                h = self._full(lay, i, h, pe, rows)
        nn = rms_rows(chat.lm.norm, h)
        out = [None] * n
        js = [j for j in range(n) if need[j]]
        if js:                                              # one map for all rows: S11 finds it bit-equal with row by row up to 15 rows
            sel = nn if len(js) == n else nn.index_select(0, torch.tensor(js, device="mps"))
            am = torch.argmax(F.linear(sel[..., : self.tau + 1], self.head)[:, -1], dim=-1).tolist()
            for j, a_ in zip(js, am):
                out[j] = a_
        return out

    def _linear(self, layer, i, x, idx):
        la = layer.linear_attn
        cs, rs = self.linear[i]
        residual = x
        n = rms_rows(layer.input_layernorm, x)
        B = n.shape[0]
        mixed = la.in_proj_qkv(n).transpose(1, 2)
        z = la.in_proj_z(n).reshape(B, 1, -1, la.head_v_dim)
        b = la.in_proj_b(n)
        a = la.in_proj_a(n)
        conv_state = cs if idx is None else cs.index_select(0, idx)
        mixed = M.causal_conv1d_update(mixed, conv_state, la.conv1d.weight.squeeze(1), la.conv1d.bias, la.activation)
        if idx is not None:
            cs.index_copy_(0, idx, conv_state)
        mixed = mixed.transpose(1, 2)
        query, key, value = torch.split(mixed, [la.key_dim, la.key_dim, la.value_dim], dim=-1)
        query = query.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(la.num_v_heads // la.num_k_heads, dim=2)
        key = key.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(la.num_v_heads // la.num_k_heads, dim=2)
        value = value.reshape(B, 1, -1, la.head_v_dim)
        beta = b.sigmoid()
        g = -la.A_log.float().exp() * F.softplus(a.float() + la.dt_bias)
        state = rs if idx is None else rs.index_select(0, idx)
        out, new = M.torch_recurrent_gated_delta_rule(query, key, value, g=g, beta=beta, initial_state=state, output_final_state=True, use_qk_l2norm_in_kernel=True)
        if idx is None:
            self.linear[i] = (cs, new)
        else:
            rs.index_copy_(0, idx, new)
        y = la.norm(out.reshape(-1, la.head_v_dim), z.reshape(-1, la.head_v_dim)).reshape(B, 1, -1)
        x = residual + la.out_proj(y)
        residual = x
        return residual + layer.mlp(rms_rows(layer.post_attention_layernorm, x))

    def _full(self, layer, i, x, pe, rows):
        a = layer.self_attn
        residual = x
        n = rms_rows(layer.input_layernorm, x)
        B = n.shape[0]
        shape = (B, 1)
        hshape = (*shape, -1, a.head_dim)
        qs, gate = torch.chunk(a.q_proj(n).view(*shape, -1, a.head_dim * 2), 2, dim=-1)
        gate = gate.reshape(*shape, -1)
        qs = a.q_norm(qs.view(hshape)).transpose(1, 2)
        ks = a.k_norm(a.k_proj(n).view(hshape)).transpose(1, 2)
        vs = a.v_proj(n).view(hshape).transpose(1, 2)
        qr, kr = M.apply_rotary_pos_emb(qs, ks, pe[0], pe[1])
        kv = self.kv[i]
        outs = []
        attn = ALL_ATTENTION_FUNCTIONS.get_interface(a.config._attn_implementation, M.eager_attention_forward)
        for j, row in enumerate(rows):
            keys = torch.cat([kv[row][0], kr[j:j + 1]], dim=-2)
            vals = torch.cat([kv[row][1], vs[j:j + 1]], dim=-2)
            kv[row] = (keys, vals)
            oj, _ = attn(a, qr[j:j + 1], keys, vals, None, dropout=0.0, scaling=a.scaling)
            outs.append(oj.reshape(1, 1, -1).contiguous())
        o = torch.cat(outs) if B > 1 else outs[0]
        o = o * torch.sigmoid(gate)
        x = residual + a.o_proj(o)
        residual = x
        return residual + layer.mlp(rms_rows(layer.post_attention_layernorm, x))


@torch.no_grad()
def qwen_prefill_hc(ctx, hc, cache=None):
    """Qwen's layers on a run of residuals: as Qwen3_5TextModel.forward does after the chip layers, with the same mask."""
    from transformers import DynamicCache
    chat = ctx.ec.chat
    n = hc.shape[1]
    cache = cache or DynamicCache(config=chat.model.config)
    tp = torch.arange(n, device="mps").view(1, -1)
    pe = chat.lm.rotary_emb(hc, tp.view(1, 1, -1).expand(3, 1, -1))
    mask = torch.ones(n, n, dtype=torch.bool, device="mps").tril(0)[None, None]
    h = hc
    for i in range(chat.n_chip, len(chat.lm.layers)):
        ty = chat.model.config.layer_types[i]
        h = chat.lm.layers[i](h, position_embeddings=pe, attention_mask=mask if ty == "full_attention" else None, position_ids=tp, past_key_values=cache)
    return chat.lm.norm(h)[:, -1:, :], cache


def prompt_hc(ctx, ex, prompt):
    """The prompt's residuals, from the engine (S1(e): bit-equal with stock's on 12 of 12 prompts). The engine's state is restored by the caller's start."""
    ec = ctx.ec
    ex.clear()
    keep = ex.run([ec.stream(i) for i in prompt], keep=True).copy()
    u = keep.view(np.uint32)
    rr = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    hcb = np.zeros((len(prompt), ec.hidden), np.uint16)
    hcb[:, : ec.d0] = TL.bits(ec.chat.lm.embed_tokens.weight[torch.tensor(prompt, device="mps"), : ec.d0])
    hcb[:, ec.keep_cols_np] = (rr >> 16).astype(np.uint16)
    return torch.from_numpy(hcb).to("mps").view(torch.bfloat16).unsqueeze(0)


def make_engines(ctx, n):
    """n more CExecs, each with its own state, sharing one token-feature table."""
    from cexec import CExec
    ec = ctx.ec
    ex0 = ec.cx
    out = []
    for _ in range(n):
        ex = CExec(ec.chat.c, ec.chat.T)
        ex.f_start, ex.f_len, ex.f_dim, ex.f_val = ex0.f_start, ex0.f_len, ex0.f_dim, ex0.f_val
        ex.p.f_start, ex.p.f_len = ex0.p.f_start, ex0.p.f_len
        ex.p.f_dim, ex.p.f_val = ex0.p.f_dim, ex0.p.f_val
        ex.fill = ex0.fill
        out.append(ex)
    return out


@torch.no_grad()
def drive(ctx, items, B, tool, layers, head, tau, on_done, exs, exp, prefill_layers=None, **flags):
    """items: list of (graph dict, question dict, tag). Runs them on B rows, in order, one row each. on_done(tag, record)."""
    nq = ctx.nq
    S_ = Slots(ctx, B, tau, layers, head)
    todo = list(items)
    gens = [None] * B
    req = [None] * B
    tags = [None] * B
    stats = {"gpu_steps": 0, "row_steps": 0, "prefill_s": 0.0, "step_s": 0.0}
    t0 = time.time()

    def advance(row, val):
        while True:
            r = gens[row].send(val)
            if r[0] == "prefill":
                s = time.perf_counter()
                prompt = r[1]
                hc = prompt_hc(ctx, exp, prompt)
                nn, cache = (prefill_layers or qwen_prefill_hc)(ctx, hc)
                y = F.linear(nn[..., : tau + 1], head)[0, -1]
                top = int(torch.argmax(y))
                S_.install(row, cache)
                del cache
                stats["prefill_s"] += time.perf_counter() - s
                val = top
                continue
            if r[0] == "done":
                on_done(tags[row], r[1])
                gens[row] = None
                req[row] = None
                return
            req[row] = r
            return

    while True:
        for row in range(B):
            if gens[row] is None and todo:
                g, q, tag = todo.pop(0)
                gens[row] = run_question(ctx, exs[row], g, q, nq, tool, **flags)
                tags[row] = tag
                advance(row, None)
        rows = [r for r in range(B) if req[r] is not None]
        if not rows:
            if not todo:
                break
            continue
        bits = np.stack([req[r][1] for r in rows])
        pos = [req[r][2] for r in rows]
        need = [req[r][3] for r in rows]
        s = time.perf_counter()
        out = S_.step(rows, bits, pos, need)
        stats["step_s"] += time.perf_counter() - s
        stats["gpu_steps"] += 1
        stats["row_steps"] += len(rows)
        for r, a in zip(rows, out):
            advance(r, a)
    stats["seconds"] = round(time.time() - t0, 1)
    stats["prefill_s"] = round(stats["prefill_s"], 1)
    stats["step_s"] = round(stats["step_s"], 1)
    return stats
