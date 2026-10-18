from contextlib import asynccontextmanager
from datetime import UTC,datetime
from uuid import UUID,uuid4
import hmac
import httpx
from fastapi import FastAPI,Header,HTTPException,Request
from psycopg.types.json import Jsonb
from .config import Settings
from .db import Database,owner_hash
from .models import Profile,MatchRequest,Feedback,Identity,ShortlistRefresh,SavedState
from .ranking import sponsor_valid,usable_channels,open_jobs
from .presentation import displayed_channels,short_match_reason


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

    def user(request,required=False):
        bearer=request.headers.get("authorization","")
        if not bearer or not settings.supabase_url or not settings.supabase_publishable_key:
            if required:
                raise HTTPException(401,"Sign in to view your account")
            return None
        try:
            response=httpx.get(settings.supabase_url.rstrip("/")+"/auth/v1/user",headers={"Authorization":bearer,"apikey":settings.supabase_publishable_key},timeout=10)
            response.raise_for_status()
            value=response.json()
            if not value.get("email_confirmed_at"):
                raise HTTPException(401,"Verify your email first")
            UUID(value["id"])
            return value
        except (httpx.HTTPError,ValueError,KeyError):
            raise HTTPException(401,"Your sign-in session could not be verified")

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
        if not settings.require_verified_email:return True
        account=user(request)
        return bool(account and session['user_id'] and str(session['user_id'])==account['id'])

    def require_result_access(session,request):
        if not verified_access(session,request):raise HTTPException(403,'Confirm your email to view your shortlist')

    def card(row,employer,bookmarked=False):
        return {"bookmarked":bookmarked,"employer_id":employer.id,"name":employer.name,"town":employer.town,"group":row["group_name"],"explanation":{**row["explanation"],"summary":short_match_reason(row["explanation"])},"tags":[c.text for c in employer.claims if c.attribution=="accepted" and c.kind=="activity"][:3],"channels":displayed_channels(employer),"sponsor":{"status":"sample_record" if employer.is_demo else "register_authorized","snapshot_date":max(m.snapshot_date for m in employer.memberships)},"verified_open_vacancies":[v.model_dump(mode="json") for v in open_jobs(employer)],"sponsorship_willingness":"not_established","rules_screen":"not_evaluated","is_demo":employer.is_demo,"workplace_location_known":bool(employer.workplace_locations)}

    def bookmark_ids(request):
        account=user(request)
        return {str(r['employer_id']) for r in db.rows('select employer_id from sm_private.employer_bookmarks where user_id=%s',(account['id'],))} if account else set()

    def normalized_profile(profile):
        normalized=db.taxonomy().normalize(profile)
        if normalized['clarification'] or profile.explore or any(not r.confirmed for r in profile.role_intents):
            raise HTTPException(422,{'code':'profile_needs_clarification','normalization':normalized})
        profile.role_intents=[r.model_copy(update={'concept_id':db.taxonomy().resolve(r.raw_label).id if db.taxonomy().resolve(r.raw_label) else None}) for r in profile.role_intents]
        return profile

    @app.get("/health")
    def health():
        db.one("select 1 as ok")
        return {"status":"ok"}

    @app.get("/api/catalogue/status")
    def catalogue():
        counts=db.one("select count(*) filter(where not is_demo) as imported,count(*) filter(where is_demo) as demo,count(*) filter(where identity_status='accepted' and not is_demo) as identity_reviewed from sm.employers")
        indexed=db.one('select count(*) as embedding_documents,count(distinct employer_id) as indexed_employers from sm.search_index_documents where index_id=(select id from sm.search_index_versions where active)')
        return {**counts,**indexed,"identity_accepted":counts['identity_reviewed'],"has_official_snapshot":bool(db.active_snapshot()),"demonstration":bool(counts["demo"]),"email_signin_available":bool(settings.supabase_url and settings.supabase_publishable_key),"requires_email_verification":settings.require_verified_email,"demo_price_gbp":settings.demo_price_gbp}

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
        normalized=db.taxonomy().normalize(body.profile)
        if normalized["clarification"] or body.profile.explore or any(not r.confirmed for r in body.profile.role_intents):
            raise HTTPException(422,{"code":"profile_needs_clarification","normalization":normalized})
        # Submitted concept IDs never bypass normalization or authorize ranking.
        body.profile.role_intents=[r.model_copy(update={"concept_id":db.taxonomy().resolve(r.raw_label).id if db.taxonomy().resolve(r.raw_label) else None}) for r in body.profile.role_intents]
        account=user(request)
        if account:
            saved=db.one("select identity from sm_private.candidate_profiles where user_id=%s order by created_at desc limit 1",(account["id"],))
            name=(saved or {}).get("identity",{}).get("name") or account.get("user_metadata",{}).get("name") or account["email"]
            body.identity=Identity(name=name,email=account["email"])
        elif body.identity is None:
            raise HTTPException(422,"Enter your name and email, or sign in before continuing")
        id=db.create_session(body,token(request),account["id"] if account else None)
        return {"session_id":id,"status":"queued","verification_required":settings.require_verified_email and account is None}

    @app.get("/api/matches/history")
    def history(request:Request):
        rows=db.rows("select id,status,created_at,access from sm_private.match_sessions where owner_hash=%s and expires_at>now() order by created_at desc limit 30",(owner_hash(token(request)),))
        return {"sessions":rows}

    @app.get("/api/matches/{id}")
    def session(id:UUID,request:Request):
        s=owned(id,request)
        data={"session_id":str(id),"status":s["status"],"stage":s["stage"],"access":s["access"],"error_code":s["error_code"],"demo_price_gbp":settings.demo_price_gbp,"starred":s["starred"],"revision":s["revision"]}
        data['verification_required']=not verified_access(s,request)
        if data['verification_required']:return data
        profile=Profile.model_validate(s['profile'])
        data['loading_context']={'roles':[r.raw_label for r in profile.role_intents],
            'background':profile.background.subject,'specialization':profile.background.specialization,
            'skills':[skill.label for skill in profile.skills[:5]],
            'locations':profile.location.preferred_regions,'related_roles_enabled':profile.related_roles_enabled}
        if s["status"]=="ready":
            results=visible_results(s)
            preview=results if s["access"]!="preview" else results[:3]
            saved=bookmark_ids(request)
            data.update({"preview":[card(r,e,e.id in saved) for r,e in preview[:20]],"preview_count":min(3,len(results)),"total_count":len(results),"locked_count":max(0,len(results)-3) if s["access"]=="preview" else 0,"direct_count":sum(r["group_name"]=="direct" for r,e in results),"related_count":sum(r["group_name"]=="related" for r,e in results),"is_demo":any(e.is_demo for r,e in results),"retrieval_mode":s["retrieval_mode"]})
        return data

    @app.get("/api/matches/{id}/results")
    def results(id:UUID,request:Request,cursor:int=0):
        s=owned(id,request)
        require_result_access(s,request)
        if cursor<0 or cursor>150:
            raise HTTPException(422,"Invalid result cursor")
        rows=visible_results(s)
        limit=len(rows) if s["access"]!="preview" else min(3,len(rows))
        selected=rows[cursor:min(cursor+20,limit)]
        saved=bookmark_ids(request)
        return {"results":[card(r,e,e.id in saved) for r,e in selected],"next_cursor":cursor+20 if cursor+20<limit else None,"total_count":len(rows),"access":s["access"]}

    @app.post('/api/matches/{id}/refresh',status_code=202)
    def refresh(id:UUID,body:ShortlistRefresh,request:Request):
        session=owned(id,request)
        require_result_access(session,request)
        profile=normalized_profile(body.profile) if body.profile else None
        with db.transaction() as c:
            current=c.execute('select * from sm_private.match_sessions where id=%s for update',(str(id),)).fetchone()
            if current['refresh_key']==body.idempotency_key:
                return {'session_id':str(id),'status':current['status']}
            if current['status'] in ('queued','processing'):
                raise HTTPException(409,'This shortlist is already updating. Please wait before making another change.')
            if profile:
                profile_id=str(uuid4())
                c.execute('insert into sm_private.candidate_profiles(id,user_id,owner_hash,profile,identity,visa_context,expires_at) values(%s,%s,%s,%s,%s,%s,%s)',
                    (profile_id,current['user_id'],current['owner_hash'],Jsonb(profile.model_dump()),Jsonb(session['identity']),Jsonb(body.visa_context.model_dump()) if body.visa_context else None,current['expires_at']))
            else:profile_id=current['profile_id']
            revision=current['revision']+1
            c.execute("update sm_private.match_sessions set profile_id=%s,status='queued',stage='Understanding your career interests',revision=%s,refresh_key=%s,updated_at=now(),error_code=null where id=%s",(profile_id,revision,body.idempotency_key,str(id)))
            c.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'match',%s,%s)",(str(uuid4()),f'match:{id}:{revision}',Jsonb({'session_id':str(id),'revision':revision})))
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
        visible=rows if session['access']!='preview' else rows[:3]
        row=next((r for r,e in visible if e.id==str(employer_id)),None)
        if not row:raise HTTPException(404,'Result not accessible')
        if body.saved:
            payload={k:row[k] for k in ('group_name','explanation')}
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
        visible=rows if s["access"]!="preview" else rows[:3]
        if body.employer_id not in {e.id for _,e in visible}:
            raise HTTPException(404,"Result not accessible")
        db.execute("insert into sm_private.feedback_events values(%s,%s,%s,%s,%s,%s,now())",(str(uuid4()),body.session_id,body.employer_id,body.event,body.position,body.note))
        return {"saved":True}

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
        else:saved=db.one("select profile from sm_private.candidate_profiles where user_id=%s and expires_at>now() order by created_at desc limit 1",(account['id'],))
        return {'profile':Profile.model_validate(saved['profile']).model_dump(mode='json') if saved else None,
                'account_key':owner_hash('onboarding:'+str(account['id']))}

    @app.get('/api/account/overview')
    def account_overview(request:Request):
        account=user(request,True)
        saved=db.one("select identity,profile from sm_private.candidate_profiles where user_id=%s and expires_at>now() order by created_at desc limit 1",(account['id'],))
        rows=db.rows("""select s.id,s.status,s.created_at,s.updated_at,s.starred,s.access,p.profile
            from sm_private.match_sessions s join sm_private.candidate_profiles p on p.id=s.profile_id
            where s.user_id=%s and p.user_id=%s and s.expires_at>now() and p.expires_at>now()
            order by s.starred desc,s.created_at desc limit 100""",(account['id'],account['id']))
        sessions=[]
        for row in rows:
            profile=Profile.model_validate(row.pop('profile'))
            sessions.append({**row,'roles':[r.raw_label for r in profile.role_intents]})
        bookmarks=[]
        records=db.rows('select employer_id,session_id,result from sm_private.employer_bookmarks where user_id=%s order by created_at desc limit 100',(account['id'],))
        employers={e.id:e for e in db.employers([str(r['employer_id']) for r in records])}
        snapshots={False:db.active_snapshot(),True:db.active_snapshot(True)}
        from .intelligence import accepted as supported
        for row in records:
            e=employers.get(str(row['employer_id']))
            if not e or (e.is_demo and settings.environment=='production') or e.identity_status!='accepted' or not sponsor_valid(e,snapshots[e.is_demo]) or not usable_channels(e):continue
            if not set(row['result']['explanation']['claim_ids']).issubset({claim.id for claim in e.claims if supported(claim)}):continue
            bookmarks.append({**card(row['result'],e,True),'session_id':str(row['session_id']) if row['session_id'] else None})
        name=(saved or {}).get('identity',{}).get('name','').strip()
        return {'first_name':name.split()[0][:60] if name and '@' not in name else None,
                'profile':Profile.model_validate(saved['profile']).model_dump(mode='json') if saved else None,
                'sessions':sessions,'bookmarks':bookmarks}

    @app.get("/api/account/matches")
    def account_matches(request:Request):
        account=user(request,True)
        return {"sessions":db.rows("select id,status,access,created_at from sm_private.match_sessions where user_id=%s and expires_at>now() order by created_at desc limit 30",(account["id"],))}

    @app.post('/api/matches/{id}/confirmation')
    def confirmation(id:UUID,request:Request):
        # Gateway-only lookup: the public catch-all deliberately excludes this path.
        s=owned(id,request)
        return {'email':s['identity']['email']}

    @app.post("/api/account/associate")
    def associate(request:Request):
        account=user(request,True)
        # Both browser proof and confirmed email are necessary; email alone cannot claim sessions.
        count=db.execute("update sm_private.match_sessions s set user_id=%s from sm_private.candidate_profiles p where p.id=s.profile_id and s.owner_hash=%s and lower(p.identity->>'email')=%s and (s.user_id is null or s.user_id=%s)",(account["id"],owner_hash(token(request)),account["email"].casefold(),account["id"]))
        db.execute("update sm_private.candidate_profiles p set user_id=%s where p.owner_hash=%s and lower(p.identity->>'email')=%s and (p.user_id is null or p.user_id=%s)",(account["id"],owner_hash(token(request)),account["email"].casefold(),account["id"]))
        return {"associated":count}

    return app


app=create_app()
