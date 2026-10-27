"""Ordinary local features computed without any backward need messages."""
from collections import Counter
from circuit_pilot import ROOT,signals,lut,TinyForest
from local_repair_pilot import NAMES
import numpy as np

KEEP=list(range(4,17))
REMOVE=[0,1,2,3,17,18,19,20]


def no_need_features(c,edits,rows):
    """No target/need arguments, masks, backward propagation or derived errors."""
    val=signals(c,rows);mask=(1<<len(rows))-1;size=len(rows)
    fanout=Counter(x for g in c.gates for x in g[:2]);X=[]
    for kind,j,slot,value in edits:
        a,b,table=c.gates[j];signal=c.n+j;old=val[signal]
        src=value if kind=='wire' else a;old_src=(a,b)[slot] if kind=='wire' else a
        nt=value if kind=='lut' else table
        aa=val[src] if kind=='wire' and slot==0 else val[a]
        bb=val[src] if kind=='wire' and slot==1 else val[b]
        new=lut(aa,bb,nt,mask)
        X.append([float(kind=='lut'),float(kind=='wire'),(table^nt).bit_count()/4,
                  table.bit_count()/4,nt.bit_count()/4,fanout[signal],float(signal in c.outputs),
                  float(src<c.n),float(c.stuck>=0 and src==c.n+c.stuck),
                  (signal-src)/(c.n+len(c.gates)),val[src].bit_count()/size,
                  1-(val[src]^val[old_src]).bit_count()/size,(new^old).bit_count()/size])
    return np.asarray(X,dtype=np.float32)


def load_saved(path):
    import json
    d=json.loads(path.read_text(encoding='utf-8'))
    m=TinyForest(trees=len(d['trees']),depth=9,leaf=12,seed=d.get('training_seed',20261026))
    m.thresholds=[np.asarray(x) for x in d['thresholds']];m.models=d['trees'];m.compile()
    return m
