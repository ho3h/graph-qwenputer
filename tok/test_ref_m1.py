"""T2: rvc/test_m1.py's test through tok/'s firmware on ref.Machine, plus a token check: printed tokens against the real tokenizer on forced_text(line). See REGISTRATION.md.

    python tok/test_ref_m1.py [--workers 4] [--quick] [--parts ...]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as O  # noqa: E402  (first: the circuit, the bridge and boot in this process)
X210 = O.X210
sys.path.insert(0, os.path.join(X210, "fw"))
sys.path.insert(0, os.path.join(X210, "rvc"))
import fwbox as F  # noqa: E402
import test_m1 as M  # noqa: E402
import fragments as FR  # noqa: E402

M.X.MODEL = os.path.expanduser("~/Models/x210/Qwen3.5-4B")
X = M.X
OUT = os.path.join(HERE, "results", "t2")
TOK_LOG = os.path.join(OUT, "tok_by_task.jsonl")
_init = M.init_worker
STAT = {"lines": 0, "equal": 0, "echoed_argument": 0, "trailing_space": 0, "added_token": 0, "other": 0, "toolong": 0, "examples": []}
ADDED = None
HEAD, TAIL = FR.HEAD.encode(), FR.TAIL.encode()


def kind(line):
    if line.startswith(FR.ARG_PREFIX):
        return "echoed_argument"
    if any(a in line for a in ADDED):
        return "added_token"
    if re.search(r"\s\n|\s$", line):
        return "trailing_space"
    return "other"


_box_init, _box_call = X.Box.__init__, X.Box.call


def box_init(self, *a, **k):
    O.set_text(M.T)
    _box_init(self, *a, **k)
    self.head, self.tail = HEAD, TAIL


def box_call(self, ids):
    global ADDED
    r = _box_call(self, ids)
    if ADDED is None:
        ADDED = [x.content for x in self.T.tok.get_added_tokens_decoder().values()]
    got = self.ses.runs[-1]
    line = r.result
    want = self.T.encode(FR.HEAD + line + FR.TAIL)
    STAT["lines"] += 1
    if got == want:
        STAT["equal"] += 1
    else:
        k = kind(line)
        STAT[k] += 1
        if k != "echoed_argument" and len(STAT["examples"]) < 8:
            i = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))
            STAT["examples"].append({"kind": k, "line": line, "at": i, "got": got[max(0, i - 2): i + 3], "want": want[max(0, i - 2): i + 3]})
    return r


X.Box.__init__, X.Box.call = box_init, box_call
_dump = M.Tally.dump


def dump(self):
    d = _dump(self)
    with open(TOK_LOG, "a") as f:
        f.write(json.dumps({"part": self.part, **STAT}, ensure_ascii=False) + "\n")
    for k in STAT:
        STAT[k] = [] if k == "examples" else 0
    return d


M.Tally.dump = dump


def adapter_init():
    F.BUILD = os.path.join(HERE, "build")
    F.set_firmware("tok", os.path.join(HERE, "graphlib.c"), [])
    M.OUT = OUT
    _init()
    O.set_text(M.T)


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(TOK_LOG):
        os.remove(TOK_LOG)
    F.BUILD = os.path.join(HERE, "build")
    os.makedirs(F.BUILD, exist_ok=True)
    F.set_firmware("tok", os.path.join(HERE, "graphlib.c"), [])
    M.OUT = OUT
    M.init_worker = adapter_init
    M.main()


if __name__ == "__main__":
    main()
