// Component integration tests in a virtual DOM; no browser or production account.
const {test,beforeEach,afterEach}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs'),{createRequire}=require('node:module');
const base=path.resolve(__dirname,'..'),requireWeb=createRequire(path.join(base,'package.json'));
const {JSDOM}=requireWeb('jsdom'),ts=requireWeb('typescript'),React=requireWeb('react');
const {act}=React,{createRoot}=requireWeb('react-dom/client');
const compiled=new Map();
function load(file){
 file=path.resolve(file);if(compiled.has(file))return compiled.get(file).exports;
 const module={exports:{}};compiled.set(file,module);
 const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
 function localRequire(spec){
  if(spec==='next/link')return {__esModule:true,default:({children,href,...props})=>React.createElement('a',{...props,href},children),useLinkStatus:()=>({pending:false})};
  if(spec==='next/image')return {__esModule:true,default:({unoptimized,...props})=>React.createElement('img',props)};
  if(spec.startsWith('@/')||spec.startsWith('.')){
   let target=spec.startsWith('@/')?path.join(base,spec.slice(2)):path.resolve(path.dirname(file),spec);
   if(target.endsWith('.json'))return JSON.parse(fs.readFileSync(target));
   for(const ext of ['','.tsx','.ts'])if(fs.existsSync(target+ext))return load(target+ext);
  }
  return requireWeb(spec);
 }
 new Function('require','module','exports',code)(localRequire,module,module.exports);return module.exports;
}
const Results=load(path.join(base,'components/results.tsx')).default;
const Account=load(path.join(base,'components/account.tsx')).default;
const {Card}=load(path.join(base,'components/employer-card.tsx'));
const idA='22222222-2222-4222-8222-222222222222',idB='22222222-2222-4222-8222-222222222223';
const profile={background:{subject:'Computing',specialization:''},role_intents:[{raw_label:'Developer'}],skills:[],location:{preferred_regions:[],relocate:false}};
const company=name=>({employer_id:name,session_id:idA,name,town:'London',bookmarked:false,group:'direct',explanation:{text:'Software services',summary:'Software services',sources:[],skill_hits:[]},tags:[],channels:[{kind:'email',value:'careers@example.invalid'},{kind:'phone',value:'+44 20 0000 0000'},{kind:'website',value:'https://example.invalid'},{kind:'address',value:'10 Example Road'},{kind:'job_board',label:'Indeed · job board',value:'https://example.invalid/jobs'}],sponsor:{status:'register_authorized'},verified_open_vacancies:[],is_demo:false});
const saved=(id,name)=>({session_id:id,status:'ready',stage:'Your shortlist is ready',access:'preview',demo_price_gbp:19,total_count:1,direct_count:1,next_cursor:null,preview:[company(name)]});
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
let root,container,dom,calls,handler;
beforeEach(()=>{
 dom=new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',{url:'http://127.0.0.1:3036/account',pretendToBeVisual:true});
 global.window=dom.window;global.document=dom.window.document;global.HTMLElement=dom.window.HTMLElement;global.Node=dom.window.Node;
 window.HTMLDialogElement.prototype.close=function(){this.open=false;};window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
 global.IS_REACT_ACT_ENVIRONMENT=true;calls=[];
 global.fetch=(url,options={})=>{calls.push({url,options});return handler(url,options);};
 container=document.getElementById('root');root=createRoot(container);
});
afterEach(async()=>{await act(async()=>root.unmount());dom.window.close();});
const render=component=>act(async()=>root.render(component));
const click=element=>act(async()=>element.dispatchEvent(new window.MouseEvent('click',{bubbles:true})));
const finish=(pending,value)=>act(async()=>{pending.resolve(value);await pending.promise;});

test('saved results show a skeleton, then cards, with no matching animation or duplicate results fetch',async()=>{
 const request=deferred();handler=()=>request.promise;
 await render(React.createElement(Results,{id:idA}));
 assert(container.querySelector('.results-skeleton'));assert(!container.querySelector('.loader-orbit'));
 await finish(request,json(saved(idA,'Saved company')));
 assert(container.textContent.includes('Saved company'));assert(!container.querySelector('.loader-orbit'));
 assert.equal(calls.filter(c=>c.url===`/api/matches/${idA}`).length,1);
 assert(!calls.some(c=>c.url.includes('/results')));
});

test('matching animation appears only after a queued or processing response',async()=>{
 handler=async()=>json({session_id:idA,status:'processing',stage:'Checking professional relevance',access:'preview',demo_price_gbp:19});
 await render(React.createElement(Results,{id:idA}));assert(container.querySelector('.loader-orbit'));
 assert(container.textContent.includes('Checking how company work fits your background'));
});

test('bookmark click updates immediately, disables duplicate clicks, and restores state on a failed save',async()=>{
 const request=deferred(),updates=[];handler=()=>request.promise;
 await render(React.createElement(Card,{employer:company('One'),id:idA,position:0,dashboard:true,onBookmarkChange:saved=>updates.push(saved)}));
 const button=container.querySelector('.reach-save');await click(button);
 assert.equal(button.getAttribute('aria-pressed'),'true');assert(button.disabled);assert.equal(button.getAttribute('aria-busy'),'true');
 await finish(request,json({detail:'Save unavailable'},503));
 assert.equal(button.getAttribute('aria-pressed'),'false');assert(!button.disabled);assert.deepEqual(updates,[true,false]);
 assert(container.querySelector('[role="alert"]').textContent.includes('previous choice has been restored'));
});

test('compact company exposes primary contacts and expands address and job boards on demand',async()=>{
 handler=async()=>json({saved:true});await render(React.createElement(Card,{employer:company('One'),id:idA,position:0,dashboard:true,compact:true}));
 assert(container.querySelector('a[href^="mailto:"]'));assert(container.querySelector('a[href^="tel:"]'));
 assert(!container.textContent.includes('10 Example Road'));assert(!container.textContent.includes('Indeed'));
 await click(container.querySelector('.company-reveal'));
 assert(container.textContent.includes('10 Example Road'));assert(container.textContent.includes('Indeed'));
 assert.equal(container.querySelector('.company-reveal').getAttribute('aria-expanded'),'true');
});

function setupAccount(){
 const a=deferred(),b=deferred(),star=deferred();
 const rows=[{id:idA,status:'ready',created_at:'2026-10-18',roles:['Software'],access:'preview',starred:false},{id:idB,status:'ready',created_at:'2026-10-17',roles:['Water'],access:'preview',starred:false}];
 handler=(url,options)=>{
  if(url==='/api/account/overview')return Promise.resolve(json({first_name:'Maya',profile,sessions:rows,bookmarks:[]}));
  if(url.endsWith('/star'))return star.promise;
  if(url===`/api/matches/${idA}`)return a.promise;
  if(url===`/api/matches/${idB}`)return b.promise;
  return Promise.resolve(json({saved:true}));
 };
 return {a,b,star};
}
test('selecting a shortlist updates its highlight immediately and a late response cannot replace the selection',async()=>{
 const {a,b}=setupAccount();await render(React.createElement(Account,{authenticated:true}));
 assert(container.querySelector('.workspace-columns'));assert(!container.querySelector('.dashboard-grid'));
 const buttons=container.querySelectorAll('.shortlist-select');await click(buttons[1]);
 assert.equal(buttons[1].getAttribute('aria-pressed'),'true');assert(container.querySelector('.saved-results-loading'));assert(!container.querySelector('.loader-orbit'));
 await finish(b,json(saved(idB,'Water company')));await finish(a,json(saved(idA,'Late software company')));
 assert(container.textContent.includes('Water company'));assert(!container.textContent.includes('Late software company'));
 assert(window.location.search.includes(idB));
 assert.equal(container.querySelectorAll('.shortlist-open')[1].getAttribute('href'),'/results/'+idB);
 const aborted=calls.find(c=>c.url===`/api/matches/${idA}`);assert(aborted.options.signal.aborted);
});

test('returning to a cached shortlist displays saved cards immediately while revalidating',async()=>{
 const {a,b}=setupAccount();await render(React.createElement(Account,{authenticated:true}));await finish(a,json(saved(idA,'Software company')));
 await click(container.querySelectorAll('.shortlist-select')[1]);await finish(b,json(saved(idB,'Water company')));
 const nextRequest=deferred();const previousHandler=handler;handler=(url,options)=>url===`/api/matches/${idA}`?nextRequest.promise:previousHandler(url,options);
 await click(container.querySelectorAll('.shortlist-select')[0]);
 assert(container.textContent.includes('Software company'));assert(!container.querySelector('.saved-results-loading'));assert(!container.querySelector('.loader-orbit'));
});

test('star responds optimistically and rolls back on failure',async()=>{
 const {a,star}=setupAccount();await render(React.createElement(Account,{authenticated:true}));await finish(a,json(saved(idA,'Software company')));
 const button=container.querySelector('.shortlist-item-star');await click(button);
 assert.equal(button.getAttribute('aria-pressed'),'true');assert(button.disabled);
 await finish(star,json({detail:'Unavailable'},503));
 assert.equal(button.getAttribute('aria-pressed'),'false');assert(container.querySelector('.workspace-notice').textContent.includes('restored'));
});

test('an authorization failure clears cached employer cards rather than leaving private results visible',async()=>{
 const request=deferred(),data=saved(idA,'Cached private company');
 const cache=new Map([[idA,{session:data,cards:data.preview,cursor:null}]]);
 handler=url=>url===`/api/matches/${idA}`?request.promise:Promise.resolve(json({saved:true}));
 await render(React.createElement(Results,{id:idA,cache}));assert(container.textContent.includes('Cached private company'));
 await finish(request,json({detail:'Sign in first'},403));
 assert.equal(cache.size,0);assert(!container.textContent.includes('Cached private company'));assert(container.querySelector('[role="alert"]'));
});

test('the previous shortlist selection is addressable and restored by browser history events',async()=>{
 const {a,b}=setupAccount();await render(React.createElement(Account,{authenticated:true}));await finish(a,json(saved(idA,'Software company')));
 assert(window.location.search.includes(idA));
 await click(container.querySelectorAll('.shortlist-select')[1]);await finish(b,json(saved(idB,'Water company')));
 assert(window.location.search.includes(idB));
 await act(async()=>{window.history.replaceState(null,'','/account?shortlist='+idA);window.dispatchEvent(new window.PopStateEvent('popstate'));});
 assert.equal(container.querySelectorAll('.shortlist-select')[0].getAttribute('aria-pressed'),'true');assert(container.textContent.includes('Software company'));
});
