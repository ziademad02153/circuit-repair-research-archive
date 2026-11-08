"""Verify Top-16 both ways: over all 50 and over solvable only."""
import json
from collections import defaultdict

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

print("Top-16 rates comparison:")
print(f"{'Group':<12} {'Solvable':>8} {'Top16':>6} {'%_solv':>8} {'%_all50':>8}")
for grp in ['n6_g18', 'n10_g50', 'n10_g100', 'n12_g100', 'n16_g100', 'n16_g200']:
    solvable = 0
    top16 = 0
    total = 0
    for cid, mdict in trials_by_case.items():
        ff = mdict.get(('forest_full_selected', 1.0))
        cnf = mdict.get(('cegis_cnf', 1.0))
        if not ff or ff['group'] != grp:
            continue
        total += 1
        if cnf and cnf['status'] == 'accepted':
            solvable += 1
            if ff['status'] == 'accepted' and ff['checks'] <= 16:
                top16 += 1
    
    pct_solv = 100 * top16 / solvable if solvable else 0
    pct_all = 100 * top16 / total if total else 0
    print(f"{grp:<12} {solvable:>8} {top16:>6} {pct_solv:>7.1f}% {pct_all:>7.1f}%")

# Also check: what does summary.json say about top-16?
print("\n\nLooking for top-16 in summary.json...")
with open('outputs/ablation-cnf-v3/summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)

# Look for strata data
if 'strata' in summary:
    print("Found strata key")
    for k, v in summary['strata'].items():
        print(f"  {k}: {v}")
elif 'size_strata' in summary:
    print("Found size_strata key")
else:
    # Search for top-16 anywhere
    def find_keys(d, prefix=""):
        if isinstance(d, dict):
            for k, v in d.items():
                if 'top' in str(k).lower() or 'strat' in str(k).lower():
                    print(f"  {prefix}{k}: {type(v).__name__}")
                find_keys(v, prefix + k + ".")
    find_keys(summary)

# Check n16_g200 with 10/50 = 20%
# 8/43 = 18.6%, 8/40 = 20%, 10/50 = 20%
print(f"\nVerification: 8/43 = {100*8/43:.1f}%, 8/40 = {100*8/40:.1f}%, 10/50 = {100*10/50:.1f}%")

