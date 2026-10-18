"""Locally built, source-backed onboarding choices. Never inferred qualifications."""
import gzip,json,os,re
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from pydantic import BaseModel,Field,field_validator
from .intelligence import digest
from .providers import embedding_provider
from .taxonomy import key

VERSION='esco-onboarding-3'


class SuggestionContext(BaseModel):
    text:str=Field(min_length=2,max_length=500)
    roles:list[str]=Field(default_factory=list,max_length=3)
    skills:list[str]=Field(default_factory=list,max_length=20)
    @field_validator('roles','skills')
    @classmethod
    def bounded_labels(cls,values):
        if any(not 1<=len(value)<=120 for value in values):raise ValueError('Invalid context label')
        return values


def root():return Path(os.getenv('SPONSORREACH_ONBOARDING_DATA',str(Path(__file__).resolve().parents[3]/'data/onboarding')))


def build(source,settings,output):
    with gzip.open(source,'rt') as f:data=json.load(f)
    occupations=[];skills={}
    for row in data['occupations']:
        links=row.get('_links',{});associations=[]
        for relation in ['hasEssentialSkill','hasOptionalSkill']:
            for skill in links.get(relation,[]):
                label=skill.get('title','').strip()
                if not 2<=len(label)<=100:continue
                skills[skill['uri']]={'id':skill['uri'],'label':label,'type':skill.get('skillType','').rsplit('/',1)[-1]}
                associations.append({'id':skill['uri'],'essential':relation=='hasEssentialSkill'})
        aliases=row.get('alternativeLabel',{}).get('en',[])
        if isinstance(aliases,str):aliases=aliases.split('\n')
        description=row.get('description',{}).get('en',{})
        if isinstance(description,dict):description=description.get('literal','')
        occupations.append({'id':row['uri'],'label':row['title'],'aliases':aliases,'description':description,
                            'skills':associations,
                            'narrower':[r['uri'] for r in links.get('narrowerOccupation',[])],
                            'broader':[r['uri'] for r in links.get('broaderOccupation',[])],
                            'isco':[r['uri'] for r in links.get('broaderIscoGroup',[])]})
    if not occupations or not skills:raise ValueError('ESCO snapshot lacks occupations or skill relationships')
    skills=sorted(skills.values(),key=lambda s:s['id']);occupations.sort(key=lambda r:r['id'])
    provider=embedding_provider(settings)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    previous=output/'vectors.npz'
    old_roles=json.loads((output/'occupations.json').read_text()) if (output/'occupations.json').exists() else []
    old_skills=json.loads((output/'skills.json').read_text()) if (output/'skills.json').exists() else []
    old_manifest=json.loads((output/'manifest.json').read_text()) if (output/'manifest.json').exists() else {}
    reusable=previous.exists() and old_manifest.get('embedding_model')==settings.embedding_model
    prior=np.load(previous) if reusable else {}
    role_vectors=prior['roles'] if reusable and [(r['id'],r['label'],r['description']) for r in old_roles]==[(r['id'],r['label'],r['description']) for r in occupations] else np.asarray(provider.embeddings([r['label']+'. '+r['description'][:900] for r in occupations]),dtype=np.float32)
    skill_vectors=prior['skills'] if reusable and [(s['id'],s['label']) for s in skills]==[(s['id'],s['label']) for s in old_skills] else np.asarray(provider.embeddings([s['label'] for s in skills]),dtype=np.float32)
    for name,rows in [('occupations.json',occupations),('skills.json',skills)]:
        (output/name).write_text(json.dumps(rows,ensure_ascii=False))
    title_vectors=prior['titles'] if reusable and 'titles' in prior and [r['label'] for r in old_roles]==[r['label'] for r in occupations] else np.asarray(provider.embeddings([r['label'] for r in occupations]),dtype=np.float32)
    np.savez_compressed(output/'vectors.npz',roles=role_vectors,skills=skill_vectors,titles=title_vectors)
    manifest={'version':VERSION,'source_version':data['requested_version'],'source_url':data['source_url'],
              'source_hash':digest(data),'embedding_model':settings.embedding_model,'occupations':len(occupations),
              'skills':len(skills),'occupation_hash':digest(occupations),'skill_hash':digest(skills)}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2));return manifest


class OnboardingLibrary:
    def __init__(self,settings):self.settings=settings;self.bundle=None
    def load(self):
        folder=root();path=folder/'manifest.json'
        if not path.exists():return False
        manifest=json.loads(path.read_text());signature=digest(manifest)
        if self.bundle and self.bundle['signature']==signature:return True
        if manifest['embedding_model']!=self.settings.embedding_model:raise ValueError('Onboarding encoder differs')
        occupations=json.loads((folder/'occupations.json').read_text());skills=json.loads((folder/'skills.json').read_text())
        if digest(occupations)!=manifest['occupation_hash'] or digest(skills)!=manifest['skill_hash']:raise ValueError('Onboarding artifact changed')
        vectors=np.load(folder/'vectors.npz');roles=vectors['roles'];skill_vectors=vectors['skills']
        if roles.shape!=(len(occupations),384) or skill_vectors.shape!=(len(skills),384) or not np.isfinite(roles).all() or not np.isfinite(skill_vectors).all():raise ValueError('Invalid onboarding vectors')
        aliases=defaultdict(set)
        preferred=defaultdict(set)
        for i,row in enumerate(occupations):
            preferred[key(row['label'])].add(i)
            for label in [row['label'],*row['aliases']]:aliases[key(label)].add(i)
        unambiguous={label:next(iter(ids)) for label,ids in aliases.items() if len(ids)==1}
        unambiguous.update({label:next(iter(ids)) for label,ids in preferred.items() if len(ids)==1})
        self.bundle={'signature':signature,'manifest':manifest,'occupations':occupations,'skills':skills,'roles':roles,
                     'title_vectors':vectors['titles'] if 'titles' in vectors else roles,
                     'skill_vectors':skill_vectors,'skill_index':{s['id']:i for i,s in enumerate(skills)},
                     'aliases':unambiguous,'skill_frequency':Counter(link['id'] for r in occupations for link in r['skills'])}
        return True

    def role_options(self, queries, vectors):
        """Occupation choices are independent of the employers already scraped."""
        b=self.bundle; options={}; by_id={r['id']:i for i,r in enumerate(b['occupations'])}
        for label,vector in zip(queries,vectors):
            scores=b.get('title_vectors',b['roles'])@vector; exact=b['aliases'].get(key(label))
            roots=[exact] if exact is not None else [int(i) for i in np.argsort(-scores)[:2] if scores[i]>=.55 and scores[i]>=scores.max()-.04]
            if not roots:continue
            for i in roots:
                row=b['occupations'][i]
                options[row['id']]={**row,'relation':'same_occupation' if exact==i else 'suggested_interest','rank':float(scores[i])+1}
                for child in row.get('narrower',[]):
                    if child in by_id:
                        r=b['occupations'][by_id[child]]
                        options.setdefault(child,{**r,'relation':'narrower_occupation','rank':float(scores[by_id[child]])+.4})
            # Nearby interests are choices, never silently substituted role intents.
            related_scores=b.get('title_vectors',b['roles'])@b.get('title_vectors',b['roles'])[exact] if exact is not None else scores
            for i in np.argsort(-related_scores)[:40]:
                if related_scores[i]<.45:continue
                row=b['occupations'][int(i)]
                overlap=0.
                if roots:
                    anchor=b['occupations'][roots[0]];a={s['id'] for s in anchor['skills']};other={s['id'] for s in row['skills']}
                    frequency=b.get('skill_frequency',{})
                    overlap=sum(1/max(1,frequency.get(s,1)) for s in a&other)/max(1e-9,sum(1/max(1,frequency.get(s,1)) for s in a|other))
                    same_family=bool(set(anchor.get('isco',[])).intersection(row.get('isco',[])))
                    if not same_family and (overlap<.035 or related_scores[i]<.55):continue
                options.setdefault(row['id'],{**row,'relation':'suggested_interest','rank':.65*float(related_scores[i])+.35*overlap})
        return [{'id':r['id'],'label':r['label'],'description':r['description'][:350],
                 'source_url':r['id'],'aliases':r.get('aliases',[])[:4],'relation':r['relation'],'requires_user_confirmation':True}
                for r in sorted(options.values(),key=lambda r:(-r['rank'],r['id']))[:10]]
    def suggest(self,context):
        empty={'skill_suggestions':[],'experience_prompts':[],'occupation_options':[]}
        if not self.load():return empty
        b=self.bundle;text=re.sub(r'https?://\S+|\S+@\S+','',context.text)
        queries=context.roles or [text];provider=embedding_provider(self.settings)
        vectors=np.asarray(provider.embeddings(queries+[text]),dtype=np.float32);selected=[]
        for i,label in enumerate(queries):
            if key(label) not in b['aliases'] and (len(key(label).split())==1 or float(np.max(b.get('title_vectors',b['roles'])@vectors[i]))<.70):
                combined=vectors[-1] if len(key(label).split())==1 else .3*vectors[i]+.7*vectors[-1]
                vectors[i]=combined/max(float(np.linalg.norm(combined)),1e-9)
        for label,vector in zip(queries,vectors):
            scores=.65*(b.get('title_vectors',b['roles'])@vector)+.35*(b['roles']@vector);exact=b['aliases'].get(key(label))
            choices=[exact] if exact is not None else [int(i) for i in np.argsort(-scores)[:2] if scores[i]>=.50 and scores[i]>=scores.max()-.035]
            for i in choices:
                if i not in selected:selected.append(i)
        anchors=list(selected)
        for i in anchors:
            occupation=b['occupations'][i];codes=set(occupation.get('isco',[]));children=set(occupation.get('narrower',[]))
            candidates=[j for j,r in enumerate(b['occupations']) if j not in selected and (codes.intersection(r.get('isco',[])) or r['id'] in children)]
            candidates.sort(key=lambda j:-float(b['roles'][j]@vectors[-1]))
            selected.extend(candidates[:5])
        chosen=[b['occupations'][i] for i in dict.fromkeys(selected)];pool={};existing={key(s) for s in context.skills}
        for order,occupation in enumerate(chosen):
            for relation in occupation['skills']:
                skill=b['skills'][b['skill_index'][relation['id']]]
                if key(skill['label']) in existing:continue
                score=float(b['skill_vectors'][b['skill_index'][skill['id']]]@vectors[-1])+.05*relation['essential']+.10*(skill.get('type')=='skill')
                item={**skill,'score':score,'occupation_order':order,'occupation':occupation['label'],
                      'source_url':occupation['id'],'requires_user_confirmation':True}
                if skill['id'] not in pool or score>pool[skill['id']]['score']:pool[skill['id']]=item
        ranked=sorted(pool.values(),key=lambda s:(-s['score'],s['id']))
        practical=[s for s in ranked if s.get('type') in {'skill','competence','skill/competence'}]
        if len(practical)>=6:
            first=practical[:6];ranked=first+[s for s in ranked if s not in first]
        # Interleave occupations so a second stated career interest remains visible.
        skills=[]
        while ranked and len(skills)<10:
            orders=set()
            for item in list(ranked):
                if item['occupation_order'] in orders:continue
                skills.append({k:v for k,v in item.items() if k not in {'score','occupation_order'}})
                ranked.remove(item);orders.add(item['occupation_order'])
                if len(skills)==10:break
        return {'skill_suggestions':skills,'experience_prompts':[{'label':s['label'],'prompt':'Describe a real project, job or placement where you used this: '+s['label']+'.','source_url':s['source_url']} for s in skills[:3]],
                'occupation_options':self.role_options(queries,vectors),
                'onboarding_version':b['signature'],'skill_source':'ESCO '+b['manifest']['source_version'],
                'qualification_claims':False}
