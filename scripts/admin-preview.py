"""Run an isolated-port admin preview without seeding data or enabling sales."""
import os
from pathlib import Path
import subprocess
import sys
import time
import argparse
ROOT=Path(__file__).resolve().parents[1]
env=os.environ.copy()
for line in (ROOT/'.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        env[key.strip()]=value.strip().strip("\"'")
parser=argparse.ArgumentParser();parser.add_argument('--test-billing',action='store_true');parser.add_argument('--port',type=int,default=3040);parser.add_argument('--api-port',type=int,default=8022);parser.add_argument('--database-url');args=parser.parse_args()
if args.test_billing and not env.get('AGENTAOS_API_KEY','').startswith('sk_test_'):raise SystemExit('A test key is required')
env.update(APP_ORIGIN=f'http://127.0.0.1:{args.port}',SPONSORMATCH_API_URL=f'http://127.0.0.1:{args.api_port}',BILLING_MODE='test' if args.test_billing else 'off',BILLING_CHECKOUT_ENABLED='true' if args.test_billing else 'false',BILLING_ENFORCE_CREDITS='true' if args.test_billing else env.get('BILLING_ENFORCE_CREDITS','false'))
if args.database_url:env['DATABASE_URL']=args.database_url
processes=[]
try:
    processes.append(subprocess.Popen([str(ROOT/'backend/.venv/bin/python'),'-m','uvicorn','sponsor_match.api:app','--host','127.0.0.1','--port',str(args.api_port)],cwd=ROOT/'backend',env=env))
    processes.append(subprocess.Popen(['npm','run','start','--','--port',str(args.port)],cwd=ROOT/'web',env=env))
    print(f'Administrator preview: http://127.0.0.1:{args.port}/admin — '+('TEST payments only' if args.test_billing else 'sales disabled')+'; no new matching worker started.',flush=True)
    while all(p.poll() is None for p in processes):time.sleep(.5)
except KeyboardInterrupt:pass
finally:
    for p in processes:
        if p.poll() is None:p.terminate()
    for p in processes:
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill()
