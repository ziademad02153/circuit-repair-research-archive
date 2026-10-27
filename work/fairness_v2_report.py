"""Read immutable raw observations; keep circuit pairs and timing repeats together."""
from __future__ import annotations
import json,hashlib,csv,sys
from collections import defaultdict,Counter
from fairness_v2_methods import ROOT,METHODS,RULES
import numpy as np

OUT=ROOT/'outputs/fairness-v2'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def contrast(index, ids, comparator, B, rng):
    def mean_metric(cid,method,key):return np.mean([index[(cid,r,method)][key] for r in range(2)])
    success=np.asarray([mean_metric(k,'learned','success')-mean_metric(k,comparator,'success') for k in ids])
    penal=np.asarray([mean_metric(k,comparator,'failure_penalized_seconds')-mean_metric(k,'learned','failure_penalized_seconds') for k in ids])
    actual=np.asarray([mean_metric(k,comparator,'elapsed')-mean_metric(k,'learned','elapsed') for k in ids])
    ix=rng.integers(0,len(ids),size=(B,len(ids)))
    result={'comparator':comparator,'unique_circuits':len(ids),'repeats_per_circuit':2}
    for label,values in [('success',success),('penalized_time',penal),('actual_time',actual)]:
        boot=values[ix].mean(axis=1)
        result[label]={'difference':float(values.mean()),
                       'ci95':list(map(float,np.quantile(boot,[.025,.975]))),
                       'ci97_5':list(map(float,np.quantile(boot,[.0125,.9875])))}
    return result


def main():
    p=json.loads((OUT/'preregistration.json').read_text());selection=json.loads((OUT/'selection.json').read_text())
    complete=json.loads((OUT/'run.complete').read_text())
    assert digest(OUT/'raw_trials.jsonl')==complete['raw_sha256']
    assert digest(OUT/'cases.jsonl')==complete['cases_sha256']
    assert digest(OUT/'selection.json')==complete['selection_sha256']
    rows=[json.loads(x) for x in (OUT/'raw_trials.jsonl').read_text().splitlines()]
    assert len(rows)==4380 and len({r['trial_id'] for r in rows})==4380
    test=[r for r in rows if r['phase']=='test'];assert len(test)==4200
    cases=[json.loads(x) for x in (OUT/'cases.jsonl').read_text().splitlines()]
    meta={r['case_id']:r for r in cases};ids=sorted({r['case_id'] for r in test});assert len(ids)==300
    index={(r['case_id'],r['repeat'],r['method']):r for r in test}
    for cid in ids:
        for repeat in range(2):
            for method in METHODS:assert (cid,repeat,method) in index
        assert [index[(cid,0,m)]['position'] for m in METHODS]==[6-index[(cid,1,m)]['position'] for m in METHODS]
    larger=[k for k in ids if meta[k]['damaged']['n']>=10];assert len(larger)==250
    rng=np.random.default_rng(p['statistics']['seed']);B=p['statistics']['bootstrap_replicates']
    primary=contrast(index,larger,selection['selected_rule'],B,rng)
    slo,shi=primary['success']['ci97_5'];tlo,thi=primary['penalized_time']['ci97_5']
    positive_success=slo>0;positive_time=tlo>0;negative_success=shi<0;negative_time=thi<0
    if (positive_success and negative_time) or (positive_time and negative_success):verdict='tradeoff'
    elif positive_success or positive_time:verdict='learned benefit demonstrated in a registered endpoint'
    elif negative_success or negative_time:verdict='selected simple rule advantage; no learned benefit demonstrated'
    else:verdict='no learned benefit demonstrated'
    primary['decision']=verdict;primary['success_benefit']=positive_success;primary['penalized_time_benefit']=positive_time
    comparisons=[]
    for method in METHODS:
        if method!='learned':
            r=contrast(index,larger,method,B,rng);r['scope']='larger_pooled';comparisons.append(r)
    grouped=defaultdict(list)
    for r in test:
        grouped[(r['group'],r['method'])].append(r)
        grouped[('all',r['method'])].append(r)
        if r['inputs']>=10:grouped[('larger',r['method'])].append(r)
    stats=[]
    groupnames=[g['group'] for g in p['groups']]+['all','larger']
    for group in groupnames:
        for method in METHODS:
            rr=grouped[(group,method)];statuses=Counter(r['status'] for r in rr)
            times=np.asarray([r['elapsed'] for r in rr]);pen=np.asarray([r['failure_penalized_seconds'] for r in rr])
            accepted=[r for r in rr if r['accepted']]
            check_records=[r['checks'] for r in rr if 'checks' in r]
            stage={}
            for key in ['candidate_generation_seconds','feature_seconds','inference_seconds','sorting_seconds','checking_seconds']:
                values=[r[key] for r in rr if key in r]
                stage[key]={'observed_trials':len(values),'mean_on_observed':float(np.mean(values)) if values else None}
            stat={'group':group,'method':method,'unique_circuits':len({r['case_id'] for r in rr}),
                  'timed_trials':len(rr),'successes':sum(r['success'] for r in rr),
                  'success_rate':sum(r['success'] for r in rr)/len(rr),
                  'mean_actual_seconds':float(times.mean()),'median_actual_seconds':float(np.median(times)),
                  'p95_actual_seconds':float(np.quantile(times,.95)),
                  'mean_failure_penalized_seconds':float(pen.mean()),
                  'timeouts':sum(r['status']=='timeout' or (r['status']=='solver_unknown' and 'timeout' in r.get('reason','').lower()) for r in rr),
                  'hard_kills':sum(r.get('hard_kill',False) for r in rr),
                  'wrong_accepted':sum(r['wrong_accepted'] for r in rr),'accepted':len(accepted),
                  'errors':statuses.get('error',0),'statuses':dict(statuses),
                  'mean_checks_on_trials_with_check_count':float(np.mean(check_records)) if check_records else None,
                  'check_count_observed_trials':len(check_records),'stages':stage}
            stats.append(stat)
    fault=[]
    for name in ['lut','wire','permanent']:
        for method in METHODS:
            rr=[r for r in test if r['fault_type']==name and r['method']==method]
            fault.append({'fault_type':name,'method':method,'unique_circuits':len({r['case_id'] for r in rr}),
                          'timed_trials':len(rr),'successes':sum(r['success'] for r in rr),
                          'success_rate':sum(r['success'] for r in rr)/len(rr),
                          'mean_penalized_seconds':float(np.mean([r['failure_penalized_seconds'] for r in rr]))})
    result={'complete':True,'development_trials':len(rows)-len(test),'test_trials':len(test),
            'unique_test_circuits':len(ids),'primary_unique_circuits':len(larger),
            'selection':selection,'primary':primary,'exploratory_comparisons':comparisons,
            'statistics':stats,'fault_breakdown':fault,'raw_sha256':digest(OUT/'raw_trials.jsonl'),
            'report_script_sha256':digest(__import__('pathlib').Path(__file__)),
            'all_accepted_independently_audited':all(r['independent_audited'] for r in rows if r['accepted']),
            'v1_protected_files_unchanged':all(digest(ROOT/k)==v for k,v in p['v1_protected_sha256'].items()),
            'frozen_model_unchanged':digest(ROOT/'outputs/local-repair-pilot/selected_model.json')==p['model_sha256'],
            'source_hashes_unchanged':all(digest(ROOT/k)==v for k,v in p['source_sha256'].items())}
    assert all(result[k] for k in ['all_accepted_independently_audited','v1_protected_files_unchanged','frozen_model_unchanged','source_hashes_unchanged'])
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    scalar=[{k:v for k,v in r.items() if not isinstance(v,dict)} for r in stats]
    with (OUT/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(scalar[0]));w.writeheader();w.writerows(scalar)
    lines=['# Learning versus simple rules: raw-log report','',
           f"Development: {len(rows)-len(test)} trials. Test: {len(test)} trials on {len(ids)} distinct circuits, two timing repeats. Budget {p['budget_seconds']:.3f} s, one edit, full checker, frozen model.",
           f"Primary simple comparator selected before test: **{selection['selected_rule']}**.",'',
           '## Primary comparison','',
           f"Population: {len(larger)} larger circuits (n >= 10), paired by circuit with timing repeats averaged. Two co-primary endpoints use 97.5% intervals each, Bonferroni family of two.",'',
           '| Endpoint (positive favors learned) | Difference | 97.5% CI |','|---|---:|---:|']
    for key,scale,unit in [('success',100,'percentage points'),('penalized_time',1000,'ms'),('actual_time',1000,'ms')]:
        r=primary[key];lo,hi=r['ci97_5']
        label=key+(' (descriptive, not primary)' if key=='actual_time' else '')
        lines.append(f"| {label} | {r['difference']*scale:.3f} {unit} | [{lo*scale:.3f}, {hi*scale:.3f}] |")
    lines += ['',f"Registered decision: **{verdict}**.",'',
              'Penalized time charges a full one-second budget to failures. Actual time is separately retained: a method that exhausts early is not credited as a faster successful repair.','',
              '## Larger pooled results','',
              '| Method | Correct / trials | Success % | Mean actual ms | Mean penalized ms | Timeouts | Wrong accepted |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for r in stats:
        if r['group']=='larger':
            lines.append(f"| {r['method']} | {r['successes']}/{r['timed_trials']} | {100*r['success_rate']:.2f} | {1000*r['mean_actual_seconds']:.3f} | {1000*r['mean_failure_penalized_seconds']:.3f} | {r['timeouts']} | {r['wrong_accepted']} |")
    lines+=['','## Every size','',
            'Each cell: correct / 100 timed trials (50 unique circuits, two repeats); mean actual ms; timeouts. Repeats are not independent circuits.','',
            '| Inputs/gates | '+' | '.join(METHODS)+' |','|---|'+'---:|'*len(METHODS)]
    lookup={(r['group'],r['method']):r for r in stats}
    for g in p['groups']:
        cells=[]
        for m in METHODS:
            r=lookup[(g['group'],m)]
            cells.append(f"{r['successes']}/{r['timed_trials']}; {1000*r['mean_actual_seconds']:.2f}; {r['timeouts']}")
        lines.append(f"| {g['n']}/{g['gates']} | "+' | '.join(cells)+' |')
    lines+=['','## Exploratory larger-population contrasts','',
            'Unadjusted 95% intervals below are descriptive; only the preselected comparator and two registered endpoints determine the primary decision.','',
            '| Comparator | Delta success pp [95% CI] | Penalized time advantage ms [95% CI] |',
            '|---|---:|---:|']
    for r in comparisons:
        def fmt(k,scale):
            d=r[k];a,b=d['ci95'];return f"{scale*d['difference']:.3f} [{scale*a:.3f}, {scale*b:.3f}]"
        lines.append(f"| {r['comparator']} | {fmt('success',100)} | {fmt('penalized_time',1000)} |")
    lines += ['','## Scope and audit','',
              f"Wrong acceptances (all development/test trials): {sum(r['wrong_accepted'] for r in rows)}. Errors: {sum(r['status']=='error' for r in rows)}. Hard watchdog kills: {sum(r.get('hard_kill',False) for r in rows)}.",
              'All accepted repairs have independent NumPy truth-vector audits. Original sources, model and protected v1 files match their registered hashes.',
              'This is an unseen-seed synthetic test, not a circuit-family/industrial benchmark study. No retrained no-need-feature ablation, stronger CNF SAT implementation, budget sweep or hardware experiment has been run here. No novelty or publication-readiness conclusion follows from this comparison.','',
              'Stage timings in summary.json are available only for completed stages/trials; missing timeout-stage timings are not zero. Fault-stratified results and all method statuses are also retained.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    compact='\n'.join(lines[:lines.index('## Every size')])+'\n'
    (OUT/'compact_report.md').write_text(compact,encoding='utf-8')
    arabic_labels={'tradeoff':'مفاضلة بين النجاح والزمن؛ لا تفوق مطلق.',
        'learned benefit demonstrated in a registered endpoint':'ظهر مكسب للتعلم في مقياس أساسي مسجل؛ تراجع المقاييس الأخرى وحدود التجربة.',
        'selected simple rule advantage; no learned benefit demonstrated':'ظهرت أفضلية للقاعدة البسيطة في مقياس أساسي؛ لم يثبت مكسب للتعلم.',
        'no learned benefit demonstrated':'لم يثبت مكسب للتعلم وفق المقياسين الأساسيين المسجلين.'}
    ar=['# نتيجة اختبار التعلم أمام القاعدة البسيطة','',arabic_labels[verdict],'',
        f"القاعدة الأساسية: `{selection['selected_rule']}`، مختارة على التطوير قبل الاختبار. الاختبار الكامل: {len(ids)} دائرة مستقلة، و{len(test)} محاولة توقيت. التحليل الأساسي على {len(larger)} دائرة أكبر، بتكرارين لكل طريقة.",'',
        '| الطريقة | نجاح المحاولات | النسبة | متوسط الزمن الفعلي ms | متوسط الزمن المعاقب ms |',
        '|---|---:|---:|---:|---:|']
    for r in stats:
        if r['group']=='larger':
            ar.append(f"| {r['method']} | {r['successes']}/{r['timed_trials']} | {100*r['success_rate']:.2f}% | {1000*r['mean_actual_seconds']:.2f} | {1000*r['mean_failure_penalized_seconds']:.2f} |")
    ar+=['','الفروق التالية موجبة لصالح المتعلم؛ فاصل كل مقياس أساسي 97.5% لتصحيح مقارنتين:','']
    for key,label,scale,unit in [('success','فرق النجاح',100,'نقطة مئوية'),('penalized_time','أفضلية الزمن المعاقب',1000,'ms')]:
        r=primary[key];lo,hi=r['ci97_5']
        ar.append(f"- {label}: {scale*r['difference']:.3f} {unit}، الفاصل [{scale*lo:.3f}, {scale*hi:.3f}].")
    ar+=['','الزمن المعاقب يحتسب ثانية كاملة للإخفاق. فواصل الثقة تجمع التكرارات داخل الدائرة نفسها. النتائج تخص مولدنا العشوائي وهذه المهلة فقط، ولا تثبت جدة الفكرة أو جاهزية النشر.',
         'الخطوة العلمية اللاحقة تعتمد على النتيجة: إن لم يثبت مكسب التعلم فلا نستمر بادعاء أفضلية النموذج؛ نراجع ما إذا كانت قاعدة الاحتياج تقدم قيمة مستقلة، مع مقارنة رمزية أقوى ودوائر معيارية.','',
         '[التقرير الكامل](summary.md) · [البيانات المشتقة](summary.json) · [السجلات الخام](raw_trials.jsonl)']
    (OUT/'result-ar.md').write_text('\n'.join(ar)+'\n',encoding='utf-8')
    print(json.dumps({'primary':primary,'v1_unchanged':result['v1_protected_files_unchanged'],
                      'wrong_accepted':sum(r['wrong_accepted'] for r in rows)}))


if __name__=='__main__':main()
