"""Deep-dive into the 211.9ms vs 55.1ms discrepancy.
Previous reports said learned_frozen had verification mean=211.9ms. Let's check."""
import json
from collections import defaultdict
import numpy as np

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

# Method 1: The paper says 55.1ms = verification loop mean on 186 mutual (FFS vs CNF)
# Method 2: What about learned_frozen on ALL 250 cases (not just mutual successes)?

# Check verification on ALL cases (including timeouts)
print("=== ALL 250 larger cases ===")
for model in ['forest_full_selected', 'learned_frozen']:
    verif_all = []
    checks_all = []
    elapsed_all = []
    for cid, mdict in trials_by_case.items():
        ff = mdict.get((model, 1.0))
        if ff and ff['group'] != 'n6_g18':
            feat = ff.get('feature_seconds', 0) or 0
            inf = ff.get('inference_seconds', 0) or 0
            sort_s = ff.get('sorting_seconds', 0) or 0
            overhead = feat + inf + sort_s
            verif = ff.get('elapsed', 0) - overhead
            verif_all.append(verif * 1000)
            checks_all.append(ff.get('checks', 0))
            elapsed_all.append(ff.get('elapsed', 0) * 1000)
    
    print(f"\n{model} (all 250 larger):")
    print(f"  Verification (ms): mean={np.mean(verif_all):.1f}, median={np.median(verif_all):.1f}")
    print(f"  Checks: mean={np.mean(checks_all):.1f}, median={np.median(checks_all):.1f}")
    print(f"  Elapsed (ms): mean={np.mean(elapsed_all):.1f}")

# Check: maybe 211.9ms was total elapsed on mutual-solved, not verification?
print("\n=== 186 mutual successes (FFS+CNF) ===")
mutual_ffs = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    ff = mdict.get(('forest_full_selected', 1.0))
    if cnf and ff and cnf['status'] == 'accepted' and ff['status'] == 'accepted' and ff['group'] != 'n6_g18':
        mutual_ffs.append(ff)

print(f"Count: {len(mutual_ffs)}")
elapsed_vals = [t['elapsed'] * 1000 for t in mutual_ffs]
feat_vals = [(t.get('feature_seconds', 0) or 0) * 1000 for t in mutual_ffs]
inf_vals = [(t.get('inference_seconds', 0) or 0) * 1000 for t in mutual_ffs]
sort_vals = [(t.get('sorting_seconds', 0) or 0) * 1000 for t in mutual_ffs]
overhead_vals = [f + i + s for f, i, s in zip(feat_vals, inf_vals, sort_vals)]
verif_vals = [e - o for e, o in zip(elapsed_vals, overhead_vals)]
checks_vals = [t['checks'] for t in mutual_ffs]

print(f"  Elapsed (ms): mean={np.mean(elapsed_vals):.1f}, median={np.median(elapsed_vals):.1f}")
print(f"  Feature (ms): mean={np.mean(feat_vals):.1f}, median={np.median(feat_vals):.1f}")
print(f"  Inference (ms): mean={np.mean(inf_vals):.1f}, median={np.median(inf_vals):.1f}")
print(f"  Sorting (ms): mean={np.mean(sort_vals):.1f}, median={np.median(sort_vals):.1f}")
print(f"  Overhead (ms): mean={np.mean(overhead_vals):.1f}, median={np.median(overhead_vals):.1f}")
print(f"  Verification (ms): mean={np.mean(verif_vals):.1f}, median={np.median(verif_vals):.1f}")
print(f"  Checks: mean={np.mean(checks_vals):.1f}, median={np.median(checks_vals):.1f}")

# Now check learned_frozen on the same 186 mutual cases
print("\n=== 186 mutual successes (LF+CNF) ===")
mutual_lf = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    lf = mdict.get(('learned_frozen', 1.0))
    if cnf and lf and cnf['status'] == 'accepted' and lf['status'] == 'accepted' and lf['group'] != 'n6_g18':
        mutual_lf.append(lf)

print(f"Count: {len(mutual_lf)}")
elapsed_vals = [t['elapsed'] * 1000 for t in mutual_lf]
feat_vals = [(t.get('feature_seconds', 0) or 0) * 1000 for t in mutual_lf]
inf_vals = [(t.get('inference_seconds', 0) or 0) * 1000 for t in mutual_lf]
sort_vals = [(t.get('sorting_seconds', 0) or 0) * 1000 for t in mutual_lf]
overhead_vals = [f + i + s for f, i, s in zip(feat_vals, inf_vals, sort_vals)]
verif_vals = [e - o for e, o in zip(elapsed_vals, overhead_vals)]
checks_vals = [t['checks'] for t in mutual_lf]

print(f"  Elapsed (ms): mean={np.mean(elapsed_vals):.1f}, median={np.median(elapsed_vals):.1f}")
print(f"  Feature (ms): mean={np.mean(feat_vals):.1f}, median={np.median(feat_vals):.1f}")
print(f"  Inference (ms): mean={np.mean(inf_vals):.1f}, median={np.median(inf_vals):.1f}")
print(f"  Sorting (ms): mean={np.mean(sort_vals):.1f}, median={np.median(sort_vals):.1f}")
print(f"  Overhead (ms): mean={np.mean(overhead_vals):.1f}, median={np.median(overhead_vals):.1f}")
print(f"  Verification (ms): mean={np.mean(verif_vals):.1f}, median={np.median(verif_vals):.1f}")
print(f"  Checks: mean={np.mean(checks_vals):.1f}, median={np.median(checks_vals):.1f}")

# Was 211.9ms the total elapsed (not verification) of learned_frozen?
# 143.1ms was supposed to be the overhead... let's check
# Maybe the older numbers included candidate_generation_seconds too?
print("\n=== candidate_generation_seconds check ===")
cg_vals = [(t.get('candidate_generation_seconds', 0) or 0) * 1000 for t in mutual_ffs]
print(f"  candidate_generation (ms): mean={np.mean(cg_vals):.1f}, median={np.median(cg_vals):.1f}")

total_with_cg = [cg + f + i + s for cg, f, i, s in zip(cg_vals, 
    [(t.get('feature_seconds', 0) or 0) * 1000 for t in mutual_ffs],
    [(t.get('inference_seconds', 0) or 0) * 1000 for t in mutual_ffs],
    [(t.get('sorting_seconds', 0) or 0) * 1000 for t in mutual_ffs])]
print(f"  Total overhead with cg (ms): mean={np.mean(total_with_cg):.1f}")

