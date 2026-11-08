"""Check the actual field names in raw_trials.jsonl and verify Top-16 computation."""
import json

# Read first few trials to see field names
with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        t = json.loads(line)
        print(f"Trial {i} keys: {sorted(t.keys())}")
        if t['method'] == 'forest_full_selected':
            print(f"  Full trial: {json.dumps(t, indent=2)[:2000]}")

