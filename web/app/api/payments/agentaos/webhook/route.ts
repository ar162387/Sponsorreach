import {NextResponse} from 'next/server';
import {createHash} from 'node:crypto';
import {provider,internal,environment} from '@/lib/billing-server';
export const runtime='nodejs';
export async function POST(request:Request){
 const secret=process.env.AGENTAOS_WEBHOOK_SECRET;if(!secret)return NextResponse.json({error:'Webhook not configured'},{status:503});
 const raw=await request.text();if(raw.length>100000)return NextResponse.json({error:'Payload too large'},{status:413});
 let event;
 try{event=provider().webhooks.verify(raw,request.headers.get('x-agentaos-signature')||'',secret) as unknown as {id?:string;business:string;type:string;data:{livemode?:boolean}};}
 catch{return NextResponse.json({error:'Invalid signature or payload'},{status:400});}
 if(event.business===process.env.AGENTAOS_BUSINESS_ID&&event.type==='account.updated')return NextResponse.json({received:true});
 if(event.business!==process.env.AGENTAOS_BUSINESS_ID||event.data?.livemode!==(environment()==='live'))return NextResponse.json({error:'Unexpected business or environment'},{status:400});
 try{await internal('inbox',{event_id:event.id||createHash('sha256').update(raw).digest('hex'),event});return NextResponse.json({received:true},{status:202});}
 catch{return NextResponse.json({error:'Unable to persist webhook; retry delivery'},{status:503});}
}
