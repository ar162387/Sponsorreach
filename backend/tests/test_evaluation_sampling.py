from sponsor_match.evaluation_sampling import sample_profiles


def test_sampler_uses_ontology_not_employer_success_and_keeps_families_together():
    skills=[{'id':'s1','label':'First practical task','type':'skill'},
            {'id':'s2','label':'Second practical task','type':'skill'}]
    occupations=[{'id':str(i),'label':'Occupation '+str(i),'skills':[{'id':'s1'},{'id':'s2'}],
                  'isco':['http://data.europa.eu/esco/isco/C'+code],'broader':[]} for i,code in enumerate(['2111','2112','3121','3122'])]
    a=sample_profiles(occupations,skills,4)
    assert a==sample_profiles(occupations,skills,4)
    assert len(a)==12 and len({c['id'] for c in a})==12
    for family in {c['family'] for c in a}:
        assert len({c['split'] for c in a if c['family']==family})==1
    assert all(c['synthetic'] for c in a)
    assert all(not c['profile']['skills'] for c in a if c['variant']=='role_only')
