from contextlib import asynccontextmanager
from datetime import UTC,datetime
from uuid import UUID,uuid4
from typing import Literal
import hmac
import os
import httpx
from fastapi import FastAPI,Header,HTTPException,Request
from psycopg.types.json import Jsonb
from .config import Settings
from .db import Database,owner_hash,IdempotencyConflict
from .models import Profile,MatchRequest,Feedback,Identity,ShortlistRefresh,SavedState, RoleIntent
from .ranking import sponsor_valid,usable_channels,open_jobs
from .presentation import displayed_channels,short_match_reason
from .billing import Credits,InsufficientCredits,billing_enabled,spending_enabled,cost,credit_environment,batch_value,lock_account,COMPANIES_PER_CREDIT

MAX_RESULT_RANK = 2**31 - 1


def create_app(settings=None,db=None):
    settings=settings or Settings.from_env()
    db=db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        db.open()
        yield
        db.close()

    app=FastAPI(title="SponsorReach",version="0.1.0",lifespan=lifespan)
    app.state.db=db

    @app.middleware("http")
    async def private_api(request:Request,call_next):
        if request.url.path!="/health" and settings.api_secret and not hmac.compare_digest(request.headers.get("x-api-secret",""),settings.api_secret):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail":"Unauthorized gateway"},status_code=401)
        response=await call_next(request)
        response.headers["Cache-Control"]="private, no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

    def token(request):
        value=request.headers.get("x-session-token","")
        if len(value)<32 or len(value)>128:
            raise HTTPException(401,"A browser session is required")
        return value

    from .member_access import closure_blocks, closure_for, install_member_access, member_auth_method_allowed
    install_member_access(app, db, settings)

    def user(request,required=False):
        # Verify once per HTTP request, never across requests or users.
        if hasattr(request.state,'verified_account'):
            account=request.state.verified_account
            if required and account is None:raise HTTPException(401,'Sign in to view your account')
            return account
        bearer=request.headers.get("authorization","")
        if not bearer or not settings.supabase_url or not settings.supabase_publishable_key:
            if required:
                raise HTTPException(401,"Sign in to view your account")
            request.state.verified_account=None
            return None
        try:
            response=httpx.get(settings.supabase_url.rstrip("/")+"/auth/v1/user",headers={"Authorization":bearer,"apikey":settings.supabase_publishable_key},timeout=10)
            response.raise_for_status()
            value=response.json()
            if not value.get("email_confirmed_at"):
                raise HTTPException(401,"Verify your email first")
            UUID(value["id"])
            if not member_auth_method_allowed(value["id"], bearer):
                raise HTTPException(401, "Sign in with an email code or a connected provider.")
            if closure_blocks(db, closure_for(db, value["id"]), bearer):
                raise HTTPException(403, "This account is unavailable. See the data deletion page for help.")
            Credits(db).ensure_signup(value['id'])
            request.state.verified_account=value
            return value
        except (httpx.HTTPError,ValueError,KeyError):
            raise HTTPException(401,"Your sign-in session could not be verified")

    from .billing_gateway import install_billing_gateway
    install_billing_gateway(app,db)
    from .admin import install_admin
    install_admin(app,db,user,os.getenv('SPONSORREACH_ADMIN_USER_IDS',''))

    def owned(id,request):
        account=user(request)
        result=db.owned_session(str(id),token(request),account["id"] if account else None)
        if not result:
            raise HTTPException(404,"Match session not found")
        return result

    def visible_results(session):
        rows=db.rows("select * from sm_private.match_results where session_id=%s order by rank",(session["id"],))
        employers={e.id:e for e in db.employers([str(r["employer_id"]) for r in rows])}
        accepted=[]
        snapshots={False:db.active_snapshot(),True:db.active_snapshot(True)}
        for r in rows:
            employer=employers.get(str(r["employer_id"]))
            if not employer:
                continue
            if employer.is_demo and settings.environment=="production":
                continue
            active=snapshots[employer.is_demo]
            if employer.identity_status!="accepted" or not sponsor_valid(employer,active) or not usable_channels(employer):
                continue
            from .intelligence import accepted as supported
            current_claims={c.id for c in employer.claims if supported(c)}
            if not set(r["explanation"]["claim_ids"]).issubset(current_claims):
                continue
            accepted.append((r,employer))
        return accepted

    def verified_access(session,request):
        if not settings.require_verified_email and not billing_enabled():return True
        account=user(request)
        return bool(account and session['user_id'] and str(session['user_id'])==account['id'])

    def require_result_access(session,request):
        if not verified_access(session,request):raise HTTPException(403,'Confirm your email to view your shortlist')

    def card(row,employer,bookmarked=False):
        explanation = {**row["explanation"], "summary": short_match_reason(row["explanation"])}
        if evidence := explanation.get("evidence"):
            current_open_urls = {vacancy.url for vacancy in open_jobs(employer)}
            explanation["evidence"] = {
                **evidence,
                "matching_vacancies": [v for v in evidence["matching_vacancies"] if v["url"] in current_open_urls],
            }
        return {"bookmarked":bookmarked,"employer_id":employer.id,"name":employer.name,"town":employer.town,"group":row["group_name"],"location_section":row.get("features", {}).get("location_section","main"),"explanation":explanation,"tags":[c.text for c in employer.claims if c.attribution=="accepted" and c.kind=="activity"][:3],"channels":displayed_channels(employer),"sponsor":{"status":"sample_record" if employer.is_demo else "register_authorized","snapshot_date":max(m.snapshot_date for m in employer.memberships)},"verified_open_vacancies":[v.model_dump(mode="json") for v in open_jobs(employer)],"sponsorship_willingness":"not_established","rules_screen":"not_evaluated","is_demo":employer.is_demo,"workplace_location_known":bool(employer.workplace_locations),"added_revision":row.get("features",{}).get("added_revision",0)}

    def main_results(rows):
        return [(row, employer) for row, employer in rows
                if row["features"].get("location_section") != "unknown"]

    def bookmark_ids(request):
        account=user(request)
        return {str(r['employer_id']) for r in db.rows('select employer_id from sm_private.employer_bookmarks where user_id=%s',(account['id'],))} if account else set()

    def normalized_profile(profile):
        normalized=db.taxonomy().normalize(profile)
        if normalized['clarification'] or profile.explore or any(not r['confirmed'] for r in normalized['role_intents']):
            raise HTTPException(422,{'code':'profile_needs_clarification','normalization':normalized})
        profile.role_intents=[RoleIntent.model_validate(role) for role in normalized['role_intents']]
        return profile

    def authorised_rows(session,request,rows):
        if not billing_enabled():return rows if session['access']!='preview' else rows[:3]
        account=user(request,True)
        if str(session['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
        if session.get('billing_environment') and session['billing_environment']!=credit_environment():return []
        legacy=session['access'] in ('demo_unlocked','paid')
        grants=db.rows("select batch from sm_private.batch_entitlements where user_id=%s and session_id=%s and environment in (%s,'legacy')",(account['id'],session['id'],credit_environment()))
        batches={r['batch'] for r in grants}
        return [(r,e) for r,e in rows if
                (legacy and not r['features'].get('added_environment')) or
                (r['rank']//COMPANIES_PER_CREDIT in batches and r['features'].get('added_environment') in (None,credit_environment()))]

    @app.post('/api/matches/{id}/batches/{batch}/unlock')
    def unlock_batch(id:UUID,batch:int,request:Request):
        if not billing_enabled() or not spending_enabled():raise HTTPException(503,'Credit spending is paused')
        account=user(request,True);s=owned(id,request)
        if str(s['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
        if s.get('billing_environment') and s['billing_environment']!=credit_environment():raise HTTPException(409,'This shortlist belongs to another payment environment')
        if s['status']!='ready' or not 0<=batch<=MAX_RESULT_RANK//COMPANIES_PER_CREDIT:raise HTTPException(409,'Batch unavailable')
        rows=[(r,e) for r,e in visible_results(s) if batch*COMPANIES_PER_CREDIT<=r['rank']<(batch+1)*COMPANIES_PER_CREDIT]
        if s['access'] in ('demo_unlocked','paid') and rows and all(not r['features'].get('added_environment') for r,_ in rows):
            return {'charged':False,'legacy':True}
        if any(r['features'].get('added_environment') not in (None,credit_environment()) for r,_ in rows):
            raise HTTPException(409,'This batch belongs to another payment environment')
        if any(e.is_demo for _,e in rows):raise HTTPException(409,'Sample results cannot consume credits')
        if not rows:return {'charged':False,'empty':True}
        try:
            with db.transaction() as c:
                lock_account(c,account['id'])
                current=c.execute("select status,revision from sm_private.match_sessions where id=%s",(str(id),)).fetchone()
                if not current or current['status']!='ready' or current['revision']!=s['revision']:
                    raise HTTPException(409,'This shortlist has changed. Reopen it before unlocking a batch.')
                charged=Credits(db).unlock_in(c,account['id'],str(id),batch,True,employer_ids=[e.id for _,e in rows])
            return {'charged':charged,'balance':Credits(db).summary(account['id'])['available']}
        except IdempotencyConflict as exc:raise HTTPException(409,str(exc))
        except InsufficientCredits:raise HTTPException(402,'Insufficient credits. Open billing to subscribe.')

    @app.get("/health")
    def health():
        db.one("select 1 as ok")
        return {"status":"ok"}

    @app.get("/api/catalogue/status")
    def catalogue():
        counts=db.one("select count(*) filter(where not is_demo) as imported,count(*) filter(where is_demo) as demo,count(*) filter(where identity_status='accepted' and not is_demo) as identity_reviewed from sm.employers")
        indexed=db.one('select count(*) as embedding_documents,count(distinct employer_id) as indexed_employers from sm.search_index_documents where index_id=(select id from sm.search_index_versions where active)')
        return {"credit_mode":billing_enabled(),**counts,**indexed,"identity_accepted":counts['identity_reviewed'],"has_official_snapshot":bool(db.active_snapshot()),"demonstration":bool(counts["demo"]),"email_signin_available":bool(settings.supabase_url and settings.supabase_publishable_key),"requires_email_verification":settings.require_verified_email}

    @app.post("/api/profiles/suggestions")
    def profile_suggestions(body:dict):
        from .onboarding import SuggestionContext,OnboardingLibrary
        from pydantic import ValidationError
        try:context=SuggestionContext.model_validate(body)
        except ValidationError as exc:raise HTTPException(422,'Provide bounded professional context and role labels') from exc
        text=body.get('text','')
        if not isinstance(text,str) or not 2<=len(text)<=500:
            raise HTTPException(422,'Provide between 2 and 500 characters of professional context')
        if settings.embedding_provider!='local':return {'available':False,'suggestions':[]}
        try:
            from .prospects import ProspectLibrary
        except ImportError:return {'available':False,'suggestions':[]}
        from .providers import ProviderUnavailable
        if not hasattr(app.state,'prospect_library'):app.state.prospect_library=ProspectLibrary(settings)
        try:result=app.state.prospect_library.suggest(text)
        except (OSError,ValueError,ProviderUnavailable):result={'available':False,'suggestions':[]}
        if not hasattr(app.state,'onboarding_library'):app.state.onboarding_library=OnboardingLibrary(settings)
        try:result.update(app.state.onboarding_library.suggest(context))
        except (OSError,ValueError,ProviderUnavailable):result.update(skill_suggestions=[],experience_prompts=[])
        result['work_areas']=list(dict.fromkeys(topic for idea in result['suggestions'] for topic in idea.get('specializations',[])))[:8]
        return result

    @app.post("/api/profiles/normalize")
    def normalize(profile:Profile):
        return db.taxonomy().normalize(profile)

    @app.post("/api/matches",status_code=202)
    def matches(body:MatchRequest,request:Request):
        body.profile=normalized_profile(body.profile)
        account=user(request,True) if billing_enabled() else user(request)
        if account:
            saved=db.one("select identity from sm_private.candidate_profiles where user_id=%s order by created_at desc limit 1",(account["id"],))
            name=(saved or {}).get("identity",{}).get("name") or account.get("user_metadata",{}).get("name") or account["email"]
            body.identity=Identity(name=name,email=account["email"])
        elif body.identity is None:
            raise HTTPException(422,"Enter your name and email, or sign in before continuing")
        try:id=db.create_session(body,token(request),account["id"] if account else None)
        except IdempotencyConflict as exc:raise HTTPException(409,str(exc))
        except InsufficientCredits:raise HTTPException(402,'Insufficient credits. Open billing to subscribe.')
        except ValueError as exc:raise HTTPException(503,str(exc))
        return {"session_id":id,"status":"queued","verification_required":settings.require_verified_email and account is None}

    @app.get("/api/matches/history")
    def history(request:Request):
        rows=db.rows("select id,status,created_at,access from sm_private.match_sessions where owner_hash=%s and (expires_at is null or expires_at>now()) and (status<>'ready' or exists(select 1 from sm_private.match_results r where r.session_id=match_sessions.id)) order by created_at desc limit 30",(owner_hash(token(request)),))
        return {"sessions":rows}

    @app.get("/api/matches/{id}")
    def session(id:UUID,request:Request):
        s=owned(id,request)
        data={"session_id":str(id),"status":s["status"],"stage":s["stage"],"access":s["access"],"error_code":s["error_code"],"starred":s["starred"],"revision":s["revision"]}
        data['verification_required']=not verified_access(s,request)
        if data['verification_required']:return data
        profile=Profile.model_validate(s['profile'])
        data['credit_mode']=billing_enabled()
        data['profile']=profile.model_dump()
        data['visa_context']=s.get('visa_context')
        data['loading_context']={'roles':[r.raw_label for r in profile.role_intents],
            'background':profile.background.subject,'specialization':profile.background.specialization,
            'skills':[skill.label for skill in profile.skills[:5]],
            'locations':profile.location.preferred_regions,'related_roles_enabled':profile.related_roles_enabled}
        if s["status"]=="ready":
            results=visible_results(s)
            if billing_enabled():
                environment=credit_environment()
                results=[(r,e) for r,e in results if r['features'].get('added_environment') in (None,environment)]
            preview=authorised_rows(s,request,results)
            saved=bookmark_ids(request)
            main=main_results(results)
            diagnostics=(s.get("versions") or {}).get("diagnostics", {})
            data["diagnostics"]=diagnostics
            data["unknown_location_count"]=len(results)-len(main)
            if not main and diagnostics:
                if diagnostics.get("out_of_area") or diagnostics.get("unknown"):
                    data["empty_reason"]="location"
                elif diagnostics.get("retrieved") and not diagnostics.get("eligible"):
                    data["empty_reason"]="eligibility"
                else:
                    data["empty_reason"]="profession"
            latest_batch=(s.get('versions') or {}).get('refinement_batch')
            initial=[(r,e) for r,e in preview if r["rank"]//COMPANIES_PER_CREDIT in (0,latest_batch)] if billing_enabled() else preview[:20]
            next_pages=[r["rank"]//COMPANIES_PER_CREDIT*COMPANIES_PER_CREDIT for r,e in preview if r["rank"]>=COMPANIES_PER_CREDIT and r["rank"]//COMPANIES_PER_CREDIT!=latest_batch]
            data.update({"next_cursor":min(next_pages) if billing_enabled() and next_pages else (20 if not billing_enabled() and len(preview)>20 else None),"preview":[card(r,e,e.id in saved) for r,e in initial],"preview_count":len(initial),"total_count":len(main),"locked_count":len(results)-len(preview),"direct_count":sum(r["group_name"]=="direct" for r,e in main),"related_count":sum(r["group_name"]=="related" for r,e in main),"is_demo":any(e.is_demo for r,e in results),"retrieval_mode":s["retrieval_mode"]})
            if billing_enabled():
                permitted={r['rank'] for r,_ in preview}
                locked=[r['rank']//COMPANIES_PER_CREDIT for r,_ in results if r['rank'] not in permitted]
                uid=user(request,True)['id']
                next_batch=min(locked) if locked else None
                with db.transaction() as c:
                    lock_account(c,uid)
                    value=batch_value(c,uid,str(id),next_batch,employer_ids=[e.id for r,e in results if r['rank']//COMPANIES_PER_CREDIT==next_batch]) if next_batch is not None else None
                    first_value=batch_value(c,uid,str(id),0) if initial else None
                    charged=bool(c.execute("select 1 from sm_private.credit_ledger where user_id=%s and session_id=%s and kind='search' and delta<0",(uid,str(id))).fetchone())
                if s['revision'] and not s['error_code']:
                    charged=bool((s.get('versions') or {}).get('refinement_charged'))
                    first_value=(s.get('versions') or {}).get('refinement_value')
                    data['refinement_empty']=latest_batch is None
                data.update(credit_mode=True,next_locked_batch=next_batch,next_batch_cost=(1 if value['chargeable'] else 0) if value else None,search_credit_charged=charged,repeat_credit_saved=bool(first_value and first_value['total'] and not first_value['chargeable']) and not charged,balance=Credits(db).summary(uid)['available'])
        return data

    @app.get("/api/matches/{id}/results")
    def results(id:UUID,request:Request,cursor:int=0):
        s=owned(id,request)
        require_result_access(s,request)
        if cursor<0 or cursor>MAX_RESULT_RANK:
            raise HTTPException(422,"Invalid result cursor")
        rows=visible_results(s)
        saved=bookmark_ids(request)
        if billing_enabled():
            if cursor%COMPANIES_PER_CREDIT:raise HTTPException(422,'Use a batch boundary')
            allowed=authorised_rows(s,request,rows)
            selected=[(r,e) for r,e in allowed if cursor<=r['rank']<cursor+COMPANIES_PER_CREDIT]
            remaining=[r['rank']//COMPANIES_PER_CREDIT*COMPANIES_PER_CREDIT for r,_ in allowed if r['rank']>=cursor+COMPANIES_PER_CREDIT]
            return {'results':[card(r,e,e.id in saved) for r,e in selected],'next_cursor':min(remaining) if remaining else None,'total_count':len(main_results(rows)),'access':s['access']}
        limit=len(rows) if s["access"]!="preview" else min(3,len(rows))
        selected=rows[cursor:min(cursor+20,limit)]
        return {"results":[card(r,e,e.id in saved) for r,e in selected],"next_cursor":cursor+20 if cursor+20<limit else None,"total_count":len(main_results(rows)),"access":s["access"]}

    @app.post('/api/matches/{id}/refresh',status_code=202)
    def refresh(id:UUID,body:ShortlistRefresh,request:Request):
        session=owned(id,request)
        require_result_access(session,request)
        profile=normalized_profile(body.profile) if body.profile else None
        paid=billing_enabled()
        if paid:
            if not body.accept_credit_cost:raise HTTPException(422,'Confirm the 1-credit cost before refining this shortlist')
            account=user(request,True)
            if str(session['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
            if not spending_enabled():raise HTTPException(503,'Credit spending is paused')
            if session.get('billing_environment') and session['billing_environment']!=credit_environment():raise HTTPException(409,'This shortlist belongs to another payment environment')
        dedupe_key=f"match:{id}:refresh:{owner_hash(body.idempotency_key)}"
        with db.transaction() as c:
            if paid:lock_account(c,account['id'])
            current=c.execute('select * from sm_private.match_sessions where id=%s for update',(str(id),)).fetchone()
            if not current:raise HTTPException(404,'Shortlist not found')
            if current['refresh_key']==body.idempotency_key or c.execute('select 1 from sm.work_items where dedupe_key=%s',(dedupe_key,)).fetchone():
                return {'session_id':str(id),'status':current['status']}
            if current['status'] in ('queued','processing'):
                raise HTTPException(409,'This shortlist is already updating. Please wait before making another change.')
            if paid:
                try:Credits(db).reserve_in(c,account['id'],str(id),renew=True)
                except InsufficientCredits as exc:raise HTTPException(402,str(exc))
            if profile:
                profile_id=str(uuid4())
                c.execute('insert into sm_private.candidate_profiles(id,user_id,owner_hash,profile,identity,visa_context,expires_at) values(%s,%s,%s,%s,%s,%s,%s)',
                    (profile_id,current['user_id'],current['owner_hash'],Jsonb(profile.model_dump()),Jsonb(session['identity']),Jsonb(body.visa_context.model_dump()) if body.visa_context else (Jsonb(session['visa_context']) if session['visa_context'] else None),current['expires_at']))
            else:profile_id=current['profile_id']
            revision=current['revision']+1
            c.execute("update sm_private.match_sessions set profile_id=%s,status='queued',stage='Understanding your career interests',revision=%s,refresh_key=%s,updated_at=now(),error_code=null where id=%s",(profile_id,revision,body.idempotency_key,str(id)))
            c.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'match',%s,%s)",(str(uuid4()),dedupe_key,Jsonb({'session_id':str(id),'revision':revision})))
        return {'session_id':str(id),'status':'queued'}

    @app.post('/api/matches/{id}/star')
    def star(id:UUID,body:SavedState,request:Request):
        account=user(request,True)
        session=owned(id,request)
        if str(session['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
        db.execute('update sm_private.match_sessions set starred=%s where id=%s',(body.saved,str(id)))
        return {'starred':body.saved}

    @app.post('/api/matches/{id}/bookmarks/{employer_id}')
    def bookmark(id:UUID,employer_id:UUID,body:SavedState,request:Request):
        account=user(request,True)
        session=owned(id,request)
        require_result_access(session,request)
        if str(session['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
        rows=visible_results(session)
        visible=authorised_rows(session,request,rows)
        row=next((r for r,e in visible if e.id==str(employer_id)),None)
        if not row:raise HTTPException(404,'Result not accessible')
        if body.saved:
            payload={k:row[k] for k in ('group_name','explanation')}
            payload['features']={'location_section':row['features'].get('location_section','main')}
            db.execute('insert into sm_private.employer_bookmarks(user_id,employer_id,session_id,result) values(%s,%s,%s,%s) on conflict(user_id,employer_id) do update set session_id=excluded.session_id,result=excluded.result',(account['id'],str(employer_id),str(id),Jsonb(payload)))
        else:db.execute('delete from sm_private.employer_bookmarks where user_id=%s and employer_id=%s',(account['id'],str(employer_id)))
        return {'bookmarked':body.saved}

    @app.post('/api/account/bookmarks/{employer_id}')
    def remove_bookmark(employer_id:UUID,body:SavedState,request:Request):
        account=user(request,True)
        if body.saved:raise HTTPException(422,'Bookmark a visible company from its shortlist')
        db.execute('delete from sm_private.employer_bookmarks where user_id=%s and employer_id=%s',(account['id'],str(employer_id)))
        return {'bookmarked':False}

    @app.post("/api/matches/{id}/demo-unlock")
    def unlock(id:UUID,request:Request):
        if billing_enabled():raise HTTPException(410,'Use credit batch unlocking')
        s=owned(id,request)
        require_result_access(s,request)
        if s["status"]!="ready":
            raise HTTPException(409,"Your shortlist is still processing")
        if len(visible_results(s))<=3:
            raise HTTPException(409,"There are no additional employers to unlock")
        db.execute("update sm_private.match_sessions set access='demo_unlocked' where id=%s and access='preview'",(str(id),))
        return {"access":"demo_unlocked","charged":False}

    @app.post("/api/feedback",status_code=201)
    def feedback(body:Feedback,request:Request):
        try:
            UUID(body.session_id);UUID(body.employer_id)
        except ValueError:
            raise HTTPException(422,"Invalid feedback target")
        s=owned(body.session_id,request)
        require_result_access(s,request)
        rows=visible_results(s)
        visible=authorised_rows(s,request,rows)
        if body.employer_id not in {e.id for _,e in visible}:
            raise HTTPException(404,"Result not accessible")
        db.execute("insert into sm_private.feedback_events values(%s,%s,%s,%s,%s,%s,now())",(str(uuid4()),body.session_id,body.employer_id,body.event,body.position,body.note))
        return {"saved":True}

    @app.get('/api/account/allowance')
    def allowance(request:Request):
        if not billing_enabled():return {'credit_mode':False,'available':0,'preview_available':True}
        account=user(request,True)
        state=Credits(db).summary(account['id'])
        return {'credit_mode':True,'available':state['available'],'signup_credits':state['signup_credits'],'preview_available':False}

    @app.get('/api/account/credit-summary')
    def credit_summary(request:Request):
        state=Credits(db).summary(user(request,True)['id'])
        return {key:state[key] for key in ('available','signup_credits','reserved','subscription')}

    @app.get('/api/account/billing')
    def billing_summary(request:Request):
        from .billing import Credits
        return Credits(db).summary(user(request,True)['id'])

    @app.get('/api/account/usage')
    def billing_usage(request:Request,period_id:str|None=None):
        from .billing import Credits
        account=user(request,True)
        try:return Credits(db).usage(account['id'],period_id)
        except ValueError:raise HTTPException(404,'Billing period not found')

    @app.get('/api/account/credit-history')
    def billing_history(request:Request,offset:int=0):
        account=user(request,True)
        if offset<0 or offset>100000:raise HTTPException(422,'Invalid history offset')
        return {'entries':db.rows('select l.id,l.created_at,l.kind,l.delta,l.session_id from sm_private.credit_ledger l left join sm_private.billing_periods p on p.id=l.period_id left join sm_private.billing_subscriptions s on s.id=p.subscription_id where l.user_id=%s and (s.environment=%s or l.period_id is null) order by l.created_at desc,l.id desc limit 20 offset %s',(account['id'],credit_environment(),offset))}

    @app.get("/api/account/identity")
    def account_identity(request:Request):
        account=user(request)
        return {"signed_in":account is not None}

    @app.get('/api/account/profile')
    def account_profile(request:Request,session_id:UUID|None=None):
        account=user(request,True)
        if session_id:
            session=owned(session_id,request)
            if str(session['user_id'])!=account['id']:raise HTTPException(404,'Shortlist not found')
            saved={'profile':session['profile']}
        else:saved=db.one("select profile from sm_private.candidate_profiles where user_id=%s and (expires_at is null or expires_at>now()) order by created_at desc limit 1",(account['id'],))
        return {'profile':Profile.model_validate(saved['profile']).model_dump(mode='json') if saved else None,
                'account_key':owner_hash('onboarding:'+str(account['id']))}

    @app.get('/api/account/overview')
    def account_overview(request:Request,section:Literal["shortlists","bookmarks"]|None=None):
        account=user(request,True)
        saved=db.one("select identity,profile from sm_private.candidate_profiles where user_id=%s and (expires_at is null or expires_at>now()) order by created_at desc limit 1",(account['id'],)) if section is None else None
        rows=[] if section=="bookmarks" else db.rows("""select s.id,s.status,s.created_at,s.updated_at,s.starred,s.access,p.profile
            from sm_private.match_sessions s join sm_private.candidate_profiles p on p.id=s.profile_id
            where s.user_id=%s and p.user_id=%s and (s.expires_at is null or s.expires_at>now()) and (p.expires_at is null or p.expires_at>now())
              and exists(select 1 from sm_private.match_results r where r.session_id=s.id)
            order by s.starred desc,s.created_at desc limit 100""",(account['id'],account['id']))
        sessions=[]
        for row in rows:
            profile=Profile.model_validate(row.pop('profile'))
            sessions.append({**row,'roles':[r.raw_label for r in profile.role_intents]})
        if section=="shortlists":return {'sessions':sessions}
        bookmarks=[]
        records=db.rows('select employer_id,session_id,result from sm_private.employer_bookmarks where user_id=%s order by created_at desc limit 100',(account['id'],))
        if section=="bookmarks" and not records:return {'sessions':[],'bookmarks':[]}
        employers={e.id:e for e in db.employers([str(r['employer_id']) for r in records])}
        snapshots={False:db.active_snapshot(),True:db.active_snapshot(True)}
        from .intelligence import accepted as supported
        for row in records:
            e=employers.get(str(row['employer_id']))
            if not e or (e.is_demo and settings.environment=='production') or e.identity_status!='accepted' or not sponsor_valid(e,snapshots[e.is_demo]) or not usable_channels(e):continue
            if not set(row['result']['explanation']['claim_ids']).issubset({claim.id for claim in e.claims if supported(claim)}):continue
            bookmarks.append({**card(row['result'],e,True),'session_id':str(row['session_id']) if row['session_id'] else None})
        if section=="bookmarks":return {'sessions':[],'bookmarks':bookmarks}
        name=(saved or {}).get('identity',{}).get('name','').strip()
        return {'first_name':name.split()[0][:60] if name and '@' not in name else None,
                'profile':Profile.model_validate(saved['profile']).model_dump(mode='json') if saved else None,
                'sessions':sessions,'bookmarks':bookmarks}

    @app.get("/api/account/matches")
    def account_matches(request:Request):
        account=user(request,True)
        return {"sessions":db.rows("select id,status,access,created_at from sm_private.match_sessions where user_id=%s and (expires_at is null or expires_at>now()) and (status<>'ready' or exists(select 1 from sm_private.match_results r where r.session_id=match_sessions.id)) order by created_at desc limit 30",(account["id"],))}

    @app.post('/api/matches/{id}/confirmation')
    def confirmation(id:UUID,request:Request):
        # Gateway-only lookup: the public catch-all deliberately excludes this path.
        s=owned(id,request)
        return {'email':s['identity']['email']}

    @app.post("/api/account/associate")
    def associate(request:Request):
        account=user(request,True)
        # Both browser proof and confirmed email are necessary; email alone cannot claim sessions.
        count=db.execute("update sm_private.match_sessions s set user_id=%s,expires_at=null from sm_private.candidate_profiles p where p.id=s.profile_id and s.owner_hash=%s and lower(p.identity->>'email')=%s and (s.user_id is null or s.user_id=%s)",(account["id"],owner_hash(token(request)),account["email"].casefold(),account["id"]))
        db.execute("update sm_private.candidate_profiles p set user_id=%s,expires_at=null where p.owner_hash=%s and lower(p.identity->>'email')=%s and (p.user_id is null or p.user_id=%s)",(account["id"],owner_hash(token(request)),account["email"].casefold(),account["id"]))
        return {"associated":count}

    return app


app=create_app()
