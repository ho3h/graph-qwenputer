#!/usr/bin/env python3
"""Writes t8/fw/build/graphlib.c and tok_lits.h: fw/graphlib.c with the strict cleaner patched in, through tok/gen_fw.py as it stands (read, not edited). Prints the hashes of every input.

    python t8/fw/gen.py
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay  # noqa: E402,F401  (first)

X210, TOK = overlay.X210, overlay.TOK
WRITES = os.environ.get("T8_WRITES") == "1"                        # the `writes` firmware: chase with closed and reopened (SPEC 3). clean.elf is built without this.
R1 = os.environ.get("T8_R1") == "1"                                # exam/R1.md: a start name several nodes share is narrowed by the first leg's relation
R2 = os.environ.get("T8_R2") == "1"                                # exam/AFTER.md P: add_node
R6 = os.environ.get("T8_R6") == "1"                                # exam/AFTER.md r6: a closed stop blocks; routes around it keep the tight loop; needs T8_R5
R5 = os.environ.get("T8_R5") == "1"                                # exam/AFTER.md r5: edited stops read their edges once; needs T8_R4
R4 = os.environ.get("T8_R4") == "1"                                # exam/AFTER.md r4: path_tight after writes; needs T8_R3
R3 = os.environ.get("T8_R3") == "1"                                # exam/AFTER.md r3: untouched nodes keep the fast iterator after a write; needs T8_R2
BUILD = os.path.join(HERE, "build_r6" if R6 else "build_r5" if R5 else "build_r4" if R4 else "build_r3" if R3 else "build_r2" if R2 else "build_r1" if R1 else "build_writes" if WRITES else "build")
src = open(os.path.join(X210, "fw", "graphlib.c")).read()

CLEANER = r'''// T8, the strict cleaner (SPEC 4). Runs only after a name has matched nothing. HDR[27]: noun length, bit 16 = the graph has the field. noinline, so a call that matches costs what it did.
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
'''
# The cleaner goes after main, so every other routine keeps its place, and its literals come last. The two NONE lines stay where they are, with a call in front.
DECL = "static u32 read_name(Span a, u32 has, u32 rp);\nstatic int reopen_none(Span a, u32 *hp);\n"
PATCHES = [("static u32 node_arg(Span a, u32 has) {", DECL + "static u32 node_arg(Span a, u32 has) {"),
           ('    if (!k) { put_s("NONE "); put_span(a.p, a.n); return NODE_ERR; }\n    if (k == 1) return first;', '    if (!k) { if ((first = read_name(a, has, 0)) != END) return first; put_s("NONE "); put_span(a.p, a.n); return NODE_ERR; }\n    if (k == 1) return first;'),
           ('    if (!k) { put_s("NONE "); put_span(a.p, a.n); return; }\n    if (!is_closed(h))', '    if (!k) { if (reopen_none(a, &h)) k = 1; else { put_s("NONE "); put_span(a.p, a.n); return; } }\n    if (!is_closed(h))')]
if WRITES:
    PATCHES += [('{"start", "legs", 0, 0},', '{"start", "legs", "closed", "reopened"},'),
                ("    case 2: f_chase(v[0], v[1]); break;", "    case 2: w_got = got; w_v = v; f_chase(v[0], v[1]); break;"),
                ("    u32 h = node_or_print(start);\n    if (h == END) return;\n    for (u32 i = 0; i < np; i++) {\n        u32 r = lr[i];", "    if (w_got >> 2 && !chase_writes()) return;\n    u32 h = node_or_print(start);\n    if (h == END) return;\n    for (u32 i = 0; i < np; i++) {\n        u32 r = lr[i];"),
                ("static u32 node_arg(Span a, u32 has);", "static u32 node_arg(Span a, u32 has);") if False else ("static void f_find(Span name, int has_given, Span has) {", "static u32 w_got, w_bad;\nstatic Span *w_v;\nstatic int chase_writes(void);\nstatic void f_find(Span name, int has_given, Span has) {"),
                ('''            put_s("AMBIGUOUS "); put_num(k); put_s(": ");
            u32 i = 0;
            for (u32 x = bk_first(hs); x != END; x = bk_next(x))
                if (label_eq(x, a) && (!only_closed''', '''            w_bad = 1; put_s("AMBIGUOUS "); put_num(k); put_s(": ");
            u32 i = 0;
            for (u32 x = bk_first(hs); x != END; x = bk_next(x))
                if (label_eq(x, a) && (!only_closed'''),
                ('if (reopen_none(a, &h)) k = 1; else { put_s("NONE ");', 'if (reopen_none(a, &h)) k = 1; else { w_bad = 1; put_s("NONE ");')]
    PATCHES += [("K_FRM, K_TO, K_WEIGHT, NKEY };", "K_FRM, K_TO, K_WEIGHT, K_CLOSED, K_REOPENED, NKEY };"),
                ("""    {0, 1, 15, 15, 15, 15, 15, 15, 15, 15, 15},  {15, 15, 0, 1, 2, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 15, 15, 0, 1, 15, 15, 15, 15},  {15, 15, 0, 1, 15, 15, 15, 2, 15, 15, 15},
    {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15},  {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15},
    {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15}, {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 3},    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 15}};""",
                 """    {0, 1, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15},  {15, 15, 0, 1, 2, 15, 15, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 15, 15, 0, 1, 15, 15, 15, 15, 2, 3},    {15, 15, 0, 1, 15, 15, 15, 2, 15, 15, 15, 15, 15},
    {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15, 15, 15},  {15, 15, 15, 15, 15, 15, 15, 15, 0, 1, 15, 15, 15},
    {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15}, {15, 15, 0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15},
    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 3, 15, 15},    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 15, 15, 15}};"""),
                ("    case 6: if (EQ4(p, 'w', 'e', 'i', 'g') && EQ2(p + 4, 'h', 't')) return K_WEIGHT; break;", "    case 6:\n        if (EQ4(p, 'w', 'e', 'i', 'g') && EQ2(p + 4, 'h', 't')) return K_WEIGHT;\n        if (EQ4(p, 'c', 'l', 'o', 's') && EQ2(p + 4, 'e', 'd')) return K_CLOSED;\n        break;"),
                ("    case 8: if (EQ4(p, 'r', 'e', 'l', 'a') && EQ4(p + 4, 't', 'i', 'o', 'n')) return K_RELATION; break;", "    case 8:\n        if (EQ4(p, 'r', 'e', 'l', 'a') && EQ4(p + 4, 't', 'i', 'o', 'n')) return K_RELATION;\n        if (EQ4(p, 'r', 'e', 'o', 'p') && EQ4(p + 4, 'e', 'n', 'e', 'd')) return K_REOPENED;\n        break;")]
    CLEANER += r'''
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
'''
# The limit lines (SPEC 3): printed from after main too.
STOPDECL = "static void stop_walk(u32 leg, u32 k, u32 h, u32 s);\nstatic void stop_change(u32 leg, u32 cnt, u32 h);\n"
PATCHES += [("static int walk(u32 *hp, u32 r, u32 n, u32 leg) {", STOPDECL + "static int walk(u32 *hp, u32 r, u32 n, u32 leg) {"),
            ('''            if (leg) { put_s("leg "); put_num(leg); put_s(": "); }
            if (!k) put_s("END at ");
            else { put_s("MULTI "); put_num(k); put_s(" at "); }
            put_fmt(h); put_s(" after "); put_num(s); put_s(" steps");
            return 0;''', "            stop_walk(leg, k, h, s);\n            return 0;"),
            ('''            if (!cnt) { put_s("leg "); put_num(i + 1); put_s(": NOCHANGE at "); put_fmt(h); return; }
            if (cnt > 1) {
                put_s("leg "); put_num(i + 1); put_s(": MULTI "); put_num(cnt); put_s(" at "); put_fmt(h);
                put_s(" after 0 steps");
                return;
            }''', "            if (cnt != 1) { stop_change(i + 1, cnt, h); return; }")]
if R1:
    PATCHES += [("    if (w_got >> 2 && !chase_writes()) return;\n    u32 h = node_or_print(start);", "    if (w_got >> 2 && !chase_writes()) return;\n    u32 h = chase_start(start, lr[0]);"),
                ("static u32 w_got, w_bad;\n", """// exam/R1.md: only when several open nodes share the name and exactly one has the first leg's relation. Everything else is node_or_print.
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
""")]
if R2:
    PATCHES += [("static inline u32 lab_len(u32 h) { return LABOFF[h + 1] - LABOFF[h]; }\nstatic inline u32 lab_byte(u32 h, u32 i) { return LABDATA[LABOFF[h] + i]; }",
                 """// exam/AFTER.md P: stops added at run time, held in RAM.
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
}"""),
                ("static inline u32 bk_first(u32 hs) { u32 v = BUCKET[hs]; return v == 0xFFFFu ? END : v; }\nstatic inline u32 bk_next(u32 h) { u32 v = LNEXT[h]; return v == 0xFFFFu ? END : v; }",
                 "static inline u32 bk_first(u32 hs) { u32 v = BUCKET[hs]; bk_hs = hs; return v == 0xFFFFu ? new_scan(0) : v; }\nstatic inline u32 bk_next(u32 h) { if (h >= BN) return new_scan(h - BN + 1); u32 v = LNEXT[h]; return v == 0xFFFFu ? new_scan(0) : v; }"),
                ("    u32 lo = 0, hi = N;\n", "    u32 lo = 0, hi = BN;\n"),
                ("    const u32 *ent = ENT_[d];\n    u32 e = OFF_[d][h + 1];\n    for (u32 i = OFF_[d][h]; i < e; i++) {", "    const u32 *ent = ENT_[d];\n    u32 e = h < BN ? OFF_[d][h + 1] : 0;\n    for (u32 i = h < BN ? OFF_[d][h] : 0; i < e; i++) {"),
                ("    it->i = OFF_[d][x]; it->e = OFF_[d][x + 1]; it->d = d; it->x = x; it->r = 0; it->gen = n_add | n_dead;", "    it->i = x < BN ? OFF_[d][x] : 0; it->e = x < BN ? OFF_[d][x + 1] : 0; it->d = d; it->x = x; it->r = 0; it->gen = n_add | n_dead | n_new;"),
                ("    const u8 *p = LABDATA + LABOFF[h], *e = LABDATA + LABOFF[h + 1];\n    while (p != e) put(*p++);", "    if (h >= BN) { for (u32 i = 0, n = new_len[h - BN]; i < n; i++) put(new_lab[h - BN][i]); return; }\n    const u8 *p = LABDATA + LABOFF[h], *e = LABDATA + LABOFF[h + 1];\n    while (p != e) put(*p++);"),
                ("    if (!(n_closed | n_add | n_dead)) { path_tight(a, b); return; }", "    if (!(n_closed | n_add | n_dead | n_new)) { path_tight(a, b); return; }"),
                ("    if (!(n_closed | n_add | n_dead) && cheapest_tight(a, b)) return;", "    if (!(n_closed | n_add | n_dead | n_new) && cheapest_tight(a, b)) return;"),
                ('static void f_unlink(Span from, Span rel, Span to) {', """static void put_s_sp(u32 h) { put_span((const u8 *)" ", 1); put_span(new_lab[h - BN], new_len[h - BN]); }
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
static void f_unlink(Span from, Span rel, Span to) {"""),
                ('"link", "unlink"};', '"link", "unlink", "add_node"};'),
                ('{"frm", "relation", "to", 0}};', '{"frm", "relation", "to", 0},                      {"name", 0, 0, 0}};'),
                ("static const u8 REQUIRED[NFN] = {1, 7, 3, 3, 3, 3, 1, 1, 7, 7};", "static const u8 REQUIRED[NFN] = {1, 7, 3, 3, 3, 3, 1, 1, 7, 7, 1};"),
                ("    default: f_unlink(v[0], v[1], v[2]); break;", "    case 9: f_unlink(v[0], v[1], v[2]); break;\n    default: f_add_node(v[0]); break;"),
                ("    RELDIR = (const u32 *)(BOOTB + HDR[7]);", "    BN = HDR[1];\n    RELDIR = (const u32 *)(BOOTB + HDR[7]);"),
                ("static void f_path(Span from, Span to) {\n    u32 a = node_or_print(from);\n    if (a == END) return;\n    u32 b = node_or_print(to);\n    if (b == END) return;\n", """// exam/AFTER.md P: a shared name whose open nodes are all joined by the change relation is one station.
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
"""),
                ("static void f_close(Span node) {\n    u32 h = node_arg(node, END);", """static void f_close(Span node) {
    u16 o[8];
    u32 m = station_nodes(node, o);
    if (m) {
        put_s("closed ");
        for (u32 i = 0; i < m; i++) { set_alive(o[i], 0); n_closed++; if (i) put_s(" | "); put_fmt(o[i]); }
        return;
    }
    u32 h = node_arg(node, END);"""),
                ("        if (k > 1) {\n            w_bad = 1; put_s(\"AMBIGUOUS \"); put_num(k); put_s(\": \");", """        if (k > 1) {
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
            w_bad = 1; put_s("AMBIGUOUS "); put_num(k); put_s(": ");"""),
                ("#define NFN 10\n", "#define NFN 11\n"),
                ("        if (EQ4(p, 'c', 'h', 'e', 'a') && EQ4(p + 4, 'p', 'e', 's', 't')) return 5;\n", "        if (EQ4(p, 'c', 'h', 'e', 'a') && EQ4(p + 4, 'p', 'e', 's', 't')) return 5;\n        if (EQ4(p, 'a', 'd', 'd', '_') && EQ4(p + 4, 'n', 'o', 'd', 'e')) return 10;\n"),
                ("    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 3, 15, 15},    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 15, 15, 15}};", "    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 3, 15, 15},    {15, 15, 15, 1, 15, 15, 15, 15, 0, 2, 15, 15, 15},\n    {0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15}};")]
if R3:
    assert R2
    PATCHES += [("static u32 n_add, n_dead;\n", "static u32 n_add, n_dead;\nstatic u32 touched_[2][MW];  // exam/AFTER.md r3: nodes with added or dead edges, by direction\n"),
                ("    return n_add ? ov_scan(0, node_of(i, d), r, d) : END;", "    if (!n_add) return END;\n    u32 h_ = node_of(i, d);\n    return BIT(touched_[d], h_) ? ov_scan(0, h_, r, d) : END;"),
                ("it->d = d; it->x = x; it->r = 0; it->gen = n_add | n_dead | n_new;", "it->d = d; it->x = x; it->r = 0; it->gen = x >= BN || ((n_add | n_dead) && BIT(touched_[d], x));"),
                ("    n_add++;\n#else\n    if (g_add(", "    n_add++;\n    SETB(touched_[0], a); SETB(touched_[1], b);\n#else\n    if (g_add("),
                ("        SETB(dead_[0], i);\n        SETB(dead_[1], j);\n", "        SETB(dead_[0], i);\n        SETB(dead_[1], j);\n        SETB(touched_[0], a); SETB(touched_[1], b);\n")]
if R4:
    assert R3
    PATCHES += [("""        u32 x = wk.q[qh++], dy = scratch[x] + 1u;
        for (u32 i = off[x], e = off[x + 1]; i < e; i++) {
            u32 y = ent[i] & 0xFFFu;
            if (BIT(mark, y)) continue;
            SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y;
            if (y == b) { D = dy; break; }
        }
""", """        u32 x = wk.q[qh++], dy = scratch[x] + 1u;
        if (x >= BN || BIT(touched_[0], x)) {  // exam/AFTER.md r4: only an edited stop takes the general iterator
            RIt it;
            rit_init(&it, x, 0);
            while (!D && rit_next(&it)) {
                EACH_TARGET(it.rr, 0, it.c, y, if (!D && !BIT(mark, y)) { SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y; if (y == b) D = dy; })
            }
            continue;
        }
        for (u32 i = off[x], e = off[x + 1]; i < e; i++) {
            u32 y = ent[i] & 0xFFFu;
            if (BIT(mark, y)) continue;
            SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y;
            if (y == b) { D = dy; break; }
        }
"""),
                ("""        u32 best = END;
        for (u32 i = ioff[y], e = ioff[y + 1]; i < e; i++) {
            u32 x = ient[i] & 0xFFFu;
            if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;
        }
""", """        u32 best = END;
        if (y >= BN || BIT(touched_[1], y)) {
            RIt it;
            rit_init(&it, y, 1);
            while (rit_next(&it)) {
                EACH_TARGET(it.rr, 1, it.c, x, if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;)
            }
        } else
        for (u32 i = ioff[y], e = ioff[y + 1]; i < e; i++) {
            u32 x = ient[i] & 0xFFFu;
            if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;
        }
"""),
                ("    if (!(n_closed | n_add | n_dead | n_new)) { path_tight(a, b); return; }", "    if (!n_closed) { path_tight(a, b); return; }")]
if R5:
    assert R4
    PATCHES += [("""            RIt it;
            rit_init(&it, x, 0);
            while (!D && rit_next(&it)) {
                EACH_TARGET(it.rr, 0, it.c, y, if (!D && !BIT(mark, y)) { SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y; if (y == b) D = dy; })
            }
            continue;
""", """            if (x < BN)  // exam/AFTER.md r5: live base edges once, then the added list once
                for (u32 i = off[x], e = off[x + 1]; i < e && !D; i++) {
                    if (n_dead && BIT(dead_[0], i)) continue;
                    u32 y = ent[i] & 0xFFFu;
                    if (BIT(mark, y)) continue;
                    SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y;
                    if (y == b) D = dy;
                }
            for (u32 j = 0; j < n_add && !D; j++) {
                if (add_a[j] != x) continue;
                u32 y = add_b[j];
                if (BIT(mark, y)) continue;
                SETB(mark, y); scratch[y] = (u16)dy; wk.q[qt++] = (u16)y;
                if (y == b) D = dy;
            }
            continue;
"""),
                ("""            RIt it;
            rit_init(&it, y, 1);
            while (rit_next(&it)) {
                EACH_TARGET(it.rr, 1, it.c, x, if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;)
            }
""", """            if (y < BN)
                for (u32 i = ioff[y], e = ioff[y + 1]; i < e; i++) {
                    if (n_dead && BIT(dead_[1], i)) continue;
                    u32 x = ient[i] & 0xFFFu;
                    if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;
                }
            for (u32 j = 0; j < n_add; j++) {
                if (add_b[j] != y) continue;
                u32 x = add_a[j];
                if (x < best && BIT(mark, x) && scratch[x] == k - 1) best = x;
            }
""")]
if R6:
    assert R5
    PATCHES += [("""    clear_bits(mark);
    SETB(mark, a); scratch[a] = 0; wk.q[qt++] = (u16)a;
    while (qh < qt && !D) {
        u32 x = wk.q[qh++], dy = scratch[x] + 1u;
        if (x >= BN""", """    clear_bits(mark);
    if (n_closed)  // exam/AFTER.md r6: a closed stop is a wall, so the search never enters it
        for (u32 w_ = 0, nw_ = (N + 31) >> 5; w_ < nw_; w_++) mark[w_] = closed_bits[w_];
    SETB(mark, a); scratch[a] = 0; wk.q[qt++] = (u16)a;
    while (qh < qt && !D) {
        u32 x = wk.q[qh++], dy = scratch[x] + 1u;
        if (x >= BN"""),
                ("""    u32 y = b;
    w2[D] = (u16)b;
    for (u32 k = D; k > 0; k--) {
        u32 best = END;
        if (y >= BN""", """    if (n_closed)  // and the walk back can't pick one up from its stale distance
        for (u32 w_ = 0, nw_ = (N + 31) >> 5; w_ < nw_; w_++) mark[w_] &= ~closed_bits[w_];
    u32 y = b;
    w2[D] = (u16)b;
    for (u32 k = D; k > 0; k--) {
        u32 best = END;
        if (y >= BN"""),
                ("    if (!n_closed) { path_tight(a, b); return; }", "    if (!n_closed || !NSPLICE) { path_tight(a, b); return; }")]
for old, new in PATCHES:
    assert src.count(old) == 1, old
    src = src.replace(old, new)
src = src.rstrip() + "\n" + CLEANER
srcpath = os.path.join(BUILD, "graphlib_bytes.c")
os.makedirs(BUILD, exist_ok=True)
open(srcpath, "w").write(src)

gen = open(os.path.join(TOK, "gen_fw.py")).read()
for old, new in (('os.path.join(X210, "fw", "graphlib.c")', repr(srcpath)),
                 ('open(os.path.join(HERE, "graphlib.c"), "w")', f'open({os.path.join(BUILD, "graphlib.c")!r}, "w")'),
                 ('open(os.path.join(HERE, "tok_lits.h"), "w")', f'open({os.path.join(BUILD, "tok_lits.h")!r}, "w")')):
    assert gen.count(old) == 1, old
    gen = gen.replace(old, new)
if R2:                                                             # a new stop has no token table, so its name prints byte by byte
    old = "static void put_lab(u32 h) { put_run(LTOK + LTOKOFF[h], LTOK + LTOKOFF[h + 1]); }"
    assert gen.count(old) == 1
    gen = gen.replace(old, "static void put_lab(u32 h) { if (h >= BN) { put_s_sp(h); return; } put_run(LTOK + LTOKOFF[h], LTOK + LTOKOFF[h + 1]); }")
    old = "static void put_fmt(u32 h) {"
    assert gen.count(old) == 1
g = {"__file__": os.path.join(TOK, "gen_fw.py"), "__name__": "__main__"}
sys.modules["overlay"] = overlay.O                                 # gen_fw's `import overlay as O` means tok's, with the patched boot_tok already loaded
exec(compile(gen, g["__file__"], "exec"), g)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


print({os.path.relpath(p, X210): sha(p) for p in (os.path.join(X210, "fw", "graphlib.c"), os.path.join(TOK, "gen_fw.py"), os.path.join(TOK, "boot_tok.py"), os.path.join(TOK, "overlay.py"), os.path.join(TOK, "core.py"), os.path.join(TOK, "fragments.py"), os.path.join(BUILD, "graphlib.c"), os.path.join(BUILD, "tok_lits.h"))})
