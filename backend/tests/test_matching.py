from datetime import UTC,datetime,timedelta
import pytest
from sponsor_match.models import Employer,Claim,Channel,Membership,Profile,Vacancy
from sponsor_match.taxonomy import Taxonomy
from sponsor_match.ranking import rank,open_jobs,sponsor_valid,rrf
from sponsor_match.intelligence import merge_employers,documents
from sponsor_match.ingest import clean,url_kind
from sponsor_match.evaluate import metrics,profiles
from sponsor_match.evidence import quote_valid,public_addresses


@pytest.fixture
def employer():
    at=datetime.now(UTC)
    return Employer(id="00000000-0000-0000-0000-000000000001",name="Acme",town="Leeds",identity_status="accepted",source_namespace="test",source_key="1",claims=[Claim(id="claim-1",kind="activity",text="Mechanical design and precision engineering using CAD",source_url="https://acme.example/services",excerpt="Mechanical design and precision engineering using CAD",observed_at=at,source_kind="first_party",attribution="accepted")],channels=[Channel(kind="website",value="https://acme.example",observed_at=at,attribution="accepted")],memberships=[Membership(route="Skilled Worker",rating="Worker (A rating)",snapshot_date=at.date().isoformat(),snapshot_id="snapshot",attribution="accepted")])


@pytest.fixture
def profile():
    return Profile.model_validate({"background":{"subject":"Mechanical Engineering"},"role_intents":[{"raw_label":"Mechanical design engineer","confirmed":True}],"career_stage":"graduate","skills":[{"label":"CAD"}]})


def test_professional_activity_match(employer,profile):
    result=rank(employer,profile,Taxonomy(),"snapshot",.8)
    assert result.group=="direct"
    assert result.explanation["skill_hits"]==["CAD"]
    assert result.explanation["claim_ids"]==["claim-1"]


def test_similarity_cannot_transfer_between_intents(employer,profile):
    from sponsor_match.models import RoleIntent
    profile.role_intents.append(RoleIntent(raw_label="Accountant",confirmed=True))
    result=rank(employer,profile,Taxonomy(),"snapshot",{"Mechanical design engineer":.2,"Accountant":1.})
    assert result.features["intent"]=="Mechanical design engineer"
    assert result.features["semantic"]==.2


@pytest.mark.parametrize("label",["HR specialist","Accountant","Marketing executive","Legal associate"])
def test_universal_functions_not_inferred(employer,profile,label):
    profile.role_intents[0].raw_label=label
    assert rank(employer,profile,Taxonomy(),"snapshot",1.) is None


@pytest.mark.parametrize("mutation",["unknown_identity","wrong_snapshot","non_worker","b_rating","unverified_claim","historical_import","stale_claim","stale_channel","search_only","absent_claim"])
def test_gate_rejections(employer,profile,mutation):
    if mutation=="unknown_identity":employer.identity_status="unverified"
    if mutation=="wrong_snapshot":employer.memberships[0].snapshot_id="old"
    if mutation=="non_worker":employer.memberships[0].route="Global Business Mobility"
    if mutation=="b_rating":employer.memberships[0].rating="Worker (B rating)"
    if mutation=="unverified_claim":employer.claims[0].attribution="unverified"
    if mutation=="historical_import":employer.claims[0].source_kind="historical_import"
    if mutation=="stale_claim":employer.claims[0].observed_at-=timedelta(days=181)
    if mutation=="stale_channel":employer.channels[0].observed_at-=timedelta(days=91)
    if mutation=="search_only":employer.channels[0].kind="search_page"
    if mutation=="absent_claim":employer.claims[0].state="verified_absent"
    assert rank(employer,profile,Taxonomy(),"snapshot",1.) is None


@pytest.mark.parametrize("rating",["Worker (A rating)","Worker (A-Premium)","Worker (A-SME+)"])
def test_rating_variants(employer,rating):
    employer.memberships[0].rating=rating
    assert sponsor_valid(employer,"snapshot")


def test_adjacent_requires_opt_in(employer,profile):
    employer.claims[0].text="Technical sales and engineering sales services"
    assert rank(employer,profile,Taxonomy(),"snapshot") is None
    profile.related_roles_enabled=True
    result=rank(employer,profile,Taxonomy(),"snapshot")
    assert result.group=="related" and "alternative" in result.explanation["text"]


def test_no_open_job_inference(employer):
    at=datetime.now(UTC)
    employer.vacancies=[Vacancy(title="Mechanical engineer",url="https://acme.example/jobs/1",provider="llm_adjudicated",verified=True,state="open",observed_at=at,country="GB")]
    assert not open_jobs(employer)
    employer.vacancies[0].provider="first_party"
    assert len(open_jobs(employer))==1
    employer.vacancies[0].closing_at=at-timedelta(days=1)
    assert not open_jobs(employer)


@pytest.mark.parametrize("country",["", "US", "India"])
def test_overseas_and_unknown_jobs_excluded(employer,country):
    employer.vacancies=[Vacancy(title="Mechanical engineer",url="https://acme.example/jobs/1",provider="first_party",verified=True,state="open",observed_at=datetime.now(UTC),country=country)]
    assert not open_jobs(employer)


def test_sparse_no_score_inflation(employer,profile):
    rich=rank(employer,profile,Taxonomy(),"snapshot").score
    employer.claims[0].text="Mechanical design"
    employer.claims[0].excerpt="Mechanical design"
    assert rank(employer,profile,Taxonomy(),"snapshot").score<rich


def test_failures_preserve_fields(employer):
    new=employer.model_copy(deep=True)
    new.channels[0].state="temporarily_unavailable"
    new.channels[0].value=""
    new.identity_status="unverified"
    merged=merge_employers(employer,new)
    assert merged.channels[0].value=="https://acme.example"
    assert merged.identity_status=="accepted"


def test_older_fields_do_not_override(employer):
    new=employer.model_copy(deep=True)
    new.channels[0].value="https://other.example"
    new.channels[0].observed_at-=timedelta(days=5)
    new.claims[0].text="Unsupported replacement"
    new.claims[0].observed_at-=timedelta(days=5)
    merged=merge_employers(employer,new)
    assert merged.channels[0].value=="https://acme.example"
    assert "Mechanical" in merged.claims[0].text


def test_verified_absence_clears_channel(employer):
    new=employer.model_copy(deep=True)
    new.channels[0].state="verified_absent"
    new.channels[0].observed_at+=timedelta(seconds=1)
    assert not merge_employers(employer,new).channels


def test_equivalent_roles_and_ambiguity(profile):
    taxonomy=Taxonomy()
    assert taxonomy.resolve("mechanical designer").id==taxonomy.resolve("Mechanical engineer").id
    profile.role_intents[0].raw_label="analyst"
    assert not taxonomy.normalize(profile)["clarification"]  # Explicit tasks can disambiguate a broad title.
    profile.skills=[]
    assert taxonomy.normalize(profile)["clarification"]
    profile.role_intents[0].raw_label="Quantum materials investigator"
    result=taxonomy.normalize(profile)
    assert not result["clarification"] and result["unknown_roles"]


def test_profile_embedding_excludes_identity(profile):
    text=profile.search_text()
    assert "email" not in text and "visa" not in text


def test_documents_omit_unverified(employer):
    employer.claims[0].attribution="unverified"
    assert documents(employer,Taxonomy())==[]


def test_fusion_no_document_count_bias():
    assert rrf([("activity",["a","a","a","b"]),("function",["b"])])[0]=="b"


def test_no_labels_no_accuracy_claim():
    assert metrics({"p":["e"]},[])["status"]=="not_evaluated"
    assert not metrics({"p":["e"]},[])["release_gate_passed"]
    assert len(profiles())==240


def test_unjudged_top_results_do_not_inflate_precision():
    result=metrics({"p":["unknown","good"]},[{"profile_id":"p","employer_id":"good","label":"direct"}],k=2)
    assert result["precision_at_k"] is None
    assert result["ndcg_at_k"] is None
    assert result["judged_coverage"]==.5


def test_reviewed_cross_source_alias_preserves_identity(employer):
    peer=employer.model_copy(deep=True)
    peer.source_namespace="legacy"
    peer.name="Acme trading alias"
    peer.identity_status="unverified"
    assert merge_employers(employer,peer).name=="Acme"


def test_import_shapes():
    assert clean("null")==clean("N/A")==""
    assert url_kind("javascript:alert(1)") is None
    assert url_kind("https://linkedin.com/in/person")=="linkedin_person"
    assert url_kind("https://indeed.com/jobs?q=accountant")=="search_page"


def test_source_spans_and_private_networks(monkeypatch):
    assert not quote_valid("legal services","We do not provide legal services","We do not provide legal services")
    assert not quote_valid("legal services","legal services","software development")
    monkeypatch.setattr("socket.getaddrinfo",lambda *a,**k:[(2,1,6,"",("127.0.0.1",80))])
    with pytest.raises(ValueError):public_addresses("localhost")


def test_card_contact_display_does_not_relax_ranking_gates(employer,profile):
    from sponsor_match.presentation import displayed_channels
    at=datetime.now(UTC)
    employer.channels=[Channel(kind='email',value='hello@acme.example',observed_at=at-timedelta(days=120)),Channel(kind='linkedin_company',value='https://linkedin.com/company/acme',state='not_observed',observed_at=at),Channel(kind='search_page',value='https://uk.indeed.com/q-acme-jobs.html',observed_at=at)]
    shown=displayed_channels(employer)
    assert len(shown)==3
    assert any('older observation' in c['note'] for c in shown)
    assert any('field-state conflict' in c['note'] for c in shown)
    assert any(c['label']=='Indeed · search results' for c in shown)
    assert rank(employer,profile,Taxonomy(),'snapshot') is None


def test_card_routes_deduplicate_and_keep_board_identities(employer):
    from sponsor_match.presentation import displayed_channels
    at=datetime.now(UTC)
    employer.channels=[Channel(kind='website',value='http://www.acme.example/',observed_at=at-timedelta(days=1)),Channel(kind='website',value='https://acme.example',observed_at=at,attribution='accepted'),Channel(kind='careers',value='https://acme.example/careers'),Channel(kind='careers',value='https://acme.example/careers'),Channel(kind='search_page',value='https://uk.indeed.com/viewjob?jk=123'),Channel(kind='job_board',value='https://www.totaljobs.com/jobs/it/in-london'),Channel(kind='job_board',value='javascript:alert(1)'),Channel(kind='email',value='wrong@other.example',attribution='rejected')]
    shown=displayed_channels(employer)
    assert len(shown)==4
    assert shown[0]['value']=='https://acme.example'
    assert any(c['label']=='Indeed · job link' for c in shown)
    assert any(c['label']=='Totaljobs · search results' for c in shown)
    assert not any(c['value'].startswith('javascript:') or c['value']=='wrong@other.example' for c in shown)


def test_removed_route_is_visible_without_click_target(employer):
    from sponsor_match.presentation import displayed_channels
    at=datetime.now(UTC)
    employer.channels=[Channel(kind='website',value='https://acme.example',observed_at=at-timedelta(days=2),attribution='accepted'),Channel(kind='website',value='https://acme.example',state='verified_absent',observed_at=at,attribution='accepted')]
    shown=displayed_channels(employer)
    assert len(shown)==1 and not shown[0]['linkable']
    assert 'unavailable at last check' in shown[0]['note']


def test_card_summary_stays_grounded_and_short():
    from sponsor_match.presentation import short_match_reason
    activity={'basis':'activity','text':'Published business activity: We create software development teams with expertise. This aligns with your interest in software developer.'}
    assert short_match_reason(activity)=='Its software development work aligns with your target role.'
    historical={'basis':'historical_role','text':'Previously observed role: Software developer. This aligns with your interest in software developer.'}
    assert short_match_reason(historical).startswith('Previously observed role:')
    assert len(short_match_reason({'basis':'function','text':'Published professional function: '+('Professional work '*30)}))<=170


def test_partial_review_reports_the_missing_profiles_in_coverage():
    result=metrics({'reviewed':['good'],'unreviewed':['new-a','new-b'],'empty':[]},
                   [{'profile_id':'reviewed','employer_id':'good','label':'direct'}],k=3)
    assert result['precision_at_k']==1.
    assert result['profiles_fully_judged_at_k']==1
    assert result['overall_judged_item_coverage']==1/3
    assert result['profiles_total']==3 and result['abstentions']==1
