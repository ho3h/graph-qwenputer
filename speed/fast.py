#!/usr/bin/env python3
"""The standard fast runner for X2.10's question runs. See speed/README.md for what is proven, per firmware and flow.

    python speed/fast.py --machine tok --flow read-t6 --questions Q.json --out results/run1 --stock 2
    python speed/fast.py --build-blocks tok                     # once per checkpoint, CPU

From Python, one machine per process:

    import fast
    fast.setup("tok")                                            # or setup("tok", elf=PATH), setup("tok", ckpt=PATH)
    fast.run(fast.items([["cities/c024", 12], ...]), fast.flow("print-chain3", limit_stop=True), "results/run1", stock=2)

What it does: Qwen's layers run as their nonzero blocks in up to 15 rows per GPU step; chip tokens on the C engine, one per row; prefill from the engine's residual, skipping the chip layers. Reference lock on, as every other runner.

What decides the path: a firmware and flow with an entry in speed/proofs.json run fast. Anything else runs slow, on stock modules one question at a time, and every record says so.
"""
import argparse
import copy
import dataclasses
import hashlib
import json
import os
import random
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
SSD = os.path.expanduser("~/Models/x210")
MACHINES = {
    "tok": {"code": "tok", "ckpt": f"{SSD}/x210-tok", "elf": "tok/build/tok.elf", "blocks": f"{SSD}/x210-tok-blocks", "delivery": "normal"},
    "clean": {"code": "tok", "ckpt": f"{SSD}/x210-tok", "elf": "t8/fw/build/clean.elf", "blocks": f"{SSD}/x210-tok-blocks", "delivery": "normal", "overlay": "t8/fw", "noun": True},   # t8's strict cleaner: not built yet; no proof until its hash has one
    "writes": {"code": "tok", "ckpt": f"{SSD}/x210-tok", "elf": "t8/fw/build_writes/writes.elf", "blocks": f"{SSD}/x210-tok-blocks", "delivery": "normal", "overlay": "t8/fw", "noun": True},   # the build Theo chose: chase with closed and reopened (t8/REGISTRATION.md, step W)
    "fw": {"code": "exec", "ckpt": f"{SSD}/x210-rvc", "elf": "fw/build/fw.elf", "blocks": f"{SSD}/x210-rvc-blocks", "delivery": "bytes"},
}
NOTE_G = "No node has exactly that name; call again with only the node's name, without any word that just describes it."
QUERY_ERRORS = {"NONE", "NORELATION", "AMBIGUOUS", "BADARG", "NOFUNCTION", "TOOLONG"}
ERROR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG|Stopped early)\b")
LIMIT = re.compile(r"^(?:leg \d+: )?(END|MULTI|NOCHANGE|CLOSED|NOPATH|Stopped early)\b")
MAX_ROWS = 15      # 16 x 32 x 128 = 65,536 elements: reductions change kernel there (results/s11_rows.json)
g = types.SimpleNamespace()     # the machine's modules, after setup()


@dataclasses.dataclass
class Flow:
    """What the runner does around Qwen and the machine. Fields below `cap` change what happens after the first line, and are off unless asked for."""
    name: str
    mode: str                     # "print": the machine's first clean line is the answer. "read": Qwen reads it and replies in its own words
    tools: str = "chase"          # "chase" (one tool), "base" (ten tools), or "writes" (chase with closed and reopened, and the worked turns in the prompt)
    extra: bool = True            # chain2's "make exactly one tool call" sentence
    told: bool = True             # chain2's "spelled out one character at a time" sentence
    retries: int = 2              # print: more attempts after an error line
    turn: int = 768               # tokens an attempt or turn may run
    max_calls: int = 12           # read
    total: int = 3072             # read
    prefill_retry: bool = False   # print: a retry after a query error starts with <tool_call>
    note: str | None = None       # print: a fixed sentence after a NONE line, fed by the runner
    limit_stop: bool = False      # print: a limit line ends the turn
    cap: int | None = None        # print: an attempt without a call ends here. Fitted on chain3's records at 320
    lazy_echo: bool = False       # print: echoes reach Qwen's layers only if a retry follows
    readback: int = 0             # print: after the answer, Qwen's own words up to this many tokens, kept apart, unscored

    def key(self):
        """What a proof is for. A flow change has its own key."""
        k = f"{self.mode}/{self.tools}/extra={int(self.extra)}/told={int(self.told)}"
        if self.mode == "print":
            k += f"/retries={self.retries}/prefill={int(self.prefill_retry)}/note={int(bool(self.note))}/rb={self.readback}"
        else:
            k += f"/calls={self.max_calls}/total={self.total}"
        ch = [n for n, on in (("limit_stop", self.limit_stop), (f"cap{self.cap}", self.cap), ("lazy_echo", self.lazy_echo)) if on]
        return k + ("/" + "+".join(ch) if ch else "")


PRESETS = {
    "print-chain3": dict(mode="print"),                                                  # rvc/chain3.py
    "print-chain4": dict(mode="print", prefill_retry=True, note=NOTE_G),                  # rvc/chain4.py's `both`
    "print-one": dict(mode="print", retries=0),                                           # t8's chain: one call, no retries
    "read-one": dict(mode="read", extra=False, told=False),                               # t8's other mode: one tool, Qwen replies; caps as T6: 12 calls, 768 a turn, 3,072 a question
    "print-writes": dict(mode="print", retries=0, tools="writes"),                        # the frozen flow, print
    "read-writes": dict(mode="read", tools="writes", extra=False, told=False),            # the frozen flow, pass to Qwen
    "read-t6": dict(mode="read", tools="base", extra=False, told=False),                  # tok/drive.py's T6
}


def flow(name, **kw):
    f = Flow(name=name, **{**PRESETS[name], **kw})
    if f.mode == "read" and (f.limit_stop or f.cap or f.lazy_echo or f.note or f.prefill_retry):
        raise ValueError("read mode: Qwen must see every echo, and the runner writes nothing; these flags are print-mode only")
    if f.lazy_echo and f.readback:
        raise ValueError("lazy_echo with readback: Qwen reads the line, so it must see the echo")
    return f


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def setup(machine, elf=None, ckpt=None):
    """Point this process at one machine. elf and ckpt override the machine's defaults; the proof lookup goes by the ELF's hash."""
    m = dict(MACHINES[machine])
    if machine == "writes" and os.environ.get("T8_R1") == "1":          # exam/R1.md
        elf = elf or os.path.join(X210, "t8/fw/build_r1/writes.elf")
    elf = os.path.abspath(elf) if elf else os.path.join(X210, m["elf"])
    ckpt = ckpt or m["ckpt"]
    assert os.path.exists(elf), elf
    assert os.path.exists(os.path.join(ckpt, "chipformer.json")), ckpt
    os.environ["CHIP_FIRMWARE"] = elf
    os.environ["TOK_CKPT"] = ckpt
    code = os.path.join(X210, m["code"])
    for p in (os.path.join(X210, "vendor", "qwenputer-riscv"), os.path.join(X210, "rvc"), code):
        sys.path.insert(0, p)
    graph_fn = lambda gr: gr
    if m.get("overlay"):                                   # t8/fw/overlay.py must be first: boot header, then tok's overlay
        sys.path.insert(0, os.path.join(X210, m["overlay"]))
        import overlay
        if not hasattr(overlay, "set_text"):                # t8's overlay wraps tok's; tok/common.py and tok/chat.py expect set_text on `overlay`
            overlay.set_text = overlay.O.set_text
    if m.get("noun"):
        import noun as N
        graph_fn = N.with_noun
    worked = None
    if machine == "writes":
        import worked
    import common as C                                     # tok/common.py loads its overlay first
    import box as X
    X.MODEL = f"{SSD}/Qwen3.5-4B"
    X.ELF = elf
    X.build_elf = lambda: elf
    import chain2 as C2
    import decode as D
    import reflib
    import score as SC
    import numpy as np
    import torch
    torch.set_grad_enabled(False)
    import torch.nn.functional as F
    from chipformer.rv import bridge as BR, core, hf
    from chipformer.rv import spec as S
    D.CKPT = ckpt
    if m["delivery"] == "normal":
        import fragments as FR
        head, tail = FR.HEAD.encode(), FR.TAIL.encode()
    else:
        head, tail = C2.HEAD, C2.TAIL
    g.__dict__.update(worked=worked, C=C, X=X, HT=X.HT, C2=C2, D=D, reflib=reflib, SC=SC, np=np, torch=torch, F=F, BR=BR, core=core, hf=hf, S=S, HEAD=head, TAIL=tail, machine=machine, elf=elf, elf_sha=sha(elf), ckpt=ckpt, blocks=m["blocks"], delivery=m["delivery"], chip_code=code, graph_fn=graph_fn, split=(reflib.split_reading if m.get("noun") else None))
    return g


def tuples(its):
    """(gr, q, tag) tuples from a caller, such as t8/fw/chain.py's hard items: tags as lists become tuples."""
    return [(a, b, tuple(c) if isinstance(c, list) else c) for a, b, c in its]


def items(pairs):
    """[graph name, question id] pairs -> what run() takes."""
    out = []
    for gname, i in pairs:
        gp, qp = g.D.graph_path(gname)
        gr = json.load(open(gp))
        q = {x["id"]: x for x in json.load(open(qp))["questions"]}[i]
        out.append((gr, q, (gname, i)))
    return out


# --- blocks ------------------------------------------------------------------------------------------
def build_blocks(out=None):
    """Once per checkpoint, CPU. The checkpoint's values, unchanged, cropped to nonzero blocks, in one file on the SSD."""
    from transformers import AutoTokenizer, Qwen3_5ForCausalLM
    torch = g.torch
    out = out or g.blocks
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    meta = json.load(open(os.path.join(g.ckpt, "chipformer.json")))
    n_chip = meta["chip_layers"]
    model = Qwen3_5ForCausalLM.from_pretrained(g.ckpt, dtype=torch.bfloat16)
    idx = {"tensors": {}, "linear": {}, "ckpt": g.ckpt, "ckpt_meta_sha256": sha(os.path.join(g.ckpt, "chipformer.json")), "ckpt_index_sha256": sha(os.path.join(g.ckpt, "model.safetensors.index.json"))}
    pos = 0
    f = open(os.path.join(out, "blocks.bin.tmp"), "wb")

    def put(name, t):
        nonlocal pos
        b = t.detach().contiguous()
        b = b.view(torch.uint16).numpy() if b.dtype == torch.bfloat16 else b.numpy()
        f.write(b.tobytes())
        idx["tensors"][name] = {"dtype": str(t.dtype).split(".")[-1], "shape": list(t.shape), "offset": pos, "bytes": b.nbytes}
        pos += b.nbytes
    lm = model.model
    for i in range(n_chip, len(lm.layers)):
        layer = lm.layers[i]
        for pname, p in layer.named_parameters():
            mod = layer.get_submodule(pname.rsplit(".", 1)[0]) if "." in pname else layer
            full = f"layers.{i}.{pname}"
            if isinstance(mod, torch.nn.Linear):
                nz = p.data != 0
                rr, cc = nz.any(1).nonzero().flatten(), nz.any(0).nonzero().flatten()
                r0, r1, c0, c1 = int(rr[0]), int(rr[-1]) + 1, int(cc[0]), int(cc[-1]) + 1
                put(full, p.data[r0:r1, c0:c1])
                idx["linear"][full] = {"rows": [r0, r1], "cols": [c0, c1], "shape": list(p.shape)}
            else:
                put(full, p.data)
    put("norm.weight", lm.norm.weight.data)
    nq = len(AutoTokenizer.from_pretrained(g.X.MODEL))
    put("head", model.lm_head.weight.data[:nq, :meta["tau_dim"] + 1])
    put("inv_freq", lm.rotary_emb.inv_freq.data)
    idx.update(attention_scaling=float(lm.rotary_emb.attention_scaling), attn=model.config._attn_implementation, nq=nq, bytes=pos, seconds=round(time.time() - t0, 1))
    f.close()
    os.replace(os.path.join(out, "blocks.bin.tmp"), os.path.join(out, "blocks.bin"))
    json.dump(idx, open(os.path.join(out, "index.json"), "w"))
    print(f"blocks {pos / 2**30:.2f} GiB at {out}, {idx['seconds']} s", flush=True)


class FastChatContext(types.SimpleNamespace):
    pass


def load_blocks():
    """Qwen's blocks on the GPU, nothing dense, no chip weights. Fast path only."""
    from chipformer.q35 import fast as QF
    from chipformer.q35.ir import Target
    from chipformer.rv.chat import RvChat
    from pathlib import Path
    from transformers import AutoConfig, AutoTokenizer
    from transformers.models.qwen3_5 import modeling_qwen3_5 as M
    from chat import ExecChat
    from cexec import CExec
    torch, np = g.torch, g.np
    t0 = time.time()
    idx = json.load(open(os.path.join(g.blocks, "index.json")))
    for key, name in (("ckpt_meta_sha256", "chipformer.json"), ("ckpt_index_sha256", "model.safetensors.index.json")):
        if key in idx:
            assert idx[key] == sha(os.path.join(g.ckpt, name)), f"blocks {g.blocks} aren't from {g.ckpt}: rebuild them"
    cfg = AutoConfig.from_pretrained(g.ckpt)
    cfg._attn_implementation = idx["attn"]
    meta = json.load(open(os.path.join(g.ckpt, "chipformer.json")))
    n_chip = meta["chip_layers"]
    mm = np.memmap(os.path.join(g.blocks, "blocks.bin"), dtype=np.uint8, mode="r")

    def arr(name):
        e = idx["tensors"][name]
        return np.frombuffer(mm, dtype=np.float32 if e["dtype"] == "float32" else np.uint16, count=int(np.prod(e["shape"])), offset=e["offset"]).reshape(e["shape"]), e

    def get(name):
        a, e = arr(name)
        t = torch.from_numpy(np.array(a))
        return (t.view(torch.bfloat16) if e["dtype"] == "bfloat16" else t).to("mps")
    layers = []
    with torch.device("meta"):
        skel = [M.Qwen3_5DecoderLayer(cfg, i) for i in range(n_chip, cfg.num_hidden_layers)]
    for i, layer in zip(range(n_chip, cfg.num_hidden_layers), skel):
        for pname, _ in list(layer.named_parameters()):
            modname, leaf = pname.rsplit(".", 1) if "." in pname else ("", pname)
            mod = layer.get_submodule(modname) if modname else layer
            full = f"layers.{i}.{pname}"
            if isinstance(mod, torch.nn.Linear):
                e = idx["linear"][full]
                parent_name, cname = modname.rsplit(".", 1)
                s = QF.SparseLinear.__new__(QF.SparseLinear)
                torch.nn.Module.__init__(s)
                s.out_features, s.in_features = e["shape"]
                s.r0, s.r1 = e["rows"]
                s.c0, s.c1 = e["cols"]
                s.dense_above = None
                s.dense = None
                s.weight = get(full)
                setattr(layer.get_submodule(parent_name), cname, s)
            else:
                setattr(mod, leaf, torch.nn.Parameter(get(full), requires_grad=False))
        layers.append(layer.eval())
    norm = M.Qwen3_5RMSNorm(cfg.hidden_size, eps=cfg.rms_norm_eps)
    norm.weight = torch.nn.Parameter(get("norm.weight"), requires_grad=False)
    rot = M.Qwen3_5TextRotaryEmbedding(config=cfg)
    rot.inv_freq = get("inv_freq")
    rot.attention_scaling = idx["attention_scaling"]
    head = get("head")
    head_cpu, _ = arr("head")
    torch.mps.synchronize()
    t_weights = time.time() - t0
    chat = RvChat.__new__(RvChat)
    chat.path = Path(g.ckpt)
    chat.meta = meta
    chat.dev = "mps"
    chat.n_chip, chat.v0 = n_chip, meta["chip_token_offset"]
    chat.tok = AutoTokenizer.from_pretrained(chat.path)
    chat.T = g.BR.Text(chat.path / "tokenizer.json")
    if hasattr(g.C, "O"):
        g.C.O.set_text(chat.T)
    chat.store_cfg = None
    chat.c = g.core.build(Target(cfg.linear_num_key_heads, cfg.linear_num_value_heads, cfg.intermediate_size), chat.T, None)
    chat.code_dims = torch.tensor(meta["code_dims"], device="mps")
    chat.id_dims = None
    chat.store_snap = None
    chat.eos = {248046, 248044}
    chat.fast = chat.executor = chat.verify = False
    chat.model = types.SimpleNamespace(config=cfg)
    chat.lm = types.SimpleNamespace(layers=[None] * n_chip + layers, norm=norm, rotary_emb=rot)
    ec = ExecChat.__new__(ExecChat)
    ec.chat = chat
    ec.cx = CExec(chat.c, chat.T)
    ec.d0 = meta["chip_dims_offset"]
    cols = meta["code_dims"] + [meta["tau_dim"], meta["mu_dim"]]
    ec.keep_cols_np = np.array(cols)
    ec.keep_cols = torch.tensor(cols, device="mps")
    ec.hidden = meta["hidden"]
    ec.n_code = len(meta["code_dims"])
    ec.dev = "mps"
    ec.rows = {}
    ec.low_bits = lambda mid: head_cpu[mid, : ec.d0]        # from the file, no GPU sync
    return FastChatContext(ec=ec, nq=idx["nq"], layers=layers, head=head, head_cpu=head_cpu, tau=meta["tau_dim"], load={"weights_s": round(t_weights, 1), "total_s": round(time.time() - t0, 1)})


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


# --- one question ------------------------------------------------------------------------------------
def forced_ids(T, tok, s):
    """The runner's sentence as the machine's delivery would print it."""
    if g.delivery == "bytes":
        return [T.printable[b] for b in s.encode()] + [T.printable[10]] * 2
    return tok.encode(s + "\n\n", add_special_tokens=False)


def run_question(ctx, ex, gr, q, tool_list, fl, verify=False):
    """A generator, one question. It asks the driver for Qwen's steps; everything else, including the machine and the lock, is here.
        ("prefill", prompt)                -> the first token
        ("text", residual bits, pos, need, ct) -> Qwen's argmax if need, else None
        ("done", record)
    With verify the question runs stock and engine in lockstep on the dense model in ctx.ec.chat, every position over all dims, and asks for nothing but "done".

    Merged from rvc/chain2.py and rvc/chain4.py (print) and tok/drive.py (read). The proof that it matches them is in speed/proofs.json."""
    np, torch, S, BR, HT = g.np, g.torch, g.S, g.BR, g.HT
    ec = ctx.ec
    chat = ec.chat
    T, tok = chat.T, chat.tok
    IM_END, EOS = tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")
    stops = {T.TCC, IM_END, EOS}
    gr = g.graph_fn(gr)
    graph = g.reflib.Graph(gr)
    setup_calls = q.get("setup") or []
    for s in setup_calls:
        graph.call(s["fn"], s["args"])
    m = g.D.parked_machine(gr, T, setup_calls)
    system = HT.system_prompt(gr) + (g.C2.EXTRA if fl.extra else "") + (g.C2.TOLD if fl.told else "")
    hist = g.worked.HISTORY if fl.tools == "writes" else []
    prompt = chat.prompt_ids([{"role": "system", "content": system}] + hist + [{"role": "user", "content": q["text"]}], tools=tool_list)
    lock = BR.Session(T, copy.deepcopy(m))
    lock.history(prompt)
    t0 = time.time()
    g.core.snapshot(chat.c, m)
    ex.p.flags = 0
    ex.start([ec.stream(i) for i in prompt])
    ts = time.perf_counter()
    cache = None
    if verify:
        out = chat._prefill(prompt)
        cache = out.past_key_values
        g.hf.inject(chat.c, cache)
        nxt = int(torch.argmax(out.logits[0, -1, : ctx.nq]))
    else:
        nxt = yield ("prefill", prompt)
    t_prefill = time.perf_counter() - ts
    pos = len(prompt)
    t_chip = t_stock = 0.0
    n_chip = n_qwen = n_echo = n_forced = own_ok = n_gpu = n_deferred = head_bad = verified = gen = 0
    calls, seg, echo, expect, deferred, forced, segments = [], [], [], [], [], [], []
    feeding = seed_tco = False
    answer, status, lock_error, attempt, mismatch, no_call_text = None, None, None, 0, None, None
    turn = fl.cap or fl.turn
    while status is None:
        st = nxt - chat.v0 if nxt >= chat.v0 else BR.text_token(nxt)
        if feeding:                                         # the runner's tokens
            n_forced += 1
            if not forced:
                seg = [T.TCO] if seed_tco else []
        elif expect:
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
                wrapped = raw.startswith(g.HEAD) and raw.endswith(g.TAIL)
                res = (raw[len(g.HEAD):-len(g.TAIL)] if wrapped else raw).decode("utf-8", "replace")
                c = calls[-1]
                c.update(result=res, wrapped=wrapped, same_as_host=res == c["host_result"], response_ids=echo, echo=len(echo))
                segments.append({"by": "tool", "ids": echo})
                answer = res
                if fl.mode == "print":
                    if g.split:                             # a cleaned name prints "name read as ..." first: the answer is the result after it
                        c["reading"], res = g.split(res)
                        if fl.tools == "writes":            # write lines come before the result too: the result is the last line
                            head = res.split("\n")
                            c["write_lines"], res = head[:-1], head[-1]
                        answer = res
                    em = ERROR.match(res)
                    if not em or attempt == fl.retries or (fl.limit_stop and LIMIT.match(res)):
                        status = "answered"
                        break
                    attempt += 1
                    word = em.group(1)
                    seed_tco = fl.prefill_retry and word in QUERY_ERRORS
                    forced = []
                    if fl.note and word == "NONE":
                        forced += forced_ids(T, tok, fl.note)
                    if seed_tco:
                        forced.append(T.TCO)
                    if forced:
                        lock.history(forced)
                seg, echo = [], []
        elif st < S.VOCAB:
            lock_error = {"got": S.name(st), "want": "text", "at_call": len(calls)}
            status = "lock"
            break
        else:
            seg.append(nxt)
            n_qwen += 1
            gen += 1
            if nxt in stops or (fl.mode == "print" and len(seg) >= turn):
                segments.append({"by": "qwen", "ids": seg})
                if nxt != T.TCC:
                    if fl.mode == "print":
                        status = "no_call"
                        no_call_text = tok.decode(seg, skip_special_tokens=False)
                    else:
                        status = "answered"
                    break
                if fl.mode == "read" and len(calls) == fl.max_calls:
                    status = "cap"
                    break
                tco = max((i for i, t in enumerate(seg) if t == T.TCO), default=-1)
                ids = seg[tco + 1:-1]
                inner = tok.decode(ids, skip_special_tokens=False)
                call = HT.parse_call(inner)
                if fl.mode == "read" and tco < 0:
                    call["error"] = (call["error"] + "; " if call["error"] else "") + "no <tool_call> in this turn"
                k = len(lock.toks)
                lock.qwen([nxt])
                expect = list(lock.toks[k + 1:])
                calls.append({"text": inner, "ids": ids, "fn": call["fn"], "args": call["args"], "raw": call.get("raw"), "parse_error": call.get("error"), "no_tco": tco < 0, "host_result": HT.answer_call(graph, call), "cap": len(ids), "chip": sum(t < S.VOCAB for t in expect), "machine_ran": True})
                echo = []
                seg = []
            elif fl.mode == "read" and (len(seg) >= fl.turn or gen >= fl.total):
                segments.append({"by": "qwen", "ids": seg})
                status = "budget"
                break
            else:
                lock.qwen([nxt])
        chip_in = nxt >= chat.v0
        ct = None
        if verify:
            tv = time.perf_counter()
            hc, logits = chat._layers(nxt, cache, None if chip_in else pos)
            hcu = hc.detach().cpu().view(torch.uint16).numpy()
            t_stock += time.perf_counter() - tv
            keep = ex.step(st).copy()
            bits, _ = ec.exec_bits(nxt, keep)
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
                nxt = ct if ct is not None else int(torch.argmax(logits[: ctx.nq]))
        elif chip_in:
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
            bits, _ = ec.exec_bits(nxt, keep)
            t_chip += time.perf_counter() - ts
            if fl.lazy_echo and ct is not None and not forced:  # Qwen's layers can wait: the circuit owns the next token
                deferred.append((bits, pos, ct))
                pos += 1
                nxt = ct
            else:
                for b, p_, c_ in deferred:
                    yield ("text", b, p_, False, c_)
                    n_gpu += 1
                    n_deferred += 1
                deferred = []
                top = yield ("text", bits, pos, ct is None and not forced, ct)
                n_gpu += 1
                pos += 1
                nxt = ct if ct is not None else top
        if ex.p.flags:
            mismatch = {"engine_flags": ex.flags(), "at_call": len(calls)}
            status = "engine_flag"
            break
        if forced:
            nxt, feeding = forced.pop(0), True
        else:
            feeding = False
    rb_ids, rb_end = [], None
    if fl.readback and status == "answered":
        rb_end = "cap"
        for _ in range(fl.readback):
            st = BR.text_token(nxt)
            keep = ex.step(st).copy()
            if verify:
                hc, logits = chat._layers(nxt, cache, pos)
                bits, _ = ec.exec_bits(nxt, keep)
                verified += 1
                if not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                    mismatch, status = {"at": "readback"}, "verify_mismatch"
                    break
                nxt = int(torch.argmax(logits[: ctx.nq]))
            else:
                bits, _ = ec.exec_bits(nxt, keep)
                nxt = yield ("text", bits, pos, True, None)
                n_gpu += 1
            pos += 1
            if nxt in stops or nxt == T.TCO:
                rb_end = "tool_call" if nxt == T.TCO else "stop"
                break
            rb_ids.append(nxt)
    state = ec.state_diff(cache) if verify and status != "verify_mismatch" and ex is ec.cx else None
    if state and state["big"]:
        mismatch, status = {"state": state}, "verify_mismatch"
    if fl.mode == "read":
        final = None
        if status == "answered":
            last = tok.decode(segments[-1]["ids"], skip_special_tokens=False)
            final = last.split("</think>")[-1].replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
        answer = final
    correct = g.SC.score(answer, q, graph.labels) if answer is not None or fl.mode == "read" else False
    reworded = g.reflib.reword(q["answer_text"]) if g.split and q.get("answer_text") else None   # data/dev's golds hold the old limit-line words until a rebuild
    yield ("done", {"gold_text_reworded": reworded, "exact_reworded": (answer == reworded) if reworded is not None else None, "id": q["id"], "kind": q.get("kind"), "text": q["text"], "gold": q.get("answer"), "gold_text": q.get("answer_text"), "status": status, "n_calls": len(calls), "calls": calls, "final": answer, "correct": correct, "no_call_text": no_call_text, "segments": segments,
                    "prompt_tokens": len(prompt), "lock_error": lock_error, "own_ok": own_ok, "chip_tokens": n_chip, "qwen_tokens": n_qwen, "echo_tokens": n_echo, "runner_tokens": n_forced, "gpu_text_steps": n_gpu, "deferred_ran": n_deferred, "deferred_never_ran": len(deferred),
                    "head_mismatch": head_bad, "verified_positions": verified, "verify_mismatch": mismatch, "end_state_diff": state, "chip_seconds": round(t_chip, 3), "stock_seconds": round(t_stock, 2), "prefill_seconds": round(t_prefill, 3), "seconds": round(time.time() - t0, 2), "engine": ex.lib_hash, "engine_flags": ex.flags(),
                    "readback_text": tok.decode(rb_ids, skip_special_tokens=False) if rb_end else None, "readback_tokens": len(rb_ids), "readback_end": rb_end})


# --- the fast driver ---------------------------------------------------------------------------------
def rms_rows(norm, x):
    """Qwen3_5RMSNorm with the mean over the residual taken row by row: a batched mean over 3,968 dims gives other bits (results/s5b_reduce.json)."""
    torch = g.torch
    x32 = x.float()
    sq = x32.pow(2)
    B = x.shape[0]
    var = sq.mean(-1, keepdim=True) if B == 1 else torch.cat([sq[j:j + 1].mean(-1, keepdim=True) for j in range(B)])
    return (x32 * torch.rsqrt(var + norm.eps) * (1.0 + norm.weight.float())).type_as(x)


class Slots:
    """B rows of Qwen's state: linear layers one tensor per layer, attention keys per row, attention itself per row."""

    def __init__(self, ctx, B):
        from transformers.models.qwen3_5 import modeling_qwen3_5 as M
        from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS
        self.M = M
        self.attn = ALL_ATTENTION_FUNCTIONS
        self.ctx, self.B = ctx, B
        self.chat = ctx.ec.chat
        self.n_chip = self.chat.n_chip
        self.types = self.chat.model.config.layer_types
        self.linear, self.kv = {}, {}

    def install(self, row, cache):
        torch = g.torch
        for i in range(self.n_chip, len(self.chat.lm.layers)):
            lay = cache.layers[i]
            if hasattr(lay, "recurrent_states"):
                c, r = lay.conv_states[0], lay.recurrent_states[0]
                if i not in self.linear:
                    self.linear[i] = (torch.zeros(self.B, *c.shape[1:], dtype=c.dtype, device="mps"), torch.zeros(self.B, *r.shape[1:], dtype=r.dtype, device="mps"))
                self.linear[i][0][row] = c[0]
                self.linear[i][1][row] = r[0]
            else:
                self.kv.setdefault(i, [None] * self.B)[row] = (lay.keys, lay.values)

    def free(self, row):
        for i in self.kv:
            self.kv[i][row] = None

    def step(self, rows, bits, pos, need):
        torch, F = g.torch, g.F
        chat = self.chat
        n = len(rows)
        idx = None if n == self.B else torch.tensor(rows, device="mps")
        h = torch.from_numpy(bits).to("mps").view(torch.bfloat16).unsqueeze(1)
        tp = torch.tensor(pos, device="mps", dtype=torch.long).view(n, 1)
        pe = chat.lm.rotary_emb(h, tp.unsqueeze(0).expand(3, -1, -1))
        for i in range(self.n_chip, len(chat.lm.layers)):
            lay = chat.lm.layers[i]
            h = self._linear(lay, i, h, idx) if self.types[i] == "linear_attention" else self._full(lay, i, h, pe, rows)
        js = [j for j in range(n) if need[j]]
        out = [None] * n
        if js:
            nn = rms_rows(chat.lm.norm, h)
            sel = nn if len(js) == n else nn.index_select(0, torch.tensor(js, device="mps"))
            am = torch.argmax(F.linear(sel[..., : self.ctx.tau + 1], self.ctx.head)[:, -1], dim=-1).tolist()
            for j, a_ in zip(js, am):
                out[j] = a_
        return out

    def _linear(self, layer, i, x, idx):
        F, M = g.F, self.M
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
        query, key, value = g.torch.split(mixed, [la.key_dim, la.key_dim, la.value_dim], dim=-1)
        rr = la.num_v_heads // la.num_k_heads
        query = query.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(rr, dim=2)
        key = key.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(rr, dim=2)
        value = value.reshape(B, 1, -1, la.head_v_dim)
        gg = -la.A_log.float().exp() * F.softplus(a.float() + la.dt_bias)
        state = rs if idx is None else rs.index_select(0, idx)
        out, new = M.torch_recurrent_gated_delta_rule(query, key, value, g=gg, beta=b.sigmoid(), initial_state=state, output_final_state=True, use_qk_l2norm_in_kernel=True)
        if idx is None:
            self.linear[i] = (cs, new)
        else:
            rs.index_copy_(0, idx, new)
        y = la.norm(out.reshape(-1, la.head_v_dim), z.reshape(-1, la.head_v_dim)).reshape(B, 1, -1)
        x = residual + la.out_proj(y)
        return x + layer.mlp(rms_rows(layer.post_attention_layernorm, x))

    def _full(self, layer, i, x, pe, rows):
        torch, M = g.torch, self.M
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
        attn = self.attn.get_interface(a.config._attn_implementation, M.eager_attention_forward)
        outs = []
        for j, row in enumerate(rows):
            keys = torch.cat([kv[row][0], kr[j:j + 1]], dim=-2)
            vals = torch.cat([kv[row][1], vs[j:j + 1]], dim=-2)
            kv[row] = (keys, vals)
            oj, _ = attn(a, qr[j:j + 1], keys, vals, None, dropout=0.0, scaling=a.scaling)
            outs.append(oj.reshape(1, 1, -1).contiguous())
        o = (torch.cat(outs) if B > 1 else outs[0]) * torch.sigmoid(gate)
        x = residual + a.o_proj(o)
        return x + layer.mlp(rms_rows(layer.post_attention_layernorm, x))


def prefill_fast(ctx, exp, prompt):
    """Qwen's layers on the prompt from the engine's residual. Returns (first token, cache)."""
    torch, np, F = g.torch, g.np, g.F
    from transformers import DynamicCache
    ec = ctx.ec
    chat = ec.chat
    exp.clear()
    keep = exp.run([ec.stream(i) for i in prompt], keep=True).copy()
    u = keep.view(np.uint32)
    rr = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    hcb = np.zeros((len(prompt), ec.hidden), np.uint16)
    hcb[:, : ec.d0] = ctx.head_cpu[np.array(prompt), : ec.d0]
    hcb[:, ec.keep_cols_np] = (rr >> 16).astype(np.uint16)
    hc = torch.from_numpy(hcb).to("mps").view(torch.bfloat16).unsqueeze(0)
    n = hc.shape[1]
    cache = DynamicCache(config=chat.model.config)
    tp = torch.arange(n, device="mps").view(1, -1)
    pe = chat.lm.rotary_emb(hc, tp.view(1, 1, -1).expand(3, 1, -1))
    mask = torch.ones(n, n, dtype=torch.bool, device="mps").tril(0)[None, None]
    h = hc
    for i in range(chat.n_chip, len(chat.lm.layers)):
        ty = chat.model.config.layer_types[i]
        h = chat.lm.layers[i](h, position_embeddings=pe, attention_mask=mask if ty == "full_attention" else None, position_ids=tp, past_key_values=cache)
    y = F.linear(chat.lm.norm(h)[:, -1:, :][..., : ctx.tau + 1], ctx.head)[0, -1]
    return int(torch.argmax(y)), cache


def drive_fast(ctx, its, fl, tools, rows, on_done, deadline=None):
    np = g.np
    S_ = Slots(ctx, rows)
    engines = make_engines(ctx, rows + 1)
    exp = engines.pop()
    todo = list(its)
    gens, req, tags = [None] * rows, [None] * rows, [None] * rows
    st = {"gpu_steps": 0, "row_steps": 0, "prefill_s": 0.0, "step_s": 0.0}
    t0 = time.time()

    def advance(row, val):
        while True:
            r = gens[row].send(val)
            if r[0] == "prefill":
                s = time.perf_counter()
                top, cache = prefill_fast(ctx, exp, r[1])
                S_.install(row, cache)
                del cache
                st["prefill_s"] += time.perf_counter() - s
                val = top
                continue
            if r[0] == "done":
                on_done(tags[row], r[1])
                S_.free(row)
                gens[row] = req[row] = None
                return
            req[row] = r
            return
    while True:
        for row in range(rows):
            if gens[row] is None and todo and not (deadline and time.time() > deadline):
                gr, q, tag = todo.pop(0)
                gens[row] = run_question(ctx, engines[row], gr, q, tools, fl)
                tags[row] = tag
                advance(row, None)
        act = [r for r in range(rows) if req[r] is not None]
        if not act:
            if not todo or (deadline and time.time() > deadline):
                break
            continue
        bits = np.stack([req[r][1] for r in act])
        s = time.perf_counter()
        out = S_.step(act, bits, [req[r][2] for r in act], [req[r][3] for r in act])
        st["step_s"] += time.perf_counter() - s
        st["gpu_steps"] += 1
        st["row_steps"] += len(act)
        for r, a in zip(act, out):
            advance(r, a)
    st.update(seconds=round(time.time() - t0, 1), prefill_s=round(st["prefill_s"], 1), step_s=round(st["step_s"], 1), left=len(todo))
    return st


def load_stock():
    """The dense model, on stock modules: for the slow path and the stock sample. 20 GiB on the GPU."""
    from chat import ExecChat
    from transformers import AutoTokenizer
    t0 = time.time()
    ec = ExecChat(g.ckpt)
    if hasattr(g.C, "O"):
        g.C.O.set_text(ec.chat.T)
    return types.SimpleNamespace(ec=ec, nq=len(AutoTokenizer.from_pretrained(g.X.MODEL)), load={"total_s": round(time.time() - t0, 1)})


def drive_slow(ctx, its, fl, tools, on_done, deadline=None):
    """One question at a time on stock modules: the slow path, with the head check. Chip tokens on the engine, as every executor run."""
    torch = g.torch
    ec = ctx.ec
    chat = ec.chat
    st = {"text_s": 0.0, "prefill_s": 0.0, "head_mismatch": 0}
    t0 = time.time()
    for gr, q, tag in its:
        if deadline and time.time() > deadline:
            break
        ge = run_question(ctx, ec.cx, gr, q, tools, fl)
        r = next(ge)
        cache = None
        while True:
            if r[0] == "prefill":
                s = time.perf_counter()
                out = chat._prefill(r[1])
                cache = out.past_key_values
                val = int(torch.argmax(out.logits[0, -1, : ctx.nq]))
                st["prefill_s"] += time.perf_counter() - s
            elif r[0] == "text":
                s = time.perf_counter()
                hc = torch.from_numpy(r[1]).to("mps").view(torch.bfloat16)
                logits = chat._qwen_step(hc, cache, r[2])
                top = int(torch.argmax(logits))
                if r[4] is not None and top != r[4]:
                    st["head_mismatch"] += 1
                val = int(torch.argmax(logits[: ctx.nq])) if r[3] else None
                st["text_s"] += time.perf_counter() - s
            else:
                on_done(tag, r[1])
                break
            r = ge.send(val)
        del cache
        torch.mps.empty_cache()
    st.update(seconds=round(time.time() - t0, 1), prefill_s=round(st["prefill_s"], 1), text_s=round(st["text_s"], 1))
    return st


# --- the proof table, the stock sample, the run --------------------------------------------------------
def proof(fl):
    p = os.path.join(HERE, "proofs.json")
    if not os.path.exists(p):
        return None
    for e in json.load(open(p)):
        if e["elf_sha256"] == g.elf_sha and e["flow"] == fl.key():
            return e
    return None


def same_tokens(a, b, flags_differ=False):
    """Two records of one question: every Qwen and machine token equal. With flags_differ, as far as both have tokens."""
    d = {}
    ca, cb = a["calls"], b["calls"]
    d["ids"] = all(x["ids"] == y["ids"] for x, y in zip(ca, cb))
    d["lines"] = all(x.get("result") == y.get("result") for x, y in zip(ca, cb))
    d["responses"] = all(x.get("response_ids") == y.get("response_ids") for x, y in zip(ca, cb))
    if not flags_differ:
        d["n_calls"] = len(ca) == len(cb)
        d["final"] = a["final"] == b["final"]
        d["status"] = a["status"] == b["status"]
        d["qwen"] = a["qwen_tokens"] == b["qwen_tokens"]
        d["echo"] = a["echo_tokens"] == b["echo_tokens"]
        d["chip"] = a["chip_tokens"] == b["chip_tokens"]
        d["segments"] = a.get("segments") == b.get("segments") if "segments" in a and "segments" in b else True
        d["prose"] = a.get("no_call_text") == b.get("no_call_text")
    return d


def stock_sample(its, fl, tools, records, n, seed, limit_s, out):
    """Whole questions, stock and engine in lockstep, every position over all dims, and tokens against the fast record. The check the batched path drops."""
    if not n:
        return None
    ctx = load_stock()
    order = list(range(len(its)))
    random.Random(seed).shuffle(order)
    t0 = time.time()
    res = {"seed": seed, "asked": n, "limit_s": limit_s, "load_s": ctx.load["total_s"], "questions": [], "positions": 0, "mismatches": 0, "head_mismatch": 0, "token_differences": 0}
    vflow = dataclasses.replace(fl, lazy_echo=False)
    for k in order:
        if len(res["questions"]) >= n or time.time() - t0 > limit_s:
            break
        gr, q, tag = its[k]
        if str(tag) not in records:
            continue
        ge = run_question(ctx, ctx.ec.cx, gr, q, tools, vflow, verify=True)
        r = next(ge)[1]
        d = same_tokens(records[str(tag)], r, flags_differ=fl.lazy_echo)
        ok = all(d.values())
        res["questions"].append({"tag": tag, "status": r["status"], "positions": r["verified_positions"], "mismatch": r["verify_mismatch"], "head_mismatch": r["head_mismatch"], "lock": r["lock_error"], "same_tokens": ok, "differ": [k_ for k_, v in d.items() if not v], "end_state": r["end_state_diff"], "seconds": r["seconds"]})
        res["positions"] += r["verified_positions"]
        res["mismatches"] += int(r["verify_mismatch"] is not None)
        res["head_mismatch"] += r["head_mismatch"]
        res["token_differences"] += int(not ok)
        print(f"stock sample {tag}: {r['verified_positions']} positions, mismatch {r['verify_mismatch']}, head {r['head_mismatch']}, same tokens {ok}", flush=True)
        json.dump(res, open(os.path.join(out, "stock_sample.json"), "w"), indent=1, default=str)
        g.torch.mps.empty_cache()
    res["seconds"] = round(time.time() - t0, 1)
    res["passed"] = res["mismatches"] == 0 and res["head_mismatch"] == 0 and res["token_differences"] == 0 and len(res["questions"]) > 0
    json.dump(res, open(os.path.join(out, "stock_sample.json"), "w"), indent=1, default=str)
    return res


def run(its, fl, out, rows=8, stock=2, stock_seed=20261102, stock_limit_s=1200, force=None, deadline_s=None):
    """Run the questions. Returns the summary. out gets all.jsonl (one record per question, whole), meta.json, and stock_sample.json.
    force="fast" or "slow" overrides the proof table; only a proof run should use force="fast", and its records say so."""
    assert 1 <= rows <= MAX_ROWS, f"rows up to {MAX_ROWS}"
    os.makedirs(out, exist_ok=True)
    pr = proof(fl)
    path = force or ("fast" if pr else "slow")
    ran_on = {"fast": "fast: Qwen blocks in batch, chip on the engine" if pr else "fast, UNPROVEN on this firmware and flow: a proof run", "slow": "slow: stock modules one at a time, chip on the engine" + ("" if pr else "; no fast proof for this firmware and flow")}[path]
    t0 = time.time()
    tools = [g.C2.chase_tool("")] if fl.tools == "chase" else g.worked.TOOLS if fl.tools == "writes" else g.HT.tools_for("base")
    ctx = load_blocks() if path == "fast" else load_stock()
    load_s = round(time.time() - t0, 1)
    meta = {"machine": g.machine, "delivery": g.delivery, "firmware": g.elf, "firmware_sha256": g.elf_sha, "ckpt": g.ckpt, "flow": dataclasses.asdict(fl), "flow_key": fl.key(), "path": path, "ran_on": ran_on, "proof": pr, "rows": rows if path == "fast" else 1, "questions": len(its), "load_seconds": load_s, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "shared_gpu": "unknown: ioreg shows other jobs unless stated", "engine": ctx.ec.cx.lib_hash}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1, default=str)
    print(f"{ran_on}; load {load_s}s; {g.machine} {g.elf_sha[:8]} {fl.key()}", flush=True)
    p = os.path.join(out, "all.jsonl")
    records = {}
    if os.path.exists(p):
        for ln in open(p):
            x = json.loads(ln)
            records[str(tuple(x["tag"]))] = x
    its2 = [i for i in its if str(i[2]) not in records]
    f = open(p, "a", encoding="utf-8", buffering=1)
    bad = []

    def done(tag, r):
        r.update(tag=list(tag), graph=tag[0], ran_on=ran_on, flow=fl.key(), firmware_sha256=g.elf_sha)
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        records[str(tag)] = r
        if r["status"] in ("lock", "engine_flag", "verify_mismatch"):
            bad.append((tag, r["status"]))
        print(f"{tag}: {r['status']} calls={r['n_calls']} correct={r['correct']} {r['seconds']}s qwen={r['qwen_tokens']} echo={r['echo_tokens']} chip={r['chip_tokens']} | {(r['final'] or '')[:50]!r}", flush=True)
    deadline = t0 + deadline_s if deadline_s else None
    st = drive_fast(ctx, its2, fl, tools, rows, done, deadline) if path == "fast" else drive_slow(ctx, its2, fl, tools, done, deadline)
    f.close()
    del ctx
    g.torch.mps.empty_cache()
    meta.update(stats=st, bad=bad, tokens=sum(r["qwen_tokens"] + r["echo_tokens"] for r in records.values()))
    meta["stock_sample"] = stock_sample(its, fl, tools, records, stock, stock_seed, stock_limit_s, out)
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1, default=str)
    if bad or (meta["stock_sample"] and not meta["stock_sample"]["passed"]):
        print("STOP: a lock error, an engine flag or the stock sample disagreed; this run's results do not count until explained", flush=True)
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", default="tok", choices=sorted(MACHINES))
    ap.add_argument("--elf", help="a firmware instead of the machine's; no proof until its hash has one")
    ap.add_argument("--ckpt")
    ap.add_argument("--build-blocks", metavar="MACHINE", help="build the block file for a machine's checkpoint, then exit")
    ap.add_argument("--flow", default="print-chain3", choices=sorted(PRESETS))
    ap.add_argument("--speed-flags", action="store_true", help="print only: limit line ends the turn, 320-token cap, echo skipped. Changes what happens after the first line")
    ap.add_argument("--limit-stop", action="store_true")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--lazy-echo", action="store_true")
    ap.add_argument("--readback", type=int, default=0)
    ap.add_argument("--questions", help="a JSON file: [[graph, id], ...], or {'draw': [...]}")
    ap.add_argument("--out")
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--stock", type=int, default=2, help="whole questions in stock lockstep after the run; 0 only for a proof that has its own")
    ap.add_argument("--stock-limit-s", type=float, default=1200)
    ap.add_argument("--deadline-s", type=float)
    ap.add_argument("--force", choices=["fast", "slow"], help="proof runs only")
    a = ap.parse_args()
    setup(a.build_blocks or a.machine, a.elf, a.ckpt)
    if a.build_blocks:
        return build_blocks()
    kw = {}
    if a.speed_flags:
        kw.update(limit_stop=True, cap=320, lazy_echo=True)
    if a.limit_stop:
        kw["limit_stop"] = True
    if a.cap:
        kw["cap"] = a.cap
    if a.lazy_echo:
        kw["lazy_echo"] = True
    if a.readback:
        kw["readback"] = a.readback
    fl = flow(a.flow, **kw)
    q = json.load(open(a.questions))
    pairs = q["draw"] if isinstance(q, dict) else q
    m = run(items([tuple(x) for x in pairs]), fl, a.out, rows=a.rows, stock=a.stock, stock_limit_s=a.stock_limit_s, force=a.force, deadline_s=a.deadline_s)
    print(json.dumps({k: m[k] for k in ("path", "ran_on", "load_seconds", "stats", "tokens", "bad")}, default=str), flush=True)
    sys.exit(3 if m["bad"] or (m["stock_sample"] and not m["stock_sample"]["passed"]) else 0)


if __name__ == "__main__":
    main()
