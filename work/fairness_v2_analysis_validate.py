"""Analytical sanity checks independent of actual benchmark outcomes."""
import json
import numpy as np
from fairness_v2_report import contrast,OUT


def main():
    index={};ids=['a','b','c','d']
    for cid in ids:
        for repeat in range(2):
            index[(cid,repeat,'learned')]={'success':True,'elapsed':.2,'failure_penalized_seconds':.2}
            index[(cid,repeat,'rule')]={'success':True,'elapsed':.6,'failure_penalized_seconds':.6}
    result=contrast(index,ids,'rule',1000,np.random.default_rng(1))
    assert result['unique_circuits']==4
    assert result['success']['ci97_5']==[0.,0.]
    assert np.allclose(result['penalized_time']['ci97_5'],[.4,.4])
    zero=contrast(index,ids,'learned',1000,np.random.default_rng(1))
    assert all(zero[k]['ci97_5']==[0.,0.] for k in ['success','actual_time','penalized_time'])
    for cid in ids:index[(cid,0,'learned')]['success']=False
    half=contrast(index,ids,'rule',1000,np.random.default_rng(1))
    assert half['success']['ci97_5']==[-.5,-.5]
    record={'status':'passed','checks':['identical methods give zero intervals',
        'constant timing advantage has exact interval','success uses within-circuit repeat mean',
        'unique circuit denominator excludes duplicate timing repeats'],
        'benchmark_outcomes_used':False}
    (OUT/'analysis_preflight.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record))


if __name__=='__main__':main()
