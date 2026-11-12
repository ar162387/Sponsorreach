'use client';
import {useWorkspaceRouter} from './workspace-navigation';
import {useEffect,useRef,useState} from 'react';

import Link from '@/components/navigation-link';
import {ArrowLeft,ArrowRight,Check,Plus,X,Compass,RotateCcw} from 'lucide-react';
import PersonalizedLoader from './personalized-loader';
import CreditAllowance from './credit-allowance';
import {refreshCredits} from './dashboard-shell';
import {searchRequest} from '@/lib/search-request';
import {api,matchingContext,type Profile,type VisaContext,type LocationMode,type ProfessionChoice} from '@/lib/types';

const initial:Profile={profile_version:1,background:{subject:'',specialization:''},role_intents:[{raw_label:'',confirmed:false}],explore:false,career_stage:'graduate',skills:[],experience_summary:'',preferred_industries:[],certifications:[],location:{preferred_regions:[],relocate:false,strict:false},related_roles_enabled:false};
function validProfile(value:unknown):value is Profile {
  if(!value||typeof value!=='object')return false;
  const p=value as Profile;
  return p.profile_version===1&&typeof p.background?.subject==='string'&&Array.isArray(p.role_intents)&&p.role_intents.every(r=>typeof r.raw_label==='string')&&Array.isArray(p.skills)&&p.skills.every(s=>typeof s.label==='string')&&Array.isArray(p.location?.preferred_regions)&&['student','graduate','experienced','career_changer'].includes(p.career_stage);
}
function cleanProfile(value:Profile):Profile {
  const p={...structuredClone(initial),...structuredClone(value)},subject=p.background.subject,specialization=p.background.specialization;
  return {...p,background:{subject:(specialization&&!subject.toLowerCase().includes(specialization.toLowerCase())?subject+' · '+specialization:subject).slice(0,180),specialization:''},role_intents:p.role_intents.length?p.role_intents.slice(0,3):[{raw_label:'',confirmed:false}],explore:false,experience_summary:'',certifications:[]};
}
const locationModes:Record<LocationMode,string>={
  anywhere:'Anywhere in the UK',
  prefer_area:'Prefer my selected city or county',
  selected_area:'Only my selected city or county',
};
const entries=(value:string,max:number)=>value.split(',').map(v=>v.trim()).filter(Boolean).slice(0,max);
export default function Intake({sourceSession,newSearch=false,embedded=false,initialProfile,initialVisa,onCancel,onComplete}:{sourceSession?:string;newSearch?:boolean;embedded?:boolean;initialProfile?:Profile;initialVisa?:VisaContext|null;onCancel?:()=>void;onComplete?:(id:string,profile:Profile)=>void}) {
  const [profile,setProfile]=useState<Profile>(()=>cleanProfile(initialProfile||initial));
  const [step,setStep]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[creditBalance,setCreditBalance]=useState<number|null>(null);
  const [roleText,setRoleText]=useState('');
  const [skill,setSkill]=useState(''),[location,setLocation]=useState(initialProfile?.location.preferred_regions.join(', ')||''),[industries,setIndustries]=useState(initialProfile?.preferred_industries.join(', ')||'');
  const [visaRoute,setVisaRoute]=useState(initialVisa?.route||''),[visaExpiry,setVisaExpiry]=useState(initialVisa?.expiry||''),[restoredNotice,setRestoredNotice]=useState(''),[draftReady,setDraftReady]=useState(false);
  const [professionChoices,setProfessionChoices]=useState<ProfessionChoice[]>([]);
  const [signedIn,setSignedIn]=useState(embedded),[accountLoading,setAccountLoading]=useState(!embedded),[accountError,setAccountError]=useState(false);
  const edited=useRef(false),draftKey=useRef(''),submissionKey=useRef<string|null>(null),roleInput=useRef<HTMLInputElement>(null),focusRole=useRef(false);
  const router=useWorkspaceRouter();
  function touch(){edited.current=true;submissionKey.current=null;}
  function update(patch:Partial<Profile>){
    touch();
    if (patch.background || patch.skills || patch.role_intents) setProfessionChoices([]);
    setProfile(p=>{
      const next={...p,...patch};
      if ((patch.background && patch.background.subject!==p.background.subject) ||
          (patch.skills && JSON.stringify(patch.skills)!==JSON.stringify(p.skills))) {
        next.role_intents=next.role_intents.map(role=>({...role,concept_id:null}));
      }
      return next;
    });
    setError('');
  }
  function restore(p:Profile){setProfessionChoices([]);const next=cleanProfile(p);setProfile(next);setLocation(next.location.preferred_regions.join(', '));setIndustries(next.preferred_industries.join(', '));}
  function startFresh(){touch();restore(initial);setStep(0);setRoleText('');setSkill('');setVisaRoute('');setVisaExpiry('');setError('');setRestoredNotice('Profile reset. Start with a new direction.');try{sessionStorage.removeItem(draftKey.current);}catch{}}
  async function checkAccount(){
    setAccountLoading(true);setAccountError(false);
    try{
      const account=embedded?{signed_in:true}:await api<{signed_in:boolean}>('account/identity');setSignedIn(account.signed_in);
      if(!account.signed_in){setDraftReady(true);return;}
      if(newSearch&&!sourceSession){setDraftReady(true);return;}
      const saved=await api<{account_key:string;profile:Profile|null}>('account/profile'+(sourceSession?'?session_id='+sourceSession:''));
      draftKey.current='sponsorreach:onboarding:v2:'+saved.account_key+':'+(sourceSession||'new');
      let draft:Profile|null=null;
      try{const stored=JSON.parse(sessionStorage.getItem(draftKey.current)||'null');if(!newSearch&&stored?.expires_at>Date.now()&&validProfile(stored.profile)){draft=stored.profile;if(!edited.current){setStep(Math.max(0,Math.min(2,Number(stored.step)||0)));if(typeof stored.visaRoute==='string')setVisaRoute(stored.visaRoute);if(typeof stored.visaExpiry==='string')setVisaExpiry(stored.visaExpiry);}}}catch{}
      const previous=sourceSession?saved.profile:draft;
      if(!edited.current&&previous&&validProfile(previous)){restore(previous);setRestoredNotice(sourceSession?'Editing this shortlist’s profile.':'Your unfinished profile has been restored.');}
      setDraftReady(true);
    }catch{setAccountError(true);}finally{setAccountLoading(false);}
  }
  useEffect(()=>{if(!embedded||!newSearch)void checkAccount();},[]);
  useEffect(()=>{if(step===0&&error&&focusRole.current){roleInput.current?.focus();focusRole.current=false;}},[step,error]);
  useEffect(()=>{
    if(!draftReady||!draftKey.current)return;
    const current={...profile,location:{...profile.location,preferred_regions:entries(location,5)},preferred_industries:entries(industries,5)};
    try{sessionStorage.setItem(draftKey.current,JSON.stringify({expires_at:Date.now()+86400000,profile:current,step,visaRoute,visaExpiry}));}catch{}
  },[profile,location,industries,step,visaRoute,visaExpiry,draftReady]);
  function addSkill(value:string){const label=value.trim();if(label&&!profile.skills.some(s=>s.label.toLowerCase()===label.toLowerCase())&&profile.skills.length<20)update({skills:[...profile.skills,{label,source:'user'}]});setSkill('');}
  const effectiveMode=profile.location.mode || (!entries(location,5).length || profile.location.relocate ? 'anywhere' : profile.location.strict ? 'selected_area' : 'prefer_area');
  function checkedProfile(){return {...profile,background:{subject:profile.background.subject.trim(),specialization:''},role_intents:profile.role_intents.map(r=>({...r,raw_label:r.raw_label.trim()})),location:{...profile.location,preferred_regions:entries(location,5)},preferred_industries:entries(industries,5)};}
  function addRole(value=roleText){
    const label=value.trim();
    const roles=profile.role_intents.filter(role=>role.raw_label);
    if(label.length<2||roles.length>=3)return;
    if(!roles.some(role=>role.raw_label.toLowerCase()===label.toLowerCase())){
      update({role_intents:[...roles,{raw_label:label,confirmed:false}]});
    }
    setRoleText('');
  }
  async function next(event:React.FormEvent){
    event.preventDefault();setError('');
    const current=checkedProfile();
    if(embedded&&step===0){
      const roles=current.role_intents.filter(role=>role.raw_label);
      const label=roleText.trim();
      if(label&&roles.length<3&&!roles.some(role=>role.raw_label.toLowerCase()===label.toLowerCase())){
        roles.push({raw_label:label,confirmed:false});
      }
      if(roles.length)current.role_intents=roles;
    }
    if(current.background.subject.length<2||current.role_intents.some(r=>r.raw_label.length<2)){setStep(0);setError('Enter your background and at least one desired role using two or more characters.');return;}
    const broad=current.role_intents.find(r=>['analyst','engineer','consultant','manager','business','graduate'].includes(r.raw_label.toLowerCase()));
    if(broad){focusRole.current=true;setStep(0);setError(`Which type of ${broad.raw_label.toLowerCase()} role interests you? Enter a specific role, such as software engineering manager or mechanical design engineer.`);return;}
    if(step===0){update(current);setRoleText('');setStep(1);return;}
    if(step===1){
      if(effectiveMode!=='anywhere'&&!current.location.preferred_regions.length){
        setError('Enter a city or county, or choose Anywhere in the UK.');return;
      }
      if(skill.trim()&&!current.skills.some(s=>s.label.toLowerCase()===skill.trim().toLowerCase())&&current.skills.length<20)current.skills=[...current.skills,{label:skill.trim(),source:'user'}];
      setSkill('');update(current);setStep(2);return;
    }
    if(creditBalance===0){setError('Your credits are used up. Your profile is saved. Open billing to get more credits.');return;}
    if(!signedIn){setError('Sign in before starting your search.');return;}
    if(accountLoading||accountError){setError('Retry your account check before starting the search.');return;}
    setBusy(true);
    try{
      submissionKey.current||=crypto.randomUUID();
      const result=await api<{session_id:string;verification_required:boolean}>(sourceSession?`matches/${sourceSession}/refresh`:'matches',{method:'POST',body:JSON.stringify(searchRequest({profile:current,sourceSession,visaContext:visaRoute||visaExpiry?{route:visaRoute,expiry:visaExpiry||null}:null,creditConsent:true,idempotencyKey:submissionKey.current}))});
      refreshCredits();
      try{sessionStorage.removeItem(draftKey.current);}catch{}
      if(onComplete)onComplete(result.session_id,current);else router.push('/results/'+result.session_id);
    }catch(e){
      const problem=e as Error&{status?:number;code?:string;field?:string;choices?:ProfessionChoice[]};
      if(problem.status===402){setCreditBalance(0);refreshCredits();}
      if(problem.choices?.length){setProfessionChoices(problem.choices);setStep(2);}
      else if(problem.code==='profile_needs_clarification'||problem.field?.startsWith('profile.')){focusRole.current=true;setStep(0);}
      setError(problem.message);setBusy(false);
    }
  }
  if(busy&&embedded)return <PersonalizedLoader context={matchingContext(profile)} error="" embedded/>;
  return <section className={embedded?'intake-shell embedded-intake':'intake-shell shell'}>
    {embedded?<header className="editor-heading"><div><h1>{sourceSession?'Refine shortlist':'New search'}</h1></div><button type="button" className="button secondary small" disabled={busy} onClick={onCancel}><X size={16}/>Close</button></header>:<aside className="intake-aside"><Link href="/" className="back-link"><ArrowLeft size={16}/>Back to home</Link><p className="eyebrow">YOUR SKILLS. YOUR SPONSOR SHORTLIST.</p><h1>Find sponsors for<br/>the work <em>you want.</em></h1><p>Tell us your background and the work you want to do.</p><ol className="step-list">{['Your background','Your preferences','Review and search'].map((label,i)=><li key={label} className={i===step?'active':i<step?'complete':''}><span>{i<step?<Check size={16}/>:String(i+1).padStart(2,'0')}</span><div>{label}</div></li>)}</ol><div className="aside-note"><Compass size={22}/><span>Research companies relevant to your skills.</span></div></aside>}
    <div className="form-panel">{(!embedded||!newSearch)&&<CreditAllowance onBalance={setCreditBalance}/>}<div className="form-top"><span>STEP {step+1} OF 3</span>{!embedded&&<span>About 2 minutes</span>}</div><div className="progress-track"><span style={{width:`${(step+1)/3*100}%`}}/></div>
      <form onSubmit={next}>
        {restoredNotice&&<p className="notice" role="status">{restoredNotice} <button type="button" className="text-button" onClick={startFresh}>Start fresh</button></p>}
        {step===0&&<><h2>What work are you looking for?</h2>{!embedded&&<p className="muted">Your background and target roles help us identify relevant companies.</p>}
          <label>Degree, field of study, or professional background<input required minLength={2} maxLength={180} value={profile.background.subject} onChange={e=>update({background:{subject:e.target.value,specialization:''}})} placeholder="e.g. Mechanical Engineering, Accounting, Nursing"/></label>
          {embedded?<><label htmlFor="search-role">Target roles</label>
            <div className="input-action"><input id="search-role" aria-label="Desired role 1" ref={roleInput} maxLength={120} value={roleText} disabled={profile.role_intents.filter(role=>role.raw_label).length>=3} onInput={event=>setRoleText(event.currentTarget.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.nativeEvent.isComposing){event.preventDefault();addRole(event.currentTarget.value);}}} placeholder="e.g. Mechanical design engineer"/><button type="button" className="icon-button" aria-label="Add role" disabled={roleText.trim().length<2} onClick={()=>{addRole();roleInput.current?.focus();}}><Plus size={18}/></button></div>
            <div className="chip-list">{profile.role_intents.filter(role=>role.raw_label).map(role=><button type="button" className="chip selected" key={role.raw_label} aria-label={'Remove '+role.raw_label} onClick={()=>update({role_intents:profile.role_intents.filter(item=>item.raw_label!==role.raw_label)})}>{role.raw_label}<X size={12}/></button>)}</div></>:<><div className="label-row"><span>What roles interest you?</span></div>{profile.role_intents.map((role,i)=><div className="role-input" key={i}><input ref={i===0?roleInput:undefined} aria-label={`Desired role ${i+1}`} required minLength={2} maxLength={120} value={role.raw_label} onChange={e=>update({role_intents:profile.role_intents.map((r,n)=>n===i?{raw_label:e.target.value,confirmed:false}:r)})} placeholder="e.g. Mechanical design engineer"/>{i>0&&<button type="button" className="icon-button" aria-label="Remove role" onClick={()=>update({role_intents:profile.role_intents.filter((_,n)=>n!==i)})}><X size={16}/></button>}</div>)}
          {profile.role_intents.length<3&&<button type="button" className="text-button" onClick={()=>update({role_intents:[...profile.role_intents,{raw_label:'',confirmed:false}]})}><Plus size={14}/>Add another role</button>}</>}
          <label>Career stage<select value={profile.career_stage} onChange={e=>update({career_stage:e.target.value as Profile['career_stage']})}><option value="student">Currently studying</option><option value="graduate">Graduate / starting my career</option><option value="experienced">Experienced professional</option><option value="career_changer">Changing career direction</option></select></label>
        </>}
        {step===1&&<><h2>Which companies could fit you?</h2>{!embedded&&<p className="muted">Add the skills and preferences you want us to consider.</p>}
          <label>Skills you want to use <span className="optional">optional</span><div className="input-action"><input maxLength={100} value={skill} onChange={e=>setSkill(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addSkill(skill);}}} placeholder="Add a technical or professional skill"/><button type="button" className="icon-button" aria-label="Add skill" onClick={()=>addSkill(skill)}><Plus size={18}/></button></div></label>
          <div className="chip-list">{profile.skills.map(s=><button type="button" className="chip selected" key={s.label} onClick={()=>update({skills:profile.skills.filter(v=>v.label!==s.label)})}>{s.label}<X size={12}/></button>)}</div>
          <label>Location preference<select value={effectiveMode} onChange={e=>update({location:{...profile.location,mode:e.target.value as LocationMode}})}>{Object.entries(locationModes).map(([mode,label])=><option value={mode} key={mode}>{label}</option>)}</select></label>
          <label>Preferred UK location<input maxLength={100} value={location} onChange={e=>{touch();setLocation(e.target.value);}} placeholder="e.g. Coventry or West Midlands"/></label>
          <p className="tiny muted">Area searches use recorded cities and counties. A company address may differ from the workplace.</p>
          <label className="checkbox-line"><input type="checkbox" checked={profile.related_roles_enabled} onChange={e=>update({related_roles_enabled:e.target.checked})}/>Include related roles</label>
          <label>Preferred industries or areas of work<input maxLength={250} value={industries} onChange={e=>{touch();setIndustries(e.target.value);}} placeholder="e.g. Renewable energy, healthcare"/></label>
          <details className="intake-visa"><summary>Visa timing (optional)</summary><label>Current route<select value={visaRoute} onChange={e=>{touch();setVisaRoute(e.target.value);}}><option value="">Prefer not to say</option><option>Graduate</option><option>Student</option><option>Skilled Worker</option><option>Other</option></select></label><label>Your visa expiry date<input type="date" value={visaExpiry} onChange={e=>{touch();setVisaExpiry(e.target.value);}}/></label><p className="tiny muted">Visa timing does not change your company recommendations. You can leave these fields blank.</p></details>
        </>}
        {step===2&&<><h2>Review your search</h2><p className="muted">A search may use 1 credit. Empty searches and mostly repeated results are free.</p><div className="profile-summary"><h3>{profile.role_intents.map(r=>r.raw_label).join(' · ')}</h3><p>{profile.background.subject}</p><div className="chip-list">{profile.skills.map(s=><span className="chip" key={s.label}>{s.label}</span>)}</div><small>{locationModes[effectiveMode]}{effectiveMode!=='anywhere'&&' · '+profile.location.preferred_regions.join(', ')}</small>{profile.preferred_industries.length>0&&<p>{profile.preferred_industries.join(', ')}</p>}</div>
          {professionChoices.map(({index,options})=><label key={index}>Which kind of {profile.role_intents[index]?.raw_label} work?
            <select value={profile.role_intents[index]?.concept_id||''} onChange={e=>{
              touch();setError('');
              const concept_id=e.target.value||null;
              setProfile(p=>({...p,role_intents:p.role_intents.map((role,i)=>i===index?{...role,concept_id,confirmed:!!concept_id}:role)}));
            }}><option value="">Choose a profession</option>{options.map(option=><option key={option.concept_id} value={option.concept_id}>{option.label}</option>)}</select>
          </label>)}
          {accountLoading?<p role="status">Checking your account…</p>:accountError?<p className="error" role="alert">We couldn’t check your account. <button type="button" className="text-button" onClick={()=>void checkAccount()}>Retry</button></p>:!signedIn?<p className="error"><Link href="/account">Sign in to start your search</Link></p>:null}
        </>}
        {error&&<p className="error" role="alert">{error}</p>}
        <div className="form-actions"><button type="button" className="back-button reset-profile" disabled={busy||accountLoading} onClick={startFresh}><RotateCcw size={15}/>Reset profile</button>{step>0&&<button type="button" className="back-button" disabled={busy} onClick={()=>{setStep(step-1);setError('');}}><ArrowLeft size={16}/>Back</button>}<button className="button" type="submit" disabled={busy||(step===2&&(accountLoading||accountError||creditBalance===0||!signedIn||professionChoices.some(choice=>!profile.role_intents[choice.index]?.concept_id)))}>{busy?'Working…':step===2?sourceSession?'Update this shortlist':'Find my sponsors':'Continue'}<ArrowRight size={18}/></button></div>
      </form>
    </div>
  </section>;
}
