"""The IR against the merged weights, on CPU, with no model object (REGISTRATION.md, "Whole-table check", part B). tablecheck.py compares tables with the IR; this compares the IR with the checkpoint, so the two together reach from the tables to the weights.

    python weightcheck.py --out results/weightcheck.json

Tensors are read one at a time with safetensors. What should be there is rebuilt from the IR nodes by this file's own code, as exact rationals, and compared: FFN units as an order-free multiset, heads by position, fixed tensors by value.

Independence. It does not import emit_layers or row. It shares emit.allocate, since the slot map is not saved in the checkpoint; check_slots tests that map's lifetimes separately and chipformer.json's code, tau and mu dims pin part of it. It repeats emit's rules for handing a slot over and clearing at the exit, because they are the rules the check is about.
Embedding rows: chip dims only, against c.feature_value, which is what the engine's token features are. Qwen's own first 2,560 dims are not IR and are not read here (check_trace.py compares a digest of them on stream tokens). Qwen's layers and their muting are not read either.
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from safetensors import safe_open  # noqa: E402

from chipformer.dsl.graph import ONE  # noqa: E402
from chipformer.q35.emit import allocate  # noqa: E402
from chipformer.q35.ir import FFN, HD, Head, K  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

LOG2_BALLAST = 40       # q35.emit.Layout's default, which rv.merge leaves
B = Fraction(2) ** LOG2_BALLAST
BALLAST = -1            # key of the summed ballast columns
torch.set_num_threads(2)
MATRICES = ("mlp.gate_proj.weight", "mlp.up_proj.weight", "mlp.down_proj.weight", "linear_attn.in_proj_qkv.weight", "linear_attn.conv1d.weight", "linear_attn.in_proj_z.weight", "linear_attn.in_proj_a.weight",
            "linear_attn.in_proj_b.weight", "linear_attn.out_proj.weight")
FIXED = {"linear_attn.dt_bias": -110.0, "linear_attn.A_log": 0.0, "linear_attn.norm.weight": 1.0, "input_layernorm.weight": 0.0, "post_attention_layernorm.weight": 0.0}


class Ck:
    def __init__(self, path):
        self.path = path
        self.idx = json.load(open(os.path.join(path, "model.safetensors.index.json")))["weight_map"]
        self.files = {}

    def handle(self, name):
        f = self.idx[name]
        if f not in self.files:
            self.files[f] = safe_open(os.path.join(self.path, f), framework="pt")
        return self.files[f]

    def tensor(self, name):
        return self.handle(name).get_tensor(name)


def sparse(t):
    """(index arrays, values as float32, negative zeros). bf16 -> fp32 is exact."""
    assert t.dtype == torch.bfloat16, t.dtype
    bits = t.view(torch.uint16).numpy()
    nz = np.nonzero((bits & 0x7FFF) != 0)
    return nz, t[tuple(torch.from_numpy(i) for i in nz)].float().numpy(), int((bits == 0x8000).sum()), t.shape


class Expect:
    def __init__(self, L, alloc, meta, cfg):
        self.c = L.c
        self.alloc = alloc
        self.off, self.m, self.h = meta["chip_dims_offset"], meta["ballast_dims"], meta["hidden"]
        self.nk, self.nv, self.inter = cfg["linear_num_key_heads"], cfg["linear_num_value_heads"], cfg["intermediate_size"]
        self.r = self.nv // self.nk
        mean = Fraction(self.m) * B * B / self.h
        k = 0
        while mean > 1:
            mean /= 4
            k += 1
        assert mean == 1, "m * B^2 / hidden is not a power of 4"
        self.cscale = Fraction(1, 2**k)             # c: the normed value of a residual value 1
        self.keep = set(L.c.keep)

    def col(self, d):
        return self.off + self.m + 1 + self.alloc.slots[d]

    def form(self, terms, scale=Fraction(1)):
        """{residual column or BALLAST: weight}: a projection row reads x * c, and the ballast dims together read B * c."""
        out = {}
        for d, cf in terms.items():
            v = scale * Fraction(float(cf))
            if d == ONE:
                out[BALLAST] = out.get(BALLAST, Fraction(0)) + v / (B * self.cscale)
            else:
                k = self.col(d)
                out[k] = out.get(k, Fraction(0)) + v / self.cscale
        return {k: v for k, v in out.items() if v}

    def actual_form(self, items):
        out = {}
        for col, v in items:
            k = BALLAST if self.off <= col < self.off + self.m else col
            out[k] = out.get(k, Fraction(0)) + Fraction(float(v))
        return {k: v for k, v in out.items() if v}

    def units(self, L_):
        """The multiset of (gate form, up form, down entries) sublayer 2L + 2 should hold."""
        g = self.c
        lv = 2 * L_ + 2
        one = {ONE: 1}
        out = Counter()

        def add(coef, a, b, d):
            out[(fk(self.form(b, Fraction(K))), fk(self.form(a, Fraction(1, K))), ((self.col(d), Fraction(float(coef))),))] += 1

        for n in g.nodes:
            if not (isinstance(n, FFN) and n.level == lv):
                continue
            for coef, a, b in n.terms:
                add(coef, a.terms, b.terms, n.out)
            if n.out in self.alloc.subtract:         # hand the slot over: take the old value out
                add(-1, {self.alloc.subtract[n.out]: 1}, one, n.out)
        for o in self.alloc.clears.get(lv, []):
            add(-1, {o: 1}, one, o)
        exit_level = max(n.level for n in g.nodes if n.name.startswith("exit."))
        if lv == exit_level:
            for o in self.alloc.final:
                if o not in self.keep:
                    add(-1, {o: 1}, one, o)
            for i in range(self.m):                  # each ballast dim loses B
                gate = fk({BALLAST: Fraction(K) / (B * self.cscale)})
                up = fk({BALLAST: Fraction(1, K) / self.cscale})
                out[(gate, up, ((self.off + i, Fraction(-1)),))] += 1
        return out

    def heads(self, L_):
        """Expected rows of each head tensor, by position."""
        g = self.c
        qkv, conv, z, a, b, o = {}, {}, {}, {}, {}, {}
        hs = [n for n in g.nodes if isinstance(n, Head) and n.level == 2 * L_ + 1]

        def chan(base, chans):
            for i, ch in chans.items():
                f = self.form(ch.expr.terms)
                if f:
                    qkv[base + i] = f
                for lag, w in enumerate(ch.taps):
                    if w:
                        conv[(base + i, 3 - lag)] = Fraction(float(w))

        for j, n in enumerate(hs):
            chan(j * HD, n.q)
            chan(self.nk * HD + j * HD, n.k)
            vhs = n.vheads()
            assert len(vhs) <= self.r
            for x, vd in enumerate(vhs):
                vh = j * self.r + x
                chan(2 * self.nk * HD + vh * HD, vd.v)
                if vd.beta is None:
                    bt = {ONE: Fraction(128)}
                else:
                    bt = {d: Fraction(256) * Fraction(float(cf)) for d, cf in vd.beta.terms.items()}
                    bt[ONE] = bt.get(ONE, Fraction(0)) - 128
                f = self.form(bt)
                if f:
                    b[vh] = f
                f = self.form(vd.a.terms)
                if f:
                    a[vh] = f
                for col, e in vd.z.items():
                    f = self.form(e.terms)
                    if f:
                        z[vh * HD + col] = f
                for col, d, w in vd.out:
                    k = (self.col(d), vh * HD + col)
                    o[k] = o.get(k, Fraction(0)) + Fraction(float(w))
        return {"qkv": qkv, "conv": conv, "z": z, "a": a, "b": b, "o": {k: v for k, v in o.items() if v}}


def fk(f):
    return tuple(sorted(f.items()))


def rows_of(sp):
    nz, vals = sp[0], sp[1]
    out = {}
    for r, c_, v in zip(nz[0].tolist(), nz[1].tolist(), vals.tolist()):
        out.setdefault(r, []).append((c_, v))
    return out


def compare_layer(E, L_, sp, fixed):
    """sp: name -> sparse(tensor). Returns problems [(tensor, message)]."""
    P = []
    gate, up, down = rows_of(sp["mlp.gate_proj.weight"]), rows_of(sp["mlp.up_proj.weight"]), rows_of(sp["mlp.down_proj.weight"])
    down_by_unit = {}
    for row, items in down.items():
        for u, v in items:
            down_by_unit.setdefault(u, []).append((row, Fraction(float(v))))
    got = Counter()
    for u in set(gate) | set(up) | set(down_by_unit):
        got[(fk(E.actual_form(gate.get(u, []))), fk(E.actual_form(up.get(u, []))), tuple(sorted(down_by_unit.get(u, []))))] += 1
    want = E.units(L_)
    if got != want:
        miss, more = want - got, got - want
        P.append(("mlp", f"layer {L_}: {sum(miss.values())} units expected and absent, {sum(more.values())} present and not expected; first absent {str(list(miss)[:1])[:220]}; first extra {str(list(more)[:1])[:220]}"))
    H = E.heads(L_)

    def by_row(name, key):
        g_ = {r: E.actual_form(i) for r, i in rows_of(sp[name]).items()}
        g_ = {r: f for r, f in g_.items() if f}
        if g_ != H[key]:
            bad = [r for r in set(g_) | set(H[key]) if g_.get(r) != H[key].get(r)]
            P.append((name, f"layer {L_}: {len(bad)} rows differ, first {sorted(bad)[:4]}"))

    by_row("linear_attn.in_proj_qkv.weight", "qkv")
    by_row("linear_attn.in_proj_z.weight", "z")
    by_row("linear_attn.in_proj_a.weight", "a")
    by_row("linear_attn.in_proj_b.weight", "b")
    nz, vals = sp["linear_attn.conv1d.weight"][:2]
    g_ = {(int(r), int(k)): Fraction(float(v)) for r, ch, k, v in zip(nz[0], nz[1], nz[2], vals)}
    if g_ != H["conv"] or (len(nz[1]) and int(nz[1].max()) != 0):
        bad = [r for r in set(g_) | set(H["conv"]) if g_.get(r) != H["conv"].get(r)]
        P.append(("conv1d", f"layer {L_}: {len(bad)} taps differ, first {sorted(bad)[:4]}"))
    nz, vals = sp["linear_attn.out_proj.weight"][:2]
    g_ = {(int(r), int(c_)): Fraction(float(v)) for r, c_, v in zip(nz[0], nz[1], vals)}
    if g_ != H["o"]:
        bad = [r for r in set(g_) | set(H["o"]) if g_.get(r) != H["o"].get(r)]
        P.append(("out_proj", f"layer {L_}: {len(bad)} entries differ, first {sorted(bad)[:4]}"))
    for name, v in FIXED.items():
        arr = fixed[name]
        if not (arr == v).all():
            P.append((name, f"layer {L_}: {int((arr != v).sum())} entries are not {v}"))
    return P


def check_slots(c, alloc):
    """Lifetimes of the shared map, by this file's own reading of the nodes: a slot's next owner starts only after the old value's last use, and a unit takes the old value out."""
    n_d = len(c.dims)
    first, last = {}, {d: -1 for d in range(1, n_d)}
    for d in c.token_fns:
        first[d] = 0

    def read(e, lv):
        for d in e.terms:
            if d != ONE:
                last[d] = max(last[d], lv)

    for n in c.nodes:
        lv = n.level
        if isinstance(n, FFN):
            first[n.out] = min(first.get(n.out, lv), lv)
            last[n.out] = max(last[n.out], lv)
            for _, a, b in n.terms:
                read(a, lv), read(b, lv)
        else:
            for ch in list(n.q.values()) + list(n.k.values()):
                read(ch.expr, lv)
            for vd in n.vheads():
                for ch in vd.v.values():
                    read(ch.expr, lv)
                read(vd.a, lv)
                for e in vd.z.values():
                    read(e, lv)
                if vd.beta is not None:
                    read(vd.beta, lv)
                for _, d, _ in vd.out:
                    first[d] = min(first.get(d, lv), lv)
                    last[d] = max(last[d], lv)
    is_ffn = {n.out for n in c.nodes if isinstance(n, FFN)}
    cleared = {o: lv for lv, os_ in alloc.clears.items() for o in os_}
    owners = {}
    for d, s in alloc.slots.items():
        owners.setdefault(s, []).append(d)
    bad = []
    handovers = 0
    for s, ds in owners.items():
        ds = sorted(ds, key=lambda d: first[d])
        for o, d in zip(ds, ds[1:]):
            handovers += 1
            if o in c.keep:
                bad.append(("keep dim handed over", o, d))
            if d in is_ffn and alloc.subtract.get(d) == o:
                if last[o] > first[d]:
                    bad.append(("subtract too early", o, d, last[o], first[d]))
            elif cleared.get(o) == first[d] - 1:
                if last[o] > first[d] - 1:
                    bad.append(("clear too early", o, d, last[o], first[d]))
            else:
                bad.append(("no unit takes the old value out", o, d))
    return {"dims": len(alloc.slots), "slots": alloc.n_slots, "handovers": handovers, "bad": len(bad), "first": bad[:6]}


def feature_block(c, feats, toks):
    """[len(toks), len(feats)] by direct calls, one per token and feature."""
    return np.array([[float(c.feature_value(d, t)) for d in feats] for t in toks], np.float32)


def compare_embedding(E, c, sl, n_vocab, v0, chunk, control=None):
    """Every row's chip dims against the token features. control: a function changing a block of the real data."""
    feats = sorted(c.token_fns)
    cols = np.array([E.col(d) - E.off for d in feats])
    res = {"rows": 0, "rows_differing": 0, "by_class": {}, "first": []}
    width = E.h - E.off
    t0 = time.time()
    for a in range(0, n_vocab, chunk):
        b = min(n_vocab, a + chunk)
        got = sl[a:b, E.off:].float().numpy()
        if control:
            control(a, b, got)
        ids = list(range(a, b))
        want = np.zeros((b - a, width), np.float32)
        real = [i for i in ids if i < v0 + S.VOCAB]
        toks = [BR.text_token(i) if i < v0 else i - v0 for i in real]
        if real:
            want[: len(real), : E.m] = float(B)
            want[np.arange(len(real))[:, None], cols[None, :]] = feature_block(c, feats, toks)
        ne = want != got
        rows = np.nonzero(ne.any(1))[0]
        res["rows"] += b - a
        res["rows_differing"] += len(rows)
        for r in rows.tolist():
            i = a + r
            cl = "text" if i < v0 else "chip" if i < v0 + S.VOCAB else "padding"
            res["by_class"][cl] = res["by_class"].get(cl, 0) + 1
            if len(res["first"]) < 12:
                dd = np.nonzero(ne[r])[0][:6]
                res["first"].append({"row": i, "class": cl, "dims": [{"dim": int(x + E.off), "ckpt": float(got[r, x]), "features": float(want[r, x])} for x in dd]})
        if a // chunk % 8 == 0 and not control:
            print(f"embedding {b} of {n_vocab}, {res['rows_differing']} rows differ, {time.time() - t0:.0f}s", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261102)
    ap.add_argument("--controls", type=int, default=60)
    ap.add_argument("--chunk", type=int, default=16384)
    ap.add_argument("--skip-embedding", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    L = C.Lite(tokenizer=False)
    c = L.c
    meta = json.load(open(C.META))
    cfg = json.load(open(os.path.join(C.CKPT, "config.json")))
    alloc = allocate(c, None, set(c.keep), cfg["intermediate_size"])
    E = Expect(L, alloc, meta, cfg)
    ck = Ck(C.CKPT)
    code = [next(iter(e.terms)) for e in c.code]
    res = {"ckpt": C.CKPT, "chipformer_circuit": meta["circuit"], "ir_stats": c.stats(), "same_stats": meta["circuit"] == c.stats(), "slots_meta": meta["slots"], "slots_alloc": alloc.n_slots,
           "code_dims_equal": meta["code_dims"] == [E.col(d) for d in code], "tau_mu_equal": (meta["tau_dim"], meta["mu_dim"]) == (E.col(next(iter(c.tau.terms))), E.col(next(iter(c.mu.terms)))),
           "printable_equal": meta["printable"] == list(L.T.printable), "scale_log2": -int(np.log2(float(E.cscale))), "slots": check_slots(c, alloc), "layers": [], "problems": []}
    print({k: res[k] for k in ("same_stats", "slots_meta", "slots_alloc", "code_dims_equal", "tau_mu_equal", "printable_equal", "scale_log2", "slots")}, flush=True)
    store = {}
    fixed_all = {}
    for L_ in range(meta["chip_layers"]):
        t1 = time.time()
        p = f"model.layers.{L_}."
        sp, fx = {}, {}
        negz = 0
        for name in MATRICES:
            s = sparse(ck.tensor(p + name))
            sp[name] = s
            negz += s[2]
        for name in FIXED:
            fx[name] = ck.tensor(p + name).float().numpy()
        probs = compare_layer(E, L_, sp, fx)
        store[L_], fixed_all[L_] = sp, fx
        row = {"layer": L_, "nonzeros": {n: int(len(sp[n][1])) for n in MATRICES}, "negative_zeros": negz, "problems": len(probs), "seconds": round(time.time() - t1, 1)}
        res["layers"].append(row)
        res["problems"] += [list(x) for x in probs]
        print(row, flush=True)
        for x in probs[:4]:
            print(" ", x, flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
    res["nonzeros_compared"] = sum(sum(r["nonzeros"].values()) for r in res["layers"])
    res["units_expected"] = sum(sum(E.units(l).values()) for l in range(meta["chip_layers"]))

    # the final norm: chip dims are -1 except the code dims (one common gain) and tau
    norm = ck.tensor("model.norm.weight").float().numpy()[E.off:]
    tau = E.col(next(iter(c.tau.terms))) - E.off
    cd = [E.col(d) - E.off for d in code]
    others = np.ones(len(norm), bool)
    others[cd + [tau]] = False
    res["final_norm"] = {"others_all_minus_1": bool((norm[others] == -1).all()), "tau_gain_log2": float(np.log2(norm[tau])), "code_gains": sorted({float(x) for x in norm[cd]})}
    print(res["final_norm"], flush=True)

    n_vocab = cfg["vocab_size"]
    h = ck.handle("model.embed_tokens.weight")
    sl = h.get_slice("model.embed_tokens.weight")
    v0 = meta["chip_token_offset"]
    if not a.skip_embedding:
        res["embedding"] = compare_embedding(E, c, sl, n_vocab, v0, a.chunk)
        res["embedding"]["seconds"] = round(time.time() - t0)
        print({k: v for k, v in res["embedding"].items() if k != "first"}, json.dumps(res["embedding"]["first"][:6])[:900], flush=True)
        json.dump(res, open(a.out, "w"), indent=1)

    # the test of the check: single-weight changes, half on nonzeros, half on zeros; the last ten on embedding rows
    rng = random.Random(a.seed)
    controls = []
    n_layers_c = a.controls - 10
    for k in range(n_layers_c):
        L_ = rng.randrange(meta["chip_layers"])
        name = rng.choice(MATRICES)
        nz, vals, ng, shape = store[L_][name]
        on_nonzero = k % 2 == 0 and len(vals) > 0
        if on_nonzero:
            i = rng.randrange(len(vals))
            old = float(vals[i])
            how = rng.choice(("double", "negate", "plus_bit"))
            new = {"double": old * 2, "negate": -old, "plus_bit": old * (1 + 1 / 128)}[how]
            v2 = vals.copy()
            v2[i] = new
            nz2 = nz
            where = [int(x[i]) for x in nz]
        else:
            existing = set(zip(*[x.tolist() for x in nz]))
            while True:
                where = [rng.randrange(s) for s in shape]
                if tuple(where) not in existing:
                    break
            old, new, how = 0.0, rng.choice((1.0, -1.0, 128.0, 2.0**-8)), "from_zero"
            nz2 = tuple(np.append(x, w) for x, w in zip(nz, where))
            v2 = np.append(vals, new)
        sp2 = dict(store[L_])
        sp2[name] = (nz2, v2, ng, shape)
        probs = compare_layer(E, L_, sp2, fixed_all[L_])
        controls.append({"tensor": f"layer {L_} {name}", "where": where, "old": old, "new": new, "how": how, "caught": bool(probs), "first": probs[0][1][:160] if probs else None})
        print(json.dumps(controls[-1])[:240], flush=True)
    if not a.skip_embedding:
        for k in range(10):
            row = rng.randrange(v0 + S.VOCAB)
            dim = rng.randrange(E.h - E.off)
            on_nonzero = k % 2 == 0
            ok, changed, differed = _control_embedding(E, c, sl, row, dim, v0, on_nonzero)
            controls.append({"tensor": "embedding", "where": [row, changed + E.off], "how": "nonzero changed" if on_nonzero else "zero made nonzero", "caught": ok, "row_already_differed": differed, "first": None})
            print(json.dumps(controls[-1]), flush=True)
    res["controls"] = {"tried": len(controls), "caught": sum(x["caught"] for x in controls), "missed": [x for x in controls if not x["caught"]], "all": controls}
    res["seconds"] = round(time.time() - t0)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("nonzeros_compared", "units_expected", "seconds")}), "problems", len(res["problems"]), "controls", res["controls"]["caught"], "of", res["controls"]["tried"], flush=True)
    sys.exit(0 if not res["problems"] and res["slots"]["bad"] == 0 and not res.get("embedding", {}).get("rows_differing") else 3)


def _control_embedding(E, c, sl, row, dim, v0, on_nonzero):
    """One value changed in one row. Compared with the row's features by the same arithmetic as compare_embedding. Returns (caught, dim changed, whether the row differed before the change)."""
    got = sl[row:row + 1, E.off:].float().numpy()[0]
    feats = sorted(c.token_fns)
    cols = np.array([E.col(d) - E.off for d in feats])
    t = BR.text_token(row) if row < v0 else row - v0
    want = np.zeros(E.h - E.off, np.float32)
    want[: E.m] = float(B)
    want[cols] = feature_block(c, feats, [t])[0]
    differed = bool((want != got).any())
    pool = np.nonzero(got != 0)[0] if on_nonzero else np.nonzero(got == 0)[0]
    d = int(pool[dim % len(pool)])
    got[d] = got[d] * 2 if got[d] else 1.0
    return bool((want != got).any()), d, differed


main()
