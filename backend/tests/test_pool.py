from sponsor_match.pool import identity_in_page,supported_activity_claims


def test_source_identity_needs_distinctive_employer_name():
    assert identity_in_page('Acme Design Limited','<title>Acme Design</title><p>Our services</p>')
    assert not identity_in_page('Acme Design Limited','<title>Other Company</title><p>Services and employment</p>')
    assert not identity_in_page('The Company Limited','<p>The company provides services.</p>')


def test_exact_source_spans_exclude_footer_and_negative_claims():
    html='''<title>Acme</title><p>We deliver Software Development for local businesses.</p>
    <p>We do not provide legal services.</p><footer>Website design by a digital marketing agency.</footer>'''
    source,claims=supported_activity_claims(html,['software development','legal services','digital marketing'])
    assert claims==[{'kind':'activity','text':'Software Development','excerpt':'We deliver Software Development for local businesses.'}]
    assert all(c['text'] in c['excerpt'] and c['excerpt'] in source for c in claims)


def test_job_adverts_do_not_establish_core_business_activity():
    _,claims=supported_activity_claims('<p>Apply for our software development vacancy.</p>',['software development'])
    assert not claims
