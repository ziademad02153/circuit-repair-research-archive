"""Common timed execution and observable counters for the registered v3 sweep."""
from __future__ import annotations
import time,gc,json,traceback
from contextlib import contextmanager
import decisive_engine as old
from circuit_pilot import ROOT,legal_edits,apply
from local_repair_pilot import local_features
from fairness_v2_methods import ranking,independent_values
from v3_features import no_need_features,load_saved
from v3_cnf import cnf_cegis
import numpy as np

OUT=ROOT/'outputs/ablation-cnf-v3'


def load_models():
    frozen=json.loads((OUT/'models.freeze.json').read_text())
    return {'learned_frozen':old.load_model(),
            'forest_full_selected':load_saved(ROOT/frozen['selected']['full21']['model_file']),
            'forest_no_need_selected':load_saved(ROOT/frozen['selected']['no_need13']['model_file'])}


def execute(payload,method,models,start,budget,emit,metrics,z3):
    @contextmanager
    def stage(name):
        metrics['last_phase']=name;emit({'phase':name});t=time.perf_counter()
        try:yield
        finally:metrics[name]=metrics.get(name,0.)+time.perf_counter()-t
    metrics['checks']=0
    if method=='cegis_cnf':return cnf_cegis(payload,start,budget,emit,metrics)
    if method=='cegis_z3':
        original=old.mismatch
        def counted(c,target):
            metrics['checks']+=1
            with stage('verification_seconds'):return original(c,target)
        old.mismatch=counted
        try:return old.cegis(payload,start,budget,emit,z3)
        finally:old.mismatch=original
    c=payload['c']
    if method=='exhaustive':candidates=legal_edits(c)
    else:
        with stage('candidate_generation_seconds'):
            edits=list(legal_edits(c));old.check_time(start,budget)
        metrics['candidate_count']=len(edits)
        if method in models:
            with stage('feature_seconds'):
                X=(no_need_features(c,edits,payload['rows']) if method=='forest_no_need_selected'
                   else local_features(c,edits,payload['rows'],payload['sample_target']))
                old.check_time(start,budget)
            with stage('inference_seconds'):
                scores=models[method].predict_proba(X)[:,1];old.check_time(start,budget)
            with stage('sorting_seconds'):
                tie=np.random.default_rng(payload['seed']+17).random(len(edits))
                order=np.lexsort((tie,-scores));old.check_time(start,budget)
        else:
            with stage('heuristic_ranking_seconds'):
                order,times=ranking(c,edits,payload['rows'],payload['sample_target'],
                                  payload['seed'],method,None,start,budget)
                metrics.update(times)
        candidates=(edits[int(i)] for i in order)
    with stage('verification_seconds'):
        for edit in candidates:
            old.check_time(start,budget);metrics['checks']+=1
            passed=old.mismatch(apply(c,edit),payload['target_full']) is None
            old.check_time(start,budget)
            if passed:return {'status':'accepted','edit':edit}
            if metrics['checks']%128==0:emit({'phase':'checking','checks':metrics['checks']})
    return {'status':'exhausted'}


def worker(pipe):
    import z3,pysat
    t=time.perf_counter();models=load_models()
    for n in [4,6,10,12,16]:old.full_inputs(n)
    pipe.send({'event':'ready','model_and_input_warmup_seconds':time.perf_counter()-t,
               'z3_version':z3.get_version_string(),'python_sat_version':pysat.__version__})
    while True:
        command=pipe.recv()
        if command is None:return
        payload,method,budget=command;gc.collect();events=[];metrics={}
        pipe.send({'event':'started'});start=time.perf_counter()
        def emit(d):
            if 'phase' in d:metrics['last_phase']=d['phase']
            events.append({'elapsed':time.perf_counter()-start,**d})
        try:result=execute(payload,method,models,start,budget,emit,metrics,z3)
        except old.Deadline:result={'status':'timeout'}
        except Exception as exc:result={'status':'error','error':repr(exc),'traceback':traceback.format_exc()}
        elapsed=time.perf_counter()-start
        if elapsed>budget and result['status']!='error':result={'status':'timeout','over_budget_result':result}
        # In old Z3 the normal return also reports a check count. The wrapper
        # retains started verifier calls on timeouts, so keep that counter.
        if method=='cegis_z3' and 'checks' in result:result['old_returned_checks']=result.pop('checks')
        pipe.send({'event':'result','elapsed':elapsed,**metrics,**result,'progress_events':events})
