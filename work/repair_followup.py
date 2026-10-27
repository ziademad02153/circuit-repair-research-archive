"""Implementation-equivalence checks and fresh exploratory scaling test.

Defined after observing the second pilot; not a confirmatory held-out claim.
No model training or parameter selection is performed in this script.
"""
import json,time,sys
from pathlib import Path
from circuit_pilot import ROOT,TinyForest,make_case,features,evaluate,apply,legal_edits,Circuit
from local_repair_pilot import local_features
import numpy as np

def load():
    d=json.loads((ROOT/'outputs/local-repair-pilot/model.json').read_text())
    m=TinyForest(trees=48,depth=9,leaf=12,seed=20261026)
    m.thresholds=[np.asarray(t) for t in d['thresholds']];m.models=d['trees']
    return m

def deploy(case,model,method,budget=16):
    t=time.perf_counter();c=case['c'];edits=case['edits'];rows=case['rows'];target=case['sample_target']
    tie=np.random.default_rng(case['seed']+17).random(len(edits))
    if method=='learned_local':
        X=local_features(c,edits,rows,target)
        probabilities=model.predict_proba(X)[:,1]
        order=np.lexsort((tie,-probabilities))
    else:
        X=features(c,edits,rows,target)
        order=np.lexsort((tie,X[:,10],X[:,0]))
    rank_seconds=time.perf_counter()-t
    success=False;checks=0
    for idx in order[:budget]:
        checks+=1
        if evaluate(apply(c,edits[int(idx)]),range(1<<c.n))==case['target']:
            success=True;break
    return {'success':success,'checks':checks,'ranking_ms':1000*rank_seconds,
            'end_to_end_ms':1000*(time.perf_counter()-t)}

def run():
    folder=ROOT/'outputs/local-repair-pilot';model=load();start=time.perf_counter()
    # Independent implementation equivalence check after vectorizing inference.
    checks=[]
    for i in range(8):
        case=make_case(81000+i,5,14,8)
        X=local_features(case['c'],case['edits'],case['rows'],case['sample_target'])
        a=model.predict_proba(X);b=model.predict_proba_reference(X)
        delta=float(np.max(np.abs(a-b)));assert delta<1e-12
        checks.append({'seed':81000+i,'max_probability_difference':delta})
    records=[]
    for i in range(64):
        n,ng=[(8,28),(9,34)][i%2]
        case=make_case(82000+i,n,ng,8)
        result={'seed':82000+i,'inputs':n,'gates':ng,'fault':case['mode'],
                'one_edit_repairable':bool(case['labels'].any())}
        for method in ['learned_local','global_small_edit']:
            result[method]=deploy(case,model,method)
        records.append(result)
    summary={'cases':len(records),'scope':'fresh exploratory scaling test after observing pilot 2; not independent confirmation of novelty',
             'one_edit_repairable':sum(r['one_edit_repairable'] for r in records),
             'implementation_checks':checks,'methods':{}}
    for method in ['learned_local','global_small_edit']:
        summary['methods'][method]={
            'successes':sum(r[method]['success'] for r in records),
            'mean_end_to_end_ms':float(np.mean([r[method]['end_to_end_ms'] for r in records])),
            'median_end_to_end_ms':float(np.median([r[method]['end_to_end_ms'] for r in records])),
            'mean_exact_checks':float(np.mean([r[method]['checks'] for r in records]))}
    # Automatic learned proposal search on a two-rewire witness. This is ONE
    # illustrative example and is not included in statistical success rates.
    gold=Circuit(3,((0,1,6),(0,1,6),(3,2,8),(3,2,6)),(5,6))
    bad=Circuit(3,gold.gates,gold.outputs,0,0)
    target=evaluate(gold,range(8));frontier=[(bad,[])];found=None;exact_checks=0
    for depth in range(2):
        next_frontier=[]
        for c,path in frontier:
            edits=list(legal_edits(c));X=local_features(c,edits,list(range(8)),target)
            score=model.predict_proba(X)[:,1]
            order=np.argsort(-score,kind='stable')[:16]
            for i in order:
                edit=edits[int(i)];new=apply(c,edit);exact_checks+=1
                if evaluate(new,range(8))==target:found=path+[edit];break
                next_frontier.append((new,path+[edit]))
            if found:break
        if found:break
        frontier=next_frontier[:16]
    summary['illustrative_two_edit_witness']={'solved':found is not None,'edits':found,'exact_checks':exact_checks,
        'warning':'one selected small witness; no general multi-edit success claim'}
    summary['seconds']=time.perf_counter()-start
    (folder/'followup.json').write_text(json.dumps({'summary':summary,'cases':records},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':run()
