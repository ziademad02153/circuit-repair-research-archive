"""Compute both 95% CI and Bonferroni-corrected 98.33% CI (alpha=0.05/3) for the 3 comparisons at 1.0s."""
import json
from collections import defaultdict
import numpy as np

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

cases_larger = []
for cid, mdict in sorted(trials_by_case.items()):
    t = mdict.get(('forest_full_selected', 1.0))
    if t and t.get('group') != 'n6_g18':
        cases_larger.append(cid)

def get_success_vector(method):
    vec = []
    for cid in cases_larger:
        t = trials_by_case[cid].get((method, 1.0))
        vec.append(1 if t and t['status'] == 'accepted' else 0)
    return np.array(vec)

ffs = get_success_vector('forest_full_selected')

np.random.seed(42)
n_boot = 10000

print("Paired bootstrap contrasts (N=250):")
for other_m in ['local_improvement', 'sample_error', 'cegis_z3']:
    oth = get_success_vector(other_m)
    diff = ffs - oth
    point_diff = np.mean(diff) * 100
    
    boot_diffs = []
    for _ in range(n_boot):
        idx = np.random.randint(0, len(cases_larger), len(cases_larger))
        boot_diffs.append(np.mean(diff[idx]) * 100)
    
    ci95_low, ci95_high = np.percentile(boot_diffs, [2.5, 97.5])
    # Bonferroni for 3 comparisons: alpha = 0.05 / 3 = 0.01667 -> 0.833% and 99.167%
    ci_bonf_low, ci_bonf_high = np.percentile(boot_diffs, [100 * (0.05/6), 100 * (1 - 0.05/6)])
    print(f"vs {other_m:18s}: diff = +{point_diff:.1f} pp | 95% CI [{ci95_low:+.1f}, {ci95_high:+.1f}] | Bonferroni 98.33% CI [{ci_bonf_low:+.1f}, {ci_bonf_high:+.1f}]")

