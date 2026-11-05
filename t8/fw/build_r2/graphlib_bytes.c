// X2.10 graph library (SPEC.md section 3) on the RV32IM core, with the graph coprocessor (COPROCESSOR.md v0,
// custom-2 ops through .insn) or, built with -DNO_GRAPH_OPS, the same algorithms on plain DROM/RAM arrays.
//
// Runs as a parked firmware: the first run initialises and parks (exit ecall); each later run (GO) reads one
// call from the text buffer at 0x8000, prints the exact result text with putchar, and parks again. RAM and the
// coprocessor state persist between calls, so close/reopen sequences work like the circuit's.
//
// Call format in the text buffer: fn NUL (key NUL value NUL)* NUL. Values are the argument strings, unchanged.
//
// rvc/ copy of cop/graphlib.c, changed only under -DBRIDGE (see rvc/DEVLOG.md and rvc/graphlib.diff): the call comes
// from the bridge's capture (row i at 0x8000 + 16 i holds the call's i-th token) in Qwen's native tool-call text, and
// the result goes out inside the response wrapping of SPEC section 6, as qwenputer's env/calc firmware does it.
// The graph is boot data read at run time (DROM at 0x21000, see boot.py; graph-op build also the coprocessor).
//
// fw/ copy of rvc/graphlib.c (see fw/DEVLOG.md and fw/graphlib.diff): general firmware changes only, no new instruction and
// not one output byte changed. Each is on by default and can be switched off for measuring (-DFW_NO_x):
//   PUT       putchar sets only a0 and a7; a label prints through a pointer
//   PARSE     a call in the template's exact token shape is read from the rows, only names and values copied
//   LEGS      chase parses its legs in one pass
//   CHEAPEST  cheapest stops when the target is finalised; a tight loop while nothing is closed or edited
#include "rt.h"

typedef unsigned int u32;
typedef int i32;
typedef unsigned short u16;
typedef unsigned char u8;

#define END 0xFFFFFFFFu
#ifndef BRIDGE
#define TEXT ((const u8 *)0x8000)
#define TEXT_LEN 2048u
#endif
#define BOOTB ((const u8 *)0x21000)
#define HDR ((const u32 *)0x21000)
#define MAXW 65535u
#define WSAT 65536u
#define MAX_STEPS 255u
#define MAX_LEGS 16u

#ifdef NO_GRAPH_OPS
#define MAXN 1024u
#else
#define MAXN 4096u
#endif
#define EHEAPMAX 1024u
#define HEAPMAX 2048u
#define MW (MAXN / 32u)

// ---------------------------------------------------------------- the graph ops (custom-2, opcode 0x5B)
#ifndef NO_GRAPH_OPS
#define GOP(name, f3, f7)                                                                         \
    static inline __attribute__((unused)) u32 name(u32 a, u32 b) {                                \
        u32 r;                                                                                    \
        __asm__ volatile(".insn r 0x5B, " #f3 ", " #f7 ", %0, %1, %2" : "=r"(r) : "r"(a), "r"(b)); \
        return r;                                                                                 \
    }
GOP(g_add, 0, 0)
GOP(g_del, 1, 0)
GOP(g_first, 2, 0)
GOP(g_next, 3, 0)
GOP(g_edge, 4, 0)
GOP(g_node, 5, 0)
GOP(g_setn, 6, 0)
GOP(g_lbyte, 7, 0)
GOP(g_lfirst, 0, 1)
GOP(g_lnext, 1, 1)
GOP(g_sop, 2, 1)
GOP(g_expand, 3, 1)
enum { S_CLEAR, S_ADD, S_HAS, S_OR, S_AND, S_DIFF, S_EMPTY, S_FIRST, S_COUNT };
#define SOP(op, s, t, x) g_sop((op) | (s) << 4 | (t) << 6, (x))
#define EXPAND(s, t, slot, dir) g_expand((s) | (t) << 2 | (slot) << 4 | (dir) << 10, 0)
#define DEGREE 0xFFFFFFFDu
#define FULL 0xFFFFFFFEu
#endif

// ---------------------------------------------------------------- globals (RAM, persistent across calls)
static u32 N, R, CHANGE, FLAGS, NSPLICE;
static const u8 *SPLICE, *RELNAMES, *RELHASH;
static const u32 *RELDIR;
static u32 n_closed;
static u32 n_edits;  // links since boot: lists may no longer be in ascending handle order

static u32 eheap[EHEAPMAX];
static u32 seen[MW], fin[MW], rb[MW];  // eff_slow: closed nodes reached, closed nodes expanded, results
static u32 mark[MW], done[MW], over[MW];
static u16 w2[MAXN];  // Dijkstra predecessors / the path
static union {
    u16 q[MAXN];
    u32 heap[HEAPMAX];
} wk;

#define BIT(a, x) ((a)[(x) >> 5] >> ((x) & 31) & 1u)
#define SETB(a, x) ((a)[(x) >> 5] |= 1u << ((x) & 31))
#define CLRB(a, x) ((a)[(x) >> 5] &= ~(1u << ((x) & 31)))

static void clear_bits(u32 *a) {
    for (u32 i = 0, n = (N + 31) >> 5; i < n; i++) a[i] = 0;
}

// ---------------------------------------------------------------- graph access, two builds
#ifdef NO_GRAPH_OPS
static const u32 *LABOFF;
static const u8 *LABDATA;
static const u16 *BUCKET, *LNEXT, *OFF_[2], *W_[2];
static const u32 *ENT_[2];
static u32 closed_bits[MW];
static u16 scratch[MAXN];

// exam/AFTER.md P: stops added at run time, held in RAM.
#define NEWMAX 16u
#define NEWLAB 31u
static u8 new_lab[NEWMAX][NEWLAB];
static u8 new_len[NEWMAX];
static u32 new_hs[NEWMAX];
static u32 n_new, BN, bk_hs;
static inline u32 lab_len(u32 h) { return h < BN ? LABOFF[h + 1] - LABOFF[h] : new_len[h - BN]; }
static inline u32 lab_byte(u32 h, u32 i) { return h < BN ? LABDATA[LABOFF[h] + i] : new_lab[h - BN][i]; }
static void put_s_sp(u32 h);
static u32 new_scan(u32 i) {
    for (; i < n_new; i++)
        if (new_hs[i] == bk_hs) return BN + i;
    return 0xFFFFFFFFu;
}
static inline u32 is_closed(u32 h) { return n_closed && BIT(closed_bits, h); }
static inline void set_alive(u32 h, u32 a) {
    if (a) CLRB(closed_bits, h); else SETB(closed_bits, h);
}
static inline u32 bk_first(u32 hs) { u32 v = BUCKET[hs]; bk_hs = hs; return v == 0xFFFFu ? new_scan(0) : v; }
static inline u32 bk_next(u32 h) { if (h >= BN) return new_scan(h - BN + 1); u32 v = LNEXT[h]; return v == 0xFFFFu ? new_scan(0) : v; }
static inline u32 w1_get(u32 h) { return scratch[h]; }
static inline void w1_set(u32 h, u32 v) { scratch[h] = (u16)v; }
// Edits (link / unlink): DROM is read-only, so a RAM overlay holds added edges and tombstones for base entries.
// Cursors: a base entry is i | end-of-node << 16; an added edge is OV | index.
#define ADDMAX 256u
#define ESW (10752u / 32u)  // more edges than fit the DROM image (12 bytes per edge, 124 KB)
#define OV 0x80000000u
static u16 add_a[ADDMAX], add_b[ADDMAX], add_w[ADDMAX];
static u8 add_r[ADDMAX];
static u32 n_add, n_dead;
static u32 dead_[2][ESW];
static u32 ov_scan(u32 i, u32 h, u32 r, u32 d) {
    for (; i < n_add; i++)
        if (add_r[i] == r && (d ? add_b[i] : add_a[i]) == h) return OV | i;
    return END;
}
static u32 base_live(u32 i, u32 e, u32 r, u32 d) {  // first live base entry of relation r at or after i
    const u32 *ent = ENT_[d];
    for (; i < e && (ent[i] >> 12) == r; i++)
        if (!n_dead || !BIT(dead_[d], i)) return i | e << 16;
    return END;
}
static u32 node_of(u32 i, u32 d) {  // the node whose base list holds entry i
    u32 lo = 0, hi = BN;
    while (hi - lo > 1) {
        u32 m = (lo + hi) >> 1;
        if (OFF_[d][m] <= i) lo = m; else hi = m;
    }
    return lo;
}
static u32 cur_first(u32 h, u32 r, u32 d) {
    const u32 *ent = ENT_[d];
    u32 e = h < BN ? OFF_[d][h + 1] : 0;
    for (u32 i = h < BN ? OFF_[d][h] : 0; i < e; i++) {
        u32 rr = ent[i] >> 12;
        if (rr == r) {
            u32 c = base_live(i, e, r, d);
            if (c != END) return c;
            break;
        }
        if (rr > r) break;
    }
    return n_add ? ov_scan(0, h, r, d) : END;
}
static u32 cur_next(u32 c, u32 d) {
    if (c & OV) {
        u32 i = c & ~OV;
        return ov_scan(i + 1, d ? add_b[i] : add_a[i], add_r[i], d);
    }
    u32 i = c & 0xFFFFu, e = c >> 16, r = ENT_[d][i] >> 12, nx;
    if (!(n_dead | n_add)) {
        if (i + 1 < e && (ENT_[d][i + 1] >> 12) == r) return c + 1;
        return END;
    }
    nx = base_live(i + 1, e, r, d);
    if (nx != END) return nx;
    return n_add ? ov_scan(0, node_of(i, d), r, d) : END;
}
static inline u32 cur_other(u32 c, u32 d) {
    if (c & OV) { u32 i = c & ~OV; return d ? add_a[i] : add_b[i]; }
    return ENT_[d][c & 0xFFFFu] & 0xFFFu;
}
static inline u32 cur_w(u32 c, u32 d) {
    if (c & OV) return add_w[c & ~OV];
    return W_[d][c & 0xFFFFu];
}
typedef struct { u32 i, e, d, c, rr, x, r, gen; } RIt;
static inline void rit_init(RIt *it, u32 x, u32 d) {
    it->i = x < BN ? OFF_[d][x] : 0; it->e = x < BN ? OFF_[d][x + 1] : 0; it->d = d; it->x = x; it->r = 0; it->gen = n_add | n_dead | n_new;
}
static inline int rit_next(RIt *it) {
    if (it->gen) {
        while (it->r < R) {
            u32 c = cur_first(it->x, it->r, it->d);
            it->rr = it->r++;
            if (c != END) { it->c = c; return 1; }
        }
        return 0;
    }
    if (it->i >= it->e) return 0;
    const u32 *ent = ENT_[it->d];
    u32 i = it->i, rr = ent[i] >> 12;
    it->c = i | it->e << 16;
    it->rr = rr;
    do i++; while (i < it->e && (ent[i] >> 12) == rr);
    it->i = i;
    return 1;
}
#else
static inline u32 lab_len(u32 h) { return g_node(h, 3); }
static inline u32 lab_byte(u32 h, u32 i) { return g_lbyte(h, i); }
static inline u32 is_closed(u32 h) { return n_closed && !g_node(h, 0); }
static inline void set_alive(u32 h, u32 a) { g_setn(h, a); }
static inline u32 bk_first(u32 hs) { return g_lfirst(hs, 0); }
static inline u32 bk_next(u32 h) { return g_lnext(h, 0); }
static inline u32 w1_get(u32 h) { return g_node(h, 2); }
static inline void w1_set(u32 h, u32 v) { g_setn(h | 2u << 12, v); }
static inline u32 cur_first(u32 h, u32 r, u32 d) { return g_first(h | r << 12, d); }
static inline u32 cur_next(u32 c, u32 d) { return g_next(c, d); }
static inline u32 cur_other(u32 c, u32 d) { return g_edge(c, d ? 0 : 2); }
static inline u32 cur_w(u32 c, u32 d) { (void)d; return g_edge(c, 3); }
typedef struct { u32 x, d, r, c, rr; } RIt;
static inline void rit_init(RIt *it, u32 x, u32 d) { it->x = x; it->d = d; it->r = 0; }
static inline int rit_next(RIt *it) {
    while (it->r < R) {
        u32 c = g_first(it->x | it->r << 12, it->d);
        it->rr = it->r++;
        if (c != END) { it->c = c; return 1; }
    }
    return 0;
}
#endif

// ---------------------------------------------------------------- output
#ifdef FW_NO_PUT
static void put(u32 c) { rv_ecall2(1, c, 0, 0); }
#else
// The machine's putchar reads a7 and a0 only, and touches nothing else.
static inline __attribute__((always_inline)) void put(u32 c) {
    register u32 r_a0 __asm__("a0") = c;
    register u32 r_a7 __asm__("a7") = 1;
    __asm__ volatile("ecall" : : "r"(r_a0), "r"(r_a7));
}
#endif
static void put_s(const char *s) { while (*s) put((u8)*s++); }
static void put_span(const u8 *p, u32 n) { for (u32 i = 0; i < n; i++) put(p[i]); }
static void put_num(u32 v) {
    char b[11];
    int n = 0;
    do { b[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) put((u8)b[--n]);
}
#if defined(NO_GRAPH_OPS) && !defined(FW_NO_PUT)
static void put_lab(u32 h) {
    if (h >= BN) { for (u32 i = 0, n = new_len[h - BN]; i < n; i++) put(new_lab[h - BN][i]); return; }
    const u8 *p = LABDATA + LABOFF[h], *e = LABDATA + LABOFF[h + 1];
    while (p != e) put(*p++);
}
#else
static void put_lab(u32 h) { for (u32 i = 0, n = lab_len(h); i < n; i++) put(lab_byte(h, i)); }
#endif
static void put_fmt(u32 h) { put('@'); put_num(h); put(' '); put_lab(h); }
// ---------------------------------------------------------------- strings (Python str.strip whitespace, UTF-8)
typedef struct { const u8 *p; u32 n; } Span;

static u32 ws1(u32 c) { return c == 32 || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }
static u32 ws_at(const u8 *p, u32 n) {  // length of a whitespace character at p[0], or 0
    if (!n) return 0;
    u32 c = p[0];
    if (c < 0x80) return ws1(c);
    if (c == 0xC2) return n >= 2 && (p[1] == 0x85 || p[1] == 0xA0) ? 2 : 0;
    if (n < 3) return 0;
    u32 a = p[1], b = p[2];
    if (c == 0xE1) return a == 0x9A && b == 0x80 ? 3 : 0;
    if (c == 0xE2) return (a == 0x80 && (b <= 0x8A || b == 0xA8 || b == 0xA9 || b == 0xAF)) || (a == 0x81 && b == 0x9F) ? 3 : 0;
    if (c == 0xE3) return a == 0x80 && b == 0x80 ? 3 : 0;
    return 0;
}
static u32 ws_end(const u8 *p, u32 n) {  // length of a whitespace character ending at p[n - 1], or 0
    if (!n) return 0;
    if (p[n - 1] < 0x80) return ws1(p[n - 1]);
    if (n >= 2 && ws_at(p + n - 2, 2) == 2) return 2;
    if (n >= 3 && ws_at(p + n - 3, 3) == 3) return 3;
    return 0;
}
static inline u32 plain(u32 c) { return c - 33u < 95u; }  // 33..127: no whitespace character starts or ends here
static Span trim(Span s) {
    u32 k;
#ifndef FW_NO_LEGS
    if (s.n && plain(s.p[0]) && plain(s.p[s.n - 1])) return s;
#endif
    while ((k = ws_at(s.p, s.n))) s.p += k, s.n -= k;
    while ((k = ws_end(s.p, s.n))) s.n -= k;
    return s;
}
static int eq_lit(Span s, const char *lit) {
    u32 i = 0;
    for (; lit[i]; i++)
        if (i >= s.n || s.p[i] != (u8)lit[i]) return 0;
    return i == s.n;
}
static int is_digit(u32 c) { return c - '0' < 10u; }

// Python int() on str: optional sign, digits with single underscores between them (ASCII digits only).
// Returns 1 and the value (saturated at 999999, sign in *neg), or 0 when it is not an integer.
static int parse_int(Span s, u32 *val, u32 *neg) {
    s = trim(s);
    u32 i = 0, v = 0, nd = 0;
    *neg = 0;
    if (i < s.n && (s.p[i] == '+' || s.p[i] == '-')) *neg = s.p[i++] == '-';
    for (; i < s.n; i++) {
        u32 c = s.p[i];
        if (is_digit(c)) {
            nd++;
            if (v < 100000) v = v * 10 + (c - '0');
        } else if (!(c == '_' && nd && i + 1 < s.n && is_digit(s.p[i + 1]))) {
            return 0;
        }
    }
    *val = v;
    return nd != 0;
}
// 1..MAX_STEPS, or 0 when invalid or out of range.
static u32 steps_arg(Span s) {
    u32 v, neg;
    if (!parse_int(s, &v, &neg) || neg || v < 1 || v > MAX_STEPS) return 0;
    return v;
}

// ---------------------------------------------------------------- labels and relations
static u32 ghash(const u8 *p, u32 n) {
    u32 h = 0x811C9DC5u;
    for (u32 i = 0; i < n; i++) h = (h ^ p[i]) * 0x01000193u;
    return (h ^ h >> 12 ^ h >> 24) & 0xFFFu;
}
static int label_eq(u32 h, Span a) {  // the label, stripped, equals the (stripped) argument
    u32 L = lab_len(h), s = 0, e = L, k;
    u8 t[3];
    for (;;) {
        if (s >= e) break;
        t[0] = (u8)lab_byte(h, s);
        if (t[0] < 0x80) { if (ws1(t[0])) { s++; continue; } break; }
        u32 m = e - s < 3 ? e - s : 3;
        for (u32 i = 1; i < m; i++) t[i] = (u8)lab_byte(h, s + i);
        if (!(k = ws_at(t, m))) break;
        s += k;
    }
    for (;;) {
        if (e <= s) break;
        t[2] = (u8)lab_byte(h, e - 1);
        if (t[2] < 0x80) { if (ws1(t[2])) { e--; continue; } break; }
        u32 m = e - s < 3 ? e - s : 3;
        for (u32 j = 0; j + 1 < m; j++) t[3 - m + j] = (u8)lab_byte(h, e - m + j);
        k = ws_end(t + 3 - m, m);
        if (!k) break;
        e -= k;
    }
    if (e - s != a.n) return 0;
    for (u32 i = 0; i < a.n; i++)
        if (lab_byte(h, s + i) != a.p[i]) return 0;
    return 1;
}
static u32 rel_lookup(Span s) {  // relation index or END (names are matched exactly, as stored)
    u32 slot = ghash(s.p, s.n) & 127u;
    for (u32 k = 0; k < 128; k++, slot = (slot + 1) & 127u) {
        u32 v = RELHASH[slot];
        if (!v) return END;
        u32 r = v - 1, d = RELDIR[r], len = d >> 16;
        if (len != s.n) continue;
        const u8 *q = RELNAMES + (d & 0xFFFFu);
        u32 i = 0;
        while (i < len && q[i] == s.p[i]) i++;
        if (i == len) return r;
    }
    return END;
}
static u32 rel_arg(Span s) {  // a relation argument: index, or END after printing NORELATION
    s = trim(s);
    u32 r = rel_lookup(s);
    if (r == END) { put_s("NORELATION "); put_span(s.p, s.n); }
    return r;
}

// ---------------------------------------------------------------- effective edges (reflib Graph.eff)
// Closed nodes are passed through along splice relations and dropped otherwise; weights through them are minimal.
// Self-loops count. There is no result buffer, so a node's degree has no limit here: a list without a closed splice
// target is walked directly; otherwise eff_slow runs Dijkstra over the closed nodes (tentative weight in the scratch
// column, which no search uses for a closed node) and leaves the open targets in the bitmap rb.
// Weights saturate at 65536, which is exact for every use: anything above 65,535 is OVERFLOW.
static inline u32 best_get(u32 y) { return BIT(over, y) ? WSAT : w1_get(y); }
static inline void best_set(u32 y, u32 c) {
    if (c >= WSAT) SETB(over, y);
    else { CLRB(over, y); w1_set(y, c); }
}
static void hpush(u32 *a, u32 *pn, u32 k) {
    u32 i = (*pn)++;
    while (i) {
        u32 p = (i - 1) >> 1;
        if (a[p] <= k) break;
        a[i] = a[p];
        i = p;
    }
    a[i] = k;
}
static u32 hpop(u32 *a, u32 *pn) {
    u32 top = a[0], n = --*pn, k = a[n], i = 0;
    for (;;) {
        u32 c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && a[c + 1] < a[c]) c++;
        if (a[c] >= k) break;
        a[i] = a[c];
        i = c;
    }
    if (n) a[i] = k;
    return top;
}
// A bounded priority queue of (cost << 12 | node) that is still exact: a key that does not fit is dropped and
// remembered (spill, spillmin), and when a dropped key could be next, the live keys are rebuilt from the bitmaps and
// best_get. So the capacity costs time on extreme graphs, never an answer.
typedef struct { u32 *a; u32 n, cap, spill, spillmin; const u32 *reached, *finished; } Hq;
static void hq_push(Hq *q, u32 k) {
    if (q->n < q->cap) { hpush(q->a, &q->n, k); return; }
    q->spill = 1;
    if (k < q->spillmin) q->spillmin = k;
}
static void hq_refill(Hq *q) {  // keeps the smallest cap live keys (a max-heap of ~key while scanning)
    u32 *a = q->a, n = 0;
    q->spill = 0; q->spillmin = END;
    for (u32 w = 0, nw = (N + 31) >> 5; w < nw; w++) {
        u32 bits = q->reached[w] & ~q->finished[w];
        for (u32 y = w << 5; bits; bits >>= 1, y++) {
            if (!(bits & 1)) continue;
            u32 k = best_get(y) << 12 | y, drop = k;
            if (n < q->cap) { hpush(a, &n, ~k); continue; }
            if (k < ~a[0]) { drop = ~hpop(a, &n); hpush(a, &n, ~k); }
            q->spill = 1;
            if (drop < q->spillmin) q->spillmin = drop;
        }
    }
    u32 m = n;
    n = 0;
    for (u32 i = 0; i < m; i++) { u32 k = ~a[i]; hpush(a, &n, k); }
    q->n = n;
}
static int hq_pop(Hq *q, u32 *k) {
    if (q->spill && (!q->n || q->a[0] > q->spillmin)) hq_refill(q);
    if (!q->n) return 0;
    *k = hpop(q->a, &q->n);
    return 1;
}
enum { EFF_BITS, EFF_TEST, EFF_RELAX };
static void relax(u32 y, u32 w);
static u32 eff_slow(u32 r, u32 d, u32 c, u32 mode) {
    u32 n = 0, w = 0, key;
    Hq q = {eheap, 0, EHEAPMAX, 0, END, seen, fin};
    clear_bits(seen); clear_bits(fin);
    if (mode == EFF_BITS) clear_bits(rb);
    for (;;) {
        for (; c != END; c = cur_next(c, d)) {
            u32 y = cur_other(c, d), ww = w + cur_w(c, d);
            if (ww > WSAT) ww = WSAT;
            if (!is_closed(y)) {
                if (mode == EFF_TEST) return 1;
                if (mode == EFF_RELAX) relax(y, ww);
                else if (!BIT(rb, y)) { SETB(rb, y); n++; }
            } else if (!BIT(fin, y) && (!BIT(seen, y) || ww < best_get(y))) {
                SETB(seen, y);
                best_set(y, ww);
                hq_push(&q, ww << 12 | y);
            }
        }
        u32 y;
        do {
            if (!hq_pop(&q, &key)) return n;
            y = key & 0xFFFu;
        } while (BIT(fin, y));
        SETB(fin, y);
        w = key >> 12;
        c = cur_first(y, r, d);
    }
}
static u32 has_slow(u32 r, u32 d, u32 c) {  // a closed target on a splice relation's list
    if (!n_closed || !SPLICE[r]) return 0;
    for (; c != END; c = cur_next(c, d))
        if (is_closed(cur_other(c, d))) return 1;
    return 0;
}
static u32 rb_next(u32 y) {  // the lowest result >= y, or END
    if (y >= N) return END;
    u32 w = y >> 5, bits = rb[w] >> (y & 31), nw = (N + 31) >> 5;
    while (!bits) {
        if (++w >= nw) return END;
        bits = rb[w];
        y = w << 5;
    }
    while (!(bits & 1)) { bits >>= 1; y++; }
    return y;
}
// BODY runs once per effective target y of the list starting at cursor c0 (ascending only in the bitmap case)
#define EACH_TARGET(r, d, c0, y, BODY)                                       \
    if (has_slow(r, d, c0)) {                                                \
        eff_slow(r, d, c0, EFF_BITS);                                        \
        for (u32 y = rb_next(0); y != END; y = rb_next(y + 1)) { BODY }      \
    } else {                                                                 \
        for (u32 c_ = (c0); c_ != END; c_ = cur_next(c_, d)) {               \
            u32 y = cur_other(c_, d);                                        \
            if (is_closed(y)) continue;                                      \
            BODY                                                             \
        }                                                                    \
    }
static u32 eff_count(u32 r, u32 c0, u32 *first) {  // how many targets, and one of them (out-direction)
    u32 k = 0;
    if (has_slow(r, 0, c0)) {
        k = eff_slow(r, 0, c0, EFF_BITS);
        *first = rb_next(0);
        return k;
    }
    for (u32 c = c0; c != END; c = cur_next(c, 0)) {
        u32 y = cur_other(c, 0);
        if (is_closed(y)) continue;
        *first = y;
        k++;
    }
    return k;
}
static u32 eff_any(u32 h, u32 r, u32 d) {  // eff(h, r, d) is not empty (leaves rb untouched)
    u32 c0 = cur_first(h, r, d);
    for (u32 c = c0; c != END; c = cur_next(c, d)) {
        if (!is_closed(cur_other(c, d))) return 1;
        if (SPLICE[r]) return eff_slow(r, d, c0, EFF_TEST);
    }
    return 0;
}

// ---------------------------------------------------------------- node arguments (reflib Graph.node)
#define NODE_ERR 0xFFFFFFFFu        // an error line has been printed
#define NODE_CLOSED 0x80000000u     // | h: a handle to a closed node (nothing printed)

// "@digits", or "@digits label" as a response line prints it (reflib: @(\d+)(?:\s+(.+))?, fullmatch, on the
// stripped argument). *lab is the label part, empty for the bare form. Digits saturate.
static int parse_handle(Span s, u32 *h, Span *lab) {
    if (s.n < 2 || s.p[0] != '@') return 0;
    u32 v = 0, i = 1, k;
    for (; i < s.n && is_digit(s.p[i]); i++)
        if (v < 0x1000000u) v = v * 10 + (s.p[i] - '0');
    if (i == 1) return 0;
    *h = v;
    *lab = (Span){s.p + i, 0};
    if (i == s.n) return 1;
    if (!ws_at(s.p + i, s.n - i)) return 0;
    while ((k = ws_at(s.p + i, s.n - i))) i += k;
    for (u32 j = i; j < s.n; j++)
        if (s.p[j] == '\n') return 0;
    *lab = (Span){s.p + i, s.n - i};
    return 1;
}
static u32 read_name(Span a, u32 has, u32 rp);
static int reopen_none(Span a, u32 *hp);
static u32 node_arg(Span a, u32 has) {
    a = trim(a);
    u32 h;
    Span lab;
    if (parse_handle(a, &h, &lab)) {
        if (h >= N || (lab.n && !label_eq(h, lab))) { put_s("NONE "); put_span(a.p, a.n); return NODE_ERR; }
        if (is_closed(h)) return NODE_CLOSED | h;
        return h;
    }
    u32 hs = ghash(a.p, a.n), k = 0, first = END;
    for (u32 x = bk_first(hs); x != END; x = bk_next(x))
        if (!is_closed(x) && label_eq(x, a) && (has == END || eff_any(x, has, 0))) {
            if (!k++) first = x;
        }
    if (!k) { if ((first = read_name(a, has, 0)) != END) return first; put_s("NONE "); put_span(a.p, a.n); return NODE_ERR; }
    if (k == 1) return first;
    put_s("AMBIGUOUS "); put_num(k); put_s(": ");
    u32 i = 0;
    for (u32 x = bk_first(hs); x != END; x = bk_next(x))
        if (!is_closed(x) && label_eq(x, a) && (has == END || eff_any(x, has, 0))) {
            if (i++) put_s(" | ");
            put_fmt(x);
        }
    return NODE_ERR;
}
static u32 node_or_print(Span a) {  // node(); errors printed (CLOSED included); END on error
    u32 h = node_arg(a, END);
    if (h == NODE_ERR) return END;
    if (h & NODE_CLOSED) { put_s("CLOSED "); put_fmt(h & ~NODE_CLOSED); return END; }
    return h;
}

// ---------------------------------------------------------------- find, follow, chase, neighbours
// exam/R1.md: only when several open nodes share the name and exactly one has the first leg's relation. Everything else is node_or_print.
static u32 chase_start(Span a, u32 r) {
    Span t = trim(a), lab;
    u32 h;
    if (!parse_handle(t, &h, &lab)) {
        u32 hs = ghash(t.p, t.n), k = 0, on = 0, first = END;
        for (u32 x = bk_first(hs); x != END; x = bk_next(x))
            if (!is_closed(x) && label_eq(x, t)) {
                k++;
                if (eff_any(x, r, 0) && !on++) first = x;
            }
        if (k > 1 && on == 1) return first;
    }
    return node_or_print(a);
}
static u32 w_got, w_bad;
static Span *w_v;
static int chase_writes(void);
static void f_find(Span name, int has_given, Span has) {
    u32 r = END;
    if (has_given && (r = rel_arg(has)) == END) return;
    u32 h = node_arg(name, r);
    if (h == NODE_ERR) return;
    if (h & NODE_CLOSED) { put_s("CLOSED "); put_fmt(h & ~NODE_CLOSED); return; }
    put_fmt(h);
}
// follow r n steps from *h; on END / MULTI prints the line (after prefix) and returns 0
static void stop_walk(u32 leg, u32 k, u32 h, u32 s);
static void stop_change(u32 leg, u32 cnt, u32 h);
static int walk(u32 *hp, u32 r, u32 n, u32 leg) {
    u32 h = *hp;
    for (u32 s = 0; s < n; s++) {
        u32 next = END, k = eff_count(r, cur_first(h, r, 0), &next);
        if (k != 1) {
            stop_walk(leg, k, h, s);
            return 0;
        }
        h = next;
    }
    *hp = h;
    return 1;
}
static void f_follow(Span node, Span rel, Span steps) {
    u32 r = rel_arg(rel);
    if (r == END) return;
    u32 n = steps_arg(steps);
    if (!n) { put_s("BADARG steps "); put_span(steps.p, steps.n); return; }
    u32 h = node_or_print(node);
    if (h == END) return;
    if (walk(&h, r, n, 0)) put_fmt(h);
}
#ifdef FW_NO_LEGS
static void f_chase(Span start, Span legs) {
    u32 lr[MAX_LEGS], ln[MAX_LEGS], np = 0;
    // pass 1: count the non-empty parts
    for (u32 i = 0, b = 0; i <= legs.n; i++)
        if (i == legs.n || legs.p[i] == ';') {
            Span p = trim((Span){legs.p + b, i - b});
            if (p.n) np++;
            b = i + 1;
        }
    if (np < 1 || np > MAX_LEGS) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }
    np = 0;
    for (u32 i = 0, b = 0; i <= legs.n; i++)
        if (i == legs.n || legs.p[i] == ';') {
            Span p = trim((Span){legs.p + b, i - b});
            b = i + 1;
            if (!p.n) continue;
            // (.+?)\s+(\d+), fullmatch: trailing digits, the whitespace run before them, a relation without '\n'
            u32 ds = p.n, k;
            while (ds && is_digit(p.p[ds - 1])) ds--;
            u32 ws = ds;
            while ((k = ws_end(p.p, ws))) ws -= k;
            int bad = ds == p.n || ws == ds || ws == 0;
            for (u32 j = 0; j < ws && !bad; j++) bad = p.p[j] == '\n';
            if (bad) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }
            u32 r = rel_arg((Span){p.p, ws});
            if (r == END) return;
            u32 n = steps_arg((Span){p.p + ds, p.n - ds});
            if (!n) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }
            lr[np] = r;
            ln[np++] = n;
        }
#else
static void f_chase(Span start, Span legs) {
    u32 lr[MAX_LEGS], ln[MAX_LEGS], np = 0, err = 0;  // err: the first bad leg's answer (1 BADARG, 2 NORELATION)
    Span bad_rel = {0, 0};
    // one pass over the parts. A wrong leg count outranks a bad leg, so a bad leg is remembered and the parts still counted.
    for (u32 i = 0, b = 0; i <= legs.n; i++)
        if (i == legs.n || legs.p[i] == ';') {
            Span p = trim((Span){legs.p + b, i - b});
            b = i + 1;
            if (!p.n) continue;
            if (++np > MAX_LEGS || err) continue;
            // (.+?)\s+(\d+), fullmatch: trailing digits, the whitespace run before them, a relation without '\n'
            u32 ds = p.n, k;
            while (ds && is_digit(p.p[ds - 1])) ds--;
            u32 ws = ds;
            while ((k = ws_end(p.p, ws))) ws -= k;
            int bad = ds == p.n || ws == ds || ws == 0;
            for (u32 j = 0; j < ws && !bad; j++) bad = p.p[j] == '\n';
            if (bad) { err = 1; continue; }
            Span rs = trim((Span){p.p, ws});
            u32 r = rel_lookup(rs);
            if (r == END) { err = 2; bad_rel = rs; continue; }
            u32 n = 0;  // only ASCII digits here: parse_int's value, saturated
            for (u32 j = ds; j < p.n; j++)
                if (n <= MAX_STEPS) n = n * 10 + (p.p[j] - '0');
            if (n < 1 || n > MAX_STEPS) { err = 1; continue; }
            lr[np - 1] = r;
            ln[np - 1] = n;
        }
    if (np < 1 || np > MAX_LEGS || err == 1) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }
    if (err) { put_s("NORELATION "); put_span(bad_rel.p, bad_rel.n); return; }
#endif
    if (w_got >> 2 && !chase_writes()) return;
    u32 h = chase_start(start, lr[0]);
    if (h == END) return;
    for (u32 i = 0; i < np; i++) {
        u32 r = lr[i];
        if (i && !eff_any(h, r, 0)) {
            u32 cnt = 0, first = END;
            if (CHANGE != END) {
                u32 cc = cur_first(h, CHANGE, 0);
                EACH_TARGET(CHANGE, 0, cc, y, if (eff_any(y, r, 0)) { if (!cnt++) first = y; })
            }
            if (cnt != 1) { stop_change(i + 1, cnt, h); return; }
            h = first;
        }
        if (!walk(&h, r, ln[i], i + 1)) return;
    }
    put_fmt(h);
}
static void f_neighbours(Span node, Span rel, int dir_given, Span dir) {
    u32 r = rel_arg(rel);
    if (r == END) return;
    u32 d = 0;
    if (dir_given) {
        if (eq_lit(dir, "in")) d = 1;
        else if (!eq_lit(dir, "out")) { put_s("BADARG direction "); put_span(dir.p, dir.n); return; }
    }
    u32 h = node_or_print(node);
    if (h == END) return;
    u32 c0 = cur_first(h, r, d), k = 0;
    if (has_slow(r, d, c0)) {
        k = eff_slow(r, d, c0, EFF_BITS);
    } else if (n_edits) {  // an added edge sits at the end of its list: ascending order through the bitmap
        clear_bits(rb);
        for (u32 c = c0; c != END; c = cur_next(c, d)) {
            u32 y = cur_other(c, d);
            if (!is_closed(y)) { SETB(rb, y); k++; }
        }
    } else {
        for (u32 c = c0; c != END; c = cur_next(c, d)) {
            u32 y = cur_other(c, d);
            if (is_closed(y)) continue;
            if (k++) put('\n');
            put_fmt(y);
        }
        if (!k) put_s("NONE");
        return;
    }
    if (!k) { put_s("NONE"); return; }
    k = 0;
    for (u32 y = rb_next(0); y != END; y = rb_next(y + 1)) {
        if (k++) put('\n');
        put_fmt(y);
    }
}

// ---------------------------------------------------------------- path
static void print_path(u32 D) {
    put_num(D); put_s(" steps: ");
    for (u32 i = 0; i <= D; i++) {
        if (i) put_s(" > ");
        put_fmt(w2[i]);
    }
}
// the cursor search: BFS over every relation's effective out-edges; dist in the scratch column (w1)
static void path_cursor(u32 a, u32 b) {
    clear_bits(mark);
    u32 qh = 0, qt = 0, D = 0;
    SETB(mark, a); w1_set(a, 0); wk.q[qt++] = (u16)a;
    while (qh < qt) {
        u32 x = wk.q[qh++], dx = w1_get(x);
        RIt it;
        rit_init(&it, x, 0);
        while (rit_next(&it)) {
            EACH_TARGET(it.rr, 0, it.c, y, if (!BIT(mark, y)) {
                SETB(mark, y); w1_set(y, dx + 1); wk.q[qt++] = (u16)y;
                if (y == b) { D = dx + 1; goto found; }
            })
        }
    }
    put_s("NOPATH");
    return;
found:;
    u32 y = b;
    w2[D] = (u16)b;
    for (u32 k = D; k > 0; k--) {  // the lowest-handle effective in-neighbour at distance k - 1
        u32 best = END;
        RIt it;
        rit_init(&it, y, 1);
        while (rit_next(&it)) {
            EACH_TARGET(it.rr, 1, it.c, x, if (x < best && BIT(mark, x) && w1_get(x) == k - 1) best = x;)
        }
        w2[k - 1] = (u16)best;
        y = best;
    }
    print_path(D);
}

#ifndef NO_GRAPH_OPS
// EXPAND search (slot 0 = every relation). Sets: S0 / S2 frontier, S1 visited (closed nodes included from the
// start, so they never join a level), S3 the closed set. Rebuild from b: x = first(in(y) & L(k - 1)), with
// L(k - 1) recomputed from a (v0 has four sets, so the levels cannot all be kept). Returns 0 on DEGREE.
static u32 level(u32 a, u32 j, u32 *fp) {  // L(j) into S_f; returns 0 on DEGREE
    u32 f = 0, t = 2;
    SOP(S_CLEAR, 0, 0, 0); SOP(S_ADD, 0, 0, a);
    SOP(S_CLEAR, 1, 0, 0); SOP(S_ADD, 1, 0, a);
    if (n_closed) SOP(S_OR, 1, 3, 0);
    for (u32 i = 0; i < j; i++) {
        if (EXPAND(f, t, 0, 0) == DEGREE) return 0;
        SOP(S_DIFF, t, 1, 0);
        SOP(S_OR, 1, t, 0);
        u32 s = f; f = t; t = s;
    }
    *fp = f;
    return 1;
}
static int path_expand(u32 a, u32 b) {
    u32 f = 0, t = 2, D = 0;
    SOP(S_CLEAR, 0, 0, 0); SOP(S_ADD, 0, 0, a);
    SOP(S_CLEAR, 1, 0, 0); SOP(S_ADD, 1, 0, a);
    if (n_closed) SOP(S_OR, 1, 3, 0);
    for (;;) {
        if (EXPAND(f, t, 0, 0) == DEGREE) return 0;
        SOP(S_DIFF, t, 1, 0);
        if (SOP(S_EMPTY, t, 0, 0)) { put_s("NOPATH"); return 1; }
        D++;
        if (SOP(S_HAS, t, 0, b)) break;
        SOP(S_OR, 1, t, 0);
        u32 s = f; f = t; t = s;
    }
    u32 y = b;
    w2[D] = (u16)b;
    for (u32 k = D; k > 1; k--) {
        if (!level(a, k - 1, &f)) return 0;
        t = 2 - f;
        SOP(S_CLEAR, t, 0, 0); SOP(S_ADD, t, 0, y);
        EXPAND(t, 1, 0, 1);
        SOP(S_AND, 1, f, 0);
        y = SOP(S_FIRST, 1, 0, 0);
        w2[k - 1] = (u16)y;
    }
    w2[0] = (u16)a;
    print_path(D);
    return 1;
}
#endif

#ifdef NO_GRAPH_OPS
// The software baseline's BFS for the common state (nothing closed, no edits): plain loops over each node's whole
// list, with no result buffer. Same search and rebuild as path_cursor; A4 measures against this, not a slowed copy.
static void path_tight(u32 a, u32 b) {
    const u16 *off = OFF_[0], *ioff = OFF_[1];
    const u32 *ent = ENT_[0], *ient = ENT_[1];
    u32 qh = 0, qt = 0, D = 0;
    clear_bits(mark);
    SETB(mark, a); scratch[a] = 0; wk.q[qt++] = (u16)a;
    while (qh < qt && !D) {
        u32 x = wk.q[qh++], dy = scratch[x] + 1u;
        for (u32 i = off[x], e = off[x + 1]; i < e; i++) {
            u32 y = ent[i] & 0xFFFu;
            if (BIT(mark, y)) continue;
            SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y;
            if (y == b) { D = dy; break; }
        }
    }
    if (!D) { put_s("NOPATH"); return; }
    u32 y = b;
    w2[D] = (u16)b;
    for (u32 k = D; k > 0; k--) {
        u32 best = END;
        for (u32 i = ioff[y], e = ioff[y + 1]; i < e; i++) {
            u32 x = ient[i] & 0xFFFu;
            if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;
        }
        w2[k - 1] = (u16)best;
        y = best;
    }
    print_path(D);
}
#endif

// exam/AFTER.md P: a shared name whose open nodes are all joined by the change relation is one station.
static u32 find_edge(u32 a, u32 r, u32 b);
static u32 joined(const u16 *o, u32 k) {
    if (k < 2 || k > 8 || CHANGE >= R) return 0;
    for (u32 i = 1; i < k; i++)
        if (find_edge(o[0], CHANGE, o[i]) == END) return 0;
    return k;
}
static u32 station_nodes(Span a, u16 *o) {
    Span t = trim(a), lab;
    u32 h, k = 0;
    if (parse_handle(t, &h, &lab)) return 0;
    u32 hs = ghash(t.p, t.n);
    for (u32 x = bk_first(hs); x != END; x = bk_next(x))
        if (!is_closed(x) && label_eq(x, t)) { if (k < 8) o[k] = (u16)x; k++; }
    return joined(o, k);
}
static void path_multi(const u16 *A, u32 na, const u16 *B, u32 nb) {
    for (u32 i = 0; i < nb; i++)
        for (u32 j = 0; j < na; j++)
            if (A[j] == B[i]) { w2[0] = B[i]; print_path(0); return; }
    clear_bits(mark);
    u32 qh = 0, qt = 0, D = END;
    for (u32 i = 0; i < na; i++) { SETB(mark, A[i]); w1_set(A[i], 0); wk.q[qt++] = A[i]; }
    while (qh < qt) {
        u32 x = wk.q[qh++], dx = w1_get(x);
        if (D != END && dx + 1 > D) break;
        RIt it;
        rit_init(&it, x, 0);
        while (rit_next(&it)) {
            EACH_TARGET(it.rr, 0, it.c, y, if (!BIT(mark, y)) {
                SETB(mark, y); w1_set(y, dx + 1); wk.q[qt++] = (u16)y;
                if (D == END) for (u32 i = 0; i < nb; i++) if (B[i] == y) D = dx + 1;
            })
        }
    }
    if (D == END) { put_s("NOPATH"); return; }
    u32 y = END;
    for (u32 i = 0; i < nb; i++)
        if (BIT(mark, B[i]) && w1_get(B[i]) == D && B[i] < y) y = B[i];
    w2[D] = (u16)y;
    for (u32 k = D; k > 0; k--) {
        u32 best = END;
        RIt it;
        rit_init(&it, y, 1);
        while (rit_next(&it)) {
            EACH_TARGET(it.rr, 1, it.c, x, if (x < best && BIT(mark, x) && w1_get(x) == k - 1) best = x;)
        }
        w2[k - 1] = (u16)best;
        y = best;
    }
    print_path(D);
}
static void f_path(Span from, Span to) {
    u16 A[8], B[8];
    u32 na = station_nodes(from, A);
    if (!na) { u32 x = node_or_print(from); if (x == END) return; A[0] = (u16)x; na = 1; }
    u32 nb = station_nodes(to, B);
    if (!nb) { u32 x = node_or_print(to); if (x == END) return; B[0] = (u16)x; nb = 1; }
    if (na > 1 || nb > 1) { path_multi(A, na, B, nb); return; }
    u32 a = A[0], b = B[0];
    if (a == b) { w2[0] = (u16)a; print_path(0); return; }
#ifndef NO_GRAPH_OPS
    if ((FLAGS & 1) && !(n_closed && NSPLICE) && path_expand(a, b)) return;
#endif
#ifdef NO_GRAPH_OPS
    if (!(n_closed | n_add | n_dead | n_new)) { path_tight(a, b); return; }
#endif
    path_cursor(a, b);
}

// ---------------------------------------------------------------- cheapest (Dijkstra, reflib's tie rule)
// Costs saturate at 65536 (anything above 65535 is OVERFLOW, and such nodes never lie on a cheaper path). Nodes are
// finalised in queue order (cost, handle); only finalised nodes relax, and a finalised node is never touched again.
static Hq Q;
static u32 rlx_x, rlx_c;
static void relax(u32 y, u32 w) {  // one arrival from rlx_x; several from one node give the same result as their min
    if (BIT(done, y)) return;
    u32 cy = rlx_c + w;
    if (cy > WSAT) cy = WSAT;
    if (BIT(mark, y)) {
        u32 by = best_get(y);
        if (cy == by && rlx_x < w2[y]) w2[y] = (u16)rlx_x;
        if (cy >= by) return;
    } else {
        SETB(mark, y);
    }
    best_set(y, cy);
    w2[y] = (u16)rlx_x;
    hq_push(&Q, cy << 12 | y);
}
#if defined(NO_GRAPH_OPS) && !defined(FW_NO_CHEAPEST)
// Nothing closed and no edits: Dijkstra over each node's whole list, in the list's order (the general search visits the same
// entries in the same order). The queue is the same bounded key order; if it would spill, return 0 and the general search,
// which handles a spill, starts over. Nothing has been printed by then. cst[y]: 0 not reached, 1 reached, 2 reached at the
// saturated cost, 3 finalised.
static u8 cst[MAXN] __attribute__((aligned(4)));
static int cheapest_tight(u32 a, u32 b) {
    const u16 *off = OFF_[0], *wt = W_[0];
    const u32 *ent = ENT_[0];
    u32 *hp = wk.heap, n = 1, cb = END;
    for (u32 *p = (u32 *)cst, *e = (u32 *)(cst + ((N + 3) & ~3u)); p != e; p++) *p = 0;
    cst[a] = 1; scratch[a] = 0; w2[a] = 0xFFFFu; hp[0] = a;
    while (n) {
        u32 key = hp[0], k = hp[--n], i = 0;
        if (n) {  // the hole sinks to k's place
            for (;;) {
                u32 c = 2 * i + 1;
                if (c >= n) break;
                u32 av = hp[c];
                if (c + 1 < n) { u32 bv = hp[c + 1]; if (bv < av) { c++; av = bv; } }
                if (av >= k) break;
                hp[i] = av;
                i = c;
            }
            hp[i] = k;
        }
        u32 x = key & 0xFFFu;
        if (cst[x] == 3) continue;
        cst[x] = 3;
        u32 cx = key >> 12;
        if (x == b) { cb = cx; break; }
        for (u32 j = off[x], e = off[x + 1]; j < e; j++) {
            u32 y = ent[j] & 0xFFFu, s = cst[y];
            if (s == 3) continue;
            u32 cy = cx + wt[j];
            if (cy > WSAT) cy = WSAT;
            if (s) {
                u32 by = s == 2 ? WSAT : scratch[y];
                if (cy == by && x < w2[y]) w2[y] = (u16)x;
                if (cy >= by) continue;
            }
            if (cy >= WSAT) {
                cst[y] = 2;
            } else {
                if (s != 1) cst[y] = 1;
                scratch[y] = (u16)cy;
            }
            w2[y] = (u16)x;
            if (n == HEAPMAX) return 0;
            u32 kk = cy << 12 | y, h = n++;
            while (h) {
                u32 p = (h - 1) >> 1, pv = hp[p];
                if (pv <= kk) break;
                hp[h] = pv;
                h = p;
            }
            hp[h] = kk;
        }
    }
    if (cb == END) { put_s("NOPATH"); return 1; }
    if (cb > MAXW) { put_s("OVERFLOW"); return 1; }
    u32 m = 0;  // the path backwards, into the queue's space (the search is over)
    for (u32 y = b; y != 0xFFFFu; y = w2[y]) wk.q[m++] = (u16)y;
    put_s("cost "); put_num(cb); put_s(": ");
    for (u32 i = m; i > 0; i--) {
        if (i != m) put_s(" > ");
        put_fmt(wk.q[i - 1]);
    }
    return 1;
}
#endif
static void f_cheapest(Span from, Span to) {
    u32 a = node_or_print(from);
    if (a == END) return;
    u32 b = node_or_print(to);
    if (b == END) return;
#if defined(NO_GRAPH_OPS) && !defined(FW_NO_CHEAPEST)
    if (!(n_closed | n_add | n_dead | n_new) && cheapest_tight(a, b)) return;
#endif
    clear_bits(mark); clear_bits(done); clear_bits(over);
    Q = (Hq){wk.heap, 0, HEAPMAX, 0, END, mark, done};
    SETB(mark, a); best_set(a, 0); w2[a] = 0xFFFFu; hq_push(&Q, a);
    u32 key;
    while (hq_pop(&Q, &key)) {
        u32 x = key & 0xFFFu;
        if (BIT(done, x)) continue;
        SETB(done, x);
#ifndef FW_NO_CHEAPEST
        if (x == b) break;  // finalised: a finalised node is never touched again, and neither are those before it
#endif
        rlx_x = x; rlx_c = key >> 12;
        RIt it;
        rit_init(&it, x, 0);
        while (rit_next(&it)) {
            if (has_slow(it.rr, 0, it.c)) { eff_slow(it.rr, 0, it.c, EFF_RELAX); continue; }
            for (u32 c = it.c; c != END; c = cur_next(c, 0)) {
                u32 y = cur_other(c, 0);
                if (!is_closed(y)) relax(y, cur_w(c, 0));
            }
        }
    }
    if (!BIT(mark, b)) { put_s("NOPATH"); return; }
    u32 cb = best_get(b);
    if (cb > MAXW) { put_s("OVERFLOW"); return; }
    u32 n = 0;  // the path backwards, into the queue's space (the search is over)
    for (u32 y = b; y != 0xFFFFu; y = w2[y]) wk.q[n++] = (u16)y;
    put_s("cost "); put_num(cb); put_s(": ");
    for (u32 i = n; i > 0; i--) {
        if (i != n) put_s(" > ");
        put_fmt(wk.q[i - 1]);
    }
}

// ---------------------------------------------------------------- close, reopen
static void f_close(Span node) {
    u16 o[8];
    u32 m = station_nodes(node, o);
    if (m) {
        put_s("closed ");
        for (u32 i = 0; i < m; i++) { set_alive(o[i], 0); n_closed++; if (i) put_s(" | "); put_fmt(o[i]); }
        return;
    }
    u32 h = node_arg(node, END);
    if (h == NODE_ERR) return;
    if (h & NODE_CLOSED) { put_s("already closed "); put_fmt(h & ~NODE_CLOSED); return; }
    set_alive(h, 0);
#ifndef NO_GRAPH_OPS
    if (FLAGS & 2) SOP(S_ADD, 3, 0, h);
#endif
    n_closed++;
    put_s("closed "); put_fmt(h);
}
static void f_reopen(Span node) {
    Span a = trim(node);
    u32 h, k = 0;
    Span lab;
    if (parse_handle(a, &h, &lab)) {
        if (h < N && (!lab.n || label_eq(h, lab))) k = 1;
    } else {  // the closed nodes with this label, or failing that every node with it
        u32 hs = ghash(a.p, a.n), every = 0;
        for (u32 x = bk_first(hs); x != END; x = bk_next(x))
            if (label_eq(x, a)) {
                if (is_closed(x)) { if (!k++) h = x; }
                else if (!every++ && !k) h = x;
            }
        u32 only_closed = k != 0;
        if (!k) k = every;
        if (k > 1) {
            u16 o[8];
            u32 m = 0;
            for (u32 x = bk_first(hs); x != END; x = bk_next(x))
                if (label_eq(x, a) && (!only_closed || is_closed(x))) { if (m < 8) o[m] = (u16)x; m++; }
            if (joined(o, m)) {
                if (!only_closed) { put_s("not closed "); put_fmt(o[0]); return; }
                put_s("reopened ");
                for (u32 i = 0; i < m; i++) { set_alive(o[i], 1); n_closed--; if (i) put_s(" | "); put_fmt(o[i]); }
                return;
            }
            w_bad = 1; put_s("AMBIGUOUS "); put_num(k); put_s(": ");
            u32 i = 0;
            for (u32 x = bk_first(hs); x != END; x = bk_next(x))
                if (label_eq(x, a) && (!only_closed || is_closed(x))) { if (i++) put_s(" | "); put_fmt(x); }
            return;
        }
    }
    if (!k) { if (reopen_none(a, &h)) k = 1; else { w_bad = 1; put_s("NONE "); put_span(a.p, a.n); return; } }
    if (!is_closed(h)) { put_s("not closed "); put_fmt(h); return; }
    set_alive(h, 1);
#ifndef NO_GRAPH_OPS
    if (FLAGS & 2) { SOP(S_CLEAR, 2, 0, 0); SOP(S_ADD, 2, 0, h); SOP(S_DIFF, 3, 2, 0); }
#endif
    n_closed--;
    put_s("reopened "); put_fmt(h);
}

// ---------------------------------------------------------------- link, unlink
static void put_edge(const char *what, u32 a, u32 r, u32 b) {
    put_s(what); put(' '); put_fmt(a); put_s(" > ");
    u32 d = RELDIR[r];
    put_span(RELNAMES + (d & 0xFFFFu), d >> 16);
    put_s(" > "); put_fmt(b);
}
static u32 find_edge(u32 a, u32 r, u32 b) {  // the raw edge's cursor (closed nodes make no difference), or END
    for (u32 c = cur_first(a, r, 0); c != END; c = cur_next(c, 0))
        if (cur_other(c, 0) == b) return c;
    return END;
}
static void f_link(Span from, Span rel, Span to, int w_given, Span weight) {
    u32 r = rel_arg(rel);
    if (r == END) return;
    u32 w = 0, neg = 0;
    if (w_given && (!parse_int(weight, &w, &neg) || (neg && w) || w > MAXW)) {
        put_s("BADARG weight "); put_span(weight.p, weight.n);
        return;
    }
    u32 a = node_or_print(from);
    if (a == END) return;
    u32 b = node_or_print(to);
    if (b == END) return;
    if (find_edge(a, r, b) != END) { put_edge("already linked", a, r, b); return; }
#ifdef NO_GRAPH_OPS
    if (n_add >= ADDMAX) { put_s("FULL"); return; }
    add_a[n_add] = (u16)a; add_b[n_add] = (u16)b; add_w[n_add] = (u16)w; add_r[n_add] = (u8)r;
    n_add++;
#else
    if (g_add(a | r << 12, b | w << 16) == FULL) { put_s("FULL"); return; }
#endif
    n_edits++;
    put_edge("linked", a, r, b);
}
static void put_s_sp(u32 h) { put_span((const u8 *)" ", 1); put_span(new_lab[h - BN], new_len[h - BN]); }
static void f_add_node(Span name) {
    Span t = trim(name), lab;
    u32 h;
    if (!t.n || t.n > NEWLAB || parse_handle(t, &h, &lab)) { put_s("BADARG name"); return; }
    u32 hs = ghash(t.p, t.n);
    for (u32 x = bk_first(hs); x != END; x = bk_next(x))
        if (label_eq(x, t)) { put_s("already exists "); put_fmt(x); return; }
    if (n_new >= NEWMAX || N >= MAXN) { put_s("FULL"); return; }
    for (u32 i = 0; i < t.n; i++) new_lab[n_new][i] = t.p[i];
    new_len[n_new] = (u8)t.n;
    new_hs[n_new] = hs;
    n_new++;
    N++;
    put_s("added "); put_fmt(N - 1);
}
static void f_unlink(Span from, Span rel, Span to) {
    u32 r = rel_arg(rel);
    if (r == END) return;
    u32 a = node_or_print(from);
    if (a == END) return;
    u32 b = node_or_print(to);
    if (b == END) return;
    u32 c = find_edge(a, r, b);
    if (c == END) { put_edge("not linked", a, r, b); return; }
#ifdef NO_GRAPH_OPS
    if (c & OV) {
        u32 i = c & ~OV, l = --n_add;
        add_a[i] = add_a[l]; add_b[i] = add_b[l]; add_w[i] = add_w[l]; add_r[i] = add_r[l];
    } else {
        u32 c2 = cur_first(b, r, 1);
        while (cur_other(c2, 1) != a) c2 = cur_next(c2, 1);
        u32 i = c & 0xFFFFu, j = c2 & 0xFFFFu;
        SETB(dead_[0], i);
        SETB(dead_[1], j);
        n_dead++;
    }
#else
    g_del(c, 0);
#endif
    put_edge("unlinked", a, r, b);
}

// ---------------------------------------------------------------- the call
#define MAXARGS 4
#define NFN 11
static const char *const FN[NFN] = {"find", "follow", "chase", "neighbours", "path", "cheapest", "close", "reopen",
                                    "link", "unlink", "add_node"};
static const char *const PARAMS[NFN][MAXARGS] = {
    {"name", "has", 0, 0},  {"node", "relation", "steps", 0}, {"start", "legs", "closed", "reopened"},
    {"node", "relation", "direction", 0},                     {"frm", "to", 0, 0},
    {"frm", "to", 0, 0},    {"node", 0, 0, 0},                {"node", 0, 0, 0},
    {"frm", "relation", "to", "weight"},                      {"frm", "relation", "to", 0},                      {"name", 0, 0, 0}};
static const u8 REQUIRED[NFN] = {1, 7, 3, 3, 3, 3, 1, 1, 7, 7, 1};  // bit i: parameter i is required

#ifdef BRIDGE
// ---------------------------------------------------------------- the capture (host/tools.py parse_call, in C)
#define CAP_ROWS 80u
#define CAP_ROW(i) ((const u8 *)0x8000 + 16u * (i))
#define CAP_BYTES (CAP_ROWS * 16u)
static u8 cb[CAP_BYTES];  // the captured call, its tokens' bytes end to end
static u32 cn, cpos, cend;

// Copies the rows. Returns 0 when a token might be cut: a row keeps a token's first 16 bytes, so a full row is refused.
// Row CAP_ROWS holds the last token of a longer call, so a call of more than CAP_ROWS tokens has lost its middle.
static int gather(u32 *full) {
    u32 n = 0, i;
    for (i = 1; i <= CAP_ROWS; i++) {
        const u8 *r = CAP_ROW(i);
        u32 k = 0, c = r[0];
        if (!c) break;
        do {
            cb[n++] = (u8)c;
            if (++k == 16) { cn = n; return 0; }
            c = r[k];
        } while (c);
    }
    cn = n;
    *full = i > CAP_ROWS;
    return 1;
}
static u32 at(u32 i, const char *lit, u32 lim) {  // length of lit when cb[i..lim) starts with it, else 0
    u32 k = 0;
    for (; lit[k]; k++)
        if (i + k >= lim || cb[i + k] != (u8)lit[k]) return 0;
    return k;
}
static u32 find_lit(u32 i, const char *lit, u32 lim) {  // first position of lit at or after i, or END
    for (; i < lim; i++)
        if (cb[i] == (u8)lit[0] && at(i, lit, lim)) return i;
    return END;
}
// tag([^>\n]*)> at i: the name, and the position after '>'
static int named_at(u32 i, const char *tag, u32 lim, Span *name, u32 *after) {
    u32 k = at(i, tag, lim);
    if (!k) return 0;
    u32 a = i + k, j = a;
    while (j < lim && cb[j] != '>' && cb[j] != '\n') j++;
    if (j >= lim || cb[j] != '>') return 0;
    *name = (Span){cb + a, j - a};
    *after = j + 1;
    return 1;
}
static int next_param(Span *key, Span *val) {  // <parameter=NAME>(.*?)</parameter>, one template newline dropped each side
    for (u32 i = cpos; i < cend; i++) {
        u32 a;
        if (cb[i] != '<' || !named_at(i, "<parameter=", cend, key, &a)) continue;
        u32 j = find_lit(a, "</parameter>", cend);
        if (j == END) return 0;
        cpos = j + 12;
        if (a < j && cb[a] == '\n') a++;
        if (a < j && cb[j - 1] == '\n') j--;
        *val = (Span){cb + a, j - a};
        return 1;
    }
    return 0;
}
#endif

#if defined(BRIDGE) && !defined(FW_NO_PARSE)
// ---------------------------------------------------------------- the common case, read in place
// A call in the template's exact token shape (every one of Qwen's 1,358 saved calls but one):
//   \n < function =NAME.. > \n ( < parameter =KEY.. > \n VALUE.. \n </ parameter > \n )* </ function > \n
// NAME and KEY rows hold no '<', '>' or '\n', and VALUE rows no '<'. For such text parse_call's regexes can only find
// what this walk finds, so the spans are the slow path's. Anything else, including a full row and row 80 in use, returns 0
// with nothing printed, and the slow path decides. Template rows are compared as words, in place; only NAME, KEY and VALUE
// bytes reach cb. Rows are word aligned and NUL padded, and a token ends at its first NUL, as in gather.
#define MAXP 6u
#define CHR4(a, b, c, d) ((u32)(a) | (u32)(b) << 8 | (u32)(c) << 16 | (u32)(d) << 24)
#define W0(r) (((const u32 *)(r))[0])
#define W1(r) (((const u32 *)(r))[1])
#define H4(r) (((const u16 *)(r))[4])
#define IS_NL(r) (W0(r) == '\n')
#define IS_LT(r) (W0(r) == '<')
#define IS_GT(r) (W0(r) == '>')
#define IS_CL(r) (W0(r) == CHR4('<', '/', 0, 0))
#define IS_FUNCTION(r) (W0(r) == CHR4('f', 'u', 'n', 'c') && W1(r) == CHR4('t', 'i', 'o', 'n') && !(r)[8])
#define IS_PARAMETER(r) (W0(r) == CHR4('p', 'a', 'r', 'a') && W1(r) == CHR4('m', 'e', 't', 'e') && H4(r) == 'r')
typedef struct { Span fn; u32 np; Span k[MAXP], v[MAXP]; } Parsed;

// One row's bytes into o (at fixed offsets, so no address arithmetic per byte): the count, or END for a refused byte or a
// full row. A name row entered at byte 1 has r[15] == 0 (checked by the caller), so byte 14 from there ends it.
#define NAME_BAD(c) (((c) | 2u) == '>' || (c) == '\n')
#define VAL_BAD(c) ((c) == '<')
#define COPY_ROW(fname, BAD)                                                                       \
    static __attribute__((noinline)) u32 fname(const u8 *r, u8 *o) {                               \
        u32 c;                                                                                     \
        c = r[0];  if (!c) return 0;  if (BAD(c)) return END; o[0] = (u8)c;                        \
        c = r[1];  if (!c) return 1;  if (BAD(c)) return END; o[1] = (u8)c;                        \
        c = r[2];  if (!c) return 2;  if (BAD(c)) return END; o[2] = (u8)c;                        \
        c = r[3];  if (!c) return 3;  if (BAD(c)) return END; o[3] = (u8)c;                        \
        c = r[4];  if (!c) return 4;  if (BAD(c)) return END; o[4] = (u8)c;                        \
        c = r[5];  if (!c) return 5;  if (BAD(c)) return END; o[5] = (u8)c;                        \
        c = r[6];  if (!c) return 6;  if (BAD(c)) return END; o[6] = (u8)c;                        \
        c = r[7];  if (!c) return 7;  if (BAD(c)) return END; o[7] = (u8)c;                        \
        c = r[8];  if (!c) return 8;  if (BAD(c)) return END; o[8] = (u8)c;                        \
        c = r[9];  if (!c) return 9;  if (BAD(c)) return END; o[9] = (u8)c;                        \
        c = r[10]; if (!c) return 10; if (BAD(c)) return END; o[10] = (u8)c;                       \
        c = r[11]; if (!c) return 11; if (BAD(c)) return END; o[11] = (u8)c;                       \
        c = r[12]; if (!c) return 12; if (BAD(c)) return END; o[12] = (u8)c;                       \
        c = r[13]; if (!c) return 13; if (BAD(c)) return END; o[13] = (u8)c;                       \
        c = r[14]; if (!c) return 14; if (BAD(c)) return END; o[14] = (u8)c;                       \
        return r[15] ? END : 15;                                                                   \
    }
COPY_ROW(copy_name, NAME_BAD)
COPY_ROW(copy_val, VAL_BAD)

// =NAME.. up to the row ">": *rp on the "=" row before, on the ">" row after. NAME is not empty.
static int name_rows(const u8 **rp, u8 **op, Span *name) {
    const u8 *r = *rp;
    u8 *o = *op;
    if (r[0] != '=' || r[15]) return 0;
    u32 n = copy_name(r + 1, o);
    if (n == END) return 0;
    o += n;
    for (;;) {
        r += 16;
        if (IS_GT(r)) break;
        n = copy_name(r, o);
        if (n == END || !n) return 0;
        o += n;
    }
    if (o == *op) return 0;
    *name = (Span){*op, (u32)(o - *op)};
    *rp = r;
    *op = o;
    return 1;
}
static int fast_parse(Parsed *P) {
    const u8 *r = CAP_ROW(1);
    u8 *o = cb;
    u32 np = 0;
    if (CAP_ROW(80)[0]) return 0;  // the window's last row in use: the slow path knows what that means
    if (!IS_NL(r) || !IS_LT(r + 16) || !IS_FUNCTION(r + 32)) return 0;
    r += 48;
    if (!name_rows(&r, &o, &P->fn) || !IS_NL(r + 16)) return 0;
    r += 32;
    for (;;) {
        if (IS_LT(r)) {
            if (!IS_PARAMETER(r + 16) || np == MAXP) return 0;
            r += 32;
            if (!name_rows(&r, &o, &P->k[np]) || !IS_NL(r + 16)) return 0;
            r += 32;
            u8 *vs = o;
            while (!(IS_NL(r) && IS_CL(r + 16))) {
                u32 n = copy_val(r, o);
                if (n == END || !n) return 0;
                o += n;
                r += 16;
            }
            P->v[np++] = (Span){vs, (u32)(o - vs)};
            if (!IS_PARAMETER(r + 32) || !IS_GT(r + 48) || !IS_NL(r + 64)) return 0;
            r += 80;
        } else if (IS_CL(r)) {
            if (!IS_FUNCTION(r + 16) || !IS_GT(r + 32) || !IS_NL(r + 48) || r[64]) return 0;
            P->np = np;
            return 1;
        } else {
            return 0;
        }
    }
}
// The same answers as the loops over FN and PARAMS, by length and bytes. KEY_x index SLOT's second dimension.
#define EQ2(p, a, b) ((p)[0] == (a) && (p)[1] == (b))
#define EQ3(p, a, b, c) (EQ2(p, a, b) && (p)[2] == (c))
#define EQ4(p, a, b, c, d) (EQ3(p, a, b, c) && (p)[3] == (d))
static u32 fn_index(Span s) {
    const u8 *p = s.p;
    switch (s.n) {
    case 4:
        if (EQ4(p, 'f', 'i', 'n', 'd')) return 0;
        if (EQ4(p, 'p', 'a', 't', 'h')) return 4;
        if (EQ4(p, 'l', 'i', 'n', 'k')) return 8;
        break;
    case 5:
        if (EQ4(p, 'c', 'h', 'a', 's') && p[4] == 'e') return 2;
        if (EQ4(p, 'c', 'l', 'o', 's') && p[4] == 'e') return 6;
        break;
    case 6:
        if (EQ4(p, 'f', 'o', 'l', 'l') && EQ2(p + 4, 'o', 'w')) return 1;
        if (EQ4(p, 'r', 'e', 'o', 'p') && EQ2(p + 4, 'e', 'n')) return 7;
        if (EQ4(p, 'u', 'n', 'l', 'i') && EQ2(p + 4, 'n', 'k')) return 9;
        break;
    case 8:
        if (EQ4(p, 'c', 'h', 'e', 'a') && EQ4(p + 4, 'p', 'e', 's', 't')) return 5;
        if (EQ4(p, 'a', 'd', 'd', '_') && EQ4(p + 4, 'n', 'o', 'd', 'e')) return 10;
        break;
    case 10:
        if (EQ4(p, 'n', 'e', 'i', 'g') && EQ4(p + 4, 'h', 'b', 'o', 'u') && EQ2(p + 8, 'r', 's')) return 3;
        break;
    }
    return NFN;
}
enum { K_NAME, K_HAS, K_NODE, K_RELATION, K_STEPS, K_START, K_LEGS, K_DIRECTION, K_FRM, K_TO, K_WEIGHT, K_CLOSED, K_REOPENED, NKEY };
static const u8 SLOT[NFN][NKEY] = {  // PARAMS as a table: the parameter's position, 15 when the function has no such key
    {0, 1, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15},  {15, 15, 0, 1, 2, 15, 15, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 15, 15, 0, 1, 15, 15, 15, 15, 2, 3},    {15, 15, 0, 1, 15, 15, 15, 2, 15, 15, 15, 15, 15},
    {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15, 15, 15},  {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15, 15, 15},
    {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15}, {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 3, 15, 15},    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 15, 15, 15},
    {0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15}};
static u32 key_index(Span s) {
    const u8 *p = s.p;
    switch (s.n) {
    case 2: if (EQ2(p, 't', 'o')) return K_TO; break;
    case 3:
        if (EQ3(p, 'h', 'a', 's')) return K_HAS;
        if (EQ3(p, 'f', 'r', 'm')) return K_FRM;
        break;
    case 4:
        if (EQ4(p, 'n', 'o', 'd', 'e')) return K_NODE;
        if (EQ4(p, 'n', 'a', 'm', 'e')) return K_NAME;
        if (EQ4(p, 'f', 'r', 'o', 'm')) return K_FRM;
        if (EQ4(p, 'l', 'e', 'g', 's')) return K_LEGS;
        break;
    case 5:
        if (EQ4(p, 's', 't', 'e', 'p') && p[4] == 's') return K_STEPS;
        if (EQ4(p, 's', 't', 'a', 'r') && p[4] == 't') return K_START;
        break;
    case 6:
        if (EQ4(p, 'w', 'e', 'i', 'g') && EQ2(p + 4, 'h', 't')) return K_WEIGHT;
        if (EQ4(p, 'c', 'l', 'o', 's') && EQ2(p + 4, 'e', 'd')) return K_CLOSED;
        break;
    case 8:
        if (EQ4(p, 'r', 'e', 'l', 'a') && EQ4(p + 4, 't', 'i', 'o', 'n')) return K_RELATION;
        if (EQ4(p, 'r', 'e', 'o', 'p') && EQ4(p + 4, 'e', 'n', 'e', 'd')) return K_REOPENED;
        break;
    case 9: if (EQ4(p, 'd', 'i', 'r', 'e') && EQ4(p + 4, 'c', 't', 'i', 'o') && p[8] == 'n') return K_DIRECTION; break;
    }
    return NKEY;
}
#endif

#ifndef BRIDGE
static Span field(u32 *pos) {
    u32 b = *pos, i = b;
    while (i < TEXT_LEN && TEXT[i]) i++;
    *pos = i + 1;
    return (Span){TEXT + b, i - b};
}
#endif

static void dispatch(u32 f, u32 got, Span *v);
static void call(void) {
#if defined(BRIDGE) && !defined(FW_NO_PARSE)
    Parsed P;
    if (fast_parse(&P)) {
        u32 f = fn_index(P.fn), got = 0;
        if (f == NFN) { put_s("NOFUNCTION "); put_span(P.fn.p, P.fn.n); return; }
        Span v[MAXARGS];
        for (u32 j = 0; j < P.np; j++) {
            u32 kid = key_index(P.k[j]), i = kid == NKEY ? 15 : SLOT[f][kid];
            if (i == 15) { put_s("BADARG "); put_s(FN[f]); return; }
            v[i] = P.v[j];
            got |= 1u << i;
        }
        if ((got & REQUIRED[f]) != REQUIRED[f]) { put_s("BADARG "); put_s(FN[f]); return; }
        dispatch(f, got, v);
        return;
    }
#endif
#ifdef BRIDGE
    u32 full = 0;
    if (!gather(&full)) { put_s("TOOLONG"); return; }
    Span fn = {cb, 0};  // no <function=...> answers NOFUNCTION with an empty name
    cpos = cend = cn;
    for (u32 i = 0; i < cn; i++) {
        u32 a;
        if (cb[i] == '<' && named_at(i, "<function=", cn, &fn, &a)) { cpos = a; break; }
    }
    u32 e = find_lit(cpos, "</function>", cn);
    if (e != END) cend = e;
    else if (full) { put_s("TOOLONG"); return; }
#else
    u32 pos = 0;
    Span fn = field(&pos);
#endif
    u32 f = 0;
    while (f < NFN && !eq_lit(fn, FN[f])) f++;
    if (f == NFN) { put_s("NOFUNCTION "); put_span(fn.p, fn.n); return; }
    Span v[MAXARGS];
    u32 got = 0;
    for (;;) {
#ifdef BRIDGE
        Span k, val;
        if (!next_param(&k, &val)) break;
#else
        Span k = field(&pos);
        if (!k.n) break;
        Span val = field(&pos);
#endif
        if (eq_lit(k, "from")) k = (Span){(const u8 *)"frm", 3};
        u32 i = 0;
        while (i < MAXARGS && !(PARAMS[f][i] && eq_lit(k, PARAMS[f][i]))) i++;
        if (i == MAXARGS) { put_s("BADARG "); put_s(FN[f]); return; }
        v[i] = val;
        got |= 1u << i;
    }
    if ((got & REQUIRED[f]) != REQUIRED[f]) { put_s("BADARG "); put_s(FN[f]); return; }
    dispatch(f, got, v);
}
static void dispatch(u32 f, u32 got, Span *v) {
    switch (f) {
    case 0: f_find(v[0], got >> 1 & 1, v[1]); break;
    case 1: f_follow(v[0], v[1], v[2]); break;
    case 2: w_got = got; w_v = v; f_chase(v[0], v[1]); break;
    case 3: f_neighbours(v[0], v[1], got >> 2 & 1, v[2]); break;
    case 4: f_path(v[0], v[1]); break;
    case 5: f_cheapest(v[0], v[1]); break;
    case 6: f_close(v[0]); break;
    case 7: f_reopen(v[0]); break;
    case 8: f_link(v[0], v[1], v[2], got >> 3 & 1, v[3]); break;
    case 9: f_unlink(v[0], v[1], v[2]); break;
    default: f_add_node(v[0]); break;
    }
}

static void init(void) {
    if (HDR[0] != 0x30313258u) { put_s("BOOT"); return; }
    N = HDR[1]; R = HDR[2]; CHANGE = HDR[3]; FLAGS = HDR[4]; NSPLICE = HDR[5];
    BN = HDR[1];
    RELDIR = (const u32 *)(BOOTB + HDR[7]);
    RELNAMES = BOOTB + HDR[8];
    SPLICE = BOOTB + HDR[9];
    RELHASH = BOOTB + HDR[10];
#ifdef NO_GRAPH_OPS
    LABOFF = (const u32 *)(BOOTB + HDR[11]);
    LABDATA = BOOTB + HDR[12];
    BUCKET = (const u16 *)(BOOTB + HDR[13]);
    LNEXT = (const u16 *)(BOOTB + HDR[14]);
    OFF_[0] = (const u16 *)(BOOTB + HDR[15]);
    ENT_[0] = (const u32 *)(BOOTB + HDR[16]);
    W_[0] = (const u16 *)(BOOTB + HDR[17]);
    OFF_[1] = (const u16 *)(BOOTB + HDR[18]);
    ENT_[1] = (const u32 *)(BOOTB + HDR[19]);
    W_[1] = (const u16 *)(BOOTB + HDR[20]);
    if (N > MAXN) put_s("BOOT N");
#endif
}

int main(void) {
    init();
    for (;;) {
        rv_ecall2(93, 0, 0, 0);  // park; the next GO resumes here with a call in the text buffer
#ifdef BRIDGE
        // \n<tool_response>\nRESULT\n</tool_response>\n<think>\n\n</think>\n, and the bridge echoes HALT as \n.
        // The bridge's printable tokens are the bytes and these four specials (bridge.SPECIALS), so <|im_end|> and
        // <|im_start|> cannot be printed: the template's turn markers are newlines here, as in env/calc.
        enum { TOOL_RESPONSE = 256, TOOL_RESPONSE_END, THINK, THINK_END };
#ifdef FW_ONELINE  // item 4's measurement only: the result and nothing around it. Changes the response, so never the default.
        call();
#else
        put('\n'); put(TOOL_RESPONSE); put('\n');
        call();
        put('\n'); put(TOOL_RESPONSE_END); put('\n');
        put(THINK); put('\n'); put('\n'); put(THINK_END); put('\n');
#endif
#else
        call();
#endif
    }
}
// T8, the strict cleaner (SPEC 4). Runs only after a name has matched nothing. HDR[27]: noun length, bit 16 = the graph has the field. noinline, so a call that matches costs what it did.
static __attribute__((noinline)) Span clean_tail(Span s) {
    for (;;) {
        if (!s.n) return s;
        u32 c = s.p[s.n - 1], k;
        if (c == '.' || c == ',' || c == ';' || c == ':' || c == '!' || c == '?') { s.n--; continue; }
        if (!(k = ws_end(s.p, s.n))) return s;
        s.n -= k;
    }
}
// how many nodes this name means, and one of them: node() (rp = 0), or f_reopen's rule (rp = 1, the closed ones, or failing that all of them)
static __attribute__((noinline)) u32 clean_try(Span c, u32 has, u32 rp, u32 *h) {
    u32 hs = ghash(c.p, c.n), k = 0, every = 0, e0 = END;
    for (u32 x = bk_first(hs); x != END; x = bk_next(x))
        if (label_eq(x, c)) {
            if (rp) {
                if (is_closed(x)) { if (!k++) *h = x; }
                else if (!every++) e0 = x;
            } else if (!is_closed(x) && (has == END || eff_any(x, has, 0))) { if (!k++) *h = x; }
        }
    if (rp && !k) { k = every; *h = e0; }
    return k;
}
static u32 __attribute__((noinline)) read_name(Span a, u32 has, u32 rp) {  // the handle, its line printed; or END
    if (!(HDR[27] >> 16)) return END;
    u32 h = END, k = 0, L = HDR[27] & 0xFFFFu;
    Span c = clean_tail(a);
    if (c.n && c.n != a.n) k = clean_try(c, has, rp, &h);
    if (!k && L && c.n > L && ws_end(c.p, c.n - L)) {
        const u8 *n = BOOTB + HDR[26], *w = c.p + c.n - L;
        u32 i = 0;
        while (i < L && n[i] == w[i]) i++;
        if (i == L) {
            Span d = clean_tail((Span){c.p, c.n - L});
            if (d.n) k = clean_try(d, has, rp, &h);
        }
    }
    if (k != 1) return END;
    put_s("name read as "); put_fmt(h); put_s("\n");
    return h;
}
static void stop_multi(u32 k) { put_s(", there are "); put_num(k); put_s(" possible next steps, so the way on isn't unique. The journey did not finish."); }
static void stop_walk(u32 leg, u32 k, u32 h, u32 s) {  // SPEC 3: k = 0 no edge, otherwise several
    if (leg) { put_s("Stopped early on leg "); put_num(leg); put_s(": after "); }
    else put_s("Stopped early: after ");
    put_num(s); put_s(" steps at "); put_fmt(h);
    if (!k) put_s(", no further step along this relation exists. The journey did not finish.");
    else stop_multi(k);
}
static void stop_change(u32 leg, u32 cnt, u32 h) {
    put_s("Stopped early on leg "); put_num(leg);
    if (!cnt) { put_s(": at "); put_fmt(h); put_s(", no change leads to that leg's relation. The journey did not finish."); return; }
    put_s(": after 0 steps at "); put_fmt(h); stop_multi(cnt);
}
static int reopen_none(Span a, u32 *hp) {  // 1: read, the handle in *hp
    u32 h;
    Span lab;
    if (parse_handle(a, &h, &lab) || (h = read_name(a, END, 1)) == END) return 0;
    *hp = h;
    return 1;
}

// SPEC 3: chase with writes. closed, then reopened, each stated on a line; NONE or AMBIGUOUS ends the call.
static int write_list(Span s, u32 rp) {
    for (u32 i = 0, b = 0; i <= s.n; i++)
        if (i == s.n || s.p[i] == ';') {
            Span p = trim((Span){s.p + b, i - b});
            b = i + 1;
            if (!p.n) continue;
            if (rp) {
                w_bad = 0;
                f_reopen(p);
                if (w_bad) return 0;
            } else {
                u32 h = node_arg(p, END);
                if (h == NODE_ERR) return 0;
                if (h & NODE_CLOSED) { put_s("already closed "); put_fmt(h & ~NODE_CLOSED); }
                else {
                    set_alive(h, 0);
                    n_closed++;
                    put_s("closed "); put_fmt(h);
                }
            }
            put_s("\n");
        }
    return 1;
}
static int chase_writes(void) {
    if (w_got >> 2 & 1 && !write_list(w_v[2], 0)) return 0;
    if (w_got >> 3 & 1 && !write_list(w_v[3], 1)) return 0;
    return 1;
}
