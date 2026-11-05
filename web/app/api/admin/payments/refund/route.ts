import {NextResponse} from 'next/server';
import {account,requestRefund,BillingError} from '@/lib/billing-server';
import {sameOrigin} from '@/lib/server';
export async function POST(request:Request){
 try{if(!sameOrigin(request))throw new BillingError('Invalid origin',403);const actor=await account(true);const raw=await request.text();if(raw.length>2000)throw new BillingError('Request too large',413);const body=JSON.parse(raw);
 if(typeof body.payment_id!=='string'||body.payment_id.length>100||typeof body.reason!=='string'||!body.reason.trim()||body.confirm_cancel!==true)throw new BillingError('A payment, reason and cancellation confirmation are required',422);
 return NextResponse.json(await requestRefund(actor.id,body.payment_id,body.reason.slice(0,1000),true),{headers:{'Cache-Control':'private, no-store'}});
 }catch(e){return NextResponse.json({error:e instanceof BillingError?e.message:'Provider refund request could not be confirmed'},{status:e instanceof BillingError?e.status:502});}
}
