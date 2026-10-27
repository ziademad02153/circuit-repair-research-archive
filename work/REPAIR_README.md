# Reproduce the zero-fee circuit-repair pilots

These are exploratory research prototypes, not a published method or a novelty
certificate. Read `../outputs/research-pilot-report.md` for the recommendation,
closest prior work, negative results, observed limits, and publication gates.

Runtime: Python 3.12 and NumPy. No GPU, API keys, online inference, paid data,
physical board, or external ML framework is used. The implementation can import
NumPy from the local `.research_deps` directory or from an ordinary environment.
The recorded run used NumPy 2.5.4. Randomness is seeded.

From the workspace root:

```powershell
python -m pip install numpy==2.5.4
python work/circuit_pilot.py
python work/verify_pilot.py
python work/local_repair_pilot.py
python work/repair_followup.py
python work/repair_validation_selection.py
python work/adder_demo.py
python work/make_repair_report.py
```

`circuit_pilot.py` contains the bit-packed circuit interpreter, synthetic harmful
fault generator, common candidate space, ordinary NumPy histogram forest, and
the first, globally informed ranking pilot. No novelty is claimed for that forest.

`local_repair_pilot.py` implements Boolean need-message propagation and the shared
local-feature repair proposer. It keeps a central scheduler and exact verifier;
do not describe it as fully decentralised execution. Main proposals observe
eight specification rows. The verifier tests every one of the 2^n inputs.

`verify_pilot.py` checks all sixteen Boolean operators and compares the packed
interpreter against an independently written scalar interpreter on 120 random
circuits and 5,952 input assignments. It also searches for a two-rewire repair.

`repair_followup.py` compares vectorised forest inference against recursive
inference and evaluates an exploratory larger-size batch without retraining.

`repair_validation_selection.py` chooses forest size on validation only, retaining
all five trials, then opens a new test batch. The choice of this experiment was
informed by earlier test results; it is exploratory development, not a final
independently registered study. It alternates runtime measurement order.

`adder_demo.py` applies the learned proposer and bounded beam search to one
hand-built 2-bit adder. A spare carry gate is supplied initially. The example is
given its full sixteen-row specification and must not be folded into the main
benchmark percentages.

Artifacts live in `outputs/circuit-pilot/` and `outputs/local-repair-pilot/`.
`selected_results.json` contains every final case, not only successes. Read the
scope notes: one-edit-repairable is not the same as physically repairable, random
logic circuits are not industrial benchmarks, and simulated rewiring is not
physical wire repair. A zero observed false acceptance rate follows from the
exhaustive checker on these tiny deterministic circuits, not learned confidence.

The raw redirected logs preserve earlier implementation timings. Optimising
inference changed runtime without changing model predictions. Hashes of the
final source files are in `source_manifest.json`.
