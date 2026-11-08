import json
from collections import defaultdict
import numpy as np

time_per_check = defaultdict(list)

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if t.get('method') == 'learned_frozen' and t.get('budget_seconds') == 10.0:
            v_sec = t.get('verification_seconds', 0)
            checks = t.get('checks', 0)
            if checks > 0 and v_sec > 0:
                time_per_check[t['group']].append(v_sec / checks)

print("Verification time per check across strata:")
for g in sorted(time_per_check.keys()):
    vals = time_per_check[g]
    print(f"  {g}: mean = {np.mean(vals)*1000:.3f} ms, median = {np.median(vals)*1000:.3f} ms (N={len(vals)})")

