# Independent walker written from SPEC.md only; imports nothing from the project.
import json,glob,os,collections,sys
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","")
g=json.load(open(R+'data/heldout/nyc/nyc.graph.json'))
it=json.load(open(R+'exam/items/nyc.json'))
names=g['relations'];idx={n:i for i,n in enumerate(names)};ch=idx[g['change']];spl={idx[n] for n in g['splice']}
lab=[n['label'] for n in g['nodes']]
out=collections.defaultdict(list)
for a,r,b,w in g['edges']: out[(a,r)].append(b)
adj=collections.defaultdict(list)
for a,r,b,w in g['edges']: adj[a].append(b)
def succ(v,r,cl):
    res=set();seen=set();st=list(out[(v,r)])
    while st:
        t=st.pop()
        if t in seen: continue
        seen.add(t)
        if t in cl:
            if r in spl: st+=out[(t,r)]
        else: res.add(t)
    return sorted(res)
def fmt(h): return f"@{h} {lab[h]}"
def chase(start,legs,cl=frozenset()):
    h=int(start[1:])
    if h in cl: return "CLOSED "+fmt(h)
    L=[]
    for x in legs.split(';'):
        x=x.strip();p=x.rsplit(' ',1);L.append((idx[p[0]],int(p[1])))
    for i,(r,n) in enumerate(L,1):
        if i>1 and not succ(h,r,cl):
            cs=[c for c in succ(h,ch,cl) if succ(c,r,cl)]
            if not cs: return f"Stopped early on leg {i}: at {fmt(h)}, no change leads to that leg's relation. The journey did not finish."
            if len(cs)>1: return f"Stopped early on leg {i}: after 0 steps at {fmt(h)}, there are {len(cs)} possible next steps, so the way on isn't unique. The journey did not finish."
            h=cs[0]
        for s in range(n):
            nx=succ(h,r,cl)
            if not nx: return f"Stopped early on leg {i}: after {s} steps at {fmt(h)}, no further step along this relation exists. The journey did not finish."
            if len(nx)>1: return f"Stopped early on leg {i}: after {s} steps at {fmt(h)}, there are {len(nx)} possible next steps, so the way on isn't unique. The journey did not finish."
            h=nx[0]
    return fmt(h)
def bfs(s,t):
    d={s:0};q=collections.deque([s])
    while q:
        v=q.popleft()
        if v==t: return d[v]
        for w in adj[v]:
            if w not in d: d[w]=d[v]+1;q.append(w)
    return None
chases=[q['args'] for q in it['questions']]
for root in ('nyc','nyc_r1'):
    d=R+'exam/results/'+root+'/'
    tot=collections.Counter();diffs=[];toks=0
    base={}
    for l in open(d+'base.jsonl'):
        r=json.loads(l);c=chases[r['i']];w=chase(c['start'],c['legs']);base[r['i']]=r['body']
        tot['base']+=1;tot['base_same']+=w==r['body'];tot['refsame']+=r['same'] and r['digest']==r['ref_digest']
        if w!=r['body']:diffs.append(('base',r['i'],w,r['body']))
    tags=collections.Counter()
    for k,u in enumerate(it['units']):
        f=d+f"close{k:02d}.jsonl";h=u['node']
        if not os.path.exists(f):continue
        seen=0
        for l in open(f):
            r=json.loads(l);tags[r['tag']]+=1;tot['refsame']+=bool(r['same']) and r['digest']==r['ref_digest'];toks+=r['chip']
            if 'i' not in r or r.get('tag','') in('close','reopen'):continue
            c=chases[r['i']]
            closed=r['tag'].startswith('closed') or r['tag']=='closed'
            if closed:
                w=chase(c['start'],c['legs'],frozenset([h]));tot['closed']+=1;same=w==r['body'];tot['closed_same']+=same
                aff=w!=base[r['i']]
                tot['aff' if aff else 'unaff']+=1
                tot['aff_changed' if aff else 'unaff_same']+= (r['body']!=base[r['i']]) if aff else (r['body']==base[r['i']])
            else:
                w=base[r['i']];tot['restored']+=1;same=r['body']==w;tot['restored_same']+=same
            if not same:diffs.append((r['tag'],k,r['i'],w,r['body']))
    pp=collections.Counter()
    pw=[p for p in it['pairs']]
    for f in sorted(glob.glob(d+'paths*.jsonl')):
        for l in open(f):
            r=json.loads(l);p=pw[int(os.path.basename(f)[5:7])*50+r['i']];s=int(p['args']['from'][1:]);t=int(p['args']['to'][1:]);n=bfs(s,t);pp['n']+=1
            b=r['body']
            if n is None: pp['ok']+=b=='NOPATH';continue
            steps=int(b.split(' steps')[0]) if ' steps' in b else None
            nodes=[int(x.split()[0][1:]) for x in b.split(': ',1)[1].split(' > ')] if steps is not None else []
            valid=steps==n and nodes[0]==s and nodes[-1]==t and all(nodes[i+1] in adj[nodes[i]] for i in range(len(nodes)-1)) and len(nodes)==n+1
            pp['ok']+=valid
            if not valid:print('PATHDIFF',p['args'],b[:200],n)
            pp['same']+=bool(r['same']) and r['digest']==r['ref_digest'];pp['maxchip']=max(pp['maxchip'],r['chip'])
    print(root,dict(tot),'tags',dict(tags),'closechiptok',toks,'paths',dict(pp),'diffs',len(diffs));print(diffs[:6])
print('closures',it['closures'],[lab[h] for h in it['closures']],'file',it['file_chases'],'gen',it['generated_chases'],'dropped',it['file_dropped_by_window'])
print('n',len(lab),'edges',len(g['edges']),'rel',len(names))
c=collections.Counter(lab);print('shared labels',sum(1 for k,v in c.items() if v>1),'nodes',sum(v for v in c.values() if v>1))
print('distinct affected questions',)
