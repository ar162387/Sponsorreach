"""Corpus-derived prospect groups. This is discovery intelligence, not relevance labels.

Occupation descriptions and employer spans are data. Company identities never
enter the synthetic candidate's search text. Low similarities remain unmapped.
"""
from collections import Counter,defaultdict
from datetime import datetime,UTC
from pathlib import Path
import csv,gzip,io,json,re,sqlite3,zipfile,shutil,tempfile,errno
from threading import RLock
import numpy as np
from .intelligence import accepted,digest
from .models import Employer,Profile
from .ranking import role_segments
from .taxonomy import key
from .providers import embedding_provider

ALGORITHM='prospect-discovery-5'
ROLE_THRESHOLD=.55
ACTIVITY_THRESHOLD=.43


def descriptors(employer):
    for claim in employer.claims:
        if not accepted(claim) or claim.kind not in {'activity','function','historical_role'}:continue
        for span in role_segments(claim):
            text=re.sub(r'\s+',' ',span).strip(' []\"\'•-')
            if claim.kind in {'function','historical_role'}:
                text=re.split(r'\s+(?:[-–—|]|at)\s+',text,maxsplit=1)[0]
                text=re.sub(r'^(?:urgently hiring|hiring now|apply now)\s*:\s*','',text,flags=re.I)
                text=re.sub(r'\s+(?:jobs|vacancies|positions)$','',text,flags=re.I)
            if len(key(employer.name))>=5 and key(employer.name) in key(text):continue
            if not 3<=len(text)<=180 or not re.search('[A-Za-z]{3}',text) or re.search(r'https?://|\S+@\S+|\b\d{5,}\b',text):continue
            if key(text)==key(employer.name):continue
            yield {'text':text,'raw_span':span,'kind':'role' if claim.kind in {'function','historical_role'} else 'activity','claim_id':claim.id}


def occupation_references(taxonomy,archive):
    descriptions={}
    with zipfile.ZipFile(archive) as z:
        name=next(n for n in z.namelist() if n.lower().endswith('descriptions.csv'))
        data=z.read(name)
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:text=data.decode('cp1252')
        rows=list(csv.reader(io.StringIO(text)))
        for row in rows:
            if len(row)>7 and row[0].startswith('soc-'):
                code=(row[5] or row[4]).strip().replace('/','')
                if code and row[7].strip():descriptions['uk-soc-2020:'+code]=row[7].strip()
    # Detailed official occupations provide broad coverage without a hand-picked
    # list. Four-digit group buckets are retained only if no detailed group exists.
    official=[c for c in taxonomy.concepts if c.id.startswith('uk-soc-2020:')]
    parents={c.metadata.get('four_digit_parent') for c in official if len(c.id.rsplit(':',1)[1])>4}
    result=[]
    for c in official:
        if len(c.id.rsplit(':',1)[1])==4 and c.metadata.get('four_digit_parent') in parents:continue
        description=descriptions.get(c.id,'')
        if 'not elsewhere classified' in description.lower() and len(description)<200:continue
        result.append({'id':c.id,'label':c.label,'description':description,'aliases':c.aliases,'source_url':c.metadata.get('source_url',''),'source_version':c.version,'text':c.label+'. '+description[:1200]})
    return result


class VectorStore:
    def __init__(self,path,provider,model):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.provider=provider;self.model=model
    def encode(self,texts,progress=lambda _:None):
        result=np.empty((len(texts),384),dtype=np.float32)
        with sqlite3.connect(self.path) as c:
            c.execute('create table if not exists vectors(model text,text_hash text,vector blob,primary key(model,text_hash))')
            missing=[]
            for i,text in enumerate(texts):
                row=c.execute('select vector from vectors where model=? and text_hash=?',(self.model,digest(text))).fetchone()
                if row:result[i]=np.frombuffer(row[0],dtype=np.float32)
                else:missing.append(i)
            for start in range(0,len(missing),256):
                batch=missing[start:start+256];vectors=self.provider.embeddings([texts[i] for i in batch])
                if len(vectors)!=len(batch):raise ValueError('Embedding count does not match input count')
                for i,vector in zip(batch,vectors):
                    result[i]=np.asarray(vector,dtype=np.float32)
                    if not np.isfinite(result[i]).all() or not .9<=np.linalg.norm(result[i])<=1.1:raise ValueError('Expected finite normalized embeddings')
                    c.execute('insert or replace into vectors values(?,?,?)',(self.model,digest(texts[i]),result[i].tobytes()))
                c.commit();progress({'embedded_new':min(start+256,len(missing)),'missing_total':len(missing),'documents_total':len(texts)})
        return result


def profile_for(group,specialization=''):
    # This is an explicitly synthetic interest profile, not an inferred degree,
    # credential, career level or skill claim about a real user.
    background='Professional interest in '+group['label']
    return Profile.model_validate({'background':{'subject':background[:180],'specialization':specialization[:180]},'role_intents':[{'raw_label':group['label'][:120],'confirmed':True}],'career_stage':'experienced','experience_summary':'','skills':[],'certifications':[],'location':{'preferred_regions':[],'relocate':True},'related_roles_enabled':False})


def commit_snapshot(staging,final):
    staging,final=Path(staging),Path(final)
    try:staging.rename(final)
    except OSError as error:
        if error.errno not in {errno.EEXIST,errno.ENOTEMPTY} or not (final/'manifest.json').exists():raise
        existing=json.loads((final/'manifest.json').read_text())
        proposed=json.loads((staging/'manifest.json').read_text())
        if existing.get('version')!=proposed.get('version'):raise ValueError('Snapshot version collision')
        shutil.rmtree(staging)
    return json.loads((final/'manifest.json').read_text())


def build_model(db,settings,output,occupation_archive,progress=lambda _:None):
    if settings.dimensions!=384:raise ValueError('Prospect discovery currently requires the pinned 384-dimensional local encoder')
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    employers=db.employers([str(r['id']) for r in db.rows("select id from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv' order by id")])
    employers.sort(key=lambda e:e.id)
    references=occupation_references(db.taxonomy(),occupation_archive)
    if not employers or not references:raise ValueError('Real employers and official occupation references are required')
    corpus=[];terms={};counts=Counter()
    for employer in employers:
        for span in descriptors(employer):
            tid=digest([span['kind'],key(span['text'])]);terms.setdefault(tid,span);counts[tid]+=1
            corpus.append({'employer_id':employer.id,'employer_version':employer.version,'term_id':tid,'claim_id':span['claim_id'],'kind':span['kind'],'raw_span':span['raw_span'],'text':span['text']})
    ids=sorted(terms);store=VectorStore(root/'vectors.sqlite3',embedding_provider(settings),settings.embedding_model)
    ref_vectors=store.encode([r['text'] for r in references],progress)
    vectors=store.encode([terms[t]['text'] for t in ids],progress)
    groups={};term_groups={};mapping=[];group_terms=defaultdict(list)
    for start in range(0,len(ids),512):
        sims=vectors[start:start+512]@ref_vectors.T
        for offset,row in enumerate(sims):
            i=start+offset;tid=ids[i];term=terms[tid];best=int(np.argmax(row));score=float(row[best]);reference=references[best]
            threshold=ROLE_THRESHOLD if term['kind']=='role' else ACTIVITY_THRESHOLD
            if score>=threshold:
                gid=reference['id']
                groups.setdefault(gid,{'id':gid,'label':reference['label'][:120],'description':reference['description'],'reference_id':gid,'source_url':reference['source_url'],'source_version':reference['source_version'],'reference_index':best})
            elif term['kind']=='role' and score>=.38 and len(term['text'].split())>=2 and len(term['text'])<=120:
                gid='observed-role:'+digest(key(term['text']))[:20]
                groups.setdefault(gid,{'id':gid,'label':term['text'],'description':'Observed historical role wording. Occupational classification remains unresolved.','reference_id':None,'source_url':'','source_version':ALGORITHM,'reference_index':None,'term_index':i})
            else:continue
            term_groups[tid]=(gid,score);group_terms[gid].append((tid,score))
    # Use attributable observed role wording as display labels when available,
    # rather than presenting broad/plural coding buckets as individual job titles.
    for gid,group in groups.items():
        role_terms=[(tid,score) for tid,score in group_terms[gid] if terms[tid]['kind']=='role' and 3<=len(terms[tid]['text'])<=100]
        group['observed_roles']=[terms[tid]['text'] for tid,_ in sorted(role_terms,key=lambda item:(-item[1],-counts[item[0]],item[0]))[:20]]
        topical=sorted([(tid,score) for tid,score in group_terms[gid] if terms[tid]['kind']=='activity' and len(terms[tid]['text'])<=100],key=lambda x:(-x[1],-counts[x[0]],x[0]))
        group['specializations']=list(dict.fromkeys(terms[tid]['text'] for tid,_ in topical))[:8]
        group['evidence_kind']='derived_occupation_mapping' if group['reference_id'] else 'observed_historical_role'
    for observation in corpus:
        if observation['term_id'] not in term_groups:continue
        gid,score=term_groups[observation['term_id']]
        mapping.append({**observation,'group_id':gid,'similarity':round(score,5),'span':terms[observation['term_id']]['text'],'mapping_status':'derived_not_reviewed'})
    employer_groups=defaultdict(set)
    for item in mapping:employer_groups[item['group_id']].add(item['employer_id'])
    for gid,group in groups.items():group['employer_count']=len(employer_groups[gid])
    groups_sorted=sorted(groups.values(),key=lambda g:g['id']);group_vectors=[]
    for group in groups_sorted:
        group_vectors.append(ref_vectors[group['reference_index']] if group['reference_index'] is not None else vectors[group['term_index']])
        group.pop('reference_index',None);group.pop('term_index',None)
    versions={e.id:e.version for e in employers}
    version=digest([ALGORITHM,settings.embedding_model,versions,terms,[(r['id'],r['text']) for r in references],ROLE_THRESHOLD,ACTIVITY_THRESHOLD])[:24]
    final_folder=root/version
    if (final_folder/'manifest.json').exists():
        prior=json.loads((final_folder/'manifest.json').read_text())
        if all((final_folder/name).exists() for name in ['groups.json','group-vectors.npz','term-vectors.npz','reference-vectors.npz','references.json','links.json.gz','corpus.json.gz','employer-versions.json']):
            return {**prior,'folder':str(final_folder.resolve()),'reused':True}
        raise ValueError('An existing prospect snapshot is incomplete; retain it for inspection before rebuilding')
    folder=Path(tempfile.mkdtemp(prefix='.building-',dir=root))
    np.savez_compressed(folder/'group-vectors.npz',vectors=np.asarray(group_vectors,dtype=np.float32))
    np.savez_compressed(folder/'term-vectors.npz',vectors=vectors,term_ids=np.asarray(ids))
    np.savez_compressed(folder/'reference-vectors.npz',vectors=ref_vectors)
    (folder/'references.json').write_text(json.dumps(references))
    (folder/'groups.json').write_text(json.dumps(groups_sorted,indent=2))
    with gzip.open(folder/'links.json.gz','wt') as f:json.dump(mapping,f)
    with gzip.open(folder/'corpus.json.gz','wt') as f:json.dump({'terms':terms,'observations':corpus},f)
    (folder/'employer-versions.json').write_text(json.dumps(versions))
    summary={'version':version,'algorithm':ALGORITHM,'model':settings.embedding_model,'dimensions':384,'employers':len(employers),'employers_with_mappings':len({m['employer_id'] for m in mapping}),'groups':len(groups_sorted),'terms':len(terms),'observations':len(corpus),'links':len(mapping),'reference_occupations':len(references),'role_threshold':ROLE_THRESHOLD,'activity_threshold':ACTIVITY_THRESHOLD,'created_at':datetime.now(UTC).isoformat(),'validated_relevance':False,'source_hash':digest(versions)}
    (folder/'manifest.json').write_text(json.dumps(summary,indent=2))
    summary=commit_snapshot(folder,final_folder)
    progress(summary)
    return {**summary,'folder':str(final_folder.resolve())}


def model_root():
    import os
    return Path(os.getenv('SPONSORMATCH_PROSPECT_MODELS',str(Path(__file__).resolve().parents[3]/'data/prospects')))


def active_pointer(settings):
    from .catalogue_cache import CatalogueCache
    return model_root()/('active-'+CatalogueCache(settings.database_url).scope+'.json')


def publish_model(db,settings,folder):
    folder=Path(folder).resolve();manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['model']!=settings.embedding_model or manifest['dimensions']!=settings.dimensions:raise ValueError('Prospect model encoder does not match this application')
    current={str(r['id']):r['version'] for r in db.rows("select id,version from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")}
    if digest(current)!=manifest['source_hash']:raise ValueError('Employer versions changed; rebuild before publishing prospect suggestions')
    # Validate all referenced artifacts before switching the pointer.
    groups=json.loads((folder/'groups.json').read_text());vectors=np.load(folder/'group-vectors.npz')['vectors']
    if len(groups)!=manifest['groups'] or vectors.shape!=(len(groups),settings.dimensions) or not np.isfinite(vectors).all():raise ValueError('Incomplete prospect model')
    references=json.loads((folder/'references.json').read_text())
    reference_ids={r['id'] for r in references if r.get('label') and isinstance(r.get('aliases',[]),list)}
    if not reference_ids or any(g.get('reference_id') and g['reference_id'] not in reference_ids for g in groups):raise ValueError('Incomplete occupation reference data')
    target=active_pointer(settings);target.parent.mkdir(parents=True,exist_ok=True)
    from uuid import uuid4
    temp=target.with_name(target.name+'.'+uuid4().hex+'.tmp');temp.write_text(json.dumps({'version':manifest['version'],'folder':str(folder)}));temp.replace(target)
    refresh_key=enqueue_cohort_refresh(db,manifest['version'])
    return {'published_prospect_version':manifest['version'],'groups':len(groups),'usage':'career_ideas_not_validated_employer_matches','cohort_refresh_queued':refresh_key}


COHORT_VERSION='prospect-cohorts-2'


class ProspectLibrary:
    def __init__(self,settings):
        self.settings=settings;self.version=None;self.groups=[];self.vectors=None;self.manifest={};self._bundle=None;self._cohort_bundle=None;self._lock=RLock()
    def load(self):
        pointer=active_pointer(self.settings)
        if not pointer.exists():return False
        meta=json.loads(pointer.read_text())
        if meta['version']==self.version:return True
        folder=Path(meta['folder']);manifest=json.loads((folder/'manifest.json').read_text())
        if manifest['model']!=self.settings.embedding_model:return False
        groups=json.loads((folder/'groups.json').read_text());vectors=np.load(folder/'group-vectors.npz')['vectors']
        if vectors.shape!=(len(groups),self.settings.dimensions) or not np.isfinite(vectors).all():return False
        aliases=defaultdict(set)
        for reference in json.loads((folder/'references.json').read_text()):
            for label in [reference['label'],*reference.get('aliases',[])]:aliases[key(label)].add(reference['id'])
        group_ids={g['id'] for g in groups}
        aliases={label:next(iter(ids)) for label,ids in aliases.items() if len(ids)==1 and next(iter(ids)) in group_ids}
        self.version,self.groups,self.vectors,self.manifest=meta['version'],groups,vectors,manifest
        self._bundle=(self.version,groups,vectors,manifest)
        self._cohort_bundle=(self.version,groups,vectors,aliases)
        return True

    def associate(self,profile):
        """Versioned interest cohorts; never candidate skills or access rules."""
        unavailable={'available':False,'algorithm':COHORT_VERSION,'assignments':[]}
        if self.settings.embedding_provider!='local':return unavailable
        with self._lock:
            if not self.load():return unavailable
            version,groups,vectors,aliases=self._cohort_bundle
        result={'available':True,'algorithm':COHORT_VERSION,'model_version':version,'assignments':[],
                'basis':'derived_professional_interests','qualification_claim':False}
        confirmed=[r for r in profile.role_intents if r.confirmed]
        if not confirmed:return result
        encoded=np.asarray(embedding_provider(self.settings).embeddings([r.raw_label for r in confirmed]+[profile.search_text()]),dtype=np.float32)
        by_id={g['id']:g for g in groups}
        observed={key(g['label']):g for g in groups if not g['reference_id'] and g['employer_count']>=2}
        for i,intent in enumerate(confirmed):
            exact=aliases.get(key(intent.raw_label))
            if exact:
                group=by_id[exact];basis='official_occupation_alias'
            elif key(intent.raw_label) in observed:
                group=observed[key(intent.raw_label)];basis='observed_role_exact_label'
            else:
                vector=.85*encoded[i]+.15*encoded[-1];norm=np.linalg.norm(vector)
                if not np.isfinite(vector).all() or norm<=0:raise ValueError('Invalid cohort query vector')
                scores=vectors@(vector/norm)
                admissible=[j for j,g in enumerate(groups) if g['reference_id'] and float(scores[j])>=.50]
                admissible.sort(key=lambda j:(-float(scores[j]),groups[j]['id']))
                if not admissible or (len(admissible)>1 and float(scores[admissible[0]]-scores[admissible[1]])<.025):
                    result['assignments'].append({'intent':intent.raw_label,'status':'unresolved'})
                    continue
                group=groups[admissible[0]];basis='semantic_proximity'
            result['assignments'].append({'intent':intent.raw_label,'status':'associated','group_id':group['id'],
                                          'label':group['label'],'association_basis':basis,'derived':True})
        return result
    def suggest(self,text,limit=6):
        text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://\S+','',text).strip()
        with self._lock:
            if len(text)<2 or not self.load():return {'available':False,'suggestions':[]}
            version,groups,vectors,manifest=self._bundle
        vector=np.asarray(embedding_provider(self.settings).embeddings([text])[0],dtype=np.float32)
        scores=vectors@vector;chosen=[];seen=set()
        admissible=[i for i,g in enumerate(groups) if (g['reference_id'] is not None and (g['observed_roles'] or g['employer_count']>=2)) or (g['reference_id'] is None and g['employer_count']>=2 and float(scores[i])>=.65)]
        if not admissible:return {'available':True,'model_version':version,'suggestions':[]}
        cutoff=max(.42,max(float(scores[i]) for i in admissible)-.10)
        for i in np.argsort(-scores):
            g=groups[int(i)];score=float(scores[i]);label=key(g['label'])
            if score<cutoff:break
            if label in seen:continue
            if g['reference_id'] is None and (g['employer_count']<2 or score<.65):continue
            if not g['observed_roles'] and g['employer_count']<2:continue
            seen.add(label)
            chosen.append({'group_id':g['id'],'label':g['label'],'description':g['description'][:350],'specializations':g['specializations'][:4],'source_url':g['source_url'],'basis':'career_idea_from_recorded_employer_evidence','requires_user_confirmation':True})
            if len(chosen)>=min(8,max(1,limit)):break
        return {'available':True,'model_version':version,'suggestions':chosen,'notice':'Career ideas based on recorded employer activities and roles. Choose the interests that describe you; these suggestions do not assert that you hold skills or qualifications.'}


def enqueue_refresh(db,index_version):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    key='prospect-refresh:'+str(index_version)
    db.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'build_prospects',%s,%s) on conflict(dedupe_key) do nothing",(str(uuid4()),key,Jsonb({'index_version':str(index_version)})))
    return key


def cohort_report(db):
    """Operator-only aggregates; do not export owner or candidate identifiers."""
    rows=db.rows("select profile_id,user_id,owner_hash,versions->'prospect_cohorts' cohorts from sm_private.match_sessions where status='ready' and expires_at>now()")
    buckets={};owners=set();with_analysis=0;unresolved=0
    for row in rows:
        owner=('account',str(row['user_id'])) if row['user_id'] else ('anonymous',row['owner_hash'])
        owners.add(owner);cohorts=row['cohorts'] or {}
        if not cohorts.get('available'):continue
        with_analysis+=1
        if any(a.get('status')=='unresolved' for a in cohorts.get('assignments',[])):unresolved+=1
        for assignment in cohorts.get('assignments',[]):
            if assignment.get('status')!='associated':continue
            key=(cohorts['model_version'],assignment['group_id'])
            bucket=buckets.setdefault(key,{'model_version':key[0],'group_id':key[1],'label':assignment['label'],'profiles':set(),'owners':set()})
            bucket['profiles'].add(str(row['profile_id']));bucket['owners'].add(owner)
    groups=[{k:v for k,v in b.items() if k not in {'profiles','owners'}}|{'profile_count':len(b['profiles']),'owner_count':len(b['owners'])} for b in buckets.values()]
    return {'scope':'operator_private_aggregate','ready_sessions':len(rows),'distinct_owners':len(owners),
            'sessions_with_analysis':with_analysis,'sessions_without_analysis':len(rows)-with_analysis,
            'sessions_with_unresolved_interests':unresolved,'groups':sorted(groups,key=lambda r:(r['model_version'],-r['owner_count'],r['group_id'])),
            'qualification_claims':False,'owner_identifiers_exported':False}


def refresh_cohorts(db,settings,limit=100,expected_version=None,library=None,session_ids=None):
    """Refresh private interest analysis while preserving every ranked result."""
    from psycopg.types.json import Jsonb
    if settings.embedding_provider!='local':return {'status':'local_encoder_required','updated':0}
    library=library or ProspectLibrary(settings)
    with library._lock:
        if not library.load():return {'status':'no_active_model','updated':0}
        version=library.version
    if expected_version and expected_version!=version:return {'status':'obsolete_model','updated':0}
    rows=db.rows("""select s.id,s.profile_id,p.profile from sm_private.match_sessions s
        join sm_private.candidate_profiles p on p.id=s.profile_id
        where s.status='ready' and s.expires_at>now()
        and (%s::uuid[] is null or s.id=any(%s::uuid[]))
        and (coalesce(s.versions->'prospect_cohorts'->>'model_version','')<>%s
             or coalesce(s.versions->'prospect_cohorts'->>'algorithm','')<>%s)
        order by s.id limit %s""",(session_ids,session_ids,version,COHORT_VERSION,max(1,min(1000,limit))))
    updated=0
    for row in rows:
        analysis=library.associate(Profile.model_validate(row['profile']))
        if not analysis.get('available') or analysis.get('model_version')!=version:
            return {'status':'model_changed','updated':updated,'model_version':version}
        # Recheck the active pointer before writing an older-model result.
        with library._lock:
            if not library.load() or library.version!=version:
                return {'status':'model_changed','updated':updated,'model_version':version}
        with db.transaction() as c:
            saved=c.execute("select versions from sm_private.match_sessions where id=%s and profile_id=%s and status='ready' and expires_at>now() for update",(row['id'],row['profile_id'])).fetchone()
            if not saved:continue
            versions=dict(saved['versions'] or {});previous=versions.get('prospect_cohorts',{})
            if previous.get('model_version')==version and previous.get('algorithm')==COHORT_VERSION:continue
            history=dict(versions.get('prospect_cohort_history',{}))
            if previous.get('available') and previous.get('model_version'):
                history.setdefault(previous.get('algorithm','unknown')+':'+previous['model_version'],previous)
            versions.update(prospect_cohorts=analysis,prospect_cohort_history=history)
            c.execute('update sm_private.match_sessions set versions=%s where id=%s',(Jsonb(versions),row['id']))
            updated+=1
    return {'status':'updated','model_version':version,'updated':updated,'batch_full':len(rows)>=max(1,min(1000,limit))}


def enqueue_cohort_refresh(db,model_version):
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    key='cohort-refresh:'+COHORT_VERSION+':'+model_version
    db.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'refresh_prospect_cohorts',%s,%s) on conflict(dedupe_key) do nothing",(str(uuid4()),key,Jsonb({'model_version':model_version})))
    return key
