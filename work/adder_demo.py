"""A named illustrative task: repair a 2-bit adder without replacing a dead gate."""
import json,time
from circuit_pilot import ROOT,Circuit,evaluate,apply,legal_edits,TinyForest
from local_repair_pilot import local_features
from verify_pilot import reference
import numpy as np

def run():
    folder=ROOT/'outputs/local-repair-pilot'
    data=json.loads((folder/'selected_model.json').read_text(encoding='utf-8'))
    m=TinyForest(trees=len(data['trees']),depth=9,leaf=12)
    m.thresholds=[np.asarray(t) for t in data['thresholds']];m.models=data['trees']
    gold=Circuit(4,((0,2,8),(0,2,8),(1,3,6),(1,3,8),(0,2,6),(6,4,6),(6,4,8),(7,10,14)),(8,9,11))
    bad=Circuit(4,gold.gates,gold.outputs,0,0)
    rows=list(range(16));target=evaluate(gold,rows)
    for row in rows:
        a=(row&1)+2*((row>>1)&1);b=((row>>2)&1)+2*((row>>3)&1)
        bits=reference(gold,row);assert sum(bit<<k for k,bit in enumerate(bits))==a+b
    edits=list(legal_edits(bad))
    one_solutions=[e for e in edits if evaluate(apply(bad,e),rows)==target]
    assert not one_solutions
    # For this example all 16 specification rows are supplied to the proposer.
    # This differs from the 8-row main benchmark and is clearly labelled.
    frontier=[(bad,[])];found=None;checks=0;t=time.perf_counter()
    for depth in range(2):
        next_frontier=[]
        for c,path in frontier:
            edits=list(legal_edits(c));X=local_features(c,edits,rows,target)
            order=np.argsort(-m.predict_proba(X)[:,1],kind='stable')[:16]
            for idx in order:
                edit=edits[int(idx)];candidate=apply(c,edit);checks+=1
                if evaluate(candidate,rows)==target:found=path+[edit];break
                next_frontier.append((candidate,path+[edit]))
            if found:break
        if found:break
        frontier=next_frontier[:16]
    repaired=bad
    if found:
        for e in found:repaired=apply(repaired,e)
        for row in rows:assert reference(repaired,row)==reference(gold,row)
    result={'task':'2-bit unsigned addition','inputs':4,'gates':8,'outputs':3,
        'known_stuck_gate':0,'stuck_value':0,'one_edit_repairs':len(one_solutions),
        'learned_beam_width':16,'max_edits':2,'solved':found is not None,
        'edits':found,'exact_candidate_checks':checks,'seconds':time.perf_counter()-t,
        'independent_verification_rows':16 if found else 0,
        'specification_rows_given_to_proposer':16,
        'warning':'One hand-built illustrative adder with a spare carry gate, not a real-hardware benchmark.',
        'truth_table':[{'a':(r&1)+2*((r>>1)&1),'b':((r>>2)&1)+2*((r>>3)&1),
                       'expected':sum(v<<k for k,v in enumerate(reference(gold,r))),
                       'damaged':sum(v<<k for k,v in enumerate(reference(bad,r))),
                       'repaired':sum(v<<k for k,v in enumerate(reference(repaired,r))) if found else None} for r in rows]}
    (folder/'adder_demo.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
