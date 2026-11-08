import json
from pathlib import Path

out_dir = Path('outputs/ablation-cnf-v3')

# Check what files exist in out_dir
files = list(out_dir.glob('*'))
print("Files in outputs/ablation-cnf-v3:")
for f in files:
    print(f"  {f.name} ({f.stat().st_size} bytes)")
