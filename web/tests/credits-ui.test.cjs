const {test,beforeEach,afterEach}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),ts=require('typescript'),React=require('react');
const {act}=React,{createRoot}=require('react-dom/client');
const base=path.resolve(__dirname,'..'),compiled=new Map(),event='sponsorreach:credits-changed';
function load(file){file=path.resolve(file);if(compiled.has(file))return compiled.get(file).exports;const module={exports:{}};compiled.set(file,module);const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;function localRequire(spec){
 if(spec.endsWith('/dashboard-shell'))return {CREDITS_CHANGED:event,refreshCredits:()=>window.dispatchEvent(new window.Event(event))};
 if(spec==='next/navigation')return {useRouter:()=>({push(){}}),usePathname:()=>'/account/search',useSearchParams:()=>new URLSearchParams()};
 if(spec==='next/link')return {__esModule:true,default:({children,href,...props})=>React.createElement('a',{...props,href},children),useLinkStatus:()=>({pending:false})};
 if(spec==='next/image')return {__esModule:true,default:({unoptimized,...props})=>React.createElement('img',props)};
 if(spec.startsWith('@/')||spec.startsWith('.')){let target=spec.startsWith('@/')?path.join(base,spec.slice(2)):path.resolve(path.dirname(file),spec);if(target.endsWith('.json'))return JSON.parse(fs.readFileSync(target));for(const ext of ['','.tsx','.ts'])if(fs.existsSync(target+ext))return load(target+ext);}
 return require(spec);
 }new Function('require','module','exports',code)(localRequire,module,module.exports);return module.exports;}
const Intake=load(path.join(base,'components/intake.tsx')).default,Results=load(path.join(base,'components/results.tsx')).default,Billing=load(path.join(base,'components/billing.tsx')).default;
const profile={profile_version:1,background:{subject:'Mechanical Engineering',specialization:''},role_intents:[{raw_label:'Mechanical engineer',confirmed:true}],explore:false,career_stage:'graduate',skills:[],experience_summary:'',preferred_industries:[],certifications:[],location:{preferred_regions:[],relocate:false,strict:false},related_roles_enabled:false};
let dom,root,container,balance,calls,extra;
const json=(v,status=200)=>new Response(JSON.stringify(v),{status});
beforeEach(()=>{dom=new JSDOM('<div id="root"></div>',{url:'http://localhost/account/search',pretendToBeVisual:true});global.window=dom.window;global.document=dom.window.document;global.sessionStorage=dom.window.sessionStorage;global.HTMLElement=dom.window.HTMLElement;global.Node=dom.window.Node;global.IS_REACT_ACT_ENVIRONMENT=true;window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};window.HTMLDialogElement.prototype.close=function(){this.open=false;};window.HTMLElement.prototype.attachEvent=function(){};window.HTMLElement.prototype.detachEvent=function(){};window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});container=document.getElementById('root');root=createRoot(container);balance=0;calls=[];extra=null;
 global.fetch=async(url,options={})=>{calls.push({url,options});if(extra){const result=extra(url,options);if(result)return result;}if(url.includes('catalogue/status'))return json({credit_mode:true});if(url.includes('account/identity'))return json({signed_in:true});if(url.includes('account/profile'))return json({account_key:'credit-test',profile:null});if(url.includes('account/allowance'))return json({credit_mode:true,available:balance});if(url.includes('profiles/normalize'))return json({role_intents:profile.role_intents,clarification:null});if(url.includes('profiles/suggestions'))return json({suggestions:[]});throw Error('Unexpected test request '+url);};});
afterEach(async()=>{await act(async()=>root.unmount());dom.window.close();});
const render=node=>act(async()=>root.render(node));
const submit=()=>act(async()=>container.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true})));
const button=text=>[...container.querySelectorAll('button')].find(b=>b.textContent.includes(text));
async function review(){await render(React.createElement(Intake,{embedded:true,initialProfile:profile}));await submit();await submit();}

test('depleted account preserves draft, disables search and links to billing',async()=>{await review();assert(button('Find my sponsors').disabled);assert(container.textContent.includes('Your credits are used up'));assert(container.querySelector('a[href="/account/billing"]'));assert(sessionStorage.getItem('sponsorreach:onboarding:v2:credit-test:new').includes('Mechanical Engineering'));assert(!calls.some(c=>c.url==='/api/matches'));});
test('confirmed top-up refreshes allowance without losing the profile',async()=>{await review();balance=100;await act(async()=>window.dispatchEvent(new window.Event(event)));assert(!button('Find my sponsors').disabled);assert(!container.textContent.includes('100 credits available'));assert(container.textContent.includes('Mechanical Engineering'));});
test('last-credit race returns a helpful error and keeps the draft',async()=>{balance=1;await review();assert.equal(container.querySelector('.checkbox-line input'),null);extra=(url)=>url==='/api/matches'?json({detail:'Insufficient credits. Open billing to subscribe.'},402):null;balance=0;await submit();assert(button('Find my sponsors').disabled);assert([...container.querySelectorAll('[role="alert"]')].some(node=>node.textContent.includes('Insufficient credits')));assert(sessionStorage.getItem('sponsorreach:onboarding:v2:credit-test:new'));});
const ready=(cost=1)=>({session_id:'11111111-1111-4111-8111-111111111111',status:'ready',stage:'Ready',access:'preview',credit_mode:true,balance:0,next_locked_batch:1,next_batch_cost:cost,locked_count:5,total_count:5,preview:[],next_cursor:null,profile,loading_context:{roles:['Mechanical engineer'],background:'Engineering',specialization:'',skills:[],locations:[],related_roles_enabled:false}});
test('free repeated batch can be opened with zero credits',async()=>{extra=url=>url.startsWith('/api/matches/')?json(ready(0)):null;await render(React.createElement(Results,{id:ready().session_id}));assert(button('Show more · Free'));assert(button('Open batch · Free'));assert(!button('Open batch · Free').disabled);assert(container.textContent.includes('This batch is free'));});
test('paid batch at zero credits shows billing while keeping results usable',async()=>{extra=url=>url.startsWith('/api/matches/')?json(ready(1)):null;await render(React.createElement(Results,{id:ready().session_id}));assert(button('Open batch · 1 credit').disabled);assert(container.querySelector('a[href="/account/billing"]'));});
test('empty search and failed search have recovery actions',async()=>{extra=url=>url.startsWith('/api/matches/')?json({...ready(),locked_count:0,total_count:0}):null;await render(React.createElement(Results,{id:ready().session_id}));assert(container.querySelector('.empty-state'));assert(container.textContent.includes('Refine this shortlist'));await act(async()=>root.unmount());root=createRoot(container);extra=url=>url.startsWith('/api/matches/')?json({...ready(),status:'failed'}):null;await render(React.createElement(Results,{id:ready().session_id}));assert(container.textContent.includes('Retry this shortlist'));});

for(const enabled of [true,false])test(`billing subscription button reflects checkout availability: ${enabled}`,async()=>{extra=url=>{if(url==='/api/account/billing')return json({available:10,reserved:0,monthly_credits:0,period:null,periods:[],subscription:null});if(url==='/api/billing/plans')return json({plans:[{slug:'monthly',name:'SponsorReach Monthly',credits:100,amount_minor:2499,currency:'EUR',environment:'test'}],enabled});if(url==='/api/billing/records')return json({payments:[],refunds:[],pending:false});if(url.startsWith('/api/account/usage'))return json({days:[]});if(url.startsWith('/api/account/credit-history'))return json({entries:[]});return null;};await render(React.createElement(Billing));assert.equal(button('Subscribe for €24.99/month').disabled,!enabled);assert.equal(container.textContent.includes('New purchases are currently unavailable'),!enabled);});

 test('form keeps location, related roles and visa in step two',async()=>{balance=10;await render(React.createElement(Intake,{embedded:true,initialProfile:profile}));assert(!container.textContent.includes('Specialisation'));assert(!container.textContent.includes('Help me explore'));assert(!container.textContent.includes('Find career ideas'));assert(!container.textContent.includes('credits available'));await submit();assert(container.textContent.includes('Preferred industries or areas of work'));assert(container.textContent.includes('Visa timing'));assert(container.querySelector('input[type="date"]'));assert(!container.querySelector('input[type="date"]').required);assert(container.querySelector('.intake-visa'));assert(!container.querySelector('textarea'));assert.equal(container.querySelector('.checkbox-line input').checked,false);assert(container.textContent.includes('Only my selected city or county'));await submit();assert(!container.querySelector('input[type="date"]'));assert(!container.textContent.includes('I understand'));assert(!container.textContent.includes('By continuing'));assert(!calls.some(c=>/profiles\/(normalize|suggestions)|catalogue\/status/.test(c.url)));});
 test('role clarification explains the rejection and returns focus to the role field',async()=>{balance=10;await review();extra=url=>url==='/api/matches'?json({detail:{code:'profile_needs_clarification',normalization:{clarification:'Which area of engineering work interests you?'}}},422):null;await submit();assert(container.textContent.includes('Which area of engineering work interests you?'));assert(container.textContent.includes('What work are you looking for?'));assert.equal(document.activeElement.getAttribute('aria-label'),'Desired role 1');assert(!container.textContent.includes('We couldn’t complete this step'));});
 test('restored legacy profiles expose prior related-role opt-in without hidden criteria',async()=>{balance=10;const old={...profile,explore:true,background:{subject:'Engineering',specialization:'Mechanical design'},role_intents:profile.role_intents,experience_summary:'old hidden experience',certifications:['old registration'],related_roles_enabled:true};await render(React.createElement(Intake,{embedded:true,initialProfile:old,onComplete(){}}));await submit();assert.equal(container.querySelector('.checkbox-line input').checked,true);await submit();let payload;extra=(url,options)=>{if(url!=='/api/matches')return null;payload=JSON.parse(options.body);return json({session_id:'11111111-1111-4111-8111-111111111111'});};await submit();assert.equal(payload.profile.explore,false);assert.equal(payload.profile.background.specialization,'');assert(payload.profile.background.subject.includes('Mechanical design'));assert.equal(payload.profile.experience_summary,'');assert.deepEqual(payload.profile.certifications,[]);assert.equal(payload.profile.related_roles_enabled,true);});

 test('the reported manager profile asks for specificity in step one without contacting the server',async()=>{balance=10;const reported={...profile,background:{subject:'software enginer',specialization:''},role_intents:[{raw_label:'manager',confirmed:false}],skills:[{label:'plumber',source:'user'},{label:'software',source:'user'},{label:'full stack',source:'user'}],location:{preferred_regions:['birmingham'],relocate:true,strict:false},related_roles_enabled:true};await render(React.createElement(Intake,{embedded:true,initialProfile:reported}));await submit();assert(container.textContent.includes('Which type of manager role interests you?'));assert.equal(document.activeElement.getAttribute('aria-label'),'Desired role 1');assert(!calls.some(c=>/matches|normalize|suggestions/.test(c.url)));assert(container.querySelector('input[placeholder="e.g. Mechanical Engineering, Accounting, Nursing"]').value==='software enginer');});

test('an ambiguous architect search asks for a profession and resubmits the selected concept', async () => {
  balance = 10;
  const ambiguous = {
    ...profile,
    background: {subject: 'Architecture and computer science', specialization: ''},
    role_intents: [{raw_label: 'Architect', confirmed: false}],
  };
  const requests = [];
  extra = (url, options) => {
    if (url !== '/api/matches') return null;
    requests.push(JSON.parse(options.body));
    if (requests.length > 1) return json({session_id: ready().session_id}, 202);
    return json({detail: {code: 'profile_needs_clarification', normalization: {
      clarification: 'Which type of architecture work do you want to do?',
      choices: [{index: 0, options: [
        {concept_id: 'bootstrap:architecture', label: 'Building architect'},
        {concept_id: 'local:sponsorreach-architect-technology', label: 'Software/cloud architect'},
      ]}],
    }}}, 422);
  };
  await render(React.createElement(Intake, {embedded: true, initialProfile: ambiguous, onComplete() {}}));
  await submit();
  await submit();
  await submit();
  assert(button('Find my sponsors').disabled);
  const select = container.querySelector('select');
  await act(async () => {
    select.value = 'bootstrap:architecture';
    select.dispatchEvent(new window.Event('change', {bubbles: true}));
  });
  assert(!button('Find my sponsors').disabled);
  await submit();
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1].profile.role_intents, [
    {raw_label: 'Architect', confirmed: true, concept_id: 'bootstrap:architecture'},
  ]);
  assert.notEqual(requests[0].idempotency_key, requests[1].idempotency_key);
});

test('a blank member search ignores saved profiles and Enter adds a role without advancing',async()=>{
  await render(React.createElement(Intake,{embedded:true,newSearch:true}));
  assert.equal(container.querySelector('input[placeholder^="e.g. Mechanical Engineering"]').value,'');
  const role=container.querySelector('#search-role');
  await act(async()=>{
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set.call(role,'Car mechanic');
    role.dispatchEvent(new window.Event('input',{bubbles:true}));
  });
  await act(async()=>{
    role.focus();
    role.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
  });
  assert(button('Car mechanic'));
  assert.equal(role.value,'');
  assert(container.textContent.includes('STEP 1 OF 3'));
  assert(!calls.some(call=>call.url.includes('/account/profile')));
});

test('refine uses the same shortlist endpoint and shows the matching loader while submitting',async()=>{
  let finish;
  extra=(url,options)=>{
    if(url.endsWith('/refresh'))return new Promise(resolve=>{finish=()=>resolve(json({session_id:ready().session_id,status:'queued'},202));});
    if(url.includes('/api/matches/'))return json(ready());
    return null;
  };
  await render(React.createElement(Results,{id:ready().session_id,embedded:true}));
  assert.equal(container.querySelector('form[aria-label="Shortlist filters"] input').value,'Mechanical Engineering');
  await submit();
  assert(container.querySelector('.loader-orbit'));
  assert(!container.textContent.includes('credits · Billing'));
  const request=calls.find(call=>call.url.endsWith('/refresh'));
  assert.equal(request.url,'/api/matches/'+ready().session_id+'/refresh');
  assert.equal(JSON.parse(request.options.body).accept_credit_cost,true);
  await act(async()=>finish());
});

test('billing structure is immediately available while account figures are pending',async()=>{
  extra=()=>new Promise(()=>{});
  await render(React.createElement(Billing));
  for(const heading of ['Research activity','Payments and receipts','Credit history']){
    assert([...container.querySelectorAll('h2')].some(element=>element.textContent===heading));
  }
  assert(container.textContent.includes('€24.99'));
  assert(container.querySelector('.billing-management'));
  assert(!container.textContent.includes('Loading your usage'));
});
