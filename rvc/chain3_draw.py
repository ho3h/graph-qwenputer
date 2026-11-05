"""The draw for the 100-question chain: seeded, dev data only, not the 17 used so far. Run under memguard from the vendored folder.

70 from data/dev/cities, 30 from data/dev/random, uniformly within each set; r097 is left out because it does not fit the image. Each drawn graph
is booted on fw/'s firmware and the canonical call compared with reflib, and the chip tokens are forecast, before any model loads.
"""
import glob, hashlib, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X
from chipformer.rv import bridge as BR
import reflib

SEED, N_CITIES, N_RANDOM = 20261102, 70, 30
FW = os.path.join(X.X210, "fw", "build", "fw.elf")
X.ELF = FW
X.build_elf = lambda: FW
USED = {("cities/c024", i) for i in (0, 1, 100, 101, 200, 201)} | {("cities/c025", i) for i in (0, 1, 100, 101, 200, 201)} | {("random/r001", 17)}
pool = {"cities": [], "random": []}
for f in sorted(glob.glob(os.path.join(X.X210, "data", "dev", "*", "*.questions.json"))):
    assert "heldout" not in f
    s, b = f.split(os.sep)[-2], os.path.basename(f).split(".")[0]
    if b == "r097":
        continue
    for q in json.load(open(f))["questions"]:
        if q.get("kind") == "chase" and (f"{s}/{b}", q["id"]) not in USED:
            pool[s].append((f"{s}/{b}", q["id"]))
rng = random.Random(SEED)
draw = rng.sample(pool["cities"], N_CITIES) + rng.sample(pool["random"], N_RANDOM)
rng.shuffle(draw)                             # a stopped run is still a fair prefix
stock = [next(k for k in draw if k[0].startswith("cities")), next(k for k in draw if k[0].startswith("random"))]
T = BR.Text(X.tokenizer_json())
chip, bad, kinds = 0, [], {}
for g, i in draw:
    gj = json.load(open(os.path.join(X.X210, "data", "dev", g + ".graph.json")))
    q = {x["id"]: x for x in json.load(open(os.path.join(X.X210, "data", "dev", g + ".questions.json")))["questions"]}[i]
    b, G = X.Box(gj, T), reflib.Graph(gj)
    for s in q.get("setup") or []:
        b.call(T.encode(X.template_text(s["fn"], s["args"])))
        G.call(s["fn"], s["args"])
    r = b.call(T.encode(X.template_text(q["call"]["fn"], q["call"]["args"])))
    chip += r.chip
    if r.result != G.call(q["call"]["fn"], q["call"]["args"]) or r.result != q["answer_text"] or not r.ok_wrap:
        bad.append([g, i, r.result, q["answer_text"]])
    k = q.get("case") or f"city kind {i // 100}"
    kinds[k] = kinds.get(k, 0) + 1
out = {"seed": SEED, "pool": {k: len(v) for k, v in pool.items()}, "draw": draw, "stock_sample": stock, "firmware_sha256": hashlib.sha256(open(FW, "rb").read()).hexdigest(),
       "canonical_chip_tokens": chip, "canonical_mismatches": bad, "kinds": kinds}
json.dump(out, open(os.path.join(HERE, "results", "chain3_draw.json"), "w"), indent=0)
print(json.dumps({k: v for k, v in out.items() if k != "draw"}))
