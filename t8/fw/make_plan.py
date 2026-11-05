#!/usr/bin/env python3
"""t8/fw/plan_clean.json: the stock sample for the cleaner firmware. Cleaned names, a limit line and refusals on c024 and r001, sized to the hour exec/REGISTRATION.md allows. path, cheapest, link, unlink with cleaned names run on the engine against the reference (engine_ref.py) and show in the coverage difference. No model."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
plan = {j["name"]: j for j in json.load(open(os.path.join(X210, "tok", "plan_tok.json")))}
c = json.load(open(os.path.join(X210, "data", "dev", "cities", "c024.graph.json")))
q = [x for x in json.load(open(os.path.join(X210, "data", "dev", "cities", "c024.questions.json")))["questions"] if x.get("kind") == "chase"][:2]
L = [n["label"] for n in c["nodes"]]
lab = lambda a: L[int(a[1:])]
s0, l0 = q[0]["call"]["args"]["start"], q[0]["call"]["args"]["legs"]
s1, l1 = q[1]["call"]["args"]["start"], q[1]["call"]["args"]["legs"]
A, B = lab(s0), lab(s1)
r = c["relations"][0]
calls = [["chase", {"start": A + " station", "legs": l0}], ["chase", {"start": B + " station.", "legs": l1}], ["find", {"name": A + "."}], ["find", {"name": "Out of " + A}], ["chase", {"start": A + " Station", "legs": l0}],
         ["follow", {"node": A + ",", "relation": r, "steps": "1"}], ["neighbours", {"node": B + " station", "relation": r}],
         ["close", {"node": B + " station"}], ["reopen", {"node": B + "."}]]
rn = json.load(open(os.path.join(X210, "data", "dev", "random", "r001.graph.json")))
one = [n["label"] for n in rn["nodes"] if [m["label"] for m in rn["nodes"]].count(n["label"]) == 1]
two = [n["label"] for n in rn["nodes"] if [m["label"] for m in rn["nodes"]].count(n["label"]) == 2]
calls2 = [["find", {"name": one[0] + "."}], ["find", {"name": one[0] + " station"}], ["find", {"name": two[0] + "."}], ["chase", {"start": one[1] + "!", "legs": f"{rn['relations'][0]} 1"}]]
out = [{"name": "clean-c024", "graph": "cities/c024", "calls": calls}, {"name": "clean-r001", "graph": "random/r001", "calls": calls2}]
json.dump(out, open(os.path.join(HERE, "plan_clean.json"), "w"), indent=0, ensure_ascii=False)
print([(j["name"], len(j["calls"])) for j in out])
