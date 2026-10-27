"""Prospectively frozen comparison; independent development selection and test."""
from __future__ import annotations
import sys,json,time,random,hashlib,multiprocessing as mp,platform
from dataclasses import asdict
from collections import defaultdict
from fairness_v2_methods import ROOT,RULES,METHODS,worker,independent_values
from decisive_engine import make_problem,full_values
from decisive_run import decode_circuit
from circuit_pilot import apply,legal_edits

OUT=ROOT/'outputs/fairness-v2';BUDGET=1.0
SIZES=[(6,18),(10,50),(10,100),(12,100),(16,100),(16,200)]


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def register():
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'preregistration.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    assert json.loads((OUT/'preflight.json').read_text())['status']=='passed'
    files=['work/circuit_pilot.py','work/local_repair_pilot.py','work/decisive_engine.py',
           'work/decisive_run.py','work/fairness_v2_methods.py','work/fairness_v2_run.py',
           'work/fairness_v2_validate.py']
    p={'registered_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       'question':'Does the frozen learner improve on an optimized simple rule selected before opening new test outcomes?',
       'groups':[{'group':f'n{n}_g{g}','n':n,'gates':g,'development_count':10,'test_count':50,
                  'development_start_seed':7000000+i*10000,'test_start_seed':8000000+i*10000}
                 for i,(n,g) in enumerate(SIZES)],
       'methods':METHODS,'development_methods':RULES,'test_repeats':2,'development_repeats':1,
       'budget_seconds':BUDGET,'settings':['full'],'sample_feature_rows':8,'edit_budget':1,
       'edit_space':'Same legal_edits: exactly one non-noop LUT or earlier-source wire edit; no edits to permanently stuck gate.',
       'faults':'Unchanged harmful-fault mixture: .4 LUT flip, .4 wire, .2 known permanent stuck-at; conditioned on changed outputs.',
       'model':'Original selected 24-tree model, feature function and inference; no fitting, recalibration, pruning or parameter tuning.',
       'rules':{'local_improvement':'Descending local need-error improvement, then ascending LUT edit distance, then seeded tie; optimized exact same keys as original local features.',
                'local_after_error':'Ascending local need-error after edit, then ascending LUT distance, then seeded tie.',
                'sample_error':'Ascending exact output error on 8 rows, then LUT distance, then seeded tie. Optimized downstream-only resimulation, no unnecessary global feature matrix.',
                'random':'Uniform seeded random priorities over the same candidate list.',
                'exhaustive':'Original lazy legal_edits order, common full checker.',
                'cegis':'Original frozen Z3 CEGIS including its sound cone localization. No claim this is best available SAT implementation.'},
       'selection':'After development only: maximize pooled success rate on n>=10, then minimize mean failure-penalized runtime there, then lexical rule name. Write selection.json before any test trial; cannot switch comparator after test.',
       'timing':'Serial steady-state worker; GC, imports, model loading/compile, shared input packing, problem generation and payload transfer excluded for every method. Candidate generation, all ranking/feature/inference work and full checking included. No progress IPC inside timer; buffered events sent after timing. Absolute 1 s method deadline; >1 s is failure. Parent watchdog at 1.20 s after acknowledgement, hardkill always failure.',
       'order':'Seeded random method order in repeat 0; reverse order in repeat 1 for each case. All circuits and methods retained.',
       'audit':'Every accepted edit independently checked with NumPy full truth-vector oracle outside timer, cached per case/edit. Gold references independently validated before trials. Raw logs retain all errors/timeouts and wrong acceptances.',
       'primary_population':'250 new larger circuits (n>=10), each equally weighted after averaging its two timed repeats.',
       'primary_endpoints':['success-rate difference learned minus development-selected simple rule',
                            'failure-penalized mean seconds advantage selected rule minus learned; failure charged full common budget'],
       'statistics':{'bootstrap_replicates':10000,'seed':20261108,
                     'resampling':'Paired by unique circuit, retaining repeats together; no independent resampling of repeats.',
                     'primary_interval':'97.5% two-sided percentile paired bootstrap per endpoint; Bonferroni family of two (>=95% simultaneous nominal coverage).',
                     'descriptive_intervals':'95% for all methods/groups, exploratory; do not replace primary comparator with a test winner.',
                     'decision':'Report evidence of benefit in a primary endpoint only if its 97.5% interval is strictly above zero. A general learned advantage requires success endpoint benefit without a significant penalized-runtime disadvantage, or penalized-runtime benefit without a significant success disadvantage. Conflicting endpoints are tradeoff, neither significant is not demonstrated. Do not claim global optimality or publication readiness.'},
       'scope_limits':['Synthetic test circuits, same generator family, limited sample size; no public/industrial benchmark result.',
                       'No model-without-need-feature retraining in this stage; does not fully identify contribution of the need representation.',
                       'Only one wall budget here; budget sensitivity and stronger CNF SAT remain future stages.',
                       'No sample-only inference claims; all accepted repairs must pass full specification.'],
       'model_sha256':digest(ROOT/'outputs/local-repair-pilot/selected_model.json'),
       'source_sha256':{x:digest(ROOT/x) for x in files},'preflight_sha256':digest(OUT/'preflight.json'),
       'v1_protected_sha256':{x:digest(ROOT/x) for x in ['outputs/decisive-repair/raw_trials.jsonl',
           'outputs/decisive-repair/cases.jsonl','outputs/decisive-repair/preregistration.json',
           'outputs/decisive-repair/summary.json']},
       'python':sys.version,'platform':platform.platform()}
    path.write_text(json.dumps(p,indent=2),encoding='utf-8');return p


def check_frozen(p):
    for rel,h in {**p['source_sha256'],**p['v1_protected_sha256']}.items():assert digest(ROOT/rel)==h,rel
    assert digest(ROOT/'outputs/local-repair-pilot/selected_model.json')==p['model_sha256']
    assert digest(OUT/'preflight.json')==p['preflight_sha256']


def generate(p):
    path=OUT/'cases.jsonl';marker=OUT/'cases.complete'
    if marker.exists():assert digest(path)==marker.read_text().strip();return
    assert not path.exists(),'Unfinished generation; preserve and inspect rather than overwrite.'
    previous={r['seed'] for r in map(json.loads,(ROOT/'outputs/decisive-repair/cases.jsonl').read_text().splitlines())}
    fingerprints=set();count=0
    with path.open('w',encoding='utf-8') as f:
        for phase in ['development','test']:
            for g in p['groups']:
                for i in range(g[phase+'_count']):
                    seed=g[phase+'_start_seed']+i
                    assert seed not in previous and seed>=7000000
                    case=make_problem(seed,g['n'],g['gates']);c=case['c']
                    assert independent_values(case['gold'])==case['target']
                    assert independent_values(c)==full_values(c)
                    fp=hashlib.sha256(json.dumps(asdict(case['gold']),sort_keys=True).encode()).hexdigest()
                    assert fp not in fingerprints,'duplicate gold circuit';fingerprints.add(fp)
                    rec={'case_id':f"{phase}:{g['group']}:{i}",'phase':phase,'group':g['group'],
                         'seed':seed,'fault_type':case['fault_type'],'generation_attempt':case['attempt'],
                         'damaged':asdict(c),'gold':asdict(case['gold']),'rows':case['rows'],
                         'sample_target':case['sample_target'],'full_target_hex':[hex(x) for x in case['target']],
                         'gold_fingerprint':fp}
                    f.write(json.dumps(rec,separators=(',',':'))+'\n');count+=1
    marker.write_text(digest(path),encoding='ascii')
    print(json.dumps({'event':'generated','cases':count}),flush=True)


class Runner:
    def __init__(self,eventlog):self.log=eventlog;self.process=None;self.restarts=0
    def start(self):
        parent,child=mp.Pipe();self.process=mp.Process(target=worker,args=(child,),daemon=True)
        self.process.start();self.pipe=parent
        if not parent.poll(120):raise RuntimeError('worker startup timeout')
        event=parent.recv();assert event['event']=='ready';self.log.write(json.dumps(event)+'\n')
    def stop(self):
        if self.process:
            if self.process.is_alive():self.process.terminate()
            self.process.join(2);self.pipe.close();self.process=None
    def trial(self,payload,method,key):
        if self.process is None:self.start()
        self.pipe.send((payload,method,BUDGET))
        if not self.pipe.poll(10):raise RuntimeError('missing start acknowledgement')
        assert self.pipe.recv()['event']=='started';t=time.perf_counter()
        if not self.pipe.poll(BUDGET+.20):
            elapsed=time.perf_counter()-t;self.stop();self.restarts+=1
            return {'status':'timeout','elapsed':elapsed,'hard_kill':True}
        result=self.pipe.recv();assert result['event']=='result'
        self.log.write(json.dumps({'trial_id':key,**result})+'\n')
        return result


def select(p):
    path=OUT/'selection.json'
    if path.exists():return json.loads(path.read_text())
    rows=[json.loads(x) for x in (OUT/'raw_trials.jsonl').read_text().splitlines()]
    dev=[r for r in rows if r['phase']=='development'];assert len(dev)==180
    assert not any(r['phase']=='test' for r in rows)
    scores=[]
    for method in RULES:
        rr=[r for r in dev if r['method']==method and r['inputs']>=10];assert len(rr)==50
        scores.append({'method':method,'cases':len(rr),'successes':sum(r['success'] for r in rr),
                       'mean_penalized_seconds':sum(r['failure_penalized_seconds'] for r in rr)/len(rr)})
    chosen=min(scores,key=lambda x:(-x['successes'],x['mean_penalized_seconds'],x['method']))['method']
    record={'selected_rule':chosen,'scores':scores,'selected_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'development_log_sha256_at_selection':digest(OUT/'raw_trials.jsonl'),'test_trials_seen':0}
    path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'event':'development_selection',**record}),flush=True);return record


def main():
    p=register();check_frozen(p)
    if '--register-only' in sys.argv:print(json.dumps(p,indent=2));return
    generate(p);done=set();raw=OUT/'raw_trials.jsonl'
    if raw.exists():done={json.loads(s)['trial_id'] for s in raw.read_text().splitlines()}
    start=time.perf_counter();count=0
    with raw.open('a',encoding='utf-8',buffering=1) as f,(OUT/'events.jsonl').open('a',encoding='utf-8',buffering=1) as events:
        runner=Runner(events)
        try:
            records=[json.loads(s) for s in (OUT/'cases.jsonl').read_text().splitlines()]
            for phase in ['development','test']:
                if phase=='test':selection=select(p)
                for rec in records:
                    if rec['phase']!=phase:continue
                    c=decode_circuit(rec['damaged']);target=tuple(int(x,16) for x in rec['full_target_hex'])
                    payload={'c':c,'seed':rec['seed'],'rows':rec['rows'],
                             'sample_target':tuple(rec['sample_target']),'target_full':target,'setting':'full'}
                    assert 'gold' not in payload
                    methods=(RULES if phase=='development' else METHODS).copy()
                    random.Random(rec['seed']+901).shuffle(methods);audit_cache={}
                    for repeat in range(p[phase+'_repeats']):
                        order=methods if repeat==0 else methods[::-1]
                        for position,method in enumerate(order):
                            key=f"{rec['case_id']}:{repeat}:{method}"
                            if key in done:continue
                            result=runner.trial(payload,method,key)
                            accepted=result['status']=='accepted' and result['elapsed']<=BUDGET
                            correct=False;audited=False;wrong_rows=None;t=time.perf_counter()
                            if accepted:
                                edit=tuple(result['edit'])
                                kind,j,slot,value=edit
                                assert j!=c.stuck and 0<=j<len(c.gates)
                                assert (slot==2 and 0<=value<16 and value!=c.gates[j][2]) if kind=='lut' else (kind=='wire' and slot in [0,1] and 0<=value<c.n+j and value!=c.gates[j][slot])
                                if edit not in audit_cache:audit_cache[edit]=independent_values(apply(c,edit))
                                vals=audit_cache[edit];diff=0
                                for a,b in zip(vals,target):diff|=a^b
                                correct=diff==0;wrong_rows=diff.bit_count();audited=True
                            row={'trial_id':key,'case_id':rec['case_id'],'phase':phase,'group':rec['group'],
                                 'seed':rec['seed'],'inputs':c.n,'gates':len(c.gates),'fault_type':rec['fault_type'],
                                 'method':method,'repeat':repeat,'position':position,'budget_seconds':BUDGET,
                                 'accepted':bool(accepted),'success':bool(accepted and correct),
                                 'wrong_accepted':bool(accepted and not correct),'independent_audited':audited,
                                 'audit_wrong_rows':wrong_rows,'audit_seconds_excluded':time.perf_counter()-t,
                                 'failure_penalized_seconds':result['elapsed'] if accepted and correct else BUDGET,
                                 **{k:v for k,v in result.items() if k not in ['event','progress_events']}}
                            f.write(json.dumps(row,separators=(',',':'))+'\n');done.add(key);count+=1
                            if result['status']=='error':raise RuntimeError(result)
                            if count%35==0:
                                print(json.dumps({'event':'progress','completed':len(done),'expected':4380,
                                                  'phase':phase,'group':rec['group'],'seconds':time.perf_counter()-start}),flush=True)
        finally:runner.stop()
    check_frozen(p);assert len(done)==4380
    (OUT/'run.complete').write_text(json.dumps({'trials':len(done),'raw_sha256':digest(raw),
        'cases_sha256':digest(OUT/'cases.jsonl'),'selection_sha256':digest(OUT/'selection.json'),
        'seconds_this_run':time.perf_counter()-start},indent=2),encoding='utf-8')
    print(json.dumps({'event':'complete','trials':len(done)}),flush=True)


if __name__=='__main__':mp.freeze_support();main()
