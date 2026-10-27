"""Post-hoc decision diagnostics from frozen v3 logs; no new performance trial.

Exploratory explanation only. Does not alter registered criteria or outcomes.
"""
from pathlib import Path
from collections import Counter
from statistics import mean, median
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/ablation-cnf-v3'
OUT = ROOT / 'outputs/research-decision-review'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    complete = json.loads((SOURCE/'run.complete').read_text())
    assert sha(SOURCE/'raw_trials.jsonl') == complete['raw_sha256']
    rows = [json.loads(x) for x in (SOURCE/'raw_trials.jsonl').read_text().splitlines()]
    assert len(rows) == 9000
    index = {(r['case_id'], r['budget_seconds'], r['method']): r for r in rows}
    records = []
    for scope in ['all', 'larger']:
        ids = sorted({r['case_id'] for r in rows if scope == 'all' or r['inputs'] >= 10})
        for budget in [.1, 1., 10.]:
            pairs = [(index[(cid, budget, 'learned_frozen')],
                      index[(cid, budget, 'cegis_cnf')]) for cid in ids]
            common = [(a,b) for a,b in pairs if a['success'] and b['success']]
            records.append({
                'scope': scope, 'budget_seconds': budget, 'circuits': len(ids),
                'learned_successes': sum(a['success'] for a,b in pairs),
                'cnf_successes': sum(b['success'] for a,b in pairs),
                'cnf_statuses': dict(Counter(b['status'] for a,b in pairs)),
                'learned_success_cnf_failure_cases': [a['case_id'] for a,b in pairs if a['success'] and not b['success']],
                'cnf_success_learned_failure_count': sum(b['success'] and not a['success'] for a,b in pairs),
                'common_success_pairs': len(common),
                'learned_faster_on_common_success_count': sum(a['elapsed'] < b['elapsed'] for a,b in common),
                'cnf_max_actual_seconds': max(b['elapsed'] for a,b in pairs),
                'mean_learned_checks_on_common_successes': mean(a['checks'] for a,b in common),
                'mean_cnf_checks_on_common_successes': mean(b['checks'] for a,b in common),
                'median_learned_checks_on_common_successes': median(a['checks'] for a,b in common),
                'median_cnf_checks_on_common_successes': median(b['checks'] for a,b in common),
            })
    common = [(a,b) for (cid,budget,method),a in index.items()
              if budget == 1. and method == 'learned_frozen' and a['inputs'] >= 10
              for b in [index[(cid,budget,'cegis_cnf')]] if a['success'] and b['success']]
    overhead = {
        'population': 'larger, 1 second, matched successful cases only',
        'pairs': len(common),
        'candidate_plus_features_exceeds_complete_cnf_trial_count': sum(
            a['candidate_generation_seconds'] + a['feature_seconds'] > b['elapsed'] for a,b in common),
        'mean_candidate_plus_feature_seconds': mean(a['candidate_generation_seconds']+a['feature_seconds'] for a,b in common),
        'mean_inference_seconds': mean(a['inference_seconds'] for a,b in common),
        'mean_cnf_actual_seconds': mean(b['elapsed'] for a,b in common),
        'interpretation_limit': 'Observed stage costs, not a new zero-inference algorithm, predicted speedup, or causal hardware-independent estimate.'
    }
    result = {
        'analysis_type': 'Post-hoc explanatory review; no new experiment or changed preregistration',
        'source_raw_sha256': sha(SOURCE/'raw_trials.jsonl'),
        'source_protocol_sha256': sha(ROOT/'experiments/ablation-cnf-v3/protocol.json'),
        'audit_source_sha256': sha(Path(__file__)),
        'comparisons': records, 'observed_preprocessing': overhead,
        'limitations': ['Known synthetic v2 cases', 'One timing run per method/budget',
                       'UNSAT is relative to the validated one-edit encoding; no independent proof certificate',
                       'No conclusion about all circuit repair methods or published models',
                       'No publication probability inferred'],
    }
    (OUT/'diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
