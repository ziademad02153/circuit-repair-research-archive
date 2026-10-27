# Learning versus simple rules: raw-log report

Development: 180 trials. Test: 4200 trials on 300 distinct circuits, two timing repeats. Budget 1.000 s, one edit, full checker, frozen model.
Primary simple comparator selected before test: **sample_error**.

## Primary comparison

Population: 250 larger circuits (n >= 10), paired by circuit with timing repeats averaged. Two co-primary endpoints use 97.5% intervals each, Bonferroni family of two.

| Endpoint (positive favors learned) | Difference | 97.5% CI |
|---|---:|---:|
| success | 9.000 percentage points | [5.000, 13.403] |
| penalized_time | 10.363 ms | [-24.125, 48.688] |
| actual_time (descriptive, not primary) | 6.977 ms | [-27.513, 45.442] |

Registered decision: **learned benefit demonstrated in a registered endpoint**.

Penalized time charges a full one-second budget to failures. Actual time is separately retained: a method that exhausts early is not credited as a faster successful repair.

## Larger pooled results

| Method | Correct / trials | Success % | Mean actual ms | Mean penalized ms | Timeouts | Wrong accepted |
|---|---:|---:|---:|---:|---:|---:|
| learned | 367/500 | 73.40 | 387.974 | 429.349 | 95 | 0 |
| local_improvement | 320/500 | 64.00 | 380.272 | 426.422 | 142 | 0 |
| local_after_error | 217/500 | 43.40 | 629.446 | 675.260 | 245 | 0 |
| sample_error | 322/500 | 64.40 | 394.951 | 439.712 | 140 | 0 |
| random | 248/500 | 49.60 | 577.959 | 624.397 | 214 | 0 |
| exhaustive | 289/500 | 57.80 | 484.675 | 531.789 | 173 | 0 |
| cegis | 261/500 | 52.20 | 587.961 | 699.033 | 163 | 0 |

## Every size

Each cell: correct / 100 timed trials (50 unique circuits, two repeats); mean actual ms; timeouts. Repeats are not independent circuits.

| Inputs/gates | learned | local_improvement | local_after_error | sample_error | random | exhaustive | cegis |
|---|---:|---:|---:|---:|---:|---:|---:|
| 6/18 | 90/100; 8.30; 0 | 90/100; 2.66; 0 | 90/100; 4.16; 0 | 90/100; 3.52; 0 | 90/100; 3.68; 0 | 90/100; 3.81; 0 | 90/100; 71.23; 0 |
| 10/50 | 78/100; 64.18; 0 | 78/100; 41.32; 0 | 78/100; 70.61; 0 | 78/100; 46.28; 0 | 78/100; 69.11; 0 | 78/100; 57.08; 0 | 78/100; 266.34; 0 |
| 10/100 | 84/100; 269.92; 0 | 84/100; 229.59; 0 | 84/100; 406.14; 0 | 84/100; 244.91; 0 | 84/100; 364.09; 0 | 84/100; 228.71; 0 | 55/100; 589.75; 29 |
| 12/100 | 78/100; 382.75; 22 | 54/100; 553.57; 46 | 37/100; 778.70; 63 | 56/100; 547.82; 44 | 64/100; 583.46; 36 | 56/100; 549.59; 44 | 58/100; 578.47; 26 |
| 16/100 | 72/100; 444.10; 28 | 58/100; 473.03; 42 | 16/100; 905.09; 84 | 58/100; 486.27; 42 | 18/100; 901.03; 82 | 43/100; 749.31; 57 | 58/100; 635.18; 30 |
| 16/200 | 55/100; 778.92; 45 | 46/100; 603.86; 54 | 2/100; 986.69; 98 | 46/100; 649.48; 54 | 4/100; 972.11; 96 | 28/100; 838.68; 72 | 12/100; 870.06; 78 |

## Exploratory larger-population contrasts

Unadjusted 95% intervals below are descriptive; only the preselected comparator and two registered endpoints determine the primary decision.

| Comparator | Delta success pp [95% CI] | Penalized time advantage ms [95% CI] |
|---|---:|---:|
| local_improvement | 9.400 [5.800, 13.200] | -2.927 [-36.196, 31.913] |
| local_after_error | 30.000 [24.400, 36.000] | 245.910 [203.907, 289.516] |
| sample_error | 9.000 [5.400, 12.800] | 10.363 [-20.452, 42.504] |
| random | 23.800 [18.600, 29.200] | 195.047 [156.013, 234.748] |
| exhaustive | 15.600 [10.000, 21.400] | 102.440 [55.098, 149.225] |
| cegis | 21.200 [16.000, 26.600] | 269.683 [232.162, 307.223] |

## Scope and audit

Wrong acceptances (all development/test trials): 0. Errors: 0. Hard watchdog kills: 0.
All accepted repairs have independent NumPy truth-vector audits. Original sources, model and protected v1 files match their registered hashes.
This is an unseen-seed synthetic test, not a circuit-family/industrial benchmark study. No retrained no-need-feature ablation, stronger CNF SAT implementation, budget sweep or hardware experiment has been run here. No novelty or publication-readiness conclusion follows from this comparison.

Stage timings in summary.json are available only for completed stages/trials; missing timeout-stage timings are not zero. Fault-stratified results and all method statuses are also retained.
