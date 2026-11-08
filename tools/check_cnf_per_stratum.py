import json
from collections import defaultdict
import numpy as np

cnf_times = defaultdict(list)
verif_times_per_check = defaultdict(list)

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if t.get('method') == 'cegis_cnf' and t.get('budget_seconds') == 1.0:
            cnf_times[t['group']].append(t['elapsed']*1000)
        if t.get('method') == 'forest_full_selected' and t.get('budget_seconds') == 10.0:
            v_sec = t.get('verification_seconds', 0)
            checks = t.get('checks', 0)
            if checks > 0 and v_sec > 0:
                verif_times_per_check[t['group']].append((v_sec / checks) * 1000)

print("CNF mean time (ms) and verification time per check (ms) across strata:")
for g in sorted(cnf_times.keys()):
    c_m = np.mean(cnf_times[g])
    c_med = np.median(cnf_times[g])
    v_m = np.mean(verif_times_per_check[g])
    print(f"  {g}: CNF mean={c_m:.1f} ms (med={c_med:.1f} ms) | Verifier per check={v_m:.3f} ms")
