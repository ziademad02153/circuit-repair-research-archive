"""Pre-performance correctness tests on seeds outside training, validation and v2."""
import json,time,threading
from v3_features import ROOT,no_need_features,KEEP,load_saved
from v3_cnf import Encoding,cnf_cegis,BACKEND
from decisive_engine import make_problem,full_values
from circuit_pilot import legal_edits,apply
from local_repair_pilot import local_features
from fairness_v2_methods import independent_values
from pysat.solvers import Solver
from pysat.examples.genhard import PHP
import numpy as np

OUT=ROOT/'outputs/ablation-cnf-v3'


def main():
    records=[];candidate_checks=0;noop_checks=0;cycle_checks=0;cegis_checks=0
    for i in range(24):
        p=make_problem(6300000+i,3 if i%2 else 4,4+i%3);c=p['c'];edits=list(legal_edits(c))
        eligible=set(range(len(c.gates)))-{c.stuck};t=time.perf_counter()
        enc=Encoding(c,eligible,t,120);enc.rows(list(range(1<<c.n)),p['target'])
        with Solver(name=BACKEND,incr=True) as solver:
            enc.append(solver)
            valid=[]
            for e in edits:
                kind,j,slot,value=e
                if kind=='lut':assume=[enc.gate[j],enc.kind]+[(v if (value>>k)&1 else -v) for k,v in enumerate(enc.table)]
                else:assume=[enc.gate[j],-enc.kind,enc.slot if slot else -enc.slot,enc.source[value]]
                expected=full_values(apply(c,e))==p['target'];actual=solver.solve(assumptions=assume)
                assert actual==expected,(i,e,expected,actual)
                if actual:assert enc.edit(solver.get_model())==e;valid.append(e)
                candidate_checks+=1
            for j,evar in enc.gate.items():
                a,b,table=c.gates[j]
                original=[evar,enc.kind]+[(v if (table>>k)&1 else -v) for k,v in enumerate(enc.table)]
                assert solver.solve(assumptions=original) is False;noop_checks+=1
                for slot,source in enumerate((a,b)):
                    assert solver.solve(assumptions=[evar,-enc.kind,enc.slot if slot else -enc.slot,enc.source[source]]) is False
                    noop_checks+=1
                if c.n+j<len(enc.source):
                    assert solver.solve(assumptions=[evar,-enc.kind,enc.source[c.n+j]]) is False;cycle_checks+=1
        payload={'c':c,'seed':p['seed'],'rows':p['rows'],'sample_target':p['sample_target'],
                 'target_full':p['target'],'setting':'full'}
        metrics={};result=cnf_cegis(payload,time.perf_counter(),30,lambda x:None,metrics)
        assert (result['status']=='accepted')==bool(valid),(i,result,len(valid))
        assert result['status'] in ['accepted','unsat'],result
        if result['status']=='accepted':assert tuple(result['edit']) in valid;assert independent_values(apply(c,tuple(result['edit'])))==p['target']
        cegis_checks+=1
        records.append({'seed':p['seed'],'valid_repairs':len(valid),'status':result['status'],
                        'candidate_tests':len(edits),'cnf_metrics':metrics})
    feature_checks=[]
    for i,(n,g) in enumerate([(4,10),(5,14),(6,18),(10,50),(10,100),(12,100),(16,100),(16,200)]):
        p=make_problem(6400000+i,n,g);edits=list(legal_edits(p['c']))
        full=local_features(p['c'],edits,p['rows'],p['sample_target'])
        no_need=no_need_features(p['c'],edits,p['rows']);assert np.array_equal(no_need,full[:,KEEP])
        assert independent_values(p['c'])==full_values(p['c'])
        feature_checks.append({'inputs':n,'gates':g,'candidate_feature_rows':len(edits)})
    selected=json.loads((OUT/'models.freeze.json').read_text())['selected']
    prediction_checks=[]
    for variant,info in selected.items():
        m=load_saved(ROOT/info['model_file']);X=full if variant=='full21' else no_need
        # Reference traversal need only sample rows; full feature equality checked above.
        subset=X[np.linspace(0,len(X)-1,100,dtype=int)]
        assert np.allclose(m.predict_proba(subset),m.predict_proba_reference(subset),rtol=0,atol=1e-12)
        prediction_checks.append({'variant':variant,'candidates':len(subset)})
    with Solver(name=BACKEND,bootstrap_with=PHP(nof_holes=16).clauses,incr=True) as solver:
        t=time.perf_counter();timer=threading.Timer(.03,solver.interrupt);timer.start()
        try:interrupted=solver.solve_limited(expect_interrupt=True)
        finally:timer.cancel();timer.join()
        seconds=time.perf_counter()-t
        assert interrupted is None and seconds<2,('interrupt test failed',interrupted,seconds)
        solver.clear_interrupt()
    record={'status':'passed','backend':BACKEND,'exhaustive_fixed_edit_sat_checks':candidate_checks,
            'noop_constraints_checked':noop_checks,'cycle_constraints_checked':cycle_checks,
            'cegis_cases':cegis_checks,'cases':records,'no_need_feature_checks':feature_checks,
            'prediction_reference_checks':prediction_checks,'native_interrupt_seconds':seconds,
            'native_interrupt_returned_unknown':True,'no_test_cases_used':True}
    (OUT/'preflight.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if not isinstance(v,list)}))


if __name__=='__main__':main()
