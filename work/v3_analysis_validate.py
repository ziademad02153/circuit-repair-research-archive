"""Check v3 summary contrast arithmetic without using any experiment outcome."""
import json
from v3_report import contrast,OUT
import numpy as np


def main():
    index={};ids=['a','b','c','d']
    for cid in ids:
        index[(cid,1.,'full')]={'success':True,'elapsed':.2,'failure_penalized_seconds':.2,'checks':3}
        index[(cid,1.,'no_need')]={'success':False,'elapsed':.1,'failure_penalized_seconds':1.,'checks':5}
    r=contrast(index,ids,'full','no_need',1.,np.random.default_rng(1))
    assert r['success']['ci97_5']==[1.,1.]
    assert np.allclose(r['actual_time']['ci95'],[-.1,-.1])
    assert np.allclose(r['penalized_time']['ci95'],[.8,.8])
    assert r['matched_success_checks']['pairs']==0
    z=contrast(index,ids,'full','full',1.,np.random.default_rng(1))
    assert all(z[k]['ci97_5']==[0.,0.] for k in ['success','actual_time','penalized_time'])
    assert z['matched_success_checks']['pairs']==4
    report={'status':'passed','experiment_outcomes_used':False,
        'checks':['constant success effect','actual time sign','failure penalty sign',
                  'matched successes exclude failed pair','identity contrast zero']}
    (OUT/'analysis_preflight.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
