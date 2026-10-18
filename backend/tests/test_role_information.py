from sponsor_match.role_information import RoleInformation


def references():
    return [{'id':f'soc:{i}00001','label':f'{domain} function','aliases':[]}
            for i,domain in enumerate(['alpha','beta','gamma','delta'],1)]


def test_counterfactuals_remove_corpus_specific_qualifiers_without_rewriting_intent():
    info=RoleInformation(references())
    raw='Alpha function'
    assert info.generic_labels(raw)==['function']
    assert raw=='Alpha function'
    assert info.generic_label('Unfamiliar function')=='function'
    assert info.generic_labels('Unfamiliar')==[]


def test_repeated_aliases_within_one_family_do_not_change_information():
    refs=references();extra=[{**refs[0],'aliases':['alpha function']*100}]
    assert RoleInformation(refs+extra).information==RoleInformation(refs).information


def test_subword_parts_do_not_make_a_common_compound_artificially_specific():
    refs=references();refs[0]['aliases']=['alpha functionword']
    def parts(words):return [['function','word'] if word=='functionword' else [word] for word in words]
    info=RoleInformation(refs,parts)
    assert info.generic_label('Novel functionword')=='functionword'


def test_equal_information_produces_no_arbitrary_contrast():
    info=RoleInformation([{'id':'soc:111100','label':'one specialty','aliases':[]}])
    assert info.generic_labels('one specialty')==[]
