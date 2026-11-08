import json
from collections import defaultdict
import numpy as np

trials_by_group = defaultdict(lambda: defaultdict(list))

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        m = t.get('method')
        if m in ['learned_frozen', 'forest_full_selected', 'cegis_cnf']:
            trials_by_group[t['group']][(m, t['budget_seconds'])].append(t)

print("Scale Group Analysis for learned_frozen and forest_full_selected:")
groups = sorted(trials_by_group.keys())

for g in groups:
    print(f"\n=================== Group: {g} ===================")
    for m in ['learned_frozen', 'forest_full_selected']:
        t_10 = trials_by_group[g][(m, 10.0)]
        cand_counts = [t.get('candidate_count', 0) for t in t_10 if t.get('candidate_count') is not None]
        feat_times = [t.get('feature_seconds', 0) for t in t_10 if t.get('feature_seconds') is not None]
        inf_times = [t.get('inference_seconds', 0) for t in t_10 if t.get('inference_seconds') is not None]
        sort_times = [t.get('sorting_seconds', 0) for t in t_10 if t.get('sorting_seconds') is not None]
        
        # Accepted cases at 10.0s (where repair was found)
        acc_10 = [t for t in t_10 if t['status'] == 'accepted']
        checks_acc = [t['checks'] for t in acc_10]
        top16_acc = [t['checks'] <= 16 for t in acc_10]
        top1_acc = [t['checks'] == 1 for t in acc_10]
        
        # Success rates at 0.1, 1.0, 10.0
        s_01 = sum(1 for t in trials_by_group[g][(m, 0.1)] if t['status'] == 'accepted')
        s_10 = sum(1 for t in trials_by_group[g][(m, 1.0)] if t['status'] == 'accepted')
        s_100 = sum(1 for t in trials_by_group[g][(m, 10.0)] if t['status'] == 'accepted')
        total = len(t_10)
        
        # CNF success
        cnf_s01 = sum(1 for t in trials_by_group[g][('cegis_cnf', 0.1)] if t['status'] == 'accepted')
        cnf_s10 = sum(1 for t in trials_by_group[g][('cegis_cnf', 1.0)] if t['status'] == 'accepted')
        cnf_s100 = sum(1 for t in trials_by_group[g][('cegis_cnf', 10.0)] if t['status'] == 'accepted')
        
        overhead = np.mean(feat_times) + np.mean(inf_times) + np.mean(sort_times)
        
        print(f"Method: {m}")
        print(f"  Candidates (mean): {np.mean(cand_counts):.1f}")
        print(f"  Guidance Overhead (mean ms): {overhead*1000:.1f} ms (feat: {np.mean(feat_times)*1000:.1f}, inf: {np.mean(inf_times)*1000:.1f}, sort: {np.mean(sort_times)*1000:.1f})")
        print(f"  On solved cases (N={len(acc_10)}/{total}):")
        print(f"    Checks to repair: mean={np.mean(checks_acc):.1f}, median={np.median(checks_acc):.1f}")
        print(f"    Top-1 rate: {np.mean(top1_acc)*100:.1f}%, Top-16 rate: {np.mean(top16_acc)*100:.1f}%")
        print(f"  Success: 0.1s={s_01}/{total} ({s_01/total*100:.1f}%), 1.0s={s_10}/{total} ({s_10/total*100:.1f}%), 10.0s={s_100}/{total} ({s_100/total*100:.1f}%)")
        print(f"  CNF Success: 0.1s={cnf_s01}/{total}, 1.0s={cnf_s10}/{total}, 10.0s={cnf_s100}/{total}")
