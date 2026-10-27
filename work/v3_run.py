"""Freeze implementation, then run actual independent trials for every budget."""
from __future__ import annotations
import json,time,hashlib,sys,random,platform,multiprocessing as mp
from v3_methods import ROOT,OUT,worker,independent_values
from decisive_run import decode_circuit
from circuit_pilot import apply
import pysat,z3,numpy as np

PROTOCOL=ROOT/'experiments/ablation-cnf-v3/protocol.json'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    p=json.loads(PROTOCOL.read_text());assert digest(PROTOCOL)==(OUT/'protocol.sha256').read_text().strip()
    for path,h in p['protected_sha256'].items():assert digest(ROOT/path)==h,path
    mf=json.loads((OUT/'models.freeze.json').read_text())
    for path,h in mf['all_model_hashes'].items():assert digest(ROOT/path)==h,path
    assert digest(OUT/'training_summary.json')==mf['training_summary_sha256']
    assert json.loads((OUT/'preflight.json').read_text())['status']=='passed'
    files=['work/v3_features.py','work/v3_train.py','work/v3_cnf.py','work/v3_validate.py',
           'work/v3_methods.py','work/v3_run.py','work/requirements-v3.txt',
           'work/decisive_run.py','work/fairness_v2_methods.py','work/decisive_engine.py',
           'work/circuit_pilot.py','work/local_repair_pilot.py']
    hashes={x:digest(ROOT/x) for x in files}
    path=OUT/'implementation.freeze.json'
    record={'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'protocol_sha256':digest(PROTOCOL),
            'sources':hashes,'models_freeze_sha256':digest(OUT/'models.freeze.json'),
            'preflight_sha256':digest(OUT/'preflight.json'),'backend':'g42',
            'versions':{'python_sat':pysat.__version__,'z3':z3.get_version_string(),'numpy':np.__version__,
                        'python':sys.version,'platform':platform.platform()},
            'clarification':'Initial repeat_reason prose says nine methods; authoritative methods list and expected count specify ten methods and 9000 trials.'}
    if path.exists():
        old=json.loads(path.read_text());assert old['sources']==hashes
        assert old['models_freeze_sha256']==record['models_freeze_sha256']
        assert old['preflight_sha256']==record['preflight_sha256']
    else:path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    return p


class Runner:
    def __init__(self,events):self.events=events;self.process=None;self.restarts=0
    def start(self):
        parent,child=mp.Pipe();self.process=mp.Process(target=worker,args=(child,),daemon=True)
        self.process.start();self.pipe=parent
        if not parent.poll(120):raise RuntimeError('worker startup timeout')
        event=parent.recv();assert event['event']=='ready';self.events.write(json.dumps(event)+'\n')
    def stop(self):
        if self.process:
            if self.process.is_alive():self.process.terminate()
            self.process.join(2);self.pipe.close();self.process=None
    def trial(self,payload,method,budget,key):
        if self.process is None:self.start()
        self.pipe.send((payload,method,budget))
        if not self.pipe.poll(10):raise RuntimeError('missing start acknowledgement')
        assert self.pipe.recv()['event']=='started';t=time.perf_counter()
        if not self.pipe.poll(budget+.25):
            elapsed=time.perf_counter()-t;self.stop();self.restarts+=1
            return {'status':'timeout','elapsed':elapsed,'hard_kill':True,'checks':None}
        result=self.pipe.recv();assert result['event']=='result'
        self.events.write(json.dumps({'trial_id':key,**result})+'\n');return result


def main():
    p=freeze()
    if '--freeze-only' in sys.argv:print(json.dumps({'status':'frozen','trials':p['expected_trials']}));return
    source=ROOT/p['case_source'].split(';')[0]
    assert digest(source)==p['case_source_sha256']
    cases=[json.loads(x) for x in source.read_text().splitlines() if json.loads(x)['phase']=='test']
    assert len(cases)==300
    own=OUT/'cases.jsonl'
    if not own.exists():
        with own.open('w',encoding='utf-8') as f:
            for c in cases:f.write(json.dumps(c,separators=(',',':'))+'\n')
    else:assert [json.loads(x) for x in own.read_text().splitlines()]==cases
    random.Random(20261112).shuffle(cases)
    raw=OUT/'raw_trials.jsonl';done=set()
    if raw.exists():done={json.loads(x)['trial_id'] for x in raw.read_text().splitlines()}
    t_all=time.perf_counter();count=0
    with raw.open('a',encoding='utf-8',buffering=1) as log,(OUT/'events.jsonl').open('a',encoding='utf-8',buffering=1) as events:
        runner=Runner(events)
        try:
            for case_index,rec in enumerate(cases):
                c=decode_circuit(rec['damaged']);gold=decode_circuit(rec['gold'])
                target=tuple(int(v,16) for v in rec['full_target_hex'])
                assert independent_values(gold)==target
                payload={'c':c,'seed':rec['seed'],'rows':rec['rows'],
                         'sample_target':tuple(rec['sample_target']),'target_full':target,'setting':'full'}
                assert 'gold' not in payload
                budgets=p['budgets_seconds'].copy();random.Random(rec['seed']+1111).shuffle(budgets)
                audit_cache={}
                for budget_position,budget in enumerate(budgets):
                    methods=p['methods'].copy();random.Random(rec['seed']*100000+int(budget*1000)).shuffle(methods)
                    for position,method in enumerate(methods):
                        key=f"{rec['case_id']}:{budget:.1f}:{method}"
                        if key in done:continue
                        r=runner.trial(payload,method,budget,key)
                        accepted=r['status']=='accepted' and r['elapsed']<=budget
                        correct=False;audited=False;wrong_rows=None;ta=time.perf_counter()
                        if accepted:
                            edit=tuple(r['edit']);kind,j,slot,value=edit
                            assert j!=c.stuck and 0<=j<len(c.gates)
                            assert (slot==2 and 0<=value<16 and value!=c.gates[j][2]) if kind=='lut' else (kind=='wire' and slot in [0,1] and 0<=value<c.n+j and value!=c.gates[j][slot])
                            if edit not in audit_cache:audit_cache[edit]=independent_values(apply(c,edit))
                            delta=0
                            for a,b in zip(audit_cache[edit],target):delta|=a^b
                            correct=delta==0;wrong_rows=delta.bit_count();audited=True
                        row={'trial_id':key,'case_id':rec['case_id'],'group':rec['group'],'seed':rec['seed'],
                             'case_order':case_index,'budget_order':budget_position,'method_order':position,
                             'inputs':c.n,'gates':len(c.gates),'fault_type':rec['fault_type'],'method':method,
                             'budget_seconds':budget,'accepted':bool(accepted),'success':bool(accepted and correct),
                             'wrong_accepted':bool(accepted and not correct),'independent_audited':audited,
                             'audit_wrong_rows':wrong_rows,'audit_seconds_excluded':time.perf_counter()-ta,
                             'failure_penalized_seconds':r['elapsed'] if accepted and correct else budget,
                             **{k:v for k,v in r.items() if k not in ['event','progress_events']}}
                        log.write(json.dumps(row,separators=(',',':'))+'\n');done.add(key);count+=1
                        if row['status']=='error' or row['wrong_accepted']:raise RuntimeError(row)
                        if count%30==0:
                            print(json.dumps({'event':'progress','completed':len(done),'expected':p['expected_trials'],
                                'case_order':case_index,'case_group':rec['group'],'seconds':time.perf_counter()-t_all,
                                'worker_restarts':runner.restarts}),flush=True)
        finally:runner.stop()
    freeze();assert len(done)==p['expected_trials']
    (OUT/'run.complete').write_text(json.dumps({'trials':len(done),'raw_sha256':digest(raw),
        'case_sha256':digest(own),'seconds_this_run':time.perf_counter()-t_all,
        'implementation_freeze_sha256':digest(OUT/'implementation.freeze.json')},indent=2),encoding='utf-8')
    print(json.dumps({'event':'complete','trials':len(done)}),flush=True)


if __name__=='__main__':mp.freeze_support();main()
