"""A ranking rerun cannot silently turn changed evidence into reviewed data."""
import json,subprocess,sys
from pathlib import Path


def test_only_unchanged_pairs_reuse_ai_judgments(tmp_path):
    script=Path(__file__).resolve().parents[2]/'scripts/reuse_unchanged_reviews.py'
    before=tmp_path/'before';after=tmp_path/'after'
    before.mkdir();after.mkdir()
    def result(eid):
        return {'employer_id':eid,'employer_name':'Synthetic fixture '+eid,'channels':[],
                'explanation':{'text':'Fixture evidence','basis':'activity','sources':[{'kind':'provided_csv','excerpt':'Original evidence','url':'urn:fixture'}],'claim_ids':['claim-'+eid],'evidence_ids':['evidence-'+eid]}}
    row={'id':'profile','family':'fixture','variant':'complete','profile':{'subject':'fixture'},'ranking':['a','b','c'],'results':[result(eid) for eid in ['a','b','c']],'versions':{'ranking':'old','prospect_model':'model'},'count':3}
    (before/'runs.json').write_text(json.dumps([row]))
    (before/'ai-anchor-reviews.json').write_text(json.dumps([{'profile_id':'profile','family':'fixture','employer_id':eid,'label':'direct','reviewer_type':'ai'} for eid in ['a','b','c']]))
    row['versions']['ranking']='new'
    row['results'][1]['explanation']['sources'][0]['excerpt']='Changed evidence'
    row['results'][2]=result('new');row['ranking'][2]='new'
    (after/'runs.json').write_text(json.dumps([row]))
    command=[sys.executable,str(script),'--before',str(before),'--after',str(after),'--depth','3']
    response=subprocess.run(command,capture_output=True,text=True)
    assert response.returncode==0,response.stderr
    labels=json.loads((after/'ai-anchor-reviews.json').read_text())
    assert [label['employer_id'] for label in labels]==['a']
    assert labels[0]['reviewer_type']=='ai' and labels[0]['ranking_version']=='new'
    unjudged=json.loads((after/'new-review-pairs.json').read_text())
    assert {r['employer_id'] for r in unjudged}=={'b','new'}
    quality=json.loads((after/'ai-development-review.json').read_text())
    assert quality['unjudged_pairs']==2 and quality['precision_at3']['pooled_recall_at_200'] is None
    assert not quality['release_ready'] and quality['independent_human_reviews']==0
    row['profile']['subject']='different profile'
    (after/'runs.json').write_text(json.dumps([row]))
    response=subprocess.run(command,capture_output=True,text=True)
    assert response.returncode!=0 and 'Profile changed' in response.stderr
