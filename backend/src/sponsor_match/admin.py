"""Staff access is assigned with verified, server-owned user IDs, never JWT user_metadata."""
from uuid import UUID,uuid4
import os
from fastapi import HTTPException,Request
from pydantic import BaseModel,Field

def staff_ids(value):
    try:
        ids={str(UUID(item.strip())) for item in value.split(',') if item.strip()}
        return ids if len(ids)==1 else set()
    except ValueError:return set() # Fail closed on a malformed configuration.

class TicketBody(BaseModel):
    subject:str=Field(min_length=1,max_length=160)
    message:str=Field(min_length=1,max_length=4000)

class ReplyBody(BaseModel):
    message:str=Field(min_length=1,max_length=4000)

class TicketState(BaseModel):
    closed:bool

def install_admin(app,db,user,allowlist):
    def admin(request):
        actor=user(request,True)
        expected=os.getenv('SPONSORREACH_ADMIN_EMAIL','').strip().lower()
        if not expected or (actor.get('email') or '').lower()!=expected or str(actor['id']) not in staff_ids(allowlist):raise HTTPException(403,'Administrator access required')
        return actor

    from .dashboard import install_dashboard
    install_dashboard(app,db,admin)

    @app.get('/api/admin/overview')
    def overview(request:Request,offset:int=0):
        admin(request)
        if not 0<=offset<=100000:raise HTTPException(422,'Invalid offset')
        return {'payments':db.rows('select p.id,p.invoice_id,p.amount_minor,p.currency,p.status,p.paid_at,b.user_id,s.environment from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id join sm_private.billing_subscriptions s on s.id=b.subscription_id order by p.paid_at desc,p.id limit 25 offset %s',(offset,)),
                'refunds':db.rows('select id,user_id,payment_id,status,created_at from sm_private.refund_requests order by created_at desc,id limit 25 offset %s',(offset,)),
                'tickets':db.rows('select * from sm_private.support_tickets order by updated_at desc,id limit 25 offset %s',(offset,)),
                'provider_actions_available':bool(os.getenv('AGENTAOS_API_KEY') and os.getenv('BILLING_INTERNAL_SECRET'))}

    @app.get('/api/account/support')
    def tickets(request:Request):
        actor=user(request,True)
        return {'tickets':db.rows('select * from sm_private.support_tickets where user_id=%s order by created_at desc limit 50',(actor['id'],))}

    @app.post('/api/account/support',status_code=201)
    def create_ticket(request:Request,body:TicketBody):
        actor=user(request,True)
        if not body.subject.strip() or not body.message.strip():raise HTTPException(422,'Enter a subject and message')
        with db.transaction() as c:
            c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('support:'+actor['id'],))
            n=c.execute("select count(*) n from sm_private.support_tickets where user_id=%s and created_at>now()-interval '1 hour'",(actor['id'],)).fetchone()['n']
            if n>=5:raise HTTPException(429,'Please wait before creating another support request')
            tid=str(uuid4())
            c.execute('insert into sm_private.support_tickets(id,user_id,subject,message) values(%s,%s,%s,%s)',(tid,actor['id'],body.subject.strip(),body.message.strip()))
        return {'id':tid}

    def owned_ticket(request,tid,is_admin):
        actor=admin(request) if is_admin else user(request,True)
        ticket=db.one('select * from sm_private.support_tickets where id=%s',(tid,))
        if not ticket or (not is_admin and str(ticket['user_id'])!=actor['id']):raise HTTPException(404,'Support request not found')
        return actor,ticket

    def conversation(request,tid,is_admin):
        _,ticket=owned_ticket(request,tid,is_admin)
        return {'ticket':ticket,'replies':db.rows('select id,message,is_staff,created_at from sm_private.support_replies where ticket_id=%s order by created_at,id',(tid,))}

    @app.get('/api/admin/support/{tid}')
    def admin_conversation(tid:UUID,request:Request):return conversation(request,tid,True)
    @app.get('/api/account/support/{tid}')
    def own_conversation(tid:UUID,request:Request):return conversation(request,tid,False)

    def reply(request,tid,body,is_admin):
        actor,ticket=owned_ticket(request,tid,is_admin)
        if not body.message.strip():raise HTTPException(422,'Enter a message')
        if ticket['status']=='closed':raise HTTPException(409,'This support request is closed')
        with db.transaction() as c:
            locked=c.execute('select status from sm_private.support_tickets where id=%s for update',(tid,)).fetchone()
            if locked['status']=='closed':raise HTTPException(409,'This support request is closed')
            count=c.execute("select count(*) n from sm_private.support_replies where actor_id=%s and created_at>now()-interval '1 hour'",(actor['id'],)).fetchone()['n']
            if count>=30:raise HTTPException(429,'Please wait before adding another reply')
            c.execute('insert into sm_private.support_replies(id,ticket_id,actor_id,is_staff,message) values(%s,%s,%s,%s,%s)',(str(uuid4()),tid,actor['id'],is_admin,body.message.strip()))
            c.execute('update sm_private.support_tickets set updated_at=now() where id=%s',(tid,))
            if is_admin:c.execute("insert into sm_private.admin_audit(id,actor_id,action,target_id) values(%s,%s,'support_reply',%s)",(str(uuid4()),actor['id'],tid))
        return {'saved':True}

    @app.post('/api/admin/support/{tid}/reply')
    def admin_reply(tid:UUID,request:Request,body:ReplyBody):return reply(request,tid,body,True)
    @app.post('/api/account/support/{tid}/reply')
    def own_reply(tid:UUID,request:Request,body:ReplyBody):return reply(request,tid,body,False)
    @app.post('/api/admin/support/{tid}/state')
    def state(tid:UUID,request:Request,body:TicketState):
        actor,_=owned_ticket(request,tid,True)
        with db.transaction() as c:
            c.execute('update sm_private.support_tickets set status=%s,updated_at=now() where id=%s',('closed' if body.closed else 'open',tid))
            c.execute('insert into sm_private.admin_audit(id,actor_id,action,target_id) values(%s,%s,%s,%s)',(str(uuid4()),actor['id'],'support_close' if body.closed else 'support_reopen',tid))
        return {'saved':True}
