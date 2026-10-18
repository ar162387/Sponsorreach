"""Drive observed onboarding controls with Playwright CLI; capture submits without email."""
import json,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
forms=json.loads((ROOT/'data/evaluation/2026-10-17/form-final/forms.json').read_text())
extra=os.getenv('BROWSER_VARIANT_SUITE')=='extra'
forms=[f for f in forms if f['variant'] in ({'complete'} if extra else {'complete','without_skills','multiple_roles','related'})]
if extra:
 forms=forms[:5]
 for i,case in enumerate(forms):
  case['id']+=':identity-visa-variant';case['signed_in']=i==4
  case['identity']={'name':'Prospect '+str(i),'email':f'profile-{i}@example.invalid'}
  case['visa_context']={'route':['Student','Skilled Worker','Other','Graduate','Student'][i],'expiry':f'202{7+i%2}-0{1+i}-15'}
cli=str(Path.home()/'.codex/skills/playwright/scripts/playwright_cli.sh')
output=ROOT/('data/evaluation/2026-10-17/browser-extra' if extra else 'data/evaluation/2026-10-17/browser-forms');output.mkdir(parents=True,exist_ok=True)
code='''async (page) => {
 const cases=CASES; const captures=[]; let received;let signedIn=false;
 await page.unrouteAll({behavior:'wait'});
 await page.route('**/api/account/identity',r=>r.fulfill({json:{signed_in:signedIn}}));
 await page.route('**/api/catalogue/status',r=>r.fulfill({json:{email_signin_available:false}}));
 await page.route('**/api/profiles/normalize',async r=>{const resp=await r.fetch({url:'http://127.0.0.1:8002/api/profiles/normalize',headers:{'content-type':'application/json','x-api-secret':'form-audit-local-only-secret-000000000000'}});await r.fulfill({response:resp});});
 await page.route('**/api/matches',async r=>{received=r.request().postDataJSON();await r.fulfill({status:422,json:{detail:'Evaluation capture complete'}});});
 for(const c of cases){
  received=null;signedIn=!!c.signed_in;const p=c.profile;
  await page.goto('http://127.0.0.1:3000/match');
  await page.getByRole('textbox',{name:'Degree, field of study, or professional background',exact:true}).fill(p.background.subject);
  await page.getByRole('textbox',{name:'Specialisation optional',exact:true}).fill(p.background.specialization);
  for(let i=0;i<p.role_intents.length;i++){if(i)await page.getByRole('button',{name:'Add another role',exact:true}).click();await page.getByRole('textbox',{name:'Desired role '+(i+1),exact:true}).fill(p.role_intents[i].raw_label);}
  await page.getByRole('combobox',{name:'Career stage',exact:true}).selectOption(p.career_stage);
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  for(const s of p.skills){await page.getByRole('textbox',{name:'Skills you want to use optional Add skill',exact:true}).fill(s.label);await page.getByRole('button',{name:'Add skill',exact:true}).click();}
  await page.getByRole('textbox',{name:'Experience or projects optional',exact:true}).fill(p.experience_summary);
  await page.getByRole('textbox',{name:'Preferred UK location',exact:true}).fill(p.location.preferred_regions.join(', '));
  await page.getByRole('checkbox',{name:'I’m willing to relocate.',exact:true}).setChecked(p.location.relocate);
  await page.getByRole('checkbox',{name:'Include companies for related roles',exact:false}).setChecked(p.related_roles_enabled);
  await page.getByText('More professional context optional',{exact:true}).click();
  await page.getByRole('textbox',{name:'Preferred industries',exact:true}).fill(p.preferred_industries.join(', '));
  await page.getByRole('textbox',{name:'Professional certifications or registration',exact:true}).fill(p.certifications.join(', '));
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  if(!signedIn){await page.getByRole('textbox',{name:'Your name',exact:true}).fill(c.identity.name);await page.getByRole('textbox',{name:'Email address',exact:true}).fill(c.identity.email);}
  else if(await page.getByRole('textbox',{name:'Email address',exact:true}).count())throw Error('Signed-in identity requested again');
  await page.getByText('Visa timing optional',{exact:true}).click();
  await page.getByRole('combobox',{name:'Current route',exact:true}).selectOption(c.visa_context.route);
  await page.getByRole('textbox',{name:'Your visa expiry date',exact:true}).fill(c.visa_context.expiry);
  const response=page.waitForResponse(r=>r.url().endsWith('/api/matches'));
  await page.getByRole('button',{name:'Find my sponsors',exact:true}).click();await response;
  if(!received)throw Error('No submit '+c.id);
  const actual=JSON.parse(JSON.stringify(received.profile));for(const r of actual.role_intents)delete r.concept_id;
  const expected=JSON.parse(JSON.stringify(p));for(const r of expected.role_intents)delete r.concept_id;
  if(JSON.stringify(actual)!==JSON.stringify(expected)||JSON.stringify(received.identity)!==JSON.stringify(signedIn?undefined:c.identity)||JSON.stringify(received.visa_context)!==JSON.stringify(c.visa_context))throw Error('Payload mismatch '+c.id+' '+JSON.stringify(received));
  captures.push({id:c.id,passed:true,payload:received});
 }
 return captures;
}'''
all_results=[]
for start in range(0,len(forms),4):
 script=code.replace('CASES',json.dumps(forms[start:start+4]))
 result=subprocess.run([cli,'-s=form-audit','run-code',script],capture_output=True,text=True,timeout=120)
 (output/f'batch-{start}.log').write_text(result.stdout+result.stderr)
 if result.returncode or '### Result\n' not in result.stdout:print(result.stdout[-1800:]+result.stderr,flush=True);raise SystemExit(1)
 captured=json.loads(result.stdout.split('### Result\n',1)[1].split('\n###',1)[0])
 all_results.extend(captured)
 (output/'captures.json').write_text(json.dumps(all_results,indent=2))
 print(json.dumps({'browser_forms_passed':len(all_results),'total':len(forms)}),flush=True)
