"""Direct factored Boolean CNF incremental CEGIS, fixed Glucose 4.2.1 backend."""
from __future__ import annotations
import time,threading
from contextlib import contextmanager
from circuit_pilot import signals,ancestors,apply
from decisive_engine import check_time,full_values,mismatch
from pysat.solvers import Solver
from pysat.card import CardEnc,EncType

BACKEND='g42'


class Encoding:
    def __init__(self,c,eligible,start,budget):
        self.c=c;self.eligible=sorted(eligible);self.start=start;self.budget=budget
        self.nv=0;self.clauses=[];self.total_constructed=0;self.total_added=0
        self.true=self.var();self.clauses.append([self.true])
        self.gate={j:self.var() for j in self.eligible}
        self.kind=self.var();self.slot=self.var();self.table=[self.var() for _ in range(4)]
        self.source=[self.var() for _ in range(c.n+max(eligible))]
        self.exactly_one(list(self.gate.values()));self.exactly_one(self.source)
        self.modes={}
        for j,e in self.gate.items():
            check_time(start,budget)
            el,ea,eb=self.var(),self.var(),self.var();self.modes[j]=(el,ea,eb)
            self.add([-el,e]);self.add([-el,self.kind]);self.add([-e,-self.kind,el])
            for lit in [e,-self.kind,-self.slot]:self.add([-ea,lit])
            self.add([-e,self.kind,self.slot,ea])
            for lit in [e,-self.kind,self.slot]:self.add([-eb,lit])
            self.add([-e,self.kind,-self.slot,eb])
            a,b,t=c.gates[j]
            self.add([-e,-self.kind]+[(-v if (t>>k)&1 else v) for k,v in enumerate(self.table)])
            self.add([-e,self.kind,self.slot,-self.source[a]])
            self.add([-e,self.kind,-self.slot,-self.source[b]])
            for s in range(c.n+j,len(self.source)):self.add([-e,self.kind,-self.source[s]])
        self.affected=set()
        for j,(a,b,_) in enumerate(c.gates):
            if j!=c.stuck and (j in self.gate or a in self.affected or b in self.affected):self.affected.add(c.n+j)

    def var(self):self.nv+=1;return self.nv

    def add(self,lits):
        self.total_constructed+=1
        if self.total_constructed%256==0:check_time(self.start,self.budget)
        # Simplify fixed TRUE and duplicate/opposite literals before adding.
        if self.true in lits:return
        clause=[];seen=set()
        for lit in lits:
            if lit==-self.true:continue
            if -lit in seen:return
            if lit not in seen:clause.append(lit);seen.add(lit)
        self.clauses.append(clause)

    def exactly_one(self,lits):
        cnf=CardEnc.equals(lits=lits,bound=1,top_id=self.nv,encoding=EncType.seqcounter)
        self.nv=max(self.nv,cnf.nv)
        for clause in cnf.clauses:self.add(clause)

    def logic(self,a,b,y,table,guard=None):
        prefix=[] if guard is None else [-guard]
        for k in range(4):
            self.add(prefix+[(-a if k&1 else a),(-b if k&2 else b),
                             y if (table>>k)&1 else -y])

    def programmable(self,a,b,y,guard):
        for k,t in enumerate(self.table):
            prefix=[-guard,(-a if k&1 else a),(-b if k&2 else b)]
            self.add(prefix+[-y,t]);self.add(prefix+[y,-t])

    def rows(self,rows,target):
        c=self.c;base=signals(c,rows)
        for r_index,row in enumerate(rows):
            check_time(self.start,self.budget)
            state=[self.true if (row>>i)&1 else -self.true for i in range(c.n)]
            for j in range(len(c.gates)):
                signal=c.n+j
                state.append(self.var() if signal in self.affected else
                             (self.true if (base[signal]>>r_index)&1 else -self.true))
            mux=self.var()
            for s,choice in enumerate(self.source):
                v=state[s];self.add([-choice,-mux,v]);self.add([-choice,mux,-v])
            for j,(a,b,t) in enumerate(c.gates):
                if c.n+j not in self.affected:continue
                y=state[c.n+j];aa,bb=state[a],state[b]
                if j in self.gate:
                    el,ea,eb=self.modes[j]
                    self.logic(aa,bb,y,t,guard=-self.gate[j])
                    self.programmable(aa,bb,y,el)
                    self.logic(mux,bb,y,t,guard=ea)
                    self.logic(aa,mux,y,t,guard=eb)
                else:self.logic(aa,bb,y,t)
            for output,bits in zip(c.outputs,target):
                self.add([state[output] if (bits>>row)&1 else -state[output]])

    def append(self,solver):
        check_time(self.start,self.budget)
        solver.append_formula(self.clauses);self.total_added+=len(self.clauses);self.clauses=[]
        check_time(self.start,self.budget)

    def edit(self,assignment):
        positive={x for x in assignment if x>0}
        j=next(j for j,e in self.gate.items() if e in positive)
        if self.kind in positive:
            return ('lut',j,2,sum((1<<k) for k,v in enumerate(self.table) if v in positive))
        source=next(i for i,v in enumerate(self.source) if v in positive)
        return ('wire',j,int(self.slot in positive),source)


def cnf_cegis(payload,start,budget,emit,metrics):
    c=payload['c'];metrics.update({'encoding_seconds':0.,'sat_solve_seconds':0.,
        'verification_seconds':0.,'checks':0,'sat_calls':0,'cegis_rows':0,
        'backend':BACKEND,'clauses_added':0,'variables':0})
    @contextmanager
    def stage(name):
        emit({'phase':name});t=time.perf_counter()
        try:yield
        finally:metrics[name]=metrics.get(name,0.)+time.perf_counter()-t
    solver=None;encoding=None
    try:
        with stage('encoding_seconds'):
            observed=full_values(c);wanted=payload['target_full']
            bad=[o for o,a,b in zip(c.outputs,observed,wanted) if a!=b]
            eligible=set(range(len(c.gates)))-{c.stuck}
            for output in bad:eligible&={s-c.n for s in ancestors(c,output) if s>=c.n}
            check_time(start,budget)
            if not eligible:return {'status':'unsat','reason':'disjoint output cones','structural_unsat':True}
            solver=Solver(name=BACKEND,incr=True)
            encoding=Encoding(c,eligible,start,budget)
            encoding.rows(payload['rows'],wanted);encoding.append(solver)
            metrics['cegis_rows']=len(payload['rows'])
        seen=set(payload['rows'])
        while True:
            check_time(start,budget)
            with stage('sat_solve_seconds'):
                metrics['sat_calls']+=1
                timer=threading.Timer(max(.000001,budget-(time.perf_counter()-start)),solver.interrupt)
                timer.daemon=True;timer.start()
                try:result=solver.solve_limited(expect_interrupt=True)
                finally:timer.cancel();timer.join()
                solver.clear_interrupt()
            check_time(start,budget)
            if result is False:return {'status':'unsat','structural_unsat':False}
            if result is None:return {'status':'solver_unknown','reason':'native solver interrupted'}
            edit=encoding.edit(solver.get_model())
            kind,j,slot,value=edit
            assert j!=c.stuck
            assert (0<=value<16 and value!=c.gates[j][2]) if kind=='lut' else (value<c.n+j and value!=c.gates[j][slot])
            with stage('verification_seconds'):
                metrics['checks']+=1;ce=mismatch(apply(c,edit),wanted)
            check_time(start,budget)
            emit({'phase':'counterexample','edit':edit,'counterexample':ce})
            if ce is None:return {'status':'accepted','edit':edit}
            assert ce not in seen;seen.add(ce)
            with stage('encoding_seconds'):
                encoding.rows([ce],wanted);encoding.append(solver);metrics['cegis_rows']+=1
    finally:
        if encoding is not None:
            metrics['variables']=encoding.nv;metrics['clauses_added']=encoding.total_added
            metrics['clauses_constructed_attempts']=encoding.total_constructed
        if solver is not None:solver.delete()
