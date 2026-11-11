"""Item 2: the capacity law of the C build, checked against the code, and the options table.

    python fw/capacity_law.py

Writes results/capacity_law.json. Three kinds of number, kept apart in the output:
  computed   from the vendored code, cop/boot.py, the built ELFs and fw/capacity_core.py's IR builds
  checked    computed and then run: boots against the DROM law; graphs answered by a recompiled firmware against reflib
  estimated  paper arithmetic for circuits that do not exist (graph heads, EXPAND)
Never reads data/heldout. Bounded: fixed lists of sizes.
"""

import json
import math
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwbox as F  # noqa: E402

X, B, BR, S = F.X, F.B, F.BR, F.S
sys.path.insert(0, os.path.join(F.X210, "lib"))
import reflib  # noqa: E402
from chipformer.q35.merge import pick_hidden  # noqa: E402

RES = os.path.join(HERE, "results")
KH_PER_LAYER = 16
DROM_KH_BYTES = 8192       # core.py byte_rows: 128 rows x 2 value heads x 32 bytes
RAM_KH_BYTES = 1024        # core.py L7-8: 128 rows x 2 value heads x 1 word
ROW_BITS = 126             # q35/ir.py HD = 128, less REF_COLS, per value head
VH_PER_KH = 2
ROWS = 128
BASE_H = 2560


def drom_law(N, E, label_total, R, rel_bytes):
    """cop/boot.py's image, in bytes, before alignment padding (at most 3 bytes per section)."""
    return (B.BOOT_OFF + 4 * B.HDR_WORDS + 4 * R + rel_bytes + R + B.RELHASH + 4 * (N + 1) + label_total + 8192 + 2 * N
            + 2 * (2 * (N + 1) + 4 * E + 2 * E) + 2 * N)


def ram_law(N, E_tomb=10752, cst=False, stack=560):
    """rvc/graphlib.c .bss at NO_GRAPH_OPS -DBRIDGE, plus the lowest stack seen (560 bytes in M1).
    0x100 data start; cb 1280; dead_ 2 x E/32 words; eheap 1024 words; w2, scratch 2N each; wk max(2N, 2048 words); seven
    N-bit maps; the overlay 256 x 7 bytes; globals 124; aligned to 16."""
    bss = 0x100 + 1280 + 2 * 4 * (E_tomb // 32) + 4096 + 4 * N + max(2 * N, 8192) + 7 * 4 * (N // 32) + 256 * 7 + 124
    if cst:
        bss += N
    return bss + stack, bss


def boot_size(g, rodata):
    return len(B.boot(g, rodata, software=True)[1])


def graph(N, E, lab=16, R=4, rng=None):
    rng = rng or random.Random(N * 7 + E)
    seen, out = set(), []
    for _ in range(40 * E + 1000):
        if len(out) == E:
            break
        a, b, r = rng.randrange(N), rng.randrange(N), rng.randrange(R)
        if (a, r, b) not in seen:
            seen.add((a, r, b))
            out.append([a, r, b, rng.randint(0, 9)])
    assert len(out) == E
    return {"format": "x210-graph/1", "name": "cap", "domain": "test",
            "nodes": [{"label": ("%0*d" % (lab, i))[:lab]} for i in range(N)], "relations": [f"line {i}" for i in range(R)],
            "edges": sorted(out), "splice": [], "change": None, "meta": {}}


def check_drom():
    prog = X.elf.program(os.path.join(F.X210, "rvc", "build", "graphlib-bridge.elf"))
    out = []
    for N, E, lab, R in ((64, 9000, 16, 4), (500, 1800, 16, 4), (1024, 7486, 16, 4), (256, 5000, 24, 20), (12, 100, 5, 2)):
        g = graph(N, E, lab, R)
        got = boot_size(g, prog.rodata)
        law = drom_law(N, E, sum(len(n["label"].encode()) for n in g["nodes"]), R, sum(len(r) for r in g["relations"]))
        out.append({"N": N, "E": E, "label": lab, "R": R, "boot": got, "law": law, "diff": got - law})
    return out


def maxn_build(maxn, src, tag):
    """The firmware recompiled with MAXN changed: returns (bss end, ELF path, or the linker's refusal)."""
    text = open(src).read()
    new = re.sub(r"#ifdef NO_GRAPH_OPS\n#define MAXN 1024u", f"#ifdef NO_GRAPH_OPS\n#define MAXN {maxn}u", text)
    assert new != text or maxn == 1024
    p = os.path.join(F.BUILD, f"maxn{maxn}_{tag}.c")
    open(p, "w").write(new)
    elf_path = os.path.join(F.BUILD, f"maxn{maxn}_{tag}.elf")
    r = subprocess.run([X.CLANG, *F.RAW_FLAGS, os.path.join(F.ENV, "crt0.S"), os.path.join(F.X210, "tools", "rt_mini.c"), p, "-o", elf_path],
                       capture_output=True, text=True)
    if r.returncode:
        return None, None, r.stderr[-200:]
    nm = subprocess.run(["/opt/homebrew/opt/llvm/bin/llvm-nm", elf_path], capture_output=True, text=True).stdout
    end = int(next(ln.split()[0] for ln in nm.splitlines() if ln.endswith(" _end")), 16)
    return end, elf_path, None


def check_recompile(T):
    """No new heads: N above 1,024 by recompiling. Real calls on real boots against reflib (boot's N limit lifted in memory)."""
    src = os.path.join(F.X210, "rvc", "graphlib.c")
    out = []
    for maxn in (1024, 2048, 2560, 2816, 3072, 4096):
        end, path, err = maxn_build(maxn, src, "rvc")
        row = {"MAXN": maxn, "bss_end": end, "law_bss": ram_law(maxn)[1], "free_for_stack": None if end is None else 0x8000 - end, "link": err or "ok"}
        out.append(row)
        if end is None or 0x8000 - end < 560:
            continue
        N = maxn - 16
        E = max(1, (B.DROM_SIZE - 4096 - 8192 - 300 - 28 * N) // 12 - 8)  # the largest edge count near the image's limit, 16-byte labels
        if E < 16:
            row["E"], row["fits"] = E, False
            continue
        g = graph(N, E)
        X.ELF = path
        B.SW_MAXN = maxn
        prog = X.elf.program(path)
        _, drom = B.boot(g, prog.rodata, software=True)
        m = F.ref.Machine.from_program(prog)
        m.drom = drom
        BR.park(m)
        ses = BR.Session(T, m)
        G = reflib.Graph(g)
        rng = random.Random(maxn)
        calls = []
        for _ in range(3):
            a, b = rng.randrange(N), rng.randrange(N)
            calls += [("path", {"from": f"@{a}", "to": f"@{b}"}), ("cheapest", {"from": f"@{a}", "to": f"@{b}"}),
                      ("neighbours", {"node": f"@{a}", "relation": "line 1"})]
        calls += [("close", {"node": f"@{N // 2}"}), ("path", {"from": "@0", "to": f"@{N - 1}"}),
                  ("find", {"name": ("%0*d" % (16, N - 1))})]
        ok = bad = 0
        toks = {}
        for fn, a in calls:
            want = G.call(fn, a)
            k = len(ses.toks)
            ids = T.encode(X.template_text(fn, a))
            ses.qwen([T.TCO] + ids + [T.TCC], max_records=8_000_000)
            raw = T.decode_bytes(ses.runs[-1]).decode("utf-8", "surrogateescape")
            got = raw.split("<tool_response>\n", 1)[1].split("\n</tool_response>", 1)[0]
            ok += got == want
            bad += got != want
            toks.setdefault(fn, []).append(sum(not S.is_text(t) for t in ses.toks[k:]))
        row.update({"N": N, "E": E, "drom": len(drom), "calls_equal_reflib": ok, "calls_wrong": bad,
                    "tokens_max": {f: max(v) for f, v in toks.items()}})
    return out


# ------------------------------------------------------------------------------------------------- the options
def sw_requires(N, E, lab=16, R=20, rel=8, added=0):
    """What the C build needs for this graph: (DROM bytes, RAM bytes). Computed from the two laws."""
    d = drom_law(N, E, lab * N, R, rel * R)
    tomb = max(10752, E)                 # dead_ must cover E
    r, _ = ram_law(max(1024, N), tomb)
    r += max(0, added - 256) * 7
    return d, r


def fits(d, r, N, E, drom, ram):
    why = []
    if N > 4096:
        why.append("N>4096 (12-bit handle)")
    if E >= 32768:
        why.append("E>=32768 (cursor format)")
    if d > drom:
        why.append(f"DROM {d // 1024} KB")
    if r > ram:
        why.append(f"RAM {r // 1024} KB")
    return why


OPTIONS = [("today: 128 KB DROM, 32 KB RAM, MAXN 1024 (the merged build)", 1 << 17, 1 << 15, 1024, False),
           ("no new heads: firmware recompiled, MAXN 2816", 1 << 17, 1 << 15, 2816, True),
           ("+16 KH: 256 KB DROM", 1 << 18, 1 << 15, 2816, True),
           ("+48 KH: 512 KB DROM", 1 << 19, 1 << 15, 2816, True),
           ("+112 KH: 1 MB DROM", 1 << 20, 1 << 15, 2816, True),
           ("+80 KH: 512 KB DROM, 64 KB RAM", 1 << 19, 1 << 16, 4096, True),
           ("+144 KH: 1 MB DROM, 64 KB RAM", 1 << 20, 1 << 16, 4096, True)]
GRAPHS = [("NYC estimate (DESIGN: 496, 1,761)", 496, 1761, 18, 50, 0),
          ("r097, dev (928, 12,503)", 928, 12503, 16, 20, 0),
          ("frontier today (1,024, 7,486)", 1024, 7486, 16, 4, 0),
          ("sparse 2,048 (E = 4N)", 2048, 8192, 16, 20, 0),
          ("large sparse (4,096, 16,000)", 4096, 16000, 16, 20, 0),
          ("large sparse (4,096, 30,000)", 4096, 30000, 16, 20, 0),
          ("dense (256, 16,384): 25% density", 256, 16384, 16, 20, 0),
          ("dense (128, 16,256): complete", 128, 16256, 16, 4, 0),
          ("dense (512, 32,000): 12% density", 512, 32000, 16, 20, 0),
          ("dense (1,024, 16,384)", 1024, 16384, 16, 20, 0),
          ("past every format (4,096, 65,536)", 4096, 65536, 16, 20, 0),
          ("edits: NYC estimate + 1,000 live added edges", 496, 1761, 18, 50, 1000),
          ("edits: NYC estimate + 4,000 live added edges", 496, 1761, 18, 50, 4000)]


def core_costs():
    out = {}
    for name in sorted(os.listdir(RES)):
        if name.startswith("capacity_core_") and name.endswith(".json"):
            d = json.load(open(os.path.join(RES, name)))
            out[name[len("capacity_core_"):-5]] = {k: d[k] for k in ("drom_bytes", "ram_bytes", "chip_layers", "key_heads", "slots", "hidden", "gb_estimate")}
    return out


def gb(hidden, layers, vocab=484_800):
    return round(2 * hidden * (vocab + 37_400 * layers + 1_473_000) / 1e9, 2)


def graph_heads(N, E, R, label_bytes=64, slots=1, dirs=2):
    """Estimated key heads of the graph circuits (COPROCESSOR.md tables), from the head geometry above."""
    keyed = lambda rows, vh=1: math.ceil(rows * vh / (ROWS * VH_PER_KH))
    edge_lo, edge_hi = keyed(E, 1), keyed(E, 4)   # all fields in one row and rewritten together / {from rel to w}, next-out, next-in, alive written apart
    node = keyed(N, 2)                            # {alive, prop, label length}, {scratch}: written apart
    labels = math.ceil(N * label_bytes / DROM_KH_BYTES)  # boot-only: a byte table
    labdir = math.ceil((4096 + N) * 2 / DROM_KH_BYTES)
    heads_dense = keyed(N * R * 2)                # first-out and first-in, dense (node, rel)
    heads_node = keyed(N * 2)                     # one first-out and first-in per node, walk the relations (COPROCESSOR proposal 6)
    heads_hashed = keyed(4 * E)                   # hashed non-empty pairs at load 1/2, both directions
    return {"node": node, "labels_boot": labels, "label_dir_boot": labdir, "edges_lo": edge_lo, "edges_hi": edge_hi,
            "list_heads_dense_NxR": heads_dense, "list_heads_per_node": heads_node, "list_heads_hashed": heads_hashed,
            "total_lo": node + labels + labdir + edge_lo + heads_node, "total_hi": node + labels + labdir + edge_hi + heads_dense,
            "total_lo_layers": math.ceil((node + labels + labdir + edge_lo + heads_node) / KH_PER_LAYER),
            "total_hi_layers": math.ceil((node + labels + labdir + edge_hi + heads_dense) / KH_PER_LAYER)}


def expand_heads(N, slots=1, dirs=2):
    per = math.ceil(N / ROWS) * math.ceil(N / (ROW_BITS * VH_PER_KH))
    sets = 4 * math.ceil(N / (ROW_BITS * VH_PER_KH))
    live = 2 * N                                   # a set op reads two sets: N dims each; EXPAND's out is a set too
    hidden, m = pick_hidden(BASE_H, 1 + 1265 + live)
    layers_added = math.ceil((per * slots * dirs + sets) / KH_PER_LAYER)
    return {"N": N, "neighbour_KH_per_slot_dir": per, "neighbour_KH": per * slots * dirs, "sets_KH": sets, "residual_dims_added_at_least": live,
            "hidden": hidden, "layers_added": layers_added, "gb_estimate": gb(hidden, 11 + layers_added)}


def main():
    T = BR.Text(X.tokenizer_json())
    res = {"note": "computed from code unless under `estimated`; see fw/DEVLOG.md"}
    res["computed"] = {
        "head_geometry": {"key_heads_per_attention_sublayer": 16, "value_heads_per_key_head": 2, "rows_per_key_head": ROWS, "columns_per_value_head": 128, "usable_columns": ROW_BITS,
                          "DROM_bytes_per_key_head": DROM_KH_BYTES, "RAM_bytes_per_key_head": RAM_KH_BYTES, "ROM_bytes_per_key_head": 8192},
        "merged_build": {"key_heads": 103, "chip_layers": 11, "hidden": 3968, "ROM_KH": 32, "RAM_KH": 32, "DROM_KH": 16, "text_buffer_KH": 1,
                         "ROM_bytes_used": 33336, "rodata_used": 460, "ram_bss_end": 23424, "ram_free_after_stack": 8784},
        "drom_law": "12,504 + (12 + mean label bytes) N + 12 E + (5 + mean relation-name bytes) R bytes (padding at most a few bytes)",
        "ram_law": "23,424 at N <= 1,024; for N > 1,024: 256 + 1,280 + E_tomb/4 + 4,096 + 4N + max(2N, 8,192) + 7N/8 + 1,792 + 124; plus 560 of stack",
        "format_limits": {"N": "4,096: 12-bit handle in ent and in the Dijkstra key", "E": "32,767: cursor i | e << 16 with OV in bit 31 (u16 offsets alone would allow 65,535)",
                          "E_tombstones": "10,752 compiled (ESW), costing E/4 bytes of RAM", "R": 64, "label_bytes": 64, "added_edges": "256 compiled, 7 bytes each",
                          "capture_rows": 80, "heap_keys": "2,048 (exact past that, by rebuild)"}}
    res["computed"]["core_builds"] = core_costs()
    res["checked"] = {"drom_law_vs_boot": check_drom(), "recompile_vs_reflib": check_recompile(T)}
    tab = []
    for name, N, E, lab, R, added in GRAPHS:
        d, r = sw_requires(N, E, lab, R, added=added)
        row = {"graph": name, "N": N, "E": E, "added": added, "drom_needed": d, "ram_needed": r, "options": {}}
        for oname, drom, ram, maxn, patched in OPTIONS:
            why = fits(d, r, N, E, drom, ram)
            if N > maxn:
                why.append(f"MAXN {maxn}")
            if not patched and E > 10752:
                why.append("tombstones compiled to 10,752")
            if added > 256 and not patched:
                why.append("overlay 256")
            row["options"][oname] = why or "holds"
        tab.append(row)
    res["computed"]["table"] = tab
    res["estimated"] = {
        "graph_heads_envelope_4096_16384_R64": graph_heads(4096, 16384, 64),
        "graph_heads_1024_16384_R20": graph_heads(1024, 16384, 20),
        "graph_heads_256_16384_R20": graph_heads(256, 16384, 20),
        "graph_heads_NYC_estimate_496_1761_R50": graph_heads(496, 1761, 50),
        "expand": [expand_heads(n) for n in (256, 496, 1024, 2048, 4096)],
        "expand_design_envelope_N1024_4slots_2dirs": expand_heads(1024, slots=4, dirs=2),
        "edges_per_key_head": {"read-only DROM": DROM_KH_BYTES // 12, "graph rows, one row rewritten whole": ROWS * VH_PER_KH, "graph rows, four write groups": ROWS // 2,
                               "RAM overlay": RAM_KH_BYTES // 7},
    }
    json.dump(res, open(os.path.join(RES, "capacity_law.json"), "w"), indent=1)
    for row in res["checked"]["drom_law_vs_boot"]:
        print(row)
    for row in res["checked"]["recompile_vs_reflib"]:
        print(row)
    print(json.dumps(res["estimated"], indent=0)[:3000])
    for row in tab:
        print(row["graph"], row["drom_needed"], row["ram_needed"], {k[:14]: v if v == "holds" else "no" for k, v in row["options"].items()})


if __name__ == "__main__":
    main()
