"""The merged checkpoint with tok/'s circuit, built by replacing only the chip side of a copy of x210-rvc, a shard at a time.

    python tok/merge_tok.py --out ~/Models/x210/x210-tok

Qwen's layers are copied bit for bit from x210-rvc (vendored merge's widening and mute already in them), so the anti-sink fit isn't repeated and memory stays low; only the
mute columns move if the mu dim moved. Replaced: the chip layers (emit_layers), the embedding (text rows: Qwen's dims unchanged, chip dims rebuilt, every printable-by-id row gets its code), the
final norm's chip dims. Same shard names and index as x210-rvc. Never writes to x210-rvc or the LaCie.
"""
import argparse
import gc
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as O  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from safetensors import safe_open  # noqa: E402
from safetensors.torch import save_file  # noqa: E402

from chipformer.q35.emit import Layout, allocate, check_bf16, emit_layers, embedding_rows  # noqa: E402
from chipformer.q35.ir import Target  # noqa: E402
from chipformer.q35.merge import TAU_GAIN, pick_hidden  # noqa: E402
from chipformer.q35.mute import MUTE  # noqa: E402
from chipformer.q35.tiny import code_gain  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from chipformer.rv.tiny import embedding_matrix  # noqa: E402

core = O.core
sys.path.insert(0, os.path.join(O.X210, "tools"))
import memguard as MG  # noqa: E402


def note(what, t0):
    print(f"{what}: {time.time() - t0:.0f}s, {MG.footprint(os.getpid()) / 2**30:.2f} GiB", flush=True)

SRC = Path(os.path.expanduser("~/Models/x210/x210-rvc"))
BASE = Path(os.path.expanduser("~/Models/x210/Qwen3.5-4B"))
DST_PREFIX = "model."
CODE_GAIN_X = 4.0  # every text row now has a code one bit from others, so a wider margin over Qwen's own logits, as the store's ID_GAIN does for the same reason


def text_rows(c, lay, T, base_emb, v0, code_dims):
    """As vendored merge.text_rows, plus: every row the machine may print by id holds its output code."""
    h = lay.hidden
    d0 = base_emb.shape[1]
    full = torch.zeros(v0, h, dtype=torch.bfloat16)
    full[:, :d0] = base_emb[:v0, :d0]
    special = sorted({T.TCO, T.TCC, *T.printable})
    plain_q = next(q for q in range(T.n) if q not in set(special))
    plain = embedding_rows(c, lay, [BR.text_token(plain_q)], h)[0]
    byte_cols = [[lay.dim(next(iter(c.tb[k][i].terms))) for i in range(8)] for k in range(S.TEXT_ROW)]
    for k in range(S.TEXT_ROW):
        for i in range(8):
            plain[byte_cols[k][i]] = 0.0
    for d in code_dims:           # (the plain row's own code, below)
        plain[d] = 0.0
    full[:, d0:] = plain[d0:].to(torch.bfloat16)
    by = np.zeros((v0, S.TEXT_ROW), dtype=np.uint8)
    for q in range(min(v0, T.n)):
        by[q] = np.frombuffer(T.row_bytes(q), dtype=np.uint8)
    for k in range(S.TEXT_ROW):
        for i in range(8):
            full[:, byte_cols[k][i]] = torch.tensor((by[:, k] >> i) & 1, dtype=torch.bfloat16)
    # the codes: ±CODE_AMP per bit, family id then payload
    q = np.arange(v0)
    ok = np.array([T.id_ok(int(x)) for x in q])
    fam = np.array([core.FAM_ID["T0"] + (int(x) >> 16) if o else 0 for x, o in zip(q, ok)])
    bits = [(fam >> i) & 1 for i in range(core.NFAM)] + [(q >> i) & 1 for i in range(core.NPAY)]
    for d, b in zip(code_dims, bits):
        full[:, d] = torch.tensor(np.where(ok, core.CODE_AMP * (2 * b - 1), 0), dtype=torch.bfloat16)
    rows = embedding_rows(c, lay, [BR.text_token(x) for x in special], h)
    for x, r in zip(special, rows):
        full[x, d0:] = r[d0:].to(torch.bfloat16)
    return full, int(ok.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()
    dst = Path(os.path.expanduser(a.out))
    assert "LaCie" not in str(dst) and dst != SRC
    t0 = time.time()
    meta0 = json.loads((SRC / "chipformer.json").read_text())
    cfg0 = json.loads((SRC / "config.json").read_text())
    base_cfg = json.loads((BASE / "config.json").read_text())["text_config"]
    d0, v0, inter = base_cfg["hidden_size"], base_cfg["vocab_size"], base_cfg["intermediate_size"]
    T = BR.Text(BASE / "tokenizer.json")
    O.set_text(T)
    c = core.build(Target(base_cfg["linear_num_key_heads"], base_cfg["linear_num_value_heads"], inter), T, None)
    keep = set(c.keep)
    alloc = allocate(c, None, keep, inter)
    hidden, m = pick_hidden(d0, 1 + alloc.n_slots)
    lay = Layout(hidden=hidden, off=d0, m=m, slots=alloc.slots)
    n_chip = c.n_layers()
    code_dims = [lay.dim(next(iter(e.terms))) for e in c.code]
    tau_d = lay.dim(next(iter(c.tau.terms)))
    mu_d = lay.dim(next(iter(c.mu.terms)))
    report = {"stats_old": meta0["circuit"], "stats_new": c.stats(), "slots_old": meta0["slots"], "slots_new": alloc.n_slots, "hidden_old": meta0["hidden"], "hidden_new": hidden, "m_old": meta0["ballast_dims"], "m_new": m,
              "chip_layers_old": meta0["chip_layers"], "chip_layers_new": n_chip, "mu_old": meta0["mu_dim"], "mu_new": mu_d, "tau_old": meta0["tau_dim"], "tau_new": tau_d, "code_old": meta0["code_dims"], "code_new": code_dims,
              "nfam": core.NFAM, "npay": core.NPAY}
    print(json.dumps(report), flush=True)
    assert hidden == meta0["hidden"] and n_chip == meta0["chip_layers"] and m == meta0["ballast_dims"], "the shape changed: stop and report"
    if a.plan_only:
        return
    assert not dst.exists() or not any(dst.glob("*.safetensors")), dst
    dst.mkdir(parents=True, exist_ok=True)
    tc = cfg0
    # the embedding first, in its own shard, then freed; the chip side after it. (memguard killed two attempts at 32 GiB holding both at once.)
    idx = json.loads((SRC / "model.safetensors.index.json").read_text())["weight_map"]
    base_idx = json.loads((BASE / "model.safetensors.index.json").read_text())["weight_map"]
    key = "model.language_model.embed_tokens.weight"
    with safe_open(BASE / base_idx[key], "pt") as fh:
        base_emb = fh.get_tensor(key)
    vocab = tc["vocab_size"]
    emb = torch.zeros(vocab, hidden, dtype=torch.bfloat16)
    rows, n_ok = text_rows(c, lay, T, base_emb, v0, code_dims)
    emb[:v0] = rows
    del rows, base_emb
    note("text rows", t0)
    chip = embedding_matrix(c, lay, S.VOCAB)
    emb[v0:v0 + S.VOCAB] = chip[:S.VOCAB].to(torch.bfloat16)
    del chip
    gc.collect()
    note("chip rows", t0)
    for a_ in range(0, v0, 1 << 16):      # the same range check as the vendored merge's, in pieces
        check_bf16("embedding", emb[a_: a_ + (1 << 16), d0:].float())
    note(f"embedding ready, {n_ok} rows printable by id", t0)
    emb_key = DST_PREFIX + "embed_tokens.weight"
    assert sum(1 for v in idx.values() if v == idx[emb_key]) == 1, "the embedding should have its own shard"
    save_file({emb_key: emb}, str(dst / (idx[emb_key] + ".tmp")), metadata={"format": "pt"})
    os.replace(dst / (idx[emb_key] + ".tmp"), dst / idx[emb_key])
    del emb
    gc.collect()
    note("embedding shard written", t0)
    layers = emit_layers(c, lay, tc, 0, DST_PREFIX, alloc, keep)
    note("emitted", t0)
    for k in list(layers):
        layers[k] = layers[k].to(torch.bfloat16)
    gc.collect()
    note(f"{len(layers)} chip tensors in bf16", t0)
    moved = {}
    same_keys = {"shards": 0, "qwen_tensors": 0, "chip_tensors": 0}
    for sh in sorted(set(idx.values())):
        if sh == idx[emb_key]:
            continue
        out = {}
        with safe_open(SRC / sh, "pt") as fh:
            for k in fh.keys():  # noqa: SIM118
                if k in layers:
                    out[k] = layers.pop(k)
                    same_keys["chip_tensors"] += 1
                elif k == DST_PREFIX + "norm.weight":
                    w = fh.get_tensor(k).float()
                    w[d0:] = -1.0
                    for d in code_dims:
                        w[d] = CODE_GAIN_X * code_gain(lay)
                    w[tau_d] = TAU_GAIN
                    check_bf16("final norm", w[d0:])
                    out[k] = w.to(torch.bfloat16)
                else:
                    t = fh.get_tensor(k)
                    assert not k.startswith("model.layers.") or int(k.split(".")[2]) >= n_chip, k
                    if mu_d != meta0["mu_dim"] and t.ndim == 2 and t.shape[1] == hidden and bool((t[:, meta0["mu_dim"]] != 0).any()):
                        t = t.clone()
                        assert not (t[:, mu_d] != 0).any(), k
                        t[:, mu_d] = t[:, meta0["mu_dim"]]
                        t[:, meta0["mu_dim"]] = 0
                        moved[k] = 1
                    out[k] = t
                    same_keys["qwen_tensors"] += 1
        tmp = dst / (sh + ".tmp")
        save_file(out, str(tmp), metadata={"format": "pt"})
        os.replace(tmp, dst / sh)
        same_keys["shards"] += 1
        n_out = len(out)
        del out
        gc.collect()
        note(f"{sh} {n_out} tensors", t0)
    assert not layers, list(layers)[:5]
    for f in ("model.safetensors.index.json", "config.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja", "LICENSE"):
        if (SRC / f).exists():
            shutil.copy(SRC / f, dst / f)
    gen = json.loads((SRC / "generation_config.json").read_text())
    gen.pop("bad_words_ids", None)     # the machine prints <|im_start|>; a plain generate also needs its own stop rule for the machine's <|im_end|>
    (dst / "generation_config.json").write_text(json.dumps(gen, indent=2))
    meta = dict(meta0)
    meta.update(layout="rv1-tok", circuit=c.stats(), slots=alloc.n_slots, code_dims=code_dims, tau_dim=tau_d, mu_dim=mu_d)
    (dst / "chipformer.json").write_text(json.dumps(meta, indent=1))
    report.update(moved_mute_columns=sorted(moved), counts=same_keys, seconds=round(time.time() - t0, 1), printable_by_id=n_ok)
    json.dump(report, open(os.path.join(HERE, "results", "merge_report.json"), "w"), indent=1)
    print(json.dumps({k: report[k] for k in ("counts", "seconds", "printable_by_id")}), flush=True)


if __name__ == "__main__":
    main()
