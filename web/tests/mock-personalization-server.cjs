// Local integration fixture only. Never included in application routes or enabled in production.
const http = require('node:http');
const id='11111111-1111-4111-8111-111111111111', sessionId='22222222-2222-4222-8222-222222222222';
const exp=Math.floor(Date.now()/1000)+3600;
const encode=value=>Buffer.from(JSON.stringify(value)).toString('base64url');
const token=encode({alg:'HS256',typ:'JWT'})+'.'+encode({sub:id,aud:'authenticated',exp,email:'maya@example.invalid'})+'.fixture-signature';
const user={id,aud:'authenticated',role:'authenticated',email:'maya@example.invalid',email_confirmed_at:'2026-10-18T00:00:00Z',confirmed_at:'2026-10-18T00:00:00Z',app_metadata:{provider:'email',providers:['email']},user_metadata:{},created_at:'2026-10-18T00:00:00Z',identities:[]};
const session={access_token:token,refresh_token:'fixture-refresh',token_type:'bearer',expires_in:3600,expires_at:exp,user};
const profile={profile_version:1,background:{subject:'Computer science',specialization:'Accessible web applications'},role_intents:[{raw_label:'Software developer',confirmed:true}],career_stage:'graduate',skills:[{label:'Python',source:'user'},{label:'SQL',source:'user'}],experience_summary:'Built a web application.',preferred_industries:['Software'],certifications:[],location:{preferred_regions:['London'],relocate:true,strict:false},related_roles_enabled:false};
let revoked=false;
http.createServer((req,res)=>{
 const url=new URL(req.url,'http://127.0.0.1:9010');
 if(url.pathname==='/fixture/login'){
  revoked=false;res.writeHead(302,{'Set-Cookie':'sb-127-auth-token=base64-'+encode(session)+'; Path=/; HttpOnly; SameSite=Lax',Location:'http://127.0.0.1:3010/'});return res.end();
 }
 const authenticated=req.headers.authorization==='Bearer '+token&&!revoked;
 const send=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'private, no-store'});res.end(JSON.stringify(value));};
 if(url.pathname==='/auth/v1/user')return send(authenticated?200:401,authenticated?user:{message:'Invalid token'});
 if(url.pathname==='/auth/v1/logout'){revoked=true;return send(200,{});}
 if(url.pathname==='/api/account/overview')return send(authenticated?200:401,authenticated?{first_name:'Maya',profile,sessions:[{id:sessionId,status:'ready',created_at:'2026-10-18T10:00:00Z',access:'preview',roles:['Software developer']}]}:{detail:'Sign in'});
 if(url.pathname==='/api/account/profile')return send(authenticated?200:401,authenticated?{profile,account_key:'fixture-maya'}:{detail:'Sign in'});
 if(url.pathname==='/api/account/identity')return send(200,{signed_in:authenticated});
 if(url.pathname==='/api/catalogue/status')return send(200,{email_signin_available:true});
 if(url.pathname==='/api/matches/history')return send(200,{sessions:[]});
 if(url.pathname==='/api/matches/'+sessionId)return send(200,{session_id:sessionId,status:'processing',stage:'Checking professional relevance',access:'preview',demo_price_gbp:19,loading_context:{roles:['Software developer'],background:'Computer science',specialization:'Accessible web applications',skills:['Python','SQL'],locations:['London'],related_roles_enabled:false}});
 return send(404,{detail:'Fixture endpoint missing'});
}).listen(9010,'127.0.0.1',()=>console.log('Fixture: http://127.0.0.1:9010/fixture/login (synthetic identity only)'));
