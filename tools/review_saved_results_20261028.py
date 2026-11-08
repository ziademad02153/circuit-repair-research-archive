"""Saved-data analysis only: no circuit/model/solver imports or experiment calls."""
from pathlib import Path
import ast
import hashlib
import json
import statistics
from datetime import datetime, timezone
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/one-session-review-2026-10-28'


def read_rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'experiments/ablation-cnf-v3/protocol.json').read_text())
    summary = json.loads((ROOT / 'outputs/ablation-cnf-v3/summary.json').read_text())
    raw = ROOT / 'outputs/ablation-cnf-v3/raw_trials.jsonl'
    rows = read_rows(raw)
    assert sha(raw) == summary['raw_sha256']
    assert len(rows) == 9000 == len({r['trial_id'] for r in rows})
    ids = sorted({r['case_id'] for r in rows if r['inputs'] >= 10})
    assert len(ids) == 250
    index = {(r['case_id'], r['budget_seconds'], r['method']): r for r in rows}
    # Extract only the pure recorded-data contrast function, not the module imports/main.
    tree = ast.parse((ROOT / 'work/v3_report.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'contrast')
    ns = {'np': np}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<saved contrast function only>', 'exec'), ns)
    rng = np.random.default_rng(protocol['statistics']['bootstrap_seed'])
    primary = [ns['contrast'](index, ids, 'forest_full_selected', 'forest_no_need_selected', 1.0, rng),
               ns['contrast'](index, ids, 'learned_frozen', 'cegis_cnf', 1.0, rng)]
    for calculated, saved in zip(primary, summary['primary_comparisons']):
        for name in ['success', 'actual_time', 'penalized_time']:
            assert calculated[name] == saved[name], (calculated['a'], name)
    table = []
    for budget in protocol['budgets_seconds']:
        selected = [r for r in rows if r['inputs'] >= 10 and r['budget_seconds'] == budget]
        methods = {}
        for method in protocol['methods']:
            rr = [r for r in selected if r['method'] == method]
            methods[method] = {'successes': sum(r['success'] for r in rr), 'circuits': len(rr),
                               'mean_actual_seconds': statistics.mean(r['elapsed'] for r in rr),
                               'timeouts': sum(r['status'] == 'timeout' for r in rr)}
        pairs = [(index[c, budget, 'learned_frozen'], index[c, budget, 'cegis_cnf']) for c in ids]
        table.append({'budget_seconds': budget, 'methods': methods,
                      'learner_only_successes': sum(x['success'] and not y['success'] for x, y in pairs),
                      'cnf_only_successes': sum(y['success'] and not x['success'] for x, y in pairs)})
    common = [(index[c, 1.0, 'learned_frozen'], index[c, 1.0, 'cegis_cnf']) for c in ids
              if index[c, 1.0, 'learned_frozen']['success'] and index[c, 1.0, 'cegis_cnf']['success']]
    overhead = {'common_successes': len(common),
                'candidate_plus_features_slower_than_complete_cnf': sum(
                    x['candidate_generation_seconds'] + x['feature_seconds'] > y['elapsed'] for x, y in common),
                'mean_candidate_plus_feature_seconds': statistics.mean(
                    x['candidate_generation_seconds'] + x['feature_seconds'] for x, _ in common),
                'mean_inference_seconds': statistics.mean(x['inference_seconds'] for x, _ in common),
                'mean_complete_cnf_seconds': statistics.mean(y['elapsed'] for _, y in common)}
    v2 = read_rows(ROOT / 'outputs/fairness-v2/raw_trials.jsonl')
    v2_counts = {}
    for method in ['learned', 'sample_error', 'local_improvement']:
        rr = [x for x in v2 if x['phase'] == 'test' and x['inputs'] >= 10 and x['method'] == method]
        v2_counts[method] = {'successful_trials': sum(x['success'] for x in rr), 'trials': len(rr),
                             'distinct_circuits': len({x['case_id'] for x in rr})}
    result = {'reviewed_at': datetime.now(timezone.utc).isoformat(), 'new_experiments': 0,
              'operations': 'Hash checking, saved-trial aggregation, registered bootstrap reanalysis and source inspection only.',
              'v3_trials': len(rows), 'v3_distinct_circuits': len({r['case_id'] for r in rows}),
              'raw_sha256': sha(raw), 'primary_intervals_exactly_match_saved': True,
              'primary_comparisons': primary, 'larger_budget_table': table,
              'matched_overhead_1s': overhead, 'v2_counts': v2_counts,
              'wrong_acceptances_recorded': sum(r['wrong_accepted'] for r in rows),
              'successful_trials_with_recorded_independent_audit': sum(r['success'] and r['independent_audited'] for r in rows),
              'solver_reported_unsat_distinct_cases': len({r['case_id'] for r in rows if r['status'] == 'unsat'}),
              'source_evidence': {
                  'no_need_features': 'work/v3_features.py:no_need_features has no target argument; KEEP=4..16 removes all target-derived features.',
                  'full_features': 'work/local_repair_pilot.py:local_features takes target and computes backward masks.',
                  'cnf_pruning': 'work/v3_cnf.py:cnf_cegis uses full-target disagreement cones; rankers use sampled rows and enumerate legal candidates.',
                  'budget': 'work/v3_methods.py:execute includes candidate/feature/inference/check costs; worker excludes startup warmup as registered.'},
              'limits': ['Synthetic, known follow-up cases; not untouched final evaluation.',
                         'One timing run per circuit/method/budget in v3.',
                         'Ablation removes target conditioning as well as need features.',
                         'System comparison does not isolate representation, pruning and encoding costs.',
                         'Recorded independent acceptance audits are not rerun here; UNSAT proof certificates absent.']}
    (OUT / 'saved-data-audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'trials': len(rows), 'new_experiments': 0, 'primary_intervals_match': True,
                      'budget_successes': [{k: v for k, v in x.items() if k != 'methods'} |
                                           {'learner': x['methods']['learned_frozen']['successes'],
                                            'cnf': x['methods']['cegis_cnf']['successes']} for x in table],
                      'overhead': overhead, 'v2': v2_counts}))


if __name__ == '__main__':
    main()
