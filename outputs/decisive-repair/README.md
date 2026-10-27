# Decisive repair experiment

The registered protocol is preregistration.json. Raw per-attempt observations
are raw_trials.jsonl; counterexamples/progress/deadlines are in events.jsonl.
All generated circuits, their gold references and their sampled specifications
are in cases.jsonl. The sample-only worker never receives the gold reference or
full truth table. Full audits occur after method execution and are not timed.

The same originally used 400 cases were reconstructed and checked field by
field in independent_audit.json. New sets cover every registered Cartesian
combination, not just paired input/gate sizes. Model weights remain unchanged.

Reproduce with Python, NumPy, z3-solver, and the frozen model file:

    python -m pip install -r work/requirements-decisive.txt
    python work/decisive_validate.py
    python work/decisive_run.py
    python work/decisive_report.py
    python work/decisive_audit.py

The runner resumes completed trial IDs without overwriting observations. For
a genuinely new timing run, use a separate copy/output directory and preserve
the original logs. Never merge timing repeats as independent circuit samples.

summary.json and summary.csv are derived by decisive_report.py. summary.md is
the full table. Every count, rate, time and interval is computed from raw logs.
Timeouts are failures. Actual wall time and failure-penalized runtime are
separate columns; the user criterion uses actual wall time, as documented in
preanalysis_time_clarification.json. The initial added penalty operationalization
is retained separately. Confidence
intervals are paired by circuit, not independent resamples of the methods.

No novelty or publication assessment is part of this experiment.
