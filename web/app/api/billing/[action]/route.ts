import {NextResponse} from 'next/server';
import {account,plans,salesAvailable,startCheckout,syncAccount,context,cancel,requestRefund,receipt,BillingError} from '@/lib/billing-server';
import {sameOrigin} from '@/lib/server';
export const runtime='nodejs';
export const dynamic='force-dynamic';
async function handle(request:Request,ctx:{params:Promise<{action:string}>}){
 try{
  const {action}=await ctx.params;
  if(request.method==='GET'&&action==='plans')return NextResponse.json({plans:await plans(),enabled:await salesAvailable()},{headers:{'Cache-Control':'no-store'}});
  const user=await account();
  if(request.method==='GET'&&action==='records'){const stored=await context(user.id);return NextResponse.json({payments:stored.payments,refunds:stored.refunds,pending:stored.checkouts.some(c=>c.status==='pending')},{headers:{'Cache-Control':'private, no-store'}});}
  if(request.method==='GET'&&action==='receipt'){
   const id=new URL(request.url).searchParams.get('invoice');if(!id||id.length>120)throw new BillingError('Invoice not found',404);
   const pdf=await receipt(user.id,id);return new NextResponse(new Uint8Array(pdf),{headers:{'Content-Type':'application/pdf','Content-Disposition':'attachment; filename="receipt.pdf"','Cache-Control':'private, no-store'}});
  }
  if(request.method!=='POST')return NextResponse.json({error:'Not found'},{status:404});
  if(!sameOrigin(request)||!request.headers.get('content-type')?.includes('application/json'))throw new BillingError('Invalid request origin or format',403);
  const raw=await request.text();if(raw.length>3000)throw new BillingError('Request too large',413);const body=JSON.parse(raw);
  let result;
  if(action==='checkout'){
   if(typeof body.plan!=='string'||!/^[a-z0-9-]{1,60}$/.test(body.plan))throw new BillingError('Choose a plan',422);
   result=await startCheckout(user.id,user.email!,body.plan);
  }else if(action==='sync')result=await syncAccount(user.id);
  else if(action==='cancel')result=await cancel(user.id);
  else if(action==='refund'){
   if(typeof body.payment_id!=='string'||body.payment_id.length>100||body.confirm_cancel!==true)throw new BillingError('Confirm cancellation with your refund request',422);
   result=await requestRefund(user.id,body.payment_id,String(body.reason||'').slice(0,1000));
  }else throw new BillingError('Not found',404);
  return NextResponse.json(result,{headers:{'Cache-Control':'private, no-store'}});
 }catch(e){return NextResponse.json({error:e instanceof BillingError?e.message:'The payment provider could not complete this step. Please retry.'},{status:e instanceof BillingError?e.status:502,headers:{'Cache-Control':'private, no-store'}});}
}
export const POST=handle;export const GET=handle;
