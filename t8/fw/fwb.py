"""The cleaner firmware on the reference machine: t8/fw/overlay first, then rvc/test_m1's machinery pointed at t8/fw/build/clean.elf. Nothing outside t8/ is written."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as OV  # noqa: E402  (first)

O = OV.O
sys.modules.setdefault("overlay", O)
X210 = OV.X210
sys.path.insert(0, os.path.join(X210, "fw"))
sys.path.insert(0, os.path.join(X210, "rvc"))
import fwbox as F  # noqa: E402
import test_m1 as M  # noqa: E402
import fragments as FR  # noqa: E402
import noun as NOUN  # noqa: E402

M.X.MODEL = os.path.expanduser("~/Models/x210/Qwen3.5-4B")
X = M.X
WRITES = os.environ.get("T8_WRITES") == "1"
BUILD = os.path.join(HERE, "build_r6" if os.environ.get("T8_R6") == "1" else "build_r5" if os.environ.get("T8_R5") == "1" else "build_r4" if os.environ.get("T8_R4") == "1" else "build_r3" if os.environ.get("T8_R3") == "1" else "build_r2" if os.environ.get("T8_R2") == "1" else "build_r1" if os.environ.get("T8_R1") == "1" else "build_writes" if WRITES else "build")
SRC = os.path.join(BUILD, "graphlib.c")
HEAD, TAIL = FR.HEAD.encode(), FR.TAIL.encode()
TOK_ELF = os.path.join(HERE, "build", "clean.elf") if WRITES else os.path.join(X210, "tok", "build", "tok.elf")   # what a build is compared with
_box_init, _box_call = X.Box.__init__, X.Box.call
_Graph = M.reflib.Graph
STAT = {"lines": 0, "equal": 0, "echoed": 0, "other": 0, "examples": []}
ADDED = None


def build():
    F.BUILD = BUILD
    return F.set_firmware("writes" if WRITES else "clean", SRC, [])


def noun_mode(on):
    """on: every graph on both sides gets the noun by SPEC 1's rule (domain 'test' and others: null). off: the file as it is, no field."""
    if on:
        class G(_Graph):
            def __init__(self, g):
                super().__init__(NOUN.with_noun(g) if "noun" not in g else g)
        M.reflib.Graph = G


def patch_box(on):
    global ADDED

    def box_init(self, g, *a, **k):
        O.set_text(M.T or a[0])
        _box_init(self, (NOUN.with_noun(g) if on and "noun" not in g else g), *a, **k)
        self.head, self.tail = HEAD, TAIL

    def box_call(self, ids):
        global ADDED
        r = _box_call(self, ids)
        if ADDED is None:
            ADDED = [x.content for x in self.T.tok.get_added_tokens_decoder().values()]
        got, line = self.ses.runs[-1], r.result
        STAT["lines"] += 1
        if got == self.T.encode(FR.HEAD + line + FR.TAIL):
            STAT["equal"] += 1
        elif "\nNONE " in "\n" + line or line.startswith(FR.ARG_PREFIX) or any(a in line for a in ADDED):
            STAT["echoed"] += 1
        elif re.search(r"\s\n|\s$", line):
            STAT["trailing_space"] = STAT.get("trailing_space", 0) + 1     # tok's T1b: a name ending in whitespace before a newline is one token in the real tokenizer
        else:
            STAT["other"] += 1
            if len(STAT["examples"]) < 6:
                STAT["examples"].append(line)
        return r

    X.Box.__init__, X.Box.call = box_init, box_call
    if on:                                                         # transcripts recorded before the cleaner: only reflib decides
        run = M.Tally.run
        M.Tally.run = lambda self, box, G, ids, where, fn=None, record=None: run(self, box, G, ids, where, fn, None)
