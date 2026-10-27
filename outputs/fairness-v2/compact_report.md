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

