"""Private persistence bridge for the Node provider adapter. Never expose via the browser proxy."""
import os,hmac
from datetime import datetime,UTC,timedelta
from uuid import uuid4,UUID
from fastapi import HTTPException,Request
from psycopg.types.json import Jsonb
from .billing import Credits,lock_account

def stamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timezone required')
    return dt

def install_billing_gateway(app,db):
    @app.post('/api/internal/billing/{action}')
    def bridge(action:str,body:dict,request:Request):
        secret=os.getenv('BILLING_INTERNAL_SECRET','')
        if len(secret)<32 or not hmac.compare_digest(request.headers.get('x-billing-secret',''),secret):raise HTTPException(401,'Private billing service only')
        mode=body.get('environment')
        if mode not in ('test','live'):raise HTTPException(422,'Invalid environment')
        uid=body.get('user_id')
        if uid:
            try:UUID(uid)
            except ValueError:raise HTTPException(422,'Invalid account')
        if action=='run-start':
            source=body.get('source','scheduled')
            if source not in ('scheduled','manual'):raise HTTPException(422,'Invalid run source')
            actor=body.get('actor_id')
            if actor:
                try:UUID(actor)
                except (ValueError,TypeError):raise HTTPException(422,'Invalid actor')
            with db.transaction() as c:
                c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('reconcile:'+mode,))
                c.execute("update sm_private.reconciliation_runs set status='interrupted',finished_at=now(),error_code='lease_expired' where environment=%s and status='running' and lease_until<=now()",(mode,))
                existing=c.execute("select id,status from sm_private.reconciliation_runs where environment=%s and status='running'",(mode,)).fetchone()
                if existing:return {**existing,'acquired':False}
                run=c.execute("insert into sm_private.reconciliation_runs(id,environment,source,actor_id) values(%s,%s,%s,%s) returning id,status",(str(uuid4()),mode,source,actor)).fetchone()
                if actor:c.execute("insert into sm_private.admin_audit(id,actor_id,action,target_id) values(%s,%s,'reconciliation_run',%s)",(str(uuid4()),actor,run['id']))
                return {**run,'acquired':True}
        if action=='run-finish':
            state=body.get('status')
            if state not in ('complete','partial','failed'):raise HTTPException(422,'Invalid run outcome')
            errors=max(0,int(body.get('errors',0)));error=body.get('error')
            if state=='complete':
                pending=db.one("select (select count(*) from sm_private.billing_events where status='pending' and id like %s)+(select count(*) from sm_private.billing_checkouts where environment=%s and status='pending' and provider_session is null) n",(mode+':%',mode))['n']
                if pending:state='partial';error='verification_pending'
            db.execute("update sm_private.reconciliation_runs set status=%s,finished_at=now(),error_count=%s,error_code=%s where id=%s and environment=%s and status='running'",(state,errors,error,body['run_id'],mode))
            return {'saved':True,'status':state,'errors':errors}
        if action=='launch-status':
            fresh=db.one("select exists(select 1 from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' and publication_date between current_date-7 and current_date) ready")
            return {'research_ready':fresh['ready']}
        if action=='plans':
            return {'plans':db.rows('select * from sm_private.billing_plans where environment=%s order by amount_minor,slug',(mode,))}
        if action=='prepare':
            if not uid:raise HTTPException(401,'Account required')
            if mode=='live' and not db.one("select exists(select 1 from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' and publication_date between current_date-7 and current_date) ready")['ready']:raise HTTPException(503,'Company research is temporarily unavailable while its official source is refreshed')
            with db.transaction() as c:
                lock_account(c,uid)
                if c.execute("select 1 from sm_private.billing_subscriptions where user_id=%s and environment=%s and status not in ('canceled','incomplete_expired')",(uid,mode)).fetchone():raise HTTPException(409,'Manage your existing subscription before starting another')
                plan=c.execute('select * from sm_private.billing_plans where slug=%s and environment=%s and active',(body.get('plan','monthly'),mode)).fetchone()
                if not plan:raise HTTPException(404,'Plan not available')
                # An ambiguous provider create is reconciled using the same durable intent.
                old=c.execute("select * from sm_private.billing_checkouts where user_id=%s and environment=%s and status='pending' for update",(uid,mode)).fetchone()
                if old:
                    if old['plan_snapshot'].get('slug')!=plan['slug']:raise HTTPException(409,'Finish or cancel the existing checkout first')
                    return old
                return c.execute("insert into sm_private.billing_checkouts(id,user_id,environment,product_id,plan_snapshot) values(%s,%s,%s,%s,%s) returning *",(str(uuid4()),uid,mode,plan['product_id'],Jsonb(plan))).fetchone()
        if action=='bind':
            row=db.one('select * from sm_private.billing_checkouts where id=%s and user_id=%s and environment=%s',(body['intent_id'],uid,mode))
            if not row:raise HTTPException(404,'Checkout not found')
            if row['provider_session'] and row['provider_session']!=body['session_id']:raise HTTPException(409,'Checkout already bound')
            db.execute('update sm_private.billing_checkouts set provider_session=%s,checkout_url=%s,expires_at=%s where id=%s',(body['session_id'],body['url'],stamp(body['expires_at']),row['id']))
            return {'saved':True}
        if action=='context':
            if uid:
                return {'checkouts':db.rows('select * from sm_private.billing_checkouts where user_id=%s and environment=%s order by created_at desc limit 10',(uid,mode)),
                        'subscriptions':db.rows('select * from sm_private.billing_subscriptions where user_id=%s and environment=%s order by updated_at desc',(uid,mode)),
                        'payments':db.rows('select p.*,b.subscription_id,b.user_id,s.environment from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where b.user_id=%s and s.environment=%s order by p.paid_at desc',(uid,mode)),
                        'refunds':db.rows('select r.* from sm_private.refund_requests r join sm_private.billing_payments p on p.id=r.payment_id join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where r.user_id=%s and s.environment=%s order by r.created_at desc',(uid,mode))}
            return {'checkouts':db.rows("select * from sm_private.billing_checkouts where environment=%s and status='pending' order by created_at limit 100",(mode,)),
                    'subscriptions':db.rows('select * from sm_private.billing_subscriptions where environment=%s',(mode,)),
                    'refunds':db.rows("select r.* from sm_private.refund_requests r join sm_private.billing_payments p on p.id=r.payment_id join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where s.environment=%s and r.status='pending' order by r.created_at limit 50",(mode,))}
        if action=='checkout-status':
            db.execute('update sm_private.billing_checkouts set status=%s where provider_session=%s and environment=%s',(body['status'],body['session_id'],mode));return {'saved':True}
        if action=='subscription':
            sub=body['subscription']
            db.execute('update sm_private.billing_subscriptions set status=%s,cancel_at_period_end=%s,updated_at=now() where id=%s and environment=%s',(sub['status'],sub['cancelAtPeriodEnd'],sub['id'],mode))
            return {'saved':True}
        if action=='inbox':
            event=body['event'];event_id=body['event_id']
            db.execute('insert into sm_private.billing_events(id,payload) values(%s,%s) on conflict do nothing',(mode+':'+event_id,Jsonb(event)))
            return {'saved':True}
        if action=='events':return {'events':db.rows("select id,payload from sm_private.billing_events where status='pending' and id like %s order by created_at limit 50",(mode+':%',))}
        if action=='event-result':
            db.execute("update sm_private.billing_events set attempts=attempts+1,status=%s,error_code=%s,processed_at=case when %s then now() else null end where id=%s",('done' if body['success'] else 'pending',body.get('error'),body['success'],body['event_id']))
            return {'saved':True}
        if action=='managed':
            intent=body.get('intent_id')
            try:intent=str(UUID(intent)) if intent else None
            except (ValueError,TypeError,AttributeError):intent=None
            row=db.one('select user_id from sm_private.billing_checkouts where environment=%s and (provider_session=%s or id=%s::uuid)',(mode,body.get('session_id'),intent))
            if not row:row=db.one('select user_id from sm_private.billing_subscriptions where environment=%s and id=%s',(mode,body.get('subscription_id')))
            return {'managed':bool(row),'owner_matches':bool(row and (not uid or str(row['user_id'])==uid))}
        if action=='fulfil':
            plan=body['plan'];sub=body['subscription'];checkout=body['checkout'];payment=body['payment']
            initial=db.one('select * from sm_private.billing_checkouts where provider_session=%s and environment=%s',(checkout['sessionId'],mode))
            known=db.one('select * from sm_private.billing_subscriptions where id=%s and environment=%s',(sub['id'],mode))
            if initial:
                owner=str(initial['user_id']);expected=initial['plan_snapshot']
                if checkout.get('metadata',{}).get('customerId')!=owner or checkout.get('metadata',{}).get('checkoutIntentId')!=str(initial['id']):raise HTTPException(409,'Checkout correlation mismatch')
            elif known:
                owner=str(known['user_id']);expected=db.one('select * from sm_private.billing_plans where product_id=%s and environment=%s',(known['product_id'],mode))
                if not expected:raise HTTPException(409,'Subscription contract missing')
                if checkout.get('metadata',{}).get('subscriptionId')!=sub['id'] or not checkout.get('metadata',{}).get('subscriptionCycle'):raise HTTPException(409,'Renewal correlation mismatch')
            else:raise HTTPException(409,'Awaiting initial subscription correlation')
            if expected['product_id']!=sub['linkId'] or expected['credits']!=plan['credits'] or expected['currency']!=sub['currency'].upper() or expected['amount_minor']!=sub['unitAmountMinor']:raise HTTPException(409,'Plan mismatch')
            # Node has verified paid invoice, product, business, environment and period.
            fresh=Credits(db).record_verified_payment(user_id=owner,subscription_id=sub['id'],payment_id=payment['id'],invoice_id=payment['invoice_id'],starts_at=stamp(body['starts_at']),ends_at=stamp(body['ends_at']),environment=mode,product_id=sub['linkId'],allowance=expected['credits'],amount_minor=payment['amount_minor'],currency=payment['currency'],plan_snapshot=expected,provider_session=checkout['sessionId'],metadata=payment.get('metadata',{}),paid_at=stamp(payment['paid_at']) if payment.get('paid_at') else None,payment_state=payment.get('status','paid'))
            if initial:db.execute("update sm_private.billing_checkouts set status='completed' where id=%s",(initial['id'],))
            return {'granted':fresh,'user_id':owner}
        if action=='payment-state':
            payment=db.one('select p.*,b.user_id from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where p.id=%s and s.environment=%s',(body['payment_id'],mode))
            if not payment:return {'known':False}
            state=body['status']
            if state not in ('held','available','paid_out','paid','refunded','disputed','charged_back'):raise HTTPException(422,'Invalid payment state')
            stored='paid' if state in ('held','available','paid_out') else state
            db.execute('update sm_private.billing_periods set suspended=%s where id=%s',(state=='disputed',payment['period_id']))
            if state in ('refunded','charged_back'):
                Credits(db).revoke(payment['period_id'])
                db.execute("update sm_private.refund_requests set status='refunded' where payment_id=%s",(payment['id'],))
            db.execute("update sm_private.billing_payments set status=%s,metadata=jsonb_set(metadata,'{mor_status}',%s) where id=%s",(stored,Jsonb(state),payment['id']))
            return {'known':True}
        if action=='refund-prepare':
            p=db.one('select p.*,b.user_id,b.subscription_id,s.environment from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where p.id=%s and s.environment=%s',(body['payment_id'],mode))
            if not p or (not body.get('staff') and str(p['user_id'])!=uid):raise HTTPException(404,'Payment not found')
            if not body.get('staff'):
                first=db.one('select p.id from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where b.user_id=%s and s.environment=%s order by p.paid_at,p.id limit 1',(uid,mode))
                if first['id']!=p['id'] or datetime.now(UTC)-p['paid_at']>timedelta(days=14):raise HTTPException(409,'Contact support to review refund eligibility')
            if p['status'] in ('refunded','disputed','charged_back'):raise HTTPException(409,'This payment cannot be refunded here')
            with db.transaction() as c:
                lock_account(c,p['user_id'])
                row=c.execute('insert into sm_private.refund_requests(id,user_id,payment_id,reason) values(%s,%s,%s,%s) on conflict(payment_id) do update set payment_id=excluded.payment_id returning *',(str(uuid4()),p['user_id'],p['id'],str(body.get('reason',''))[:1000])).fetchone()
                if body.get('staff'):c.execute("insert into sm_private.admin_audit(id,actor_id,action,target_id) values(%s,%s,'refund_request',%s)",(str(uuid4()),uid,row['id']))
            return {'request':row,'payment':p}
        if action=='refund-decision':
            from .admin import staff_ids
            if uid not in staff_ids(os.getenv('SPONSORREACH_ADMIN_USER_IDS','')):raise HTTPException(403,'Administrator required')
            note=str(body.get('note','')).strip()
            if not note or len(note)>1000:raise HTTPException(422,'Record the provider decision and reference')
            with db.transaction() as c:
                r=c.execute('select r.* from sm_private.refund_requests r join sm_private.billing_payments p on p.id=r.payment_id join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where r.id=%s and s.environment=%s for update of r',(body['request_id'],mode)).fetchone()
                if not r:raise HTTPException(404,'Refund request not found')
                if r['status'] not in ('pending','requested','declined'):raise HTTPException(409,'Refund already completed')
                c.execute("update sm_private.refund_requests set status='declined',provider_note=%s where id=%s",('Provider decline recorded by authorised staff: '+note,r['id']))
                c.execute("insert into sm_private.admin_audit(id,actor_id,action,target_id) values(%s,%s,'refund_decline_recorded',%s)",(str(uuid4()),uid,r['id']))
            return {'status':'declined'}
        if action=='refund-status':
            db.execute('update sm_private.refund_requests set status=%s,provider_note=%s where id=%s',(body['status'],body.get('note'),body['request_id']));return {'saved':True}
        if action=='maintenance':
            Credits(db).release_abandoned()
            for p in db.rows('select id from sm_private.billing_periods where ends_at<=now() and not revoked'):
                Credits(db).revoke(p['id'],'expiry')
            # Recover free-preview reservations whose background work died.
            db.execute("update sm_private.billing_accounts a set preview_session=null from sm_private.match_sessions s where s.id=a.preview_session and s.status='failed'")
            return {'saved':True}
        if action=='sync-state':
            row=db.one("select * from sm_private.billing_sync where id='transactions'")
            if 'cursor' in body:db.execute("update sm_private.billing_sync set cursor=%s,last_success_at=case when %s then now() else last_success_at end,error_code=%s where id='transactions'",(body['cursor'],body.get('success',False) and not body.get('error'),body.get('error')))
            return row
        raise HTTPException(404,'Unknown billing operation')
