"""Frozen learned proposer, exhaustive repair, and Z3/CEGIS; one common edit space."""
from __future__ import annotations
import sys,time,json,random,functools,gc
from pathlib import Path
from collections import Counter
from circuit_pilot import ROOT,Circuit,apply,legal_edits,random_circuit,ancestors,lut,TinyForest
from local_repair_pilot import local_features
import numpy as np

class Deadline(Exception):pass

@functools.lru_cache(maxsize=24)
def full_inputs(n):
    count=1<<n;nb=(count+7)//8
    out=[]
    for i in range(n):
        if i<3:
            v=int.from_bytes(bytes([0xaa,0xcc,0xf0][i:i+1])*nb,'little')
            # The singleton-list expression above produces one byte.
        else:
            half=(1<<i)//8
            v=int.from_bytes((b'\x00'*half+b'\xff'*half)*(nb//(2*half)),'little')
        out.append(v&((1<<count)-1))
    return tuple(out)

def full_values(c):
    mask=(1<<(1<<c.n))-1;values=list(full_inputs(c.n))
    for j,(a,b,t) in enumerate(c.gates):
        values.append((mask if c.stuck_value else 0) if j==c.stuck else lut(values[a],values[b],t,mask))
    return tuple(values[o] for o in c.outputs)

def sampled_values(c,rows):
    mask=(1<<len(rows))-1
    vals=[sum(((r>>i)&1)<<k for k,r in enumerate(rows)) for i in range(c.n)]
    for j,(a,b,t) in enumerate(c.gates):
        vals.append((mask if c.stuck_value else 0) if j==c.stuck else lut(vals[a],vals[b],t,mask))
    return tuple(vals[o] for o in c.outputs)

def row_targets(target,rows):
    return tuple(sum(((v>>r)&1)<<k for k,r in enumerate(rows)) for v in target)

def make_problem(seed,n,ng):
    """Same RNG sequence and harmful-fault conditioning as original make_case."""
    rng=random.Random(seed)
    for attempt in range(200):
        gold=random_circuit(rng,n,ng);target=full_values(gold)
        active=sorted(set.union(*(ancestors(gold,o) for o in gold.outputs)))
        j=rng.choice([s-n for s in active if s>=n])
        mode=rng.choices(['lut','wire','permanent'],[.4,.4,.2])[0]
        if mode=='permanent':bad=Circuit(n,gold.gates,gold.outputs,j,rng.randrange(2))
        elif mode=='lut':bad=apply(gold,('lut',j,2,gold.gates[j][2]^(1<<rng.randrange(4))))
        else:
            slot=rng.randrange(2)
            source=rng.choice([x for x in range(n+j) if x!=gold.gates[j][slot]])
            bad=apply(gold,('wire',j,slot,source))
        if full_values(bad)==target:continue
        rows=rng.sample(range(1<<n),8)
        return {'seed':seed,'fault_type':mode,'attempt':attempt,'gold':gold,'c':bad,
                'target':target,'rows':rows,'sample_target':row_targets(target,rows)}
    raise RuntimeError('failed generation')

def load_model():
    p=ROOT/'outputs/local-repair-pilot/selected_model.json'
    d=json.loads(p.read_text(encoding='utf-8'))
    m=TinyForest(trees=len(d['trees']),depth=9,leaf=12)
    m.thresholds=[np.asarray(t) for t in d['thresholds']];m.models=d['trees'];m.compile()
    return m

def mismatch(c,target):
    values=full_values(c);delta=0
    for a,b in zip(values,target):delta|=a^b
    return None if not delta else (delta&-delta).bit_length()-1

def check_time(start,budget):
    if time.perf_counter()-start>=budget:raise Deadline()

def learned(payload,model,start,budget,emit):
    c=payload['c'];rows=payload['rows'];target=payload['sample_target']
    edits=list(legal_edits(c));check_time(start,budget)
    X=local_features(c,edits,rows,target);check_time(start,budget)
    scores=model.predict_proba(X)[:,1];check_time(start,budget)
    ties=np.random.default_rng(payload['seed']+17).random(len(edits))
    order=np.lexsort((ties,-scores));check_time(start,budget)
    emit({'phase':'ranked','candidates':len(edits)})
    checks=0
    for idx in order:
        check_time(start,budget);edit=edits[int(idx)];new=apply(c,edit);checks+=1
        passed=(mismatch(new,payload['target_full']) is None) if payload['setting']=='full' else sampled_values(new,rows)==target
        check_time(start,budget)
        if passed:return {'status':'accepted','edit':edit,'checks':checks,'candidate_count':len(edits)}
        if checks%64==0:emit({'phase':'checking','checks':checks})
    return {'status':'exhausted','checks':checks,'candidate_count':len(edits)}

def exhaustive(payload,start,budget,emit):
    c=payload['c'];checks=0
    for edit in legal_edits(c):
        check_time(start,budget);checks+=1;new=apply(c,edit)
        passed=(mismatch(new,payload['target_full']) is None) if payload['setting']=='full' else sampled_values(new,payload['rows'])==payload['sample_target']
        check_time(start,budget)
        if passed:return {'status':'accepted','edit':edit,'checks':checks}
        if checks%64==0:emit({'phase':'checking','checks':checks})
    return {'status':'exhausted','checks':checks}

def cegis(payload,start,budget,emit,z3):
    c=payload['c'];ng=len(c.gates);ctx=z3.Context();solver=z3.Solver(ctx=ctx)
    # Sound cone localization: a single modified gate must affect every output
    # currently disagreeing with the available specification. No valid repair
    # is removed. Unaffected gates can be constant-folded for each input block.
    observed=full_values(c) if payload['setting']=='full' else sampled_values(c,payload['rows'])
    wanted=payload['target_full'] if payload['setting']=='full' else payload['sample_target']
    bad_outputs=[o for o,a,b in zip(c.outputs,observed,wanted) if a!=b]
    eligible=set(range(ng))-{c.stuck}
    for output in bad_outputs:
        eligible&={s-c.n for s in ancestors(c,output) if s>=c.n}
    if not eligible:return {'status':'unsat','checks':0,'reason':'disjoint output cones'}
    affected=set()
    for j,(a,b,t) in enumerate(c.gates):
        if j!=c.stuck and (j in eligible or a in affected or b in affected):affected.add(c.n+j)
    eg=z3.Int('edit_gate',ctx=ctx);kind=z3.Bool('is_lut',ctx=ctx)
    slot=z3.Int('wire_slot',ctx=ctx);source=z3.Int('wire_source',ctx=ctx)
    table=z3.BitVec('new_lut',4,ctx=ctx)
    solver.add(eg>=0,eg<ng,eg!=c.stuck)
    solver.add(z3.Or(*[eg==j for j in sorted(eligible)]))
    solver.add(z3.Implies(z3.Not(kind),z3.And(slot>=0,slot<2,source>=0,source<c.n+eg)))
    for j,(a,b,t) in enumerate(c.gates):
        solver.add(z3.Implies(z3.And(eg==j,kind),table!=z3.BitVecVal(t,4,ctx=ctx)))
        solver.add(z3.Implies(z3.And(eg==j,z3.Not(kind),slot==0),source!=a))
        solver.add(z3.Implies(z3.And(eg==j,z3.Not(kind),slot==1),source!=b))
    block=0;seen=set(payload['rows']);checks=0
    def add_rows(rows,targets):
        nonlocal block
        check_time(start,budget);width=len(rows)
        state=z3.Array('state_'+str(block),z3.IntSort(ctx),z3.BitVecSort(width,ctx));block+=1
        zero=z3.BitVecVal(0,width,ctx);allone=z3.BitVecVal((1<<width)-1,width,ctx)
        constants=[sum(((r>>i)&1)<<k for k,r in enumerate(rows)) for i in range(c.n)]
        mask=(1<<width)-1
        for j,(a,b,t) in enumerate(c.gates):
            constants.append((mask if c.stuck_value else 0) if j==c.stuck else lut(constants[a],constants[b],t,mask))
        for i in range(c.n):
            bits=sum(((r>>i)&1)<<k for k,r in enumerate(rows))
            solver.add(z3.Select(state,i)==z3.BitVecVal(bits,width,ctx))
        for j,(a,b,t) in enumerate(c.gates):
            check_time(start,budget)
            if c.n+j not in affected:
                value=z3.BitVecVal(constants[c.n+j],width,ctx)
            elif j==c.stuck:
                value=allone if c.stuck_value else zero
            else:
                modified=z3.And(eg==j,z3.Not(kind))
                aa=z3.Select(state,z3.If(z3.And(modified,slot==0),source,z3.IntVal(a,ctx)))
                bb=z3.Select(state,z3.If(z3.And(modified,slot==1),source,z3.IntVal(b,ctx)))
                tt=z3.If(z3.And(eg==j,kind),table,z3.BitVecVal(t,4,ctx))
                terms=[~aa&~bb,aa&~bb,~aa&bb,aa&bb]
                value=zero
                for k,term in enumerate(terms):
                    value=value|z3.If(z3.Extract(k,k,tt)==z3.BitVecVal(1,1,ctx),term,zero)
            solver.add(z3.Select(state,c.n+j)==value)
        for o,t in zip(c.outputs,targets):solver.add(z3.Select(state,o)==z3.BitVecVal(t,width,ctx))
    add_rows(payload['rows'],payload['sample_target'])
    while True:
        check_time(start,budget)
        solver.set(timeout=max(1,int(1000*(budget-(time.perf_counter()-start)))))
        result=solver.check();check_time(start,budget)
        if result==z3.unsat:return {'status':'unsat','checks':checks,'cegis_blocks':block}
        if result!=z3.sat:return {'status':'solver_unknown','checks':checks,'reason':solver.reason_unknown()}
        assignment=solver.model();j=assignment.eval(eg).as_long()
        if z3.is_true(assignment.eval(kind)):
            edit=('lut',j,2,assignment.eval(table).as_long())
        else:edit=('wire',j,assignment.eval(slot).as_long(),assignment.eval(source).as_long())
        ek,ej,es,ev=edit
        assert 0<=ej<len(c.gates) and ej!=c.stuck
        assert (0<=ev<16 and ev!=c.gates[ej][2]) if ek=='lut' else (es in [0,1] and 0<=ev<c.n+ej and ev!=c.gates[ej][es])
        checks+=1;new=apply(c,edit)
        if payload['setting']=='sample':
            assert sampled_values(new,payload['rows'])==payload['sample_target']
            check_time(start,budget)
            return {'status':'accepted','edit':edit,'checks':checks,'cegis_blocks':block}
        ce=mismatch(new,payload['target_full']);check_time(start,budget)
        emit({'phase':'cegis','iteration':checks,'edit':edit,'counterexample':ce})
        if ce is None:return {'status':'accepted','edit':edit,'checks':checks,'cegis_blocks':block}
        assert ce not in seen;seen.add(ce)
        add_rows([ce],row_targets(payload['target_full'],[ce]))

def worker(pipe):
    import z3,traceback
    model=load_model()
    for n in [6,7,10,12,16]:full_inputs(n)
    pipe.send({'event':'ready','z3_version':z3.get_version_string()})
    while True:
        command=pipe.recv()
        if command is None:return
        payload,method,budget=command
        gc.collect();start=time.perf_counter();pipe.send({'event':'started','clock':start})
        last={}
        def emit(d):
            last.update(d);pipe.send({'event':'progress','elapsed':time.perf_counter()-start,**d})
        try:
            if method=='learned':result=learned(payload,model,start,budget,emit)
            elif method=='exhaustive':result=exhaustive(payload,start,budget,emit)
            else:result=cegis(payload,start,budget,emit,z3)
        except Deadline:result={'status':'timeout','last_progress':last}
        except Exception as exc:result={'status':'error','error':repr(exc),'traceback':traceback.format_exc()}
        elapsed=time.perf_counter()-start
        if elapsed>budget and result['status']!='error':
            result={'status':'timeout','over_budget_result':result}
        pipe.send({'event':'result','elapsed':elapsed,**result})
