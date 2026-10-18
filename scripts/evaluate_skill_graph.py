"""Reproducible development diagnostics; not independent relevance judgments."""
import json,time,sys
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from profile_matrix import matrix
from sponsor_match.config import Settings,LOCAL_MODEL
from sponsor_match.db import Database
from sponsor_match.models import Profile
from sponsor_match.search import Matcher
from sponsor_match.presentation import displayed_channels
import argparse
parser=argparse.ArgumentParser(description='Local synthetic full-form skill-graph diagnostic; sends no emails')
parser.add_argument('--output',required=True)
parser.add_argument('--baseline',action='store_true',help='Run the existing matcher with the graph disabled')
parser.add_argument('--profiles',help='Exact frozen cases to replay, instead of the default development matrix')
args=parser.parse_args();output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
s=Settings(database_url='postgresql://localhost:55432/sponsormatch',embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384,environment='production',role_graph_enabled=not args.baseline);db=Database(s.database_url);db.open();m=Matcher(db,s)
cases=[x for x in matrix() if x['variant'] in ['minimal','complete','multiple_roles']]
friend={'background':{'subject':'Environmental engineering'},'role_intents':[{'raw_label':'Environmental engineer','confirmed':True},{'raw_label':'MTO','confirmed':True}],'career_stage':'graduate','skills':[{'label':l} for l in ['waste management','carbon accounting','solid waste managment','air pollution control techonologies','water and waste water treatment technologies','environmental sustainability']]}
cases += [{'id':'friend:both','profile':friend},{'id':'friend:mto-only','profile':{**friend,'role_intents':[{'raw_label':'MTO','confirmed':True}]}},{'id':'friend:engineer-only','profile':{**friend,'role_intents':[{'raw_label':'Engineer','confirmed':True}]}}]
extra=[('network','IT','IT engineer',['Networking','TCP/IP','Network administration']),('mobile','Computer science','Software engineer',['Mobile app development','Android','Kotlin']),('front-end','Computer science','Software engineer',['Front end development','JavaScript','React']),('backend','Computer science','Software engineer',['Backend web development','Python','PostgreSQL']),('chef','Culinary arts','Chef',['Food preparation','Cooking','Food hygiene']),('dentist','Dentistry','Dentist',['Dental treatment','Patient care']),('automotive','Automotive engineering','Automotive engineer',['Vehicle design','Automotive systems']),('hr-law-negative','Human resources','HR specialist',['Employee relations','Recruitment','CIPD'])]
for id,bg,role,skills in extra:cases.append({'id':id,'profile':dict(background={'subject':bg},role_intents=[{'raw_label':role,'confirmed':True}],career_stage='graduate',skills=[{'label':x} for x in skills])})
rows=[]
if args.profiles:cases=json.loads(Path(args.profiles).read_text())
for case in cases:
 start=time.perf_counter();p=Profile.model_validate(case['profile']);trace={}
 try:results,mode,versions=m.search(p,trace=trace)
 except Exception as exc:
  rows.append({'id':case['id'],'family':case.get('family',case['id'].split(':')[0]),'split':case.get('split','development'),'profile':p.model_dump(),'status':'failed','error_type':type(exc).__name__,'count':0,'elapsed_ms':round(1000*(time.perf_counter()-start),1),'results':[]})
  output.write_text(json.dumps(rows,indent=2));print(case['id'],'FAILED',type(exc).__name__,flush=True);continue
 em={e.id:e for e in db.employers([r.employer_id for r in results[:10]])}
 rows.append({'id':case['id'],'family':case.get('family',case['id'].split(':')[0]),'variant':case.get('variant','custom'),'split':case.get('split','development'),'profile':p.model_dump(),'count':len(results),'elapsed_ms':round(1000*(time.perf_counter()-start),1),'mode':mode,'versions':versions,**trace,'results':[{'name':em[r.employer_id].name,**asdict(r),'channels':displayed_channels(em[r.employer_id]),'claims':[c.model_dump(mode='json') for c in em[r.employer_id].claims]} for r in results[:10]]})
 output.write_text(json.dumps(rows,indent=2));print(case['id'],len(results),round(time.perf_counter()-start,2),flush=True)
db.close()
