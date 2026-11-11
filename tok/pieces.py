"""Refused names in tokens: a piece table from the graph's own names, boot data only, firmware prints through it. See REGISTRATION.md T7, T8. Also for t8's generator.

Table, appended after the boot image, header word 28 its offset from BOOT_ADDR (0: no table), 29 its size in bytes:
  u16 bucket[512]   first entry's index in u16 words from the table's start, 0xFFFF empty; hash = ghash(piece bytes) & 511
  entry: u16 next, u16 len | nw << 8, piece bytes padded to even, u16 words[nw] (tok/boot_tok.py's encoding)
PUT_SPAN_C replaces put_span in the firmware: bytes stay exact whatever the table holds, since a piece prints only when all its bytes compare equal.
"""
import struct

import boot_tok as BT
from refused import cut

WS = (32, 9, 10, 13, 11, 12)


def build_table(names):
    t = {}
    for s in names:
        if any(x in s for x in _added()):
            continue
        p = cut((" " + s).encode())
        for x in p or []:
            if len(x) >= 2 and len(x) < 256 and x not in t:
                t[x] = BT.encode_entries(BT.TEXT.tok.encode(x.decode(), add_special_tokens=False).ids)
    buckets = [[] for _ in range(512)]
    for k in t:
        buckets[BT.ghash(k) & 511].append(k)
    head = [0xFFFF] * 512
    words = []
    for b, keys in enumerate(buckets):
        prev = None
        for k in keys:
            at = 512 + len(words)
            if prev is None:
                head[b] = at
            else:
                words[prev - 512] = at
            prev = at
            w = t[k]
            assert len(w) < 256
            pad = k + b"\0" * (len(k) & 1)
            words += [0xFFFF, len(k) | len(w) << 8] + list(struct.unpack(f"<{len(pad) // 2}H", pad)) + w
    assert 512 + len(words) < 0xFFFF
    return struct.pack(f"<{512 + len(words)}H", *(head + words)), len(t)


def _added():
    return [a.content for a in BT.TEXT.tok.get_added_tokens_decoder().values()]


_CACHE = {}


def attach(drom, names, limit=128 * 1024):
    """The DROM image with the table after it and header words 28, 29 set; unchanged if it would not fit."""
    key = tuple(names)
    if key not in _CACHE:
        _CACHE[key] = build_table(names)
    tab, n = _CACHE[key]
    start = len(drom) + (-len(drom) % 4)
    if start + len(tab) > limit:
        return drom, 0
    off = start - BT.BOOT_OFF
    b = bytearray(drom.ljust(start, b"\0") + tab)
    struct.pack_into("<2I", b, BT.BOOT_OFF + 4 * 28, off, len(tab))
    return bytes(b), n


PUT_SPAN_C = r'''// tok/pieces: an echoed argument through the piece table. a(k): the bytes after a virtual pending space.
#define PA(k) (virt ? ((k) ? p[(k) - 1] : 32u) : (u32)p[k])
static inline u32 p_letter(u32 c) { return (c | 32) - 'a' < 26u; }
static inline u32 p_digit(u32 c) { return c - '0' < 10u; }
static inline u32 p_ws(u32 c) { return c == 32 || (c >= 9 && c <= 13); }
static __attribute__((noinline)) u32 p_cut(const u8 *p, u32 virt, u32 m, u32 i) {  // the end of the piece starting at i: the tokenizer's regex on ASCII
    u32 c = PA(i), j = i + 1;
    if (c == '\'' && j < m) {
        u32 d = PA(j) | 32, e = j + 1 < m ? PA(j + 1) | 32 : 0;
        if (d == 's' || d == 't' || d == 'm' || d == 'd') return i + 2;
        if ((d == 'r' && e == 'e') || (d == 'v' && e == 'e') || (d == 'l' && e == 'l')) return i + 3;
    }
    if (p_letter(c) || (c != 13 && c != 10 && !p_digit(c) && j < m && p_letter(PA(j)))) {
        while (j < m && p_letter(PA(j))) j++;
        return j;
    }
    if (p_digit(c)) return j;
    if (c == 32 && j < m && !p_ws(PA(j)) && !p_digit(PA(j))) {
        j++;
        while (j < m && !p_letter(PA(j)) && !p_digit(PA(j)) && !p_ws(PA(j))) j++;
        return j;
    }
    if (p_ws(c)) {
        while (j < m && p_ws(PA(j))) j++;
        return j;
    }
    while (j < m && !p_letter(PA(j)) && !p_digit(PA(j)) && !p_ws(PA(j))) j++;
    return j;
}
static __attribute__((noinline)) const u16 *p_find(const u8 *p, u32 virt, u32 i, u32 j) {  // the entry of piece [i, j), or 0
    u32 h = 0x811C9DC5u;
    for (u32 k = i; k < j; k++) h = (h ^ PA(k)) * 0x01000193u;
    h = (h ^ h >> 12 ^ h >> 24) & 511u;
    u32 at = PTAB[h];
    while (at != 0xFFFFu) {
        const u16 *e = PTAB + at;
        if ((e[1] & 255u) == j - i) {
            const u8 *b = (const u8 *)(e + 2);
            u32 k = 0;
            while (k < j - i && b[k] == PA(i + k)) k++;
            if (k == j - i) return e;
        }
        at = e[0];
    }
    return 0;
}
static void put_span(const u8 *p, u32 n) {
    u32 virt = PEND;
    PEND = 0;
    u32 m = n + virt;
    u32 ascii = PTAB != 0;
    for (u32 k = 0; ascii && k < n; k++) if (p[k] >= 128) ascii = 0;
    if (!ascii) {
        if (virt) put(' ');
        for (u32 i = 0; i < n; i++) put(p[i]);
        return;
    }
    for (u32 i = 0; i < m; ) {
        u32 j = p_cut(p, virt, m, i);
        const u16 *e = j - i >= 2 ? p_find(p, virt, i, j) : 0;
        if (e) {
            u32 len = e[1] & 255u, nw = e[1] >> 8;
            const u16 *w = e + 2 + (len + 1) / 2;
            put_run(w, w + nw);
        } else {
            for (u32 k = i; k < j; k++) put(PA(k));
        }
        i = j;
    }
}
#undef PA
'''

OLD_PUT_SPAN = "static void put_span(const u8 *p, u32 n) { flush_pend(); for (u32 i = 0; i < n; i++) put(p[i]); }\n"
PTAB_DECL = "static const u16 *PTAB;\n"
INIT_LINE = "    if (HDR[28]) PTAB = (const u16 *)(BOOTB + HDR[28]);\n"


def patch(src):
    """Firmware source (a tok/gen_fw.py output) with the table's put_span."""
    assert OLD_PUT_SPAN in src
    src = src.replace(OLD_PUT_SPAN, PTAB_DECL + PUT_SPAN_C)
    a = "    LTOKOFF = (const u16 *)(BOOTB + HDR[22]);\n"
    assert a in src
    return src.replace(a, INIT_LINE + a)
