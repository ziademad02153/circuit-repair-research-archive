"""Second, separately held-out pilot: shared local repair proposals.

Boolean need messages propagate backwards through the DAG. A shared small
forest ranks LUT/rewiring edits using local signals and need messages only.
Global exhaustive verification ACCEPTS proposals, but does not supply their
ranking features. This is a hybrid proposal-and-check system, not fully
decentralised execution. The first pilot's test seeds are not reused.
"""
from __future__ import annotations
import json,time,random,csv,hashlib,sys
from pathlib import Path
from collections import Counter
from circuit_pilot import Circuit,lut,signals,evaluate,apply,legal_edits,err,TinyForest,ROOT
import numpy as np

NAMES=['local_after_error','local_improvement','need_fraction','need_conflict',
       'kind_lut','kind_wire','lut_edit_distance','old_lut_ones','new_lut_ones',
       'fanout','is_output','source_is_input','source_is_stuck','source_gap',
       'source_ones','source_similarity','local_change','before_error',
       'source_after_error','required_zero_fraction','required_one_fraction']

def local_features(c,edits,rows,target):
    mask=(1<<len(rows))-1;size=len(rows)
    val=signals(c,rows)
    zero=[0]*len(val);one=[0]*len(val)
    for signal,t in zip(c.outputs,target):
        zero[signal]|=mask^t;one[signal]|=t
    # Each step is a message along an actual wire. This reverse-DAG schedule
    # uses O(depth) synchronous local rounds if implemented in parallel.
    for j in reversed(range(len(c.gates))):
        if j==c.stuck:continue
        z,o=zero[c.n+j],one[c.n+j]
        a,b,table=c.gates[j]
        for parent,other,left in [(a,val[b],True),(b,val[a],False)]:
            out0=lut(0,other,table,mask) if left else lut(other,0,table,mask)
            out1=lut(mask,other,table,mask) if left else lut(other,mask,table,mask)
            bad0=(z&out0)|(o&(mask^out0))
            bad1=(z&out1)|(o&(mask^out1))
            zero[parent]|=bad1&(mask^bad0)
            one[parent]|=bad0&(mask^bad1)
    fanout=Counter(x for g in c.gates for x in g[:2])
    X=[]
    for kind,j,slot,value in edits:
        a,b,table=c.gates[j];signal=c.n+j
        z,o=zero[signal],one[signal]
        old=val[signal]
        src=value if kind=='wire' else a
        old_src=(a,b)[slot] if kind=='wire' else a
        nt=value if kind=='lut' else table
        aa=val[src] if kind=='wire' and slot==0 else val[a]
        bb=val[src] if kind=='wire' and slot==1 else val[b]
        new=lut(aa,bb,nt,mask)
        before=((z&old)|(o&(mask^old))).bit_count()/size
        after=((z&new)|(o&(mask^new))).bit_count()/size
        X.append([after,before-after,(z|o).bit_count()/size,(z&o).bit_count()/size,
            float(kind=='lut'),float(kind=='wire'),(table^nt).bit_count()/4,
            table.bit_count()/4,nt.bit_count()/4,fanout[signal],float(signal in c.outputs),
            float(src<c.n),float(c.stuck>=0 and src==c.n+c.stuck),
            (signal-src)/(c.n+len(c.gates)),val[src].bit_count()/size,
            1-(val[src]^val[old_src]).bit_count()/size,(new^old).bit_count()/size,
            before,((z&val[src])|(o&(mask^val[src]))).bit_count()/size,
            z.bit_count()/size,o.bit_count()/size])
    return np.asarray(X,dtype=np.float32)

def build(start,amount,sizes,samples):
    # Imported generator includes the same fault distribution as pilot 1, but
    # we retain neither its global candidate features nor any gold-circuit
    # information in local_features.
    from circuit_pilot import make_case
    out=[];t=time.perf_counter()
    for i in range(amount):
        n,ng=sizes[i%len(sizes)]
        case=make_case(start+i,n,ng,samples)
        case['global_X']=case.pop('X')
        case['X']=local_features(case['c'],case['edits'],case['rows'],case['sample_target'])
        out.append(case)
        if (i+1)%100==0:
            print(json.dumps({'stage':start,'done':i+1,'seconds':round(time.perf_counter()-t,2)}),flush=True)
    return out

def test(cases,model):
    records=[];local_times=[];global_times=[];predict_times=[];verification_times=[]
    methods=['learned_local','local_greedy','global_sample_greedy','global_small_edit','exhaustive_order']
    from circuit_pilot import features
    for case in cases:
        c=case['c'];edits=case['edits'];rows=case['rows'];target=case['sample_target']
        t=time.perf_counter();X=local_features(c,edits,rows,target);local_times.append(time.perf_counter()-t)
        t=time.perf_counter();probs=model.predict_proba(X)[:,1];predict_times.append(time.perf_counter()-t)
        t=time.perf_counter();gx=features(c,edits,rows,target);global_times.append(time.perf_counter()-t)
        tie=np.random.default_rng(case['seed']+17).random(len(X))
        orders={
            'learned_local':np.lexsort((tie,-probs)),
            'local_greedy':np.lexsort((tie,X[:,6],-X[:,1])),
            'global_sample_greedy':np.lexsort((tie,gx[:,0])),
            'global_small_edit':np.lexsort((tie,gx[:,10],gx[:,0])),
            'exhaustive_order':np.arange(len(X))}
        record={'seed':case['seed'],'inputs':c.n,'gates':len(c.gates),'fault':case['mode'],
            'one_edit_repairable':bool(case['labels'].any()),'candidates':len(X)}
        for name,order in orders.items():
            hits=np.flatnonzero(case['labels'][order])
            record[name]=int(hits[0]+1) if len(hits) else None
        # Measure actual exhaustive check latency independently. No training
        # pair is used by the proposer. Checking n=6..7 means 64..128 inputs.
        t=time.perf_counter()
        for e in edits[:16]:evaluate(apply(c,e),range(1<<c.n))==case['target']
        verification_times.append((time.perf_counter()-t)/min(16,len(edits)))
        records.append(record)
    N=len(cases);R=sum(r['one_edit_repairable'] for r in records)
    result={'cases':N,'one_edit_repairable':R,'methods':{},'timing_ms':{
        'local_features_mean':1000*float(np.mean(local_times)),
        'learned_ranking_mean':1000*float(np.mean(predict_times)),
        'global_features_mean':1000*float(np.mean(global_times)),
        'one_exact_verification_mean':1000*float(np.mean(verification_times))}}
    for name in methods:
        result['methods'][name]={str(b):{'success':sum(r[name] is not None and r[name]<=b for r in records),
            'total':N} for b in [1,4,16,64]}
    # Paired bootstrap: uncertainty concerns synthetic circuit sampling only.
    rng=np.random.default_rng(9001)
    for base in ['global_sample_greedy','global_small_edit','local_greedy']:
        dif=np.asarray([int(r['learned_local'] is not None and r['learned_local']<=16)-
                        int(r[base] is not None and r[base]<=16) for r in records])
        boot=np.array([rng.choice(dif,len(dif),replace=True).mean() for _ in range(2000)])
        result.setdefault('paired_difference_at_16',{})[base]={'mean':float(dif.mean()),
            'bootstrap_95_percent':[float(v) for v in np.quantile(boot,[0.025,0.975])]}
    return result,records

def run():
    folder=ROOT/'outputs'/'local-repair-pilot';folder.mkdir(parents=True,exist_ok=True)
    protocol={'created':'2026-10-25','intent':'exploratory second pilot after seeing pilot 1; new held-out seeds',
        'train':{'seeds':[50000,50479],'sizes':[[4,10],[5,14]],'count':480},
        'validation':{'seeds':[60000,60119],'sizes':[[4,10],[5,14]],'count':120},
        'test':{'seeds':[70000,70399],'sizes':[[6,18],[7,22]],'count':400},
        'sampled_specification_rows':8,'primary_budget':16,
        'model':{'trees':48,'depth':9,'leaf':12,'seed':20261026},
        'no_post_test_hyperparameter_selection':True,
        'scope':'shared local proposer with global verifier; known stuck location; one-edit candidates; synthetic harmful faults conditional on changing outputs'}
    (folder/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    start=time.perf_counter()
    train=build(50000,480,[(4,10),(5,14)],8)
    valid=build(60000,120,[(4,10),(5,14)],8)
    X=np.concatenate([c['X'] for c in train]);y=np.concatenate([c['labels'] for c in train])
    model=TinyForest(trees=48,depth=9,leaf=12,seed=20261026)
    t=time.perf_counter();model.fit(X,y);fit=time.perf_counter()-t
    validation,_=test(valid,model)
    print(json.dumps({'validation':validation,'fit_seconds':fit}),flush=True)
    final=build(70000,400,[(6,18),(7,22)],8)
    result,records=test(final,model)
    output={'protocol':protocol,'training':{'cases':480,'candidate_rows':len(y),
        'positive_candidates':int(y.sum()),'fit_seconds':fit},'validation':validation,'test':result,
        'feature_importance':dict(sorted(zip(NAMES,map(float,model.feature_importances_)),key=lambda t:-t[1])),
        'total_seconds':time.perf_counter()-start,
        'limitations':['exploratory synthetic pilot','one-edit proposal space only','global verifier and scheduler remain',
            'message propagation is heuristic and not a new theorem','no claim of speedup over SAT/ECO tools',
            'no comparison to published learned controllers yet','not evidence of global novelty or acceptance probability']}
    (folder/'results.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    (folder/'model.json').write_text(json.dumps({'thresholds':[x.tolist() for x in model.thresholds],
        'trees':model.models,'features':NAMES}),encoding='utf-8')
    with (folder/'test_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=records[0].keys());writer.writeheader();writer.writerows(records)
    (folder/'source.sha256').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),encoding='ascii')
    print(json.dumps(output,indent=2),flush=True)

if __name__=='__main__':run()
