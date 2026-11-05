import 'server-only';
import {AsyncLocalStorage} from 'node:async_hooks';
const reconciliationSignal=new AsyncLocalStorage<AbortSignal>();
import {AgentaOS,type Checkout,type Subscription} from '@agentaos/pay';
import {apiBase,supabase,isAdministrator} from './server';
export type Plan={active:boolean;slug:string;name:string;product_id:string;amount_minor:number;currency:string;credits:number;interval:string;environment:string};
type Intent={id:string;user_id:string;provider_session:string|null;checkout_url:string|null;status:string;plan_snapshot:Plan;environment:string};
type StoredSubscription={id:string;user_id:string;product_id:string;status:string;environment:string};
type Payment={id:string;invoice_id:string;status:string;paid_at:string;amount_minor:number;currency:string;subscription_id:string;user_id:string};
export type Context={checkouts:Intent[];subscriptions:StoredSubscription[];payments:Payment[];refunds:{id:string;payment_id:string;status:string;user_id?:string}[]};
export class BillingError extends Error{constructor(message:string,public status=503){super(message);}}
export function environment(){const m=process.env.BILLING_MODE;if(m==='live'||m==='test')return m;return process.env.AGENTAOS_API_KEY?.startsWith('sk_live_')?'live':'test';}
export function provider(){reconciliationSignal.getStore()?.throwIfAborted();const key=process.env.AGENTAOS_API_KEY||'';if(!key.startsWith(environment()==='live'?'sk_live_':'sk_test_'))throw new BillingError('Payment provider credentials are unavailable');return new AgentaOS(key,{timeout:15000,maxRetries:0});}
export function checkoutEnabled(){return ['test','live'].includes(process.env.BILLING_MODE||'')&&process.env.BILLING_CHECKOUT_ENABLED==='true'&&!!process.env.AGENTAOS_API_KEY&&!!process.env.BILLING_INTERNAL_SECRET&&(environment()!=='live'||(process.env.BILLING_LIVE_APPROVED==='true'&&!!process.env.AGENTAOS_WEBHOOK_SECRET&&!!process.env.SPONSORMATCH_CONTROLLER_NAME&&!!process.env.SPONSORMATCH_OPERATOR_ADDRESS&&!!process.env.SPONSORMATCH_SUPPORT_EMAIL));}
export async function internal<T>(action:string,body:Record<string,unknown>={}):Promise<T>{
 reconciliationSignal.getStore()?.throwIfAborted();
 const secret=process.env.BILLING_INTERNAL_SECRET||'';if(secret.length<32)throw new BillingError('Billing service is not configured');
 const r=await fetch(apiBase()+'/api/internal/billing/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-API-Secret':process.env.SPONSORMATCH_API_SECRET||'','X-Billing-Secret':secret},body:JSON.stringify({...body,environment:environment()}),cache:'no-store',signal:AbortSignal.timeout(20000)});
 const result=await r.json();if(!r.ok)throw new BillingError(typeof result.detail==='string'?result.detail:'Billing request failed',r.status);return result;
}
export async function account(staff=false){const client=await supabase();const user=client?(await client.auth.getUser()).data.user:null;if(!user||!user.email_confirmed_at)throw new BillingError('Sign in to your verified account',401);
 if(staff&&!isAdministrator(user))throw new BillingError('Administrator access required',403);return user;}
export async function plans(includeArchived=false){const rows=(await internal<{plans:Plan[]}>('plans')).plans;return includeArchived?rows:rows.filter(p=>p.active&&p.currency==='USD'&&p.amount_minor===2499&&p.interval==='month'&&p.credits===800).slice(0,1);}
export async function context(uid?:string){return internal<Context>('context',uid?{user_id:uid}:{});}
async function subscriptions(){const all:Subscription[]=[];for(let offset=0;offset<10000;offset+=100){const p=await provider().subscriptions.list({limit:100,offset});all.push(...p.items);if(!p.hasMore)return all;}throw new BillingError('Subscription reconciliation exceeded its page limit');}
export async function startCheckout(uid:string,email:string,slug:string){if(!checkoutEnabled())throw new BillingError('Purchases are currently unavailable');
 if(environment()==='test'&&process.env.BILLING_TEST_CHECKOUT_PUBLIC!=='true'&&!(process.env.SPONSORREACH_ADMIN_USER_IDS||'').split(',').includes(uid))throw new BillingError('This test checkout is restricted to the administrator',403);
 if(!(await plans()).some(p=>p.slug===slug))throw new BillingError('The US$24.99 monthly subscription is not yet available');
 const i=await internal<Intent>('prepare',{user_id:uid,plan:slug});if(i.provider_session&&i.checkout_url){const old=await provider().checkouts.retrieve(i.provider_session);if(old.status==='open')return {sessionId:i.provider_session,checkoutUrl:i.checkout_url};await internal('checkout-status',{session_id:i.provider_session,status:old.status});if(old.status==='completed'){await confirmSession(i.provider_session,uid);throw new BillingError('Your payment is being confirmed. Refresh billing.',409);}return startCheckout(uid,email,slug);}
 const p=await provider().paymentLinks.retrieve(i.plan_snapshot.product_id);
 if(p.id!==i.plan_snapshot.product_id||p.type!=='subscription'||p.billingInterval!=='month'||Math.round(p.amount*100)!==i.plan_snapshot.amount_minor||!['USD','USDC'].includes(p.currency)||i.plan_snapshot.currency!=='USD'||i.plan_snapshot.amount_minor!==2499)throw new BillingError('The configured product does not match this plan');
 const origin=process.env.AGENTAOS_RETURN_ORIGIN||'';if(!origin.startsWith('https://'))throw new BillingError('A secure payment return address is required');
 const checkout=await provider().checkouts.create({linkId:p.id,buyerEmail:email,metadata:{customerId:uid,checkoutIntentId:i.id},successUrl:origin+'/account/billing',cancelUrl:origin+'/account/billing',...(process.env.AGENTAOS_WEBHOOK_SECRET?{webhookUrl:origin+'/api/payments/agentaos/webhook'}:{})},{idempotencyKey:i.id} as Parameters<AgentaOS['checkouts']['create']>[1]);
 await internal('bind',{intent_id:i.id,user_id:uid,session_id:checkout.sessionId,url:checkout.checkoutUrl,expires_at:checkout.expiresAt});return {sessionId:checkout.sessionId,checkoutUrl:checkout.checkoutUrl};
}
// Subscription state alone never creates credits; a completed checkout and paid invoice are required.
type Sale={id:string;orgId:string;status:string;sessionId:string|null;morStatus?:string;createdAt:string};
export async function confirmSession(sessionId:string,uid?:string,knownSale?:Sale){
 if(uid){const ctx=await context(uid);if(!ctx.checkouts.some(i=>i.provider_session===sessionId))throw new BillingError('Checkout not found',404);}
 const checkout=await provider().checkouts.retrieve(sessionId);
 if(checkout.orgId!==process.env.AGENTAOS_BUSINESS_ID)throw new BillingError('Payment business mismatch',409);
 if(checkout.status!=='completed'){await internal('checkout-status',{session_id:sessionId,status:checkout.status==='open'?'pending':checkout.status});return {status:checkout.status};}
 const subscriptionId=checkout.metadata?.subscriptionId;if(typeof subscriptionId!=='string'){if(!uid&&!checkout.metadata?.checkoutIntentId&&!checkout.metadata?.subscriptionCycle)return {status:'unmanaged'};throw new BillingError('Awaiting subscription details',409);}
 const managed=await internal<{managed:boolean;owner_matches:boolean}>('managed',{session_id:checkout.sessionId,subscription_id:subscriptionId,intent_id:checkout.metadata?.checkoutIntentId,...(uid?{user_id:uid}:{})});
 if(!managed.managed||!managed.owner_matches){if(!uid)return {status:'unmanaged'};throw new BillingError('Checkout not found',404);}
 const sub=(await subscriptions()).find(s=>s.id===subscriptionId);
 if(!sub||!sub.currentPeriodEnd)throw new BillingError('Awaiting subscription confirmation',409);
 const catalogue=await plans(true);const plan=catalogue.find(p=>p.product_id===sub.linkId);
 if(!plan&&!uid)return {status:'unmanaged'};
 if(!plan||sub.billingInterval!=='month'||sub.unitAmountMinor!==plan.amount_minor||sub.currency.toUpperCase()!==plan.currency)throw new BillingError('Payment plan mismatch',409);
 const invoices=await provider().subscriptions.invoices(sub.id);const paid=invoices.filter(i=>i.status==='paid').sort((a,b)=>Date.parse(b.issuedAt)-Date.parse(a.issuedAt));
 let invoice:typeof paid[number]|undefined,details:Awaited<ReturnType<AgentaOS['invoices']['retrieve']>>|undefined,sale:Sale|undefined;
 for(const candidate of paid){
  if(checkout.invoiceId&&candidate.id!==checkout.invoiceId)continue;
  if(candidate.currency.toUpperCase()!==plan.currency)continue;
  const record=await provider().invoices.retrieve(candidate.id);
  if(record.orgId!==process.env.AGENTAOS_BUSINESS_ID||!record.transactionId||record.fiatCurrency?.toUpperCase()!==plan.currency)continue;
  let transaction=knownSale?.id===record.transactionId?knownSale:undefined;
  if(!transaction){
   const from=new Date(Date.parse(candidate.issuedAt)-86400000).toISOString().slice(0,10);
   for(let offset=0;offset<2000;offset+=100){reconciliationSignal.getStore()?.throwIfAborted();const page=await provider().transactions.list({direction:'inbound',from,limit:100,offset});transaction=(page.items as Sale[]).find(t=>t.id===record.transactionId);if(transaction||!page.hasMore)break;}
  }
  // The transaction references the internal checkout UUID; return links use its public token.
  if(!transaction||![checkout.id,checkout.sessionId].filter(Boolean).includes(transaction.sessionId||''))continue;
  invoice=candidate;details=record;sale=transaction;break;
 }
 if(!invoice||!details||!sale)throw new BillingError('Awaiting paid invoice confirmation and verified payment settlement',409);
 const newer=paid.filter(i=>Date.parse(i.issuedAt)>Date.parse(invoice!.issuedAt)).at(-1);
 const periodEnd=newer?.issuedAt||sub.currentPeriodEnd;
 // Paid access begins at confirmed payment, never at an abandoned checkout's creation time.
 const periodStart=sale.createdAt;
 if(sub.status==='trialing'||sub.status==='incomplete'||sub.status==='incomplete_expired')throw new BillingError('A paid subscription is required',409);
 if(sale.orgId!==process.env.AGENTAOS_BUSINESS_ID||sale.status!=='confirmed'||!['held','available','paid_out','refunded','disputed','charged_back'].includes(sale.morStatus||''))throw new BillingError('Awaiting verified payment settlement',409);
 const paymentState=['held','available','paid_out'].includes(sale.morStatus!)?'paid':sale.morStatus;
 const amount=details.fiatAmount??details.amount;const gross=details.taxInclusive===false?amount+(details.taxAmount||0):amount;
 const result=await internal<{granted:boolean}>('fulfil',{plan,subscription:sub,checkout,starts_at:periodStart,ends_at:periodEnd,payment:{id:details.transactionId,invoice_id:invoice.id,amount_minor:Math.round(gross*100),currency:plan.currency,paid_at:sale.createdAt,status:paymentState,metadata:{invoice_number:invoice.invoiceNumber,mor_status:sale.morStatus}}});
 await internal('subscription',{subscription:sub});return {status:'completed',granted:result.granted};
}
export async function syncAccount(uid:string){let pending=false;const ctx=await context(uid);for(const i of ctx.checkouts.filter(i=>i.status==='pending'&&i.provider_session)){try{const state=await confirmSession(i.provider_session!,uid);if(state.status==='open')pending=true;}catch(e){if(e instanceof BillingError&&e.status===409)pending=true;else throw e;}}
 for(const sub of (ctx.subscriptions.length?await subscriptions():[]).filter(s=>ctx.subscriptions.some(old=>old.id===s.id)))await internal('subscription',{subscription:sub});return {...await context(uid),pending};}
export async function cancel(uid:string){const ctx=await context(uid);const active=ctx.subscriptions.filter(s=>!['canceled','incomplete_expired'].includes(s.status));for(const s of active){await provider().subscriptions.cancel(s.id,{atPeriodEnd:true});await internal('subscription',{subscription:{id:s.id,status:s.status,cancelAtPeriodEnd:true}});}return {scheduled:true};}
export async function requestRefund(uid:string,paymentId:string,reason:string,staff=false){
 const r=await internal<{request:{id:string;status:string};payment:Payment}>('refund-prepare',{user_id:uid,payment_id:paymentId,reason,staff});
 return submitSavedRefund(r.request,r.payment.user_id,paymentId);
}
async function submitSavedRefund(request:{id:string;status:string},userId:string,paymentId:string){
 if(['requested','refunded','declined'].includes(request.status))return {status:request.status};
 // Reconciliation retries the saved, authorised request even if the initial network call failed.
 await cancel(userId);
 const response=await fetch('https://api.agentaos.ai/api/v1/gateway/transactions/'+encodeURIComponent(paymentId)+'/refund-request',{method:'POST',headers:{'x-api-key':process.env.AGENTAOS_API_KEY!,'Content-Type':'application/json','Idempotency-Key':request.id},body:'{}',signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw new BillingError('Refund request could not be confirmed. It is saved for reconciliation.',502);
 const decision=await response.json() as {status?:string;note?:string};
 const status=decision.status==='executed'?'refunded':decision.status==='declined'?'declined':'requested';
 await internal('refund-status',{request_id:request.id,status,note:decision.note});
 if(status==='refunded')await internal('payment-state',{payment_id:paymentId,status:'refunded'});return {status};
}

export async function receipt(uid:string,invoiceId:string){const ctx=await context(uid);if(!ctx.payments.some(p=>p.invoice_id===invoiceId))throw new BillingError('Invoice not found',404);return provider().invoices.getReceipt(invoiceId);}

type Event={id?:string;business:string;type:string;data:Record<string,unknown>};
export async function processEvent(event:Event){if(event.business!==process.env.AGENTAOS_BUSINESS_ID||event.data.livemode!==(environment()==='live'))throw new BillingError('Webhook business or environment mismatch',400);
 if(event.type==='checkout.session.completed'){const id=event.data.sessionId;if(typeof id!=='string')throw new BillingError('Invalid checkout event',400);await confirmSession(id);}
 else if(event.type.startsWith('subscription.')){const current=(await subscriptions()).find(s=>s.id===event.data.id);if(current)await internal('subscription',{subscription:current});}
 // Refunds and disputes are reconciled from provider transaction state, never inferred from an old event.
}
async function reconcileWork(signal:AbortSignal){
 await internal('maintenance');const ctx=await context();let errors=0;
 for(const r of ctx.refunds||[]){reconciliationSignal.getStore()?.throwIfAborted();if(r.status==='pending'&&r.user_id){try{await submitSavedRefund(r,r.user_id,r.payment_id);}catch{errors++;}}}
 if(ctx.checkouts.some(i=>!i.provider_session)){
  for(let offset=0;offset<2000;offset+=100){reconciliationSignal.getStore()?.throwIfAborted();const page=await provider().checkouts.list({limit:100,offset});
   for(const remote of page.items){const i=ctx.checkouts.find(i=>!i.provider_session&&remote.metadata?.checkoutIntentId===i.id&&remote.metadata?.customerId===i.user_id);if(i){await internal('bind',{intent_id:i.id,user_id:i.user_id,session_id:remote.sessionId,url:remote.checkoutUrl,expires_at:remote.expiresAt});i.provider_session=remote.sessionId;}}
   if(!page.hasMore)break;
  }
 }
 for(const i of ctx.checkouts){reconciliationSignal.getStore()?.throwIfAborted();if(!i.provider_session)continue;try{await confirmSession(i.provider_session);}catch{errors++;}}
 for(const s of (await subscriptions()).filter(s=>ctx.subscriptions.some(old=>old.id===s.id)))await internal('subscription',{subscription:s});
 const events=await internal<{events:{id:string;payload:Event}[]}>('events');for(const e of events.events){try{await processEvent(e.payload);await internal('event-result',{event_id:e.id,success:true});}catch{errors++;await internal('event-result',{event_id:e.id,success:false,error:'provider_sync_failed'});}}
 const checkpoint=await internal<{cursor:number}>('sync-state');let offset=checkpoint.cursor;
 // Bounded scan resumes at the durable cursor; full history includes old refunds and chargebacks.
 for(let page=0;page<5;page++){reconciliationSignal.getStore()?.throwIfAborted();
  const tx=await provider().transactions.list({direction:'inbound',limit:100,offset});
  for(const raw of tx.items){const t=raw as typeof raw&{morStatus?:string;refundRequestStatus?:string;refundRequestNote?:string};
   if(t.status==='confirmed'&&t.sessionId){try{await confirmSession(t.sessionId,undefined,t);}catch{errors++;}}
   if(t.morStatus)await internal('payment-state',{payment_id:t.id,status:t.morStatus});
  }
  offset=tx.hasMore?offset+100:0;await internal('sync-state',{cursor:offset,success:!tx.hasMore,error:errors?'sync_items_pending':null});if(!tx.hasMore)break;
 }
 return {errors,complete:offset===0};
}
export async function salesAvailable(){if(!checkoutEnabled())return false;if(!(await plans()).length)return false;if(environment()==='test')return true;return (await internal<{research_ready:boolean}>('launch-status')).research_ready;}
export async function commercialOffer(){const creditMode=['test','live'].includes(process.env.BILLING_MODE||'')||process.env.BILLING_ENFORCE_CREDITS==='true';let catalogue:Plan[]=[];if(creditMode){try{catalogue=await plans();}catch{}}return {creditMode,enabled:await salesAvailable(),catalogue};}

export async function reconcile(source:'scheduled'|'manual'='scheduled',actorId?:string){
 const run=await internal<{id:string;acquired:boolean}>('run-start',{source,actor_id:actorId});
 if(!run.acquired)return {run_id:run.id,status:'running',errors:0};
 const signal=AbortSignal.timeout(180000);
 try{const result=await reconciliationSignal.run(signal,()=>reconcileWork(signal));const status=result.errors||!result.complete?'partial':'complete';const outcome=await internal<{status?:string}>('run-finish',{run_id:run.id,status,errors:result.errors,error:result.errors?'sync_items_pending':!result.complete?'scan_in_progress':null});return {...result,run_id:run.id,status:outcome.status||status};}
 catch(error){await internal('run-finish',{run_id:run.id,status:'failed',errors:1,error:'provider_sync_failed'});throw error;}
}
