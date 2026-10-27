"""Descriptive post-hoc claim checks; does not modify the registered v2 study."""
from pathlib import Path
import sys,json,hashlib
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.research_deps'))
import numpy as np


def main():
    p=ROOT/'outputs/fairness-v2'
    s=json.loads((p/'summary.json').read_text())
    raw=[json.loads(x) for x in (p/'raw_trials.jsonl').read_text().splitlines()]
    rr=[r for r in raw if r['phase']=='test' and r['inputs']>=10]
    result={'analysis_type':'post-hoc descriptive review of reviewer claims; not a new confirmatory test',
        'raw_sha256':hashlib.sha256((p/'raw_trials.jsonl').read_bytes()).hexdigest(),
        'primary':s['primary'],'larger':{},'faults_all_test':s['fault_breakdown']}
    for method in ['learned','sample_error','local_improvement','cegis']:
        a=[r for r in rr if r['method']==method]
        observed=[r['checks'] for r in a if 'checks' in r]
        success=[r['checks'] for r in a if r['success'] and 'checks' in r]
        stat=next(x for x in s['statistics'] if x['group']=='larger' and x['method']==method)
        result['larger'][method]={'success_trials':sum(r['success'] for r in a),'trials':len(a),
            'checks_observed_n':len(observed),'mean_checks_observed':float(np.mean(observed)),
            'mean_checks_success_only':float(np.mean(success)),
            'median_checks_success_only':float(np.median(success)),
            'p90_checks_success_only':float(np.quantile(success,.9)),
            'p95_checks_success_only':float(np.quantile(success,.95)),
            'stages':stat['stages'],'statuses':dict(Counter(r['status'] for r in a))}
    solved={}
    for r in rr:
        if r['success']:solved.setdefault(r['case_id'],set()).add(r['method'])
    result['larger_union_any_method_any_repeat']=len(solved)
    result['larger_learned_any_repeat']=sum('learned' in methods for methods in solved.values())
    result['larger_learned_both_repeats']=sum(sum(r['success'] for r in rr if r['case_id']==cid and r['method']=='learned')==2 for cid in {r['case_id'] for r in rr})
    index={(r['case_id'],r['repeat'],r['method']):r for r in rr}
    result['matched_success_checks']={}
    for method in ['sample_error','local_improvement']:
        pairs=[]
        for r in rr:
            if r['method']=='learned' and r['success']:
                b=index[(r['case_id'],r['repeat'],method)]
                if b['success']:pairs.append((r['checks'],b['checks']))
        a=np.asarray(pairs)
        result['matched_success_checks'][method]={'pairs':len(pairs),
            'learned_mean':float(a[:,0].mean()),'rule_mean':float(a[:,1].mean()),
            'learned_median':float(np.median(a[:,0])),'rule_median':float(np.median(a[:,1])),
            'learned_fewer':int(sum(a[:,0]<a[:,1])),'rule_fewer':int(sum(a[:,1]<a[:,0])),
            'equal':int(sum(a[:,0]==a[:,1]))}
    for label,scope in [('all_test',[r for r in raw if r['phase']=='test']),('larger',rr)]:
        perm=[r for r in scope if r['method']=='cegis' and r['fault_type']=='permanent']
        result['permanent_cegis_'+label]={'trials':len(perm),'unique_circuits':len({r['case_id'] for r in perm}),
            'statuses':dict(Counter(r['status'] for r in perm)),
            'unsat_unique':len({r['case_id'] for r in perm if r['status']=='unsat'})}
    result['caveats']=['Counts of checks with a recorded result mix successes and exhausted searches and exclude most timeouts.',
        'Stage means condition on stage completion; missing values are not zeros.',
        'Common-success comparisons still condition on successes inside the time budget; they are descriptive, not hardware-independent universal rank distributions.',
        'Observed solved union is not a certified repairability ceiling.',
        'UNSAT is a result of our current encoding in the fixed one-edit domain, not general physical irreparability. Counts must separate unique circuits and timing repeats.',
        'Fault breakdown covers all 300 test circuits; primary pooled comparison covers 250 larger circuits.',
        'Removing need features must also remove derived after-error/before-error/improvement/source-error and required-bit features, and avoid computing the removed messages.']
    result['no_need_remove_feature_indices']=[0,1,2,3,17,18,19,20]
    out=ROOT/'outputs/reviewer-analysis-v2';out.mkdir(exist_ok=True)
    (out/'claim-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'observed_mean_checks':{k:v['mean_checks_observed'] for k,v in result['larger'].items()},
        'matched_success':result['matched_success_checks'],
        'observed_solved_union':result['larger_union_any_method_any_repeat'],
        'unsat_all_test':result['permanent_cegis_all_test'],'unsat_larger':result['permanent_cegis_larger']}))


if __name__=='__main__':main()
