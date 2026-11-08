"""Check forest_full_selected trial fields and verify Top-16 from checks field."""
import json
from collections import defaultdict

# Read forest_full_selected trials to find the checks field
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if t['method'] == 'forest_full_selected' and t['budget_seconds'] == 1.0:
            print(f"Case: {t['case_id']}, checks={t['checks']}, status={t['status']}")
            print(f"  Keys: {sorted(t.keys())}")
            print(f"  Full: candidate_count={t.get('candidate_count')}, "
                  f"candidate_generation_seconds={t.get('candidate_generation_seconds')}, "
                  f"heuristic_ranking_seconds={t.get('heuristic_ranking_seconds')}, "
                  f"sorting_seconds={t.get('sorting_seconds')}, "
                  f"verification_seconds={t.get('verification_seconds')}")
            break

# Top-16 means the successful repair was found within the first 16 checks
# So checks <= 16 AND status == 'accepted' 
print("\n\nTop-16 per stratum (checks<=16 and accepted, among solvable):")
strata = defaultdict(lambda: {'solvable': 0, 'top16': 0})

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if t['method'] == 'forest_full_selected' and t['budget_seconds'] == 1.0:
            grp = t['group']
            # Check if this case is solvable (check CNF)
            # We need CNF status too -- skip for now, use 10s status as proxy
            pass

# Better: load all trials first
trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

strata = defaultdict(lambda: {'solvable': 0, 'top16': 0, 'total': 0})
for cid, mdict in trials_by_case.items():
    ff = mdict.get(('forest_full_selected', 1.0))
    cnf = mdict.get(('cegis_cnf', 1.0))
    if not ff:
        continue
    grp = ff['group']
    strata[grp]['total'] += 1
    
    # Solvable = CNF can solve it
    if cnf and cnf['status'] == 'accepted':
        strata[grp]['solvable'] += 1
        # Top-16 = learner finds repair in first 16 checks
        if ff['status'] == 'accepted' and ff['checks'] <= 16:
            strata[grp]['top16'] += 1

print("\nTop-16 rates (among solvable instances):")
for grp in ['n6_g18', 'n10_g50', 'n10_g100', 'n12_g100', 'n16_g100', 'n16_g200']:
    s = strata[grp]
    pct = 100 * s['top16'] / s['solvable'] if s['solvable'] else 0
    print(f"  {grp}: {s['top16']}/{s['solvable']} = {pct:.1f}% (total={s['total']})")

