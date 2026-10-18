import io
import json
import zipfile
from datetime import UTC,datetime,timedelta
from types import SimpleNamespace
import pytest
import httpx
from sponsor_match.providers import OpenAI,ProviderUnavailable
from sponsor_match.config import Settings
from sponsor_match.taxonomy import Taxonomy
from sponsor_match.vacancies import json_jobs
from sponsor_match.evidence import fetch_public
from sponsor_match.taxonomies import safe_zip,decoded
from sponsor_match.models import Employer,Channel
from sponsor_match.vacancies import verify_vacancy


def test_supabase_connection_alias_and_local_defaults(monkeypatch):
    monkeypatch.setattr('sponsor_match.config.load_app_environment',lambda:None)
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('EMBEDDING_PROVIDER',raising=False)
    monkeypatch.setenv('SUPABASE_CONNECTION_STRING','postgresql://user:[YOUR-PASSWORD]@db.example/postgres')
    monkeypatch.setenv('SUPABASE_DATABASE_PASSWORD','pass@word:with/slash')
    settings=Settings.from_env()
    assert 'pass%40word%3Awith%2Fslash' in settings.database_url
    assert settings.embedding_provider=='local' and settings.dimensions==384


def test_embeddings_validate_shape_and_provider_absence(monkeypatch):
    provider=OpenAI(Settings())
    with pytest.raises(ProviderUnavailable):provider.embeddings(["Engineering services"])
    monkeypatch.setattr(provider,"_post",lambda *a:{"data":[{"index":0,"embedding":[1.]}]})
    with pytest.raises(ProviderUnavailable):provider.embeddings(["Engineering services"])


def test_extraction_rejects_invented_spans(monkeypatch):
    provider=OpenAI(Settings())
    body={"claims":[{"kind":"activity","text":"accounting services","excerpt":"We provide accounting services."},{"kind":"function","text":"HR department","excerpt":"We have an HR department."}]}
    monkeypatch.setattr(provider,"_post",lambda *a:{"output":[{"content":[{"type":"output_text","text":json.dumps(body)}]}]})
    claims=provider.extract("We provide accounting services.","https://acme.example","Acme")
    assert len(claims)==1 and claims[0]["kind"]=="activity"


def test_untrusted_private_source_cannot_be_fetched(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo",lambda *a,**k:[(2,1,6,"",("10.0.0.1",80))])
    with pytest.raises(ValueError):fetch_public("https://internal.example")
    with pytest.raises(ValueError):fetch_public("file:///etc/passwd")
    with pytest.raises(ValueError):fetch_public("https://username:password@example.com")


def test_structured_adverts_are_separate_from_model_tags():
    html='<script type="application/ld+json">'+json.dumps({"@graph":[{"@type":"Organization","name":"Acme"},{"@type":"JobPosting","title":"Engineer","hiringOrganization":{"name":"Acme"},"validThrough":"2026-11-01"}]})+'</script>'
    assert len(json_jobs(html))==1
    assert not json_jobs('<p>We once advertised an Engineer.</p>')


@pytest.mark.parametrize("country,expected",[("GB","open"),("US","unverified"),("","unverified")])
def test_vacancy_verification_requires_uk_location(monkeypatch,country,expected):
    employer=Employer(id="test",name="Acme",identity_status="accepted",source_namespace="test",source_key="1",channels=[Channel(kind="website",value="https://acme.example",attribution="accepted")])
    job={"@type":"JobPosting","title":"Mechanical engineer","hiringOrganization":{"name":"Acme"},"validThrough":(datetime.now(UTC)+timedelta(days=10)).isoformat(),"jobLocation":{"address":{"addressLocality":"Town","addressCountry":country}}}
    html='<script type="application/ld+json">'+json.dumps(job)+'</script>'
    monkeypatch.setattr("sponsor_match.vacancies.fetch_public",lambda url:(html,url,"text/html"))
    db=SimpleNamespace(employer=lambda id:employer,taxonomy=lambda:Taxonomy(),save_employer=lambda *a:None)
    result=verify_vacancy(db,"test","https://acme.example/jobs/1",True)
    assert result["state"]==expected
    assert result["verified_open"]==(expected=="open")


@pytest.mark.parametrize("kind,state",[("email","inconclusive"),("careers","verified_absent")])
def test_removed_source_is_not_absence_of_contact(monkeypatch,kind,state):
    from sponsor_match.evidence import refresh_channel
    from sponsor_match.intelligence import merge_employers
    value="hello@acme.example" if kind=="email" else "https://acme.example/careers"
    employer=Employer(id="test",name="Acme",source_namespace="test",source_key="1",channels=[Channel(kind=kind,value=value,source_url="https://acme.example/contact",attribution="accepted",observed_at=datetime.now(UTC)-timedelta(days=2))])
    observations=[]
    def save(incoming):
        observations.extend(incoming.channels)
        merged=merge_employers(employer.model_copy(deep=True),incoming)
        employer.channels=merged.channels
    def gone(url):
        response=httpx.Response(404,request=httpx.Request("GET",url))
        response.raise_for_status()
    monkeypatch.setattr("sponsor_match.evidence.fetch_public",gone)
    db=SimpleNamespace(employer=lambda id:employer.model_copy(deep=True),save_employer=save)
    refresh_channel(db,"test",kind,value)
    assert observations[0].state==state
    assert bool(employer.channels)==(kind=="email")
    if kind=="email":assert employer.channels[0].state=="found"


def test_ons_encoding_and_role_pluralization():
    assert decoded(b"Classified\xa0role")=="Classified\u00a0role"
    taxonomy=Taxonomy()
    assert "bootstrap:mechanical" in taxonomy.inferred_concepts("Our mechanical engineers design components.")
    assert taxonomy.resolve("Senior software engineer").id=="bootstrap:software"


def test_professional_source_does_not_require_whole_corpus_scans():
    from sponsor_match.taxonomy import Concept
    concepts=[Concept(f"test:{n}",f"Specialist discipline {n}",[],[],[],[],[]) for n in range(1000)]
    taxonomy=Taxonomy(concepts)
    assert taxonomy.inferred_concepts("Specialist discipline 912")==["test:912"]
