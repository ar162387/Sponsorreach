import pytest
from sponsor_match.ingest import register_identity_attributable


@pytest.mark.parametrize('county,official,identities,expected',[
    ('County A',[''],1,True),
    ('County A',['County A',''],1,True),
    ('',['County A'],1,True),
    ('null',['County A'],1,True),
    ('County A',['County B'],1,False),
    ('County A',['County A','County B'],1,False),
    ('County A',['County A'],2,False),
])
def test_register_linkage_distinguishes_unknown_county_from_conflicting_identity(county,official,identities,expected):
    assert register_identity_attributable('accepted',county,official,identities)==expected


def test_register_linkage_does_not_promote_an_unverified_employer():
    assert not register_identity_attributable('unverified','',[''],1)
