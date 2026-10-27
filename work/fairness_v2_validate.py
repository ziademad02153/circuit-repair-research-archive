"""Correctness-only preflight; seeds disjoint from development and test."""
import json, time, hashlib
from dataclasses import asdict
from fairness_v2_methods import (ROOT, RULES, METHODS, local_rule_keys,
    sample_error_keys, ranking, independent_values, run_method, load_model)
from decisive_engine import make_problem, full_values
from circuit_pilot import legal_edits, apply, evaluate
from local_repair_pilot import local_features
from verify_pilot import reference
import numpy as np
import z3


def main():
    out = ROOT/'outputs/fairness-v2'; out.mkdir(parents=True, exist_ok=True)
    model = load_model(); records = []; checks = 0
    for i in range(24):
        p = make_problem(6100000+i, 4, 6); c = p['c']; edits = list(legal_edits(c))
        assert len(set(edits)) == len(edits)
        assert independent_values(c) == full_values(c)
        assert independent_values(p['gold']) == p['target']
        for row in range(16):
            assert reference(c,row) == tuple((x >> row) & 1 for x in full_values(c))
        X = local_features(c, edits, p['rows'], p['sample_target'])
        t = time.perf_counter()
        imp, aft, dist = local_rule_keys(c,edits,p['rows'],p['sample_target'],t,60)
        assert np.array_equal(imp,X[:,1]) and np.array_equal(aft,X[:,0]) and np.array_equal(dist,X[:,6])
        error, distance = sample_error_keys(c,edits,p['rows'],p['sample_target'],t,60)
        expected = [sum((a^b).bit_count() for a,b in zip(evaluate(apply(c,e),p['rows']),p['sample_target'])) for e in edits]
        assert np.array_equal(error, expected)
        tie = np.random.default_rng(p['seed']+17).random(len(edits))
        expected_orders = {
            'local_improvement':np.lexsort((tie,X[:,6],-X[:,1])),
            'local_after_error':np.lexsort((tie,X[:,6],X[:,0])),
            'sample_error':np.lexsort((tie,distance,error)),
            'learned':np.lexsort((tie,-model.predict_proba(X)[:,1]))}
        for method, order in expected_orders.items():
            actual,_ = ranking(c,edits,p['rows'],p['sample_target'],p['seed'],method,model,t,60)
            assert np.array_equal(actual,order),method
        valid = {e for e in edits if full_values(apply(c,e))==p['target']}
        payload={'c':c,'seed':p['seed'],'rows':p['rows'],'sample_target':p['sample_target'],
                 'target_full':p['target'],'setting':'full'}
        statuses={}
        for method in METHODS:
            result = run_method(payload,method,model,time.perf_counter(),60,lambda x:None,z3)
            assert result['status'] in ['accepted','unsat','exhausted'],result
            assert (result['status']=='accepted') == bool(valid),(i,method,result)
            if result['status']=='accepted':
                assert tuple(result['edit']) in valid
                assert independent_values(apply(c,tuple(result['edit'])))==p['target']
            statuses[method]=result['status'];checks+=1
        records.append({'seed':p['seed'],'fault_type':p['fault_type'],
                        'legal_candidates':len(edits),'valid_repairs':len(valid),'statuses':statuses})
    large=[]
    for i,(n,g) in enumerate([(6,18),(10,50),(10,100),(12,100),(16,100),(16,200)]):
        p=make_problem(6200000+i,n,g);c=p['c'];edits=list(legal_edits(c))
        assert independent_values(c)==full_values(c)
        assert independent_values(p['gold'])==p['target']
        # Check optimized global error keys against literal full resimulation.
        ids=np.random.default_rng(i+4).choice(len(edits),min(50,len(edits)),replace=False)
        subset=[edits[int(k)] for k in ids];t=time.perf_counter()
        error,_=sample_error_keys(c,subset,p['rows'],p['sample_target'],t,60)
        expected=[sum((a^b).bit_count() for a,b in zip(evaluate(apply(c,e),p['rows']),p['sample_target'])) for e in subset]
        assert np.array_equal(error,expected)
        X=local_features(c,subset,p['rows'],p['sample_target'])
        imp,aft,dist=local_rule_keys(c,subset,p['rows'],p['sample_target'],t,60)
        assert np.array_equal(imp,X[:,1]) and np.array_equal(aft,X[:,0]) and np.array_equal(dist,X[:,6])
        for e in subset[:5]:assert independent_values(apply(c,e))==full_values(apply(c,e))
        large.append({'inputs':n,'gates':g,'candidate_keys_checked':len(subset),
                      'independent_full_candidate_checks':min(5,len(subset))})
    result={'status':'passed','tiny_method_comparisons':checks,'tiny_cases':records,
            'large_correctness_checks':large,'z3_version':z3.get_version_string(),
            'ranking_api_has_no_complete_target':True,
            'optimized_rules_match_reference_keys':True,
            'purpose':'correctness only, not validation selection or test outcomes'}
    (out/'preflight.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','tiny_method_comparisons':checks,'large_cases':len(large)}))


if __name__=='__main__':main()
