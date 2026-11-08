"""Calculate exact bootstrap CIs for forest_full_selected vs heuristics and Z3 at 1.0s."""
import json
from collections import defaultdict
import numpy as np

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

# We want 250 larger circuits at budget 1.0s
cases_larger = []
for cid, mdict in sorted(trials_by_case.items()):
    t = mdict.get(('forest_full_selected', 1.0))
    if t and t.get('group') != 'n6_g18':
        cases_larger.append(cid)

print(f"Total larger cases: {len(cases_larger)}")

np.random.seed(42)
n_boot = 10000

def get_success_vector(method):
    vec = []
    for cid in cases_larger:
        t = trials_by_case[cid].get((method, 1.0))
        vec.append(1 if t and t['status'] == 'accepted' else 0)
    return np.array(vec)

ffs = get_success_vector('forest_full_selected')
print(f"forest_full_selected: {np.sum(ffs)}/250 = {np.mean(ffs)*100:.1f}%")

for other_m in ['local_improvement', 'sample_error', 'cegis_z3', 'exhaustive', 'random', 'local_after_error']:
    oth = get_success_vector(other_m)
    diff = ffs - oth
    point_diff = np.mean(diff) * 100
    
    # Paired bootstrap
    boot_diffs = []
    for _ in range(n_boot):
        idx = np.random.randint(0, len(cases_larger), len(cases_larger))
        boot_diffs.append(np.mean(diff[idx]) * 100)
    
    ci95_low, ci95_high = np.percentile(boot_diffs, [2.5, 97.5])
    print(f"vs {other_m:20s}: diff = +{point_diff:.1f} pp, 95% CI [{ci95_low:+.1f}, {ci95_high:+.1f}], success: {np.sum(oth)}/250 ({np.mean(oth)*100:.1f}%)")

