import {NextResponse} from 'next/server';
import {supabase,sameOrigin} from '@/lib/server';
export async function POST(request:Request){
 if(!sameOrigin(request))return NextResponse.json({error:'Invalid origin'},{status:403});
 if(!request.headers.get('content-type')?.includes('application/json'))return NextResponse.json({error:'JSON required'},{status:415});
 const email=process.env.SPONSORREACH_ADMIN_EMAIL?.trim().toLowerCase();
 const ids=new Set((process.env.SPONSORREACH_ADMIN_USER_IDS||'').split(',').map(v=>v.trim()).filter(Boolean));
 if(!email||ids.size!==1)return NextResponse.json({error:'The administrator account must be configured before sign-in.'},{status:503});
 const client=await supabase();if(!client)return NextResponse.json({error:'Sign-in is unavailable.'},{status:503});
 try{
  const raw=await request.text();if(raw.length>2500)return NextResponse.json({error:'Invalid credentials'},{status:400});
  const body=JSON.parse(raw);
  if(typeof body.email!=='string'||body.email.trim().toLowerCase()!==email||typeof body.password!=='string'||!body.password||body.password.length>1024)return NextResponse.json({error:'Unable to sign in with those credentials.'},{status:401});
  const {data,error}=await client.auth.signInWithPassword({email,password:body.password});
  if(error||!data.user||!ids.has(data.user.id)||!data.user.email_confirmed_at){
   if(data.session)await client.auth.signOut();
   return NextResponse.json({error:'Unable to sign in with those credentials.'},{status:401});
  }
  return NextResponse.json({signed_in:true},{headers:{'Cache-Control':'private, no-store'}});
 }catch{return NextResponse.json({error:'Unable to sign in. Please try again.'},{status:400});}
}
