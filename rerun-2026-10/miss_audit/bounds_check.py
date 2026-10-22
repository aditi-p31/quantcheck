"""Independent check of bounds.py rows 1-4: depth-first search over all per-stratum allocations with exact
fractions (no logs, no floating point). Strata sizes are typed in from BOUNDS.md section 2. Usage: python3 bounds_check.py"""
from math import comb
from fractions import Fraction
def p(N,n,D,k):
    return Fraction(sum(comb(D,x)*comb(N-D,n-x) for x in range(k+1)), comb(N,n))
def best(strata, adverse=None, alpha=Fraction(1,20)):
    # strata: list of (name,N,n)
    tabs=[]
    for name,N,n in strata:
        k=1 if name==adverse else 0
        t=[]
        for D in range(N+1):
            v=p(N,n,D,k)
            if v<alpha: break
            t.append(v)
        tabs.append(t)
    bestT=[0,None]
    def dfs(i,prod,tot,alloc):
        if i==len(tabs):
            if tot>bestT[0]: bestT[0]=tot; bestT[1]=list(alloc)
            return
        for D,v in enumerate(tabs[i]):
            q=prod*v
            if q<alpha: break
            alloc.append(D); dfs(i+1,q,tot+D,alloc); alloc.pop()
    dfs(0,Fraction(1),0,[])
    return bestT
S233=[('codellama',18,6),('deepseek',12,7),('gemma',22,7),('granite',57,9),('llama',25,8),('mistral',22,7),('phi',10,7),('qwen',24,6),('starcoder2',2,2),('yi',41,7)]
S223=[('codellama',18,6),('deepseek',11,6),('gemma',21,6),('granite',54,6),('llama',23,6),('mistral',21,6),('phi',9,6),('qwen',24,6),('starcoder2',2,2),('yi',40,6)]
print('row1',best(S233)); print('row2',best(S233,'gemma')); print('row3',best(S223)); print('row4',best(S223,'gemma'))
