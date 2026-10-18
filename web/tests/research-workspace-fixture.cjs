// Local UI fixture only: synthetic identity, employers and slow/failing responses.
// It has no production route and never sends email or calls an embedding provider.
const http = require('node:http');
const host='http://127.0.0.1:9030', app='http://127.0.0.1:3036';
const uid='11111111-1111-4111-8111-111111111111';
const ids=['22222222-2222-4222-8222-222222222222','22222222-2222-4222-8222-222222222223','22222222-2222-4222-8222-222222222224'];
const encode=value=>Buffer.from(JSON.stringify(value)).toString('base64url');
const exp=Math.floor(Date.now()/1000)+3600;
const token=encode({alg:'HS256',typ:'JWT'})+'.'+encode({sub:uid,aud:'authenticated',exp,email:'maya@example.invalid'})+'.fixture-signature';
const user={id:uid,aud:'authenticated',role:'authenticated',email:'maya@example.invalid',email_confirmed_at:'2026-10-18T00:00:00Z',app_metadata:{provider:'email',providers:['email']},user_metadata:{},created_at:'2026-10-18T00:00:00Z',identities:[]};
const session={access_token:token,refresh_token:'fixture-refresh',token_type:'bearer',expires_in:3600,expires_at:exp,user};
const profile={profile_version:1,background:{subject:'Computer science',specialization:'Accessible web applications'},role_intents:[{raw_label:'Software developer',confirmed:true}],career_stage:'graduate',skills:[{label:'Python',source:'user'},{label:'SQL',source:'user'}],experience_summary:'Built a web application.',preferred_industries:[],certifications:[],location:{preferred_regions:['London'],relocate:true,strict:false},related_roles_enabled:false};
const rows=ids.map((id,index)=>({id,status:'ready',starred:index===0,created_at:'2026-10-18T10:00:00Z',access:index===1?'preview':'demo_unlocked',roles:[['Software engineering & web development','Water treatment & environmental engineering','Human resources'][index]]}));
const names=[['Workshop Digital','Cobalt Cloud','Northstar Software','Signal Labs'],['River Systems','Estuary Engineering','Waterworks Design'],[]];
const bookmarks=new Set();let failNext=false,processing=false,mutations=0;
function company(id,index) {
 const n=ids.indexOf(id),name=names[n][index], eid=`33333333-3333-4333-8333-${String(n*10+index+1).padStart(12,'0')}`;
 return {employer_id:eid,session_id:id,name,town:['London','Birmingham','Manchester','Leeds'][index],bookmarked:bookmarks.has(eid),group:'direct',explanation:{text:n===0?'Designs and develops software applications, cloud platforms and accessible web experiences. Its engineering services connect with your chosen skills.':'Designs water and wastewater treatment systems for industrial clients.',summary:n===0?'Software engineering, cloud platforms and accessible web applications.':'Water and wastewater treatment engineering.',basis:'activity',sources:[],skill_hits:[]},tags:[],channels:[{kind:'email',value:`careers@${name.toLowerCase().replaceAll(' ','')}.invalid`},{kind:'phone',value:'+44 20 0000 0000'},{kind:'website',value:'https://example.invalid',label:'Website'},{kind:'careers',value:'https://example.invalid/careers',label:'Careers'},{kind:'linkedin_company',value:'https://example.invalid/company',label:'LinkedIn'},{kind:'address',value:'10 Example Street, London'},{kind:'job_board',value:'https://example.invalid/jobs',label:'Indeed · job board'}],sponsor:{status:'register_authorized',snapshot_date:'2026-10-18'},verified_open_vacancies:[],is_demo:false,workplace_location_known:false};
}
http.createServer(async(req,res)=>{
 const url=new URL(req.url,host);let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
 const send=(code,value,delay=0)=>setTimeout(()=>{res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'private, no-store'});res.end(JSON.stringify(value));},delay);
 if(url.pathname==='/fixture/login'){res.writeHead(302,{'Set-Cookie':'sb-127-auth-token=base64-'+encode(session)+'; Path=/; HttpOnly; SameSite=Lax',Location:app+'/account'});return res.end();}
 if(url.pathname==='/fixture/fail-bookmark'){failNext=true;return send(200,{ok:true});}
 if(url.pathname==='/fixture/processing'){processing=!!body.active;return send(200,{ok:true});}
 if(url.pathname==='/fixture/metrics')return send(200,{mutations});
 const authenticated=req.headers.authorization==='Bearer '+token;
 if(url.pathname==='/auth/v1/user')return send(authenticated?200:401,authenticated?user:{message:'Invalid token'});
 if(url.pathname==='/api/account/identity')return send(200,{signed_in:authenticated});
 if(url.pathname==='/api/account/overview')return send(authenticated?200:401,{first_name:'Maya',profile,sessions:rows,bookmarks:ids.flatMap(id=>names[ids.indexOf(id)].map((_,index)=>company(id,index))).filter(c=>c.bookmarked)},250);
 if(url.pathname==='/api/account/profile')return send(200,{profile,account_key:'fixture'});
 if(url.pathname==='/api/catalogue/status')return send(200,{email_signin_available:true});
 if(url.pathname==='/api/profiles/normalize')return send(200,{role_intents:body.role_intents.map(r=>({...r,confirmed:true})),clarification:null});
 if(url.pathname==='/api/profiles/suggestions')return send(200,{suggestions:[],skill_suggestions:[],work_areas:[]});
 if(url.pathname.endsWith('/star')){mutations++;const row=rows.find(r=>url.pathname.includes(r.id));row.starred=body.saved;return send(200,{starred:body.saved},1200);}
 if(url.pathname.includes('/bookmarks/')){mutations++;if(failNext){failNext=false;return send(503,{detail:'Fixture save failure'},1500);}const eid=url.pathname.split('/').pop();body.saved?bookmarks.add(eid):bookmarks.delete(eid);return send(200,{bookmarked:body.saved},1200);}
 if(url.pathname.endsWith('/refresh')){mutations++;processing=true;return send(202,{session_id:ids.find(id=>url.pathname.includes(id)),status:'queued'},800);}
 if(url.pathname.endsWith('/demo-unlock')){mutations++;rows.find(r=>url.pathname.includes(r.id)).access='demo_unlocked';return send(200,{access:'demo_unlocked',charged:false},800);}
 if(url.pathname==='/api/feedback')return send(201,{saved:true});
 const id=ids.find(id=>url.pathname==='/api/matches/'+id);
 if(id){const row=rows.find(r=>r.id===id),all=names[ids.indexOf(id)].map((_,i)=>company(id,i));return send(200,{session_id:id,status:processing?'processing':'ready',stage:'Checking professional relevance',starred:row.starred,total_count:all.length,direct_count:all.length,locked_count:0,access:row.access,demo_price_gbp:19,preview:all,next_cursor:null,loading_context:{roles:row.roles,background:profile.background.subject,specialization:profile.background.specialization,skills:['Python','SQL'],locations:['London'],related_roles_enabled:false}},id===ids[0]?850:300);}
 return send(404,{detail:'Missing fixture endpoint'});
}).listen(9030,'127.0.0.1',()=>console.log('Synthetic UI fixture: '+host+'/fixture/login'));
