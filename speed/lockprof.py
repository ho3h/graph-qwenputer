import sys,time,json,copy
sys.path.insert(0,'.')
import fast
fast.setup("tok")
g=fast.g
from chipformer.q35.ir import Target
T=g.BR.Text(g.ckpt+"/tokenizer.json")
g.C.O.set_text(T)
rs=[json.loads(l) for l in open('results/proofs/p2_fast_1/all.jsonl')][:4]
out=[]
for r in rs:
    its=fast.items([tuple(r['tag'])]); gr,q,tag=its[0]
    m=g.D.parked_machine(gr,T,q.get('setup') or [])
    lock=g.BR.Session(T,copy.deepcopy(m))
    from transformers import AutoTokenizer
    t0=time.perf_counter(); lock.qwen([T.TCO]+r['calls'][0]['ids']+[T.TCC]); dt=time.perf_counter()-t0
    out.append({"tag":tag,"lock_s":round(dt,2),"chip":r['calls'][0]['chip']})
    print(out[-1],flush=True)
json.dump(out,open('results/lockprof.json','w'),indent=1)
