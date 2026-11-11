/* The chip layers of the merged checkpoint, run from the checkpoint's own tensors: HF's Qwen3_5DecoderLayer equations, one token at a time, in C.

   Not the circuit's IR and not exec/engine.c's tables: every number here is a weight read from the safetensors (wexec.py), and every step of the HF forward is
   done, in its order, with its bf16 rounding points. The only thing skipped is arithmetic whose result is known from zeros: a zero weight, a zero input, a value
   head with no weights, a unit whose gate is not positive. This is a different execution path from stock modules on MPS; it counts only where it is bit-equal with
   a saved stock trace.

   Built with -ffp-contract=off, no fast-math. */
#include <math.h>
#include <stdint.h>
#include <string.h>

#define HD 128
#define NK 16
#define NV 32
#define QKV (2 * NK * HD + NV * HD)   /* 8192 */
#define KEY_BASE (NK * HD)
#define V_BASE (2 * NK * HD)
#define MAX_D 4096
#define MAX_U 9216
#define EPS 1e-6f

#ifdef WPROF
uint64_t w_prof[16];
static inline uint64_t cyc(void) { uint64_t v; __asm__ volatile("mrs %0, cntvct_el0" : "=r"(v)); return v; }
#define T0 uint64_t t_ = cyc();
#define T(i) { uint64_t n_t = cyc(); w_prof[i] += n_t - t_; t_ = n_t; }
#else
#define T0
#define T(i)
#endif
enum { F_SILU = 1, F_SIG = 2, F_DECAY = 4, F_RESIDUE = 8 };

typedef struct {
    /* columns are chip dims minus d0 */
    int32_t *q_ptr, *q_row; float *q_w;      /* in_proj_qkv, by column */
    int32_t *z_ptr, *z_row; float *z_w;      /* in_proj_z, by column */
    int32_t *a_ptr, *a_row; float *a_w;
    int32_t *b_ptr, *b_row; float *b_w;
    int32_t *g_ptr, *g_row; float *g_w;      /* gate_proj, by column */
    int32_t *u_ptr, *u_col; float *u_w;      /* up_proj, by unit (row), column is chip dim minus d0 */
    int32_t *d_ptr, *d_dim; float *d_w;      /* down_proj, by unit (column), dim is the residual dim minus d0 */
    int32_t *o_ptr, *o_dim; float *o_w;      /* out_proj, by value column (vh * HD + col) */
    float *conv;                             /* [QKV][4], oldest first, as F.conv1d reads it */
    int32_t n_lag; int32_t *lag_row;         /* rows with a nonzero weight on an earlier position */
    float *hist;                             /* [QKV][3], oldest first */
    float *w_in, *w_post;                    /* 1 + weight of the two RMS norms, chip dims */
    float *w_norm;                           /* [HD] the gated norm's weight */
    float *A_exp, *dt_bias;                  /* [NV] exp(A_log) in fp32; dt_bias */
    int32_t *vh_active;                      /* [NV] */
    float *S;                                /* [NV][HD][HD] */
    int32_t *vh_nrows;                       /* [NV] */
    /* memo of the ballast's contribution: the ballast columns come first in each sum, so starting from their partial sums is the same arithmetic */
    float base_v;                            /* the normed ballast value the memo holds, 0 if none */
    int32_t base_nq, base_nz, base_ng;
    float *qb, *zb, *gb, *ab, *bb;           /* [QKV], [NV*HD], [MAX_U], [NV], [NV] */
    int32_t *qb_r, *zb_r, *gb_r;             /* the rows they touch */
} WLayer;

typedef struct {
    int32_t nL, d0, chip, n_keep, nfam, npay, vocab, text_token, n_printable, hidden;
    WLayer *L;
    float *x;                                 /* [chip] the residual's chip dims */
    int32_t *keep;                            /* chip dim of each kept value */
    int32_t *f_start, *f_len; uint16_t *f_dim; float *f_val; float *f_qsum;
    int32_t *fam_kind, *fam_base, *fam_size, *printable;
    uint32_t flags; int32_t miss_token; int64_t steps, residue, not_saturated, heads_run; int32_t ballast;
} WProg;

static inline float bf16(float v) {
    union { float f; uint32_t u; } a; a.f = v;
    uint32_t e = a.u & 0x7F800000u;
    if (e == 0x7F800000u) return v;          /* inf or nan keep */
    a.u = (a.u + 0x7FFFu + ((a.u >> 16) & 1u)) & 0xFFFF0000u;
    return a.f;
}

/* x * sigmoid(x), on an already rounded bf16 value, at the IR's saturated values; anything between is computed and flagged. */
static inline float silu_bf16(WProg *p, float v) {
    if (v == 0.f) return v;
    if (v >= 18.f) return v;
    if (v <= -104.f) return -0.f;
    p->flags |= F_SILU; p->not_saturated++;
    return bf16(v / (1.f + expf(-v)));
}

/* in fp32 as RMSNormGated: F.silu(gate.to(fp32)) */
static inline float silu_f32(WProg *p, float v) {
    if (v == 0.f) return v;
    if (v >= 18.f) return v * (1.f / (1.f + expf(-v)));
    if (v <= -104.f) return -0.f;
    p->flags |= F_SILU; p->not_saturated++;
    return v / (1.f + expf(-v));
}

static inline float sigmoid_bf16(WProg *p, float v) {
    if (v >= 128.f) return 1.f;
    if (v <= -128.f) return 0.f;
    if (v == 0.f) return 0.5f;
    p->flags |= F_SIG; p->not_saturated++;
    return bf16(1.f / (1.f + expf(-v)));
}

static inline float softplus_f32(float v) {
    if (v > 20.f) return v;
    if (v < -200.f) return 0.f;
    return log1pf(expf(v));
}

/* the sum of squares over the chip dims */
static inline float chip_sq(const float *x, int32_t n) {
    float s = 0.f;
    for (int32_t i = 0; i < n; i++) s += x[i] * x[i];
    return s;
}

int64_t w_stat[8];

static void build_memo(WLayer *L, int32_t m, float v, uint8_t *seen, uint8_t *zseen, uint8_t *useen) {
    int32_t nr = 0, nz = 0, nu = 0;
    memset(L->ab, 0, sizeof(float) * NV);
    memset(L->bb, 0, sizeof(float) * NV);
    for (int32_t c = 0; c < m; c++) {
        for (int32_t i = L->q_ptr[c]; i < L->q_ptr[c + 1]; i++) {
            int32_t r = L->q_row[i];
            if (!seen[r]) { seen[r] = 1; L->qb_r[nr++] = r; L->qb[r] = 0.f; }
            L->qb[r] += L->q_w[i] * v;
        }
        for (int32_t i = L->z_ptr[c]; i < L->z_ptr[c + 1]; i++) {
            int32_t r = L->z_row[i];
            if (!zseen[r]) { zseen[r] = 1; L->zb_r[nz++] = r; L->zb[r] = 0.f; }
            L->zb[r] += L->z_w[i] * v;
        }
        for (int32_t i = L->a_ptr[c]; i < L->a_ptr[c + 1]; i++) L->ab[L->a_row[i]] += L->a_w[i] * v;
        for (int32_t i = L->b_ptr[c]; i < L->b_ptr[c + 1]; i++) L->bb[L->b_row[i]] += L->b_w[i] * v;
        for (int32_t i = L->g_ptr[c]; i < L->g_ptr[c + 1]; i++) {
            int32_t r = L->g_row[i];
            if (!useen[r]) { useen[r] = 1; L->gb_r[nu++] = r; L->gb[r] = 0.f; }
            L->gb[r] += L->g_w[i] * v;
        }
    }
    for (int32_t i = 0; i < nr; i++) seen[L->qb_r[i]] = 0;
    for (int32_t i = 0; i < nz; i++) zseen[L->zb_r[i]] = 0;
    for (int32_t i = 0; i < nu; i++) useen[L->gb_r[i]] = 0;
    L->base_nq = nr; L->base_nz = nz; L->base_ng = nu; L->base_v = v;
}

/* Is every ballast dim's normed value the same, and nonzero? Then the memo can stand for those columns. */
static inline float ballast_same(const float *n_, int32_t m) {
    float v = n_[0];
    if (v == 0.f) return 0.f;
    for (int32_t i = 1; i < m; i++) if (n_[i] != v) return 0.f;
    return v;
}

/* One token through one chip layer. x holds the residual's chip dims; qsum is the sum of squares over the Qwen dims, which chip layers never write. */
static void layer_step(WProg *p, WLayer *L, float *x, float qsum, int32_t *act, float *n_, float *qkv, int32_t *trow, uint8_t *seen, float *z, int32_t *tz, uint8_t *zseen, float *a, float *b, float *y, int32_t *ty, uint8_t *yseen, float *gt, int32_t *tu, uint8_t *useen) {
    const int32_t chip = p->chip;
    const float hidden = (float)p->hidden;
    T0
    /* --- attention sublayer: input_layernorm --- */
    float rs = 1.f / sqrtf((qsum + chip_sq(x, chip)) / hidden + EPS);
    int32_t na = 0;
    for (int32_t i = 0; i < chip; i++) {
        if (x[i] != 0.f) {
            n_[i] = bf16(x[i] * rs * L->w_in[i]);
            act[na++] = i;
        } else n_[i] = 0.f;
    }
    T(0)
    /* in_proj_qkv, in_proj_z, a, b over the active columns */
    int32_t nr = 0, nz = 0;
    const int32_t m = p->ballast;
    float bv = ballast_same(n_, m);
    int32_t k0 = 0;
    if (bv != 0.f) {
        if (L->base_v != bv) build_memo(L, m, bv, seen, zseen, useen);
        memcpy(a, L->ab, sizeof(float) * NV);
        memcpy(b, L->bb, sizeof(float) * NV);
        for (int32_t i = 0; i < L->base_nq; i++) { int32_t r = L->qb_r[i]; seen[r] = 1; trow[nr++] = r; qkv[r] = L->qb[r]; }
        for (int32_t i = 0; i < L->base_nz; i++) { int32_t r = L->zb_r[i]; zseen[r] = 1; tz[nz++] = r; z[r] = L->zb[r]; }
        while (k0 < na && act[k0] < m) k0++;
    } else {
        memset(a, 0, sizeof(float) * NV);
        memset(b, 0, sizeof(float) * NV);
    }
    for (int32_t k = k0; k < na; k++) {
        int32_t c = act[k];
        float v = n_[c];
        if (v == 0.f) continue;
        for (int32_t i = L->q_ptr[c]; i < L->q_ptr[c + 1]; i++) {
            int32_t r = L->q_row[i];
            if (!seen[r]) { seen[r] = 1; trow[nr++] = r; qkv[r] = 0.f; }
            qkv[r] += L->q_w[i] * v;
        }
        for (int32_t i = L->z_ptr[c]; i < L->z_ptr[c + 1]; i++) {
            int32_t r = L->z_row[i];
            if (!zseen[r]) { zseen[r] = 1; tz[nz++] = r; z[r] = 0.f; }
            z[r] += L->z_w[i] * v;
        }
        for (int32_t i = L->a_ptr[c]; i < L->a_ptr[c + 1]; i++) a[L->a_row[i]] += L->a_w[i] * v;
        for (int32_t i = L->b_ptr[c]; i < L->b_ptr[c + 1]; i++) b[L->b_row[i]] += L->b_w[i] * v;
    }
    T(1)
    /* the conv window: rows with earlier taps need their history even when this token's input is zero */
    for (int32_t i = 0; i < L->n_lag; i++) {
        int32_t r = L->lag_row[i];
        if (!seen[r]) { seen[r] = 1; trow[nr++] = r; qkv[r] = 0.f; }
    }
    /* conv over the touched rows, then silu; lists by head */
    static __thread int32_t qn[NK], kn[NK], vn[NV];
    static __thread int16_t ql[NK][HD], kl[NK][HD], vl[NV][HD];
    static __thread float out[QKV];
    memset(qn, 0, sizeof(qn)); memset(kn, 0, sizeof(kn)); memset(vn, 0, sizeof(vn));
    for (int32_t i = 0; i < nr; i++) {
        int32_t r = trow[i];
        float cur = bf16(qkv[r]);                                /* the matmul's bf16 output */
        qkv[r] = cur;
        const float *w = L->conv + 4 * (int64_t)r;
        const float *h = L->hist + 3 * (int64_t)r;
        float c = bf16(w[0] * h[0] + w[1] * h[1] + w[2] * h[2] + w[3] * cur);
        float s = silu_bf16(p, c);
        out[r] = s;
        if (s != 0.f) {
            if (r < KEY_BASE) { int32_t j = r / HD; ql[j][qn[j]++] = r - j * HD; }
            else if (r < V_BASE) { int32_t j = (r - KEY_BASE) / HD; kl[j][kn[j]++] = r - KEY_BASE - j * HD; }
            else { int32_t j = (r - V_BASE) / HD; vl[j][vn[j]++] = r - V_BASE - j * HD; }
        }
    }
    T(2)
    /* the delta rule, per value head */
    int32_t ny = 0;
    const float sq128 = sqrtf(128.f);
    for (int32_t vh = 0; vh < NV; vh++) {
        if (!L->vh_active[vh]) continue;
        int32_t kh = vh / (NV / NK);
        float *S = L->S + (int64_t)vh * HD * HD;
        p->heads_run++;
        /* decay: exp(-exp(A_log) * softplus(a + dt_bias)) */
        float av = bf16(a[vh]);
        float sp = softplus_f32(av + L->dt_bias[vh]);
        float g = -L->A_exp[vh] * sp;
        if (g != 0.f) {
            float d = expf(g);
            if (d != 1.f) {
                if (d != 0.f && d != 0.5f && !(fabsf(d - 0.5f) < 1e-6f)) p->flags |= F_DECAY;
                int32_t nc = L->vh_nrows[vh] * HD;
                if (d == 0.f) memset(S, 0, sizeof(float) * nc);
                else for (int32_t i = 0; i < nc; i++) S[i] *= d;
            }
        }
        /* write */
        float beta = sigmoid_bf16(p, bf16(b[vh]));
        int32_t nk_ = kn[kh];
        const int32_t kbase = KEY_BASE + kh * HD;
        if (nk_ && beta != 0.f) {
            float ss = 0.f;
            for (int32_t i = 0; i < nk_; i++) { float v = out[kbase + kl[kh][i]]; ss += v * v; }
            float inv = 1.f / sqrtf(ss + EPS);
            float vv[HD];
            memset(vv, 0, sizeof(vv));
            const int32_t vbase = V_BASE + vh * HD;
            for (int32_t i = 0; i < vn[vh]; i++) vv[vl[vh][i]] = out[vbase + vl[vh][i]];
            float mem[HD];
            memset(mem, 0, sizeof(mem));
            for (int32_t i = 0; i < nk_; i++) {
                int32_t row = kl[kh][i];
                float kk = out[kbase + row] * inv;
                const float *Sr = S + (int64_t)row * HD;
                for (int32_t c = 0; c < HD; c++) mem[c] += Sr[c] * kk;
            }
            for (int32_t c = 0; c < HD; c++) vv[c] = (vv[c] - mem[c]) * beta;
            for (int32_t i = 0; i < nk_; i++) {
                int32_t row = kl[kh][i];
                float kk = out[kbase + row] * inv;
                float *Sr = S + (int64_t)row * HD;
                for (int32_t c = 0; c < HD; c++) Sr[c] += kk * vv[c];
                if (row + 1 > L->vh_nrows[vh]) L->vh_nrows[vh] = row + 1;
            }
        }
        /* read */
        int32_t nq_ = qn[kh];
        if (!nq_) continue;
        const int32_t qbase = kh * HD;
        float ss = 0.f;
        for (int32_t i = 0; i < nq_; i++) { float v = out[qbase + ql[kh][i]]; ss += v * v; }
        float inv = 1.f / sqrtf(ss + EPS);
        float o[HD];
        memset(o, 0, sizeof(o));
        for (int32_t i = 0; i < nq_; i++) {
            int32_t row = ql[kh][i];
            float qq = out[qbase + row] * inv / sq128;
            const float *Sr = S + (int64_t)row * HD;
            for (int32_t c = 0; c < HD; c++) o[c] += Sr[c] * qq;
        }
        float var = 0.f;
        for (int32_t c = 0; c < HD; c++) { o[c] = bf16(o[c]); var += o[c] * o[c]; }
        if (var == 0.f) continue;
        float r2 = 1.f / sqrtf(var / (float)HD + EPS);
        /* the output, only where z and the out_proj column exist */
        for (int32_t c = 0; c < HD; c++) {
            int32_t col = vh * HD + c;
            if (L->o_ptr[col] == L->o_ptr[col + 1] || !zseen[col]) continue;
            float zv = bf16(z[col]);
            float gs = silu_f32(p, zv);
            float h2 = bf16(bf16(o[c] * r2) * L->w_norm[c]);
            float cv = bf16(h2 * gs);
            if (cv == 0.f) continue;
            for (int32_t i = L->o_ptr[col]; i < L->o_ptr[col + 1]; i++) {
                int32_t d = L->o_dim[i];
                if (!yseen[d]) { yseen[d] = 1; ty[ny++] = d; y[d] = 0.f; }
                y[d] += L->o_w[i] * cv;
            }
        }
    }
    T(3)
    /* conv windows move on, seen rows cleared */
    for (int32_t i = 0; i < L->n_lag; i++) {
        int32_t r = L->lag_row[i];
        float *h = L->hist + 3 * (int64_t)r;
        h[0] = h[1]; h[1] = h[2]; h[2] = seen[r] ? qkv[r] : 0.f;
    }
    for (int32_t i = 0; i < nr; i++) seen[trow[i]] = 0;
    for (int32_t i = 0; i < nz; i++) zseen[tz[i]] = 0;
    /* residual */
    for (int32_t i = 0; i < ny; i++) {
        int32_t d = ty[i];
        x[d] = bf16(x[d] + bf16(y[d]));
        yseen[d] = 0;
    }
    T(4)
    /* --- MLP sublayer --- */
    rs = 1.f / sqrtf((qsum + chip_sq(x, chip)) / hidden + EPS);
    na = 0;
    for (int32_t i = 0; i < chip; i++) {
        if (x[i] != 0.f) { n_[i] = bf16(x[i] * rs * L->w_post[i]); act[na++] = i; }
        else n_[i] = 0.f;
    }
    T(5)
    int32_t nu = 0;
    bv = ballast_same(n_, m);
    k0 = 0;
    if (bv != 0.f) {
        if (L->base_v != bv) build_memo(L, m, bv, seen, zseen, useen);
        for (int32_t i = 0; i < L->base_ng; i++) { int32_t u = L->gb_r[i]; useen[u] = 1; tu[nu++] = u; gt[u] = L->gb[u]; }
        while (k0 < na && act[k0] < m) k0++;
    }
    for (int32_t k = k0; k < na; k++) {
        int32_t c = act[k];
        float v = n_[c];
        if (v == 0.f) continue;
        for (int32_t i = L->g_ptr[c]; i < L->g_ptr[c + 1]; i++) {
            int32_t u = L->g_row[i];
            if (!useen[u]) { useen[u] = 1; tu[nu++] = u; gt[u] = 0.f; }
            gt[u] += L->g_w[i] * v;
        }
    }
    T(6)
    w_stat[0] += na; w_stat[1] += nu;
    ny = 0;
    for (int32_t k = 0; k < nu; k++) {
        int32_t u = tu[k];
        useen[u] = 0;
        float gv = silu_bf16(p, bf16(gt[u]));
        if (!(gv > 0.f) && !(gv < 0.f)) continue;              /* zero of either sign: the product is a zero */
        float up = 0.f;
        for (int32_t i = L->u_ptr[u]; i < L->u_ptr[u + 1]; i++) up += L->u_w[i] * n_[L->u_col[i]];
        float pr = bf16(gv * bf16(up));
        if (pr == 0.f) continue;
        for (int32_t i = L->d_ptr[u]; i < L->d_ptr[u + 1]; i++) {
            int32_t d = L->d_dim[i];
            if (!yseen[d]) { yseen[d] = 1; ty[ny++] = d; y[d] = 0.f; }
            y[d] += L->d_w[i] * pr;
        }
    }
    T(7)
    for (int32_t i = 0; i < ny; i++) {
        int32_t d = ty[i];
        x[d] = bf16(x[d] + bf16(y[d]));
        yseen[d] = 0;
    }
    T(8)
}

int w_step(WProg *p, int32_t tok) {
    int32_t ix = tok < p->vocab ? tok : p->vocab + (tok - p->text_token);
    int32_t st = p->f_start[ix];
    if (st < 0) { p->miss_token = tok; return 1; }
    float *x = p->x;
    memset(x, 0, sizeof(float) * p->chip);
    for (int32_t i = 0, n = p->f_len[ix]; i < n; i++) x[p->f_dim[st + i]] = p->f_val[st + i];
    float qsum = p->f_qsum[ix];
    static __thread int32_t act[MAX_D], trow[QKV], tz[NV * HD], ty[MAX_D], tu[MAX_U];
    static __thread float n_[MAX_D], qkv[QKV], z[NV * HD], y[MAX_D], gt[MAX_U], a[NV], b[NV];
    static __thread uint8_t seen[QKV], zseen[NV * HD], yseen[MAX_D], useen[MAX_U];
    for (int32_t l = 0; l < p->nL; l++)
        layer_step(p, p->L + l, x, qsum, act, n_, qkv, trow, seen, z, tz, zseen, a, b, y, ty, yseen, gt, tu, useen);
    p->steps++;
    return 0;
}

/* After a step: is every chip dim other than the kept ones (and they alone) zero? Counts positions with residue. */
int64_t w_check_residue(WProg *p, const uint8_t *is_keep) {
    for (int32_t i = 0; i < p->chip; i++)
        if (!is_keep[i] && p->x[i] != 0.f) { p->residue++; p->flags |= F_RESIDUE; break; }
    return p->residue;
}

static int32_t next_token(const WProg *p) {
    const float *x = p->x;
    uint32_t bits = 0; int any = 0;
    int nb = p->nfam + p->npay;
    for (int i = 0; i < nb; i++) {
        float v = x[p->keep[i]];
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

int w_burst(WProg *p, int32_t tok, int64_t max_steps, int32_t *out_tok, int64_t *out_n, int32_t *rec) {
    int64_t n = 0;
    int32_t t = tok;
    int st = 2;
    while (n < max_steps) {
        if (w_step(p, t)) { st = 3; break; }
        t = next_token(p);
        if (rec) rec[n] = t;
        n++;
        if (t == -1) { st = 1; break; }
        if (t == -2) { st = 4; break; }
        if (t >= p->vocab) { st = 0; break; }
    }
    *out_tok = t; *out_n = n;
    return st;
}

int64_t w_run(WProg *p, const int32_t *toks, int64_t n, float *keep_out, const uint8_t *is_keep) {
    for (int64_t i = 0; i < n; i++) {
        if (w_step(p, toks[i])) return i;
        if (keep_out) {
            for (int32_t k = 0; k < p->n_keep; k++) keep_out[i * p->n_keep + k] = p->x[p->keep[k]];
            if (is_keep) w_check_residue(p, is_keep);
        }
    }
    return n;
}
