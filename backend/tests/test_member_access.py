"""Social account and deletion invariants with real PostgreSQL and a fake Auth API."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC
import json
import os
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from sponsor_match.api import create_app
from sponsor_match.billing import Credits
from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.member_access import closure_blocks, closure_for, request_closure, restore_member, erase_provider_data


@pytest.fixture
def access(monkeypatch):
    url = os.getenv("MEMBER_ACCESS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set MEMBER_ACCESS_TEST_DATABASE_URL to a dedicated disposable PostgreSQL database")
    db = Database(url)
    db.open()
    db.execute("create schema if not exists auth")
    db.execute("""create table if not exists auth.users(
        id uuid primary key,email text unique,email_confirmed_at timestamptz,is_sso_user boolean default false)""")
    db.execute("""create table if not exists auth.sessions(
        id uuid primary key,user_id uuid,created_at timestamptz default now())""")
    db.migrate()
    db.close()
    settings = Settings(database_url=url, api_secret="private-fixture", supabase_url="https://auth.example.invalid",
                        supabase_publishable_key="publishable-fixture")
    db = Database(url)
    auth_failures = []
    receipts = []
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-fixture")
    monkeypatch.setenv("RESEND_API_KEY", "mail-fixture")
    monkeypatch.setenv("SPONSORREACH_DELETION_FROM", "fixture@example.invalid")
    monkeypatch.setattr("sponsor_match.member_access.httpx.post",
                        lambda *args, **kwargs: receipts.append(kwargs["json"]) or httpx.Response(200))

    def user_payload(row):
        return {"id": str(row["id"]), "email": row["email"], "email_confirmed_at": "confirmed"}

    def auth_request(settings, method, path, *, bearer=None, body=None, **kwargs):
        if path == "admin/users":
            row = db.one("insert into auth.users(id,email,email_confirmed_at) values(%s,%s,now()) returning *",
                         (uuid4(), body["email"]))
            return httpx.Response(200, json=user_payload(row))
        if path == "user":
            row = db.one("select * from auth.users where id=%s", (bearer,))
            return httpx.Response(200, json=user_payload(row)) if row else httpx.Response(401)
        if path == "admin/generate_link":
            row = db.one("select id from auth.users where email=%s", (body["email"],))
            return httpx.Response(200, json={"id": str(row["id"]), "hashed_token": str(row["id"])})
        if path == "verify":
            return httpx.Response(200, json={"user": {"id": body["token_hash"]},
                                            "access_token": body["token_hash"], "refresh_token": "fixture"})
        if path == "logout?scope=global":
            return httpx.Response(204)
        if path.startswith("admin/users/") and method == "DELETE":
            if auth_failures:
                return httpx.Response(auth_failures.pop())
            db.execute("delete from auth.users where id=%s", (path.rsplit("/", 1)[1],))
            return httpx.Response(200)
        raise AssertionError(path)

    monkeypatch.setattr("sponsor_match.member_access.auth_request", auth_request)
    with TestClient(create_app(settings, db)) as client:
        def call(action, body, user=None):
            headers = {"X-API-Secret": settings.api_secret}
            if user:
                headers["Authorization"] = "Bearer " + user
            return client.post("/api/internal/member-access/" + action, headers=headers, json=body)

        yield db, call, auth_failures, receipts


def create_account(db):
    uid = str(uuid4())
    email = uid + "@gmail.com"
    db.execute("insert into auth.users(id,email,email_confirmed_at) values(%s,%s,now())", (uid, email))
    return uid, email


def attempt(call, provider, user=None, shortlist=None):
    flow = {"id": str(uuid4()), "browser": uuid4().hex + uuid4().hex}
    assert call("attempt", {**flow, "provider": provider, "shortlist": shortlist}, user).status_code == 200
    assert call("claim", {**flow, "browser": "wrong", "provider": provider}).status_code == 410
    assert call("claim", {**flow, "provider": provider}).status_code == 200
    assert call("claim", {**flow, "provider": provider}).status_code >= 400
    return flow


def test_google_and_facebook_reuse_email_account_with_missing_email_and_replay(access):
    db, call, _, _ = access
    uid, email = create_account(db)
    shortlist = str(uuid4())
    google = uuid4().hex
    flow = attempt(call, "google", shortlist=shortlist)
    result = call("proof", {**flow, "subject": google, "email": email, "authoritative": True}).json()
    assert result["user_id"] == uid and result["shortlist"] == shortlist
    assert call("proof", {**flow, "subject": google}).status_code == 410
    flow = attempt(call, "google")
    assert call("proof", {**flow, "subject": google, "email": "changed@example.net"}).json()["user_id"] == uid

    facebook = uuid4().hex
    flow = attempt(call, "facebook")
    assert call("proof", {**flow, "subject": facebook}).json()["verify"]
    assert call("challenge", {**flow, "email": email}).status_code == 200
    stranger, _ = create_account(db)
    assert call("complete", {**flow, "proof": stranger}).status_code == 403
    assert call("complete", {**flow, "proof": uid}).json()["user_id"] == uid
    assert call("complete", {**flow, "proof": uid}).status_code == 410
    flow = attempt(call, "facebook")
    assert call("proof", {**flow, "subject": facebook}).json()["user_id"] == uid
    assert call("methods", {}, uid).json()["providers"] == ["facebook", "google"]
    assert Credits(db).summary(uid)["signup_credits"] == 5


def test_nonhosted_google_email_and_manual_link_collision(access):
    db, call, _, _ = access
    uid, email = create_account(db)
    stranger, _ = create_account(db)
    google = uuid4().hex
    flow = attempt(call, "google")
    assert call("proof", {**flow, "subject": google, "email": email}).json()["verify"]
    assert call("methods", {}, uid).json()["providers"] == []
    assert call("challenge", {**flow, "email": email}).status_code == 200
    assert call("complete", {**flow, "proof": uid}).status_code == 200

    collision = attempt(call, "google", stranger)
    assert call("proof", {**collision, "subject": google}).status_code == 409
    facebook = attempt(call, "facebook", uid)
    assert call("proof", {**facebook, "subject": "linked-" + google}).json()["linking"]
    assert call("challenge", {**facebook, "email": "wrong@example.net"}, stranger).status_code == 403
    assert call("challenge", {**facebook, "email": "wrong@example.net"}, uid).json()["email"] == email
    assert call("complete", {**facebook, "proof": uid}, uid).json()["linking"]


def test_new_google_account_and_concurrent_repeat_share_one_identity(access):
    db, call, _, _ = access
    email = uuid4().hex + "@gmail.com"
    subject = uuid4().hex
    flow1, flow2 = attempt(call, "google"), attempt(call, "google")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda flow: call("proof", {**flow, "subject": subject, "email": email, "authoritative": True}),
                                [flow1, flow2]))
    assert all(result.status_code == 200 for result in results)
    assert results[0].json()["user_id"] == results[1].json()["user_id"]
    assert db.one("select count(*) n from auth.users where email=%s", (email,))["n"] == 1


def test_closure_restoration_active_billing_and_failed_purge_retry(access):
    db, call, auth_failures, receipts = access
    uid, email = create_account(db)
    old_session = uuid4()
    db.execute("insert into auth.sessions(id,user_id,created_at) values(%s,%s,now()-interval '1 hour')", (old_session, uid))
    subject = uuid4().hex
    db.execute("insert into sm_private.member_signin_methods values('facebook',%s,%s)", (subject, uid))
    db.execute("insert into sm_private.support_tickets(id,user_id,subject,message) values(%s,%s,'Privacy','Fixture')", (uuid4(), uid))
    renewal = uuid4().hex
    db.execute("""insert into sm_private.billing_subscriptions(id,user_id,environment,status,product_id)
                  values(%s,%s,'test','active','test-product')""", (renewal, uid))

    response = call("close", {}, uid)
    assert response.status_code == 200
    first = response.json()
    assert call("status", {"user_id": uid}).json()["blocked"]
    assert call("methods", {}, uid).status_code == 403
    assert not db.one("select 1 from sm_private.member_signin_methods where subject=%s", (subject,))
    job = {"user_id": uid, "request_id": first["request_id"], "environment": "test"}
    assert call("deletion-billing", job).json()["renewals"]
    assert call("process-deletion", job).json()["pending"]
    assert receipts and email in receipts[0]["to"]
    db.execute("update sm_private.billing_subscriptions set cancel_at_period_end=true where id=%s", (renewal,))
    assert not call("process-deletion", job).json()["pending"]
    assert restore_member(db, uid)

    def bearer(session):
        token = base64.urlsafe_b64encode(json.dumps({"session_id": str(session)}).encode()).decode().rstrip("=")
        return "Bearer header." + token + ".signature"

    assert closure_blocks(db, closure_for(db, uid), bearer(old_session))
    new_session = uuid4()
    db.execute("insert into auth.sessions(id,user_id) values(%s,%s)", (new_session, uid))
    assert not closure_blocks(db, closure_for(db, uid), bearer(new_session))
    assert db.one("select 1 from sm_private.support_tickets where user_id=%s", (uid,))
    immediate = request_closure(db, uid, email, immediate=True)
    assert not restore_member(db, uid)
    job["request_id"] = str(immediate["request_id"])
    auth_failures.append(503)
    assert call("process-deletion", job).status_code == 503
    assert call("status", {"user_id": uid}).json()["blocked"]
    assert not call("process-deletion", job).json()["pending"]
    assert not db.one("select 1 from auth.users where id=%s", (uid,))
    assert not db.one("select 1 from sm_private.support_tickets where user_id=%s", (uid,))
    assert not call("process-deletion", job).json()["pending"]


def test_provider_only_erasure_preserves_account(access):
    db, call, _, _ = access
    uid, _ = create_account(db)
    subject = uuid4().hex
    db.execute("insert into sm_private.member_signin_methods values('facebook',%s,%s)", (subject, uid))
    assert erase_provider_data(db, "facebook", subject) == 1
    assert erase_provider_data(db, "facebook", subject) == 0
    assert call("methods", {}, uid).json()["providers"] == []
