"""Professional-interest cohort sensitivity; excludes identity and visa fields."""
import argparse,json
from collections import Counter
from pathlib import Path
from sponsor_match.config import Settings
from sponsor_match.prospects import ProspectLibrary
from sponsor_match.models import Profile


def main():
    p=argparse.ArgumentParser();p.add_argument('--profiles',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    library=ProspectLibrary(Settings.from_env());rows=[]
    for case in json.loads(Path(args.profiles).read_text()):
        result=library.associate(Profile.model_validate(case['profile']))
        rows.append({'profile_id':case['id'],'family':case.get('family'),'variant':case.get('variant'),**result})
    associated=Counter(a['group_id'] for row in rows for a in row['assignments'] if a['status']=='associated')
    summary={'profiles':len(rows),'models':dict(Counter(r.get('model_version','unavailable') for r in rows)),
             'profiles_with_association':sum(any(a['status']=='associated' for a in r['assignments']) for r in rows),
             'unresolved_intents':sum(a['status']=='unresolved' for r in rows for a in r['assignments']),
             'group_exposure':dict(associated),'derived_interest_only':True,'qualification_claims_created':0,'identity_fields_exported':False}
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    (root/'associations.json').write_text(json.dumps(rows,indent=2));(root/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
