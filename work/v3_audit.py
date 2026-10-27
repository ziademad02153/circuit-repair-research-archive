"""Audit complete v3 artifacts, sources, model selection and immutable parents."""
from pathlib import Path
import json,hashlib,zipfile
from circuit_pilot import ROOT

OUT=ROOT/'outputs/ablation-cnf-v3';PROTOCOL=ROOT/'experiments/ablation-cnf-v3/protocol.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=json.loads(PROTOCOL.read_text());assert digest(PROTOCOL)==(OUT/'protocol.sha256').read_text().strip()
    imp=json.loads((OUT/'implementation.freeze.json').read_text());models=json.loads((OUT/'models.freeze.json').read_text())
    train=json.loads((OUT/'training_summary.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    complete=json.loads((OUT/'run.complete').read_text())
    for rel,h in {**p['protected_sha256'],**imp['sources'],**models['all_model_hashes']}.items():assert digest(ROOT/rel)==h,rel
    assert digest(OUT/'training_summary.json')==models['training_summary_sha256']
    assert digest(OUT/'models.freeze.json')==imp['models_freeze_sha256']
    assert digest(OUT/'preflight.json')==imp['preflight_sha256']
    assert digest(OUT/'training_cases.jsonl')==train['training_cases_sha256']
    assert digest(OUT/'training_arrays.npz')==train['training_arrays_sha256']
    assert digest(OUT/'raw_trials.jsonl')==complete['raw_sha256']==summary['raw_sha256']
    assert digest(OUT/'cases.jsonl')==complete['case_sha256']
    rows=[json.loads(x) for x in (OUT/'raw_trials.jsonl').read_text().splitlines()]
    assert len(rows)==p['expected_trials'] and len({r['trial_id'] for r in rows})==len(rows)
    cases=[json.loads(x) for x in (OUT/'cases.jsonl').read_text().splitlines()]
    train_cases=[json.loads(x) for x in (OUT/'training_cases.jsonl').read_text().splitlines()]
    assert not {c['seed'] for c in cases}&{c['seed'] for c in train_cases}
    for variant in ['full21','no_need13']:
        chosen=min([r for r in train['all_models'] if r['variant']==variant],
            key=lambda r:(-r['validation_top16_successes'],r['validation_mean_clipped_rank'],r['training_seed']))
        assert chosen['model_sha256']==models['selected'][variant]['model_sha256']
    for row in rows:
        assert row['accepted']==(row['status']=='accepted' and row['elapsed']<=row['budget_seconds'])
        assert not row['success'] or (row['independent_audited'] and row['audit_wrong_rows']==0)
        if not row['success']:assert row['failure_penalized_seconds']==row['budget_seconds']
    by_case={}
    for r in rows:by_case.setdefault(r['case_id'],[]).append(r)
    for cid,rr in by_case.items():
        assert len(rr)==30
        for budget in p['budgets_seconds']:
            assert {r['method'] for r in rr if r['budget_seconds']==budget}==set(p['methods'])
    assert not ({r['case_id'] for r in rows if r['status'] in ['unsat','exhausted']} & {r['case_id'] for r in rows if r['success']})
    record={'audit':'passed','trials':len(rows),'unique_test_circuits':len(cases),
        'weights_validation_selection_verified':True,'training_test_seeds_disjoint':True,
        'full_control_original_seed_reproduced':summary['original_full_seed_model_reproduced'],
        'protected_parents_sources_and_models_unchanged':True,'no_unsat_or_exhaustion_vs_success_conflict':True,
        'accepted_independent_audits':sum(r['independent_audited'] for r in rows),
        'wrong_acceptances':summary['wrong_acceptances'],'errors':summary['errors'],
        'raw_sha256':digest(OUT/'raw_trials.jsonl'),'report_sha256':digest(ROOT/'work/v3_report.py'),
        'audit_sha256':digest(Path(__file__))}
    (OUT/'audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    readme='''# V3: no-need feature ablation and direct Boolean CNF budget sweep

The initial protocol is experiments/ablation-cnf-v3/protocol.json. Training,
weights and implementation each have separate immutable freeze files. The
protocol precedes training; the performance implementation and all weights are
frozen before timed evaluation. Prose typo “nine methods” is transparently
clarified in freeze records: the authoritative list contains ten methods and
the registered expected count is 9000 (300 circuits x 10 x 3 budgets).

The six fitted models, every validation rank, training arrays, seeds, clause counts,
counterexamples, individual deadlines and verifier counts are retained. Only
validation selects the three-seed model per feature variant. no_need13 computes
its features directly without backward-need masks or target-derived features.
The matched full21 control uses the same data, architecture and seed choices.

Direct CNF factors edit selectors, source selection and LUT bits. Glucose 4.2.1
via python-sat is fixed before performance. Each CEGIS candidate is full-checked;
counterexamples append row constraints. Encoding, solving and verification are
separately timed inside the common budget. Native interruption uses documented
solve_limited(expect_interrupt=True) and interrupt, never a failed solve as UNSAT.

The test reuses the known v2 cases, explicitly a diagnostic follow-up rather
than a new unopened final holdout. All methods run independently at 0.1, 1 and
10 seconds, with one timing run per budget; no trajectory reuse. Actual times,
failure-penalized times, stage observation counts, unknowns and timeouts are
separate. Verifier-check summaries explicitly condition on success. A common-
success subset is still conditional on the time budget, not an uncensored rank
distribution. UNSAT is bounded to the encoding, with no independently checked
proof certificate claimed. All accepted edits have independent NumPy audits.

Read result-ar.md for Arabic tables and summary.md/json/csv for all quantities.
All reported result numbers are generated by work/v3_report.py from raw logs.

From project root, with compatible Python on Windows (the tested platform):

    python -m pip install -r work/requirements-v3.txt
    python work/v3_analysis_validate.py
    python work/v3_report.py
    python work/v3_audit.py

The timing runner resumes existing IDs; do not overwrite previous runs or merge
reruns as new circuits. Code expects preserved v2 provenance files as part of
its audit. No public-benchmark, hardware, novelty or publication claim is made.

Official implementation references:
https://pysathq.github.io/docs/html/api/solvers.html
https://pysathq.github.io/docs/html/api/card.html
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    files={x for x in OUT.iterdir() if x.is_file() and x.suffix!='.zip'}
    files.add(PROTOCOL)
    files.update(ROOT/x for x in p['protected_sha256'])
    files.update(ROOT/x for x in imp['sources'])
    files.update(ROOT/'work'/x for x in ['v3_report.py','v3_audit.py','v3_analysis_validate.py'])
    # v3 case data are included; protected v2 raw metadata are retained for audit.
    files.add(ROOT/'outputs/fairness-v2/cases.jsonl')
    with zipfile.ZipFile(OUT/'raw_logs_and_code.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(files):z.write(file,str(file.relative_to(ROOT)))
    print(json.dumps({**record,'archive_bytes':(OUT/'raw_logs_and_code.zip').stat().st_size}))


if __name__=='__main__':main()
