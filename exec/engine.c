/* The chip layers as a table interpreter: one token at a time, IEEE fp32, the bf16 rounding points of the HF model. compile_ir.py makes the tables. All buffers are owned by the Python caller;
   this file allocates nothing and every loop is bounded by a table size or the caller's max_steps.

   A level evaluates all its gates (or channels) with no per-expression branch, in runs of equal length, then visits only the positive ones. Touched residual dims are tracked, because x is always a
   bf16 value, so x + 0 changes nothing. */
#include <arm_neon.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#define HD 128
#define MAX_HEADS 32
#define MAX_TOUCH 16384

enum { F_GATE = 1, F_READ = 2, F_KEY = 4, F_Z = 8, F_CHAN = 16, F_DECAY = 32 };
enum { ST_TEXT = 0, ST_OWNER_OFF = 1, ST_MAX = 2, ST_MISS = 3, ST_DECODE = 4 };

typedef struct {
    int32_t D, n_mem, V, n_levels, n_keep, one, nfam, npay, vocab, text_token, n_printable, pad;
    float *mem, *y, *S, *val, *aup;
    const int32_t *levels, *buckets, *eptr; const uint16_t *tix; const float *tw, *ec;
    const int32_t *aexpr, *gstart, *ua; const float *ucoef; const int32_t *uout, *outs;
    const int32_t *zexpr, *lag_slot, *lag_dim, *fan_ptr, *fan_h, *fan_row;
    const int32_t *h_v, *h_always, *vh_a, *vh_beta, *vh_S, *vh_v, *vh_z, *v_col, *v_expr, *z_expr, *z_o, *o_col, *o_dim; const float *o_w;
    const int32_t *keep, *p_t, *p_a, *p_b; const float *p_r; int32_t *vh_nrows;
    /* token features: index = token for chip tokens, vocab + qwen id for text tokens; start < 0 means not filled */
    int32_t *f_start, *f_len; const uint16_t *f_dim; const float *f_val;
    const int32_t *fam_kind, *fam_base, *fam_size, *printable;   /* kind: 0 invalid, 1 control, 2 sized, 3 Q */
    uint32_t flags; int32_t miss_token; int64_t steps, units_on, reads, writes;
} Prog;

/* level record */
enum { L_KIND, L_A0, L_A1, L_G0, L_E0, L_NE, L_LAG0, L_LAG1, L_FAN0, L_NH, L_B0, L_B1, L_LV, L_P0, L_P1, L_O0, L_O1, L_WIDTH };
#define L_Z0 L_A0
#define L_Z1 L_A1
#define L_H0 L_G0

static inline float bf16r(float f) {                 /* nearest bf16 value, ties to even: as q35.ir.bf16 */
#ifdef NO_ROUNDING                                   /* a deliberately wrong build, for the negative control */
    return f;
#endif
    uint32_t u; memcpy(&u, &f, 4);
    u += 0x7FFF + ((u >> 16) & 1);
    u &= 0xFFFF0000u;
    memcpy(&f, &u, 4);
    return f;
}

static inline float eval_expr(const Prog *p, int32_t e) {
    const float *restrict mem = p->mem, *restrict tw = p->tw;
    const uint16_t *restrict tix = p->tix;
    int32_t a = p->eptr[e], b = p->eptr[e + 1];
    float s = p->ec[e];
    for (int32_t i = a; i < b; i++) s += tw[i] * mem[tix[i]];
    return s;
}

/* The level's shared sums: t = x_a + r x_b, in creation order. */
static inline void pairs(const Prog *p, const int32_t *L) {
    float *restrict mem = p->mem;
    const int32_t *restrict pt = p->p_t, *restrict pa = p->p_a, *restrict pb = p->p_b;
    const float *restrict pr = p->p_r;
    for (int32_t i = L[L_P0]; i < L[L_P1]; i++) mem[pt[i]] = mem[pa[i]] + pr[i] * mem[pb[i]];
}

#define TERM(j) w[j] * mem[ix[j]]
#define RUN(N, EXPR) for (int32_t e = e0; e < e1; e++, ix += (N), w += (N)) val[e] = ec[e] + (EXPR);

/* All forms of the level's runs of equal length. */
static inline void eval_runs(const Prog *p, const int32_t *L) {
    const float *restrict mem = p->mem, *restrict ec = p->ec;
    float *restrict val = p->val;
    for (int32_t b = L[L_B0]; b < L[L_B1]; b++) {
        const int32_t *B = p->buckets + 3 * b;
        int32_t n = B[0], e0 = B[1], e1 = B[2];
        int32_t t0 = p->eptr[e0];
        const uint16_t *restrict ix = p->tix + t0;
        const float *restrict w = p->tw + t0;
        switch (n) {
        case 0: for (int32_t e = e0; e < e1; e++) val[e] = ec[e]; break;
        case 1: RUN(1, TERM(0)) break;
        case 2: RUN(2, TERM(0) + TERM(1)) break;
        case 3: RUN(3, (TERM(0) + TERM(1)) + TERM(2)) break;
        case 4: RUN(4, (TERM(0) + TERM(1)) + (TERM(2) + TERM(3))) break;
        case 5: RUN(5, (TERM(0) + TERM(1)) + (TERM(2) + TERM(3)) + TERM(4)) break;
        case 6: RUN(6, (TERM(0) + TERM(1)) + (TERM(2) + TERM(3)) + (TERM(4) + TERM(5))) break;
        default:
            for (int32_t e = e0; e < e1; e++, ix += n, w += n) {
                float s = ec[e];
                for (int32_t j = 0; j < n; j++) s += TERM(j);
                val[e] = s;
            }
        }
    }
}

/* x = bf16(x + bf16(y)) on the dims written in this sublayer. A dim touched twice is settled the first time (y is 0 after), so duplicates are harmless; when there are more touches than the
   level has output dims, the level's list is shorter. */
static inline void apply_y(Prog *p, const int32_t *L, const int32_t *touched, int32_t nt) {
    float *restrict mem = p->mem, *restrict y = p->y;
    const int32_t *list = touched;
    int32_t n = nt;
    int32_t no = L[L_O1] - L[L_O0];
    if (nt > no) { list = p->outs + L[L_O0]; n = no; }
    for (int32_t i = 0; i < n; i++) {
        int32_t d = list[i];
        mem[d] = bf16r(mem[d] + bf16r(y[d]));
        y[d] = 0.f;
    }
}

static void ffn_level(Prog *p, const int32_t *L, int32_t *restrict touched) {
    float *restrict y = p->y, *restrict aup = p->aup;
    const float *restrict val = p->val;
    pairs(p, L);
    for (int32_t i = L[L_A0]; i < L[L_A1]; i++)     /* the up factor of each distinct a */
        aup[i] = bf16r(eval_expr(p, p->aexpr[i]) * 0.0078125f);
    eval_runs(p, L);
    int32_t e0 = L[L_E0], ne = L[L_NE], g0 = L[L_G0];
    const int32_t *restrict gstart = p->gstart, *restrict ua = p->ua, *restrict uout = p->uout;
    const float *restrict ucoef = p->ucoef;
    int64_t on = 0;
    int32_t nt = 0;
    const float32x4_t zero = vdupq_n_f32(0.f), lim = vdupq_n_f32(-0.8125f);
    uint32x4_t badneg = vdupq_n_u32(0);
    /* a gate is valid at 0, >= 18/128 or <= -104/128: anything else means silu is not relu, and is flagged */
    for (int32_t i = 0; i < ne; i += 4) {             /* val[] has spare room past the end */
        float32x4_t v = vld1q_f32(val + e0 + i);
        uint32x4_t pos = vcgtq_f32(v, zero);
        badneg = vorrq_u32(badneg, vandq_u32(vcgtq_f32(v, lim), vcltq_f32(v, zero)));
        if (vmaxvq_u32(pos) == 0) continue;
        for (int32_t k = 0; k < 4 && i + k < ne; k++) {
            float b = val[e0 + i + k];
            if (!(b > 0.f)) continue;
            float gk = bf16r(b * 128.f);
            if (gk < 18.f) p->flags |= F_GATE;
            int32_t g = g0 + i + k, u1 = gstart[g + 1];
            int32_t last = -1; float prod = 0.f;
            for (int32_t u = gstart[g]; u < u1; u++) {
                int32_t d = uout[u], a = ua[u];
                if (a != last) { last = a; prod = bf16r(gk * aup[a]); }
                y[d] += ucoef[u] * prod;
                touched[nt++] = d;
            }
            on += u1 - gstart[g];
        }
    }
    /* the tail of the last vector may read past ne: only flag from real entries */
    if (vmaxvq_u32(badneg)) {
        for (int32_t i = 0; i < ne; i++) { float b = val[e0 + i]; if (b < 0.f && b > -0.8125f) p->flags |= F_GATE; }
    }
    p->units_on += on;
#ifdef PROFILE
    { extern uint64_t chip_on[64], chip_nt[64]; int32_t l = (int32_t)((L - p->levels) / L_WIDTH); chip_on[l] += on; chip_nt[l] += nt; }
#endif
    apply_y(p, L, touched, nt);
}

static void head_level(Prog *p, const int32_t *L, int32_t *restrict touched) {
    float *restrict mem = p->mem, *restrict y = p->y, *restrict val = p->val;
    pairs(p, L);
    eval_runs(p, L);
    int32_t e0 = L[L_E0], ne = L[L_NE], f0 = L[L_FAN0], nh = L[L_NH], h0 = L[L_H0];
    int32_t kbest[MAX_HEADS], r0[MAX_HEADS], r1[MAX_HEADS], nk[MAX_HEADS], nq[MAX_HEADS];
    float kmax[MAX_HEADS], qm[MAX_HEADS];
    for (int32_t h = 0; h < nh; h++) { kbest[h] = -1; nk[h] = nq[h] = 0; kmax[h] = 0.f; }
    int anyq = 0;
    uint32_t bad = 0;
    const float32x4_t zero = vdupq_n_f32(0.f), hi = vdupq_n_f32(18.f), lo = vdupq_n_f32(-104.f);
    for (int32_t i = 0; i < ne; i += 4) {
        float32x4_t v = vld1q_f32(val + e0 + i);
        /* channels are valid at 0, >= 18 or <= -104 */
        uint32x4_t b = vandq_u32(vandq_u32(vcltq_f32(v, hi), vcgtq_f32(v, lo)), vmvnq_u32(vceqq_f32(v, zero)));
        bad |= vmaxvq_u32(b);
        if (vmaxvq_u32(vcgtq_f32(v, zero)) == 0) continue;
        for (int32_t k = 0; k < 4 && i + k < ne; k++) {
            float s = val[e0 + i + k];
            if (!(s > 0.f)) continue;
            int32_t c = f0 + i + k;
            for (int32_t f = p->fan_ptr[c]; f < p->fan_ptr[c + 1]; f++) {
                int32_t h = p->fan_h[f], rk = p->fan_row[f], row = rk & 0xFFFF;
                if (rk >> 16) {                       /* a key */
                    nk[h]++;
                    if (s > kmax[h]) { kmax[h] = s; kbest[h] = row; }
                } else {
                    if (nq[h] == 0) { r0[h] = row; qm[h] = s; }
                    else if (nq[h] == 1) { r1[h] = row; if (s != qm[h]) p->flags |= F_READ; }
                    else p->flags |= F_READ;
                    nq[h]++;
                    anyq = 1;
                }
            }
        }
    }
    if (bad) {
        for (int32_t i = 0; i < ne; i++) { float s = val[e0 + i]; if (s != 0.f && s < 18.f && s > -104.f) p->flags |= F_CHAN; }
    }
    if (anyq)                                         /* every distinct z of the level, once */
        for (int32_t i = L[L_Z0]; i < L[L_Z1]; i++) val[p->zexpr[i]] = eval_expr(p, p->zexpr[i]);
    int32_t nt = 0;
    for (int32_t hh = 0; hh < nh; hh++) {
        int32_t h = h0 + hh;
        if (kbest[hh] < 0 && nq[hh] == 0 && !p->h_always[h]) continue;
        if (nk[hh] > 1) p->flags |= F_KEY;
        for (int32_t vh = p->h_v[h]; vh < p->h_v[h + 1]; vh++) {
            float *restrict S = p->S + (int64_t)p->vh_S[vh] * HD * HD;
            if (p->vh_a[vh] >= 0) {
                float a = eval_expr(p, p->vh_a[vh]);
                if (a != 0.f) {                       /* only the rows its keys or its snapshot reach */
                    int32_t nc = p->vh_nrows[vh] * HD;
                    if (a == 110.f) { for (int32_t i = 0; i < nc; i++) S[i] *= 0.5f; }
                    else if (a == 238.f) memset(S, 0, sizeof(float) * nc);
                    else p->flags |= F_DECAY;
                }
            }
            if (kbest[hh] >= 0) {
                float beta = p->vh_beta[vh] >= 0 ? eval_expr(p, p->vh_beta[vh]) : 1.f;
                if (beta > 0.5f) {
                    float *row = S + (int64_t)kbest[hh] * HD;
                    memset(row, 0, sizeof(float) * HD);
                    for (int32_t i = p->vh_v[vh]; i < p->vh_v[vh + 1]; i++) {
                        float s = eval_expr(p, p->v_expr[i]);
                        if (s != 0.f && !(s >= 18.f) && !(s <= -104.f)) p->flags |= F_CHAN;
                        row[p->v_col[i]] = s > 0.f ? s : 0.f;
                    }
                    p->writes++;
                }
            }
            if (nq[hh]) {
                const float *ra = S + (int64_t)r0[hh] * HD;
                const float *rb = nq[hh] >= 2 ? S + (int64_t)r1[hh] * HD : NULL;
                float c0 = ra[0] + (rb ? rb[0] : 0.f), c1 = ra[1] + (rb ? rb[1] : 0.f);
                float ref = c0 * c0 + c1 * c1;
                if (ref > 0.f) {
                    float norm = sqrtf(ref / 128.f);
                    for (int32_t zg = p->vh_z[vh]; zg < p->vh_z[vh + 1]; zg++) {
                        float z = val[p->z_expr[zg]];
                        if (z <= 0.f) { if (z != 0.f && z > -104.f) p->flags |= F_Z; continue; }
                        if (z < 18.f) p->flags |= F_Z;
                        for (int32_t o = p->z_o[zg]; o < p->z_o[zg + 1]; o++) {
                            int32_t col = p->o_col[o], d = p->o_dim[o];
                            float v = rb ? ra[col] + rb[col] : ra[col];
                            y[d] += (v / norm) * z * p->o_w[o];
                            touched[nt++] = d;
                        }
                    }
                }
                p->reads++;
            }
        }
    }
    for (int32_t i = L[L_LAG0]; i < L[L_LAG1]; i++) { /* the lag windows move on: the input x becomes lag 1 */
        float *restrict w = mem + p->lag_slot[i];
        w[2] = w[1]; w[1] = w[0]; w[0] = mem[p->lag_dim[i]];
    }
    apply_y(p, L, touched, nt);
}

#ifdef PROFILE
uint64_t chip_prof[64], chip_on[64], chip_nt[64];
#endif

/* One token through every sublayer. Returns 0, or 1 if the token's features are not filled yet (nothing changed). */
int chip_step(Prog *p, int32_t tok) {
    int32_t ix = tok < p->vocab ? tok : p->vocab + (tok - p->text_token);
    int32_t st = p->f_start[ix];
    if (st < 0) { p->miss_token = tok; return 1; }
    float *mem = p->mem;
    memset(mem, 0, sizeof(float) * p->D);
    mem[p->one] = 1.f;
    for (int32_t i = 0, n = p->f_len[ix]; i < n; i++) mem[p->f_dim[st + i]] = p->f_val[st + i];
    int32_t touched[MAX_TOUCH];
    for (int32_t l = 0; l < p->n_levels; l++) {
        const int32_t *L = p->levels + L_WIDTH * l;
#ifdef PROFILE
        uint64_t t0 = __builtin_readcyclecounter();
#endif
        if (L[L_KIND] == 0) ffn_level(p, L, touched); else head_level(p, L, touched);
#ifdef PROFILE
        chip_prof[l] += __builtin_readcyclecounter() - t0;
#endif
    }
    p->steps++;
    return 0;
}

/* The circuit's next token from the kept code dims: -1 none (owner off), -2 a code that names no token. */
static int32_t next_token(const Prog *p) {
    const float *mem = p->mem;
    uint32_t bits = 0; int any = 0;
    int nb = p->nfam + p->npay;
    for (int i = 0; i < nb; i++) {
        float v = mem[p->keep[i]];
        if (v != 0.f) any = 1;
        if (v > 0.f) bits |= 1u << i;
    }
    if (!any) return -1;
    uint32_t fid = bits & ((1u << p->nfam) - 1), pay = bits >> p->nfam;
    switch (p->fam_kind[fid]) {
    case 1: return p->fam_base[fid];
    case 2: return (int32_t)pay < p->fam_size[fid] ? p->fam_base[fid] + (int32_t)pay : -2;
    case 3: return (int32_t)pay < p->n_printable && p->printable[pay] >= 0 ? p->text_token + p->printable[pay] : -2;
    default: return -2;
    }
}

int32_t chip_next(const Prog *p) { return next_token(p); }

/* Feed tokens, each next token decided by the circuit, until the next token is a text token, the circuit lets go, the code is bad, a feature is missing or max_steps is reached.
   On return *out_tok is the token that would be fed next (or -1 / -2), *out_n the steps taken; rec[i], if given, is the next token after step i. */
int chip_burst(Prog *p, int32_t tok, int64_t max_steps, int32_t *out_tok, int64_t *out_n, int32_t *rec) {
    int64_t n = 0;
    int32_t t = tok;
    int st = ST_MAX;
    while (n < max_steps) {
        if (chip_step(p, t)) { st = ST_MISS; break; }
        t = next_token(p);
        if (rec) rec[n] = t;
        n++;
        if (t == -1) { st = ST_OWNER_OFF; break; }
        if (t == -2) { st = ST_DECODE; break; }
        if (t >= p->vocab) { st = ST_TEXT; break; }
    }
    *out_tok = t; *out_n = n;
    return st;
}

/* A teacher-forced stretch: every token given; the kept dims of each position are written to keep_out (n x n_keep). Returns the count done (< n only on a missing feature). */
int64_t chip_run(Prog *p, const int32_t *toks, int64_t n, float *keep_out) {
    const float *mem = p->mem;
    for (int64_t i = 0; i < n; i++) {
        if (chip_step(p, toks[i])) return i;
        if (keep_out) for (int32_t k = 0; k < p->n_keep; k++) keep_out[i * p->n_keep + k] = mem[p->keep[k]];
    }
    return n;
}
