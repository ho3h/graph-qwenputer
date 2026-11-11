"""X2.10 graph coprocessor, reference level (COPROCESSOR.md v0 on Python state).

``CopMachine`` wraps the vendored traced machine (``chipformer.rv.ref.Machine``, unedited): every word whose
opcode is custom-2 (0x5B) is executed here, everything else by the vendored ``record``. Each graph op is one record:
an op token ``GOP(op)``, then rd's value record (``NT`` when rd = x0), the same shape as the core's other
rd-writing instructions.

Instruction word: R-type, opcode 0x5B; (f7, f3) selects the op (``OPS``). Operands as COPROCESSOR.md, with the
v0 ambiguities resolved as recorded in DEVLOG.md:
  - GADD's "dir-flags" (rs1 bits 18..31) are reserved and must be 0.
  - EXPAND's 6-bit rel field selects an index slot (0..3). Boot declares each slot as a set of relations; a row
    (node, slot, dir) counts the live edges to each neighbour in the slot's relations (a multiset row, as the
    DeltaNet head holds it). EXPAND answers DEGREE when a read's sum at any node exceeds DEGREE_MAX.
  - SOP sub-ops 0..8: clear, add, has, or, and, diff, empty, first, count.
Out-of-envelope operands (a handle >= N, a set op beyond SET_N, an unknown op) raise ``CopError``: they are
program bugs, never silent.

Token family ``GOP`` (16 ids) is allocated after the vendored vocabulary (spec.VOCAB), the way spec.py appends the
store families after the controls: ids VOCAB .. VOCAB + 15.
"""

from dataclasses import dataclass, field

from chipformer.rv import ref, spec as S

M32 = 0xFFFFFFFF
END, FULL, DEGREE = M32, (-2) & M32, (-3) & M32

# envelopes (COPROCESSOR.md state table)
N_MAX, LABEL_MAX, E_ROWS, R_MAX = 4096, 64, 16384, 64
SET_N, N_SETS, N_SLOTS = 1024, 4, 4
DEGREE_MAX = 256  # bf16 represents every integer up to 2^8 exactly; A3 pins the bound the head actually holds

OPS = {  # name: (f7, f3)
    "GADD": (0, 0), "GDEL": (0, 1), "GFIRST": (0, 2), "GNEXT": (0, 3),
    "GEDGE": (0, 4), "GNODE": (0, 5), "GSETN": (0, 6), "GLBYTE": (0, 7),
    "GLFIRST": (1, 0), "GLNEXT": (1, 1), "SOP": (1, 2), "EXPAND": (1, 3),
}
OP_ID = {n: i for i, n in enumerate(OPS)}
BY_SEL = {v: n for n, v in OPS.items()}
SOP_NAMES = ["clear", "add", "has", "or", "and", "diff", "empty", "first", "count"]

GOP_BASE, GOP_SIZE = S.VOCAB, 16
VOCAB = GOP_BASE + GOP_SIZE


def gop_tok(op: str) -> int:
    return GOP_BASE + OP_ID[op]


def is_gop(t: int) -> bool:
    return GOP_BASE <= t < GOP_BASE + GOP_SIZE


class CopError(Exception):
    pass


@dataclass
class Cop:
    """The coprocessor's state: node table, label bytes and directory, edge rows, list heads, sets, index rows."""

    n: int = 0
    alive: list = field(default_factory=list)
    prop: list = field(default_factory=list)
    scratch: list = field(default_factory=list)
    label: list = field(default_factory=list)  # bytes per node
    bucket: dict = field(default_factory=dict)  # 12-bit hash -> [nodes], chain order = insertion order
    bnext: dict = field(default_factory=dict)  # node -> next node in its bucket
    rows: list = field(default_factory=list)  # [from, rel, to, w, alive] per row
    free: list = field(default_factory=list)  # free rows (LIFO)
    lists: dict = field(default_factory=dict)  # (node, rel, dir) -> [rows] in insertion order
    sets: list = field(default_factory=lambda: [set() for _ in range(N_SETS)])
    slots: list = field(default_factory=lambda: [None] * N_SLOTS)  # frozenset of relations, or None
    nbr: dict = field(default_factory=dict)  # (node, slot, dir) -> {neighbour: count}

    # --- boot-side setup (not instructions) ---
    def add_node(self, lab: bytes, prop: int = 0) -> int:
        if self.n >= N_MAX:
            raise CopError("FULL: node table")
        if len(lab) > LABEL_MAX:
            raise CopError(f"label of {len(lab)} bytes > {LABEL_MAX}")
        h = self.n
        self.n += 1
        self.alive.append(1)
        self.prop.append(prop & 0xFFFF)
        self.scratch.append(0)
        self.label.append(bytes(lab))
        return h

    def link_label(self, h: int, hsh: int) -> None:
        chain = self.bucket.setdefault(hsh & 0xFFF, [])
        if chain:
            self.bnext[chain[-1]] = h
        chain.append(h)
        self.bnext[h] = None

    def declare_slot(self, k: int, rels) -> None:
        if self.n > SET_N:
            raise CopError(f"EXPAND envelope: N = {self.n} > {SET_N}")
        assert self.slots[k] is None and not self.rows, "declare slots before any edge"
        self.slots[k] = frozenset(rels)

    # --- helpers ---
    def _node(self, h: int) -> int:
        if not 0 <= h < self.n:
            raise CopError(f"handle {h} outside N = {self.n}")
        return h

    def _row(self, e: int) -> list:
        if not 0 <= e < len(self.rows) or not self.rows[e][4]:
            raise CopError(f"edge row {e} not live")
        return self.rows[e]

    def _set(self, s: int) -> set:
        if self.n > SET_N:
            raise CopError(f"set op outside the set envelope (N = {self.n} > {SET_N})")
        return self.sets[s]

    def _index(self, a: int, r: int, b: int, delta: int) -> None:
        for k, rels in enumerate(self.slots):
            if rels is not None and r in rels:
                for x, y, d in ((a, b, 0), (b, a, 1)):
                    row = self.nbr.setdefault((x, k, d), {})
                    row[y] = row.get(y, 0) + delta
                    if not row[y]:
                        del row[y]

    # --- the ops (values are unsigned 32-bit) ---
    def gadd(self, a: int, r: int, b: int, w: int) -> int:
        self._node(a), self._node(b)
        if not 0 <= r < R_MAX:
            raise CopError(f"relation {r}")
        if self.free:
            e = self.free.pop()
            self.rows[e] = [a, r, b, w, 1]
        elif len(self.rows) < E_ROWS:
            e = len(self.rows)
            self.rows.append([a, r, b, w, 1])
        else:
            return FULL
        self.lists.setdefault((a, r, 0), []).append(e)
        self.lists.setdefault((b, r, 1), []).append(e)
        self._index(a, r, b, +1)
        return e

    def gdel(self, e: int) -> int:
        a, r, b, _, _ = self._row(e)
        self.lists[(a, r, 0)].remove(e)
        self.lists[(b, r, 1)].remove(e)
        self.rows[e][4] = 0
        self.free.append(e)
        self._index(a, r, b, -1)
        return 0

    def exec(self, op: str, a: int, b: int) -> int:
        if op == "GADD":
            if a >> 18:
                raise CopError("GADD dir-flags are reserved")
            if b & 0xF000:
                self._bad(b)
            return self.gadd(a & 0xFFF, a >> 12 & 63, b & 0xFFF, b >> 16 & 0xFFFF)
        if op == "GDEL":
            return self.gdel(a)
        if op == "GFIRST":
            lst = self.lists.get((self._node(a & 0xFFF), a >> 12 & 63, b & 1), [])
            return lst[0] if lst else END
        if op == "GNEXT":
            fr, r, to, _, _ = self._row(a)
            lst = self.lists[(fr, r, 0) if b & 1 == 0 else (to, r, 1)]
            i = lst.index(a) + 1
            return lst[i] if i < len(lst) else END
        if op == "GEDGE":
            row = self._row(a)
            if b > 3:
                raise CopError(f"GEDGE field {b}")
            return row[b]
        if op == "GNODE":
            h = self._node(a)
            return [self.alive, self.prop, self.scratch][b][h] if b < 3 else len(self.label[h]) if b == 3 \
                else self._bad(b)
        if op == "GSETN":
            h, f = self._node(a & 0xFFF), a >> 12
            if f == 0:
                self.alive[h] = b & 1
            elif f in (1, 2):
                (self.prop if f == 1 else self.scratch)[h] = b & 0xFFFF
            else:
                raise CopError(f"GSETN field {f}")
            return 0
        if op == "GLBYTE":
            lab = self.label[self._node(a)]
            return lab[b] if b < len(lab) else 0
        if op == "GLFIRST":
            chain = self.bucket.get(a & 0xFFF)
            return chain[0] if chain else END
        if op == "GLNEXT":
            nx = self.bnext.get(self._node(a))
            return END if nx is None else nx
        if op == "SOP":
            sub, s, t = a & 15, a >> 4 & 3, a >> 6 & 3
            if sub >= len(SOP_NAMES):
                raise CopError(f"SOP {sub}")
            name, A = SOP_NAMES[sub], self._set(s)
            if name == "clear":
                A.clear()
            elif name == "add":
                if not 0 <= b < min(self.n, SET_N):
                    raise CopError(f"SOP add {b}")
                A.add(b)
            elif name == "has":
                return int(b in A)
            elif name == "or":
                A |= self._set(t)
            elif name == "and":
                A &= self._set(t)
            elif name == "diff":
                A -= self._set(t)
            elif name == "empty":
                return int(not A)
            elif name == "first":
                return min(A) if A else END
            elif name == "count":
                return len(A)
            return 0
        if op == "EXPAND":
            s, t, k, d = a & 3, a >> 2 & 3, a >> 4 & 63, a >> 10 & 1
            if k >= N_SLOTS or self.slots[k] is None:
                raise CopError(f"EXPAND slot {k} not indexed")
            src = self._set(s)
            tot = {}
            for x in src:
                for y, c in self.nbr.get((x, k, d), {}).items():
                    tot[y] = tot.get(y, 0) + c
            if tot and max(tot.values()) > DEGREE_MAX:
                return DEGREE
            self.sets[t] = set(tot)
            return 0
        raise CopError(op)

    @staticmethod
    def _bad(v):
        raise CopError(f"operand {v:#x} out of range")


class CopMachine(ref.Machine):
    """ref.Machine plus the graph coprocessor on custom-2. Counts records (instructions) and tokens."""

    cop: Cop = None
    n_records: int = 0
    n_tokens: int = 0
    n_gops: int = 0

    @classmethod
    def make(cls, prog, cop: Cop, drom: bytes) -> "CopMachine":
        m = cls.from_program(prog)
        m.cop, m.drom = cop, drom
        m.n_records = m.n_tokens = m.n_gops = 0
        return m

    def record(self) -> list[int]:
        if self.n != S.N_MAX:
            word = self.rom[(self.pc - S.ROM_BASE) >> 2]
            if word & 0x7F == 0x5B:
                toks = self._graph(word)
                self.n_records += 1
                self.n_tokens += len(toks)
                return toks
        toks = super().record()
        self.n_records += 1
        self.n_tokens += len(toks)
        return toks

    def _graph(self, w: int) -> list[int]:
        rd, f3, rs1, rs2, f7 = w >> 7 & 31, w >> 12 & 7, w >> 15 & 31, w >> 20 & 31, w >> 25
        op = BY_SEL.get((f7, f3))
        self.steps += 1
        if op is None:
            self.halted, self.fault = True, (S.FAULTS.index("illegal"), self.pc)
            return S.fault_record(S.FAULTS.index("illegal"), self.pc)
        v = self.cop.exec(op, self.x[rs1], self.x[rs2]) & M32
        self.n_gops += 1
        self.n += 1
        if rd:
            self.x[rd] = v
            return [gop_tok(op)] + S.value_record(v)
        return [gop_tok(op), S.tok("NT")]
