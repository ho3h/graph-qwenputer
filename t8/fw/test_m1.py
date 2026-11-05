#!/usr/bin/env python3
"""M1: rvc/test_m1.py's whole test through the cleaner firmware against lib/reflib.py. --noun on: every graph carries the noun by SPEC 1's rule. off: no field, so exact matching only, as today.
    python t8/fw/test_m1.py --noun on|off [--workers 4]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwb as W  # noqa: E402

M, F = W.M, W.F
ON = os.environ.get("T8_NOUN") == "on"
OUT = os.path.join(HERE, "results", *(["r1"] if os.environ.get("T8_R1") == "1" else []), ("m1_writes_" if W.WRITES else "m1_noun_") + ("on" if ON else "off"))
TOKLOG = os.path.join(OUT, "tok_by_task.jsonl")
_init, _dump = M.init_worker, M.Tally.dump


def dump(self):
    d = _dump(self)
    with open(TOKLOG, "a") as f:
        f.write(json.dumps({"part": self.part, **W.STAT}, ensure_ascii=False) + "\n")
    for k in W.STAT:
        W.STAT[k] = [] if k == "examples" else 0
    return d


M.Tally.dump = dump


def init():
    W.build()
    M.OUT = OUT
    _init()
    W.O.set_text(M.T)
    W.noun_mode(ON)
    W.patch_box(ON)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(TOKLOG):
        os.remove(TOKLOG)
    W.build()
    M.OUT = OUT
    M.init_worker = init
    M.main()
