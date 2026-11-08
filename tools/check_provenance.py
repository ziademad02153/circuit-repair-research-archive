import json

freeze = json.loads(open('outputs/ablation-cnf-v3/models.freeze.json').read())
print("models.freeze.json content:")
print(json.dumps(freeze, indent=2))

pilot_model = json.loads(open('outputs/local-repair-pilot/selected_model.json').read())
print("\nPilot model keys:")
print(pilot_model.keys())
print("Pilot model metadata / trees:", len(pilot_model.get('trees', [])))
