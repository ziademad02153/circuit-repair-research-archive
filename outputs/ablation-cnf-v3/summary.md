# v3: need-feature ablation and CNF budget sweep

Trials 9000; test circuits 300; primary larger population 250; one timing run per case/method/budget.
Known v2 cases reused as a diagnostic follow-up. All 300 retained. Full checker; one non-noop edit; equal actual budgets.

## Training selection (validation only)

| Variant | RNG seed | Top-16 validation successes / cases | Mean clipped rank | Fit seconds |
|---|---:|---:|---:|---:|
| full21 | 20261026 | 77/120 | 23.342 | 5.230 |
| full21 | 20261027 | 77/120 | 22.600 | 5.692 |
| full21 | 20261028 | 78/120 | 22.600 | 5.032 |
| no_need13 | 20261026 | 30/120 | 45.225 | 5.149 |
| no_need13 | 20261027 | 30/120 | 44.617 | 5.241 |
| no_need13 | 20261028 | 31/120 | 45.317 | 5.827 |

Original full-feature seed model exactly reproduced: True.

## Larger population success versus budget

| Method | 0.1 s | 1 s | 10 s |
|---|---:|---:|---:|
| learned_frozen | 54/250 (21.60%) | 186/250 (74.40%) | 202/250 (80.80%) |
| forest_full_selected | 52/250 (20.80%) | 186/250 (74.40%) | 201/250 (80.40%) |
| forest_no_need_selected | 53/250 (21.20%) | 147/250 (58.80%) | 190/250 (76.00%) |
| local_improvement | 123/250 (49.20%) | 165/250 (66.00%) | 188/250 (75.20%) |
| local_after_error | 49/250 (19.60%) | 111/250 (44.40%) | 171/250 (68.40%) |
| sample_error | 108/250 (43.20%) | 163/250 (65.20%) | 188/250 (75.20%) |
| random | 56/250 (22.40%) | 129/250 (51.60%) | 176/250 (70.40%) |
| exhaustive | 94/250 (37.60%) | 148/250 (59.20%) | 193/250 (77.20%) |
| cegis_z3 | 10/250 (4.00%) | 142/250 (56.80%) | 200/250 (80.00%) |
| cegis_cnf | 204/250 (81.60%) | 204/250 (81.60%) | 204/250 (81.60%) |

## Registered primary success contrasts, 1 second

Positive = first method minus second. Paired 97.5% intervals per endpoint; two-endpoint Bonferroni family.

| First | Second | Delta success pp | 97.5% CI |
|---|---|---:|---:|
| forest_full_selected | forest_no_need_selected | 15.600 | [10.000, 21.600] |
| learned_frozen | cegis_cnf | -7.200 | [-11.200, -3.600] |

## Descriptive frozen learner versus CNF at each budget

These 95% per-budget intervals are descriptive, not simultaneous claims across budgets.

| Budget s | Delta success pp [95% CI] | Actual time advantage ms [95% CI] | Penalized time advantage ms [95% CI] |
|---|---:|---:|---:|
| 0.1 | -60.000 [-66.000, -54.000] | -91.809 [-96.967, -86.822] | -56.240 [-60.507, -51.926] |
| 1.0 | -7.200 [-10.400, -4.000] | -338.466 [-383.201, -295.487] | -203.567 [-238.039, -171.374] |
| 10.0 | -0.800 [-2.000, 0.000] | -951.123 [-1233.237, -697.969] | -362.566 [-520.359, -239.231] |

## Per-size frozen learner versus CNF, descriptive

All registered sizes and budgets shown. Per-cell 95% intervals are not simultaneous or confirmatory subgroup tests. Positive success difference favors the learner.

| Size | Budget s | Learner successes | CNF successes | Delta success pp [95% CI] |
|---|---:|---:|---:|---:|
| n10_g100 | 0.1 | 7/50 | 42/50 | -70.000 [-82.000, -56.000] |
| n10_g100 | 1.0 | 42/50 | 42/50 | 0.000 [0.000, 0.000] |
| n10_g100 | 10.0 | 42/50 | 42/50 | 0.000 [0.000, 0.000] |
| n10_g50 | 0.1 | 38/50 | 39/50 | -2.000 [-6.000, 0.000] |
| n10_g50 | 1.0 | 39/50 | 39/50 | 0.000 [0.000, 0.000] |
| n10_g50 | 10.0 | 39/50 | 39/50 | 0.000 [0.000, 0.000] |
| n12_g100 | 0.1 | 9/50 | 39/50 | -60.000 [-74.000, -46.000] |
| n12_g100 | 1.0 | 39/50 | 39/50 | 0.000 [0.000, 0.000] |
| n12_g100 | 10.0 | 39/50 | 39/50 | 0.000 [0.000, 0.000] |
| n16_g100 | 0.1 | 0/50 | 41/50 | -82.000 [-92.000, -72.000] |
| n16_g100 | 1.0 | 36/50 | 41/50 | -10.000 [-20.000, -2.000] |
| n16_g100 | 10.0 | 41/50 | 41/50 | 0.000 [0.000, 0.000] |
| n16_g200 | 0.1 | 0/50 | 43/50 | -86.000 [-94.000, -76.000] |
| n16_g200 | 1.0 | 30/50 | 43/50 | -26.000 [-38.000, -14.000] |
| n16_g200 | 10.0 | 41/50 | 43/50 | -4.000 [-10.000, 0.000] |
| n6_g18 | 0.1 | 45/50 | 45/50 | 0.000 [0.000, 0.000] |
| n6_g18 | 1.0 | 45/50 | 45/50 | 0.000 [0.000, 0.000] |
| n6_g18 | 10.0 | 45/50 | 45/50 | 0.000 [0.000, 0.000] |

## Larger population timing and failures

| Budget | Method | Mean actual ms | Mean penalized ms | Timeout | Unknown | Wrong |
|---|---|---:|---:|---:|---:|---:|
| 0.1 | learned_frozen | 108.238 | 89.147 | 196 | 0 | 0 |
| 0.1 | forest_full_selected | 107.182 | 88.935 | 198 | 0 | 0 |
| 0.1 | forest_no_need_selected | 96.440 | 90.629 | 197 | 0 | 0 |
| 0.1 | local_improvement | 63.025 | 62.825 | 121 | 0 | 0 |
| 0.1 | local_after_error | 89.929 | 89.546 | 197 | 0 | 0 |
| 0.1 | sample_error | 71.150 | 70.912 | 139 | 0 | 0 |
| 0.1 | random | 88.037 | 87.749 | 186 | 0 | 0 |
| 0.1 | exhaustive | 73.764 | 73.835 | 148 | 0 | 0 |
| 0.1 | cegis_z3 | 98.738 | 98.873 | 226 | 0 | 0 |
| 0.1 | cegis_cnf | 16.429 | 32.907 | 0 | 0 | 0 |
| 1.0 | learned_frozen | 355.011 | 402.219 | 45 | 0 | 0 |
| 1.0 | forest_full_selected | 359.259 | 406.275 | 45 | 0 | 0 |
| 1.0 | forest_no_need_selected | 502.219 | 549.225 | 84 | 0 | 0 |
| 1.0 | local_improvement | 367.011 | 417.595 | 66 | 0 | 0 |
| 1.0 | local_after_error | 610.710 | 661.915 | 120 | 0 | 0 |
| 1.0 | sample_error | 377.061 | 427.157 | 68 | 0 | 0 |
| 1.0 | random | 559.977 | 611.283 | 102 | 0 | 0 |
| 1.0 | exhaustive | 459.609 | 511.320 | 83 | 0 | 0 |
| 1.0 | cegis_z3 | 542.099 | 659.287 | 70 | 0 | 0 |
| 1.0 | cegis_cnf | 16.545 | 198.652 | 0 | 0 | 0 |
| 10.0 | learned_frozen | 967.812 | 2217.395 | 9 | 0 | 0 |
| 10.0 | forest_full_selected | 1007.265 | 2238.293 | 10 | 0 | 0 |
| 10.0 | forest_no_need_selected | 1958.525 | 3205.036 | 21 | 0 | 0 |
| 10.0 | local_improvement | 1587.006 | 2846.554 | 23 | 0 | 0 |
| 10.0 | local_after_error | 2752.835 | 4010.094 | 40 | 0 | 0 |
| 10.0 | sample_error | 1610.068 | 2864.551 | 23 | 0 | 0 |
| 10.0 | random | 2451.697 | 3715.234 | 35 | 0 | 0 |
| 10.0 | exhaustive | 1689.934 | 2948.124 | 18 | 0 | 0 |
| 10.0 | cegis_z3 | 1136.392 | 2795.612 | 5 | 0 | 0 |
| 10.0 | cegis_cnf | 16.689 | 1854.830 | 0 | 0 | 0 |

## CNF stages, larger population

Means include completed or partially executed measured stages; hard kills can have missing observations. Native/model initialization costs remain within/excluded as defined by protocol.

| Budget | Encoding mean ms (observed trials) | SAT solve mean ms (observed trials) | Verification mean ms |
|---|---:|---:|---:|
| 0.1 | 11.238 (250) | 3.052 (250) | 1.524 (250) |
| 1.0 | 11.339 (250) | 3.049 (250) | 1.525 (250) |
| 10.0 | 11.384 (250) | 3.132 (250) | 1.546 (250) |

## Verifier checks among successful trials only

Conditional on each method succeeding before its deadline. Not the same subset across methods and not uncensored ranks. Matched-success contrasts are in summary.json.

| Budget | Method | Successful observations | Mean checks | Median | p90 | p95 |
|---|---|---:|---:|---:|---:|---:|
| 0.1 | learned_frozen | 54 | 52.130 | 2.000 | 181.500 | 259.250 |
| 0.1 | forest_full_selected | 52 | 85.288 | 2.000 | 213.300 | 262.400 |
| 0.1 | forest_no_need_selected | 53 | 565.698 | 270.000 | 1840.000 | 1987.200 |
| 0.1 | local_improvement | 123 | 176.122 | 11.000 | 383.200 | 833.400 |
| 0.1 | local_after_error | 49 | 1469.837 | 1386.000 | 2812.000 | 2925.800 |
| 0.1 | sample_error | 108 | 165.315 | 10.000 | 228.600 | 750.300 |
| 0.1 | random | 56 | 1443.696 | 1090.500 | 3225.000 | 3662.000 |
| 0.1 | exhaustive | 94 | 761.968 | 328.000 | 1936.800 | 3406.450 |
| 0.1 | cegis_z3 | 10 | 1.200 | 1.000 | 2.000 | 2.000 |
| 0.1 | cegis_cnf | 204 | 4.108 | 4.000 | 7.000 | 9.000 |
| 1.0 | learned_frozen | 186 | 336.618 | 26.500 | 875.500 | 1744.000 |
| 1.0 | forest_full_selected | 186 | 361.242 | 37.500 | 790.500 | 2152.500 |
| 1.0 | forest_no_need_selected | 147 | 1690.381 | 766.000 | 5367.000 | 6031.400 |
| 1.0 | local_improvement | 165 | 1106.036 | 22.000 | 3289.400 | 7334.600 |
| 1.0 | local_after_error | 111 | 3430.982 | 2362.000 | 10334.000 | 10855.000 |
| 1.0 | sample_error | 163 | 831.957 | 18.000 | 2790.400 | 5580.000 |
| 1.0 | random | 129 | 3139.240 | 2017.000 | 8201.400 | 10079.600 |
| 1.0 | exhaustive | 148 | 1561.892 | 682.000 | 4081.300 | 5558.650 |
| 1.0 | cegis_z3 | 142 | 3.239 | 3.000 | 6.000 | 6.950 |
| 1.0 | cegis_cnf | 204 | 4.108 | 4.000 | 7.000 | 9.000 |
| 10.0 | learned_frozen | 202 | 531.084 | 44.000 | 1488.300 | 2908.750 |
| 10.0 | forest_full_selected | 201 | 541.736 | 56.000 | 1234.000 | 3062.000 |
| 10.0 | forest_no_need_selected | 190 | 2447.668 | 1577.000 | 6535.700 | 6986.500 |
| 10.0 | local_improvement | 188 | 2171.617 | 54.500 | 10798.000 | 11450.950 |
| 10.0 | local_after_error | 171 | 5420.743 | 3506.000 | 11391.000 | 11908.500 |
| 10.0 | sample_error | 188 | 2025.032 | 34.500 | 10551.900 | 11284.000 |
| 10.0 | random | 176 | 4245.659 | 3161.500 | 10306.000 | 11233.250 |
| 10.0 | exhaustive | 193 | 3034.591 | 1371.000 | 10997.400 | 13093.800 |
| 10.0 | cegis_z3 | 200 | 4.020 | 4.000 | 7.000 | 8.050 |
| 10.0 | cegis_cnf | 204 | 4.108 | 4.000 | 7.000 | 9.000 |

## Repairability and integrity

Unique solver-reported UNSAT cases (all 300): 51. Observed solved union: 249. Still unknown: 0.
UNSAT refers to the validated encoding in the exact one-edit domain; no independently checked SAT proof certificate is claimed. Primary denominator includes all cases. Secondary conditional rates, every size/fault/status and stage observation counts are in summary.json.
Wrong accepted: 0; errors: 0; hard kills: 1.
No public/family-held-out benchmark or hardware experiment in this round. Removing the need-derived bundle also removes target-derived signals; it does not prove backward need propagation is uniquely necessary or better than every alternative target-conditioned representation.
