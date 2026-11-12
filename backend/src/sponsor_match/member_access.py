"""Private member identity and account closure operations."""
import base64
import hmac
import json
import os
from datetime import datetime, UTC
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, Request

from .billing import lock_account
from .db import owner_hash


def auth_request(settings, method, path, *, admin=False, bearer=None, body=None):
    key = os.getenv("SUPABASE_SECRET_KEY", "") if admin else settings.supabase_publishable_key
    if not settings.supabase_url or not key:
        raise HTTPException(503, "Account service is unavailable")
    headers = {"apikey": key}
    # Legacy service-role keys are JWTs. Current secret keys use the apikey header.
    if bearer or (admin and key.count(".") == 2):
        headers["Authorization"] = "Bearer " + (bearer or key)
    try:
        return httpx.request(method, settings.supabase_url.rstrip("/") + "/auth/v1/" + path,
                             headers=headers, json=body, timeout=8)
    except httpx.RequestError:
        raise HTTPException(503, "Account service is unavailable") from None


def confirmed_identity(settings, bearer):
    if not bearer.startswith("Bearer "):
        raise HTTPException(401, "Sign in to your account")
    response = auth_request(settings, "GET", "user", bearer=bearer[7:])
    if response.status_code >= 500:
        raise HTTPException(503, "Account service is unavailable")
    if not response.is_success:
        raise HTTPException(401, "Your sign-in session could not be verified")
    identity = response.json()
    if not identity.get("email_confirmed_at") or not identity.get("email"):
        raise HTTPException(401, "Verify your email first")
    identity["id"] = str(UUID(identity["id"]))
    if not member_auth_method_allowed(identity["id"], bearer):
        raise HTTPException(403, "Sign in with an email code or a connected provider.")
    return identity


def staff_account(uid, email):
    ids = {value.strip() for value in os.getenv("SPONSORREACH_ADMIN_USER_IDS", "").split(",")}
    return bool(uid and uid in ids) or bool(email and email == os.getenv("SPONSORREACH_ADMIN_EMAIL", "").strip().lower())


def auth_claims(bearer):
    try:
        payload = bearer.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError, IndexError):
        return {}


def member_auth_method_allowed(uid, bearer):
    # Members use OTP and social sign-in. A password set on an unconfirmed
    # Supabase signup must not gain app access when the mailbox owner verifies.
    methods = auth_claims(bearer).get("amr") or []
    return not any(method.get("method") == "password" for method in methods) or staff_account(uid, "")


def closure_blocks(db, closure, bearer=""):
    if not closure:
        return False
    if closure["status"] != "restored":
        return True
    # The bearer has already been verified by Supabase. Refuse sessions issued
    # created before restoration, even if a previous token was refreshed.
    try:
        session = db.one("select created_at from auth.sessions where id=%s and user_id=%s",
                         (str(UUID(auth_claims(bearer)["session_id"])), closure["user_id"]))
        return not session or session["created_at"] <= closure["restored_at"]
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return True


def closure_for(db, uid):
    return db.one("select user_id,status,restored_at from sm_private.member_closures where user_id=%s", (uid,))


def _account_lock(c, uid):
    c.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", ("member:" + str(uid),))


def _social_account(c, uid):
    _account_lock(c, uid)
    closure = c.execute("select status from sm_private.member_closures where user_id=%s", (uid,)).fetchone()
    if closure and closure["status"] != "restored":
        raise HTTPException(403, "This account is scheduled for deletion. See the data deletion page for help.")
    user = c.execute("select id,email,email_confirmed_at from auth.users where id=%s", (uid,)).fetchone()
    if not user or not user["email_confirmed_at"] or not user["email"] or staff_account(str(uid), user["email"].lower()):
        raise HTTPException(403, "Use your existing sign-in method.")
    return user


def _link(c, provider, subject, uid):
    c.execute("""insert into sm_private.member_signin_methods(provider,subject,user_id)
                 values(%s,%s,%s) on conflict do nothing""", (provider, subject, uid))
    linked = c.execute("""select user_id from sm_private.member_signin_methods where provider=%s and subject=%s""",
                       (provider, subject)).fetchone()
    if not linked or str(linked["user_id"]) != str(uid):
        raise HTTPException(409, "This sign-in method is already connected. Use your existing sign-in method, or disconnect the old connection in Settings.")


def _social_session(settings, user):
    response = auth_request(settings, "POST", "admin/generate_link", admin=True,
                            body={"type": "magiclink", "email": user["email"]})
    if not response.is_success:
        raise HTTPException(503, "Sign-in is temporarily unavailable. Try an email code.")
    link = response.json()
    if link.get("id") != str(user["id"]) or not link.get("hashed_token"):
        raise HTTPException(409, "Use your existing sign-in method.")
    response = auth_request(settings, "POST", "verify", body={"type": "email", "token_hash": link["hashed_token"]})
    if not response.is_success:
        raise HTTPException(503, "Sign-in is temporarily unavailable. Try an email code.")
    result = response.json()
    if result.get("user", {}).get("id") != str(user["id"]) or not result.get("refresh_token") or not result.get("access_token"):
        raise HTTPException(409, "Use your existing sign-in method.")
    return {key: result[key] for key in ("access_token", "refresh_token")}


def install_member_access(app, db, settings):
    @app.post("/api/internal/member-access/{action}")
    def member_access(action: str, request: Request, body: dict):
        if not settings.api_secret or not hmac.compare_digest(request.headers.get("x-api-secret", ""), settings.api_secret):
            raise HTTPException(401, "Private account service only")
        bearer = request.headers.get("authorization", "")
        if action == "status":
            uid = str(UUID(body["user_id"]))
            return {"blocked": not member_auth_method_allowed(uid, bearer) or closure_blocks(db, closure_for(db, uid), bearer)}
        if action in ("attempt", "claim", "proof", "challenge", "complete", "pending"):
            return social_attempt(db, settings, action, body, bearer)
        if action == "deletion-jobs":
            db.execute("delete from sm_private.member_signin_attempts where expires_at<=now()")
            return {"jobs": db.rows("""select user_id,request_id from sm_private.member_closures
                where status in ('pending','purging') and (billing_checked_at is null
                or receipt_email is not null or purge_at<=now())
                order by last_attempt_at nulls first,purge_at limit 5""")}
        if action in ("deletion-billing", "process-deletion", "expire-checkout"):
            uid, request_id = str(UUID(body["user_id"])), str(UUID(body["request_id"]))
            mode = body["environment"]
            if mode not in ("test", "live"):
                raise HTTPException(422, "Invalid billing environment")
            if action == "process-deletion":
                return process_closure(db, settings, uid, request_id, mode)
            if not db.one("""select 1 from sm_private.member_closures where user_id=%s and request_id=%s
                             and status in ('pending','purging')""", (uid, request_id)):
                return {"checkouts": [], "renewals": False}
            if action == "expire-checkout":
                db.execute("""update sm_private.billing_checkouts set status='expired'
                           where user_id=%s and environment=%s and id=%s and status='pending'
                           and provider_session is null and expires_at<=now()""", (uid, mode, str(UUID(body["intent_id"]))))
                return {"updated": True}
            return {"checkouts": db.rows("""select id,provider_session,expires_at from sm_private.billing_checkouts
                      where user_id=%s and environment=%s and status='pending'""", (uid, mode)),
                    "renewals": db.one("""select exists(select 1 from sm_private.billing_subscriptions
                       where user_id=%s and environment=%s and not cancel_at_period_end
                       and status not in ('canceled','incomplete_expired')) pending""", (uid, mode))["pending"]}

        identity = confirmed_identity(settings, bearer)
        uid, email = identity["id"], identity["email"].lower()
        if closure_blocks(db, closure_for(db, uid), bearer):
            raise HTTPException(403, "This account is unavailable. See the data deletion page for help.")
        if staff_account(uid, email):
            raise HTTPException(403, "This setting is for member accounts.")
        if action == "methods":
            return {"providers": [row["provider"] for row in db.rows(
                "select provider from sm_private.member_signin_methods where user_id=%s order by provider", (uid,))]}
        if action == "disconnect":
            with db.transaction() as c:
                _social_account(c, uid)
                c.execute("delete from sm_private.member_signin_methods where user_id=%s and provider=%s",
                          (uid, body["provider"]))
            return {"disconnected": True}
        if action == "close":
            if not all(os.getenv(k) for k in ("SUPABASE_SECRET_KEY", "RESEND_API_KEY", "SPONSORREACH_DELETION_FROM")):
                raise HTTPException(503, "Account deletion is temporarily unavailable online. Email privacy@sponsorreach.uk for help.")
            result = request_closure(db, uid, email)
            # The database lock takes effect first, even if the Auth service is temporarily unavailable.
            try:
                auth_request(settings, "POST", "logout?scope=global", bearer=bearer[7:])
            except HTTPException:
                pass
            return result
        raise HTTPException(404, "Unknown action")


def social_attempt(db, settings, action, body, bearer):
    attempt_id = str(UUID(body["id"]))
    browser_hash = owner_hash(body["browser"])
    if action == "attempt":
        link_id = None
        if bearer:
            user = confirmed_identity(settings, bearer)
            link_id = user["id"]
            if closure_blocks(db, closure_for(db, link_id), bearer) or staff_account(link_id, user["email"].lower()):
                raise HTTPException(403, "Use your existing sign-in method.")
        db.execute("""delete from sm_private.member_signin_attempts where id in
            (select id from sm_private.member_signin_attempts where expires_at<=now() order by expires_at limit 25)""")
        db.execute("""insert into sm_private.member_signin_attempts(id,browser_hash,provider,link_user_id,shortlist_id)
                      values(%s,%s,%s,%s,%s)""", (attempt_id, browser_hash, body["provider"], link_id, body.get("shortlist")))
        return {"started": True}

    with db.transaction() as c:
        flow = c.execute("""select * from sm_private.member_signin_attempts
           where id=%s and browser_hash=%s and expires_at>now() for update""", (attempt_id, browser_hash)).fetchone()
        if not flow:
            raise HTTPException(410, "Your sign-in attempt expired. Start again or use an email code.")
        provider = flow["provider"]
        link_id = flow["link_user_id"]
        shortlist = flow["shortlist_id"]
        if action == "claim" and flow["state"] == "started" and provider == body["provider"]:
            c.execute("update sm_private.member_signin_attempts set state='exchanging' where id=%s", (attempt_id,))
            return {"claimed": True, "linking": bool(link_id)}
        if action == "proof" and flow["state"] == "exchanging":
            subject, email = body["subject"], body.get("email")
            binding = c.execute("select user_id from sm_private.member_signin_methods where provider=%s and subject=%s",
                                (provider, subject)).fetchone()
            if not link_id:
                account_id = binding["user_id"] if binding else None
                if not account_id and provider == "google" and body.get("authoritative") and email and not staff_account("", email):
                    c.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", ("member-email:" + email,))
                    existing = c.execute("select id,email_confirmed_at from auth.users where lower(email)=%s and not is_sso_user", (email,)).fetchone()
                    if existing and existing["email_confirmed_at"]:
                        account_id = existing["id"]
                    elif not existing:
                        created = auth_request(settings, "POST", "admin/users", admin=True, body={"email": email, "email_confirm": True})
                        if created.is_success:
                            account_id = UUID(created.json()["id"])
                        elif created.status_code >= 500:
                            raise HTTPException(503, "Sign-in is temporarily unavailable. Try an email code.")
                if account_id:
                    user = _social_account(c, account_id)
                    if binding:
                        current_binding = c.execute("""select user_id from sm_private.member_signin_methods
                            where provider=%s and subject=%s""", (provider, subject)).fetchone()
                        if not current_binding or current_binding["user_id"] != account_id:
                            raise HTTPException(409, "This sign-in method changed. Start again or use an email code.")
                    else:
                        _link(c, provider, subject, account_id)
                    session = _social_session(settings, user)
                    c.execute("delete from sm_private.member_signin_attempts where id=%s", (attempt_id,))
                    return {"session": session, "user_id": account_id, "shortlist": shortlist}
            elif binding and binding["user_id"] != link_id:
                raise HTTPException(409, "This sign-in method is connected to another account. Use your existing sign-in method.")

            c.execute("""update sm_private.member_signin_attempts set state='verify',subject=%s,suggested_email=%s,
                         expires_at=now()+interval '15 minutes' where id=%s""", (subject, email, attempt_id))
            return {"verify": True, "linking": bool(link_id)}
        if flow["state"] != "verify":
            raise HTTPException(410, "Start a new sign-in attempt.")
        current = confirmed_identity(settings, bearer) if bearer else None
        if link_id and (not current or current["id"] != str(link_id)
                        or closure_blocks(db, closure_for(db, link_id), bearer)):
            raise HTTPException(403, "Return to Settings and start the connection again.")
        if action == "pending":
            return {"provider": provider, "email": current["email"] if link_id else flow["suggested_email"], "linking": bool(link_id)}
        if action == "challenge":
            email = current["email"].lower() if link_id else body["email"]
            if staff_account("", email):
                raise HTTPException(403, "Use your existing sign-in method.")
            c.execute("update sm_private.member_signin_attempts set challenged_email=%s where id=%s", (email, attempt_id))
            return {"email": email, "linking": bool(link_id)}
        if action == "complete":
            proof = confirmed_identity(settings, "Bearer " + body["proof"])
            if (proof["email"].lower() != flow["challenged_email"]
                or (link_id and proof["id"] != str(link_id))):
                raise HTTPException(403, "Verify the email for this sign-in attempt.")
            _social_account(c, proof["id"])
            _link(c, provider, flow["subject"], proof["id"])
            c.execute("delete from sm_private.member_signin_attempts where id=%s", (attempt_id,))
            return {"user_id": proof["id"], "linking": bool(link_id), "shortlist": shortlist}
        raise HTTPException(404, "Unknown sign-in action")


def request_closure(db, uid, email, *, immediate=False):
    with db.transaction() as c:
        _account_lock(c, uid)
        lock_account(c, uid)
        row = c.execute("""insert into sm_private.member_closures(user_id,request_id,status,purge_at,receipt_email)
            values(%s,%s,'pending',now()+case when %s then interval '0' else interval '30 days' end,%s)
            on conflict(user_id) do update set
              request_id=case when member_closures.status='restored' then excluded.request_id else member_closures.request_id end,
              status=case when member_closures.status='restored' then 'pending' else member_closures.status end,
              purge_at=case when member_closures.status='restored' then excluded.purge_at
                           else least(member_closures.purge_at,excluded.purge_at) end,
              receipt_email=case when member_closures.status='restored' or excluded.receipt_email is null then excluded.receipt_email else member_closures.receipt_email end,
              billing_checked_at=case when member_closures.status='restored' then null else member_closures.billing_checked_at end
            returning request_id,purge_at""", (uid, uuid4(), immediate, email if not immediate else None)).fetchone()
        facebook = c.execute("""delete from sm_private.member_signin_methods where user_id=%s and provider='facebook'
                              returning subject""", (uid,)).fetchone()
    # Attempt completion locks the flow before the account. Clean up attempts
    # after releasing the account lock to preserve that lock ordering.
    db.execute("delete from sm_private.member_signin_attempts where link_user_id=%s or suggested_email=%s or challenged_email=%s",
               (uid, email, email))
    if facebook:
        db.execute("delete from sm_private.member_signin_attempts where provider='facebook' and subject=%s", (facebook["subject"],))
    return row


def billing_pending(c, uid, mode):
    return c.execute("""select exists(select 1 from sm_private.billing_subscriptions
          where user_id=%s and environment=%s and not cancel_at_period_end
          and status not in ('canceled','incomplete_expired'))
        or exists(select 1 from sm_private.billing_checkouts where user_id=%s and environment=%s and status='pending') pending""",
                     (uid, mode, uid, mode)).fetchone()["pending"]


def send_receipt(row):
    key, sender = os.getenv("RESEND_API_KEY"), os.getenv("SPONSORREACH_DELETION_FROM")
    if not key or not sender:
        return False
    date = row["purge_at"].strftime("%d %B %Y at %H:%M UTC")
    try:
        response = httpx.post("https://api.resend.com/emails", timeout=8,
            headers={"Authorization": "Bearer " + key, "Idempotency-Key": "account-closure/" + str(row["request_id"])},
            json={"from": sender, "to": [row["receipt_email"]], "subject": "SponsorReach account deletion scheduled",
                  "text": f"Your SponsorReach account is locked and scheduled for permanent deletion on {date}. "
                          "To request restoration before then, email privacy@sponsorreach.uk from your account email."})
        return response.is_success
    except httpx.RequestError:
        return False


def process_closure(db, settings, uid, request_id, mode):
    # Claim the irreversible step before calling the Auth API. A failed Auth
    # deletion leaves the row purging, so the next run retries safely.
    with db.transaction() as c:
        _account_lock(c, uid)
        lock_account(c, uid)
        row = c.execute("""select * from sm_private.member_closures
             where user_id=%s and request_id=%s and status in ('pending','purging') for update""",
                        (uid, request_id)).fetchone()
        if not row:
            return {"pending": False}
        c.execute("update sm_private.member_closures set last_attempt_at=now() where user_id=%s", (uid,))
        sent = not row["receipt_email"] or send_receipt(row)
        if sent:
            c.execute("update sm_private.member_closures set receipt_email=null where user_id=%s", (uid,))
        billing_done = not billing_pending(c, uid, "live") and (mode != "test" or not billing_pending(c, uid, "test"))
        if billing_done:
            c.execute("update sm_private.member_closures set billing_checked_at=now() where user_id=%s", (uid,))
        if not billing_done or row["purge_at"] > datetime.now(UTC):
            return {"pending": not billing_done or not sent}
        c.execute("update sm_private.member_closures set status='purging',receipt_email=null where user_id=%s", (uid,))

    with db.transaction() as c:
        _account_lock(c, uid)
        row = c.execute("select status from sm_private.member_closures where user_id=%s for update", (uid,)).fetchone()
        if not row or row["status"] != "purging":
            return {"pending": False}
        lock_account(c, uid)
        response = auth_request(settings, "DELETE", "admin/users/" + uid, admin=True)
        if not response.is_success and response.status_code != 404:
            raise HTTPException(503, "Account purge will be retried")
        purge_member_data(c, uid)
        c.execute("update sm_private.member_closures set status='purged' where user_id=%s", (uid,))
        c.execute("""delete from sm_private.member_closures where user_id=%s and not exists
                   (select 1 from sm_private.billing_accounts where user_id=%s)""", (uid, uid))
    return {"pending": not sent}


def purge_member_data(c, uid):
    c.execute("delete from sm_private.member_signin_methods where user_id=%s", (uid,))
    c.execute("""delete from sm_private.admin_audit where actor_id=%s or target_id in
                  (select id from sm_private.support_tickets where user_id=%s)""", (uid, uid))
    c.execute("delete from sm_private.support_replies where actor_id=%s", (uid,))
    c.execute("delete from sm_private.support_tickets where user_id=%s", (uid,))
    c.execute("delete from sm_private.employer_bookmarks where user_id=%s", (uid,))
    c.execute("delete from sm_private.credit_reservations where user_id=%s", (uid,))
    c.execute("select set_config('sponsorreach.member_purge',%s,true)", (uid,))
    c.execute("delete from sm_private.credit_ledger where user_id=%s", (uid,))
    c.execute("delete from sm_private.signup_credit_grants where user_id=%s", (uid,))
    c.execute("""delete from sm.work_items where kind='match' and payload->>'session_id' in
                 (select id::text from sm_private.match_sessions where user_id=%s)""", (uid,))
    c.execute("delete from sm_private.match_sessions where user_id=%s", (uid,))
    c.execute("""delete from sm_private.candidate_profiles p where p.user_id=%s and not exists
                 (select 1 from sm_private.match_sessions s where s.profile_id=p.id)""", (uid,))
    c.execute("update sm_private.billing_accounts set preview_session=null where user_id=%s", (uid,))
    c.execute("update sm_private.billing_checkouts set checkout_url=null where user_id=%s", (uid,))
    c.execute("update sm_private.refund_requests set reason='',provider_note=null where user_id=%s", (uid,))
    # Retain the minimum provider references needed for settled financial records.
    c.execute("""delete from sm_private.billing_checkouts b where b.user_id=%s and not exists
                 (select 1 from sm_private.billing_payments p where p.checkout_id=b.id or p.provider_session=b.provider_session)""", (uid,))
    c.execute("""delete from sm_private.billing_periods b where b.user_id=%s and not exists
                 (select 1 from sm_private.billing_payments p where p.period_id=b.id)""", (uid,))
    c.execute("""delete from sm_private.billing_subscriptions b where b.user_id=%s and not exists
                 (select 1 from sm_private.billing_periods p where p.subscription_id=b.id)""", (uid,))
    c.execute("""delete from sm_private.billing_accounts b where b.user_id=%s and not exists
                 (select 1 from sm_private.billing_subscriptions s where s.user_id=b.user_id)
                 and not exists (select 1 from sm_private.billing_checkouts s where s.user_id=b.user_id)
                 and not exists (select 1 from sm_private.refund_requests r where r.user_id=b.user_id)""", (uid,))


def restore_member(db, uid):
    with db.transaction() as c:
        _account_lock(c, uid)
        return bool(c.execute("""update sm_private.member_closures set status='restored',receipt_email=null,restored_at=now()
            where user_id=%s and status='pending' and purge_at>now() and billing_checked_at is not null returning user_id""", (uid,)).fetchone())


def erase_provider_data(db, provider, subject):
    with db.transaction() as c:
        linked = c.execute("""select user_id from sm_private.member_signin_methods
                               where provider=%s and subject=%s""", (provider, subject)).fetchone()
        c.execute("delete from sm_private.member_signin_attempts where provider=%s and subject=%s", (provider, subject))
        if linked:
            _account_lock(c, linked["user_id"])
        return c.execute("delete from sm_private.member_signin_methods where provider=%s and subject=%s", (provider, subject)).rowcount
