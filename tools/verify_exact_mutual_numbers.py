"""Verify exact timing statistics for forest_full_selected across 186 mutual cases."""
import json
from collections import defaultdict
import numpy as np

trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

mutual_ffs = []
for cid, mdict in sorted(trials_by_case.items()):
    cnf = mdict.get(('cegis_cnf', 1.0))
    ffs = mdict.get(('forest_full_selected', 1.0))
    if cnf and ffs and cnf['status'] == 'accepted' and ffs['status'] == 'accepted':
        if ffs.get('group') != 'n6_g18':
            mutual_ffs.append((cid, cnf, ffs))

print(f"Mutual count: {len(mutual_ffs)}")

# candidate_generation_seconds
cg = [ffs.get('candidate_generation_seconds', 0) * 1000 for _, _, ffs in mutual_ffs]
# feature_seconds
feat = [ffs.get('feature_seconds', 0) * 1000 for _, _, ffs in mutual_ffs]
# inference_seconds
inf = [ffs.get('inference_seconds', 0) * 1000 for _, _, ffs in mutual_ffs]
# sorting_seconds
sort_s = [ffs.get('sorting_seconds', 0) * 1000 for _, _, ffs in mutual_ffs]
# total overhead
overhead = [c + f + i + s for c, f, i, s in zip(cg, feat, inf, sort_s)]
# verification seconds (from trial)
verif_field = [ffs.get('verification_seconds', 0) * 1000 for _, _, ffs in mutual_ffs]
# verification loop = elapsed - overhead
elapsed = [ffs.get('elapsed', 0) * 1000 for _, _, ffs in mutual_ffs]
verif_calc = [e - o for e, o in zip(elapsed, overhead)]
# checks
checks = [ffs.get('checks', 0) for _, _, ffs in mutual_ffs]

# CNF elapsed
cnf_elapsed = [cnf.get('elapsed', 0) * 1000 for _, cnf, _ in mutual_ffs]
cnf_checks = [cnf.get('checks', 0) for _, cnf, _ in mutual_ffs]

print(f"Candidate Gen: mean={np.mean(cg):.1f} ms, median={np.median(cg):.1f} ms")
print(f"Feature Extr : mean={np.mean(feat):.1f} ms, median={np.median(feat):.1f} ms")
print(f"Tree Infer   : mean={np.mean(inf):.1f} ms, median={np.median(inf):.1f} ms")
print(f"Sorting      : mean={np.mean(sort_s):.1f} ms, median={np.median(sort_s):.1f} ms")
print(f"Overhead (w/o cg): mean={np.mean(feat)+np.mean(inf)+np.mean(sort_s):.1f} ms, median={np.median([f+i+s for f,i,s in zip(feat,inf,sort_s)]):.1f} ms")
print(f"Overhead (w/ cg) : mean={np.mean(overhead):.1f} ms, median={np.median(overhead):.1f} ms")
print(f"Verification field: mean={np.mean(verif_field):.1f} ms, median={np.median(verif_field):.1f} ms")
print(f"Verification calc : mean={np.mean(verif_calc):.1f} ms, median={np.median(verif_calc):.1f} ms")
print(f"Checks: mean={np.mean(checks):.1f}, median={np.median(checks):.1f}")
print(f"CNF Elapsed: mean={np.mean(cnf_elapsed):.1f} ms, median={np.median(cnf_elapsed):.1f} ms")
print(f"CNF Checks : mean={np.mean(cnf_checks):.1f}, median={np.median(cnf_checks):.1f}")

