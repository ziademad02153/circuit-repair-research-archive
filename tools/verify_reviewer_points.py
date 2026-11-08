"""Verify every reviewer point from the latest feedback against raw_trials.jsonl."""
import json
from collections import defaultdict
import numpy as np

# Load all trials
trials_by_case = defaultdict(dict)
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        trials_by_case[t['case_id']][(t['method'], t['budget_seconds'])] = t

# ==========================================
# POINT 1: "terminating between 1.10s and 2.66s" — check g200:49
# ==========================================
print("=" * 60)
print("POINT 1: Check all 15 resolved deficit instances at 10s")
print("=" * 60)

deficit_cases = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    ff1 = mdict.get(('forest_full_selected', 1.0))
    ff10 = mdict.get(('forest_full_selected', 10.0))
    if cnf and ff1 and cnf['status'] == 'accepted' and ff1['status'] != 'accepted':
        deficit_cases.append((cid, cnf, ff1, ff10))

resolved = [(cid, c, f1, f10) for cid, c, f1, f10 in deficit_cases if f10 and f10['status'] == 'accepted']
unresolved = [(cid, c, f1, f10) for cid, c, f1, f10 in deficit_cases if not f10 or f10['status'] != 'accepted']

print(f"Total deficit: {len(deficit_cases)}")
print(f"Resolved at 10s: {len(resolved)}")
print(f"Unresolved at 10s: {len(unresolved)}")

resolved_times = sorted([(cid, f10['elapsed']) for cid, c, f1, f10 in resolved], key=lambda x: x[1])
print("\nResolved cases (sorted by elapsed):")
for cid, elapsed in resolved_times:
    print(f"  {cid}: {elapsed:.3f}s")
print(f"\nMin: {resolved_times[0][1]:.3f}s, Max: {resolved_times[-1][1]:.3f}s")

# ==========================================
# POINT 2: Edit count formula
# ==========================================
print("\n" + "=" * 60)
print("POINT 2: Edit count formula verification")
print("=" * 60)

# The paper says |edits| ≈ G·(15+2G)
# Reviewer says actual matches G² + G(2n+13)
# Let's check actual candidate counts from trials
for grp_name in ['n6_g18', 'n10_g50', 'n10_g100', 'n12_g100', 'n16_g100', 'n16_g200']:
    cands = []
    for cid, mdict in trials_by_case.items():
        for (m, b), t in mdict.items():
            if t.get('group') == grp_name and m == 'forest_full_selected' and b == 1.0:
                cands.append(t.get('candidate_count', 0))
    if cands:
        mean_c = np.mean(cands)
        # Parse n and G
        parts = grp_name.split('_')
        n = int(parts[0][1:])
        G = int(parts[1][1:])
        formula_paper = G * (15 + 2*G)
        formula_reviewer = G**2 + G*(2*n + 13)
        formula_simple = G*(2*n + 2*G + 13)  # expanded reviewer formula
        print(f"{grp_name}: actual_mean={mean_c:.1f}, paper_formula={formula_paper}, reviewer_formula={formula_reviewer}, G*(2n+2G+13)={formula_simple}")

# ==========================================
# POINT 3: Outlier cases g200:39 (84 checks) and g100:22 (622 checks)
# ==========================================
print("\n" + "=" * 60)
print("POINT 3: Outlier cases with few checks")
print("=" * 60)

# g200:39 details
g200_39 = trials_by_case.get('test:n16_g200:39', {})
ff1_39 = g200_39.get(('forest_full_selected', 1.0))
if ff1_39:
    feat = ff1_39.get('feature_seconds', 0) * 1000
    inf = ff1_39.get('inference_seconds', 0) * 1000
    sort_t = ff1_39.get('sort_seconds', 0) * 1000
    overhead = feat + inf + sort_t
    print(f"g200:39 at 1.0s: feat={feat:.1f}ms, inf={inf:.1f}ms, sort={sort_t:.1f}ms, overhead={overhead:.1f}ms")
    print(f"  checks={ff1_39.get('checks')}, elapsed={ff1_39.get('elapsed'):.3f}s")
    remaining = 1000 - overhead
    print(f"  Budget remaining after overhead: {remaining:.1f}ms")
    if ff1_39.get('checks', 0) > 0:
        ms_per_check = remaining / ff1_39['checks']
        print(f"  ms per check: {ms_per_check:.2f}ms")

# g100:22 details
g100_22 = trials_by_case.get('test:n16_g100:22', {})
ff1_22 = g100_22.get(('forest_full_selected', 1.0))
if ff1_22:
    feat = ff1_22.get('feature_seconds', 0) * 1000
    inf = ff1_22.get('inference_seconds', 0) * 1000
    sort_t = ff1_22.get('sort_seconds', 0) * 1000
    overhead = feat + inf + sort_t
    print(f"\ng100:22 at 1.0s: feat={feat:.1f}ms, inf={inf:.1f}ms, sort={sort_t:.1f}ms, overhead={overhead:.1f}ms")
    print(f"  checks={ff1_22.get('checks')}, elapsed={ff1_22.get('elapsed'):.3f}s")
    remaining = 1000 - overhead
    print(f"  Budget remaining after overhead: {remaining:.1f}ms")
    if ff1_22.get('checks', 0) > 0:
        ms_per_check = remaining / ff1_22['checks']
        print(f"  ms per check: {ms_per_check:.2f}ms")

# Compare with typical g100 overhead
print("\nAll n16_g100 overhead values:")
for cid, mdict in sorted(trials_by_case.items()):
    ff = mdict.get(('forest_full_selected', 1.0))
    if ff and ff.get('group') == 'n16_g100':
        feat = ff.get('feature_seconds', 0) * 1000
        inf = ff.get('inference_seconds', 0) * 1000
        print(f"  {cid}: feat={feat:.1f}ms, inf={inf:.1f}ms, total={feat+inf:.1f}ms, checks={ff.get('checks')}")

# ==========================================
# POINT 4: Median verification vs "hundreds of candidates"
# ==========================================
print("\n" + "=" * 60)
print("POINT 4: Verification time stats (186 mutual successes)")
print("=" * 60)

mutual = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    ff = mdict.get(('forest_full_selected', 1.0))
    if cnf and ff and cnf['status'] == 'accepted' and ff['status'] == 'accepted':
        grp = ff.get('group', '')
        if grp != 'n6_g18':  # larger only
            mutual.append((cid, cnf, ff))

print(f"Mutual successes (larger): {len(mutual)}")

checks = [ff.get('checks', 0) for _, _, ff in mutual]
verif_times = []
for _, _, ff in mutual:
    elapsed = ff.get('elapsed', 0)
    feat = ff.get('feature_seconds', 0)
    inf = ff.get('inference_seconds', 0)
    sort_s = ff.get('sort_seconds', 0)
    overhead = feat + inf + sort_s
    verif = elapsed - overhead
    verif_times.append(verif * 1000)

cnf_times = [c.get('elapsed', 0) * 1000 for _, c, _ in mutual]

print(f"Checks: mean={np.mean(checks):.1f}, median={np.median(checks):.1f}")
print(f"Verification time (ms): mean={np.mean(verif_times):.1f}, median={np.median(verif_times):.1f}")
print(f"CNF time (ms): mean={np.mean(cnf_times):.1f}, median={np.median(cnf_times):.1f}")

overhead_times = []
for _, _, ff in mutual:
    feat = ff.get('feature_seconds', 0)
    inf = ff.get('inference_seconds', 0)
    sort_s = ff.get('sort_seconds', 0)
    overhead_times.append((feat + inf + sort_s) * 1000)

print(f"Overhead (ms): mean={np.mean(overhead_times):.1f}, median={np.median(overhead_times):.1f}")

# ==========================================
# POINT 5: Verification time comparison between models
# ==========================================
print("\n" + "=" * 60)
print("POINT 5: Verification time - forest_full_selected vs learned_frozen")
print("=" * 60)

# Check learned_frozen verification times on the same mutual set
lf_verif = []
ffs_verif = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    ff = mdict.get(('forest_full_selected', 1.0))
    lf = mdict.get(('learned_frozen', 1.0))
    if cnf and ff and lf and cnf['status'] == 'accepted' and ff['status'] == 'accepted' and lf['status'] == 'accepted':
        grp = ff.get('group', '')
        if grp != 'n6_g18':
            # forest_full_selected
            ffs_elapsed = ff.get('elapsed', 0)
            ffs_overhead = ff.get('feature_seconds', 0) + ff.get('inference_seconds', 0) + ff.get('sort_seconds', 0)
            ffs_v = (ffs_elapsed - ffs_overhead) * 1000
            ffs_verif.append(ffs_v)
            
            # learned_frozen
            lf_elapsed = lf.get('elapsed', 0)
            lf_overhead = lf.get('feature_seconds', 0) + lf.get('inference_seconds', 0) + lf.get('sort_seconds', 0)
            lf_v = (lf_elapsed - lf_overhead) * 1000
            lf_verif.append(lf_v)

print(f"Cases where both models + CNF succeed at 1.0s: {len(ffs_verif)}")
print(f"forest_full_selected verification (ms): mean={np.mean(ffs_verif):.1f}, median={np.median(ffs_verif):.1f}")
print(f"learned_frozen verification (ms): mean={np.mean(lf_verif):.1f}, median={np.median(lf_verif):.1f}")
print(f"\nlearned_frozen total elapsed stats:")

# Full comparison of elapsed times
lf_total = []
ffs_total = []
for cid, mdict in trials_by_case.items():
    ff = mdict.get(('forest_full_selected', 1.0))
    lf = mdict.get(('learned_frozen', 1.0))
    if ff and lf:
        grp = ff.get('group', '')
        if grp != 'n6_g18':
            ffs_total.append(ff.get('elapsed', 0) * 1000)
            lf_total.append(lf.get('elapsed', 0) * 1000)
            
print(f"  forest_full_selected elapsed (ms): mean={np.mean(ffs_total):.1f}")
print(f"  learned_frozen elapsed (ms): mean={np.mean(lf_total):.1f}")

# Check the checks count per model on mutual cases
ffs_checks_m = []
lf_checks_m = []
for cid, mdict in trials_by_case.items():
    cnf = mdict.get(('cegis_cnf', 1.0))
    ff = mdict.get(('forest_full_selected', 1.0))
    lf = mdict.get(('learned_frozen', 1.0))
    if cnf and ff and lf and cnf['status'] == 'accepted' and ff['status'] == 'accepted' and lf['status'] == 'accepted':
        grp = ff.get('group', '')
        if grp != 'n6_g18':
            ffs_checks_m.append(ff.get('checks', 0))
            lf_checks_m.append(lf.get('checks', 0))

print(f"\nMutual 3-way (CNF+FFS+LF) cases: {len(ffs_checks_m)}")
print(f"  forest_full_selected checks: mean={np.mean(ffs_checks_m):.1f}")
print(f"  learned_frozen checks: mean={np.mean(lf_checks_m):.1f}")

# ==========================================
# POINT 6: "decisively outperforms all non-SAT baselines at >= 1.0s"
# ==========================================
print("\n" + "=" * 60)
print("POINT 6: Non-SAT comparison at 10s")
print("=" * 60)

methods_10s = defaultdict(int)
for cid, mdict in trials_by_case.items():
    for (m, b), t in mdict.items():
        if b == 10.0 and t.get('group', '') != 'n6_g18':
            if t['status'] == 'accepted':
                methods_10s[m] += 1

for m, count in sorted(methods_10s.items(), key=lambda x: -x[1]):
    print(f"  {m}: {count}/250 ({100*count/250:.1f}%)")

# ==========================================
# POINT 7: Top-16 computation scope
# ==========================================
print("\n" + "=" * 60)
print("POINT 7: Top-16 — computed on solvable only or all 50?")
print("=" * 60)

# We need to check: for each stratum, how many of 50 cases are solvable?
# And then compute top-16 both ways
for grp_name in ['n6_g18', 'n10_g50', 'n10_g100', 'n12_g100', 'n16_g100', 'n16_g200']:
    solvable = 0
    top16_count = 0
    total_in_group = 0
    for cid, mdict in trials_by_case.items():
        ff = mdict.get(('forest_full_selected', 1.0))
        cnf = mdict.get(('cegis_cnf', 1.0))
        if ff and ff.get('group') == grp_name:
            total_in_group += 1
            cnf_solved = cnf and cnf['status'] == 'accepted'
            if cnf_solved:
                solvable += 1
            # Top-16 means first valid rank <= 16
            # We need to know the first valid rank from the trial
            fvr = ff.get('first_valid_rank')
            if fvr is not None and fvr <= 16:
                top16_count += 1
    
    pct_all = 100 * top16_count / total_in_group if total_in_group else 0
    pct_solvable = 100 * top16_count / solvable if solvable else 0
    print(f"{grp_name}: total={total_in_group}, solvable={solvable}, top16={top16_count}, "
          f"pct_all={pct_all:.1f}%, pct_solvable={pct_solvable:.1f}%")

