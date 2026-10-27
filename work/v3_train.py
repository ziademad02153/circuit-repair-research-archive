"""Three seeds per feature variant; validation-only seed selection, no v3 test."""
import json,time,hashlib,sys
from dataclasses import asdict
from circuit_pilot import ROOT,legal_edits,apply,TinyForest,make_case
from decisive_engine import make_problem,full_values
from local_repair_pilot import local_features,NAMES
from v3_features import no_need_features,KEEP,REMOVE
import numpy as np

OUT=ROOT/'outputs/ablation-cnf-v3'
PROTOCOL=ROOT/'experiments/ablation-cnf-v3/protocol.json'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=json.loads(PROTOCOL.read_text());assert digest(PROTOCOL)==(OUT/'protocol.sha256').read_text().strip()
    if (OUT/'models.freeze.json').exists():
        print('Training already frozen; nothing overwritten.');return
    files=['work/v3_features.py','work/v3_train.py','work/circuit_pilot.py','work/local_repair_pilot.py','work/decisive_engine.py']
    freeze={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'protocol_sha256':digest(PROTOCOL),
            'sources':{x:digest(ROOT/x) for x in files},
            'clarification':'repeat_reason says nine methods in prose; authoritative methods list contains ten and expected_trials=9000. No design or count change.'}
    target=OUT/'training.freeze.json'
    if target.exists():assert json.loads(target.read_text())['sources']==freeze['sources']
    else:target.write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    training=[];validation=[];case_records=[]
    t_all=time.perf_counter()
    with (OUT/'training.log.jsonl').open('a',encoding='utf-8',buffering=1) as log:
        def event(d):
            log.write(json.dumps(d)+'\n');print(json.dumps(d),flush=True)
        for split,start,count,dest in [('train',50000,480,training),('validation',60000,120,validation)]:
            for i in range(count):
                n,g=[(4,10),(5,14)][i%2];seed=start+i;case=make_problem(seed,n,g)
                c=case['c'];edits=list(legal_edits(c))
                labels=np.asarray([full_values(apply(c,e))==case['target'] for e in edits],dtype=bool)
                full=local_features(c,edits,case['rows'],case['sample_target'])
                no_need=no_need_features(c,edits,case['rows']);assert np.array_equal(no_need,full[:,KEEP])
                if i<4:
                    original=make_case(seed,n,g,8)
                    assert original['c']==c and original['gold']==case['gold'] and original['rows']==case['rows']
                    assert np.array_equal(labels,original['labels'])
                dest.append({'seed':seed,'X21':full,'X13':no_need,'y':labels})
                case_records.append({'split':split,'seed':seed,'gold':asdict(case['gold']),'damaged':asdict(c),
                    'rows':case['rows'],'sample_target':case['sample_target'],
                    'full_target_hex':[hex(v) for v in case['target']],'candidate_rows':len(edits),
                    'positive_candidates':int(labels.sum())})
                if (i+1)%60==0:event({'event':'data','split':split,'completed':i+1,'seconds':time.perf_counter()-t_all})
        with (OUT/'training_cases.jsonl').open('w',encoding='utf-8') as f:
            for r in case_records:f.write(json.dumps(r,separators=(',',':'))+'\n')
        y=np.concatenate([c['y'] for c in training])
        X21=np.concatenate([c['X21'] for c in training]);X13=np.concatenate([c['X13'] for c in training])
        np.savez_compressed(OUT/'training_arrays.npz',X21=X21,X13=X13,y=y,
            case_seeds=np.asarray([c['seed'] for c in training]),
            offsets=np.cumsum([0]+[len(c['y']) for c in training]))
        results=[]
        for variant,key,features in [('full21','X21',NAMES),('no_need13','X13',[NAMES[i] for i in KEEP])]:
            X=X21 if key=='X21' else X13
            for seed in p['training']['training_rng_seeds']:
                begin=time.perf_counter();m=TinyForest(trees=24,depth=9,leaf=12,seed=seed);m.fit(X,y)
                fit_seconds=time.perf_counter()-begin;m.compile();valid=[]
                for c in validation:
                    probs=m.predict_proba(c[key])[:,1]
                    tie=np.random.default_rng(c['seed']+17).random(len(probs));order=np.lexsort((tie,-probs))
                    hits=np.flatnonzero(c['y'][order]);rank=int(hits[0]+1) if len(hits) else None
                    valid.append({'case_seed':c['seed'],'first_valid_rank':rank,
                                  'success_top16':bool(rank is not None and rank<=16),
                                  'rank_clipped65':min(rank,65) if rank is not None else 65})
                weights={'variant':variant,'training_seed':seed,'trees':m.models,
                         'thresholds':[x.tolist() for x in m.thresholds],'features':features,
                         'architecture':{'trees':24,'depth':9,'leaf':12}}
                model_path=OUT/f'model_{variant}_{seed}.json'
                model_path.write_text(json.dumps(weights),encoding='utf-8')
                r={'variant':variant,'training_seed':seed,'fit_seconds':fit_seconds,
                   'training_candidates':len(y),'training_positive_candidates':int(y.sum()),
                   'validation_cases':len(valid),'validation_top16_successes':sum(x['success_top16'] for x in valid),
                   'validation_mean_clipped_rank':float(np.mean([x['rank_clipped65'] for x in valid])),
                   'model_file':str(model_path.relative_to(ROOT)),'model_sha256':digest(model_path),'validation_records':valid}
                results.append(r);event({'event':'fit_complete',**{k:v for k,v in r.items() if k!='validation_records'}})
        selected={}
        for variant in ['full21','no_need13']:
            best=min([r for r in results if r['variant']==variant],
                key=lambda r:(-r['validation_top16_successes'],r['validation_mean_clipped_rank'],r['training_seed']))
            selected[variant]={k:v for k,v in best.items() if k!='validation_records'}
        result={'all_models':results,'selected':selected,'training_seconds_total':time.perf_counter()-t_all,
                'training_cases_sha256':digest(OUT/'training_cases.jsonl'),'training_arrays_sha256':digest(OUT/'training_arrays.npz'),
                'protocol_sha256':digest(PROTOCOL),'no_test_outcomes_used_for_selection':True}
        (OUT/'training_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        models={r['model_file']:r['model_sha256'] for r in results}
        frozen={'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':selected,
                'all_model_hashes':models,'training_summary_sha256':digest(OUT/'training_summary.json'),
                'protocol_sha256':digest(PROTOCOL),'training_source_freeze_sha256':digest(OUT/'training.freeze.json')}
        (OUT/'models.freeze.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
        event({'event':'training_complete','selected':selected})


if __name__=='__main__':main()
