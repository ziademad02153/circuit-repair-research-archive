"""Pre-register, generate immutable cases, run sequential timed workers, audit logs."""
from __future__ import annotations
import sys,json,time,hashlib,itertools,random,multiprocessing as mp,platform,os
from pathlib import Path
from dataclasses import asdict
from decisive_engine import ROOT,Circuit,make_problem,worker,full_values,mismatch,apply

OUT=ROOT/'outputs'/'decisive-repair'
METHODS=['learned','cegis','exhaustive']
BUDGET=1.0

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def register():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'preregistration.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    groups=[{'group':'old400','n':None,'gates':None,'count':400,'start_seed':90000}]
    for idx,(n,g) in enumerate(itertools.product([10,12,16],[50,100,200])):
        groups.append({'group':f'n{n}_g{g}','n':n,'gates':g,'count':200,'start_seed':1000000+idx*10000})
    p={'registered_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       'groups':groups,'methods':METHODS,'settings':['full','sample'],
       'same_common_wall_clock_budget_seconds':BUDGET,
       'edit_budget':1,'edit_space':'exactly one non-noop LUT replacement or one earlier-source rewiring; same generator as legal_edits; stuck gates cannot be edited',
       'fault_model':'original harmful-fault generator: LUT flip .4, wrong wire .4, known stuck-at-0/1 gate .2; conditional on changed output',
       'sample_rows':8,'full':'All methods may use full truth-table checker. CEGIS starts from the same eight rows and adds actual counterexamples.',
       'sample':'Only eight uniformly sampled rows available during search/acceptance; full specification and gold circuit withheld from worker. Complete oracle audit afterward is excluded from method runtime.',
       'learned':'unchanged selected 24-tree model and feature code; all ranked candidates eligible until time budget, not the earlier 16-check cap',
       'exhaustive':'deterministic legal_edits order, check every edit directly; complete checker in full setting, sample checker in sample setting',
       'cegis':'Z3 symbolic one-edit encoding of same domain, sound localization to intersection of disagreeing-output cones and constant folding of unaffected gates. Incremental sampled-row constraints with complete-checker counterexamples in full setting. No complete oracle in sample setting.',
       'timing':'candidate generation, features, solver encoding/solving, ranking and all acceptance checks included. Excludes common problem generation, model loading/compilation, interpreter/solver imports, input bit-pattern preparation, payload transfer, and post-hoc audit. Only one method runs at a time. Order deterministically shuffled per circuit and setting.',
       'timeout':'deadline after 1.0 second. Cooperative checks, Z3 remaining-ms timeout, parent hard kill at 1.10 seconds. Any elapsed>1.0 or hard kill is a failure. Actual observed wall time and timeout counts retained.',
       'failure_penalized_runtime':'success uses actual elapsed; timeout, wrong acceptance, unsat, exhausted, or error uses the full 1.0-second budget. Raw actual runtimes also reported.',
       'criteria':{'rule':'learned useful iff on at least one larger FULL-specification group its paired success-rate advantage OR paired failure-penalized runtime advantage over CEGIS has 95% bootstrap interval strictly above zero. Otherwise exact required label: SAT/CEGIS dominates.',
                   'bootstrap_replicates':10000,'bootstrap_seed':20261025,
                   'confidence':.95,'multiple_testing':'unadjusted per comparison; additionally report Bonferroni simultaneous intervals for all 18 comparisons; primary label follows unadjusted user criterion',
                   'success':'accepted within budget and equivalent on every input; includes all requested cases in denominator',
                   'wrong_acceptance':'accepted within budget on available specification but differs on complete oracle; report wrong/accepted and wrong/all',
                   'no_tuning':True},
       'model_sha256':digest(ROOT/'outputs/local-repair-pilot/selected_model.json'),
       'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'work/decisive_engine.py',ROOT/'work/decisive_run.py',ROOT/'work/circuit_pilot.py',ROOT/'work/local_repair_pilot.py']},
       'python':sys.version,'platform':platform.platform()}
    path.write_text(json.dumps(p,indent=2),encoding='utf-8')
    return p

def encode_circuit(c):return asdict(c)
def decode_circuit(d):return Circuit(d['n'],tuple(tuple(x) for x in d['gates']),tuple(d['outputs']),d['stuck'],d['stuck_value'])

def generate(p):
    path=OUT/'cases.jsonl'
    if (OUT/'cases.complete').exists():return
    existing={}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            d=json.loads(line);existing[d['case_id']]=d
    old=json.loads((ROOT/'outputs/local-repair-pilot/selected_results.json').read_text(encoding='utf-8'))['cases']
    with path.open('a',encoding='utf-8',buffering=1) as f:
        for group in p['groups']:
            start=time.perf_counter()
            for i in range(group['count']):
                cid=group['group']+'_'+str(i)
                if cid in existing:continue
                n,g=([6,18] if i%2==0 else [7,22]) if group['group']=='old400' else [group['n'],group['gates']]
                d=make_problem(group['start_seed']+i,n,g)
                if group['group']=='old400':
                    assert d['seed']==old[i]['seed'] and d['fault_type']==old[i]['fault']
                rec={'case_id':cid,'group':group['group'],'index':i,'seed':d['seed'],
                     'fault_type':d['fault_type'],'generation_attempt':d['attempt'],
                     'damaged':encode_circuit(d['c']),'gold':encode_circuit(d['gold']),
                     'rows':d['rows'],'sample_target':d['sample_target'],
                     'full_target_hex':[hex(x) for x in d['target']]}
                f.write(json.dumps(rec,separators=(',',':'))+'\n')
            print(json.dumps({'event':'generated','group':group['group'],'seconds':time.perf_counter()-start}),flush=True)
    (OUT/'cases.complete').write_text(digest(path),encoding='ascii')

class Runner:
    def __init__(self,eventlog):self.eventlog=eventlog;self.process=None;self.pipe=None;self.restarts=0
    def start(self):
        parent,child=mp.Pipe();self.process=mp.Process(target=worker,args=(child,),daemon=True);self.process.start();self.pipe=parent
        if not parent.poll(120):raise RuntimeError('worker startup timeout')
        ready=parent.recv();assert ready['event']=='ready'
        self.eventlog.write(json.dumps({'event':'worker_ready','pid':self.process.pid,**ready})+'\n')
    def stop(self):
        if self.process is not None:
            if self.process.is_alive():self.process.terminate()
            self.process.join(2)
            self.pipe.close();self.process=None
    def trial(self,payload,method,key):
        if self.process is None:self.start()
        self.pipe.send((payload,method,BUDGET))
        if not self.pipe.poll(10):raise RuntimeError('worker did not acknowledge trial')
        event=self.pipe.recv();assert event['event']=='started'
        self.eventlog.write(json.dumps({'trial':key,**event})+'\n')
        parent_start=time.perf_counter();last={}
        while True:
            elapsed=time.perf_counter()-parent_start
            if elapsed>BUDGET+.10:
                self.stop();self.restarts+=1
                return {'status':'timeout','elapsed':elapsed,'hard_kill':True,'last_progress':last}
            if self.pipe.poll(min(.01,max(.001,BUDGET+.10-elapsed))):
                event=self.pipe.recv();self.eventlog.write(json.dumps({'trial':key,**event})+'\n')
                if event['event']=='result':return event
                last=event

def main():
    p=register()
    if '--register-only' in sys.argv:
        print(json.dumps(p,indent=2));return
    if '--generate-only' in sys.argv:generate(p);return
    # Refuse silent model/source changes after registration.
    assert digest(ROOT/'outputs/local-repair-pilot/selected_model.json')==p['model_sha256']
    for rel,sha in p['source_sha256'].items():assert digest(ROOT/rel)==sha,rel
    generate(p)
    casepath=OUT/'cases.jsonl';assert digest(casepath)==(OUT/'cases.complete').read_text().strip()
    done=set();rawpath=OUT/'raw_trials.jsonl'
    if rawpath.exists():
        for line in rawpath.read_text(encoding='utf-8').splitlines():done.add(json.loads(line)['trial_id'])
    runner=None;count=0;start=time.perf_counter()
    with (OUT/'events.jsonl').open('a',encoding='utf-8',buffering=1) as events,rawpath.open('a',encoding='utf-8',buffering=1) as out:
        runner=Runner(events)
        try:
            with casepath.open(encoding='utf-8') as cases:
                for line in cases:
                    rec=json.loads(line);c=decode_circuit(rec['damaged']);full=tuple(int(x,16) for x in rec['full_target_hex'])
                    for setting in p['settings']:
                        methods=METHODS.copy();random.Random(rec['seed']+(setting=='sample')).shuffle(methods)
                        payload={'seed':rec['seed'],'c':c,'rows':rec['rows'],'sample_target':tuple(rec['sample_target']),
                                 'setting':setting,'target_full':full if setting=='full' else None}
                        assert 'gold' not in payload
                        for method in methods:
                            key=f"{rec['case_id']}:{setting}:{method}"
                            if key in done:continue
                            result=runner.trial(payload,method,key)
                            accepted=result['status']=='accepted' and result['elapsed']<=BUDGET
                            correct=False;counterexample=None;wrong_rows=None
                            audit_start=time.perf_counter()
                            if accepted:
                                repaired=apply(c,tuple(result['edit']))
                                vals=full_values(repaired);diff=0
                                for x,y in zip(vals,full):diff|=x^y
                                correct=diff==0;wrong_rows=diff.bit_count()
                                counterexample=None if not diff else (diff&-diff).bit_length()-1
                            audit_elapsed=time.perf_counter()-audit_start
                            record={'trial_id':key,'case_id':rec['case_id'],'group':rec['group'],'seed':rec['seed'],
                                    'inputs':c.n,'gates':len(c.gates),'fault_type':rec['fault_type'],
                                    'setting':setting,'method':method,'budget_seconds':BUDGET,
                                    'accepted':accepted,'success':bool(accepted and correct),
                                    'wrong_accepted':bool(accepted and not correct),
                                    'audit_wrong_rows':wrong_rows,'audit_counterexample':counterexample,
                                    'audit_seconds_excluded':audit_elapsed,
                                    'failure_penalized_seconds':result['elapsed'] if accepted and correct else BUDGET,
                                    **{k:v for k,v in result.items() if k!='event'}}
                            out.write(json.dumps(record,separators=(',',':'))+'\n');done.add(key);count+=1
                            if count%60==0:
                                print(json.dumps({'event':'progress','completed':len(done),'new_this_run':count,
                                    'seconds':time.perf_counter()-start,'last_group':rec['group'],'worker_restarts':runner.restarts}),flush=True)
        finally:
            if runner:runner.stop()
    (OUT/'run.complete').write_text(json.dumps({'trials':len(done),'raw_sha256':digest(rawpath),
        'case_sha256':digest(casepath),'seconds_this_run':time.perf_counter()-start}),encoding='utf-8')

if __name__=='__main__':mp.freeze_support();main()
