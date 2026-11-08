import json

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for i in range(5):
        line = f.readline()
        trial = json.loads(line)
        print(f"Trial {i}:")
        print(f"  keys: {list(trial.keys())}")
        print(f"  method={trial.get('method')}, budget={trial.get('budget_seconds')}, seed={trial.get('case_seed')}, status={trial.get('status')}")
        print(f"  metrics={trial.get('metrics')}")

