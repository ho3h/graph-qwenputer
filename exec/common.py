"""Shared set-up for exec/: the circuit, the tokenizer view RvChat exposes, and teacher-forced dev streams. No weights loaded.

Run from the vendored folder (or with PYTHONPATH set) so `chipformer` resolves to the vendored copy.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
RVC = os.path.join(X210, "rvc")
sys.path.insert(0, RVC)
import box as X  # noqa: E402

from chipformer.q35.ir import Target  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

CKPT = "<drive>/Models/x210-rvc"
META = os.path.join(CKPT, "chipformer.json")


class Lite:
    """What decode.py's stream helpers need from RvChat, without the model: T, tok, c, v0, prompt_ids."""

    def __init__(self, ckpt=CKPT, tokenizer=True):
        cfg = json.load(open(os.path.join(ckpt, "config.json")))
        self.meta = json.load(open(os.path.join(ckpt, "chipformer.json")))
        self.T = BR.Text(os.path.join(ckpt, "tokenizer.json"))
        self.c = core.build(Target(cfg["linear_num_key_heads"], cfg["linear_num_value_heads"], cfg["intermediate_size"]), self.T)
        self.v0, self.n_chip = self.meta["chip_token_offset"], self.meta["chip_layers"]
        self.tok = None
        if tokenizer:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(ckpt)

    def prompt_ids(self, messages, tools=()):
        out = self.tok.apply_chat_template(messages, tools=list(tools) or None, add_generation_prompt=True,
                                           enable_thinking=False, tokenize=True)
        if not isinstance(out, list):
            out = out["input_ids"]
        return [int(x) for x in out]


def to_model(v0, t):
    return v0 + t if t < S.VOCAB else t - S.TEXT_TOKEN


def to_stream(v0, mid):
    return mid - v0 if mid >= v0 else BR.text_token(mid)


# Which firmware the streams boot: rvc's build by default, or an already built ELF named by CHIP_FIRMWARE (never rebuilt here, and fw/ is only read).
FIRMWARE = os.environ.get("CHIP_FIRMWARE")
if FIRMWARE:
    assert os.path.exists(FIRMWARE), FIRMWARE
    X.ELF = FIRMWARE
    X.build_elf = lambda: FIRMWARE
