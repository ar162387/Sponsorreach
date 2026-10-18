"""Occupation-stratified interest tests, complementary to the full-form matrix.

No employer names, relevance labels, accounts or qualifications are generated.
Official descriptions supply hypothetical interests, never asserted experience.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path
from sponsor_match.discovery_profiles import DiscoveryProfiles
from sponsor_match.intelligence import digest

VERSION='official-interest-matrix-1'


def matrix(references,per_family=2):
    if per_family<1:raise ValueError('per_family must be positive')
    families=defaultdict(list)
    for reference in references:
        code=reference['id'].rsplit(':',1)[-1]
        if code and code[0].isdigit() and len(reference['label'])<=120:
            families[code[0]].append(reference)
    rows=[];selected=[]
    for family,items in sorted(families.items()):
        # Stable hash sampling avoids choosing familiar or successful occupations.
        for reference in sorted(items,key=lambda r:digest([VERSION,r['id']]))[:per_family]:
            selected.append(reference['id'])
            from sponsor_match.prospects import profile_for
            base=profile_for(reference)
            text=reference.get('description','').strip()
            prefix='Interested in work involving: '
            if len(text)>500-len(prefix):
                text=text[:500-len(prefix)].rsplit(' ',1)[0].rstrip(' ,;:')+'…'
                text=text[:500-len(prefix)]
            complete=base.model_copy(deep=True)
            complete.experience_summary=prefix+text if text else ''
            variants={'complete':complete,'minimal':base}
            for stage in ['student','graduate','career_changer']:
                variants[stage]=complete.model_copy(update={'career_stage':stage})
            local=complete.model_copy(deep=True);local.location.relocate=False
            variants['no_relocation']=local
            related=complete.model_copy(update={'related_roles_enabled':True})
            variants['related']=related
            alias=next((a for a in reference.get('aliases',[]) if a!=reference['label'] and 2<=len(a)<=120),None)
            if alias:
                alternative=complete.model_copy(deep=True)
                alternative.role_intents[0].raw_label=alias
                variants['official_alias']=alternative
            for variant,profile in variants.items():
                rows.append({'id':reference['id']+':'+variant,'family':reference['id'],
                             'major_family':family,'variant':variant,'profile':profile.model_dump(mode='json'),
                             'provenance':{'reference_id':reference['id'],'source_version':reference.get('source_version'),
                                           'source_url':reference.get('source_url'),'reference_hash':digest(reference)},
                             'candidate_qualification_claims':False})
    return rows,{'version':VERSION,'major_families':len(families),'selected_references':selected,
                 'profiles':len(rows),'references_hash':digest(sorted(references,key=lambda r:r['id'])),'profiles_hash':digest(rows),
                 'human_judgments':0,'quality_accuracy_measured':False,
                 'scope':'Source-derived hypothetical interests and field sensitivity. Skills and credentials remain empty; use the separate complete-form matrix to test those fields.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-folder',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--per-family',type=int,default=2)
    args=parser.parse_args();folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    references=DiscoveryProfiles(args.model_folder).references
    rows,metadata=matrix(references,args.per_family)
    if not rows:raise ValueError('No official occupations available')
    (folder/'forms.json').write_text(json.dumps(rows,indent=2))
    (folder/'sampling.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
