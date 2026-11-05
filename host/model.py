"""Base Qwen 3.5 4B under stock HF transformers (bf16, MPS): load once, switch attention implementations, forward.

Kept apart from the loop (harness.py) so a long-lived worker can reload the loop without reloading the weights.
"""

import os
import time

import torch

MODEL = ("<drive>/Models/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/"
         "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")


def mem():
    """(allocated, driver) bytes on MPS, or zeros elsewhere."""
    if torch.backends.mps.is_available():
        return torch.mps.current_allocated_memory(), torch.mps.driver_allocated_memory()
    return 0, 0


class Qwen:
    def __init__(self, path=MODEL, device="mps", attn="sdpa"):
        from transformers import AutoModelForImageTextToText, AutoTokenizer

        t0 = time.time()
        self.path, self.dev = path, device
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForImageTextToText.from_pretrained(
            path, dtype=torch.bfloat16, attn_implementation=attn).to(device).eval()
        self.load_seconds = round(time.time() - t0, 1)
        self.nq = len(self.tok)
        ids = self.tok.convert_tokens_to_ids
        self.TCO, self.TCC = ids("<tool_call>"), ids("</tool_call>")
        self.IM_END, self.EOS = ids("<|im_end|>"), ids("<|endoftext|>")
        self.peak_driver = 0
        self.env = {k: os.environ.get(k) for k in ("PYTORCH_MPS_HIGH_WATERMARK_RATIO",
                                                    "PYTORCH_MPS_LOW_WATERMARK_RATIO")}

    @property
    def attn(self):
        return self.model.config.get_text_config()._attn_implementation

    def set_attn(self, impl):
        if impl != self.attn:
            self.model.set_attn_implementation(impl)
        assert self.attn == impl, (self.attn, impl)

    @torch.no_grad()
    def forward(self, ids, cache):
        """Feed `ids` (one chunk) after `cache`; returns (greedy next id, cache)."""
        x = torch.tensor([ids], device=self.dev)
        out = self.model(input_ids=x, past_key_values=cache, use_cache=True, logits_to_keep=1)
        nxt = int(torch.argmax(out.logits[0, -1, : self.nq]))
        self.peak_driver = max(self.peak_driver, mem()[1])
        return nxt, out.past_key_values
