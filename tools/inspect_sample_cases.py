"""Inspect manual cases from raw_trials.jsonl: g200:39, g100:22, g200:49, and g200:18."""
import json

targets = {'test:n16_g200:39', 'test:n16_g100:22', 'test:n16_g200:49', 'test:n16_g200:18'}

with open('outputs/ablation-cnf-v3/raw_trials.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        t = json.loads(line)
        if t['case_id'] in targets and t['method'] in ('forest_full_selected', 'cegis_cnf'):
            print(f"Case: {t['case_id']} | Method: {t['method']} | Budget: {t['budget_seconds']}s")
            print(f"  Status: {t['status']} | Checks: {t['checks']} | Elapsed: {t['elapsed']:.4f}s")
            if t['method'] == 'forest_full_selected':
                print(f"  feat: {t.get('feature_seconds',0)*1000:.1f}ms | inf: {t.get('inference_seconds',0)*1000:.1f}ms | verif: {t.get('verification_seconds',0)*1000:.1f}ms")
            print("-" * 50)

