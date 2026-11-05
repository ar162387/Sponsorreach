"""Read-only, staff-authorized workspace projections. No provider calls on GET."""
import os
from uuid import UUID
from fastapi import HTTPException, Request
from .billing import Credits,credit_environment


def install_dashboard(app, db, admin):
    def health():
        mode=credit_environment()
        return {'environment':mode,'last_run':db.one('select id,status,started_at,finished_at,error_count,error_code,source from sm_private.reconciliation_runs where environment=%s order by started_at desc limit 1',(mode,)),
                'last_success_at':(db.one("select max(finished_at) stamp from sm_private.reconciliation_runs where environment=%s and status='complete'",(mode,)) or {}).get('stamp')}

    @app.get('/api/admin/dashboard/health')
    def get_health(request:Request):
        admin(request)
        return health()

    @app.get('/api/admin/dashboard/summary')
    def summary(request:Request):
        admin(request)
        data=health();mode=data['environment']
        data['counts']=db.one("""select
          (select count(*) from sm_private.billing_accounts) members,
          (select count(*) from sm_private.support_tickets where status='open') open_tickets,
          (select count(*) from sm_private.billing_checkouts where environment=%s and status='pending') pending_checkouts,
          (select count(*) from sm_private.billing_events where status<>'done' and id like %s) pending_events,
          (select count(*) from sm_private.refund_requests r join sm_private.billing_payments p on p.id=r.payment_id join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where s.environment=%s and r.status in ('pending','requested')) pending_refunds""",(mode,mode+':%',mode))
        return data

    @app.get('/api/admin/dashboard/members/{uid}')
    def member(uid:UUID,request:Request):
        admin(request)
        account=db.one('select user_id,created_at from sm_private.billing_accounts where user_id=%s',(uid,))
        if not account:raise HTTPException(404,'Member not found')
        profile=db.one("select identity->>'first_name' first_name from sm_private.candidate_profiles where user_id=%s order by created_at desc limit 1",(uid,))
        return {'account':account,'profile':profile,'balance':Credits(db).summary(str(uid)),
                'shortlists':db.rows('select id,status,created_at from sm_private.match_sessions where user_id=%s order by created_at desc limit 25',(uid,)),
                'payments':db.rows('select p.id,p.amount_minor,p.currency,p.status,p.paid_at,s.environment from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where b.user_id=%s order by p.paid_at desc limit 25',(uid,)),
                'tickets':db.rows('select id,subject,status,updated_at from sm_private.support_tickets where user_id=%s order by updated_at desc limit 25',(uid,))}

    @app.get('/api/admin/dashboard/{resource}')
    def records(resource:str,request:Request,offset:int=0,q:str='',status:str='',environment:str='',start:str='',end:str=''):
        admin(request)
        if not 0<=offset<=100000 or len(q)>160 or len(status)>60 or environment not in ('','all','test','live','signup'):raise HTTPException(422,'Invalid filter')
        # Fixed projections exclude raw webhook payloads, credentials and profile documents.
        sources={
          'members':("select a.user_id::text id,a.user_id,a.created_at,coalesce(p.identity->>'first_name','Member') name from sm_private.billing_accounts a left join lateral (select identity from sm_private.candidate_profiles where user_id=a.user_id order by created_at desc limit 1) p on true",'created_at',False),
          'payments':('select p.id,b.user_id,p.amount_minor,p.currency,p.status,p.paid_at,s.environment from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id','paid_at',True),
          'refunds':('select r.id,r.user_id,r.payment_id,r.status,r.created_at,s.environment from sm_private.refund_requests r join sm_private.billing_payments p on p.id=r.payment_id join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id','created_at',True),
          'credits':("select l.id,l.user_id,l.delta,l.kind,l.created_at,coalesce(s.environment,'signup') environment,l.session_id from sm_private.credit_ledger l left join sm_private.billing_periods b on b.id=l.period_id left join sm_private.billing_subscriptions s on s.id=b.subscription_id",'created_at',True),
          'support':('select id,user_id,subject,status,created_at,updated_at from sm_private.support_tickets','updated_at',False),
          'checkouts':('select id,user_id,status,created_at,environment,provider_session is not null provider_bound from sm_private.billing_checkouts','created_at',True),
          'events':("select id,status,attempts,created_at,error_code,split_part(id,':',1) environment from sm_private.billing_events",'created_at',True),
          'runs':('select id,status,started_at,finished_at,error_count,error_code,source,environment from sm_private.reconciliation_runs','started_at',True),
          'reservations':("select r.id,r.user_id,r.session_id,r.units,r.state status,r.expires_at,coalesce(s.environment,'signup') environment from sm_private.credit_reservations r left join sm_private.billing_periods b on b.id=r.period_id left join sm_private.billing_subscriptions s on s.id=b.subscription_id",'expires_at',True),
          'issues':("select p.id,b.user_id,p.status,p.paid_at,s.environment,'Paid period has no credit grant' issue from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id where p.status='paid' and not b.revoked and not exists(select 1 from sm_private.credit_ledger l where l.period_id=b.id and l.kind='grant')",'paid_at',True),
        }
        if resource not in sources:raise HTTPException(404,'View not found')
        source,date_col,has_mode=sources[resource];clauses=[];args=[]
        if q:clauses.append('row_to_json(v)::text ilike %s');args.append('%'+q+'%')
        state_col='kind' if resource=='credits' else 'status'
        if status and resource not in ('members',):clauses.append(state_col+'=%s');args.append(status)
        if environment and environment!='all' and has_mode:clauses.append('environment=%s');args.append(environment)
        from datetime import date
        for value,op,extra in [(start,'>=',''),(end,'<',"+interval '1 day'")]:
            if value:
                try:date.fromisoformat(value)
                except ValueError:raise HTTPException(422,'Invalid date')
                clauses.append(f"{date_col} {op} %s::date{extra}");args.append(value)
        where=' where '+' and '.join(clauses) if clauses else ''
        rows=db.rows(f'select * from ({source}) v{where} order by {date_col} desc,id desc limit 26 offset %s',(*args,offset))
        return {'rows':rows[:25],'has_more':len(rows)>25,'offset':offset,**health()}
