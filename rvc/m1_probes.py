"""M1 extras: a negative control for the byte comparison, the known divergences measured, and path / cheapest on the IR."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X
import ir_check as IC
from chipformer.rv import bridge as BR
from chipformer.rv import core
import reflib
from transformers import AutoTokenizer

T = BR.Text(X.tokenizer_json())
HF = AutoTokenizer.from_pretrained(X.MODEL)
res = {}
g = json.load(open(os.path.join(X.X210, "data", "dev", "cities", "c024.graph.json")))
qs = [x for x in json.load(open(os.path.join(X.X210, "data", "dev", "cities", "c024.questions.json")))["questions"]
      if x["kind"] == "chase"][:100]

# negative control: the machine holds the graph minus 20 edges (or one label changed); the reference holds the real graph
import copy, random
rng = random.Random(0)
bad = copy.deepcopy(g)
for e in rng.sample(bad["edges"], 20):
    bad["edges"].remove(e)
b, G, n = X.Box(bad, T), reflib.Graph(g), 0
for x in qs:
    r = b.call(T.encode(X.template_text(x["call"]["fn"], x["call"]["args"])))
    n += r.result != G.call(x["call"]["fn"], x["call"]["args"])
res["negative_control_20_edges_removed"] = {"calls": len(qs), "mismatches_found": n}

# divergences from the host tool
tiny = {"format": "x210-graph/1", "name": "d", "domain": "t",
        "nodes": [{"label": "Café"}, {"label": "Oak"}, {"label": "Elm"}, {"label": "Ash"}], "relations": ["r"],
        "edges": [[0, 0, 1, 1], [1, 0, 2, 1], [2, 0, 3, 1]], "splice": [], "change": None, "meta": {}}
cases = {"non-NFC argument (Cafe + combining acute)": X.template_text("find", {"name": "Café"}),
         "non-ASCII digit handle": X.template_text("find", {"name": "@٣"}),
         "non-ASCII digit steps": X.template_text("follow", {"node": "@1", "relation": "r", "steps": "٣"}),
         "invalid UTF-8 cut across the argument": None, "NUL token in the argument": None}
out = {}
for name, s in cases.items():
    if s is None:
        continue
    ids = T.encode(s)
    b, G = X.Box(tiny, T), reflib.Graph(tiny)
    out[name] = {"host": X.reference(G, HF.decode(ids, skip_special_tokens=False)), "machine": b.call(ids).result}
# a partial UTF-8 byte as an argument
ids = T.encode("\n<function=find>\n<parameter=name>\n") + [T.printable[0xC3]] + T.encode("\n</parameter>\n</function>\n")
b, G = X.Box(tiny, T), reflib.Graph(tiny)
out["lone UTF-8 lead byte in the argument"] = {"host": X.reference(G, HF.decode(ids, skip_special_tokens=False)), "machine": b.call(ids).result}
# the NUL token ends the capture
ids = T.encode("\n<function=find>\n<parameter=name>\nOak") + [188] + T.encode("\n</parameter>\n</function>\n")
b, G = X.Box(tiny, T), reflib.Graph(tiny)
out["NUL token in the argument"] = {"host": X.reference(G, HF.decode(ids, skip_special_tokens=False)), "machine": b.call(ids).result}
# </tool_call> with no <tool_call> in the turn: the host parses the whole turn's text, the bridge re-reads the last capture
b, G = X.Box(tiny, T), reflib.Graph(tiny)
first = b.call(T.encode(X.template_text("find", {"name": "Oak"}))).result
turn = T.encode(X.template_text("find", {"name": "Elm"}))
k = len(b.ses.runs)
b.ses.qwen(turn + [T.TCC])
raw = T.decode_bytes(b.ses.runs[k])
out["</tool_call> with no <tool_call> in the turn (after find Oak; the turn says find Elm)"] = {
    "host": X.reference(G, HF.decode(turn, skip_special_tokens=False)), "machine": raw[len(b.head):-len(b.tail)].decode(), "first_call": first}
res["divergences"] = out

# path and cheapest on the circuit's IR (ir_check's sessions have neither)
t0 = time.time()
c = core.build(IC.target(), T)
tg = json.load(open(os.path.join(X.X210, "host", "test", "tiny.graph.json")))
N = len(tg["nodes"])
r = IC.check_session(c, T, tg, [("path", {"from": "@0", "to": f"@{N - 1}"}), ("cheapest", {"from": "@0", "to": f"@{N - 1}"}),
                                ("follow", {"node": "@0", "relation": tg["relations"][0], "steps": "2"}),
                                ("neighbours", {"node": "@0", "relation": tg["relations"][0]})])
r["graph"] = "host/test/tiny"
res["ir_path_cheapest"] = r
res["tiny_N_E"] = [N, len(tg["edges"])]
json.dump(res, open(os.path.join(HERE, "results", "m1_probes.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
