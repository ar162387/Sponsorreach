from sponsor_match.bulk import assess_draft
from sponsor_match.taxonomy import Taxonomy


def draft(source, phrase='bookkeeping', name='Acme Accountants Ltd'):
    return {'status':'prepared','name':name,'source_text':source,'requested_url':'https://acme.example','resolved_url':'https://www.acme.example/', 'claims':[{'kind':'activity','text':phrase,'excerpt':source.split('\n')[-1]}]}


def test_bulk_requires_full_identity_and_source_span():
    taxonomy=Taxonomy()
    item=draft('Acme Accountants\nWe provide bookkeeping services.')
    assert assess_draft(item,taxonomy)[1]=='source_corroborated'
    item['source_text']='Other Accountants\nWe provide bookkeeping services.'
    assert not assess_draft(item,taxonomy)[0]
    item=draft('Acme Accountants\nWe do not provide bookkeeping services.')
    assert not assess_draft(item,taxonomy)[0]


def test_recruiters_clients_do_not_establish_internal_professions():
    item=draft('Acme Accountants\nWe are a recruitment agency for bookkeeping professionals.')
    assert not assess_draft(item,Taxonomy())[0]


def test_teaching_exchange_and_generic_identity_require_review():
    item=draft('Acme College\nOur teaching exchange programmes.', 'teaching', 'Acme College Ltd')
    assert not assess_draft(item,Taxonomy())[0]
    item=draft('Care Services\nOur nursing care.', 'nursing care', 'Care Services Ltd')
    assert not assess_draft(item,Taxonomy())[0]


def test_failed_and_redirected_sources_never_publish():
    item=draft('Acme Accountants\nWe provide bookkeeping services.')
    item['resolved_url']='https://other.example'
    assert not assess_draft(item,Taxonomy())[0]
    item['status']='source_unavailable'
    assert not assess_draft(item,Taxonomy())[0]


def test_products_and_job_titles_do_not_become_core_professional_services():
    assert not assess_draft(draft('Acme Accountants\nOur bookkeeping software powers your business.', 'bookkeeping'),Taxonomy())[0]
    assert not assess_draft(draft('Acme Products\nCatering Products','Catering','Acme Products Ltd'),Taxonomy())[0]
    assert not assess_draft(draft('Acme Digital\nDigital Marketing Manager (2026)','Digital Marketing','Acme Digital Ltd'),Taxonomy())[0]
