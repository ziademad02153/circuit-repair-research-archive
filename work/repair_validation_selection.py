"""Choose forest size on validation only, then use NEW test seeds.

Exploratory model development after the two earlier pilots. Their test outcomes
motivated this experiment and are not called confirmatory evidence. All tried
ensemble sizes and their validation results are retained.
"""
import json,time,copy,csv
from circuit_pilot import ROOT,TinyForest,make_case,features,evaluate,apply
from local_repair_pilot import local_features
from repair_followup import load,deploy
import numpy as np

def prefix(base,size):
    m=TinyForest(trees=size,depth=base.depth,leaf=base.leaf,seed=base.seed)
    m.thresholds=base.thresholds;m.models=base.models[:size];return m

def run():
    folder=ROOT/'outputs/local-repair-pilot';base=load();start=time.perf_counter()
    choices=[4,8,16,24,48];models={n:prefix(base,n) for n in choices}
    validation={str(n):{'successes_at_16':0,'cases':120,'predict_seconds':0.0} for n in choices}
    for i in range(120):
        n,g=[(4,10),(5,14)][i%2]
        case=make_case(60000+i,n,g,8)
        X=local_features(case['c'],case['edits'],case['rows'],case['sample_target'])
        tie=np.random.default_rng(case['seed']+17).random(len(X))
        for size,m in models.items():
            t=time.perf_counter();p=m.predict_proba(X)[:,1]
            validation[str(size)]['predict_seconds']+=time.perf_counter()-t
            ids=np.lexsort((tie,-p))[:16]
            validation[str(size)]['successes_at_16']+=int(case['labels'][ids].any())
    # Maximum validation success count; break ties toward smaller model.
    chosen=max(choices,key=lambda n:(validation[str(n)]['successes_at_16'],-n))
    selection={'scope':'exploratory; validation-only ensemble-size selection followed by unused test seeds',
        'validation':validation,'selected_trees':chosen,'selection_rule':'highest validation success at 16 checks; ties use fewer trees',
        'test_seeds':[90000,90399],'test_count':400,'test_sizes':[[6,18],[7,22]],
        'no_model_changes_after_opening_these_test_cases':True}
    (folder/'selection_protocol.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    model=models[chosen];records=[]
    for i in range(400):
        n,g=[(6,18),(7,22)][i%2];case=make_case(90000+i,n,g,8)
        rec={'seed':case['seed'],'inputs':n,'gates':g,'fault':case['mode'],
             'one_edit_repairable':bool(case['labels'].any())}
        # Alternate order; input packing and both models warmed before timing.
        order=['learned_local','global_small_edit'] if i%2==0 else ['global_small_edit','learned_local']
        for name in order:rec[name]=deploy(case,model,name,budget=16)
        records.append(rec)
    summary={'cases':400,'one_edit_repairable':sum(r['one_edit_repairable'] for r in records),'methods':{}}
    for name in ['learned_local','global_small_edit']:
        summary['methods'][name]={'successes':sum(r[name]['success'] for r in records),
            'mean_ms':float(np.mean([r[name]['end_to_end_ms'] for r in records])),
            'median_ms':float(np.median([r[name]['end_to_end_ms'] for r in records])),
            'mean_checks':float(np.mean([r[name]['checks'] for r in records]))}
    dif=np.asarray([int(r['learned_local']['success'])-int(r['global_small_edit']['success']) for r in records])
    rng=np.random.default_rng(20261027)
    boot=np.asarray([rng.choice(dif,len(dif),replace=True).mean() for _ in range(4000)])
    summary['paired_success_difference']={'difference':float(dif.mean()),'bootstrap_95_percent':list(map(float,np.quantile(boot,[.025,.975])))}
    ratio=[]
    a=np.asarray([r['learned_local']['end_to_end_ms'] for r in records]);b=np.asarray([r['global_small_edit']['end_to_end_ms'] for r in records])
    for _ in range(4000):
        ids=rng.integers(0,len(records),len(records));ratio.append(float(b[ids].mean()/a[ids].mean()))
    summary['mean_runtime_ratio_global_over_local']={'ratio':float(b.mean()/a.mean()),
        'paired_bootstrap_95_percent':list(map(float,np.quantile(ratio,[.025,.975])))}
    result={'protocol':selection,'test':summary,'seconds':time.perf_counter()-start,'cases':records}
    (folder/'selected_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (folder/'selected_model.json').write_text(json.dumps({'thresholds':[t.tolist() for t in model.thresholds],
        'trees':model.models,'features':__import__('local_repair_pilot').NAMES}),encoding='utf-8')
    print(json.dumps({'protocol':selection,'test':summary,'seconds':result['seconds']},indent=2),flush=True)

if __name__=='__main__':run()
