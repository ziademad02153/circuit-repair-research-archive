"""All v3 reported quantities derive from stored training/validation or raw trials."""
from __future__ import annotations
import json,hashlib,csv
from collections import defaultdict,Counter
from circuit_pilot import ROOT
import numpy as np

OUT=ROOT/'outputs/ablation-cnf-v3'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def contrast(index,ids,a,b,budget,rng):
    x=[index[(cid,budget,a)] for cid in ids];y=[index[(cid,budget,b)] for cid in ids]
    samples=rng.integers(0,len(ids),size=(10000,len(ids)))
    result={'a':a,'b':b,'budget_seconds':budget,'circuits':len(ids)}
    for key,left,right in [('success',[int(r['success']) for r in x],[int(r['success']) for r in y]),
                           ('actual_time',[r['elapsed'] for r in y],[r['elapsed'] for r in x]),
                           ('penalized_time',[r['failure_penalized_seconds'] for r in y],[r['failure_penalized_seconds'] for r in x])]:
        delta=np.asarray(left)-np.asarray(right);boot=delta[samples].mean(axis=1)
        result[key]={'difference':float(delta.mean()),'ci95':list(map(float,np.quantile(boot,[.025,.975]))),
                     'ci97_5':list(map(float,np.quantile(boot,[.0125,.9875])))}
    common=[(r['checks'],q['checks']) for r,q in zip(x,y) if r['success'] and q['success'] and r.get('checks') is not None and q.get('checks') is not None]
    result['matched_success_checks']={'pairs':len(common)}
    if common:
        z=np.asarray(common)
        for i,label in enumerate(['a','b']):
            result['matched_success_checks'][label]={'mean':float(z[:,i].mean()),'median':float(np.median(z[:,i])),
                'p90':float(np.quantile(z[:,i],.9)),'p95':float(np.quantile(z[:,i],.95))}
    return result


def main():
    p=json.loads((ROOT/'experiments/ablation-cnf-v3/protocol.json').read_text())
    complete=json.loads((OUT/'run.complete').read_text());assert digest(OUT/'raw_trials.jsonl')==complete['raw_sha256']
    rows=[json.loads(x) for x in (OUT/'raw_trials.jsonl').read_text().splitlines()]
    assert len(rows)==p['expected_trials'] and len({r['trial_id'] for r in rows})==len(rows)
    cases=[json.loads(x) for x in (OUT/'cases.jsonl').read_text().splitlines()];meta={c['case_id']:c for c in cases}
    ids=sorted(meta);larger=[cid for cid in ids if meta[cid]['damaged']['n']>=10];assert len(ids)==300 and len(larger)==250
    index={(r['case_id'],r['budget_seconds'],r['method']):r for r in rows}
    for cid in ids:
        for budget in p['budgets_seconds']:
            for method in p['methods']:assert (cid,budget,method) in index
    bad_unsat={r['case_id'] for r in rows if r['status']=='unsat'}
    observed_solved={r['case_id'] for r in rows if r['success']}
    assert not (bad_unsat & observed_solved),'UNSAT conflicts with a valid repair'
    exhausted={r['case_id'] for r in rows if r['status']=='exhausted'}
    assert not (exhausted & observed_solved),'complete exhaustion conflicts with a valid repair'
    groups=defaultdict(list)
    for r in rows:
        for scope in [r['group'],'all']+(['larger'] if r['inputs']>=10 else []):groups[(scope,r['budget_seconds'],r['method'])].append(r)
    stats=[];stage_names=['candidate_generation_seconds','feature_seconds','inference_seconds','sorting_seconds',
        'heuristic_ranking_seconds','encoding_seconds','sat_solve_seconds','verification_seconds']
    for (scope,budget,method),rr in sorted(groups.items()):
        t=np.array([r['elapsed'] for r in rr]);pen=np.array([r['failure_penalized_seconds'] for r in rr])
        success=[r for r in rr if r['success']];checks=[r['checks'] for r in success if r.get('checks') is not None]
        r={'scope':scope,'budget_seconds':budget,'method':method,'circuits':len(rr),
           'successes':len(success),'success_rate':len(success)/len(rr),
           'mean_actual_seconds':float(t.mean()),'median_actual_seconds':float(np.median(t)),
           'p90_actual_seconds':float(np.quantile(t,.9)),'p95_actual_seconds':float(np.quantile(t,.95)),
           'mean_failure_penalized_seconds':float(pen.mean()),'timeouts':sum(x['status']=='timeout' for x in rr),
           'unknown':sum(x['status']=='solver_unknown' for x in rr),'errors':sum(x['status']=='error' for x in rr),
           'wrong_accepted':sum(x['wrong_accepted'] for x in rr),'statuses':dict(Counter(x['status'] for x in rr)),
           'check_censored_trials':sum(x['status'] in ['timeout','solver_unknown'] for x in rr),
           'hard_kills':sum(x.get('hard_kill',False) for x in rr)}
        r['checks_among_successes']={'observations':len(checks),'mean':float(np.mean(checks)) if checks else None,
            'median':float(np.median(checks)) if checks else None,'p90':float(np.quantile(checks,.9)) if checks else None,
            'p95':float(np.quantile(checks,.95)) if checks else None}
        r['stages']={}
        for name in stage_names:
            values=[x[name] for x in rr if name in x]
            r['stages'][name]={'observed_trials':len(values),'mean_on_observed':float(np.mean(values)) if values else None,
                'p95_on_observed':float(np.quantile(values,.95)) if values else None}
        stats.append(r)
    rng=np.random.default_rng(p['statistics']['bootstrap_seed'])
    primary=[contrast(index,larger,'forest_full_selected','forest_no_need_selected',1.,rng),
             contrast(index,larger,'learned_frozen','cegis_cnf',1.,rng)]
    for c in primary:
        lo,hi=c['success']['ci97_5'];c['positive_success_evidence']=lo>0;c['negative_success_evidence']=hi<0
    contrasts=[]
    for budget in p['budgets_seconds']:
        for a,b in [('forest_full_selected','forest_no_need_selected'),('learned_frozen','cegis_cnf'),
                    ('forest_full_selected','cegis_cnf'),('learned_frozen','sample_error')]:
            contrasts.append(contrast(index,larger,a,b,budget,rng))
    size_contrasts=[]
    # Protocol secondary analysis only: fixed sizes and budgets, no subgroup
    # selection. Primary endpoints and their RNG draws above remain unchanged.
    for group in sorted({c['group'] for c in cases}):
        group_ids=[cid for cid in ids if meta[cid]['group']==group]
        for budget in p['budgets_seconds']:
            c=contrast(index,group_ids,'learned_frozen','cegis_cnf',budget,rng)
            c['group']=group;size_contrasts.append(c)
    fault=[]
    for budget in p['budgets_seconds']:
        for method in p['methods']:
            for ft in ['lut','wire','permanent']:
                rr=[r for r in rows if r['budget_seconds']==budget and r['method']==method and r['fault_type']==ft]
                fault.append({'budget_seconds':budget,'method':method,'fault_type':ft,'circuits':len(rr),
                              'successes':sum(r['success'] for r in rr),'success_rate':sum(r['success'] for r in rr)/len(rr)})
    unsat_by_solver={method:sorted({r['case_id'] for r in rows if r['method']==method and r['status']=='unsat'})
                     for method in ['cegis_cnf','cegis_z3']}
    solver_unsat=set(unsat_by_solver['cegis_cnf'])|set(unsat_by_solver['cegis_z3'])
    secondary=[]
    for scope,pop in [('all',ids),('larger',larger)]:
        remaining=[cid for cid in pop if cid not in solver_unsat]
        for budget in p['budgets_seconds']:
            for method in p['methods']:
                rr=[index[(cid,budget,method)] for cid in remaining]
                secondary.append({'scope':scope,'budget_seconds':budget,'method':method,
                    'excluded_solver_reported_unsat':len(pop)-len(remaining),'remaining_denominator':len(rr),
                    'successes':sum(r['success'] for r in rr),'rate':sum(r['success'] for r in rr)/len(rr) if rr else None})
    training=json.loads((OUT/'training_summary.json').read_text())
    original=json.loads((ROOT/'outputs/local-repair-pilot/selected_model.json').read_text())
    reproduced=json.loads((OUT/'model_full21_20261026.json').read_text())
    control_reproduced=(original['trees']==reproduced['trees'] and original['thresholds']==reproduced['thresholds'])
    result={'complete':True,'trials':len(rows),'test_circuits':len(ids),'larger_circuits':len(larger),
            'training_validation':training,'primary_comparisons':primary,'descriptive_budget_contrasts':contrasts,
            'statistics':stats,'fault_breakdown':fault,'descriptive_size_budget_contrasts':size_contrasts,
            'solver_reported_unsat_cases':unsat_by_solver,
            'unsat_union_count':len(solver_unsat),'observed_solved_union_count':len(observed_solved),
            'unknown_repairability_count':len(ids)-len(solver_unsat)-len(observed_solved),
            'secondary_excluding_solver_reported_unsat':secondary,
            'original_full_seed_model_reproduced':control_reproduced,
            'wrong_acceptances':sum(r['wrong_accepted'] for r in rows),
            'errors':sum(r['status']=='error' for r in rows),'hard_kills':sum(r.get('hard_kill',False) for r in rows),
            'all_accepted_independently_audited':all(r['independent_audited'] for r in rows if r['accepted']),
            'raw_sha256':digest(OUT/'raw_trials.jsonl'),'report_source_sha256':digest(__import__('pathlib').Path(__file__)),
            'scope':'Prospectively specified follow-up on previously inspected v2 circuits; not an untouched final test. Single timing run at each budget. No novelty or publication claim.'}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    scalar=[{k:v for k,v in r.items() if not isinstance(v,dict)} for r in stats]
    with (OUT/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(scalar[0]));w.writeheader();w.writerows(scalar)
    lookup={(r['scope'],r['budget_seconds'],r['method']):r for r in stats}
    lines=['# v3: need-feature ablation and CNF budget sweep','',
           f"Trials {len(rows)}; test circuits {len(ids)}; primary larger population {len(larger)}; one timing run per case/method/budget.",
           'Known v2 cases reused as a diagnostic follow-up. All 300 retained. Full checker; one non-noop edit; equal actual budgets.','',
           '## Training selection (validation only)','',
           '| Variant | RNG seed | Top-16 validation successes / cases | Mean clipped rank | Fit seconds |',
           '|---|---:|---:|---:|---:|']
    for r in training['all_models']:
        lines.append(f"| {r['variant']} | {r['training_seed']} | {r['validation_top16_successes']}/{r['validation_cases']} | {r['validation_mean_clipped_rank']:.3f} | {r['fit_seconds']:.3f} |")
    lines += ['',f"Original full-feature seed model exactly reproduced: {control_reproduced}.",'',
              '## Larger population success versus budget','',
              '| Method | 0.1 s | 1 s | 10 s |','|---|---:|---:|---:|']
    for method in p['methods']:
        cells=[]
        for budget in p['budgets_seconds']:
            r=lookup[('larger',budget,method)];cells.append(f"{r['successes']}/{r['circuits']} ({100*r['success_rate']:.2f}%)")
        lines.append('| '+method+' | '+' | '.join(cells)+' |')
    lines += ['','## Registered primary success contrasts, 1 second','',
              'Positive = first method minus second. Paired 97.5% intervals per endpoint; two-endpoint Bonferroni family.','',
              '| First | Second | Delta success pp | 97.5% CI |','|---|---|---:|---:|']
    for c in primary:
        d=c['success'];lo,hi=d['ci97_5']
        lines.append(f"| {c['a']} | {c['b']} | {100*d['difference']:.3f} | [{100*lo:.3f}, {100*hi:.3f}] |")
    lines += ['','## Descriptive frozen learner versus CNF at each budget','',
              'These 95% per-budget intervals are descriptive, not simultaneous claims across budgets.','',
              '| Budget s | Delta success pp [95% CI] | Actual time advantage ms [95% CI] | Penalized time advantage ms [95% CI] |','|---|---:|---:|---:|']
    for c in contrasts:
        if (c['a'],c['b'])!=('learned_frozen','cegis_cnf'):continue
        def fmt(key,scale):
            r=c[key];lo,hi=r['ci95'];return f"{scale*r['difference']:.3f} [{scale*lo:.3f}, {scale*hi:.3f}]"
        lines.append(f"| {c['budget_seconds']} | {fmt('success',100)} | {fmt('actual_time',1000)} | {fmt('penalized_time',1000)} |")
    lines += ['','## Per-size frozen learner versus CNF, descriptive','',
              'All registered sizes and budgets shown. Per-cell 95% intervals are not simultaneous or confirmatory subgroup tests. Positive success difference favors the learner.','',
              '| Size | Budget s | Learner successes | CNF successes | Delta success pp [95% CI] |',
              '|---|---:|---:|---:|---:|']
    for c in size_contrasts:
        a=lookup[(c['group'],c['budget_seconds'],'learned_frozen')]
        b=lookup[(c['group'],c['budget_seconds'],'cegis_cnf')]
        d=c['success'];lo,hi=d['ci95']
        lines.append(f"| {c['group']} | {c['budget_seconds']} | {a['successes']}/{a['circuits']} | {b['successes']}/{b['circuits']} | {100*d['difference']:.3f} [{100*lo:.3f}, {100*hi:.3f}] |")
    lines += ['','## Larger population timing and failures','',
              '| Budget | Method | Mean actual ms | Mean penalized ms | Timeout | Unknown | Wrong |',
              '|---|---|---:|---:|---:|---:|---:|']
    for budget in p['budgets_seconds']:
        for method in p['methods']:
            r=lookup[('larger',budget,method)]
            lines.append(f"| {budget} | {method} | {1000*r['mean_actual_seconds']:.3f} | {1000*r['mean_failure_penalized_seconds']:.3f} | {r['timeouts']} | {r['unknown']} | {r['wrong_accepted']} |")
    lines += ['','## CNF stages, larger population','',
              'Means include completed or partially executed measured stages; hard kills can have missing observations. Native/model initialization costs remain within/excluded as defined by protocol.','',
              '| Budget | Encoding mean ms (observed trials) | SAT solve mean ms (observed trials) | Verification mean ms |',
              '|---|---:|---:|---:|']
    for budget in p['budgets_seconds']:
        r=lookup[('larger',budget,'cegis_cnf')]
        cells=[]
        for name in ['encoding_seconds','sat_solve_seconds','verification_seconds']:
            v=r['stages'][name];cells.append('NA' if v['mean_on_observed'] is None else f"{1000*v['mean_on_observed']:.3f} ({v['observed_trials']})")
        lines.append(f"| {budget} | "+' | '.join(cells)+' |')
    lines += ['','## Verifier checks among successful trials only','',
              'Conditional on each method succeeding before its deadline. Not the same subset across methods and not uncensored ranks. Matched-success contrasts are in summary.json.','',
              '| Budget | Method | Successful observations | Mean checks | Median | p90 | p95 |','|---|---|---:|---:|---:|---:|---:|']
    for budget in p['budgets_seconds']:
        for method in p['methods']:
            c=lookup[('larger',budget,method)]['checks_among_successes']
            def num(x):return 'NA' if x is None else f'{x:.3f}'
            lines.append(f"| {budget} | {method} | {c['observations']} | {num(c['mean'])} | {num(c['median'])} | {num(c['p90'])} | {num(c['p95'])} |")
    lines += ['','## Repairability and integrity','',
              f"Unique solver-reported UNSAT cases (all 300): {len(solver_unsat)}. Observed solved union: {len(observed_solved)}. Still unknown: {len(ids)-len(solver_unsat)-len(observed_solved)}.",
              'UNSAT refers to the validated encoding in the exact one-edit domain; no independently checked SAT proof certificate is claimed. Primary denominator includes all cases. Secondary conditional rates, every size/fault/status and stage observation counts are in summary.json.',
              f"Wrong accepted: {result['wrong_acceptances']}; errors: {result['errors']}; hard kills: {result['hard_kills']}.",
              'No public/family-held-out benchmark or hardware experiment in this round. Removing the need-derived bundle also removes target-derived signals; it does not prove backward need propagation is uniquely necessary or better than every alternative target-conditioned representation.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    ar=['# نتيجة إزالة سمات الاحتياج والمقارنة مع CNF','',
        f"اكتملت {len(rows)} محاولة، على {len(ids)} دائرة معروفة من v2. الجدول التالي للأحجام الأكبر: {len(larger)} دائرة. تشغيل واحد مستقل لكل مهلة وطريقة.",'',
        '| الطريقة | نجاح عند 0.1 ثانية | نجاح عند ثانية | نجاح عند 10 ثوانٍ |','|---|---:|---:|---:|']
    labels={'learned_frozen':'المتعلم المجمد السابق','forest_full_selected':'الغابة الكاملة بضبط التحقق','forest_no_need_selected':'الغابة بدون سمات الاحتياج',
            'local_improvement':'قاعدة الاحتياج بلا تعلم','sample_error':'قاعدة خطأ العينة','cegis_z3':'Z3 القديم','cegis_cnf':'CNF المباشر'}
    for method in labels:
        cells=[]
        for budget in p['budgets_seconds']:
            r=lookup[('larger',budget,method)];cells.append(f"{r['successes']}/{r['circuits']} ({100*r['success_rate']:.2f}%)")
        ar.append('| '+labels[method]+' | '+' | '.join(cells)+' |')
    ar+=['','المقارنتان الأساسيتان عند ثانية، بفاصل 97.5% لكل منهما:','']
    for c in primary:
        d=c['success'];lo,hi=d['ci97_5']
        ar.append(f"- {labels[c['a']]} ناقص {labels[c['b']]}: {100*d['difference']:.3f} نقطة مئوية، الفاصل [{100*lo:.3f}, {100*hi:.3f}].")
    ar+=['','هذه إزالة لحزمة السمات المشتقة من الاحتياج، ولا تثبت أن الرسائل وحدها لا يمكن استبدالها بتمثيل آخر. لم نعد ضبط النماذج على نتائج الاختبار. الحالات نفسها سبق الاطلاع عليها، لذلك هذا اختبار متابعة وليس اختبارًا نهائيًا جديدًا لم يُفتح.',
         'تفاصيل الزمن وبناء CNF والمهل والفحوص وUNSAT في [التقرير الكامل](summary.md)، وجميع البيانات المشتقة في [summary.json](summary.json). لا استنتاج عن الجدة أو القبول في مجلة من هذه الأرقام.']
    (OUT/'result-ar.md').write_text('\n'.join(ar)+'\n',encoding='utf-8')
    print(json.dumps({'trials':len(rows),'primary':primary,'unsat_union':len(solver_unsat),
                      'observed_solved_union':len(observed_solved),'unknown':result['unknown_repairability_count'],
                      'wrong':result['wrong_acceptances'],'errors':result['errors']}))


if __name__=='__main__':main()
