"""Functional preflight on separate tiny seeds; no learned-model tuning."""
import json,time,sys
from decisive_engine import ROOT,Circuit,full_inputs,full_values,make_problem,sampled_values,row_targets,cegis,exhaustive,learned,load_model
from circuit_pilot import evaluate,legal_edits,apply
from verify_pilot import reference
import z3

def run():
    records=[];model=load_model()
    for n in [3,4,6,10,12,16]:
        inp=full_inputs(n)
        for row in [0,1,2,(1<<n)//2,(1<<n)-1]:
            assert tuple((x>>row)&1 for x in inp)==tuple((row>>i)&1 for i in range(n))
    for i in range(20):
        case=make_problem(3100000+i,4,6)
        c=case['c'];target=case['target']
        assert full_values(c)==evaluate(c,range(16))
        for row in range(16):
            assert tuple((v>>row)&1 for v in full_values(c))==reference(c,row)
        for setting in ['full','sample']:
            payload={'c':c,'seed':case['seed'],'rows':case['rows'],'sample_target':case['sample_target'],
                     'setting':setting,'target_full':target if setting=='full' else None}
            possible=[]
            for e in legal_edits(c):
                new=apply(c,e)
                if (full_values(new)==target if setting=='full' else sampled_values(new,case['rows'])==case['sample_target']):possible.append(e)
            result=cegis(payload,time.perf_counter(),20,lambda d:None,z3)
            assert (result['status']=='accepted')==bool(possible),(i,setting,result,len(possible))
            if result['status']=='accepted':assert tuple(result['edit']) in possible
            records.append({'seed':case['seed'],'setting':setting,'valid_candidates':len(possible),
                            'z3_status':result['status'],'z3_checks':result.get('checks')})
    path=ROOT/'outputs/decisive-repair/preflight.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'bit_patterns_checked_n':[3,4,6,10,12,16],
        'exhaustive_vs_cegis_cases':records,'z3_version':z3.get_version_string()},indent=2),encoding='utf-8')
    print(json.dumps({'preflight':'passed','comparisons':len(records),'z3':z3.get_version_string()}))

if __name__=='__main__':run()
