'use client';
import {useCallback,useEffect,useState} from 'react';
import Link from '@/components/navigation-link';
import {DataValue,DataRows} from './data-placeholder';
import {refreshCredits} from './dashboard-shell';
import {api} from '@/lib/types';
type Period={id:string;starts_at:string;ends_at:string;allowance:number;plan_snapshot?:{name?:string}};
type Summary={signup_credits?:number;available:number;reserved:number;monthly_credits:number;period:Period|null;periods:Period[];subscription:{status:string;cancel_at_period_end:boolean;period_end:string}|null};
type Plan={slug:string;name:string;credits:number;amount_minor:number;currency:string;environment:string};
type Day={day:string;searches:number;batches:number};
type Entry={id:string;created_at:string;kind:string;delta:number;session_id:string|null};
type Payment={id:string;invoice_id:string;status:string;amount_minor:number;currency:string;paid_at:string};
type Refund={id:string;payment_id:string;status:string};
const date=(s:string)=>new Date(s).toLocaleDateString('en-GB',{dateStyle:'medium',timeZone:'UTC'});
const money=(n:number,currency:string)=>new Intl.NumberFormat('en-GB',{style:'currency',currency}).format(n/100);
export default function Billing(){
 const [summary,setSummary]=useState<Summary|null>(null),[period,setPeriod]=useState(''),[days,setDays]=useState<Day[]>([]),[entries,setEntries]=useState<Entry[]>([]),[offset,setOffset]=useState(0),[error,setError]=useState(''),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[catalogue,setCatalogue]=useState<Plan[]>([]),[enabled,setEnabled]=useState(false),[payments,setPayments]=useState<Payment[]>([]),[refunds,setRefunds]=useState<Refund[]>([]),[busy,setBusy]=useState(false),[pending,setPending]=useState(false),[checkout,setCheckout]=useState(''),[revision,setRevision]=useState(0),[cancelConfirm,setCancelConfirm]=useState(false),[refundId,setRefundId]=useState(''),[refundConfirm,setRefundConfirm]=useState(false);
 const [plansLoading,setPlansLoading]=useState(true),[recordsLoading,setRecordsLoading]=useState(true),[usageLoading,setUsageLoading]=useState(true),[historyLoading,setHistoryLoading]=useState(true);
 const refresh=useCallback(async()=>{const s=await api<Summary>('account/billing');setSummary(s);refreshCredits();setPeriod(p=>p||s.periods[0]?.id||'signup');},[]);
 const sync=useCallback(async()=>{const r=await api<{payments:Payment[];refunds:Refund[];pending:boolean}>('billing/sync',{method:'POST',body:'{}'});setPayments(r.payments);setRefunds(r.refunds);setPending(r.pending);await refresh();setRevision(n=>n+1);},[refresh]);
 useEffect(()=>{let active=true;const c=new AbortController();
  api<Summary>('account/billing',{signal:c.signal}).then(s=>{if(active){setSummary(s);setPeriod(p=>p||s.periods[0]?.id||'signup');}}).catch(e=>{if(active&&!c.signal.aborted)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
  api<{plans:Plan[];enabled:boolean}>('billing/plans',{signal:c.signal}).then(r=>{if(active){setCatalogue(r.plans);setEnabled(r.enabled);}}).catch(e=>{if(active&&!c.signal.aborted)setError(e.message);}).finally(()=>{if(active)setPlansLoading(false);});
  if(new URLSearchParams(window.location.search).has('sessionId')){sync().catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setRecordsLoading(false);});}
  else api<{payments:Payment[];refunds:Refund[];pending:boolean}>('billing/records',{signal:c.signal}).then(r=>{if(active){setPayments(r.payments);setRefunds(r.refunds);setPending(r.pending);}}).catch(e=>{if(active&&!c.signal.aborted)setError(e.message);}).finally(()=>{if(active)setRecordsLoading(false);});
  return()=>{active=false;c.abort();};},[sync]);
 useEffect(()=>{if(!pending)return;const timer=setTimeout(()=>sync().catch(e=>setError(e.message)),6000);return()=>clearTimeout(timer);},[pending,revision,sync]);
 useEffect(()=>{let active=true;if(summary){setUsageLoading(true);api<{days:Day[]}>('account/usage'+(period?'?period_id='+period:'')).then(r=>{if(active)setDays(r.days);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setUsageLoading(false);});}return()=>{active=false;};},[period,!!summary,revision]);
 useEffect(()=>{let active=true;setHistoryLoading(true);api<{entries:Entry[]}>('account/credit-history?offset='+offset).then(r=>{if(active)setEntries(r.entries);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setHistoryLoading(false);});return()=>{active=false;};},[offset,revision]);
 async function action(path:string,body:Record<string,unknown>,message:string){setBusy(true);setError('');try{const r=await api<{checkoutUrl?:string;status?:string}>(path,{method:'POST',body:JSON.stringify(body)});if(r.checkoutUrl){setCheckout(r.checkoutUrl);setPending(true);window.location.assign(r.checkoutUrl);return;}setNotice(r.status==='declined'?'The provider declined this refund request. Please contact support.':message);await sync();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const used=days.reduce((n,d)=>n+Number(d.searches)+Number(d.batches),0),max=Math.max(1,...days.map(d=>Number(d.searches)+Number(d.batches)));
 const view=summary;
 const subscription=view?.subscription;
 const canCancel=subscription&&!['canceled','incomplete_expired'].includes(subscription.status)&&!subscription.cancel_at_period_end;
 const creditLabels:Record<string,string>={grant:'Credits added',search:'Sponsor search',batch:'Results batch',spend:'Credit used',expiry:'Credits expired',refund:'Credits refunded'};
 const displayedPlans=catalogue.length?catalogue:[{slug:'',name:'SponsorReach Monthly',credits:100,amount_minor:2499,currency:'EUR',environment:''}];
 const firstPayment=payments.at(-1),eligible=firstPayment&&Date.now()-Date.parse(firstPayment.paid_at)<=14*86400000;
 return <section className="shell billing-shell member-billing">
 <h1>Credits &amp; billing</h1>
 {error&&<p className="error" role="alert">{error} <Link href="/account/support">Get support</Link></p>}
 {notice&&<p className="notice" role="status">{notice}</p>}
 <div className="billing-overview">
   <article><span>Available now</span><strong><DataValue loading={loading} label="available credits">{view?.available??'—'}</DataValue></strong><small><DataValue loading={loading} label="reserved credits">{view?.reserved??'—'}</DataValue> reserved for searches</small></article>
   <article><span>Subscription</span><strong className="billing-status"><DataValue loading={loading} label="subscription status">{view?(subscription?.status.replaceAll('_',' ')||'No subscription'):'—'}</DataValue></strong><small><DataValue loading={loading} label="billing period">{view?.period?`${subscription?.cancel_at_period_end?'Access ends':'Current period ends'} ${date(view.period.ends_at)}`:view?'No paid billing period':'—'}</DataValue></small></article>
   <article><span>Period allowance</span><strong><DataValue loading={loading} label="period allowance">{view?.monthly_credits??'—'}</DataValue></strong><small>Unused credits expire each paid month</small></article>
 </div>
 {subscription&&['past_due','unpaid','incomplete'].includes(subscription.status)&&<p className="notice">Your latest payment needs attention. Follow the instructions from AgentaOS or <Link href="/account/support">contact support</Link>.</p>}
 {displayedPlans.map(p=><article className="billing-section billing-plan" key={p.slug}>
   <div><h2>{p.name}</h2><p><strong>{money(p.amount_minor,p.currency)} / month</strong> · {p.credits} credits per paid month</p><small>Renews monthly. Checkout shows any applicable tax before payment.</small></div>
   <div className="billing-plan-action">{p.environment==='test'&&<small>Test payments only</small>}
   {(!subscription||['canceled','incomplete_expired'].includes(subscription.status))&&<button className="button small" disabled={!enabled||!p.slug||!summary||busy} onClick={()=>action('billing/checkout',{plan:p.slug},'Checkout ready.')}>Subscribe for {money(p.amount_minor,p.currency)}/month</button>}
   {!plansLoading&&!enabled&&<small>New purchases are currently unavailable.</small>}</div>
 </article>)}
 {checkout&&<p><a className="button" href={checkout} target="_blank" rel="noopener noreferrer">Open secure checkout ↗</a></p>}
 {pending&&<p role="status">Waiting for payment confirmation.</p>}
 <section className="billing-section">
   <header className="billing-section-heading"><div><h2>Research activity</h2><p><DataValue loading={usageLoading&&!!summary||loading} label="credits used">{summary?used:'—'}</DataValue> credits used</p></div>
   <label htmlFor="billing-period">Billing period (UTC)<select id="billing-period" value={period||'signup'} disabled={loading} onChange={e=>setPeriod(e.target.value)}><option value="signup">Signup credit activity</option>{view?.periods.map(p=><option key={p.id} value={p.id}>{date(p.starts_at)} – {date(p.ends_at)}</option>)}</select></label></header>
   {loading||summary&&usageLoading?<DataRows label="credit usage"/>:!summary?<p className="billing-empty">Research activity is temporarily unavailable.</p>:days.length?<><div className="usage-bars" aria-hidden="true">{days.map(d=><div className="usage-day" key={d.day}><div className="usage-stack" style={{height:`${(Number(d.searches)+Number(d.batches))/max*75}px`}}><span style={{flex:Number(d.batches)}}/><span style={{flex:Number(d.searches)}}/></div><small>{new Date(d.day).getUTCDate()}</small></div>)}</div><div className="billing-table"><table aria-label="Daily credit usage"><thead><tr><th>Date</th><th>Searches</th><th>Additional batches</th></tr></thead><tbody>{days.map(d=><tr key={d.day}><th scope="row">{date(d.day)}</th><td>{d.searches}</td><td>{d.batches}</td></tr>)}</tbody></table></div></>:<p className="billing-empty">No research activity in this period.</p>}
 </section>
 <section className="billing-section">
   <header className="billing-section-heading"><h2>Payments and receipts</h2><button className="text-button" disabled={busy} onClick={()=>{setBusy(true);sync().catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Refresh payment status</button></header>
   {recordsLoading?<DataRows label="payments"/>:!payments.length?<p className="billing-empty">No confirmed payments yet.</p>:<div className="billing-table"><table><thead><tr><th>Date</th><th>Amount</th><th>Status</th><th>Receipt</th></tr></thead><tbody>{payments.map(p=><tr key={p.id}><td>{date(p.paid_at)}</td><td className="billing-amount">{money(p.amount_minor,p.currency)}</td><td><span className="billing-payment-status">{p.status.replaceAll('_',' ')}</span></td><td><a href={'/api/billing/receipt?invoice='+encodeURIComponent(p.invoice_id)}>Download PDF</a></td></tr>)}</tbody></table></div>}
 </section>
 <section className="billing-section">
   <header className="billing-section-heading"><h2>Credit history</h2></header>
   {historyLoading?<DataRows label="credit history"/>:entries.length?<div className="billing-table"><table aria-label="Credit history"><thead><tr><th>Date (UTC)</th><th>Activity</th><th>Credits</th><th>Research</th></tr></thead><tbody>{entries.map(e=><tr key={e.id}><td>{date(e.created_at)}</td><td>{creditLabels[e.kind]||e.kind.replaceAll('_',' ')}</td><td className="billing-amount">{e.delta>0?'+':''}{e.delta}</td><td>{e.session_id?<Link href={'/account/shortlists?shortlist='+e.session_id}>Open shortlist</Link>:'—'}</td></tr>)}</tbody></table></div>:<p className="billing-empty">No credit activity yet.</p>}
   {(offset>0||entries.length===20)&&<div className="billing-pagination"><button className="text-button" disabled={historyLoading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-20))}>Previous</button><button className="text-button" disabled={historyLoading||entries.length<20} onClick={()=>setOffset(n=>n+20)}>Next</button></div>}
 </section>
 <p className="billing-credit-note">A search or an additional batch of up to 5 companies may use 1 credit. Empty and mostly repeated batches are free.</p>
 <footer className="billing-management">
   {refunds.map(r=><p key={r.id}>Refund request: {r.status}</p>)}
   <details><summary>Refunds</summary>
     <p>The 14-day refund promise applies to the first subscription payment, including after some credit use. Your statutory rights remain unaffected.</p>
     {eligible&&firstPayment&&firstPayment.status!=='refunded'&&<>
       <label><input type="checkbox" checked={refundConfirm} onChange={e=>{setRefundConfirm(e.target.checked);if(!e.target.checked)setRefundId('');}}/> Request a first-payment refund and cancel renewal</label>
       <button className="text-button" disabled={busy||!refundConfirm} onClick={()=>setRefundId(firstPayment.id)}>Review refund request</button>
       {refundId&&<div><p>AgentaOS reviews this request. Confirmed refunds remove unused credits from the affected period.</p><button className="button secondary small" disabled={busy||!refundConfirm} onClick={()=>action('billing/refund',{payment_id:refundId,confirm_cancel:true,reason:'First-payment voluntary refund request'},'Refund requested. Future renewal has been cancelled.')}>Submit refund and cancel renewal</button></div>}
     </>}
     <Link href="/account/support">Get help with a payment</Link>
   </details>
   {canCancel&&<details><summary>Cancel renewal</summary>
     <p>Your paid allowance is available until the current period ends.</p>
     <label><input type="checkbox" checked={cancelConfirm} onChange={e=>setCancelConfirm(e.target.checked)}/> Stop future automatic renewal</label>
     <button className="button secondary small" disabled={busy||!cancelConfirm} onClick={()=>action('billing/cancel',{},'Renewal cancellation scheduled.')}>Confirm cancellation</button>
   </details>}
 </footer>
 </section>;
}
