"""Verify retained artifacts and summarize raw trials. Python standard library only.

Does not import models, generate circuits, run solvers, or execute experiments.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = read(ROOT/'ARCHIVE-MANIFEST.json')
    for item in manifest['files']:
        file = ROOT/item['path']
        assert file.is_file(), f"Missing: {item['path']}"
        assert file.stat().st_size == item['bytes'], item['path']
        assert digest(file) == item['sha256'], f"Changed: {item['path']}"
    folder = ROOT/'outputs/ablation-cnf-v3'
    protocol = read(ROOT/'experiments/ablation-cnf-v3/protocol.json')
    freeze = read(folder/'implementation.freeze.json')
    models = read(folder/'models.freeze.json')
    frozen = {**protocol['protected_sha256'], **freeze['sources'], **models['all_model_hashes']}
    for relative, expected in frozen.items():
        file = ROOT/relative.replace('\\','/')
        assert digest(file) == expected, f'Frozen file changed: {relative}'
    assert digest(ROOT/'experiments/ablation-cnf-v3/protocol.json') == (folder/'protocol.sha256').read_text().strip()
    summary, complete = read(folder/'summary.json'), read(folder/'run.complete')
    raw = folder/'raw_trials.jsonl'
    assert digest(raw) == summary['raw_sha256'] == complete['raw_sha256']
    trials = [json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines() if line]
    assert len(trials) == len({r['trial_id'] for r in trials}) == protocol['expected_trials']
    ids = sorted({r['case_id'] for r in trials})
    index = {(r['case_id'],r['budget_seconds'],r['method']):r for r in trials}
    for case in ids:
        for budget in protocol['budgets_seconds']:
            for method in protocol['methods']:
                assert (case,budget,method) in index
    solved = {r['case_id'] for r in trials if r['success']}
    unsat = {r['case_id'] for r in trials if r['status']=='unsat'}
    assert not (solved & unsat), 'Conflicting repairability records'
    assert all(r['independent_audited'] and r['audit_wrong_rows']==0 for r in trials if r['success'])
    assert all(not r['wrong_accepted'] for r in trials)
    assert all(r['elapsed']<=r['budget_seconds'] for r in trials if r['success'])
    assert all(r['failure_penalized_seconds']==r['budget_seconds'] for r in trials if not r['success'])
    table=[]
    for budget in protocol['budgets_seconds']:
        methods={}
        for method in ['learned_frozen','forest_no_need_selected','local_improvement','sample_error','cegis_z3','cegis_cnf']:
            rr=[r for r in trials if r['inputs']>=10 and r['budget_seconds']==budget and r['method']==method]
            count=sum(r['success'] for r in rr)
            saved=next(r for r in summary['statistics'] if r['scope']=='larger' and r['budget_seconds']==budget and r['method']==method)
            assert count==saved['successes'] and len(rr)==saved['circuits']
            methods[method]={'successes':count,'circuits':len(rr),'statuses':dict(Counter(r['status'] for r in rr))}
        table.append({'budget_seconds':budget,'methods':methods})
    result={'status':'passed','date':'2026-10-27','copied_artifacts_verified':len(manifest['files']),
        'frozen_source_and_model_hashes_verified':len(frozen),'v3_trials':len(trials),
        'v3_circuits':len(ids),'solver_reported_unsat_cases':len(unsat),
        'observed_repaired_cases':len(solved),'larger_budget_results':table,
        'new_experiments':0,'raw_sha256':digest(raw),
        'scope':'Checks retained files and recorded outcomes; does not re-prove UNSAT, rerun independent checking, or reproduce timings.'}
    (ROOT/'ARTIFACT-VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
