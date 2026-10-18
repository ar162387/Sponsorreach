"""Fictional local demo data, deliberately separate from official source records."""
from datetime import UTC,datetime
from uuid import uuid5,NAMESPACE_URL
from psycopg.types.json import Jsonb
from .models import Employer,Claim,Channel,Membership
from .intelligence import digest


def seed_demo(db,settings):
    if settings.environment=="production":
        raise ValueError("Demo fixtures are disabled in production")
    db.seed_taxonomy()
    at=datetime.now(UTC)
    snapshot=digest(["fictional-demo-register",at.date().isoformat()])
    db.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{active}','false') where kind='demo_register'")
    db.execute("insert into sm.source_artifacts(id,kind,namespace,url,sha256,publication_date,metadata) values(%s,'demo_register','demo:fictional','',%s,%s,%s) on conflict(id) do update set metadata=excluded.metadata",(snapshot,snapshot,at.date(),Jsonb({"active":True,"fictional":True})))
    samples=[
        ("Northstar Design Studio","Birmingham","Mechanical design and precision engineering using CAD and SolidWorks.","activity"),
        ("Meridian Manufacturing","Coventry","Manufacturing engineering and mechanical design for specialist equipment.","activity"),
        ("Fieldworks Engineering","Derby","Our mechanical engineers develop components using CAD and manufacturing processes.","function"),
        ("Forma Product Lab","Nottingham","Mechanical design and precision engineering for product development.","activity"),
        ("Pennine Systems","Sheffield","Mechanical engineering and manufacturing engineering consultancy.","activity"),
        ("Arc Technical Partners","Leeds","Technical sales and engineering sales services.","activity"),
        ("Ledger & Finch","Manchester","Accountancy, bookkeeping and tax advisory services with ACCA professionals.","activity"),
        ("Balance Accounting","Leeds","Accounting services and financial reporting for small businesses.","activity"),
        ("Quill Legal","Bristol","Legal services and contract law advice from our solicitors.","activity"),
        ("Cobalt Software","London","Software development with Python and TypeScript.","activity"),
        ("Beacon Analytics","Bristol","Data analytics and business intelligence services using SQL and statistics.","activity"),
        ("Harbour Nursing","Liverpool","Nursing care and nursing services from registered nurses.","activity"),
        ("Kite Creative","Brighton","Graphic design, visual design and branding services.","activity"),
        ("Amplify Studio","London","Digital marketing and content marketing services.","activity"),
        ("People Practice","Manchester","Human resources consulting and employee relations.","activity"),
    ]
    taxonomy=db.taxonomy()
    for i,(name,town,text,kind) in enumerate(samples):
        id=str(uuid5(NAMESPACE_URL,"sponsormatch:fictional:"+name))
        slug=name.casefold().replace(" ","-").replace("&","")
        url=f"https://{slug}.example/about"
        claim=Claim(id=digest([id,kind,text]),kind=kind,text=text,excerpt=text,source_url=url,observed_at=at,source_kind="demo",attribution="accepted")
        employer=Employer(id=id,name=name,town=town,identity_status="accepted",claims=[claim],channels=[Channel(kind="website",value=f"https://{slug}.example",source_url=url,observed_at=at,attribution="accepted"),Channel(kind="email",value=f"careers@{slug}.example",source_url=url,observed_at=at,attribution="accepted"),Channel(kind="careers",value=f"https://{slug}.example/careers",source_url=url,observed_at=at,attribution="accepted")],memberships=[Membership(route="Skilled Worker",rating="Worker (A rating)",snapshot_date=at.date().isoformat(),snapshot_id=snapshot,attribution="accepted")],source_namespace="demo:fictional",source_key=str(i),is_demo=True)
        db.save_employer(employer,taxonomy)
    return {"fictional_demo_employers":len(samples)}
