'use client';
import {useEffect,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from '@/components/navigation-link';
import {ArrowLeft,ArrowRight,Check,Plus,X,Compass,RotateCcw} from 'lucide-react';
import CreditAllowance from './credit-allowance';
import {refreshCredits} from './dashboard-shell';
import {searchRequest} from '@/lib/search-request';
import {api,type Profile,type VisaContext} from '@/lib/types';

const initial:Profile={profile_version:1,background:{subject:'',specialization:''},role_intents:[{raw_label:'',confirmed:false}],explore:false,career_stage:'graduate',skills:[],experience_summary:'',preferred_industries:[],certifications:[],location:{preferred_regions:[],relocate:false,strict:false},related_roles_enabled:false};
function validProfile(value:unknown):value is Profile {
  if(!value||typeof value!=='object')return false;
  const p=value as Profile;
  return p.profile_version===1&&typeof p.background?.subject==='string'&&Array.isArray(p.role_intents)&&p.role_intents.every(r=>typeof r.raw_label==='string')&&Array.isArray(p.skills)&&p.skills.every(s=>typeof s.label==='string')&&Array.isArray(p.location?.preferred_regions)&&['student','graduate','experienced','career_changer'].includes(p.career_stage);
}
function cleanProfile(value:Profile):Profile {
  const p={...structuredClone(initial),...structuredClone(value)},subject=p.background.subject,specialization=p.background.specialization;
  return {...p,background:{subject:(specialization&&!subject.toLowerCase().includes(specialization.toLowerCase())?subject+' · '+specialization:subject).slice(0,180),specialization:''},role_intents:p.role_intents.length?p.role_intents.slice(0,3):[{raw_label:'',confirmed:false}],explore:false,experience_summary:'',certifications:[],related_roles_enabled:false};
}
const entries=(value:string,max:number)=>value.split(',').map(v=>v.trim()).filter(Boolean).slice(0,max);
export default function Intake({sourceSession,newSearch=false,embedded=false,initialProfile,initialVisa,onCancel,onComplete}:{sourceSession?:string;newSearch?:boolean;embedded?:boolean;initialProfile?:Profile;initialVisa?:VisaContext|null;onCancel?:()=>void;onComplete?:(id:string,profile:Profile)=>void}) {
  const [profile,setProfile]=useState<Profile>(()=>cleanProfile(initialProfile||initial));
  const [step,setStep]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[creditBalance,setCreditBalance]=useState<number|null>(null);
  const [skill,setSkill]=useState(''),[location,setLocation]=useState(initialProfile?.location.preferred_regions.join(', ')||''),[industries,setIndustries]=useState(initialProfile?.preferred_industries.join(', ')||'');
  const [visaRoute,setVisaRoute]=useState(initialVisa?.route||''),[visaExpiry,setVisaExpiry]=useState(initialVisa?.expiry||''),[restoredNotice,setRestoredNotice]=useState(''),[draftReady,setDraftReady]=useState(false);
  const [signedIn,setSignedIn]=useState(embedded),[accountLoading,setAccountLoading]=useState(!embedded),[accountError,setAccountError]=useState(false);
  const edited=useRef(false),draftKey=useRef(''),submissionKey=useRef<string|null>(null),roleInput=useRef<HTMLInputElement>(null),focusRole=useRef(false);
  const router=useRouter();
  function touch(){edited.current=true;submissionKey.current=null;}
  function update(patch:Partial<Profile>){touch();setProfile(p=>({...p,...patch}));setError('');}
  function restore(p:Profile){const next=cleanProfile(p);setProfile(next);setLocation(next.location.preferred_regions.join(', '));setIndustries(next.preferred_industries.join(', '));}
  function startFresh(){touch();restore(initial);setStep(0);setSkill('');setVisaRoute('');setVisaExpiry('');setError('');setRestoredNotice('Profile reset. Start with a new direction.');try{sessionStorage.removeItem(draftKey.current);}catch{}}
  async function checkAccount(){
    setAccountLoading(true);setAccountError(false);
    try{
      const account=embedded?{signed_in:true}:await api<{signed_in:boolean}>('account/identity');setSignedIn(account.signed_in);
      if(!account.signed_in){setDraftReady(true);return;}
      const saved=await api<{account_key:string;profile:Profile|null}>('account/profile'+(sourceSession?'?session_id='+sourceSession:''));
      draftKey.current='sponsorreach:onboarding:v2:'+saved.account_key+':'+(sourceSession||'new');
      let draft:Profile|null=null;
      try{const stored=JSON.parse(sessionStorage.getItem(draftKey.current)||'null');if(!newSearch&&stored?.expires_at>Date.now()&&validProfile(stored.profile)){draft=stored.profile;if(!edited.current){setStep(Math.max(0,Math.min(2,Number(stored.step)||0)));if(typeof stored.visaRoute==='string')setVisaRoute(stored.visaRoute);if(typeof stored.visaExpiry==='string')setVisaExpiry(stored.visaExpiry);}}}catch{}
      const previous=sourceSession?saved.profile:draft;
      if(!edited.current&&previous&&validProfile(previous)){restore(previous);setRestoredNotice(sourceSession?'Editing this shortlist’s profile.':'Your unfinished profile has been restored.');}
      setDraftReady(true);
    }catch{setAccountError(true);}finally{setAccountLoading(false);}
  }
  useEffect(()=>{void checkAccount();},[]);
  useEffect(()=>{if(step===0&&error&&focusRole.current){roleInput.current?.focus();focusRole.current=false;}},[step,error]);
  useEffect(()=>{
    if(!draftReady||!draftKey.current)return;
    const current={...profile,location:{...profile.location,preferred_regions:entries(location,5)},preferred_industries:entries(industries,5)};
    try{sessionStorage.setItem(draftKey.current,JSON.stringify({expires_at:Date.now()+86400000,profile:current,step,visaRoute,visaExpiry}));}catch{}
  },[profile,location,industries,step,visaRoute,visaExpiry,draftReady]);
  function addSkill(value:string){const label=value.trim();if(label&&!profile.skills.some(s=>s.label.toLowerCase()===label.toLowerCase())&&profile.skills.length<20)update({skills:[...profile.skills,{label,source:'user'}]});setSkill('');}
  function checkedProfile(){return {...profile,background:{subject:profile.background.subject.trim(),specialization:''},role_intents:profile.role_intents.map(r=>({...r,raw_label:r.raw_label.trim()})),location:{...profile.location,preferred_regions:entries(location,5)},preferred_industries:entries(industries,5)};}
  async function next(event:React.FormEvent){
    event.preventDefault();setError('');
    const current=checkedProfile();
    if(current.background.subject.length<2||current.role_intents.some(r=>r.raw_label.length<2)){setStep(0);setError('Enter your background and at least one desired role using two or more characters.');return;}
    const broad=current.role_intents.find(r=>['analyst','engineer','consultant','manager','business','graduate'].includes(r.raw_label.toLowerCase()));
    if(broad){focusRole.current=true;setStep(0);setError(`Which type of ${broad.raw_label.toLowerCase()} role interests you? Enter a specific role, such as software engineering manager or mechanical design engineer.`);return;}
    if(step===0){update(current);setStep(1);return;}
    if(step===1){
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
      const problem=e as Error&{status?:number;code?:string;field?:string};
      if(problem.status===402){setCreditBalance(0);refreshCredits();}
      if(problem.code==='profile_needs_clarification'||problem.field?.startsWith('profile.')){focusRole.current=true;setStep(0);}
      setError(problem.message);setBusy(false);
    }
  }
  return <section className={embedded?'intake-shell embedded-intake':'intake-shell shell'}>
    {embedded?<header className="editor-heading"><div><span className="workspace-kicker">{sourceSession?'REFINE SHORTLIST':'NEW SEARCH'}</span><h2>{sourceSession?'Fine-tune your search':'Start a new search'}</h2></div><button type="button" className="button secondary small" disabled={busy} onClick={onCancel}><X size={16}/>Close</button></header>:<aside className="intake-aside"><Link href="/" className="back-link"><ArrowLeft size={16}/>Back to home</Link><p className="eyebrow">YOUR SKILLS. YOUR SPONSOR SHORTLIST.</p><h1>Find sponsors for<br/>the work <em>you want.</em></h1><p>Tell us your background and the work you want to do.</p><ol className="step-list">{['Your background','Your preferences','Review and search'].map((label,i)=><li key={label} className={i===step?'active':i<step?'complete':''}><span>{i<step?<Check size={16}/>:String(i+1).padStart(2,'0')}</span><div>{label}</div></li>)}</ol><div className="aside-note"><Compass size={22}/><span>Research companies relevant to your skills.</span></div></aside>}
    <div className="form-panel"><CreditAllowance onBalance={setCreditBalance}/><div className="form-top"><span>STEP {step+1} OF 3</span><span>About 2 minutes</span></div><div className="progress-track"><span style={{width:`${(step+1)/3*100}%`}}/></div>
      <form onSubmit={next}>
        {restoredNotice&&<p className="notice" role="status">{restoredNotice} <button type="button" className="text-button" onClick={startFresh}>Start fresh</button></p>}
        {step===0&&<><h2>What work are you looking for?</h2><p className="muted">Your background and target roles help us identify relevant companies.</p>
          <label>Degree, field of study, or professional background<input required minLength={2} maxLength={180} value={profile.background.subject} onChange={e=>update({background:{subject:e.target.value,specialization:''}})} placeholder="e.g. Mechanical Engineering, Accounting, Nursing"/></label>
          <div className="label-row"><span>What roles interest you?</span></div>{profile.role_intents.map((role,i)=><div className="role-input" key={i}><input ref={i===0?roleInput:undefined} aria-label={`Desired role ${i+1}`} required minLength={2} maxLength={120} value={role.raw_label} onChange={e=>update({role_intents:profile.role_intents.map((r,n)=>n===i?{raw_label:e.target.value,confirmed:false}:r)})} placeholder="e.g. Mechanical design engineer"/>{i>0&&<button type="button" className="icon-button" aria-label="Remove role" onClick={()=>update({role_intents:profile.role_intents.filter((_,n)=>n!==i)})}><X size={16}/></button>}</div>)}
          {profile.role_intents.length<3&&<button type="button" className="text-button" onClick={()=>update({role_intents:[...profile.role_intents,{raw_label:'',confirmed:false}]})}><Plus size={14}/>Add another role</button>}
          <label>Career stage<select value={profile.career_stage} onChange={e=>update({career_stage:e.target.value as Profile['career_stage']})}><option value="student">Currently studying</option><option value="graduate">Graduate / starting my career</option><option value="experienced">Experienced professional</option><option value="career_changer">Changing career direction</option></select></label>
        </>}
        {step===1&&<><h2>Which companies could fit you?</h2><p className="muted">Add the skills and preferences you want us to consider.</p>
          <label>Skills you want to use <span className="optional">optional</span><div className="input-action"><input maxLength={100} value={skill} onChange={e=>setSkill(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addSkill(skill);}}} placeholder="Add a technical or professional skill"/><button type="button" className="icon-button" aria-label="Add skill" onClick={()=>addSkill(skill)}><Plus size={18}/></button></div></label>
          <div className="chip-list">{profile.skills.map(s=><button type="button" className="chip selected" key={s.label} onClick={()=>update({skills:profile.skills.filter(v=>v.label!==s.label)})}>{s.label}<X size={12}/></button>)}</div>
          <label>Preferred UK location<input maxLength={100} value={location} onChange={e=>{touch();setLocation(e.target.value);}} placeholder="Anywhere in the UK, or a city / region"/></label>
          <label className="checkbox-line"><input type="checkbox" checked={profile.location.relocate} onChange={e=>update({location:{...profile.location,relocate:e.target.checked}})}/><span>I’m willing to relocate.</span></label>
          <label>Preferred industries or areas of work<input maxLength={250} value={industries} onChange={e=>{touch();setIndustries(e.target.value);}} placeholder="e.g. Renewable energy, healthcare"/></label>
          <section aria-labelledby="visa-timing-title"><h3 id="visa-timing-title">Visa timing</h3><label>Current route<select value={visaRoute} onChange={e=>{touch();setVisaRoute(e.target.value);}}><option value="">Prefer not to say</option><option>Graduate</option><option>Student</option><option>Skilled Worker</option><option>Other</option></select></label><label>Your visa expiry date<input type="date" value={visaExpiry} onChange={e=>{touch();setVisaExpiry(e.target.value);}}/></label><p className="tiny muted">Visa timing does not change your company recommendations. You can leave these fields blank.</p></section>
        </>}
        {step===2&&<><h2>Your sponsor search starts here.</h2><p className="muted">Review your details, then find relevant sponsor companies.</p><div className="profile-summary"><span className="eyebrow">YOUR SPONSOR SEARCH PROFILE</span><h3>{profile.role_intents.map(r=>r.raw_label).join(' · ')}</h3><p>{profile.background.subject}</p><div className="chip-list">{profile.skills.map(s=><span className="chip" key={s.label}>{s.label}</span>)}</div><small>{profile.location.preferred_regions.join(', ')||'Anywhere in the UK'}{profile.location.relocate?' · Open to relocating':''}</small>{profile.preferred_industries.length>0&&<p>{profile.preferred_industries.join(', ')}</p>}</div>
          {accountLoading?<p role="status">Checking your account…</p>:accountError?<p className="error" role="alert">We couldn’t check your account. <button type="button" className="text-button" onClick={()=>void checkAccount()}>Retry</button></p>:!signedIn?<p className="error"><Link href="/account">Sign in to start your search</Link></p>:null}
        </>}
        {error&&<p className="error" role="alert">{error}</p>}
        <div className="form-actions"><button type="button" className="back-button reset-profile" disabled={busy||accountLoading} onClick={startFresh}><RotateCcw size={15}/>Reset profile</button>{step>0&&<button type="button" className="back-button" disabled={busy} onClick={()=>{setStep(step-1);setError('');}}><ArrowLeft size={16}/>Back</button>}<button className="button" type="submit" disabled={busy||(step===2&&(accountLoading||accountError||creditBalance===0||!signedIn))}>{busy?'Working…':step===2?sourceSession?'Update this shortlist':'Find my sponsors':'Continue'}<ArrowRight size={18}/></button></div>
      </form>
    </div>
  </section>;
}
