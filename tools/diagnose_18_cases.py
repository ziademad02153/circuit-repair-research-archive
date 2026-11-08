import json
from collections import defaultdict
import numpy as np

# Load trials
trials = defaultdict(dict)

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        # key by (case_id, method, budget)
        cid = t['case_id']
        m = t['method']
        b = t['budget_seconds']
        trials[cid][(m, b)] = t

print(f"Total cases indexed: {len(trials)}")

# Let's find the 18 cases where at budget 1.0s: cegis_cnf is accepted but forest_full_selected is NOT accepted!
cases_18 = []
for cid, mdict in trials.items():
    cnf_t = mdict.get(('cegis_cnf', 1.0))
    ff_t = mdict.get(('forest_full_selected', 1.0))
    if cnf_t and ff_t:
        if cnf_t['status'] == 'accepted' and ff_t['status'] != 'accepted':
            cases_18.append((cid, cnf_t, ff_t, mdict.get(('forest_full_selected', 10.0))))

print(f"Number of cases where CNF succeeded at 1.0s but forest_full_selected timed out: {len(cases_18)}")

print("\n--- Details of the 18 Deficit Cases ---")
for cid, cnf, ff1, ff10 in cases_18:
    grp = ff1['group']
    cand_count = ff1.get('candidate_count', 0)
    checks_1s = ff1.get('checks', 0)
    elapsed_1s = ff1.get('elapsed', 0)
    feat_1s = ff1.get('feature_seconds', 0)
    inf_1s = ff1.get('inference_seconds', 0)
    
    # Check 10s outcome
    status_10s = ff10.get('status') if ff10 else 'N/A'
    checks_10s = ff10.get('checks', 0) if ff10 else 'N/A'
    elapsed_10s = ff10.get('elapsed', 0) if ff10 else 'N/A'
    
    print(f"Case {cid} ({grp}): Cands={cand_count}")
    print(f"  At 1.0s: checks={checks_1s}, feat={feat_1s*1000:.1f}ms, inf={inf_1s*1000:.1f}ms, elapsed={elapsed_1s:.3f}s, status={ff1.get('status')}")
    print(f"  At 10.0s: status={status_10s}, checks={checks_10s}, elapsed={elapsed_10s:.3f}s")

