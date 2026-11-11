"""Qwen's layers as nonzero blocks, in one file on a fast disk, with no chip-layer weights: what the executor path needs.

    python blocks.py --build DIR      # once, CPU: reads the merged checkpoint (read-only), writes DIR/blocks.bin and DIR/index.json
    ctx = blocks.load(DIR)            # a context batchrun.drive can use; no dense weights, nothing read from the LaCie's weights

Values are the checkpoint's, unchanged. Blocks and the positional head are bit-equal with dense on what S3, S4a and S4 ran.
"""
import argparse, json, os, sys, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import torch
import textlib as TL
from chipformer.q35 import fast as QF
from chipformer.q35.ir import Target
from chipformer.rv import bridge as BR, core
from chipformer.rv.chat import RvChat
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForCausalLM
from transformers.models.qwen3_5 import modeling_qwen3_5 as M
D, X = TL.D, TL.X
NCHIP = 11


def build(out):
    t0 = time.time()
    meta = json.load(open(os.path.join(D.CKPT, "chipformer.json")))
    model = Qwen3_5ForCausalLM.from_pretrained(D.CKPT, dtype=torch.bfloat16)
    os.makedirs(out, exist_ok=True)
    idx = {"tensors": {}, "linear": {}, "shared": {}}
    pos = 0
    f = open(os.path.join(out, "blocks.bin"), "wb")
    def put(name, t):
        nonlocal pos
        b = t.detach().contiguous().numpy() if t.dtype != torch.bfloat16 else t.detach().contiguous().view(torch.uint16).numpy()
        f.write(b.tobytes())
        idx["tensors"][name] = {"dtype": str(t.dtype).split(".")[-1], "shape": list(t.shape), "offset": pos, "bytes": b.nbytes}
        pos += b.nbytes
    lm = model.model
    for i in range(NCHIP, len(lm.layers)):
        layer = lm.layers[i]
        for pname, p in layer.named_parameters():
            mod = layer.get_submodule(pname.rsplit(".", 1)[0]) if "." in pname else layer
            full = f"layers.{i}.{pname}"
            if isinstance(mod, torch.nn.Linear):
                w = p.data
                nz = w != 0
                rr = nz.any(1).nonzero().flatten(); cc = nz.any(0).nonzero().flatten()
                r0, r1, c0, c1 = int(rr[0]), int(rr[-1]) + 1, int(cc[0]), int(cc[-1]) + 1
                put(full, w[r0:r1, c0:c1])
                idx["linear"][full] = {"rows": [r0, r1], "cols": [c0, c1], "shape": list(w.shape)}
            else:
                put(full, p.data)
    put("norm.weight", lm.norm.weight.data)
    tau = meta["tau_dim"]
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    put("head", model.lm_head.weight.data[:nq, :tau + 1])
    put("inv_freq", lm.rotary_emb.inv_freq.data)
    idx["attention_scaling"] = float(lm.rotary_emb.attention_scaling)
    idx["attn"] = model.config._attn_implementation
    idx["nq"] = nq
    idx["seconds"] = round(time.time() - t0, 1)
    idx["bytes"] = pos
    f.close()
    json.dump(idx, open(os.path.join(out, "index.json"), "w"))
    print("built", round(pos / 2**30, 2), "GiB", idx["seconds"], "s", flush=True)


class Emb:
    def __init__(self, w):
        self.weight = w


def load(dr, n_engines=9):
    from cexec import CExec
    from chat import ExecChat
    t = {}
    t0 = time.time()
    idx = json.load(open(os.path.join(dr, "index.json")))
    cfg = AutoConfig.from_pretrained(D.CKPT)
    cfg._attn_implementation = idx["attn"]
    mm = np.memmap(os.path.join(dr, "blocks.bin"), dtype=np.uint8, mode="r")
    def get(name, to="mps"):
        e = idx["tensors"][name]
        a = np.frombuffer(mm, dtype=np.uint16 if e["dtype"] == "bfloat16" else (np.float32 if e["dtype"] == "float32" else np.uint16), count=int(np.prod(e["shape"])), offset=e["offset"])
        tt = torch.from_numpy(a.copy()) if e["bytes"] < 2**20 else torch.from_numpy(np.asarray(a))
        if e["dtype"] == "bfloat16":
            tt = tt.view(torch.bfloat16)
        return tt.reshape(e["shape"]).to(to)
    layers = []
    with torch.device("meta"):
        skeleton = [M.Qwen3_5DecoderLayer(cfg, i) for i in range(NCHIP, cfg.num_hidden_layers)]
    for i, layer in zip(range(NCHIP, cfg.num_hidden_layers), skeleton):
        for pname, p in list(layer.named_parameters()):
            modname, leaf = pname.rsplit(".", 1) if "." in pname else ("", pname)
            mod = layer.get_submodule(modname) if modname else layer
            full = f"layers.{i}.{pname}"
            if isinstance(mod, torch.nn.Linear):
                e = idx["linear"][full]
                parent_name, cname = modname.rsplit(".", 1)
                parent = layer.get_submodule(parent_name)
                fake = types.SimpleNamespace(shape=e["shape"])
                s = QF.SparseLinear.__new__(QF.SparseLinear)
                torch.nn.Module.__init__(s)
                s.out_features, s.in_features = e["shape"]
                s.r0, s.r1 = e["rows"]; s.c0, s.c1 = e["cols"]
                s.dense_above = None; s.dense = None
                s.weight = get(full)
                setattr(parent, cname, s)
            else:
                setattr(mod, leaf, torch.nn.Parameter(get(full), requires_grad=False))
        layer.eval()
        layers.append(layer)
    norm = M.Qwen3_5RMSNorm(cfg.hidden_size, eps=cfg.rms_norm_eps)
    norm.weight = torch.nn.Parameter(get("norm.weight"), requires_grad=False)
    with torch.device("meta"):
        pass
    rot = M.Qwen3_5TextRotaryEmbedding(config=cfg)
    rot.inv_freq = get("inv_freq")
    rot.attention_scaling = idx["attention_scaling"]
    head = get("head")
    torch.mps.synchronize()
    t["weights_to_gpu"] = round(time.time() - t0, 1); t0 = time.time()
    chat = RvChat.__new__(RvChat)
    from pathlib import Path
    chat.path = Path(D.CKPT)
    chat.meta = json.loads((chat.path / "chipformer.json").read_text())
    chat.dev = "mps"
    chat.n_chip, chat.v0 = chat.meta["chip_layers"], chat.meta["chip_token_offset"]
    chat.tok = AutoTokenizer.from_pretrained(chat.path)
    t["tokenizer"] = round(time.time() - t0, 1); t0 = time.time()
    chat.T = BR.Text(chat.path / "tokenizer.json")
    t["bridge_text"] = round(time.time() - t0, 1); t0 = time.time()
    chat.store_cfg = None
    chat.c = core.build(Target(cfg.linear_num_key_heads, cfg.linear_num_value_heads, cfg.intermediate_size), chat.T, None)
    t["core_build"] = round(time.time() - t0, 1); t0 = time.time()
    chat.code_dims = torch.tensor(chat.meta["code_dims"], device="mps")
    chat.id_dims = None
    chat.store_snap = None
    chat.eos = {248046, 248044}
    chat.fast = chat.executor = chat.verify = False
    chat.model = types.SimpleNamespace(config=cfg)
    lm_layers = [None] * NCHIP + layers
    chat.lm = types.SimpleNamespace(layers=lm_layers, norm=norm, rotary_emb=rot, embed_tokens=Emb(head))
    ec = ExecChat.__new__(ExecChat)
    ec.chat = chat
    ec.cx = CExec(chat.c, chat.T)
    ec.d0 = chat.meta["chip_dims_offset"]
    cols = chat.meta["code_dims"] + [chat.meta["tau_dim"], chat.meta["mu_dim"]]
    ec.keep_cols_np = np.array(cols)
    ec.keep_cols = torch.tensor(cols, device="mps")
    ec.hidden = chat.meta["hidden"]
    ec.n_code = len(chat.meta["code_dims"])
    ec.dev = "mps"
    ec.rows = {}
    ctx = types.SimpleNamespace(ec=ec, nq=idx["nq"], layers=layers, head=head, tau=chat.meta["tau_dim"], load_phases=t)
    return ctx


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build")
    a = ap.parse_args()
    build(a.build)
