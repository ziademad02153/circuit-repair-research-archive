"""Independent bit-by-bit oracle and checks for the research pilots."""
import json,random,time
from circuit_pilot import Circuit,random_circuit,evaluate,lut,apply,legal_edits,structural_witness,ROOT

def reference(c,row):
    state=[bool((row>>j)&1) for j in range(c.n)]
    for j,(a,b,table) in enumerate(c.gates):
        assert 0<=a<c.n+j and 0<=b<c.n+j
        state.append(bool(c.stuck_value) if j==c.stuck else bool((table>>(int(state[a])+2*int(state[b])))&1))
    return tuple(int(state[o]) for o in c.outputs)

def run():
    t=time.perf_counter();rng=random.Random(1729);assignments=0
    for table in range(16):
        for a in [0,1]:
            for b in [0,1]:
                assert lut(a,b,table,1)==((table>>(a+2*b))&1)
    for i in range(120):
        n=3+i%5;ng=6+i%12
        c=random_circuit(rng,n,ng)
        if i%3==0:c=Circuit(n,c.gates,c.outputs,rng.randrange(ng),rng.randrange(2))
        rows=list(range(1<<n));packed=evaluate(c,rows)
        for k,row in enumerate(rows):
            assert tuple((v>>k)&1 for v in packed)==reference(c,row)
            assignments+=1
    gold=Circuit(3,((0,1,6),(0,1,6),(3,2,8),(3,2,6)),(5,6))
    bad=Circuit(gold.n,gold.gates,gold.outputs,0,0)
    rows=list(range(8));target=evaluate(gold,rows)
    edits=list(legal_edits(bad))
    one=[e for e in edits if evaluate(apply(bad,e),rows)==target]
    assert len(one)==0
    found=None;checked=0
    for e1 in edits:
        mid=apply(bad,e1)
        for e2 in legal_edits(mid):
            checked+=1
            if evaluate(apply(mid,e2),rows)==target:
                found=[e1,e2];break
        if found:break
    assert found is not None
    fixed_rows=[{'input':row,'target':reference(gold,row),'damaged':reference(bad,row),
                 'repaired':reference(apply(apply(bad,found[0]),found[1]),row)} for row in rows]
    for r in fixed_rows:assert r['target']==r['repaired']
    out={'all_16_boolean_operators_checked':True,'random_circuits':120,
         'independent_input_assignments_checked':assignments,
         'witness':{'zero_one_edit_solutions':len(one),'one_edit_candidates':len(edits),
                    'two_edit_search_candidates_checked':checked,'automatically_found_edits':found,
                    'truth_table':fixed_rows},'seconds':time.perf_counter()-t}
    path=ROOT/'outputs'/'circuit-pilot'/'independent_verification.json'
    path.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))

if __name__=='__main__':run()
