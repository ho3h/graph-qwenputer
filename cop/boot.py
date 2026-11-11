"""Boot an ``x210-graph/1`` file: the coprocessor state (graph-op build) and the DROM boot blob (both builds).

The hash is defined once, here (``ghash``) and in graphlib.c (``ghash``), as the same FNV-1a-32 over UTF-8 bytes
folded to 12 bits; test_a1_dev.py checks that every label of every graph resolves through its bucket.

DROM layout: the program's .rodata from 0x20000 (at most 4 KB), then the boot blob at BOOT_ADDR = 0x21000.
The blob starts with HDR_WORDS u32 words (offsets are from BOOT_ADDR):
   0 magic 'X210'   1 N   2 R   3 change (0xFFFFFFFF: none)   4 flags (bit0: EXPAND slot 0 = all relations,
   bit1: sets usable, N <= SET_N)   5 number of splice relations   6 E
   7 reldir: R u32 = name offset | length << 16 (into relnames)   8 relnames   9 splice: R bytes
  10 relhash: RELHASH bytes, rel + 1 (0 empty), linear probing from ghash(name) % RELHASH
  -- software sections (NO_GRAPH_OPS build only; 0 when absent) --
  11 laboff u32[N+1]   12 labdata   13 bucket u16[4096] (0xFFFF: empty)   14 lnext u16[N]
  15 outoff u16[N+1]   16 outent u32[E] = to | rel << 12   17 outw u16[E]
  18 inoff u16[N+1]    19 inent u32[E] = from | rel << 12  20 inw u16[E]
  21 prop u16[N]
"""

import json
import struct
import unicodedata

from cop_ref import Cop, CopError, LABEL_MAX, N_MAX, E_ROWS, R_MAX, SET_N

M32 = 0xFFFFFFFF
DROM_BASE, BOOT_ADDR, DROM_SIZE = 0x20000, 0x21000, 128 * 1024
BOOT_OFF = BOOT_ADDR - DROM_BASE
HDR_WORDS, RELHASH, MAGIC = 22, 128, 0x30313258
NONE16 = 0xFFFF
SW_MAXN = 1024  # graphlib.c MAXN in the NO_GRAPH_OPS build


class BootLimit(Exception):
    pass


def ghash(b: bytes) -> int:
    h = 0x811C9DC5
    for c in b:
        h = ((h ^ c) * 0x01000193) & M32
    return (h ^ h >> 12 ^ h >> 24) & 0xFFF


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def load(path_or_dict):
    g = path_or_dict if isinstance(path_or_dict, dict) else json.load(open(path_or_dict))
    assert g["format"] == "x210-graph/1"
    return g


def boot(g, rodata: bytes, software: bool, index: bool = True):
    """(Cop or None, DROM bytes). ``software`` selects the NO_GRAPH_OPS image (graph in DROM arrays, no Cop);
    ``index=False`` leaves EXPAND unindexed so path runs the cursor search (tests both routes)."""
    g = load(g)
    labels = [n["label"] for n in g["nodes"]]
    props = [n.get("prop", 0) for n in g["nodes"]]
    rels = list(g["relations"])
    N, R = len(labels), len(rels)
    if N > N_MAX:
        raise BootLimit(f"FULL nodes {N} > {N_MAX}")
    if R > R_MAX:
        raise BootLimit(f"FULL relations {R} > {R_MAX}")
    rix = {r: i for i, r in enumerate(rels)}  # reflib's map: a repeated name resolves to its last index
    splice = sorted({rix[r] for r in g.get("splice", [])})
    change = rix[g["change"]] if g.get("change") else None
    edges = sorted(tuple(e) for e in g["edges"])
    E = len(edges)
    if len({(a, r, b) for a, r, b, _ in edges}) != E:
        raise BootLimit("duplicate (from, rel, to) edge (SPEC 1 forbids them)")
    if software and N > SW_MAXN:
        raise BootLimit(f"software image holds N <= {SW_MAXN} (N = {N})")
    if E > E_ROWS:
        raise BootLimit(f"FULL edges {E} > {E_ROWS}")
    labb = []
    for lab in labels:
        if unicodedata.normalize("NFC", lab) != lab:
            raise BootLimit(f"label not NFC: {lab!r}")
        b = lab.encode()
        if len(b) > LABEL_MAX:
            raise BootLimit(f"label of {len(b)} bytes > {LABEL_MAX}: {lab!r}")
        labb.append(b)
    keys = [norm(lab).encode() for lab in labels]
    idx = index and N <= SET_N

    cop = None
    if not software:
        cop = Cop()
        for b, p in zip(labb, props):
            cop.add_node(b, p)
        for h, k in enumerate(keys):
            cop.link_label(h, ghash(k))
        if idx:
            cop.declare_slot(0, range(R))
        for a, r, b, w in edges:
            e = cop.gadd(a, r, b, w)
            if e == (-2) & M32:
                raise BootLimit("FULL edge rows")

    # --- the blob ---
    blob = bytearray(4 * HDR_WORDS)
    hdr = [0] * HDR_WORDS

    def put(data: bytes, align: int = 4) -> int:
        blob.extend(bytes(-len(blob) % align))
        off = len(blob)
        blob.extend(data)
        return off

    names = [r.encode() for r in rels]
    relnames = b"".join(names)
    dirw, o = [], 0
    for b in names:
        assert len(b) < 1 << 16 and o < 1 << 16
        dirw.append(o | len(b) << 16)
        o += len(b)
    hdr[7] = put(struct.pack(f"<{R}I", *dirw))
    hdr[8] = put(relnames)
    hdr[9] = put(bytes(int(i in splice) for i in range(R)))
    table = [0] * RELHASH
    for name, i in rix.items():
        s = ghash(name.encode()) % RELHASH
        while table[s]:
            s = (s + 1) % RELHASH
        table[s] = i + 1
    hdr[10] = put(bytes(table))
    if software:
        laboff = [0]
        for b in labb:
            laboff.append(laboff[-1] + len(b))
        hdr[11] = put(struct.pack(f"<{N + 1}I", *laboff))
        hdr[12] = put(b"".join(labb))
        bucket, lnext, last = [NONE16] * 4096, [NONE16] * N, {}
        for h, k in enumerate(keys):
            s = ghash(k)
            if s in last:
                lnext[last[s]] = h
            else:
                bucket[s] = h
            last[s] = h
        hdr[13] = put(struct.pack("<4096H", *bucket))
        hdr[14] = put(struct.pack(f"<{N}H", *lnext))
        for d, (base_o, base_e, base_w) in enumerate(((15, 16, 17), (18, 19, 20))):
            lst = sorted((a, r, b, w) if d == 0 else (b, r, a, w) for a, r, b, w in edges)
            off, i = [], 0
            for h in range(N + 1):
                while i < len(lst) and lst[i][0] < h:
                    i += 1
                off.append(i)
            hdr[base_o] = put(struct.pack(f"<{N + 1}H", *off))
            hdr[base_e] = put(struct.pack(f"<{E}I", *[y | r << 12 for _, r, y, _ in lst]))
            hdr[base_w] = put(struct.pack(f"<{E}H", *[w for *_, w in lst]))
        hdr[21] = put(struct.pack(f"<{N}H", *props))
    hdr[:7] = [MAGIC, N, R, M32 if change is None else change, int(idx) | int(N <= SET_N) << 1, len(splice), E]
    blob[:4 * HDR_WORDS] = struct.pack(f"<{HDR_WORDS}I", *hdr)

    if len(rodata) > BOOT_OFF:
        raise BootLimit(f"program rodata {len(rodata)} > {BOOT_OFF}")
    drom = rodata.ljust(BOOT_OFF, b"\0") + bytes(blob)
    if len(drom) > DROM_SIZE:
        raise BootLimit(f"DROM {len(drom)} > {DROM_SIZE} bytes (graph too large for this image)")
    return cop, drom
