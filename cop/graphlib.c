// X2.10 graph library (SPEC.md section 3) on the RV32IM core, with the graph coprocessor (COPROCESSOR.md v0,
// custom-2 ops through .insn) or, built with -DNO_GRAPH_OPS, the same algorithms on plain DROM/RAM arrays.
//
// Runs as a parked firmware: the first run initialises and parks (exit ecall); each later run (GO) reads one
// call from the text buffer at 0x8000, prints the exact result text with putchar, and parks again. RAM and the
// coprocessor state persist between calls, so close/reopen sequences work like the circuit's.
//
// Call format in the text buffer: fn NUL (key NUL value NUL)* NUL. Values are the argument strings, unchanged.
// The graph is boot data read at run time (DROM at 0x21000, see boot.py; graph-op build also the coprocessor).
#include "rt.h"

typedef unsigned int u32;
typedef int i32;
typedef unsigned short u16;
typedef unsigned char u8;

#define END 0xFFFFFFFFu
#define TEXT ((const u8 *)0x8000)
#define TEXT_LEN 2048u
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

static inline u32 lab_len(u32 h) { return LABOFF[h + 1] - LABOFF[h]; }
static inline u32 lab_byte(u32 h, u32 i) { return LABDATA[LABOFF[h] + i]; }
static inline u32 is_closed(u32 h) { return n_closed && BIT(closed_bits, h); }
static inline void set_alive(u32 h, u32 a) {
    if (a) CLRB(closed_bits, h); else SETB(closed_bits, h);
}
static inline u32 bk_first(u32 hs) { u32 v = BUCKET[hs]; return v == 0xFFFFu ? END : v; }
static inline u32 bk_next(u32 h) { u32 v = LNEXT[h]; return v == 0xFFFFu ? END : v; }
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
    u32 lo = 0, hi = N;
    while (hi - lo > 1) {
        u32 m = (lo + hi) >> 1;
        if (OFF_[d][m] <= i) lo = m; else hi = m;
    }
    return lo;
}
static u32 cur_first(u32 h, u32 r, u32 d) {
    const u32 *ent = ENT_[d];
    u32 e = OFF_[d][h + 1];
    for (u32 i = OFF_[d][h]; i < e; i++) {
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
    it->i = OFF_[d][x]; it->e = OFF_[d][x + 1]; it->d = d; it->x = x; it->r = 0; it->gen = n_add | n_dead;
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
static void put(u32 c) { rv_ecall2(1, c, 0, 0); }
static void put_s(const char *s) { while (*s) put((u8)*s++); }
static void put_span(const u8 *p, u32 n) { for (u32 i = 0; i < n; i++) put(p[i]); }
static void put_num(u32 v) {
    char b[11];
    int n = 0;
    do { b[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) put((u8)b[--n]);
}
static void put_lab(u32 h) { for (u32 i = 0, n = lab_len(h); i < n; i++) put(lab_byte(h, i)); }
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
static Span trim(Span s) {
    u32 k;
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
    if (!k) { put_s("NONE "); put_span(a.p, a.n); return NODE_ERR; }
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
static void f_find(Span name, int has_given, Span has) {
    u32 r = END;
    if (has_given && (r = rel_arg(has)) == END) return;
    u32 h = node_arg(name, r);
    if (h == NODE_ERR) return;
    if (h & NODE_CLOSED) { put_s("CLOSED "); put_fmt(h & ~NODE_CLOSED); return; }
    put_fmt(h);
}
// follow r n steps from *h; on END / MULTI prints the line (after prefix) and returns 0
static int walk(u32 *hp, u32 r, u32 n, u32 leg) {
    u32 h = *hp;
    for (u32 s = 0; s < n; s++) {
        u32 next = END, k = eff_count(r, cur_first(h, r, 0), &next);
        if (k != 1) {
            if (leg) { put_s("leg "); put_num(leg); put_s(": "); }
            if (!k) put_s("END at ");
            else { put_s("MULTI "); put_num(k); put_s(" at "); }
            put_fmt(h); put_s(" after "); put_num(s); put_s(" steps");
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
    u32 h = node_or_print(start);
    if (h == END) return;
    for (u32 i = 0; i < np; i++) {
        u32 r = lr[i];
        if (i && !eff_any(h, r, 0)) {
            u32 cnt = 0, first = END;
            if (CHANGE != END) {
                u32 cc = cur_first(h, CHANGE, 0);
                EACH_TARGET(CHANGE, 0, cc, y, if (eff_any(y, r, 0)) { if (!cnt++) first = y; })
            }
            if (!cnt) { put_s("leg "); put_num(i + 1); put_s(": NOCHANGE at "); put_fmt(h); return; }
            if (cnt > 1) {
                put_s("leg "); put_num(i + 1); put_s(": MULTI "); put_num(cnt); put_s(" at "); put_fmt(h);
                put_s(" after 0 steps");
                return;
            }
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

static void f_path(Span from, Span to) {
    u32 a = node_or_print(from);
    if (a == END) return;
    u32 b = node_or_print(to);
    if (b == END) return;
    if (a == b) { w2[0] = (u16)a; print_path(0); return; }
#ifndef NO_GRAPH_OPS
    if ((FLAGS & 1) && !(n_closed && NSPLICE) && path_expand(a, b)) return;
#endif
#ifdef NO_GRAPH_OPS
    if (!(n_closed | n_add | n_dead)) { path_tight(a, b); return; }
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
static void f_cheapest(Span from, Span to) {
    u32 a = node_or_print(from);
    if (a == END) return;
    u32 b = node_or_print(to);
    if (b == END) return;
    clear_bits(mark); clear_bits(done); clear_bits(over);
    Q = (Hq){wk.heap, 0, HEAPMAX, 0, END, mark, done};
    SETB(mark, a); best_set(a, 0); w2[a] = 0xFFFFu; hq_push(&Q, a);
    u32 key;
    while (hq_pop(&Q, &key)) {
        u32 x = key & 0xFFFu;
        if (BIT(done, x)) continue;
        SETB(done, x);
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
            put_s("AMBIGUOUS "); put_num(k); put_s(": ");
            u32 i = 0;
            for (u32 x = bk_first(hs); x != END; x = bk_next(x))
                if (label_eq(x, a) && (!only_closed || is_closed(x))) { if (i++) put_s(" | "); put_fmt(x); }
            return;
        }
    }
    if (!k) { put_s("NONE "); put_span(a.p, a.n); return; }
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
#define NFN 10
static const char *const FN[NFN] = {"find", "follow", "chase", "neighbours", "path", "cheapest", "close", "reopen",
                                    "link", "unlink"};
static const char *const PARAMS[NFN][MAXARGS] = {
    {"name", "has", 0, 0},  {"node", "relation", "steps", 0}, {"start", "legs", 0, 0},
    {"node", "relation", "direction", 0},                     {"frm", "to", 0, 0},
    {"frm", "to", 0, 0},    {"node", 0, 0, 0},                {"node", 0, 0, 0},
    {"frm", "relation", "to", "weight"},                      {"frm", "relation", "to", 0}};
static const u8 REQUIRED[NFN] = {1, 7, 3, 3, 3, 3, 1, 1, 7, 7};  // bit i: parameter i is required

static Span field(u32 *pos) {
    u32 b = *pos, i = b;
    while (i < TEXT_LEN && TEXT[i]) i++;
    *pos = i + 1;
    return (Span){TEXT + b, i - b};
}

static void call(void) {
    u32 pos = 0;
    Span fn = field(&pos);
    u32 f = 0;
    while (f < NFN && !eq_lit(fn, FN[f])) f++;
    if (f == NFN) { put_s("NOFUNCTION "); put_span(fn.p, fn.n); return; }
    Span v[MAXARGS];
    u32 got = 0;
    for (;;) {
        Span k = field(&pos);
        if (!k.n) break;
        Span val = field(&pos);
        if (eq_lit(k, "from")) k = (Span){(const u8 *)"frm", 3};
        u32 i = 0;
        while (i < MAXARGS && !(PARAMS[f][i] && eq_lit(k, PARAMS[f][i]))) i++;
        if (i == MAXARGS) { put_s("BADARG "); put_s(FN[f]); return; }
        v[i] = val;
        got |= 1u << i;
    }
    if ((got & REQUIRED[f]) != REQUIRED[f]) { put_s("BADARG "); put_s(FN[f]); return; }
    switch (f) {
    case 0: f_find(v[0], got >> 1 & 1, v[1]); break;
    case 1: f_follow(v[0], v[1], v[2]); break;
    case 2: f_chase(v[0], v[1]); break;
    case 3: f_neighbours(v[0], v[1], got >> 2 & 1, v[2]); break;
    case 4: f_path(v[0], v[1]); break;
    case 5: f_cheapest(v[0], v[1]); break;
    case 6: f_close(v[0]); break;
    case 7: f_reopen(v[0]); break;
    case 8: f_link(v[0], v[1], v[2], got >> 3 & 1, v[3]); break;
    default: f_unlink(v[0], v[1], v[2]); break;
    }
}

static void init(void) {
    if (HDR[0] != 0x30313258u) { put_s("BOOT"); return; }
    N = HDR[1]; R = HDR[2]; CHANGE = HDR[3]; FLAGS = HDR[4]; NSPLICE = HDR[5];
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
        call();
    }
}
