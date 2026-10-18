"""Full-form sensitivity benchmark. Local real catalogue; never sends email."""
import argparse,json,time
from pathlib import Path
from dataclasses import asdict,replace
from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.models import Profile,Skill
from sponsor_match.search import Matcher
from sponsor_match.presentation import displayed_channels
CASES=[
 ('software','Computer science','Software developer','Backend web applications',['Python','SQL'],'Built Python APIs and SQL databases for a university project.','Technology','AWS Certified Cloud Practitioner','Software engineer'),
 ('accounting','Accounting','Accountant','Audit and financial reporting',['ACCA','Financial reporting'],'Prepared accounts, reconciliations and financial reports during an internship.','Professional services','ACCA','Trainee accountant'),
 ('mechanical','Mechanical engineering','Mechanical engineer','CAD and manufacturing',['CAD','SolidWorks'],'Designed mechanical components and tested manufacturing prototypes.','Manufacturing','CSWA','Mechanical design engineer'),
 ('nursing','Nursing','Registered nurse','Adult clinical nursing',['Patient care','Clinical care'],'Supported adult patients, clinical observations and care planning.','Healthcare','NMC','Staff nurse'),
 ('legal','Law','Legal associate','Commercial contracts',['Legal research','Contract law'],'Researched case law and drafted commercial contract summaries.','Legal services','SQE1','Paralegal'),
 ('marketing','Marketing','Marketing specialist','Digital campaigns',['SEO','Content marketing'],'Managed SEO content and measured digital campaign performance.','Advertising','Google Analytics','Marketing executive'),
 ('hr','Human resources','HR specialist','Employee relations',['CIPD','Employee relations'],'Supported recruitment onboarding and employee relations casework.','Professional services','CIPD Level 5','HR advisor'),
 ('materials','Materials science','Materials scientist','Polymers and materials testing',['Polymers','Laboratory'],'Tested polymer materials and analysed experimental laboratory results.','Manufacturing','Laboratory safety','Materials scientist'),
 ('cybersecurity','Computer science','Cybersecurity analyst','Network security',['Cybersecurity','Network security'],'Analysed network security events and investigated incident reports.','Technology','CompTIA Security+','Cybersecurity analyst'),
 ('quantum','Physics','Quantum lattice researcher','Quantum condensed matter',['Quantum simulation','Lattice models'],'Simulated quantum lattice models for a condensed matter research project.','Scientific research','Research training','Quantum lattice researcher'),
 ('waiter','Hospitality','Waiter','Restaurant service',['Customer service','Food service'],'Served restaurant guests, took orders and coordinated with kitchen staff.','Hospitality','Food safety Level 2','Waiter'),
 ('restaurant_manager','Hospitality management','Restaurant manager','Restaurant operations',['Team supervision','Stock control'],'Managed staff rotas, guest service and restaurant stock.','Hospitality','Food safety Level 3','Restaurant manager'),
 ('plumber','Plumbing apprenticeship','Plumber','Domestic installation',['Plumbing','Pipework'],'Installed and repaired domestic pipework and water systems.','Construction','NVQ Plumbing Level 2','Plumber'),
 ('electrician','Electrical installation','Electrician','Building electrical installation',['Electrical installation','Inspection'],'Installed circuits and tested electrical systems in buildings.','Construction','City and Guilds 18th Edition','Electrician'),
 ('warehouse','Logistics','Warehouse operative','Distribution operations',['Stock control','Picking'],'Picked orders, checked incoming stock and prepared dispatches.','Logistics','Forklift training','Warehouse operative'),
 ('hairdresser','Hairdressing','Hairdresser','Salon hair services',['Hair cutting','Colouring'],'Cut, styled and coloured hair during salon work.','Personal services','NVQ Hairdressing Level 2','Hairdresser'),

]
def matrix():
 out=[]
 for family,bg,role,spec,skills,exp,industry,cert,synonym in CASES:
  base=Profile.model_validate(dict(background={'subject':bg},role_intents=[{'raw_label':role,'confirmed':True}],career_stage='graduate'))
  full=base.model_copy(deep=True);full.background.specialization=spec;full.skills=[Skill(label=s) for s in skills];full.experience_summary=exp;full.preferred_industries=[industry];full.certifications=[cert];full.location.preferred_regions=['London'];full.location.relocate=True
  variants={'minimal':base,'complete':full}
  for field in ['specialization','skills','experience_summary','preferred_industries','certifications','location']:
   p=full.model_copy(deep=True)
   if field=='specialization':p.background.specialization=''
   elif field=='location':p.location.preferred_regions=[]
   else:setattr(p,field,'' if field=='experience_summary' else [])
   variants['without_'+field]=p
  for stage in ['student','experienced','career_changer']:
   p=full.model_copy(deep=True);p.career_stage=stage;variants[stage]=p
  p=full.model_copy(deep=True);p.location.relocate=False;variants['no_relocation']=p
  p=full.model_copy(deep=True);p.location.preferred_regions=['Manchester'];variants['manchester']=p
  p=full.model_copy(deep=True);p.related_roles_enabled=True;variants['related']=p
  p=full.model_copy(deep=True);p.role_intents[0].raw_label=synonym;variants['synonym']=p
  p=full.model_copy(deep=True);p.skills.append(Skill(label='Communication'));variants['extra_transferable_skill']=p
  p=full.model_copy(deep=True);p.role_intents.append(type(p.role_intents[0])(raw_label='Accountant' if family!='accounting' else 'Software developer',confirmed=True));variants['multiple_roles']=p
  for variant,p in variants.items():out.append(dict(id=family+':'+variant,family=family,variant=variant,profile=p.model_dump(),identity={'name':'Evaluation Prospect','email':'evaluation@example.invalid'},visa_context={'route':'Graduate','expiry':'2027-10-01'}))
 return out

def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 settings=replace(Settings.from_env(),database_url='postgresql://localhost:55432/sponsormatch',environment='production')
 db=Database(settings.database_url);db.open();matcher=Matcher(db,settings);rows=[]
 try:
  cases=matrix();(output/'forms.json').write_text(json.dumps(cases,indent=2))
  for case in cases:
   p=Profile.model_validate(case['profile']);start=time.perf_counter();results,mode,versions=matcher.search(p)
   employers={e.id:e for e in db.employers([r.employer_id for r in results[:10]])}
   rows.append({**case,'elapsed_ms':round((time.perf_counter()-start)*1000,2),'mode':mode,'versions':versions,'direct_count':sum(r.group=='direct' for r in results),'related_count':sum(r.group=='related' for r in results),'ranking':[r.employer_id for r in results if r.group=='direct'],'results':[{**asdict(r),'employer_name':employers[r.employer_id].name,'channels':displayed_channels(employers[r.employer_id]),'claims':[c.model_dump(mode='json') for c in employers[r.employer_id].claims if c.attribution=='accepted']} for r in results[:10]]})
   if len(rows)%17==0:print(json.dumps({'completed':len(rows),'family':case['family']}),flush=True)
  (output/'runs.json').write_text(json.dumps(rows,indent=2,default=str))
  comparisons=[]
  for row in rows:
   full=next(r for r in rows if r['family']==row['family'] and r['variant']=='complete');a=full['ranking'][:10];b=row['ranking'][:10]
   comparisons.append({'id':row['id'],'direct':row['direct_count'],'related':row['related_count'],'same_top3':a[:3]==b[:3],'overlap_at10':len(set(a)&set(b))/max(1,len(set(a)|set(b))),'top3':[r['employer_name'] for r in row['results'][:3]]})
  (output/'comparisons.json').write_text(json.dumps(comparisons,indent=2))
 finally:db.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
