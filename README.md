# Learned guidance vs. symbolic circuit repair

An unpublished research archive comparing a small learned edit ranker with
simple heuristics, exhaustive search, and SAT/CEGIS for single-edit Boolean
circuit repair. Experiments ran on CPU.

**Status: closed research direction, retained for audit and reuse.** The current
evidence does not justify continuing this project toward a journal submission.
This repository is a technical archive, not a published paper or an accepted
method. [Arabic overview](README.ar.md).

Private GitHub repository: https://github.com/ziademad02153/circuit-repair-research-archive

## Main result

The stronger direct-CNF baseline outperformed or matched the frozen learner in
observed repair success on the tested larger synthetic circuits. No larger
case was repaired by the learner but not CNF at the same budget.

| Wall-clock budget | Frozen learner | Direct CNF/CEGIS |
|---|---:|---:|
| 0.1 s | 54 / 250 | 204 / 250 |
| 1 s | 186 / 250 | 204 / 250 |
| 10 s | 202 / 250 | 204 / 250 |

The need-derived feature bundle helped the forest relative to removing that
bundle. This ablation also removes all target-derived features, so it does not
isolate a unique benefit of need propagation from target conditioning itself.

CNF reported 249 repairs and 51 UNSAT cases across all 300 v3 circuits. UNSAT
is relative to the implemented one-edit encoding; independent UNSAT proof
certificates were not retained. All accepted repairs have recorded independent
checker audits, with no wrong acceptances in v3.

## What the experiments measure

- Combinational, two-input LUT circuits with injected harmful LUT, wire, and
  permanent stuck-at faults. The stuck location is known when present.
- Exactly one non-noop LUT replacement or legal earlier-source rewiring. No
  added gates or output rewiring; stuck gates cannot be edited.
- Rankers use eight sampled specification rows. In the full-specification
  setting, repair acceptance and CEGIS use a complete checker.
- v3 has 300 circuits, 10 methods and 3 actual budget runs: 9,000 trials. The
  primary larger group contains 250 circuits. A trial is not a distinct circuit.
- Costs for candidate generation, features, ranking, encoding, solving and
  verification are inside the method budget. Warmup/model loading is excluded
  as recorded in the protocol. Timeouts are failures.

## Verify the archive without running experiments

Use Python 3.12 or later. No additional package is needed:

```sh
python tools/verify_archive.py
```

This checks file hashes, frozen artifacts, trial coverage and result counts.
It writes `ARTIFACT-VERIFICATION.json`. It does **not** train a model, run a
solver, regenerate circuits, re-prove UNSAT or reproduce timing measurements.

## Read the evidence

1. [Final decision and interpretation, Arabic](docs/final-existing-work-review-2026-10-27.ar.md)
2. [Latest complete result tables](outputs/ablation-cnf-v3/summary.md)
3. [Registered v3 protocol](experiments/ablation-cnf-v3/protocol.json)
4. [Raw v3 trials](outputs/ablation-cnf-v3/raw_trials.jsonl)
5. [v3 audit](outputs/ablation-cnf-v3/audit.json)
6. [Earlier simple-rule comparison](outputs/fairness-v2/compact_report.md)
7. [Earlier Z3 and sampled-specification comparison](outputs/decisive-repair/compact_report.md)

Earlier reports remain unchanged. In particular, the earlier `useful` label
concerned the original Z3 baseline, not the subsequent stronger CNF baseline.
It must not be presented as the final project conclusion.

## Layout

| Directory | Contents |
|---|---|
| `work/` | Original circuit, ranking, training, solver and analysis code |
| `experiments/` | Historical registered protocols and planning records |
| `outputs/` | Models, generated cases, raw trials, events and reports |
| `docs/` | Final decision and historical fairness review |
| `tools/` | Archive verification without experiment execution |

`ARCHIVE-MANIFEST.json` records the hashes and sizes of copied source artifacts.
The original local project was preserved. Installed dependencies, caches,
duplicate ZIP files, console logs and private administrative correspondence
are excluded. Historical plans are archival, not instructions to continue work.

## Reproducing analyses or experiments

Historical dependencies are pinned in `work/requirements-v3.txt`. With a
compatible environment, `work/v3_report.py` regenerates statistics from saved
trials. That historical command overwrites its derived summaries, so use a
separate checkout when reproducing analyses. The archive verifier above is the
default entry point.

The old runners are research code, not a one-click product. They retain the
original paths and freeze checks. Do not append new measurements to the frozen
logs or treat existing completed runs as fresh experiments. Fresh performance
evaluation would require its own preregistered protocol and independent data.

## Limitations

The circuits are synthetic. v3 reuses previously inspected v2 cases and has
one timing run per case/method/budget; it is not an untouched final holdout.
There are no public-family-held-out circuit results or comparisons against
published learned repair models. These results do not establish a general
limitation of learned circuit repair, novelty, or a publication probability.
The negative outcome is specific to the implementations and settings tested.

## Attribution and licensing status

No author identity, institutional affiliation or publication DOI has been
invented. No project-wide open-source license has been selected
for this archive. No third-party package binaries are redistributed. External
software and papers retain their own terms; public access alone is not a
license grant. Publication and author metadata can be added by the project owner.
