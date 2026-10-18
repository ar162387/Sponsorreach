"""Compare frozen synthetic form runs without reusing labels as new judgments."""
import argparse
import json
from collections import Counter
from pathlib import Path


def compare(before,after):
    old={r['id']:r for r in before}
    new={r['id']:r for r in after}
    if len(old)!=len(before) or len(new)!=len(after):
        raise ValueError('Duplicate profile IDs in comparison')
    if old.keys()!=new.keys():raise ValueError('Compare the same frozen profile set')
    fields={};deltas=[]
    anchors={r['family']:r for r in after if r['variant']=='complete'}
    for pid,row in new.items():
        previous=old[pid]
        if row['profile']!=previous['profile']:raise ValueError('Profile inputs changed: '+pid)
        a,b=previous['ranking'],row['ranking']
        deltas.append({'profile_id':pid,'family':row['family'],'variant':row['variant'],
                       'previous_count':len(a),'current_count':len(b),
                       'same_top3':a[:3]==b[:3],'same_top10':a[:10]==b[:10],
                       'admitted_employers':sorted(set(b)-set(a)),
                       'removed_employers':sorted(set(a)-set(b))})
        anchor=anchors.get(row['family'])
        if anchor is None:continue
        field=fields.setdefault(row['variant'],{'profiles':0,'top3_changed':0,'top10_changed':0,'count_changed':0})
        field['profiles']+=1
        field['top3_changed']+=int(b[:3]!=anchor['ranking'][:3])
        field['top10_changed']+=int(b[:10]!=anchor['ranking'][:10])
        field['count_changed']+=int(len(b)!=len(anchor['ranking']))
    # Frequency counts use every saved position, not just the displayed ten.
    exposure=Counter(e for row in after for e in row['ranking'])
    return {'before_version':before[0]['versions']['ranking'],
            'after_version':after[0]['versions']['ranking'],'profiles':len(after),
            'top3_changed':sum(not d['same_top3'] for d in deltas),
            'top10_changed':sum(not d['same_top10'] for d in deltas),
            'counts_changed':sum(d['previous_count']!=d['current_count'] for d in deltas),
            'unique_employers':len(exposure),'employer_exposures':dict(exposure),
            'field_sensitivity':fields,'profile_deltas':deltas,
            'relevance_accuracy_measured':False,
            'limitations':['Ranking changes do not establish improved relevance.',
                          'Unchanged optional-field results may reflect missing employer evidence.',
                          'The experimental matcher does not yet retrieve substantive related careers.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--before',required=True);p.add_argument('--after',required=True)
    args=p.parse_args();folder=Path(args.after)
    result=compare(json.loads((Path(args.before)/'runs.json').read_text()),json.loads((folder/'runs.json').read_text()))
    (folder/'version-comparison.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in {'employer_exposures','profile_deltas'}},indent=2))


if __name__=='__main__':main()
