import json

with open('outputs/ablation-cnf-v3/summary.json', 'r') as f:
    d = json.load(f)

for item in d.get('primary_comparisons', []):
    if item.get('budget_seconds') == 1.0:
        print(item.get('a'), 'vs', item.get('b'))
        print('  actual_time:', item.get('actual_time'))
        print('  matched_success_checks:', item.get('matched_success_checks'))

for item in d.get('descriptive_budget_contrasts', []):
    if item.get('budget_seconds') == 1.0 and item.get('b') == 'cegis_cnf':
        print(item.get('a'), 'vs', item.get('b'))
        print('  actual_time:', item.get('actual_time'))
        print('  matched_success_checks:', item.get('matched_success_checks'))
