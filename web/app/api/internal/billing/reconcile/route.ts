import {NextResponse} from 'next/server';
import {timingSafeEqual} from 'node:crypto';
import {reconcile} from '@/lib/billing-server';
export const runtime='nodejs';
export async function POST(request:Request){
 const secret=process.env.BILLING_RECONCILE_SECRET||'',provided=request.headers.get('authorization')||'';
 const expected='Bearer '+secret;
 if(secret.length<32||Buffer.byteLength(expected)!==Buffer.byteLength(provided)||!timingSafeEqual(Buffer.from(provided),Buffer.from(expected)))return NextResponse.json({error:'Unauthorized'},{status:401});
 try{return NextResponse.json(await reconcile(),{headers:{'Cache-Control':'no-store'}});}catch{return NextResponse.json({error:'Reconciliation failed'},{status:503});}
}
