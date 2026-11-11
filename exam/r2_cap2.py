"""exam/AFTER.md U0, the 14-stop route alone: does it stop at the harness cap? Through tokrun with T8_R2=1."""
import json,os,sys
HERE=os.path.join(os.getcwd(),"exam");sys.path.insert(0,HERE)
import mach as M, noun as N, reflib, box as XX
it=json.load(open(os.path.join(HERE,"items","nyc.json")))
g=N.with_noun(json.load(open(os.path.join(HERE,"items","nyc_t.graph.json"))))
pair=M.Pair(g,it["prompt_ids"],it["between_ids"],coverage=False);T=pair.T
def run(tag,calls):
    pair.fresh();G=reflib.Graph(g)
    for fn,a in calls:
        r=pair.call(T.encode(XX.template_text(fn,a)));w=G.call(fn,a)
        if not r["same"] or fn in("path",):print(tag,fn,"same",r["same"],"status",r["status"],"wrap",r["wrap"],"chip",r["chip"],"echo",r["echo"],"flags",r["flags"],"body",repr(r["body"][:60]),"ref",repr((r["ref_body"] or "")[:40]),"reflib_eq",r["ref_body"]==w,flush=True)
names=[f"Capstop {i:02d}" for i in range(16)]
for k in (14,):
    c=[("add_node",{"name":n}) for n in names[:k]];p="Roosevelt Island"
    for n in names[:k]:c.append(("link",{"from":p,"relation":"T northbound","to":n}));p=n
    c.append(("path",{"from":"Roosevelt Island","to":names[k-1]}))
    run(f"k{k}",c)
