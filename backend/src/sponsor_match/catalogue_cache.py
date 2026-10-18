"""Compressed cache of public employer/taxonomy data, keyed by database and version.

No candidate, account, contact-click or session data enters this cache. Callers
must check current database versions before reusing employer records.
"""
import hashlib,json,os,sqlite3,zlib
from pathlib import Path
from contextlib import contextmanager
from psycopg.conninfo import conninfo_to_dict

TAXONOMY_SIGNATURE="select encode(extensions.digest(coalesce(string_agg(payload::text,',' order by id),''),'sha256'),'hex') signature from sm.concepts where kind='occupation'"

class CatalogueCache:
    def __init__(self,url):
        info=conninfo_to_dict(url)
        identity={k:info.get(k,'') for k in ['host','hostaddr','port','dbname','user']}
        self.scope=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        self.path=Path(os.getenv('SPONSORMATCH_CATALOGUE_CACHE',str(Path(__file__).resolve().parents[3]/'.local/catalogue-cache.sqlite3')))

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(self.path,timeout=5)
        try:
            c.execute('pragma journal_mode=wal')
            c.execute('create table if not exists records(scope text,kind text,record_key text,version text,payload blob,touched real default(unixepoch()),primary key(scope,kind,record_key))')
            with c:yield c
        finally:c.close()

    def get_many(self,kind,versions):
        if not versions:return {}
        result={};keys=list(versions)
        try:
            with self.connect() as c:
                for start in range(0,len(keys),800):
                    batch=keys[start:start+800]
                    rows=c.execute('select record_key,version,payload from records where scope=? and kind=? and record_key in ('+','.join('?' for _ in batch)+')',[self.scope,kind,*batch])
                    for key,version,payload in rows:
                        if version==versions[key]:
                            try:result[key]=json.loads(zlib.decompress(payload))
                            except (ValueError,zlib.error):pass
        except (OSError,sqlite3.Error):pass
        return result

    def put_many(self,kind,records):
        if not records:return
        try:
            packed=[(self.scope,kind,key,version,zlib.compress(json.dumps(payload,default=str).encode(),3)) for key,(version,payload) in records.items()]
            with self.connect() as c:
                c.executemany('insert into records(scope,kind,record_key,version,payload) values(?,?,?,?,?) on conflict(scope,kind,record_key) do update set version=excluded.version,payload=excluded.payload,touched=unixepoch()',packed)
                c.execute('delete from records where scope=? and kind=? and record_key in (select record_key from records where scope=? and kind=? order by touched desc,record_key limit -1 offset 10000)',(self.scope,kind,self.scope,kind))
        except (OSError,sqlite3.Error):pass
