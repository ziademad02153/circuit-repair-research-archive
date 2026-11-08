import json
import numpy as np

# Load trials
trials = {}
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials[(t['case_id'], t['method'], t['budget_seconds'])] = t

# Find mutual successes at 1.0s for forest_full_selected and cegis_cnf
cases = sorted(list(set(k[0] for k in trials.keys() if k[0].startswith('test:'))))
larger_cases = [c for c in cases if not c.startswith('test:n6_g18')]

print(f"Total larger test cases: {len(larger_cases)}")

mutual_ff = []
for c in larger_cases:
    t_ff = trials.get((c, 'forest_full_selected', 1.0))
    t_cnf = trials.get((c, 'cegis_cnf', 1.0))
    if t_ff and t_cnf and t_ff['status'] == 'accepted' and t_cnf['status'] == 'accepted':
        mutual_ff.append((c, t_ff, t_cnf))

print(f"Mutual successes for forest_full_selected & cegis_cnf at 1.0s: {len(mutual_ff)}")

mutual_lf = []
for c in larger_cases:
    t_lf = trials.get((c, 'learned_frozen', 1.0))
    t_cnf = trials.get((c, 'cegis_cnf', 1.0))
    if t_lf and t_cnf and t_lf['status'] == 'accepted' and t_cnf['status'] == 'accepted':
        mutual_lf.append((c, t_lf, t_cnf))

print(f"Mutual successes for learned_frozen & cegis_cnf at 1.0s: {len(mutual_lf)}")

# Check if the cases are identical
ff_cases = set(c[0] for c in mutual_ff)
lf_cases = set(c[0] for c in mutual_lf)
print(f"Are mutual cases identical between forest_full_selected and learned_frozen? {ff_cases == lf_cases}")

# Calculate breakdown for forest_full_selected
feat_ff = [t[1]['feature_seconds']*1000 for t in mutual_ff]
inf_ff = [t[1]['inference_seconds']*1000 for t in mutual_ff]
sort_ff = [t[1]['sorting_seconds']*1000 for t in mutual_ff]
verif_ff = [t[1]['verification_seconds']*1000 for t in mutual_ff]
checks_ff = [t[1]['checks'] for t in mutual_ff]

cnf_time = [t[2]['elapsed']*1000 for t in mutual_ff]

overhead_ff = np.array(feat_ff) + np.array(inf_ff) + np.array(sort_ff)

print("\n--- Breakdown for forest_full_selected on 186 mutual cases ---")
print(f"Feature extraction: mean={np.mean(feat_ff):.1f} ms, median={np.median(feat_ff):.1f} ms")
print(f"Inference: mean={np.mean(inf_ff):.1f} ms, median={np.median(inf_ff):.1f} ms")
print(f"Sorting: mean={np.mean(sort_ff):.1f} ms, median={np.median(sort_ff):.1f} ms")
print(f"Total Overhead: mean={np.mean(overhead_ff):.1f} ms, median={np.median(overhead_ff):.1f} ms")
print(f"Verification: mean={np.mean(verif_ff):.1f} ms, median={np.median(verif_ff):.1f} ms")
print(f"Checks: mean={np.mean(checks_ff):.1f}, median={np.median(checks_ff):.1f}")
print(f"CNF Total Time: mean={np.mean(cnf_time):.1f} ms, median={np.median(cnf_time):.1f} ms")

# How many cases had overhead > cnf_time?
count_overhead_gt_cnf = sum(1 for o, c in zip(overhead_ff, cnf_time) if o > c)
print(f"Cases where overhead > complete CNF: {count_overhead_gt_cnf} / {len(mutual_ff)} ({count_overhead_gt_cnf/len(mutual_ff)*100:.1f}%)")

