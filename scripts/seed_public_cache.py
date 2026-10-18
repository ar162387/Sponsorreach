"""Seed public cache from the prepared catalogue; remote versions remain authoritative."""
import psycopg,json
from sponsor_match.config import Settings
from sponsor_match.catalogue_cache import CatalogueCache,TAXONOMY_SIGNATURE
with psycopg.connect('postgresql://localhost:55432/sponsormatch') as c:
    cache=CatalogueCache(Settings.from_env().database_url)
    signature=c.execute(TAXONOMY_SIGNATURE).fetchone()[0]
    taxonomy=[r[0] for r in c.execute("select payload from sm.concepts where kind='occupation' order by id")]
    cache.put_many('taxonomy',{'active':(signature,taxonomy)})
    records={r[0]['id']:(r[0]['version'],r[0]) for r in c.execute("select payload from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")}
    with cache.connect() as disk:disk.execute("delete from records where scope=? and kind='employer'",(cache.scope,))
    cache.put_many('employer',records)
    print(json.dumps({'public_employers_cached':len(records),'taxonomy_concepts_cached':len(taxonomy),'private_records_cached':0}))
