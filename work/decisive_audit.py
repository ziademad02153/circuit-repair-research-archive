"""Post-run independent checks, provenance hashes, and reproducible raw-log bundle."""
import json,hashlib,zipfile,sys,time
from pathlib import Path
from dataclasses import asdict
from decisive_engine import ROOT,full_inputs
from circuit_pilot import make_case
import numpy as np

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'outputs/decisive-repair';p=json.loads((folder/'preregistration.json').read_text())
    assert (folder/'run.complete').exists()
    bits=[]
    for n in [6,7,10,12,16]:
        rows=np.arange(1<<n,dtype=np.uint32)
        for i,v in enumerate(full_inputs(n)):
            unpacked=np.unpackbits(np.frombuffer(v.to_bytes(((1<<n)+7)//8,'little'),dtype=np.uint8),bitorder='little')[:1<<n]
            assert np.array_equal(unpacked,((rows>>i)&1).astype(np.uint8))
        bits.append({'inputs':n,'rows':1<<n,'bits_checked':n*(1<<n),'pass':True})
    old=[]
    with (folder/'cases.jsonl').open() as f:
        for line in f:
            rec=json.loads(line)
            if rec['group']!='old400':continue
            c=make_case(rec['seed'],rec['damaged']['n'],len(rec['damaged']['gates']),8)
            checks={'damaged':json.loads(json.dumps(asdict(c['c'])))==rec['damaged'],
                    'gold':json.loads(json.dumps(asdict(c['gold'])))==rec['gold'],
                    'rows':c['rows']==rec['rows'],
                    'sample_target':list(c['sample_target'])==rec['sample_target'],
                    'full_target':list(map(hex,c['target']))==rec['full_target_hex']}
            assert all(checks.values()),(rec['case_id'],checks)
            old.append({'case_id':rec['case_id'],'checks':checks})
    sources=[ROOT/x for x in p['source_sha256']]
    hashes={str(x.relative_to(ROOT)):digest(x) for x in sources}
    assert hashes==p['source_sha256']
    model=ROOT/'outputs/local-repair-pilot/selected_model.json';assert digest(model)==p['model_sha256']
    out={'packed_input_bit_checks':bits,'old400_exact_reconstruction':old,
         'frozen_sources_unchanged':True,'frozen_model_unchanged':True,
         'source_hashes':hashes,'model_hash':digest(model),
         'report_script_sha256':digest(ROOT/'work/decisive_report.py')}
    (folder/'independent_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    readme='''# Decisive repair experiment

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
'''
    (folder/'README.md').write_text(readme,encoding='utf-8')
    include=[x for x in folder.iterdir() if x.is_file() and x.suffix!='.zip']
    include += [ROOT/'work'/x for x in ['decisive_engine.py','decisive_run.py','decisive_validate.py','decisive_report.py','decisive_audit.py','requirements-decisive.txt','circuit_pilot.py','local_repair_pilot.py','verify_pilot.py']]
    include += [model,ROOT/'outputs/decisive-repair-run.log',ROOT/'outputs/decisive-repair-stderr.log',ROOT/'outputs/decisive-repair-registration.log']
    archive=folder/'raw_logs_and_code.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in include:
            if file.exists():z.write(file,str(file.relative_to(ROOT)))
    print(json.dumps({'audit':'passed','old_cases_checked':len(old),'input_bits_checked':sum(x['bits_checked'] for x in bits),
                      'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive)}))

if __name__=='__main__':main()
