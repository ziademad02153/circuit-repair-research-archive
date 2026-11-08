"""Verify every single number in Table 2 from raw data."""
import json
from collections import defaultdict
import numpy as np

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

strata_info = [
    ('n6_g18', '$n=6, G=18$'),
    ('n10_g50', '$n=10, G=50$'),
    ('n10_g100', '$n=10, G=100$'),
    ('n12_g100', '$n=12, G=100$'),
    ('n16_g100', '$n=16, G=100$'),
    ('n16_g200', '$n=16, G=200$'),
]

print(f"{'Group':<12} {'Cands':>8} {'Overhead':>10} {'Top16%':>8} {'0.1s L/C':>10} {'1.0s L/C':>10} {'10s L/C':>10} {'CNF Time':>10}")

for grp, label in strata_info:
    cands_list = []
    overhead_list = []
    cnf_time_list = []
    
    solvable = 0
    top16 = 0
    
    l_01, c_01 = 0, 0
    l_1, c_1 = 0, 0
    l_10, c_10 = 0, 0
    
    for cid, mdict in sorted(trials_by_case.items()):
        ff_1 = mdict.get(('forest_full_selected', 1.0))
        cnf_1 = mdict.get(('cegis_cnf', 1.0))
        
        if not ff_1 or ff_1['group'] != grp:
            continue
            
        # Candidates
        cands_list.append(ff_1.get('candidate_count', 0))
        
        # Overhead (feature + inference + sorting)
        feat = ff_1.get('feature_seconds', 0) or 0
        inf = ff_1.get('inference_seconds', 0) or 0
        sort_s = ff_1.get('sorting_seconds', 0) or 0
        overhead_list.append((feat + inf + sort_s) * 1000)
        
        # CNF time at 1.0s on solvable cases
        if cnf_1 and cnf_1['status'] == 'accepted':
            solvable += 1
            cnf_time_list.append(cnf_1.get('elapsed', 0) * 1000)
            if ff_1['status'] == 'accepted' and ff_1.get('checks', 999999) <= 16:
                top16 += 1
                
        # L/C at 0.1s
        ff_01 = mdict.get(('forest_full_selected', 0.1))
        cnf_01 = mdict.get(('cegis_cnf', 0.1))
        if ff_01 and ff_01['status'] == 'accepted':
            l_01 += 1
        if cnf_01 and cnf_01['status'] == 'accepted':
            c_01 += 1
            
        # L/C at 1.0s
        if ff_1 and ff_1['status'] == 'accepted':
            l_1 += 1
        if cnf_1 and cnf_1['status'] == 'accepted':
            c_1 += 1
            
        # L/C at 10.0s
        ff_10 = mdict.get(('forest_full_selected', 10.0))
        cnf_10 = mdict.get(('cegis_cnf', 10.0))
        if ff_10 and ff_10['status'] == 'accepted':
            l_10 += 1
        if cnf_10 and cnf_10['status'] == 'accepted':
            c_10 += 1

    mean_cands = np.mean(cands_list)
    mean_oh = np.mean(overhead_list)
    pct_top16 = (top16 / solvable * 100) if solvable else 0
    mean_cnf_t = np.mean(cnf_time_list) if cnf_time_list else 0
    
    print(f"{grp:<12} {mean_cands:>8.1f} {mean_oh:>8.1f}ms {pct_top16:>7.1f}% "
          f"{l_01:>3}/{c_01:<3}   {l_1:>3}/{c_1:<3}   {l_10:>3}/{c_10:<3}   {mean_cnf_t:>8.1f}ms")

