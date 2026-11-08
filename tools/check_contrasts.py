import json

with open('outputs/ablation-cnf-v3/summary.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("Contrasts involving forest_full_selected or learned_frozen vs cegis_cnf:")
for item in d.get('primary_comparisons', []):
    print(item.get('a'), 'vs', item.get('b'), item.get('budget_seconds'), 's:', item.get('success'))

for item in d.get('descriptive_budget_contrasts', []):
    if 'cegis_cnf' in (item.get('a'), item.get('b')):
        print(item.get('a'), 'vs', item.get('b'), item.get('budget_seconds'), 's:', item.get('success'))

