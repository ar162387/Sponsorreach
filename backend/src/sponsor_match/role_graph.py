"""Versioned ESCO occupation → task → attributable employer-span graph.

All employer edges are derived, not facts about hiring. Build locally after a
catalogue import. Query-time work uses precomputed edges and the pinned encoder.
No occupation-specific keyword lists, graph database or paid model calls.
"""
from collections import Counter,defaultdict
from pathlib import Path
import gzip,json,os,hashlib,re
from difflib import SequenceMatcher
import numpy as np
from .intelligence import digest,accepted
from .onboarding import OnboardingLibrary
from .taxonomy import key,contains

VERSION='esco-task-graph-6'
RELATION_DUTIES=['Developing software applications and computer systems',
                'Teaching and training people, delivering education',
                'Selling, retailing and distributing products and supplies',
                'Representing members of an association',
                'Recruiting and supplying staff for other employers']


def relation_templates(task):
    return [f'Software tools for {task}',f'Training and education about {task}',
            f'Selling products and supplies for {task}',f'Membership association for {task}',
            f'Recruitment and staffing services for {task}']


def stem(word):
    # Language normalization, independent of occupation names.
    for _ in range(2):
        for suffix in ('ical','ing','ers','ics','ant','ist','er','or','s'):
            if word.endswith(suffix) and len(word)-len(suffix)>=4:
                word=word[:-len(suffix)];break
    return word


def root():
    return Path(os.getenv('SPONSORREACH_ROLE_GRAPH_DATA',str(Path(__file__).resolve().parents[3]/'data/role-graph')))


def file_hash(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def build(settings,prospect_folder,output):
    library=OnboardingLibrary(settings)
    if not library.load():raise ValueError('Build the ESCO onboarding bundle first')
    b=library.bundle
    if b['manifest']['version']!='esco-onboarding-3':raise ValueError('Occupation hierarchy, skill types and title vectors are required')
    folder=Path(prospect_folder)
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['model']!=settings.embedding_model:raise ValueError('Graph and employer encoders differ')
    terms=np.load(folder/'term-vectors.npz');vectors=terms['vectors'];ids=terms['term_ids'].tolist()
    with gzip.open(folder/'corpus.json.gz','rt') as f:corpus=json.load(f)
    frequency=Counter(link['id'] for r in b['occupations'] for link in r['skills'])
    task_edges={}; role_edges={}; activity_scores={}
    # Bounded matrix blocks; no 26k × skill-catalogue matrix retained in memory.
    for start in range(0,len(ids),256):
        block=vectors[start:start+256]
        skill_scores=block@b['skill_vectors'].T
        occupation_scores=block@b['roles'].T
        title_scores=block@b['title_vectors'].T
        for offset,tid in enumerate(ids[start:start+256]):
            term=corpus['terms'][tid]
            scores=skill_scores[offset]
            top=np.argpartition(-scores,min(15,len(scores)-1))[:16]
            task_edges[tid]=[[b['skills'][int(i)]['id'],round(float(scores[i]),5)] for i in top
                             if scores[i]>=.62 and frequency[b['skills'][int(i)]['id']]<=max(25,len(b['occupations'])*.035)]
            # Keep sparse occupation edges; broad text cannot enter every family.
            scores=occupation_scores[offset]
            top=np.argpartition(-scores,min(19,len(scores)-1))[:20]
            activity_scores[tid]={b['occupations'][int(i)]['id']:round(float(scores[i]),5) for i in top if scores[i]>=.35}
            if term['kind']=='role':
                scores=title_scores[offset]
                top=np.argpartition(-scores,min(7,len(scores)-1))[:8]
                best=int(np.argmax(scores));second=float(np.partition(scores,-2)[-2])
                role_edges[tid]={b['occupations'][best]['id']:round(float(scores[best]),5)} if scores[best]>=.86 and scores[best]-second>=.04 else {}
                exact=b['aliases'].get(key(term['text']))
                if exact is not None:role_edges[tid]={b['occupations'][exact]['id']:1.}
    from .providers import embedding_provider
    from .prospects import VectorStore
    provider=embedding_provider(settings)
    store=VectorStore(Path(output)/'relation-vectors.sqlite3',provider,settings.embedding_model)
    linked=sorted({sid for edges in task_edges.values() for sid,_ in edges})
    text=[text for sid in linked for text in relation_templates(b['skills'][b['skill_index'][sid]]['label'])]
    print('Encoding generic evidence relations:',len(text),flush=True)
    relation_vectors=store.encode(text,lambda n:print(json.dumps(n),flush=True)).reshape(len(linked),len(RELATION_DUTIES),settings.dimensions)
    relations={sid:i for i,sid in enumerate(linked)}
    for i,tid in enumerate(ids):
        for edge in task_edges[tid]:edge.append((relation_vectors[relations[edge[0]]]@vectors[i]).round(5).tolist())
    duties=np.asarray(provider.embeddings(RELATION_DUTIES),dtype=np.float32)
    permission_scores=b['roles']@duties.T
    permissions={r['id']:(permission_scores[i]>=.40).tolist() for i,r in enumerate(b['occupations'])}
    skill_competition=[]
    for start in range(0,len(b['skills']),256):
        scores=b['skill_vectors'][start:start+256]@b['roles'].T
        skill_competition.extend(np.max(scores,axis=1).tolist())
    payload={'terms':corpus['terms'],'observations':corpus['observations'],'tasks':task_edges,'roles':role_edges,'activities':activity_scores,'skill_competition':skill_competition,'relation_permissions':permissions}
    version=digest([VERSION,b['signature'],manifest['version'],payload])[:24]
    out=Path(output)/version;out.mkdir(parents=True,exist_ok=True)
    with gzip.open(out/'graph.json.gz','wt') as f:json.dump(payload,f)
    np.savez_compressed(out/'term-vectors.npz',vectors=vectors.astype(np.float16),ids=np.asarray(ids))
    result={'version':version,'algorithm':VERSION,'onboarding_version':b['signature'],'prospect_version':manifest['version'],
            'embedding_model':settings.embedding_model,'payload_hash':digest(payload),'employers':manifest['employers'],
            'occupations':len(b['occupations']),'skills':len(b['skills']),'observations':len(corpus['observations']),
            'task_edges':sum(map(len,task_edges.values())),'role_edges':sum(map(len,role_edges.values())),
            'compressed_hash':file_hash(out/'graph.json.gz'),'vectors_hash':file_hash(out/'term-vectors.npz')}
    (out/'manifest.json').write_text(json.dumps(result,indent=2))
    return {**result,'folder':str(out.resolve())}


class RoleGraph:
    def __init__(self,settings):
        self.library=OnboardingLibrary(settings);self.settings=settings;self.payload=None;self.version=None

    def load(self):
        pointer=root()/'active.json'
        if not pointer.exists():return False
        version=json.loads(pointer.read_text())['version']
        if self.version==version:return True
        if not self.library.load():return False
        folder=root()/version;manifest=json.loads((folder/'manifest.json').read_text())
        if manifest['embedding_model']!=self.settings.embedding_model or manifest['onboarding_version']!=self.library.bundle['signature']:
            raise ValueError('Graph encoder or taxonomy differs')
        if file_hash(folder/'graph.json.gz')!=manifest['compressed_hash'] or file_hash(folder/'term-vectors.npz')!=manifest['vectors_hash']:raise ValueError('Graph artifact changed')
        with gzip.open(folder/'graph.json.gz','rt') as f:payload=json.load(f)
        self.payload=payload;self.version=version
        self.occupations={r['id']:r for r in self.library.bundle['occupations']}
        self.word_frequency=Counter(stem(w) for r in self.occupations.values() for w in set(key(r['label']).split()))
        self.skill_frequency=Counter(t['id'] for r in self.occupations.values() for t in r['skills'])
        self.by_skill=defaultdict(set);self.by_role=defaultdict(set)
        for tid,edges in payload['tasks'].items():
            for edge in edges:self.by_skill[edge[0]].add(tid)
        for tid,edges in payload['roles'].items():
            for rid in edges:self.by_role[rid].add(tid)
        self.observations=defaultdict(list)
        for row in payload['observations']:self.observations[row['term_id']].append(row)
        arrays=np.load(folder/'term-vectors.npz');self.term_vectors=arrays['vectors']
        if self.term_vectors.shape!=(len(payload['terms']),self.settings.dimensions) or not np.isfinite(self.term_vectors).all():raise ValueError('Invalid graph vectors')
        self.term_index={tid:i for i,tid in enumerate(arrays['ids'].tolist())}
        return True

    def family(self,rid):
        found=set();pending=[rid]
        while pending:
            node=pending.pop()
            if node in found or node not in self.occupations:continue
            found.add(node);pending.extend(self.occupations[node].get('narrower',[]))
        return found

    def task_family(self,rid):
        # ISCO siblings support task interpretation, not automatic title equivalence.
        codes=self.isco_codes(rid)
        return self.family(rid)|{r['id'] for r in self.occupations.values() if codes.intersection(self.isco_codes(r['id']))}

    def isco_codes(self,rid,seen=None):
        seen=set() if seen is None else seen
        if rid in seen or rid not in self.occupations:return set()
        seen.add(rid);row=self.occupations[rid]
        return set(row.get('isco',[])).union(*(self.isco_codes(parent,seen) for parent in row.get('broader',[])))

    def professional_groups(self,rid):
        # Three-digit ISCO groups describe neighbouring work, not title aliases.
        return {code.rsplit('/',1)[-1][:4] for code in self.isco_codes(rid)}

    def resolve(self,label,vector):
        b=self.library.bundle;exact=b['aliases'].get(key(label))
        if exact is not None:return b['occupations'][exact]['id']
        if len(key(label))>=6:
            nearby={}
            for alias,i in b['aliases'].items():
                if abs(len(alias)-len(key(label)))>3:continue
                score=SequenceMatcher(None,key(label),alias).ratio()
                nearby[i]=max(nearby.get(i,0.),score)
            order=sorted(nearby,key=nearby.get,reverse=True)
            if order and nearby[order[0]]>=.90 and (len(order)<2 or nearby[order[0]]-nearby[order[1]]>=.04):return b['occupations'][order[0]]['id']
        scores=b['title_vectors']@vector;order=np.argsort(-scores)
        # Preserve unseen/ambiguous wording instead of assigning the closest label.
        if scores[order[0]]<.70 or scores[order[0]]-scores[order[1]]<.055:return None
        return b['occupations'][int(order[0])]['id']

    def retrieve(self,profile,vectors,skill_vectors=None,context_vector=None,skill_relation_vectors=None):
        """Return bounded employer candidates and auditable span-level paths."""
        support=defaultdict(dict);resolved={}
        raw_candidates=[]
        if skill_vectors is not None and len(skill_vectors) and context_vector is not None and skill_relation_vectors is not None:
            raw_scores=self.term_vectors@np.asarray(skill_vectors).T
            context_scores=self.term_vectors@np.asarray(context_vector)
            b=self.library.bundle;skill_scores=b['skill_vectors']@np.asarray(skill_vectors).T
            for tid,index in self.term_index.items():
                term=self.payload['terms'][tid];selected=int(np.argmax(raw_scores[index]));similarity=float(raw_scores[index,selected])
                if term['kind']!='activity' or similarity<.85 or context_scores[index]<.50:continue
                if len(key(profile.skills[selected].label).split())<2:continue
                nearest=int(np.argmax(skill_scores[:,selected]));sid=b['skills'][nearest]['id']
                # A named knowledge subject alone is not evidence that the
                # employer performs a practical task. It can still contribute
                # through the occupation/context gates below.
                if skill_scores[nearest,selected]>=.85 and b['skills'][nearest].get('type')=='knowledge':continue
                if skill_scores[nearest,selected]>=.60 and getattr(self,'skill_frequency',{}).get(sid,0)>30:continue
                relations=np.asarray(skill_relation_vectors[selected])@self.term_vectors[index]
                raw_candidates.append((tid,selected,similarity,relations))
        for intent,vector in zip(profile.role_intents,vectors):
            rid=self.resolve(intent.raw_label,np.asarray(vector,dtype=np.float32))
            interpreted=False
            if not rid and context_vector is not None:
                # An acronym or broad title does not veto explicit professional
                # context. This interpretation never changes the submitted title.
                b=self.library.bundle;scores=b['roles']@np.asarray(context_vector)
                title_scores=b['title_vectors']@np.asarray(vector)
                if float(np.max(title_scores))>=.50:scores=.6*scores+.4*title_scores
                order=np.argsort(-scores);best=int(order[0])
                if scores[best]>=.48 and (scores[best]-scores[order[1]]>=.025 or (len(profile.skills)>=2 and scores[best]>=.55)):
                    rid=b['occupations'][best]['id'];interpreted=True
            permitted=np.asarray(self.payload['relation_permissions'].get(rid,[False]*len(RELATION_DUTIES)),dtype=bool)
            for tid,selected,similarity,relations in raw_candidates:
                if (relations[~permitted]>similarity+.025).any():continue
                term=self.payload['terms'][tid]
                for obs in self.observations[tid]:
                    support[obs['employer_id']].setdefault(intent.raw_label,[]).append({**obs,
                        'span':obs.get('raw_span',term['text']),'term':term['text'],
                        'path':{'relation':'explicit_task','skill':profile.skills[selected].label,'similarity':similarity,'context_interpretation':not bool(rid)},
                        'raw_skill_alignment':similarity})
            if not rid:continue
            resolved[intent.raw_label]=rid;family=self.family(rid);task_family=self.task_family(rid)
            associations=defaultdict(list)
            for r in sorted(task_family):
                for s in self.occupations[r]['skills']:associations[s['id']].append((r,s['essential']))
            # A set iteration must never decide which relationship is retained.
            essential={sid:min(rows,key=lambda row:(row[0]!=rid,not row[1],row[0])) for sid,rows in associations.items()}
            family_frequency=Counter(t['id'] for r in task_family for t in self.occupations[r]['skills'])
            b=self.library.bundle;role_index={r['id']:i for i,r in enumerate(b['occupations'])}
            def usable_task(sid):
                skill=b['skills'][b['skill_index'][sid]]
                if skill.get('type')!='knowledge':return True
                # Knowledge subjects can support a core professional activity,
                # but shared background knowledge cannot create another function.
                words=[stem(w) for w in key(self.occupations[rid]['label']).split() if len(w)>3]
                if not words:return False
                frequency=getattr(self,'word_frequency',{})
                core=min(words,key=lambda w:frequency.get(w,0))
                return core in {stem(w) for w in key(skill['label']).split()}
            # A shared prerequisite (e.g. civil engineering in an environmental
            # profile) cannot establish that the employer performs the intended work.
            essential={sid:r for sid,r in essential.items() if
                usable_task(sid) and family_frequency[sid]/max(1,getattr(self,'skill_frequency',family_frequency)[sid])>=.10
                and max(float(b['skill_vectors'][b['skill_index'][sid]]@b['roles'][role_index[f]]) for f in task_family)
                >=self.payload['skill_competition'][b['skill_index'][sid]]-.18}
            user_scores=np.max(b['skill_vectors']@np.asarray(skill_vectors).T,axis=1) if skill_vectors is not None and len(skill_vectors) else None
            # Explicit technical/task skills narrow the work. Broad soft skills
            # do not become a universal route into every company.
            specific={sid for sid in essential if self.by_skill.get(sid) and user_scores is not None and user_scores[b['skill_index'][sid]]>=.62}
            skill_driven=bool(specific)
            # Tasks refine ranking without erasing strongly supported core work
            # solely because its source omits a narrower task description.
            tids=set().union(*(self.by_skill[s] for s in essential),*(self.by_role[r] for r in family))
            for tid in tids:
                term=self.payload['terms'][tid];bridge=None
                if term['kind']=='role':
                    matches=[(score,r) for r,score in self.payload['roles'].get(tid,{}).items() if r in family]
                    if not matches:continue
                    strength,occupation=max(matches);bridge={'relation':'occupation_title','occupation_id':occupation,'similarity':strength}
                else:
                    if len(key(term['text']).split())==1 and re.search(r'(?:ical|al|ic)$',key(term['text'])):continue
                    # Management is a function, not something established by a sector.
                    isco=self.isco_codes(rid)
                    if any(code.rsplit('/',1)[-1].startswith('C1') for code in isco):continue
                    scope=max((score for r,score in self.payload['activities'][tid].items() if r in task_family),default=0.)
                    if scope<.35:continue
                    groups=self.professional_groups(rid)
                    best_scope=max((score for other,score in self.payload['activities'][tid].items()
                                    if not groups.intersection(self.professional_groups(other))),default=0.)
                    strong_core=scope>=.45 and any(s in essential and essential[s][1] and score>=.75
                                    and b['skills'][b['skill_index'][s]].get('type')!='knowledge'
                                    for s,score,_ in self.payload['tasks'][tid])
                    if scope<.50 and scope<best_scope-.08 and not strong_core:continue
                    permitted=np.asarray(self.payload['relation_permissions'][rid],dtype=bool)
                    best_task=max((edge[1] for edge in self.payload['tasks'][tid]),default=0.)
                    matches=[(score,s) for s,score,relations in self.payload['tasks'][tid] if s in essential
                             and (not skill_driven or s in specific or (scope>=.45 and score>=.75 and b['skills'][b['skill_index'][s]].get('type')!='knowledge'))
                             and score>=best_task-.10
                             and (essential[s][1] or (scope>=.50 and score>=.65) or (skill_driven and scope>=.40 and score>=.68))
                             and (np.asarray(relations)[~permitted]<=score+.025).all()]
                    if not matches:continue
                    strength,sid=max(matches);occupation,is_essential=essential[sid]
                    bridge={'relation':'occupational_task','occupation_id':occupation,'skill_id':sid,'essential':is_essential,'similarity':strength,'scope_alignment':scope,
                            'context_interpretation':interpreted,'explicit_skill_alignment':float(user_scores[b['skill_index'][sid]]) if sid in specific else None}
                for obs in self.observations[tid]:
                    eid=obs['employer_id'];rows=support[eid].setdefault(intent.raw_label,[])
                    raw_alignment=float(np.max(np.asarray(skill_vectors)@self.term_vectors[self.term_index[tid]])) if skill_vectors is not None and len(skill_vectors) else 0.
                    rows.append({**obs,'span':obs.get('raw_span',term['text']),'path':bridge,'term':term['text'],'raw_skill_alignment':raw_alignment})
        ordered=sorted(support,key=lambda eid:(-max(s['path']['similarity'] for rows in support[eid].values() for s in rows),eid))[:1500]
        return ordered,{eid:support[eid] for eid in ordered},resolved

    def accepted_support(self,employer,rows):
        claims={c.id:c for c in employer.claims if accepted(c)};supported={}
        for label,paths in rows.items():
            valid=[]
            for path in paths:
                claim=claims.get(path['claim_id'])
                if not claim or path['employer_version']!=employer.version:continue
                if path['span'] not in claim.text or path['span'] not in claim.excerpt:continue
                valid.append(path)
            supported[label]=valid
        return supported

    def describe(self,path):
        relation=path['path']
        if relation['relation']=='explicit_task':return {'skill':relation['skill'],'relation':'explicit_task'}
        occupation=self.occupations[relation['occupation_id']]
        if relation['relation']=='occupation_title':return {'occupation':occupation['label'],'source_url':occupation['id'],'relation':'occupation_title'}
        b=self.library.bundle;skill=b['skills'][b['skill_index'][relation['skill_id']]]
        return {'occupation':occupation['label'],'source_url':occupation['id'],'skill':skill['label'],'relation':'occupational_task'}
