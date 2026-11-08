"""Create a clean, ready-to-upload ZIP bundle for Overleaf."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ZIP_PATH = DOCS / 'tmlr_submission_bundle.zip'

files_to_zip = [
    (DOCS / 'paper_tmlr.tex', 'main.tex'),
    (DOCS / 'tmlr.sty', 'tmlr.sty'),
    (DOCS / 'tmlr.bst', 'tmlr.bst'),
    (DOCS / 'references.bib', 'references.bib'),
    (DOCS / 'figures' / 'success_vs_budget.pdf', 'figures/success_vs_budget.pdf'),
    (DOCS / 'figures' / 'latency_breakdown.pdf', 'figures/latency_breakdown.pdf'),
    (DOCS / 'figures' / 'success_vs_budget.png', 'figures/success_vs_budget.png'),
    (DOCS / 'figures' / 'latency_breakdown.png', 'figures/latency_breakdown.png'),
]

with zipfile.ZipFile(ZIP_PATH, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for src, arcname in files_to_zip:
        assert src.exists(), f"Missing file: {src}"
        z.write(src, arcname)
        print(f"Added: {arcname} ({src.stat().st_size} bytes)")

print(f"\nSuccessfully created bundle at: {ZIP_PATH}")
print(f"Bundle size: {ZIP_PATH.stat().st_size} bytes")
