from sponsor_match.coverage import profile_clarification,CoverageLedger
from sponsor_match.models import Profile
from sponsor_match.taxonomy import Taxonomy


def test_discovery_requires_the_same_confirmation_and_clarification_as_the_form():
    p=Profile.model_validate({'background':{'subject':'Professional interests'},'career_stage':'experienced','role_intents':[{'raw_label':'Unfamiliar specialist niche','confirmed':True}]})
    taxonomy=Taxonomy()
    assert profile_clarification(p,taxonomy) is None
    p.role_intents[0].confirmed=False
    assert profile_clarification(p,taxonomy)
    p.role_intents[0].confirmed=True;p.role_intents[0].raw_label='Analyst'
    assert 'Which area' in profile_clarification(p,taxonomy)
    p.explore=True
    assert profile_clarification(p,taxonomy)


def test_exposure_counts_distinguish_actual_baseline_and_generated_searches(tmp_path):
    ledger=CoverageLedger(tmp_path/'coverage.sqlite3');run=ledger.start({'fixture':True})
    ledger.record(run,{'role':'first'},[],0,{})
    ledger.record(run,{'role':'second'},[],1,{})
    ledger.record(run,{'role':'second'},[],1,{})
    assert ledger.profile_counts(run)=={'total':2,'baseline':1,'generated':1}
