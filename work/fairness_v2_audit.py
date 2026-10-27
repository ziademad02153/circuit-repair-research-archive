"""Verify selection chronology, frozen provenance and package complete raw evidence."""
import json,hashlib,zipfile
from pathlib import Path
from fairness_v2_methods import ROOT

OUT=ROOT/'outputs/fairness-v2'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=json.loads((OUT/'preregistration.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text());assert summary['complete']
    data=(OUT/'raw_trials.jsonl').read_bytes();lines=data.splitlines(keepends=True)
    rows=[json.loads(x) for x in lines]
    assert len(rows)==4380 and len({r['trial_id'] for r in rows})==4380
    assert all(r['phase']=='development' for r in rows[:180])
    assert all(r['phase']=='test' for r in rows[180:])
    assert hashlib.sha256(b''.join(lines[:180])).hexdigest()==sel['development_log_sha256_at_selection']
    assert sel['test_trials_seen']==0
    new=[json.loads(x) for x in (OUT/'cases.jsonl').read_text().splitlines()]
    old=[json.loads(x) for x in (ROOT/'outputs/decisive-repair/cases.jsonl').read_text().splitlines()]
    assert not ({r['seed'] for r in new}&{r['seed'] for r in old})
    oldfp={hashlib.sha256(json.dumps(r['gold'],sort_keys=True).encode()).hexdigest() for r in old}
    assert not (oldfp & {r['gold_fingerprint'] for r in new})
    assert len({r['gold_fingerprint'] for r in new})==len(new)
    for rel,h in {**p['source_sha256'],**p['v1_protected_sha256']}.items():assert digest(ROOT/rel)==h,rel
    assert digest(ROOT/'outputs/local-repair-pilot/selected_model.json')==p['model_sha256']
    for r in rows:
        assert r['accepted']==(r['status']=='accepted' and r['elapsed']<=p['budget_seconds'])
        assert not r['success'] or (r['accepted'] and r['independent_audited'] and r['audit_wrong_rows']==0)
        if not r['success']:assert r['failure_penalized_seconds']==p['budget_seconds']
    record={'audit':'passed','raw_trials':len(rows),'unique_test_circuits':len({r['case_id'] for r in rows if r['phase']=='test'}),
            'development_selection_prefix_hash_verified':True,'test_seen_at_selection':sel['test_trials_seen'],
            'all_gold_fingerprints_unique_and_disjoint_from_v1':True,
            'frozen_sources_model_and_v1_logs_unchanged':True,
            'independent_acceptance_checks':sum(r['independent_audited'] for r in rows),
            'wrong_acceptances':sum(r['wrong_accepted'] for r in rows),
            'raw_sha256':digest(OUT/'raw_trials.jsonl'),
            'report_source_sha256':digest(ROOT/'work/fairness_v2_report.py'),
            'audit_source_sha256':digest(Path(__file__))}
    (OUT/'audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    readme='''# Fairness and learning ablation follow-up

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
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    files={x for x in OUT.iterdir() if x.is_file() and x.suffix!='.zip'}
    files.update(ROOT/rel for rel in p['source_sha256'])
    files.update(ROOT/rel for rel in p['v1_protected_sha256'])
    files.update(ROOT/'work'/x for x in ['fairness_v2_report.py','fairness_v2_analysis_validate.py',
        'fairness_v2_audit.py','verify_pilot.py','requirements-decisive.txt'])
    files.add(ROOT/'outputs/local-repair-pilot/selected_model.json')
    if (ROOT/'docs/fairness-review-v2.md').exists():files.add(ROOT/'docs/fairness-review-v2.md')
    with zipfile.ZipFile(OUT/'raw_logs_and_code.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(files):z.write(file,str(file.relative_to(ROOT)))
    print(json.dumps({**record,'archive_bytes':(OUT/'raw_logs_and_code.zip').stat().st_size}))


if __name__=='__main__':main()
