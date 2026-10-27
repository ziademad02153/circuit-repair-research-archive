# Fairness and learning ablation follow-up

preregistration.json fixes source hashes, seeds, timing, baseline selection and
statistical endpoints. selection.json was frozen after the first 180 development
trials, before the 4200 test trials; audit.json verifies the raw prefix hash.

The test contains 300 distinct synthetic circuits, two timing repeats per
method, seven methods. Confidence resampling keeps the repeats of each circuit
together. The two primary endpoint intervals are 97.5% each; all other intervals
are descriptive. Each method has the same one-edit domain and one-second budget.
The original 24-tree model is not retrained or tuned.

raw_trials.jsonl contains every trial. events.jsonl contains buffered progress.
cases.jsonl contains the circuits, references and sampled ranking inputs.
summary.md, summary.csv, summary.json are generated exclusively from raw logs.
Stage timing means condition on the stage having completed, never on missing=0.

The .research_deps folder may supply dependencies; on a new environment use:

    python -m pip install -r work/requirements-decisive.txt
    python work/fairness_v2_report.py
    python work/fairness_v2_audit.py

The original v1 sources/logs/model remain unchanged. Do not overwrite them or
merge timing repeats as independent circuits. The runner resumes completed IDs;
a new timing experiment needs a separate registered directory/seed plan.

This experiment does not include retrained removal-of-need-feature models,
public circuit benchmarks, stronger CNF CEGIS, additional time budgets, or real
hardware. It evaluates the incremental value of learning relative to simple
rules on a fresh-seed synthetic set. It is not a publication-readiness judgment.
