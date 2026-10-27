"""CPU pilot: learned ranking of bounded circuit-repair edits.

Synthetic combinational circuits only. This is NOT a reproduction of SODC,
not a local/distributed controller, and not evidence of publication novelty.
The ranker observes a sampled specification; an independent exhaustive checker
tests all Boolean inputs. All methods get exactly the same legal edit space.
"""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import sys, json, random, time, platform, hashlib, csv
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import Counter
from functools import lru_cache
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.research_deps'))
import numpy as np

class TinyForest:
    """Small histogram classification forest, implemented here using NumPy only.

    Balanced class weights, random feature subsets and row subsampling. No
    novelty is claimed for this conventional learner; it is a CPU feasibility
    instrument, not the proposed research contribution.
    """
    def __init__(self, trees=32, depth=8, leaf=12, seed=20261025):
        self.trees,self.depth,self.leaf,self.seed=trees,depth,leaf,seed
    def fit(self,X,y):
        self.thresholds=[np.unique(np.quantile(X[:,j],np.linspace(0,1,17)[1:-1])) for j in range(X.shape[1])]
        bins=np.column_stack([np.searchsorted(t,X[:,j],side='left') for j,t in enumerate(self.thresholds)]).astype(np.uint8)
        weights=np.where(y,0.5/max(1,y.sum()),0.5/max(1,(~y).sum()))*len(y)
        self.feature_importances_=np.zeros(X.shape[1]);self.models=[]
        rng=np.random.default_rng(self.seed)
        def grow(ids,depth):
            total=weights[ids].sum(); pos=weights[ids][y[ids]].sum()
            probability=float(pos/max(total,1e-12))
            if depth==0 or len(ids)<2*self.leaf or pos<1e-9 or total-pos<1e-9:
                return [probability]
            best=None; best_gain=0.0
            for j in rng.choice(X.shape[1],min(8,X.shape[1]),replace=False):
                nb=len(self.thresholds[j])+1
                if nb<2: continue
                hist=np.bincount(bins[ids,j],weights=weights[ids],minlength=nb)
                positive=np.bincount(bins[ids,j],weights=weights[ids]*y[ids],minlength=nb)
                counts=np.bincount(bins[ids,j],minlength=nb)
                left=np.cumsum(hist)[:-1]; right=total-left
                lp=np.cumsum(positive)[:-1]; rp=pos-lp
                lc=np.cumsum(counts)[:-1]
                gain=lp*lp/np.maximum(left,1e-12)+rp*rp/np.maximum(right,1e-12)-pos*pos/max(total,1e-12)
                gain[(lc<self.leaf)|((len(ids)-lc)<self.leaf)]=-1
                k=int(gain.argmax())
                if gain[k]>best_gain:
                    best_gain=float(gain[k]);best=(int(j),k)
            if best is None: return [probability]
            j,k=best; mask=bins[ids,j]<=k
            self.feature_importances_[j]+=best_gain
            return [j,k,grow(ids[mask],depth-1),grow(ids[~mask],depth-1)]
        for _ in range(self.trees):
            ids=rng.choice(len(y),int(len(y)*0.75),replace=False)
            self.models.append(grow(ids,self.depth))
        self.feature_importances_/=max(self.feature_importances_.sum(),1e-12)
        return self
    def predict_proba(self,X):
        bins=np.column_stack([np.searchsorted(t,X[:,j],side='left') for j,t in enumerate(self.thresholds)]).astype(np.uint8)
        if not hasattr(self,'compiled'):self.compile()
        f,k,left,right,p=self.compiled
        tree_ids=np.arange(len(self.models))[:,None]
        row_ids=np.arange(len(X))[None,:]
        nodes=np.zeros((len(self.models),len(X)),dtype=np.int32)
        for _ in range(self.depth):
            features=f[tree_ids,nodes]
            choose_left=bins[row_ids,features]<=k[tree_ids,nodes]
            nodes=np.where(choose_left,left[tree_ids,nodes],right[tree_ids,nodes])
        result=p[tree_ids,nodes].mean(axis=0)
        return np.column_stack([1-result,result])
    def compile(self):
        forests=[]
        for tree in self.models:
            nodes=[]
            def flat(node):
                i=len(nodes);nodes.append(None)
                if len(node)==1:nodes[i]=[0,0,i,i,node[0]]
                else:
                    j,k,l,r=node;li=flat(l);ri=flat(r)
                    nodes[i]=[j,k,li,ri,0.0]
                return i
            flat(tree);forests.append(nodes)
        width=max(map(len,forests))
        arrays=[np.zeros((len(forests),width),dtype=np.int32) for _ in range(4)]
        probabilities=np.zeros((len(forests),width))
        for t,nodes in enumerate(forests):
            a=np.asarray(nodes)
            for j in range(4):arrays[j][t,:len(nodes)]=a[:,j].astype(np.int32)
            probabilities[t,:len(nodes)]=a[:,4]
        self.compiled=(*arrays,probabilities)
    def predict_proba_reference(self,X):
        bins=np.column_stack([np.searchsorted(t,X[:,j],side='left') for j,t in enumerate(self.thresholds)]).astype(np.uint8)
        result=np.zeros(len(X))
        def visit(node,ids):
            if len(node)==1: result[ids]+=node[0];return
            j,k,left,right=node;mask=bins[ids,j]<=k
            visit(left,ids[mask]);visit(right,ids[~mask])
        for tree in self.models:visit(tree,np.arange(len(X)))
        result/=len(self.models)
        return np.column_stack([1-result,result])

FEATURES = ['sample_errors', 'relative_improvement', 'kind_lut', 'kind_wire',
            'relative_gate_depth', 'relative_source_depth', 'relative_old_source_depth',
            'fanout', 'output_gate', 'fault_ancestor', 'lut_edit_distance',
            'old_lut_ones', 'new_lut_ones', 'source_is_input', 'source_is_fault',
            'source_ones', 'source_similarity', 'local_change_fraction',
            'outputs_reachable', 'current_sample_errors']

@dataclass(frozen=True)
class Circuit:
    n: int
    gates: tuple  # (source_a, source_b, 4-bit LUT), gate j has signal n+j
    outputs: tuple
    stuck: int = -1
    stuck_value: int = 0

def lut(a, b, table, mask):
    na, nb = a ^ mask, b ^ mask
    value = 0
    if table & 1: value |= na & nb
    if table & 2: value |= a & nb
    if table & 4: value |= na & b
    if table & 8: value |= a & b
    return value

@lru_cache(maxsize=1024)
def input_signals(n,rows):
    return tuple(sum(((row>>i)&1)<<k for k,row in enumerate(rows)) for i in range(n))

def signals(c, rows):
    rows=tuple(rows)
    mask = (1 << len(rows)) - 1
    values = list(input_signals(c.n,rows))
    for j, (a, b, table) in enumerate(c.gates):
        values.append((mask if c.stuck_value else 0) if j == c.stuck else lut(values[a], values[b], table, mask))
    return values

def evaluate(c, rows):
    values = signals(c, rows)
    return tuple(values[i] for i in c.outputs)

def apply(c, edit):
    kind, j, slot, value = edit
    gates = list(c.gates)
    g = list(gates[j])
    g[2 if kind == 'lut' else slot] = value
    gates[j] = tuple(g)
    return Circuit(c.n, tuple(gates), c.outputs, c.stuck, c.stuck_value)

def legal_edits(c):
    for j, (a, b, table) in enumerate(c.gates):
        if j == c.stuck: continue
        for t in range(16):
            if t != table: yield ('lut', j, 2, t)
        for slot, old in enumerate((a, b)):
            for source in range(c.n + j):
                if source != old: yield ('wire', j, slot, source)

def ancestors(c, signal):
    seen, todo = set(), [signal]
    while todo:
        x = todo.pop()
        if x in seen: continue
        seen.add(x)
        if x >= c.n:
            j = x - c.n
            if j != c.stuck: todo.extend(c.gates[j][:2])
    return seen

def err(values, target):
    return sum((a ^ b).bit_count() for a, b in zip(values, target))

def features(c, edits, rows, target):
    # No complete truth table, original undamaged circuit, or repair labels here.
    current = signals(c, rows)
    current_out = tuple(current[o] for o in c.outputs)
    base = err(current_out, target)
    denom = len(rows) * len(c.outputs)
    mask = (1 << len(rows)) - 1
    out_anc = [ancestors(c, o) for o in c.outputs]
    fanout = Counter(x for g in c.gates for x in g[:2])
    output = []
    for edit in edits:
        kind, j, slot, value = edit
        a, b, table = c.gates[j]
        signal = c.n+j
        new_c = apply(c, edit)
        new_out = evaluate(new_c, rows)
        errors = err(new_out, target)
        source = value if kind == 'wire' else a
        old_source = (a, b)[slot] if kind == 'wire' else a
        new_table = value if kind == 'lut' else table
        aa = current[value] if kind == 'wire' and slot == 0 else current[a]
        bb = current[value] if kind == 'wire' and slot == 1 else current[b]
        local = lut(aa, bb, new_table, mask)
        output.append([
            errors/denom, (base-errors)/denom, float(kind=='lut'), float(kind=='wire'),
            j/max(1,len(c.gates)-1), source/(c.n+len(c.gates)), old_source/(c.n+len(c.gates)),
            fanout[signal], float(signal in c.outputs),
            float(c.stuck >= 0 and c.n+c.stuck in ancestors(c, signal)),
            (table ^ new_table).bit_count()/4, table.bit_count()/4, new_table.bit_count()/4,
            float(source<c.n), float(c.stuck>=0 and source==c.n+c.stuck),
            current[source].bit_count()/len(rows),
            1-(current[source]^current[old_source]).bit_count()/len(rows),
            (local ^ current[signal]).bit_count()/len(rows),
            sum(signal in anc for anc in out_anc), base/denom])
    return np.asarray(output, dtype=np.float32)

def random_circuit(rng, n, ng):
    # Common, nonconstant binary operators; repairs can use all 16 LUTs.
    tables = [6, 8, 14, 7, 1, 9, 11, 13, 2, 4]
    gates = []
    for j in range(ng):
        a, b = rng.sample(range(n+j), 2)
        gates.append((a,b,rng.choice(tables)))
    return Circuit(n, tuple(gates), tuple(n+j for j in range(ng-3, ng)))

def make_case(seed, n, ng, count):
    rng = random.Random(seed)
    fullrows = list(range(1<<n))
    for _ in range(200):
        gold = random_circuit(rng, n, ng)
        target = evaluate(gold, fullrows)
        active = sorted(set.union(*(ancestors(gold,o) for o in gold.outputs)))
        active = [s-n for s in active if s>=n]
        j = rng.choice(active)
        mode = rng.choices(['lut','wire','permanent'], [0.4,0.4,0.2])[0]
        if mode == 'permanent':
            damaged = Circuit(n,gold.gates,gold.outputs,j,rng.randrange(2))
        elif mode == 'lut':
            damaged = apply(gold, ('lut',j,2,gold.gates[j][2] ^ (1<<rng.randrange(4))))
        else:
            slot = rng.randrange(2)
            alternatives = [x for x in range(n+j) if x != gold.gates[j][slot]]
            damaged = apply(gold, ('wire',j,slot,rng.choice(alternatives)))
        if evaluate(damaged,fullrows) == target: continue
        rows = rng.sample(fullrows,min(count,len(fullrows)))
        sample_target = evaluate(gold,rows)
        edits = list(legal_edits(damaged))
        # Labels/correctness computed separately, never passed to features().
        labels = np.array([evaluate(apply(damaged,e),fullrows)==target for e in edits], dtype=bool)
        return {'seed':seed, 'mode':mode, 'c':damaged, 'rows':rows, 'target':target,
                'sample_target':sample_target, 'edits':edits, 'labels':labels,
                'X':features(damaged,edits,rows,sample_target),
                'gold':gold}
    raise RuntimeError('could not generate a harmful fault')

def build_cases(start, amount, sizes, count):
    cases = []
    t = time.perf_counter()
    for i in range(amount):
        n,ng = sizes[i%len(sizes)]
        cases.append(make_case(start+i,n,ng,count))
    print(json.dumps({'generated':amount,'start_seed':start,'seconds':round(time.perf_counter()-t,3)}),flush=True)
    return cases

def evaluate_rankings(cases, model):
    records = []
    t_features = t_predict = 0.0
    for case in cases:
        # Timing includes constructing candidate/sample predictions.
        t = time.perf_counter()
        X = features(case['c'],case['edits'],case['rows'],case['sample_target'])
        t_features += time.perf_counter()-t
        t = time.perf_counter()
        probs = model.predict_proba(X)[:,1]
        t_predict += time.perf_counter()-t
        rng = np.random.default_rng(case['seed']+71)
        tie = rng.random(len(X))
        orders = {
            'learned':np.lexsort((tie,-probs)),
            'sample_greedy':np.lexsort((tie,X[:,0])),
            'sample_greedy_small_edit':np.lexsort((tie,X[:,10],X[:,0])),
            'random':np.argsort(tie),
        }
        row = {'seed':case['seed'],'inputs':case['c'].n,'gates':len(case['c'].gates),
               'fault':case['mode'],'candidates':len(X),'repairable_one_edit':bool(case['labels'].any()),
               'sample_invisible_fault':err(evaluate(case['c'],case['rows']),case['sample_target'])==0}
        for name,order in orders.items():
            hits = np.flatnonzero(case['labels'][order])
            row[name+'_first_verified_repair'] = int(hits[0]+1) if len(hits) else None
        records.append(row)
    summary = {'total':len(cases),'repairable_one_edit':sum(r['repairable_one_edit'] for r in records),
               'sample_invisible_faults':sum(r['sample_invisible_fault'] for r in records),
               'feature_seconds':t_features,'predict_seconds':t_predict,'methods':{}}
    for name in orders:
        out = {}
        for budget in [1,4,16,64]:
            hits = sum(r[name+'_first_verified_repair'] is not None and r[name+'_first_verified_repair']<=budget for r in records)
            out[str(budget)] = {'successes':hits,'all_cases_rate':hits/len(records),
                'repairable_rate':hits/max(1,summary['repairable_one_edit'])}
        summary['methods'][name] = out
    return summary,records

def structural_witness():
    # The two output gates use a permanently dead XOR. Rewire to an existing
    # spare XOR preceding both consumers; no new gates or backwards edges.
    c = Circuit(3,((0,1,6),(0,1,6),(3,2,8),(3,2,6)),(5,6))
    d = Circuit(c.n,c.gates,c.outputs,0,0)
    repaired = apply(apply(d,('wire',2,0,4)),('wire',3,0,4))
    target = evaluate(c,range(8))
    assert evaluate(repaired,range(8)) == target
    return {'inputs':3,'gates':4,'permanent_fault_gate':0,'wire_edits':2,
            'all_input_assignments':8,'exact_equivalence':True,
            'fixed_wiring_input_support':[sorted(ancestors(d,o)&set(range(3))) for o in d.outputs],
            'target_depends_on_inputs':[0,1,2],
            'meaning':'Fixed wiring disconnects x0,x1 from both outputs; no LUT-only edit can recover their dependence. Two rewires use an existing spare XOR gate.'}

def run():
    root = ROOT/'outputs'/'circuit-pilot'
    root.mkdir(parents=True,exist_ok=True)
    start = time.perf_counter()
    count=8
    train=build_cases(10000,320,[(4,10),(4,12)],count)
    valid=build_cases(20000,100,[(4,10),(4,12)],count)
    test=build_cases(30000,240,[(5,14),(6,18)],count)
    X=np.concatenate([c['X'] for c in train])
    y=np.concatenate([c['labels'] for c in train])
    model=TinyForest(trees=32,depth=8,leaf=12,seed=20261025)
    t=time.perf_counter(); model.fit(X,y); fit=time.perf_counter()-t
    print(json.dumps({'train_candidates':len(y),'positive_candidates':int(y.sum()),'fit_seconds':fit}),flush=True)
    validation,validation_rows=evaluate_rankings(valid,model)
    testing,test_rows=evaluate_rankings(test,model)
    sensitivity={}
    for samples in [4,16]:
        recases=[make_case(40000+i,6,18,samples) for i in range(80)]
        sensitivity[str(samples)],_=evaluate_rankings(recases,model)
    result={'protocol':{'seed':20261025,'train_seed_range':[10000,10319],
        'validation_seed_range':[20000,20099],'test_seed_range':[30000,30239],
        'training_sizes':[[4,10],[4,12]],'test_sizes':[[5,14],[6,18]],
        'observed_specification_rows':count,'candidate_space':'one LUT replacement or one acyclic wire source replacement; permanently stuck gates cannot be edited',
        'verification':'exhaustive enumeration of all 2^n inputs; no approximate acceptance',
        'selected_hyperparameters_without_test_tuning':True,
        'warning':'Candidate feature generation simulates every legal edit on sampled inputs; verifier-query counts alone are not total compute.'},
        'environment':{'python':sys.version,'platform':platform.platform(),'processor':platform.processor(),'numpy':np.__version__},
        'training':{'circuits':len(train),'candidates':len(y),'positives':int(y.sum()),'fit_seconds':fit},
        'validation':validation,'test':testing,'sensitivity':sensitivity,
        'feature_importance':dict(sorted(zip(FEATURES,map(float,model.feature_importances_)),key=lambda p:-p[1])),
        'structural_witness':structural_witness(),
        'total_seconds':time.perf_counter()-start,
        'limitations':['synthetic small combinational DAGs','known reference specification',
            'single-edit learned ranker only','not a decentralised rule','no physical hardware',
            'not a reproduction or measured comparison to SODC or ICLR 2023',
            'global novelty and publication suitability not proven by this experiment']}
    (root/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (root/'model.json').write_text(json.dumps({'thresholds':[t.tolist() for t in model.thresholds],
        'trees':model.models,'features':FEATURES}),encoding='utf-8')
    with (root/'test_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(test_rows[0]));writer.writeheader();writer.writerows(test_rows)
    (root/'validation_cases.json').write_text(json.dumps(validation_rows,indent=2),encoding='utf-8')
    (root/'source.sha256').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),encoding='ascii')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': run()
