"""All reported numbers are computed from immutable case/trial logs."""
import json,sys,math,csv,hashlib
from collections import Counter,defaultdict
from pathlib import Path
from decisive_engine import ROOT
import numpy as np
OUT=ROOT/'outputs/decisive-repair'

def wilson(k,n):
    if not n:return [None,None]
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-half),min(1,mid+half)]

def main():
    p=json.loads((OUT/'preregistration.json').read_text(encoding='utf-8'))
    records=[json.loads(l) for l in (OUT/'raw_trials.jsonl').read_text(encoding='utf-8').splitlines()]
    unique={r['trial_id']:r for r in records};assert len(unique)==len(records),'duplicate trials'
    expected=sum(g['count'] for g in p['groups'])*len(p['methods'])*len(p['settings'])
    if '--partial' not in sys.argv:assert len(records)==expected,(len(records),expected)
    groups=defaultdict(list)
    for r in records:groups[(r['group'],r['setting'],r['method'])].append(r)
    stats=[]
    for g in p['groups']:
        for setting in p['settings']:
            for method in p['methods']:
                rows=groups[(g['group'],setting,method)]
                if not rows:continue
                n=len(rows);success=sum(r['success'] for r in rows);accepted=sum(r['accepted'] for r in rows)
                wrong=sum(r['wrong_accepted'] for r in rows)
                actual=np.asarray([r['elapsed'] for r in rows]);pen=np.asarray([r['failure_penalized_seconds'] for r in rows])
                statuses=Counter(r['status'] for r in rows)
                timeouts=sum(r['status']=='timeout' or (r['status']=='solver_unknown' and 'timeout' in r.get('reason','').lower()) for r in rows)
                stats.append({'group':g['group'],'inputs':g['n'],'gates':g['gates'],'setting':setting,'method':method,'cases':n,
                    'successes':success,'success_rate':success/n,'success_wilson_95':wilson(success,n),
                    'accepted':accepted,'wrong_accepted':wrong,
                    'wrong_per_accepted':wrong/accepted if accepted else None,
                    'wrong_per_accepted_wilson_95':wilson(wrong,accepted),
                    'wrong_per_case':wrong/n,'timeouts':timeouts,'statuses':dict(statuses),
                    'mean_actual_seconds':float(actual.mean()),'median_actual_seconds':float(np.median(actual)),
                    'p95_actual_seconds':float(np.quantile(actual,.95)),
                    'mean_failure_penalized_seconds':float(pen.mean()),
                    'sum_actual_seconds':float(actual.sum())})
    comparisons=[];wins=[];penalized_wins=[];B=p['criteria']['bootstrap_replicates'];rng=np.random.default_rng(p['criteria']['bootstrap_seed'])
    for group in p['groups']:
        if group['group']=='old400':continue
        a={r['case_id']:r for r in groups[(group['group'],'full','learned')]}
        b={r['case_id']:r for r in groups[(group['group'],'full','cegis')]}
        ids=sorted(set(a)&set(b))
        if len(ids)!=group['count']:continue
        ds=np.asarray([int(a[k]['success'])-int(b[k]['success']) for k in ids])
        dt=np.asarray([b[k]['failure_penalized_seconds']-a[k]['failure_penalized_seconds'] for k in ids])
        da=np.asarray([b[k]['elapsed']-a[k]['elapsed'] for k in ids])
        ix=rng.integers(0,len(ids),(B,len(ids)))
        bs=ds[ix].mean(axis=1);bt=dt[ix].mean(axis=1);ba=da[ix].mean(axis=1)
        alpha=.05;adjusted=.05/18
        row={'group':group['group'],'pairs':len(ids),
             'success_difference_learned_minus_cegis':float(ds.mean()),
             'success_difference_ci95':list(map(float,np.quantile(bs,[alpha/2,1-alpha/2]))),
             'success_difference_bonferroni_ci':list(map(float,np.quantile(bs,[adjusted/2,1-adjusted/2]))),
             'penalized_time_advantage_cegis_minus_learned_seconds':float(dt.mean()),
             'penalized_time_advantage_ci95':list(map(float,np.quantile(bt,[alpha/2,1-alpha/2]))),
             'penalized_time_advantage_bonferroni_ci':list(map(float,np.quantile(bt,[adjusted/2,1-adjusted/2]))),
             'actual_time_advantage_cegis_minus_learned_seconds':float(da.mean()),
             'actual_time_advantage_ci95':list(map(float,np.quantile(ba,[alpha/2,1-alpha/2])))}
        row['success_criterion_pass']=row['success_difference_ci95'][0]>0
        row['time_criterion_pass']=row['actual_time_advantage_ci95'][0]>0
        row['penalized_time_criterion_pass']=row['penalized_time_advantage_ci95'][0]>0
        row['criterion_pass']=row['success_criterion_pass'] or row['time_criterion_pass']
        if row['criterion_pass']:wins.append(group['group'])
        if row['success_criterion_pass'] or row['penalized_time_criterion_pass']:penalized_wins.append(group['group'])
        comparisons.append(row)
    complete=len(records)==expected
    verdict=('useful' if wins else 'SAT/CEGIS dominates') if complete else 'INCOMPLETE'
    result={'log_rows':len(records),'expected_rows':expected,'complete':complete,'statistics':stats,
            'paired_comparisons':comparisons,'registered_criterion_label':verdict,'passing_groups':wins,
            'criterion_runtime':'actual measured wall-clock seconds, following user request and pre-analysis clarification',
            'secondary_failure_penalized_label':('useful' if penalized_wins else 'SAT/CEGIS dominates') if complete else 'INCOMPLETE',
            'secondary_failure_penalized_passing_groups':penalized_wins,
            'raw_log_sha256':hashlib.sha256((OUT/'raw_trials.jsonl').read_bytes()).hexdigest(),
            'model_sha256_unchanged':hashlib.sha256((ROOT/'outputs/local-repair-pilot/selected_model.json').read_bytes()).hexdigest()==p['model_sha256']}
    name='partial_summary' if not complete else 'summary'
    (OUT/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (OUT/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
        keys=[k for k in stats[0] if not isinstance(stats[0][k],(list,dict))]
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(stats)
    lines=['# Raw-log experiment report','',
           f"Trials: {len(records)} / {expected}. Budget: {p['same_common_wall_clock_budget_seconds']:.3f} s. Edits: {p['edit_budget']}. Sample rows: {p['sample_rows']}.",
           f"Frozen model hash unchanged: {int(result['model_sha256_unchanged'])}.",
           '', 'Time is measured search/acceptance wall time. Generation, imports/model compilation and independent after-the-fact audit are excluded. Failed trials are charged the full budget in the separately reported failure-penalized metric. All timeouts are failures.',
           '', '| Group | Spec | Method | Correct / N | Success % | Mean actual ms | Median ms | p95 ms | Mean penalized ms | Timeouts | Accepted | Wrong | Wrong / accepted % |',
           '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in stats:
        wrong='NA' if r['wrong_per_accepted'] is None else f"{100*r['wrong_per_accepted']:.2f}"
        lines.append(f"| {r['group']} | {r['setting']} | {r['method']} | {r['successes']}/{r['cases']} | {100*r['success_rate']:.2f} | {1000*r['mean_actual_seconds']:.3f} | {1000*r['median_actual_seconds']:.3f} | {1000*r['p95_actual_seconds']:.3f} | {1000*r['mean_failure_penalized_seconds']:.3f} | {r['timeouts']} | {r['accepted']} | {r['wrong_accepted']} | {wrong} |")
    lines+=['','## Paired bootstrap: larger sizes, full specification','',
            'Positive differences favor learned. Intervals below are unadjusted 95%; simultaneous Bonferroni intervals are retained in summary.json. The user criterion uses actual wall time. The initially added failure-penalized operationalization is retained as a secondary metric; see preanalysis_time_clarification.json.',
            '', '| Group | Δ success pp [95% CI] | Δ penalized ms [95% CI] | Δ actual ms [95% CI] | Criterion 0/1 |',
            '|---|---:|---:|---:|---:|']
    for r in comparisons:
        def interval(mean,key,scale):
            ci=r[key];return f"{r[mean]*scale:.3f} [{ci[0]*scale:.3f}, {ci[1]*scale:.3f}]"
        lines.append('| '+r['group']+' | '+interval('success_difference_learned_minus_cegis','success_difference_ci95',100)+' | '+interval('penalized_time_advantage_cegis_minus_learned_seconds','penalized_time_advantage_ci95',1000)+' | '+interval('actual_time_advantage_cegis_minus_learned_seconds','actual_time_advantage_ci95',1000)+f" | {int(r['criterion_pass'])} |")
    lines+=['',f'Registered criterion label: **{verdict}**.','',
        'Status counts, Wilson intervals, individual edits, counterexamples, timeout events and all per-case times are in the accompanying JSON/JSONL logs. No novelty or publication assessment is made.']
    (OUT/(name+'.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    indexed={(r['group'],r['setting'],r['method']):r for r in stats}
    compact=[f"Budget {p['same_common_wall_clock_budget_seconds']:.3f} s; max edits {p['edit_budget']}; sampled rows {p['sample_rows']}; trials {len(records)}/{expected}.",
             '', 'Full specification. Cell: correct/N; mean actual ms; timeouts.',
             '', '| Inputs/gates | Learned | SAT/CEGIS | Exhaustive |','|---|---:|---:|---:|']
    for group in p['groups']:
        label='old400 (6/18 + 7/22)' if group['group']=='old400' else f"{group['n']}/{group['gates']}"
        cells=[]
        for method in p['methods']:
            r=indexed.get((group['group'],'full',method))
            cells.append('NA' if r is None else f"{r['successes']}/{r['cases']}; {r['mean_actual_seconds']*1000:.2f}; {r['timeouts']}")
        compact.append('| '+label+' | '+' | '.join(cells)+' |')
    compact+=['','Sample-only specification. Cell: correct/N; wrong/accepted (wrong %); mean actual ms.',
              '', '| Inputs/gates | Learned | SAT/CEGIS | Exhaustive |','|---|---:|---:|---:|']
    for group in p['groups']:
        label='old400 (6/18 + 7/22)' if group['group']=='old400' else f"{group['n']}/{group['gates']}"
        cells=[]
        for method in p['methods']:
            r=indexed.get((group['group'],'sample',method))
            if r is None:cells.append('NA');continue
            wrong='NA' if r['wrong_per_accepted'] is None else f"{r['wrong_per_accepted']*100:.2f}%"
            cells.append(f"{r['successes']}/{r['cases']}; {r['wrong_accepted']}/{r['accepted']} ({wrong}); {r['mean_actual_seconds']*1000:.2f}")
        compact.append('| '+label+' | '+' | '.join(cells)+' |')
    compact+=['','Paired 95% CI, full setting. Positive differences favor learned.',
              '', '| Inputs/gates | Δ success pp [CI] | Δ actual ms [CI] |','|---|---:|---:|']
    for r in comparisons:
        def ci(mean,key,mul):
            a,b=r[key];return f"{r[mean]*mul:.2f} [{a*mul:.2f}, {b*mul:.2f}]"
        compact.append('| '+r['group']+' | '+ci('success_difference_learned_minus_cegis','success_difference_ci95',100)+' | '+ci('actual_time_advantage_cegis_minus_learned_seconds','actual_time_advantage_ci95',1000)+' |')
    compact+=['',f'Criterion label: **{verdict}**.']
    (OUT/'compact_report.md').write_text('\n'.join(compact)+'\n',encoding='utf-8')
    print(json.dumps({'completed':len(records),'expected':expected,'label':verdict,'passing_groups':wins}))

if __name__=='__main__':main()
