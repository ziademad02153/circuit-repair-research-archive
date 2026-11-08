# The Inference Overhead Barrier: Why Learned Guidance Struggles Against Factored CNF in Single-Edit Combinational Circuit Repair

**Technical Report & Research Archive**  
*Repository:* [https://anonymous.4open.science/r/circuit-repair-research-archive](https://anonymous.4open.science/r/circuit-repair-research-archive)  
*Status:* Completed experimental study; auditable open research archive.  
*Artifact Verification:* Verified reproducible (`tools/verify_archive.py` passes all 121 artifacts and 26 frozen hashes).

---

## Abstract

Machine learning guidance is frequently proposed to accelerate combinatorial search and program synthesis by prioritizing promising candidate transformations. In this work, we conduct a controlled empirical study evaluating whether a lightweight, vectorized learned ranker (a NumPy-implemented histogram decision forest) utilizing local topological features and backward Boolean need-message propagation can outperform modern symbolic solvers in single-edit combinational circuit repair. 

Across a pre-registered benchmark of 9,000 trials on 300 synthetic 2-LUT circuits under strict wall-clock deadlines (0.1s, 1.0s, and 10.0s), our findings show that a direct, factored Boolean CNF encoding solved via Glucose 4.2.1 in a Counterexample-Guided Inductive Synthesis (CEGIS) loop completely dominates the learned approach. At a 0.1-second deadline, CNF achieves an 81.6% repair rate (204/250 larger circuits) compared to 21.6% (54/250) for the learned ranker. Even at 10.0 seconds, the learned ranker reaches 80.8% (202/250), failing to solve any instance that CNF could not solve. 

Fine-grained latency profiling reveals the core bottleneck: on circuits solved by both methods, candidate generation and feature extraction alone required an average of 50.26 ms, and vectorized tree inference added 90.36 ms (totaling ~140.6 ms of upfront guidance overhead), whereas complete CNF synthesis terminated in an average of 16.72 ms. Furthermore, while an ablation study demonstrates that need-derived features improve ranking success by +15.6 percentage points over an ablated model, the ablated model strictly lacked access to target specification values; thus, the empirical gain reflects target conditioning rather than a unique property of message propagation. All 5,644 successful trials were independently audited by an exact exhaustive verifier with zero incorrect acceptances. We discuss the implications of this *inference overhead barrier* for neuro-symbolic system design and explain why speculative extensions (such as multi-edit repair or larger input sizes) exacerbate rather than mitigate this asymmetry.

---

## 1. Introduction

Combinational circuit repair seeks an edit to a buggy digital logic circuit such that its input-output behavior matches a target specification. Because exhaustive search through legal circuit modifications scales poorly with circuit depth and fanout, a compelling hypothesis is that learned ranking models—trained on structural graph features and sampled execution discrepancies—can effectively predict which gates and rewiring choices are most likely to repair the fault.

Previous exploratory phases in this project suggested that learned ranking was "useful" when compared against an initial SMT baseline implemented in Z3 using high-level integer/array constraints. However, in formal verification and automated reasoning, symbolic baselines are highly sensitive to encoding decisions. 

To rigorously test whether learned guidance provides a genuine computational advantage, we established a pre-registered experimental study (Protocol v3) comparing:
1. **Learned Rankers**: Ensembles utilizing structural graph signals and backward Boolean need-message propagation from failing specification samples.
2. **Heuristic Baselines**: Lightweight heuristics based on local error reductions and sample evaluations without learned parameters.
3. **Optimized Direct-CNF CEGIS**: A dedicated Boolean CNF encoding employing sequential counter cardinality constraints and structural cone-of-influence localization, solved incrementally via Glucose 4.2.1.

Our empirical results demonstrate a decisive negative outcome for the learned guidance hypothesis in this domain. Rather than discarding or obscuring this result, this archive documents the complete code, frozen models, execution protocols, and independent verification logs.

---

## 2. Problem Formulation and Repair Space

### 2.1 Circuit Model
We consider combinational logic circuits represented as Directed Acyclic Graphs (DAGs) over 2-input Look-Up Tables (2-LUTs). A circuit $\mathcal{C}$ consists of:
* $n$ primary inputs $x_0, \dots, x_{n-1}$.
* $m$ primary outputs $y_0, \dots, y_{m-1}$.
* $G$ internal gates $g_j = (a_j, b_j, T_j)$ for $j \in \{0, \dots, G-1\}$, where $a_j, b_j < n + j$ are incoming input or gate signals, and $T_j \in \{0, \dots, 15\}$ represents the 4-bit Boolean truth table of the LUT.

Circuit execution is evaluated using bit-packed integer masks over $2^n$ assignments.

### 2.2 Fault Injection Model
Harmful synthetic faults are injected into fault-free specifications:
1. **LUT Mutation**: Modifying the 4-bit truth table $T_j \to T'_j$ such that $T'_j \ne T_j$.
2. **Rewiring**: Replacing an input signal $(a_j \text{ or } b_j)$ with another valid topological source signal $s < n + j$.
3. **Stuck-at Faults**: Permanently clamping a gate output to 0 or 1. The identity and location of a stuck-at gate are treated as known.

### 2.3 Single-Edit Repair Domain
A legal repair is defined as **exactly one** non-noop edit to a non-stuck gate:
* Replacing $T_j$ with a different 4-bit truth table $T'_j \in \{0, \dots, 15\} \setminus \{T_j\}$, or
* Replacing input connection $a_j$ or $b_j$ with an earlier topological signal $s < n+j$.

No new gates may be added, no primary output wiring may be redirected, and stuck-at gates cannot be modified. The repair is accepted if and only if the modified circuit $\mathcal{C}'$ satisfies the complete truth table specification across all $2^n$ assignments.

---

## 3. Systems Under Test

### 3.1 Learned Guidance (`TinyForest` + Need Messages)
The learned ranker generates all legal single edits, extracts a feature vector for each, scores candidates using a vectorized decision forest, and presents candidates to the full verifier in descending order of predicted score.

* **Backward Need-Message Propagation**: Given 8 sampled specification input rows where the circuit output disagrees with the specification, desired binary states (`need_zero`, `need_one`) are initialized at primary outputs and propagated backwards along topological wires in reverse DAG order.
* **Feature Representation (21 Dimensions)**:
  * *13 Structural/Local Features*: Gate fanout, output proximity, distance from primary inputs, whether the edit is a LUT change vs. rewiring, Hamming distance of the LUT change, source signal switching activity, and local error rates on sampled rows.
  * *8 Target-Conditioned Need Features*: Consistency between candidate output signals and propagated need masks across the 8 sampled specification rows.
* **Model Architecture**: A histogram-based decision forest (`TinyForest`) implemented entirely in NumPy (depth 9, minimum leaf size 12, 10–20 trees), evaluated using vectorized branch evaluations to eliminate Python interpretation overhead during scoring.

### 3.2 Direct-CNF CEGIS Solver (`v3_cnf.py`)
The symbolic solver directly encodes the single-edit synthesis problem into Propositional Conjunctive Normal Form (CNF):
* **Gate Selection & Mode Encoding**: Indicator variables select exactly one gate $j$ and one modification mode (LUT table replacement or input rewiring) via sequential counter cardinality encodings (`pysat.card.CardEnc.equals(bound=1)`).
* **Structural Cone-of-Influence Pruning**: Only gates in the transitive fan-in of failing primary outputs are declared eligible for modification.
* **CEGIS Loop**: The solver is initialized with constraints enforcing correctness only on currently observed counterexamples. If Glucose 4.2.1 finds a satisfying assignment (a candidate repair), the candidate is checked by the exhaustive verifier. If verification fails, the failing input vector is added as a new CNF constraint, and solving resumes incrementally.

### 3.3 Baselines
* **`cegis_z3`**: The legacy SMT-based synthesis engine using high-level integer/array variables.
* **`local_improvement`**: A non-learned heuristic that ranks edits by the net agreement with backward need masks.
* **`sample_error`**: A heuristic that simulates candidates across the 8 sampled rows and ranks them by observed Hamming error reduction.
* **`exhaustive` / `random`**: Sequential and random traversals of legal candidate edits.

---

## 4. Empirical Evaluation

### 4.1 Benchmark Setup
Experiments were executed on an AMD CPU architecture under Python 3.12. The primary evaluation set consists of 250 larger synthetic circuits ($n \in \{10, 12, 16\}$, gates $G \in \{50, 100, 200\}$) plus 50 smaller reference circuits ($n=6, G=18$). Each circuit-method-budget combination was run with separate wall-clock timeouts of 0.1s, 1.0s, and 10.0s, totaling 9,000 distinct trials.

### 4.2 Primary Results

```
Success Rate vs. Wall-Clock Budget (250 Larger Circuits)

100% ─────────────────────────────────────────────────────────────
     │
 80% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 
     │   [CNF: 81.6%] ────────── [CNF: 81.6%] ────────── [CNF: 81.6%]
 60% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 
     │                           [Learner: 74.4%]        [Learner: 80.8%]
 40% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 
     │
 20% ─ ─ [Learner: 21.6%]
     │
  0% └─────────────┬───────────────────────┬───────────────────────┬───
                 0.1s                    1.0s                    10.0s
```

| Method | 0.1 s Budget | 1.0 s Budget | 10.0 s Budget |
| :--- | :---: | :---: | :---: |
| **Direct CNF (`cegis_cnf`)** | **204 / 250 (81.6%)** | **204 / 250 (81.6%)** | **204 / 250 (81.6%)** |
| **Learned Ranker (`learned_frozen`)** | 54 / 250 (21.6%) | 186 / 250 (74.4%) | 202 / 250 (80.8%) |
| Selected Forest (`forest_full_selected`) | 52 / 250 (20.8%) | 186 / 250 (74.4%) | 201 / 250 (80.4%) |
| Ablated Forest (`forest_no_need_selected`)| 53 / 250 (21.2%) | 147 / 250 (58.8%) | 190 / 250 (76.0%) |
| Local Improvement Heuristic | 123 / 250 (49.2%) | 165 / 250 (66.0%) | 188 / 250 (75.2%) |
| Sample Error Heuristic | 108 / 250 (43.2%) | 163 / 250 (65.2%) | 188 / 250 (75.2%) |
| Exhaustive Search | 94 / 250 (37.6%) | 148 / 250 (59.2%) | 193 / 250 (77.2%) |
| Random Ordering | 56 / 250 (22.4%) | 129 / 250 (51.6%) | 176 / 250 (70.4%) |
| Legacy SMT (`cegis_z3`) | 10 / 250 (4.0%) | 142 / 250 (56.8%) | 200 / 250 (80.0%) |

**Key Statistical Findings:**
* At the pre-registered 1.0-second primary endpoint, the learned ranker lagged behind direct CNF by **−7.2 percentage points** (paired 97.5% bootstrap CI: `[−11.2, −3.6]`).
* Out of 250 circuits, exactly 204 are repairable within the single-edit domain (51 were formally proved UNSAT by CNF). **In zero cases did the learned ranker find a repair where CNF failed.**
* CNF solved all 204 repairable instances within 0.1 seconds, whereas the learned ranker timed out on 150 of those same instances at 0.1s.

---

## 5. Latency Profiling: The Inference Overhead Barrier

To diagnose why learned ranking failed under tight deadlines, we analyzed the component latencies across the 186 larger circuits that were successfully solved by both `learned_frozen` and `cegis_cnf` at 1.0 second:

| Processing Stage | Mean Execution Time | % of 1s Deadline |
| :--- | :---: | :---: |
| Candidate Enumeration & Feature Construction | 50.26 ms | 5.0% |
| Vectorized Decision Forest Inference | 90.36 ms | 9.0% |
| Candidate Sorting | 2.52 ms | 0.3% |
| **Total Upfront Guidance Overhead** | **143.14 ms** | **14.3%** |
| Subsequent Verification Loop (to repair) | 211.87 ms | 21.2% |
| **Complete Direct CNF Execution (Solve + Verify)** | **16.72 ms** | **1.7%** |

In **172 out of 186 instances (92.5%)**, the learned model had not yet produced its first candidate score before the direct CNF solver had already synthesized and formally proven the complete repair.

```
Execution Latency on Matched Successful Instances (N = 186)

Direct CNF:
[Solve+Verify: 16.7ms]

Learned Ranker:
[Features: 50.3ms] ──> [Inference: 90.4ms] ──> [Sort: 2.5ms] ──> [Verify: 211.9ms]
└──────────────── Guidance Overhead: 143.1ms ───────────────┘
```

The learned ranker required a mean of **336.6 verification calls** to hit a valid repair, whereas CEGIS required a mean of only **4.0 solver-verifier interactions**. Even though individual candidate simulations are fast, executing hundreds of candidate checks plus upfront feature extraction is orders of magnitude slower than a modern conflict-driven clause learning (CDCL) solver searching the factored Boolean space.

---

## 6. Ablation Analysis: Need Propagation vs. Target Conditioning

The registered protocol included an ablation experiment comparing the selected full-feature forest (`forest_full_selected`) against an ablated variant trained without need features (`forest_no_need_selected`).

At 1.0 second, the full forest outperformed the ablated model by **+15.6 percentage points** (186/250 vs. 147/250; 97.5% CI: `[+10.0, +21.6]`).

However, code inspection of `work/v3_features.py` reveals an important methodological confound:
* `no_need_features` does not accept the `target` argument; removing the 8 need features stripped **all information regarding the desired output specification** from the feature matrix.
* Consequently, this ablation does not demonstrate a unique advantage of *backward message propagation* over other forms of target-conditioned signals (such as forward error simulation on output rows). It merely shows that conditioning edit selection on the target output is superior to ranking edits solely by topological graph structure.

---

## 7. Discussion: Why a "Crossover" to Machine Learning is Unlikely

It is tempting to hypothesize that expanding the benchmark scope—either to larger circuit topologies or to multi-edit repair—would reveal a "crossover point" where symbolic solvers break down and learned guidance prevails. A rigorous analysis of the underlying algorithmic mechanics indicates the opposite:

1. **Scaling Circuit Inputs ($n \ge 24$)**:
   When $n$ is large, truth-table evaluation across $2^n$ inputs is computationally intractable. Sound verification must transition from truth-table evaluation to a **SAT-based miter**. In this regime, every verification call invoked by the ranker becomes a full SAT call. Since the ranker requires hundreds of verifications while CEGIS requires only a handful of inductive counterexamples, the ranker's relative performance deteriorates drastically.

2. **Multi-Edit Repair ($k \ge 2$)**:
   The candidate search space scales combinatorially ($O(G^k)$). For a 200-gate circuit with 2 edits, explicit candidate generation entails over $10^7$ candidate pairs. Extracting features and running neural or forest inference across millions of pairs imposes an insurmountable computational burden. Conversely, CDCL SAT solvers prune multi-variable combinatorial spaces implicitly via conflict clause learning without explicit enumeration.

---

## 8. Threats to Validity & Limitations

* **Synthetic Topologies**: Circuits were generated via synthetic DAG generators and do not reflect the full structural idiosyncrasies of standard industrial benchmarks (e.g., ISCAS-85 or EPFL).
* **Single-Edit Restriction**: While mathematically precise, physical silicon defects or deep synthesis bugs frequently span multiple gates or functional blocks.
* **Deterministic Oracle**: The fault location of stuck-at gates was treated as known, simplifying fault localization.

---

## 9. Reproducibility & Verification

The archive is engineered for permanent independent audit without requiring specialized hardware or proprietary packages:
* **Integrity Verification**: Running `python tools/verify_archive.py` verifies the SHA-256 digests of all 121 source files, frozen model parameters, and raw JSONL logs against `ARCHIVE-MANIFEST.json`.
* **Zero Wrong Acceptances**: All 5,644 successful trials recorded across protocol v3 passed independent post-hoc verification against an exact, independently coded scalar truth-table interpreter.
* **Reproducible Statistics**: Re-running the statistical audit (`tools/review_saved_results_20261028.py`) directly reproduces every paired bootstrap interval and percentage reported in this document from `outputs/ablation-cnf-v3/raw_trials.jsonl`.

---

## 10. Conclusion

This study provides a rigorous, auditable demonstration of the *inference overhead barrier* in learned program and circuit repair. While lightweight machine learning models can outperform naive random or local search, their proposal overhead renders them uncompetitive against factored, structurally pruned SAT encodings for single-edit combinational repair. 

We recommend that future research into neuro-symbolic circuit synthesis avoid testing against unoptimized, high-level solvers, rigorously account for end-to-end feature extraction latencies, and maintain information parity in ablation controls.

---

### Artifact Summary
* **Raw Trials**: `outputs/ablation-cnf-v3/raw_trials.jsonl` (9,000 records)
* **Registered Protocol**: `experiments/ablation-cnf-v3/protocol.json`
* **Frozen Models**: `outputs/ablation-cnf-v3/models.freeze.json`
* **Verification Script**: `tools/verify_archive.py`
