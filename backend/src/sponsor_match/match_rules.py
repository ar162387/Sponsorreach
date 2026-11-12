"""Reviewed rules for company discovery, independent of the embedding model."""
from .taxonomy import contains, key

PROFESSION_VERSION = 'profession-2'
ALIAS_VERSION = 'skill-industry-1'
LOCATION_VERSION = 'company-area-1'
EXPLANATION_VERSION = 'match-evidence-1'

# Exact synonyms only. In particular, no city/county or neighbouring-area inference.
AREA_ALIASES = {'city of edinburgh': 'edinburgh'}
UNKNOWN_AREAS = {'', 'unknown', 'n a', 'none', 'united kingdom', 'uk', 'england',
                 'scotland', 'wales', 'northern ireland', 'great britain', 'gb'}

SKILLS = {
    'react': ('react', 'react js', 'reactjs'),
    'power bi': ('power bi', 'powerbi'),
}

INDUSTRIES = {
    'software development': ('software engineering', 'application development', 'web development', 'custom software'),
    'automotive engineering': ('automotive', 'vehicle manufacturing', 'automotive components'),
    'financial services': ('banking', 'investment management', 'insurance services'),
    'healthcare': ('health care', 'nursing services', 'nursing care', 'medical services', 'hospital services'),
    'accounting and audit': ('accountancy', 'accounting services', 'audit services', 'tax advisory', 'bookkeeping'),
    'infrastructure': ('civil engineering', 'infrastructure design', 'transport infrastructure'),
    'education': ('school education', 'primary education', 'educational services'),
    'hospitality': ('restaurant', 'catering services', 'hotel', 'food preparation'),
    'building services': ('building services engineering', 'electrical installation', 'mechanical and electrical services'),
    'design and publishing': ('graphic design', 'visual design', 'book publishing', 'illustration', 'editorial design'),
    'marketing and advertising': ('digital marketing', 'marketing services', 'advertising agency', 'seo services'),
    'community pharmacy': ('pharmacy services', 'retail pharmacy', 'dispensing medicines'),
    'medical diagnostics': ('clinical diagnostics', 'diagnostic laboratory', 'pathology services', 'medical laboratory'),
    'architecture': ('architectural design', 'architectural practice', 'architectural services'),
}


def area_key(text):
    value = key(text)
    return AREA_ALIASES.get(value, value) if value not in UNKNOWN_AREAS else ''


def location_evidence(employer, location):
    wanted = {area_key(value) for value in location.preferred_regions} - {''}
    observed = []
    for field, values, kind in (
        ('workplace_locations', employer.workplace_locations, 'recorded_workplace'),
        ('town', [employer.town], 'company_address'),
        ('county', [employer.county], 'company_address'),
    ):
        for value in values:
            if area_key(value):
                observed.append({'type': kind, 'value': value, 'field': field,
                                 'matches_area': area_key(value) in wanted,
                                 'employer_id': employer.id, 'employer_version': employer.version})
    matches = [item for item in observed if item['matches_area']]
    if location.effective_mode == 'anywhere':
        return {'status': 'unrestricted', 'sources': observed}
    status = 'match' if matches else 'out_of_area' if observed else 'unknown'
    return {'status': status, 'sources': observed}


def skill_identity(label):
    normalized = key(label)
    for canonical, synonyms in SKILLS.items():
        if normalized in synonyms:
            return canonical, synonyms
    # Preserve meaningful punctuation in short programming-language names.
    if label.strip().casefold() in {'c', 'c++', 'c#', 'f#', '.net'}:
        return label.strip().casefold(), (label.strip(),)
    return normalized, (label,)


def skill_present(span, phrase):
    import re
    if phrase.strip().casefold() in {'c', 'c++', 'c#', 'f#', '.net'}:
        return bool(re.search(r'(?<![\w+#])' + re.escape(phrase.strip()) + r'(?![\w+#])', span, re.I))
    return contains(span, phrase)


def industry_phrases(label):
    normalized = key(label)
    for canonical, aliases in INDUSTRIES.items():
        if normalized == canonical or normalized in aliases:
            return (canonical, *aliases)
    return (label,)
