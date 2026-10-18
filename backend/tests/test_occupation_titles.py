import numpy as np
from sponsor_match.occupation_titles import title_supported,TitleCompetition


def test_only_strong_distant_competitors_veto_title_evidence():
    own=np.array([.50,.50,.50,.70])
    competitor=np.array([.80,.80,.59,.75])
    affinity=np.array([.20,.60,.20,.20])
    assert title_supported(own,competitor,affinity).tolist()==[False,True,True,True]


def test_ambiguous_aliases_preserve_all_parents_and_cache_is_replayable(tmp_path):
    refs=[{'id':'soc:111101','label':'alpha','aliases':['shared']},{'id':'soc:222201','label':'beta','aliases':['shared']}]
    vectors=np.array([[1.,0.],[0.,1.]],dtype=np.float32)
    class Store:
        model='test'
        calls=0
        def encode(self,labels):
            self.calls+=1
            values={'alpha':[1.,0.],'beta':[0.,1.],'shared':[.8,.6]}
            return np.array([values[label] for label in labels],dtype=np.float32)
    store=Store();ids=['role','activity'];terms={'role':{'kind':'role'},'activity':{'kind':'activity'}}
    # A shared title is usable in either family, even when it is the nearest.
    terms_vectors=np.array([[.8,.6],[0.,1.]],dtype=np.float32)
    args=(tmp_path/'model',store,refs,vectors,ids,terms,terms_vectors)
    first=TitleCompetition(*args)
    assert first.mask(0).tolist()==[True,True]
    assert first.mask(1).tolist()==[True,True]
    assert first.features(0,0)['closest_parents']==['1111','2222']
    assert first.features(1,0) is None
    second=TitleCompetition(*args)
    assert store.calls==1 and np.array_equal(first.mask(0),second.mask(0))
