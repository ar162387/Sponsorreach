import argparse
import csv
import json
import logging
import os
import time
from pathlib import Path
from uuid import UUID,uuid4
from psycopg.types.json import Jsonb
from psycopg import OperationalError
from psycopg_pool import PoolTimeout
from .config import Settings
from .db import Database
from .models import Profile
from .providers import OpenAI
from .search import Matcher
from .ingest import import_csv,import_legacy,import_ledger,import_register
from .fixtures import seed_demo
from .evidence import fetch_public,page_text,review_source,refresh_channel
from .evaluate import profiles,metrics
from .taxonomy import Concept

log=logging.getLogger("sponsormatch")


def worker(db,settings,once=False):
    matcher=Matcher(db,settings)
    if not once and settings.embedding_provider=='local':
        from .providers import ProviderUnavailable
        try:matcher.provider.embeddings(['Professional employer matching.'])
        except ProviderUnavailable:log.warning('Local embedding model unavailable; evidence-gated fallback remains available')
    idle_delay=.3
    while True:
        try:
            # Catalogue imports, crawling and index/model builds stay local in
            # manual-update deployments. Candidate matching still runs online.
            item=db.claim_work(kinds=['match','refresh_prospect_cohorts'] if settings.manual_catalogue_updates else None)
        except (OperationalError,PoolTimeout):
            if once:raise
            log.warning('Database connection interrupted; worker will reconnect')
            time.sleep(2)
            continue
        if not item:
            if once:
                return
            time.sleep(idle_delay)
            idle_delay=min(2,idle_delay*2)
            continue
        idle_delay=.3
        try:
            if item["kind"]=="match":
                matcher.process_session(item["payload"]["session_id"],revision=item["payload"].get("revision",0))
            elif item["kind"]=="build_prospects":
                from .prospects import build_model,publish_model,model_root
                archive=Path(__file__).resolve().parents[3]/'data/taxonomies/ons-extended-soc-20260827.zip'
                if not archive.exists():raise ValueError('Install the official ONS occupation artifact before model refresh')
                result=build_model(db,settings,model_root(),archive,lambda _:db.execute("update sm.work_items set leased_until=now()+interval '30 minutes' where id=%s",(item['id'],)))
                publish_model(db,settings,result['folder'])
            elif item['kind']=='refresh_prospect_cohorts':
                from .prospects import refresh_cohorts
                while True:
                    report=refresh_cohorts(db,settings,expected_version=item['payload']['model_version'])
                    db.execute("update sm.work_items set leased_until=now()+interval '2 minutes' where id=%s",(item['id'],))
                    if report['status']!='updated' or not report['batch_full']:break
            elif item["kind"]=="refresh_channel":
                refresh_channel(db,**item["payload"])
            elif item["kind"]=="refresh_vacancy":
                from .vacancies import verify_vacancy
                verify_vacancy(db,**item["payload"],attribution_reviewed=True)
            else:
                raise ValueError("unknown_work_kind")
            db.finish_work(item["id"])
        except Exception as e:
            # Never log profile bodies, contact values, DB credentials or provider responses.
            code="provider_unavailable" if "Provider" in type(e).__name__ else "processing_failed"
            log.error("Work %s failed (%s)",item["id"],type(e).__name__)
            db.fail_work(item,code,settings.max_attempts)
        if once:
            return


def main():
    parser=argparse.ArgumentParser(description="SponsorReach operations")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("migrate")
    p=sub.add_parser('audit-csv');p.add_argument('path');p.add_argument('--output',required=True)
    p=sub.add_parser('cleanup-catalogue');p.add_argument('path');p.add_argument('--namespace',required=True);p.add_argument('--output',required=True)
    sub.add_parser("seed-taxonomy")
    sub.add_parser("seed-demo")
    for command in ["import-csv","import-legacy","import-ledger"]:
        p=sub.add_parser(command);p.add_argument("path");p.add_argument("--namespace",required=True)
    p=sub.add_parser("import-register");p.add_argument("path");p.add_argument("--url",required=True);p.add_argument("--publication-date",required=True);p.add_argument("--allow-large-change",action="store_true")
    p=sub.add_parser("fetch-register");p.add_argument("--output",default="../data/register")
    p=sub.add_parser("index");p.add_argument("--batch-size",type=int,default=32);p.add_argument("--resume")
    sub.add_parser("index-versions")
    p=sub.add_parser("rollback-index");p.add_argument("index_id")
    p=sub.add_parser("worker");p.add_argument("--once",action="store_true");p.add_argument("--concurrency",type=int,default=int(os.getenv("MATCH_WORKER_CONCURRENCY","2")))
    p=sub.add_parser('prepare-pool');p.add_argument('--output',required=True);p.add_argument('--per-family',type=int,default=6);p.add_argument('--cache-dir')
    p=sub.add_parser('publish-prepared');p.add_argument('folder')
    p=sub.add_parser('activate-csv-baseline');p.add_argument('path');p.add_argument('--namespace',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('benchmark-prospects');p.add_argument('--output',required=True);p.add_argument('--concurrency',type=int,default=2);p.add_argument('--labels')
    p=sub.add_parser('build-prospects');p.add_argument('--output',default='../data/prospects');p.add_argument('--occupation-archive',default='../data/taxonomies/ons-extended-soc-20260827.zip');p.add_argument('--publish',action='store_true')
    p=sub.add_parser('build-role-graph');p.add_argument('--prospect-folder',required=True);p.add_argument('--output',required=True);p.add_argument('--publish',action='store_true')
    p=sub.add_parser('publish-prospects');p.add_argument('folder')
    p=sub.add_parser('cohort-report');p.add_argument('--output',required=True)
    p=sub.add_parser('refresh-cohorts');p.add_argument('--limit',type=int,default=100)
    p=sub.add_parser('coverage-audit');p.add_argument('--model-folder',required=True);p.add_argument('--output',required=True);p.add_argument('--baseline',action='append',default=[]);p.add_argument('--max-profiles',type=int,default=200);p.add_argument('--round-size',type=int,default=25);p.add_argument('--rounds',type=int,default=8);p.add_argument('--resume');p.add_argument('--strategy',choices=['current','semantic'],default='current')
    p=sub.add_parser("prepare-source");p.add_argument("employer_id");p.add_argument("url");p.add_argument("--output",required=True);p.add_argument("--llm",action="store_true")
    p=sub.add_parser("review-source");p.add_argument("employer_id");p.add_argument("source_json");p.add_argument("--identity-reviewed",action="store_true")
    p=sub.add_parser("import-taxonomy");p.add_argument("path");p.add_argument("--namespace",required=True);p.add_argument("--version",required=True)
    p=sub.add_parser("fetch-ons");p.add_argument("--output",default="../data/taxonomies")
    p=sub.add_parser("verify-vacancy");p.add_argument("employer_id");p.add_argument("url");p.add_argument("--attribution-reviewed",action="store_true")
    p=sub.add_parser("link-employers");p.add_argument("canonical_id");p.add_argument("duplicate_id");p.add_argument("--evidence-id",required=True);p.add_argument("--identity-reviewed",action="store_true")
    p=sub.add_parser("evaluation-profiles");p.add_argument("--output",required=True)
    p=sub.add_parser("evaluate");p.add_argument("rankings");p.add_argument("labels");p.add_argument("--k",type=int,default=10)
    p=sub.add_parser("benchmark-reranker");p.add_argument("inputs");p.add_argument("labels")
    sub.add_parser("schedule-refresh")
    sub.add_parser("status")
    sub.add_parser('embedding-check')
    sub.add_parser("purge-expired")
    args=parser.parse_args()
    if args.command=='audit-csv':
        from .catalogue_cleanup import inspect_csv
        _,report=inspect_csv(args.path)
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in {'records','possible_name_town_duplicate_groups'}},indent=2));return
    settings=Settings.from_env()
    if args.command=='build-role-graph':
        from .role_graph import build
        result=build(settings,args.prospect_folder,args.output)
        if args.publish:
            pointer=Path(args.output)/'active.json';temp=pointer.with_suffix('.tmp')
            temp.write_text(json.dumps({'version':result['version']}));temp.replace(pointer)
        print(json.dumps(result,indent=2));return
    if args.command=='embedding-check':
        from .providers import embedding_provider
        started=time.perf_counter()
        vectors=embedding_provider(settings).embeddings(['Mechanical design engineer using CAD','Designing machinery and manufactured components','Preparing tax returns and financial accounts'])
        print(json.dumps({'provider':settings.embedding_provider,'model':settings.embedding_model,'dimensions':len(vectors[0]),'seconds':round(time.perf_counter()-started,3),'engineering_pair_cosine':sum(a*b for a,b in zip(vectors[0],vectors[1])),'accounting_pair_cosine':sum(a*b for a,b in zip(vectors[0],vectors[2]))},indent=2))
        return
    if args.command=="evaluation-profiles":
        Path(args.output).write_text(json.dumps(profiles(),indent=2)+"\n");return
    if args.command=="evaluate":
        print(json.dumps(metrics(json.loads(Path(args.rankings).read_text()),json.loads(Path(args.labels).read_text()),args.k),indent=2));return
    if args.command=="benchmark-reranker":
        from .rerank import benchmark
        print(json.dumps(benchmark(json.loads(Path(args.inputs).read_text()),json.loads(Path(args.labels).read_text())),indent=2));return
    db=Database(settings.database_url);db.open()
    try:
        result=None
        if args.command=="migrate":
            db.migrate();result={"migrated":True}
        elif args.command=='cleanup-catalogue':
            from .catalogue_cleanup import cleanup_catalogue
            result=cleanup_catalogue(db,args.path,args.namespace,args.output)
        elif args.command=="seed-taxonomy":
            db.seed_taxonomy();result={"concepts":len(db.taxonomy().concepts)}
        elif args.command=="seed-demo":
            result=seed_demo(db,settings)
        elif args.command=='publish-prepared':
            from .bulk import publish_prepared
            result=publish_prepared(db,args.folder)
        elif args.command=='activate-csv-baseline':
            from .csv_baseline import apply_baseline
            result=apply_baseline(db,args.path,args.namespace,args.output)
        elif args.command=='benchmark-prospects':
            from .benchmark import run_benchmark
            result=run_benchmark(db,settings,args.output,args.concurrency,args.labels)
        elif args.command in {"import-csv","import-legacy","import-ledger"}:
            result={"import-csv":import_csv,"import-legacy":import_legacy,"import-ledger":import_ledger}[args.command](db,args.path,args.namespace)
        elif args.command=='build-prospects':
            from .prospects import build_model,publish_model
            result=build_model(db,settings,args.output,args.occupation_archive,lambda row:print(json.dumps(row),flush=True))
            if args.publish:result.update(publish_model(db,settings,result['folder']))
        elif args.command=='publish-prospects':
            from .prospects import publish_model
            result=publish_model(db,settings,args.folder)
        elif args.command=='cohort-report':
            from .prospects import cohort_report
            result=cohort_report(db)
            target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,indent=2))
        elif args.command=='refresh-cohorts':
            from .prospects import refresh_cohorts
            result=refresh_cohorts(db,settings,args.limit)
        elif args.command=='coverage-audit':
            from .coverage import coverage_loop
            result=coverage_loop(db,settings,args.model_folder,args.output,args.baseline,args.max_profiles,args.round_size,args.rounds,lambda row:print(json.dumps(row),flush=True),resume=args.resume,strategy=args.strategy)
        elif args.command=="import-register":
            result=import_register(db,args.path,args.url,args.publication_date,args.allow_large_change)
        elif args.command=="fetch-register":
            from bs4 import BeautifulSoup
            import re
            html,_,_=fetch_public("https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers")
            soup=BeautifulSoup(html,"html.parser")
            urls=sorted({a["href"] for a in soup.select("a[href]") if "assets.publishing.service.gov.uk" in a["href"] and a["href"].endswith(".csv")})
            if len(urls)!=1:
                raise ValueError("Unable to identify a unique official register download")
            match=re.search(r"(\d{4}-\d{2}-\d{2})",urls[0])
            if not match:
                raise ValueError("The register URL does not include its publication date")
            content,final,_=fetch_public(urls[0],limit=30_000_000)
            folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
            target=folder/(match[1]+".csv")
            target.write_bytes(content)
            result=import_register(db,target,final,match[1])
        elif args.command=="index":
            from .indexes import build_index
            result=build_index(db,settings,args.batch_size,args.resume)
            if settings.embedding_provider=='local' and db.one("select exists(select 1 from sm.employers where payload->>'matching_basis'='provided_csv') present")['present']:
                from .prospects import enqueue_refresh
                result['prospect_refresh_queued']=enqueue_refresh(db,result['published_index'])
        elif args.command=="index-versions":
            result=db.rows("select id,model,dimensions,status,active,created_at,published_at from sm.search_index_versions order by created_at desc")
        elif args.command=="rollback-index":
            from .indexes import publish_index
            version=db.one("select status from sm.search_index_versions where id=%s",(str(UUID(args.index_id)),))
            if not version or version['status']!='published':raise ValueError("Choose a previously published index")
            result=publish_index(db,args.index_id)
        elif args.command=="worker":
            if args.once or args.concurrency==1:
                worker(db,settings,args.once)
            else:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(8,max(1,args.concurrency))) as executor:
                    futures=[executor.submit(worker,db,settings) for _ in range(min(8,max(1,args.concurrency)))]
                    for future in futures:future.result()
        elif args.command=='prepare-pool':
            from .pool import prepare_pool
            report=prepare_pool(db,args.output,args.per_family,cache_dir=args.cache_dir)
            result={k:report[k] for k in ['selected','statuses']}
        elif args.command=="prepare-source":
            employer=db.employer(args.employer_id)
            if not employer:
                raise ValueError("Employer not found")
            data,url,_=fetch_public(args.url)
            text=page_text(data)
            claims=OpenAI(settings).extract(text,url,employer.name) if args.llm else []
            Path(args.output).write_text(json.dumps({"url":url,"source_text":text,"claims":claims,"review_status":"unreviewed"},indent=2)+"\n")
            result={"draft_saved":True,"claims":len(claims),"requires_operator_review":True}
        elif args.command=="review-source":
            source=json.loads(Path(args.source_json).read_text())
            result=review_source(db,args.employer_id,source["url"],source["source_text"],source["claims"],args.identity_reviewed)
        elif args.command=="import-taxonomy":
            concepts=[]
            with Path(args.path).open(newline="",encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    label=row.get("preferredLabel") or row.get("label")
                    identifier=row.get("conceptUri") or row.get("id") or row.get("code")
                    if label and identifier:
                        concepts.append(Concept(id=args.namespace+":"+identifier,label=label,aliases=(row.get("altLabels") or row.get("aliases") or "").split("\n"),activities=[],skills=[],backgrounds=[],related=[],version=args.version))
            if not concepts:
                raise ValueError("Expected preferredLabel/label and conceptUri/id/code columns")
            from .taxonomy import Taxonomy
            db.seed_taxonomy(Taxonomy(concepts));result={"concepts_imported":len(concepts),"version":args.version}
        elif args.command=="fetch-ons":
            from .taxonomies import fetch_ons
            result=fetch_ons(db,args.output)
        elif args.command=="verify-vacancy":
            from .vacancies import verify_vacancy
            result=verify_vacancy(db,args.employer_id,args.url,args.attribution_reviewed)
        elif args.command=="link-employers":
            from .identity import link_employers
            result=link_employers(db,args.canonical_id,args.duplicate_id,args.evidence_id,args.identity_reviewed)
        elif args.command=="schedule-refresh":
            rows=db.rows("select employer_id,kind,payload from sm.contact_channels where attribution='accepted' and state='found' and observed_at<now()-interval '30 days'")
            count=0
            for row in rows:
                payload={"employer_id":str(row["employer_id"]),"kind":row["kind"],"value":row["payload"]["value"]}
                key="refresh:"+str(row["employer_id"])+":"+row["kind"]+":"+time.strftime("%Y-%m-%d")
                count+=db.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'refresh_channel',%s,%s) on conflict(dedupe_key) do nothing",(str(uuid4()),key,Jsonb(payload)))
            result={"refreshes_queued":count}
            vacancies=db.rows("select employer_id,payload from (select distinct on(employer_id,payload->>'url') employer_id,payload,state,observed_at from sm.vacancy_observations order by employer_id,payload->>'url',observed_at desc nulls last) latest where state='open' and observed_at<now()-interval '24 hours'")
            for row in vacancies:
                payload={"employer_id":str(row["employer_id"]),"url":row["payload"]["url"]}
                key="vacancy:"+str(row["employer_id"])+":"+row["payload"]["url"]+":"+time.strftime("%Y-%m-%d")
                count+=db.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'refresh_vacancy',%s,%s) on conflict(dedupe_key) do nothing",(str(uuid4()),key,Jsonb(payload)))
            result={"refreshes_queued":count}
        elif args.command=="purge-expired":
            with db.transaction() as c:
                c.execute("delete from sm_private.match_sessions where expires_at<now()")
                count=c.execute("delete from sm_private.candidate_profiles where expires_at<now()").rowcount
                c.execute("delete from sm.query_cache where expires_at<now()")
            result={"expired_profiles_deleted":count}
        elif args.command=="status":
            result={"employers":db.one("select count(*) as n from sm.employers")["n"],"documents":db.one("select count(*) as n,(select count(*) from sm.search_index_documents e join sm.search_index_versions v on v.id=e.index_id where v.active and (e.embedding is not null or e.embedding_384 is not null)) as embedded from sm.search_documents"),"active_index":db.one("select id,model,dimensions,published_at from sm.search_index_versions where active"),"work":db.rows("select state,count(*) as n from sm.work_items group by state"),"official_snapshot":db.active_snapshot(),"demo_snapshot":db.active_snapshot(True)}
        if result is not None:
            print(json.dumps(result,indent=2,default=str))
    finally:
        db.close()


if __name__=="__main__":
    main()
