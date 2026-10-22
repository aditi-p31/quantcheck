"""Seed search for the first-version miss-audit sample (sensitivity_sample.json): tries random.Random(s).sample(pool, 10)
and shuffle-then-take-10 over 48 frame variants and about 300,000 seeds. Finds no match (log: v1_seed_search.log; about
16 minutes). Inputs follow the repository layout (QUANTCHECK_ROOT overrides the root). Usage, from the repository root:
python3 rerun-2026-10/miss_audit/v1_seed_search.py > v1_seed_search.log"""
import json,os,random,sys,time
HERE=os.path.dirname(os.path.abspath(__file__))
P=os.path.abspath(os.environ.get("QUANTCHECK_ROOT") or os.path.join(HERE,"..",".."))
rows=[json.loads(l) for l in open(os.path.join(P,"results","audit_scored.jsonl")) if l.strip()]
sc={r['tag']:r for r in rows}
invl=json.load(open(os.path.join(P,"inventory_candidates.json")))['artifacts']
inv={a['tag']:a for a in invl}
tun={i.replace('_',':',1) for i in json.load(open(os.path.join(P,"rerun-2026-10","serial","tuning_configs.json")))['ids']}
off=[r['tag'] for r in rows if r['channel']=='ollama-official']
v1=[a['tag'] for a in json.load(open(os.path.join(P,"sensitivity_sample.json")))['artifacts']]
v1s=set(v1)
bases={
 'frame233': [t for t in off if sc[t]['smoke_pass']>=9 and t not in tun],
 'healthy255': [t for t in off if sc[t]['verdict']=='healthy'],
}
variants={}
for bn,b in bases.items():
    for cut in [None,4.0,4.5,5.0]:
        for noqwen in [False,True]:
            pool=[t for t in b if (cut is None or inv[t]['file_size_gb']<=cut) and (not noqwen or sc[t]['family']!='qwen2.5-coder')]
            if not v1s<=set(pool): continue
            for order in ['file','sorted','inv']:
                if order=='sorted': p=sorted(pool)
                elif order=='inv':
                    idx={a['tag']:i for i,a in enumerate(invl)}; p=sorted(pool,key=lambda t: idx[t])
                else: p=list(pool)
                variants[(bn,cut,noqwen,order)]=p
print(len(variants), {k:len(v) for k,v in variants.items()}, flush=True)
seeds=list(range(0,300001))+list(range(20260801,20260832))+[2026,20260812,20260813,1234,12345,123456,31337,8675309]
first=v1[0]
hits=[]
t0=time.time()
for k,p in variants.items():
    n=len(p)
    for s in seeds:
        r=random.Random(s)
        out=r.sample(p,10)
        if out[0]==first or set(out)==v1s:
            if out==v1 or set(out)==v1s: hits.append((k,s,out==v1)); print('HIT',k,s,out==v1,flush=True)
        # shuffle variant
        q=list(p); random.Random(s).shuffle(q)
        if set(q[:10])==v1s: hits.append((k,s,'shuffle')); print('HIT shuffle',k,s,flush=True)
    print('done',k,round(time.time()-t0),flush=True)
print('hits',hits)
