#!/usr/bin/env python3
"""Start a stable local preview, API and worker; --watch opts into live reload."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def environment():
    env=os.environ.copy()
    path=ROOT/".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                name,value=line.split("=",1)
                env.setdefault(name.strip(),value.strip().strip("\"'"))
    env.setdefault("DATABASE_URL",env.get('SUPABASE_CONNECTION_STRING') or 'postgresql://localhost:55432/sponsormatch')
    env.setdefault("SPONSORMATCH_ENV","development")
    env.setdefault("APP_ORIGIN","http://127.0.0.1:3000")
    if not env.get("SPONSORMATCH_API_SECRET"):
        env["SPONSORMATCH_API_SECRET"]=secrets.token_hex(32)
    return env


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--demo",action="store_true");parser.add_argument("--watch",action="store_true",help="Use Next development live reload instead of a stable compiled preview");args=parser.parse_args()
    env=environment()
    if args.demo:
        # Never seed fictional records into the configured remote database.
        env['DATABASE_URL']='postgresql://localhost:55432/sponsormatch'
        env['REQUIRE_VERIFIED_EMAIL']='false'
    for command in ["uv","npm"]:
        if not shutil.which(command):raise SystemExit(f"Install {command} before starting")
    subprocess.run(["uv","sync","--extra","test","--extra","local","--locked"],cwd=ROOT/"backend",env=env,check=True)
    if not (ROOT/"web/node_modules").exists():
        subprocess.run(["npm","ci","--no-audit","--no-fund"],cwd=ROOT/"web",env=env,check=True)
    subprocess.run(["uv","run","--no-sync","sponsormatch","migrate"],cwd=ROOT/"backend",env=env,check=True)
    subprocess.run(["uv","run","--no-sync","sponsormatch","seed-taxonomy"],cwd=ROOT/"backend",env=env,check=True)
    if args.demo:subprocess.run(["uv","run","--no-sync","sponsormatch","seed-demo"],cwd=ROOT/"backend",env=env,check=True)
    web_env=env.copy()
    if args.watch:
        web_command=["npm","run","dev"]
    else:
        web_env.update(NODE_ENV="production",HOSTNAME="127.0.0.1",PORT="3000")
        subprocess.run(["npm","run","build"],cwd=ROOT/"web",env=web_env,check=True)
        standalone=ROOT/"web/.next/standalone"
        # Next's standalone server intentionally omits public/static assets.
        shutil.copytree(ROOT/"web/public",standalone/"public",dirs_exist_ok=True)
        shutil.copytree(ROOT/"web/.next/static",standalone/".next/static",dirs_exist_ok=True)
        web_command=["node",str(standalone/"server.js")]
    processes=[]
    try:
        for command,cwd in [(["uv","run","--no-sync","uvicorn","sponsor_match.api:app","--host","127.0.0.1","--port","8001"],ROOT/"backend"),(["uv","run","--no-sync","sponsormatch","worker"],ROOT/"backend"),(web_command,ROOT/"web")]:
            processes.append(subprocess.Popen(command,cwd=cwd,env=web_env if cwd==ROOT/"web" else env))
        print("SponsorReach: http://127.0.0.1:3000 — Ctrl+C stops these app processes",flush=True)
        while all(p.poll() is None for p in processes):time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill()


if __name__=="__main__":main()
