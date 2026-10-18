"""Bounded k6 probe of the real engine on local data; never targets Supabase.

Run from backend: uv run --no-sync python ../scripts/run_load_probe.py
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from uuid import uuid4
import httpx
import psycopg
from sponsor_match.benchmark import prospect_profiles

ROOT=Path(__file__).resolve().parents[1]
LOCAL='postgresql://localhost:55432/sponsormatch'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--vus',type=int,default=2)
    parser.add_argument('--seconds',type=int,default=15)
    parser.add_argument('--output',default=str(ROOT/'data/evaluation/2026-10-16/load'))
    args=parser.parse_args()
    if not 1<=args.vus<=4 or not 1<=args.seconds<=60:raise ValueError('Local probe bounded to 1–4 VUs and 1–60 seconds')
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    cases=[c for c in prospect_profiles() if c['occupation_family']!='adversarial' and c['id'].endswith(':0')]
    (output/'load-prospects.json').write_text(json.dumps(cases))
    run_id=uuid4().hex
    env=os.environ.copy()
    env.update(DATABASE_URL=LOCAL,SPONSORMATCH_ENV='production',SPONSORMATCH_API_SECRET=secrets.token_hex(32),REQUIRE_VERIFIED_EMAIL='true',SUPABASE_URL='',SUPABASE_PUBLISHABLE_KEY='',EMBEDDING_PROVIDER='local')
    children=[]
    with (output/'server.log').open('w') as log:
        try:
            children.append(subprocess.Popen(['uv','run','--no-sync','uvicorn','sponsor_match.api:app','--host','127.0.0.1','--port','8002'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log))
            children.append(subprocess.Popen(['uv','run','--no-sync','sponsormatch','worker','--concurrency','2'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log))
            for _ in range(100):
                try:
                    if httpx.get('http://127.0.0.1:8002/health',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                if any(p.poll() is not None for p in children):raise RuntimeError('Local probe services failed to start')
                time.sleep(.1)
            else:raise RuntimeError('Local probe services did not become ready')
            # Let the worker load the pinned local embedding model before measuring HTTP.
            time.sleep(3)
            env.update(LOAD_BASE='http://127.0.0.1:8002',LOAD_RUN_ID=run_id,LOAD_API_SECRET=env['SPONSORMATCH_API_SECRET'],LOAD_VUS=str(args.vus),LOAD_DURATION=f'{args.seconds}s',PROSPECTS_FILE=str(output/'load-prospects.json'))
            result=subprocess.run(['k6','run','--summary-export',str(output/'summary.json'),str(ROOT/'load/matching.js')],env=env,capture_output=True,text=True)
            (output/'k6.log').write_text(result.stdout+'\n'+result.stderr)
            report={'exit_code':result.returncode,'vus':args.vus,'duration_seconds':args.seconds,'target':'isolated localhost API, real employer catalogue','supabase_load_requests':0,'emails_sent':0,'scope':'HTTP API + local queue + worker + local embeddings + local Postgres. Excludes Next.js gateway, verified results render and Supabase network latency.'}
            (output/'scope.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report),flush=True)
            print(result.stdout[-5000:],flush=True)
        finally:
            for child in children:
                if child.poll() is None:child.terminate()
            for child in children:
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            # Exact run marker; never delete real candidate data or other probes.
            with psycopg.connect(LOCAL) as c:
                ids=[r[0] for r in c.execute("select id from sm_private.candidate_profiles where identity->>'email'=%s",(f'load-{run_id}@example.invalid',))]
                sessions=[str(r[0]) for r in c.execute('select id from sm_private.match_sessions where profile_id=any(%s::uuid[])',(ids,))]
                c.execute("delete from sm.work_items where payload->>'session_id'=any(%s)",(sessions,))
                c.execute('delete from sm_private.match_sessions where profile_id=any(%s::uuid[])',(ids,))
                c.execute('delete from sm_private.candidate_profiles where id=any(%s::uuid[])',(ids,))


if __name__=='__main__':main()
