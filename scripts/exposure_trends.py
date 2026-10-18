"""Compare audited synthetic exposure counts without treating them as demand.

Reads completed public/synthetic artifacts only. No DB or account access.
"""
import argparse,html,json
from pathlib import Path
from sponsor_match.intelligence import digest

VERSION='confirmed-exposure-trends-1'


def rates(row,profiles):
    counts={name:int(row[field]) for name,field in [('appearances','new_appearances'),('preview_appearances','preview_appearances'),('top10_appearances','top10_appearances')]}
    if profiles<0 or any(value<0 or value>profiles for value in counts.values()):raise ValueError('Exposure exceeds confirmed profile count')
    if not counts['preview_appearances']<=counts['top10_appearances']<=counts['appearances']:raise ValueError('Exposure depths are inconsistent')
    return {**counts,**{name+'_per_1000_profiles':1000*value/profiles if profiles else None for name,value in counts.items()},
            'best_rank':row.get('best_new_rank'),'example_profile_id':(row.get('example_profile') or {}).get('profile_id'),'state':row['state']}


def load_run(folder):
    folder=Path(folder);confirmed=folder/'confirmed-profiles'
    summary=json.loads((confirmed/'summary.json').read_text());audit=json.loads((confirmed/'profile-readiness-audit.json').read_text())
    metadata=json.loads((folder/'run-metadata.json').read_text());rows=json.loads((confirmed/'employer-coverage.json').read_text())
    if metadata.get('status')!='completed':raise ValueError('Use completed coverage runs')
    expected={'source_run':summary['run_id'],'ranking_version':summary['ranking_version'],'source_model':summary['model_version'],'source_hash':metadata['source_hash']}
    if any(audit.get(key)!=value for key,value in expected.items()):raise ValueError('Readiness audit describes another run')
    if summary['profiles_evaluated']!=audit['valid_profiles'] or len(rows)!=summary['employers']:raise ValueError('Confirmed counts are inconsistent')
    if len({r['employer_id'] for r in rows})!=len(rows):raise ValueError('Duplicate employer outcomes')
    stats={r['employer_id']:rates(r,audit['valid_profiles']) for r in rows}
    if sum(r['appearances']>0 for r in stats.values())!=audit['valid_reached']:raise ValueError('Reached counts are inconsistent')
    if sum(r['preview_appearances']>0 for r in stats.values())!=audit['valid_preview_reached'] or sum(r['top10_appearances']>0 for r in stats.values())!=audit['valid_top10_reached']:raise ValueError('Rank-depth counts are inconsistent')
    descriptor={'run_id':summary['run_id'],'ranking_version':summary['ranking_version'],'proposal_version':metadata['proposal_version'],
                'model_version':summary['model_version'],'source_hash':metadata['source_hash'],'snapshot':metadata['snapshot'],
                'normalization_policy_hash':audit['policy_hash'],'confirmed_profiles':audit['valid_profiles'],'employers':len(rows),
                'reached':audit['valid_reached'],'preview_reached':audit['valid_preview_reached'],'top10_reached':audit['valid_top10_reached'],
                'outcomes_hash':digest(rows),'readiness_hash':digest(audit),'metadata_hash':digest(metadata),'folder':folder.name}
    return descriptor,rows,stats


def compare(folders):
    runs=[];employers={}
    for folder in folders:
        run,rows,stats=load_run(folder)
        if any(r['run_id']==run['run_id'] for r in runs):raise ValueError('Repeated run ID')
        runs.append(run)
        for row in rows:
            entry=employers.setdefault(row['employer_id'],{'employer_id':row['employer_id'],'name':row['name'],'runs':{}})
            entry['name']=row['name'];entry['runs'][run['run_id']]={**stats[row['employer_id']],'employer_version':row['employer_version']}
    if len(runs)<2:raise ValueError('Compare at least two runs')
    first,last=runs[0],runs[-1];changes=[]
    for field in ['ranking_version','proposal_version','model_version','source_hash','snapshot','normalization_policy_hash']:
        if first[field]!=last[field]:changes.append(field)
    for entry in employers.values():
        a=entry['runs'].get(first['run_id']);b=entry['runs'].get(last['run_id'])
        if a is None:change='added_to_catalogue'
        elif b is None:change='removed_from_catalogue'
        elif not a['appearances'] and b['appearances']:change='newly_reached'
        elif a['appearances'] and not b['appearances']:change='no_longer_reached'
        elif b['appearances']:change='reached_in_both'
        else:change='unreached_in_both'
        entry['change']=change
        entry['appearance_rate_delta_per_1000']=b['appearances_per_1000_profiles']-a['appearances_per_1000_profiles'] if a and b and a['appearances_per_1000_profiles'] is not None and b['appearances_per_1000_profiles'] is not None else None
    rows=sorted(employers.values(),key=lambda r:(r['name'].casefold(),r['employer_id']))
    from collections import Counter
    summary={'version':VERSION,'runs':runs,'changed_version_dimensions':changes,'employers':len(rows),
             'changes':dict(Counter(r['change'] for r in rows)),'profiles_same_size':first['confirmed_profiles']==last['confirmed_profiles'],
             'employer_rows_hash':digest(rows),'relevance_accuracy_measured':False,'independent_human_reviews':0,
             'note':'Appearances are within synthetic test profiles, not candidate demand or employment probability. Different profile pools and evidence/ranking versions are not a controlled performance comparison. Rate changes alone are not relevance regressions.'}
    return summary,rows


def render(folder,summary,rows):
    esc=lambda value:html.escape(str(value));runs=summary['runs'];first,last=runs[0],runs[-1]
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>SponsorReach employer exposure trends</title><style>body{font:16px/1.5 system-ui;color:#123e50;background:#f7f9f8;margin:32px auto;padding:0 20px;max-width:1300px;overflow-wrap:anywhere}.scroll{overflow:auto}table{border-collapse:collapse;background:white;width:100%}th,td{padding:12px;border-bottom:1px solid #dbe6e8;text-align:left}input{padding:12px;width:min(95%,500px)}a{color:#087e76}</style><h1>Employer exposure by test version</h1>'''
    page+='<p>'+esc(summary['employers'])+' employer records · '+esc(len(runs))+' completed runs. Every employer is included, including zero-result records.</p><p>'+esc(summary['note'])+'</p><ul>'
    for run in runs:page+='<li>'+esc(run['run_id'][:8])+' · '+esc(run['ranking_version'])+' / '+esc(run['proposal_version'])+' · '+esc(run['confirmed_profiles'])+' confirmed profiles · '+esc(run['reached'])+' employers reached.</li>'
    page+='</ul><p><a href="summary.json">Versions and totals</a> · <a href="employer-trends.json">Every employer / every run</a></p><input id="q" aria-label="Filter employers" placeholder="Search employer or reach status"><div class="scroll"><table><thead><tr><th>Employer</th><th>Change</th><th>Earlier appearances / per 1,000 profiles</th><th>Latest appearances / per 1,000 profiles</th><th>Latest top three / top ten</th><th>Latest best rank</th></tr></thead><tbody>'
    def rate(value):return '—' if value is None else f'{value:.2f}'
    for row in rows:
        a=row['runs'].get(first['run_id']);b=row['runs'].get(last['run_id'])
        cells=[row['name'],row['change'].replace('_',' '),str(a['appearances'])+' / '+rate(a['appearances_per_1000_profiles']) if a else 'Not in catalogue',str(b['appearances'])+' / '+rate(b['appearances_per_1000_profiles']) if b else 'Not in catalogue',str(b['preview_appearances'])+' / '+str(b['top10_appearances']) if b else '—',b['best_rank'] if b and b['best_rank'] else '—']
        page+='<tr>'+''.join('<td>'+esc(value)+'</td>' for value in cells)+'</tr>'
    page+='</tbody></table></div><script>document.querySelector("#q").addEventListener("input",e=>{for(const row of document.querySelectorAll("tbody tr"))row.hidden=!row.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script></html>'
    (Path(folder)/'report.html').write_text(page)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--coverage',action='append',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();summary,rows=compare(args.coverage);folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    (folder/'summary.json').write_text(json.dumps(summary,indent=2));(folder/'employer-trends.json').write_text(json.dumps(rows,indent=2));render(folder,summary,rows)
    print(json.dumps({key:value for key,value in summary.items() if key!='runs'},indent=2))


if __name__=='__main__':main()
