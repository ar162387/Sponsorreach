const {test,beforeEach,afterEach}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom'),ts=require('typescript'),React=require('react');
const {act}=React,{createRoot}=require('react-dom/client');
const base=path.resolve(__dirname,'..'),compiled=new Map(),event='sponsorreach:credits-changed';
function load(file){file=path.resolve(file);if(compiled.has(file))return compiled.get(file).exports;const module={exports:{}};compiled.set(file,module);const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;function localRequire(spec){
 if(spec.endsWith('/dashboard-shell'))return {CREDITS_CHANGED:event,refreshCredits:()=>window.dispatchEvent(new window.Event(event))};
 if(spec.endsWith('.module.css'))return {};
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
async function setField(element, value) {
  await act(async () => {
    const select = element instanceof window.HTMLSelectElement;
    const prototype = select ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
    element.dispatchEvent(new window.Event(select ? 'change' : 'input', { bubbles: true }));
  });
}
async function addTag(field, kind, text, commit = true) {
  const group = container.querySelectorAll('.search-tag-field')[field];
  await setField(group.querySelector('select'), kind);
  const input = group.querySelector('input');
  await setField(input, text);
  if (commit) await act(async () => {
    input.focus();
    input.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  });
}
async function fillSearch(role = 'Mechanical engineer', background = 'Mechanical Engineering', onComplete = () => {}) {
  await render(React.createElement(Intake, { onComplete, onCancel() {} }));
  await setField(container.querySelector('.search-background-field input'), background);
  await addTag(0, 'role', role);
}
const findSponsors = () => button('Find sponsors');

test('depleted account keeps the form, disables search and links to billing', async () => {
  await fillSearch();
  assert(findSponsors().disabled);
  assert(container.textContent.includes('Your credits are used up'));
  assert(container.querySelector('a[href="/account/billing"]'));
  assert(button('Mechanical engineer'));
  assert(!calls.some(c => c.url === '/api/matches'));
});
test('confirmed top-up refreshes allowance without losing search criteria', async () => {
  await fillSearch();
  balance = 100;
  await act(async () => window.dispatchEvent(new window.Event(event)));
  assert(!findSponsors().disabled);
  assert(button('Mechanical engineer'));
});
test('last-credit race returns a helpful error and keeps the draft', async () => {
  balance = 1;
  await fillSearch();
  extra = url => url === '/api/matches' ? json({ detail:'Insufficient credits. Open billing to subscribe.' }, 402) : null;
  balance = 0;
  await submit();
  assert(findSponsors().disabled);
  assert([...container.querySelectorAll('[role="alert"]')].some(node => node.textContent.includes('Insufficient credits')));
  assert(button('Mechanical engineer'));
});
const ready=(cost=1)=>({session_id:'11111111-1111-4111-8111-111111111111',status:'ready',stage:'Ready',access:'preview',credit_mode:true,balance:0,next_locked_batch:1,next_batch_cost:cost,locked_count:5,total_count:5,preview:[],next_cursor:null,profile,loading_context:{roles:['Mechanical engineer'],background:'Engineering',specialization:'',skills:[],locations:[],related_roles_enabled:false}});
test('free repeated batch can be opened with zero credits',async()=>{extra=url=>url.startsWith('/api/matches/')?json(ready(0)):null;await render(React.createElement(Results,{id:ready().session_id}));assert(button('Show more · Free'));assert(button('Open batch · Free'));assert(!button('Open batch · Free').disabled);assert(container.textContent.includes('This batch is free'));});
test('paid batch at zero credits shows billing while keeping results usable',async()=>{extra=url=>url.startsWith('/api/matches/')?json(ready(1)):null;await render(React.createElement(Results,{id:ready().session_id}));assert(button('Open batch · 1 credit').disabled);assert(container.querySelector('a[href="/account/billing"]'));});
test('empty search and failed search have recovery actions',async()=>{extra=url=>url.startsWith('/api/matches/')?json({...ready(),locked_count:0,total_count:0}):null;await render(React.createElement(Results,{id:ready().session_id}));assert(container.querySelector('.empty-state'));assert(container.textContent.includes('Refine this shortlist'));await act(async()=>root.unmount());root=createRoot(container);extra=url=>url.startsWith('/api/matches/')?json({...ready(),status:'failed'}):null;await render(React.createElement(Results,{id:ready().session_id}));assert(container.textContent.includes('Retry this shortlist'));});

for(const enabled of [true,false])test(`billing subscription button reflects checkout availability: ${enabled}`,async()=>{extra=url=>{if(url==='/api/account/billing')return json({available:10,reserved:0,monthly_credits:0,period:null,periods:[],subscription:null});if(url==='/api/billing/plans')return json({plans:[{slug:'monthly',name:'SponsorReach Monthly',credits:100,amount_minor:2499,currency:'EUR',environment:'test'}],enabled});if(url==='/api/billing/records')return json({payments:[],refunds:[],pending:false});if(url.startsWith('/api/account/usage'))return json({days:[]});if(url.startsWith('/api/account/credit-history'))return json({entries:[]});return null;};await render(React.createElement(Billing));assert.equal(button('Subscribe for €24.99/month').disabled,!enabled);assert.equal(container.textContent.includes('New purchases are currently unavailable'),!enabled);});

test('new searches use two typed fields to send multiple roles, skills, locations and industries', async () => {
  balance = 10;
  let payload, completed;
  extra = (url, options) => {
    if (url !== '/api/matches') return null;
    payload = JSON.parse(options.body);
    return json({ session_id: ready().session_id }, 202);
  };
  await fillSearch(undefined, undefined, id => { completed = id; });
  assert.equal(container.querySelectorAll('.search-tag-field input').length, 2);
  assert(!/Career stage|Visa timing|Include related roles|STEP 1 OF 3/.test(container.textContent));
  await addTag(0, 'role', 'Product designer');
  await addTag(0, 'skill', 'CAD');
  await addTag(0, 'skill', 'Prototyping');
  await addTag(1, 'location', 'Coventry');
  await addTag(1, 'location', 'Manchester');
  await addTag(1, 'industry', 'Renewable energy');
  await addTag(1, 'industry', 'Healthcare', false);
  assert(!payload);
  await submit();
  assert.equal(completed, ready().session_id);
  assert.deepEqual(payload.profile.role_intents.map(role => role.raw_label), ['Mechanical engineer', 'Product designer']);
  assert.deepEqual(payload.profile.skills.map(skill => skill.label), ['CAD', 'Prototyping']);
  assert.deepEqual(payload.profile.location, { preferred_regions:['Coventry','Manchester'], mode:'prefer_area', relocate:false, strict:false });
  assert.deepEqual(payload.profile.preferred_industries, ['Renewable energy', 'Healthcare']);
  assert.equal(payload.visa_context, null);
  assert.equal(payload.profile.career_stage, 'graduate');
  assert(!calls.some(c => /profiles\/|catalogue\/status|account\/profile/.test(c.url)));
});

test('broad roles are explained and focused before a search request is sent', async () => {
  balance = 10;
  await fillSearch('manager', 'Software engineering');
  await submit();
  assert(container.textContent.includes('Which type of manager role interests you?'));
  assert.equal(document.activeElement, container.querySelector('.search-tag-field input'));
  assert(!calls.some(c => c.url === '/api/matches'));
});

test('an ambiguous architect search asks for a profession and resubmits the selected concept', async () => {
  balance = 10;
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
  await fillSearch('Architect', 'Architecture and computer science');
  await submit();
  assert(findSponsors().disabled);
  assert(container.textContent.includes('Which type of architecture work do you want to do?'));
  await setField(container.querySelector('.search-clarification select'), 'bootstrap:architecture');
  assert(!findSponsors().disabled);
  await submit();
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1].profile.role_intents, [
    {raw_label: 'Architect', confirmed: true, concept_id: 'bootstrap:architecture'},
  ]);
  assert.notEqual(requests[0].idempotency_key, requests[1].idempotency_key);
});

test('refine uses the same shortlist endpoint and shows the matching loader while submitting',async()=>{
  let finish;
  const saved = { ...ready(), profile: {
    ...profile, career_stage:'experienced', background:{subject:'Mechanical Engineering',specialization:'Robotics'},
    skills:[{label:'CAD',source:'user'}], related_roles_enabled:true,
    location:{preferred_regions:['Coventry'],mode:'selected_area',relocate:false,strict:true},
  } };
  extra=(url,options)=>{
    if(url.endsWith('/refresh'))return new Promise(resolve=>{finish=()=>resolve(json({session_id:ready().session_id,status:'queued'},202));});
    if(url.includes('/api/matches/'))return json(saved);
    return null;
  };
  await render(React.createElement(Results,{id:ready().session_id,embedded:true}));
  assert.equal(container.querySelector('form[aria-label="Shortlist filters"] input').value,'Mechanical Engineering · Robotics');
  assert(button('Mechanical engineer'));
  assert(button('CAD'));
  assert(button('Coventry'));
  await addTag(0, 'skill', 'Python');
  await addTag(1, 'industry', 'Manufacturing');
  await submit();
  assert(container.querySelector('.loader-orbit'));
  assert(!container.textContent.includes('credits · Billing'));
  const request=calls.find(call=>call.url.endsWith('/refresh'));
  assert.equal(request.url,'/api/matches/'+ready().session_id+'/refresh');
  const payload = JSON.parse(request.options.body);
  assert.equal(payload.accept_credit_cost, true);
  assert.deepEqual(payload.profile.background, saved.profile.background);
  assert.deepEqual(payload.profile.location, saved.profile.location);
  assert.equal(payload.profile.career_stage, 'experienced');
  assert.equal(payload.profile.related_roles_enabled, true);
  assert.deepEqual(payload.profile.skills.map(skill => skill.label), ['CAD','Python']);
  assert.deepEqual(payload.profile.preferred_industries, ['Manufacturing']);
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
