"""Experimental semantic professional alignment, independent of niche keyword lists.

Uses accepted claim spans and official occupation descriptions. This matcher is
for offline comparison until coverage AND relevance audits justify promotion.
"""
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
import gzip,json,re
import numpy as np
from .intelligence import accepted,digest
from .providers import embedding_provider
from .ranking import Ranked,QUALITY,sponsor_valid,usable_channels,interleave_intents
from .taxonomy import contains,key

VERSION='semantic-evidence-experiment-15'

RELATION_DUTIES=[
    'Professional technical services, specialist practice, research and consulting',
    'Training and education, teaching, tutoring and delivering education',
    'Selling and supplying merchandise, retailing goods, wholesaling and distributing products',
    'Membership association, representing members and providing membership services',
]


def occupation_relation_permissions(reference_vectors,duty_vectors):
    scores=reference_vectors@duty_vectors.T
    # Only strong occupational-duty support can relax a negative relation.
    # Weak distribution similarity is insufficient to treat product suppliers
    # as employers performing every activity associated with those products.
    permitted=(scores>=.40)&(scores>=scores[:,[0]]-.03)
    permitted[:,0]=True
    return permitted,scores


def unambiguous_aliases(references):
    aliases=defaultdict(set)
    for i,reference in enumerate(references):
        for label in [reference['label'],*reference.get('aliases',[])]:aliases[key(label)].add(i)
    return {label:next(iter(indices)) for label,indices in aliases.items() if len(indices)==1}


def underspecified_role_words(references):
    """Find generic fragments from occupation vocabulary, not a keyword list."""
    parents=defaultdict(set)
    exact=unambiguous_aliases(references)
    for reference in references:
        parent=reference['id'].rsplit(':',1)[-1][:4]
        for label in [reference['label'],*reference.get('aliases',[])]:
            for word in key(label).split():parents[word].add(parent)
    return {word for word,families in parents.items() if len(families)>=3 and word not in exact}


def ambiguous_unqualified_titles(references):
    """Learn omitted domain qualifiers from official aliases across families."""
    parents=defaultdict(set)
    for reference in references:
        parent=reference['id'].rsplit(':',1)[-1][:4]
        for title in [reference['label'],*reference.get('aliases',[])]:
            unqualified=key(re.sub(r'\([^)]*\)','',title))
            if unqualified:parents[unqualified].add(parent)
    return {title for title,families in parents.items() if len(families)>1}


def relation_templates(role):
    """Generic evidence relations; no profession vocabulary or employer rules."""
    return [f'{role} services and professional work',
            f'Training and education about {role}',
            f'Selling and supplying products for {role}',
            f'Membership association for {role}']


def activity_relation_mask(vectors, relation_vectors, margin=.08,permitted=None):
    scores=vectors@relation_vectors.T
    # Similar subject matter can describe teaching or merchandise rather than
    # performing the profession. Abstain when that relation is clearly stronger.
    permitted=np.asarray(permitted if permitted is not None else [True,False,False,False],dtype=bool)
    incompatible=np.where(permitted[1:],-np.inf,scores[:,1:])
    allowed=scores[:,0]+margin>=incompatible.max(axis=1)
    if not permitted[2]:allowed &= scores[:,0]+.04>=scores[:,2]
    return allowed,scores


def occupational_contrasts(labels,vectors,reference_vectors,parents,reference):
    """Discard counterfactuals that confidently preserve the same occupation."""
    retained=[]
    for label,vector in zip(labels,vectors):
        scores=reference_vectors@vector;best=int(np.argmax(scores))
        other=scores[parents!=parents[reference]]
        alternative=float(other.max()) if len(other) else -1.
        if best==reference and float(scores[reference])>=.60 and float(scores[reference])-alternative>=.025:continue
        retained.append((label,vector))
    return retained


class SemanticMatcher:
    ranking_version=VERSION
    def __init__(self,db,settings,model_folder):
        self.db,self.settings=db,settings;self.folder=Path(model_folder)
        self.manifest=json.loads((self.folder/'manifest.json').read_text())
        if self.manifest['model']!=settings.embedding_model:raise ValueError('Semantic model and query encoder must match')
        data=np.load(self.folder/'term-vectors.npz');self.vectors=data['vectors'];self.term_ids=data['term_ids'].tolist()
        self.references=json.loads((self.folder/'references.json').read_text());self.reference_vectors=np.load(self.folder/'reference-vectors.npz')['vectors']
        self.aliases=unambiguous_aliases(self.references)
        broad_words=underspecified_role_words(self.references)
        ambiguous_titles=ambiguous_unqualified_titles(self.references)
        with gzip.open(self.folder/'corpus.json.gz','rt') as f:corpus=json.load(f)
        self.terms=corpus['terms'];self.observations=defaultdict(list)
        for row in corpus['observations']:self.observations[row['term_id']].append(row)
        self.term_is_role=np.array([self.terms[tid]['kind']=='role' for tid in self.term_ids])
        self.term_is_broad=np.array([self.terms[tid]['kind']=='role' and key(self.terms[tid]['text']) in broad_words|ambiguous_titles for tid in self.term_ids])
        self.parents=np.array([r['id'].rsplit(':',1)[1][:4] for r in self.references])
        reference_scores=self.vectors@self.reference_vectors.T
        self.term_reference=np.argmax(reference_scores,axis=1)
        self.term_reference_score=np.max(reference_scores,axis=1)
        # Measure ambiguity across distinct occupation families, rather than
        # counting near-identical detailed occupations as competing concepts.
        margins=[]
        for start in range(0,len(self.term_ids),512):
            scores=reference_scores[start:start+512]
            own=self.parents[self.term_reference[start:start+512]]
            alternatives=np.where(self.parents[None,:]!=own[:,None],scores,-np.inf)
            margins.extend(self.term_reference_score[start:start+512]-alternatives.max(axis=1))
        self.term_reference_margin=np.asarray(margins)
        self.provider=embedding_provider(settings)
        from .role_information import RoleInformation
        self.role_information=RoleInformation(self.references,getattr(self.provider,'word_parts',None))
        duties=np.asarray(self.provider.embeddings(RELATION_DUTIES),dtype=np.float32)
        self.relation_permissions,self.relation_duty_scores=occupation_relation_permissions(self.reference_vectors,duties)
        from .prospects import VectorStore
        self.context_store=VectorStore(self.folder.parent/'claim-context-vectors.sqlite3',self.provider,settings.embedding_model)
        from .occupation_titles import TitleCompetition
        self.title_competition=TitleCompetition(self.folder,self.context_store,self.references,self.reference_vectors,self.term_ids,self.terms,self.vectors)

    def search(self,profile,progress=lambda _:None,audit=None):
        snapshot=self.db.active_snapshot()
        versions={'ranking':VERSION,'prospect_model':self.manifest['version'],'snapshot':snapshot,'embedding':self.settings.embedding_model}
        from .exposure_order import profile_tie_shortlist,source_tie_scores,SOURCE_VERSION
        versions['tie_order']=SOURCE_VERSION
        labels=[r.raw_label for r in profile.role_intents]
        generic_labels=[self.role_information.generic_labels(label) for label in labels]
        query=self.provider.embeddings(labels+[profile.search_text()]+[text for role in labels for text in relation_templates(role)]+[label for group in generic_labels for label in group])
        contexts=self.vectors@np.asarray(query[len(labels)],dtype=np.float32)
        candidates=defaultdict(lambda:defaultdict(list))
        generic_offset=len(labels)+1+sum(len(relation_templates(label)) for label in labels)
        for intent_index,(intent,vector) in enumerate(zip(profile.role_intents,query)):
            role_vector=np.asarray(vector,dtype=np.float32)
            role_scores=self.vectors@role_vector
            ontology_scores=self.reference_vectors@role_vector
            alias_ref=self.aliases.get(key(intent.raw_label))
            ref=alias_ref if alias_ref is not None else int(np.argmax(ontology_scores))
            count=len(generic_labels[intent_index])
            contrasts=occupational_contrasts(generic_labels[intent_index],np.asarray(query[generic_offset:generic_offset+count],dtype=np.float32),self.reference_vectors,self.parents,ref)
            generic_offset+=count
            specificity=role_scores-np.max(self.vectors@np.asarray([v for _,v in contrasts]).T,axis=1) if contrasts else None
            ref_confidence=1. if alias_ref is not None else float(ontology_scores[ref])
            permitted=self.relation_permissions[ref] if ref_confidence>=.50 else np.array([True,False,False,False])
            task_scores=self.vectors@self.reference_vectors[ref]
            same_family=self.parents[self.term_reference]==self.parents[ref]
            confident_other_family=(self.term_reference_score>=.55)&(ref_confidence>=.50)&(~same_family)
            role_eligible=self.term_is_role&((role_scores>=.70)|((role_scores>=.50)&same_family&(task_scores>=.48)))
            role_eligible &= ~self.term_is_broad
            if specificity is not None:role_eligible &= specificity>=-.04
            # A short role fragment must resolve to the intended profession.
            # High surface resemblance alone can confuse unrelated delivery,
            # officer or assistant functions. Strong direct titles remain usable.
            role_eligible &= (role_scores>=.70)|(same_family&(self.term_reference_score>=.48)&(self.term_reference_margin>=.025))
            role_eligible&=~(confident_other_family&(role_scores<.88))
            # A niche title may not resolve to the correct official family.
            # Preserve strong direct wording, as in the existing family gate;
            # a taxonomy disagreement cannot override near-exact role evidence.
            role_eligible &= (role_scores>=.88)|self.title_competition.mask(ref)
            activity_eligible=(~self.term_is_role)&((role_scores>=.57)|((role_scores>=.35)&(task_scores>=.50)&(ref_confidence>=.50)))
            # A shared field alone is insufficient: activity evidence must also
            # align with the occupation's actual work, not just its subject words.
            activity_eligible &= task_scores>=.45
            # Nearby occupation buckets often share a core activity. Reject
            # cross-family activity only with a meaningful alternative margin
            # and no strong direct wording alignment.
            activity_eligible &= ~(confident_other_family&(self.term_reference_score-task_scores>=.03)&(role_scores<.70))
            # SOC major group 1 identifies managerial occupations. A sector
            # activity alone does not establish a management function. Require
            # near-explicit occupational wording or an observed role/function.
            if self.parents[ref].startswith('1'):
                activity_eligible &= role_scores>=.80
            template_count=len(relation_templates(intent.raw_label))
            offset=len(labels)+1+intent_index*template_count
            relation_ok,relation_scores=activity_relation_mask(self.vectors,np.asarray(query[offset:offset+template_count],dtype=np.float32),permitted=permitted)
            activity_eligible &= relation_ok
            eligible=np.flatnonzero(role_eligible|activity_eligible)
            retrieval=.55*role_scores+.25*task_scores+.20*contexts
            eligible=eligible[np.argsort(-retrieval[eligible])[:1200]]
            for i in eligible:
                tid=self.term_ids[int(i)];term=self.terms[tid]
                for observation in self.observations[tid]:
                    eid=observation['employer_id'];alternatives=candidates[eid][intent.raw_label]
                    entry={'observation':observation,'span':observation.get('text',term['text']),'raw_span':observation.get('raw_span',term.get('raw_span',term['text'])),'kind':term['kind'],'role_similarity':float(role_scores[i]),'task_alignment':float(task_scores[i]),'context_similarity':float(contexts[i]),'retrieval':float(retrieval[i]),'occupation_reference':self.references[ref]['id'],'reference_index':ref,'relation_scores':relation_scores[i].tolist(),'permitted_relations':permitted.tolist(),'specificity_margin':float(specificity[i]) if specificity is not None else None,'generic_role_labels':[label for label,_ in contrasts],'title_competition':self.title_competition.features(i,ref)}
                    if not any(e['observation']['claim_id']==observation['claim_id'] and e['raw_span']==entry['raw_span'] for e in alternatives):
                        alternatives.append(entry)
                        alternatives.sort(key=lambda e:(-e['retrieval'],e['observation']['claim_id'],e['raw_span']))
                        del alternatives[8:]
        progress('Checking professional relevance')
        ids=sorted(candidates,key=lambda eid:(-max(e['retrieval'] for entries in candidates[eid].values() for e in entries),eid))[:1500]
        employers=self.db.employers(ids);results=[]
        context_texts=list(dict.fromkeys(c.text for e in employers for c in e.claims if accepted(c) and c.kind=='activity'))
        quoted_contexts=[]
        for employer in employers:
            accepted_by_id={c.id:c for c in employer.claims if accepted(c) and c.kind=='activity'}
            for entries in candidates[employer.id].values():
                for match in entries:
                    claim=accepted_by_id.get(match['observation']['claim_id'])
                    if claim and len(match['span'].split())==1 and match['observation']['employer_version']==employer.version and match['raw_span'] in claim.excerpt:
                        quoted_contexts.append(claim.excerpt)
        context_texts=list(dict.fromkeys([*context_texts,*quoted_contexts]))
        context_vectors=dict(zip(context_texts,self.context_store.encode(context_texts))) if context_texts else {}
        for employer in employers:
            if employer.is_demo or employer.identity_status!='accepted' or not sponsor_valid(employer,snapshot):continue
            channels=usable_channels(employer)
            if not channels:continue
            if profile.location.strict and employer.workplace_locations and not profile.location.relocate and profile.location.preferred_regions and not any(contains(loc,p) for loc in employer.workplace_locations for p in profile.location.preferred_regions):continue
            accepted_claims={c.id:c for c in employer.claims if accepted(c)}
            best=None
            for intent_index,intent in enumerate(profile.role_intents):
                for evidence_rank,match in enumerate(candidates[employer.id].get(intent.raw_label,[]),1):
                    if not match or match['observation']['employer_version']!=employer.version:continue
                    claim=accepted_claims.get(match['observation']['claim_id'])
                    if not claim or key(match['span']) not in key(claim.text) or match['raw_span'] not in claim.excerpt:continue
                    source_relations=None
                    whole_source_support=None
                    if claim.kind=='activity':
                        offset=len(labels)+1+intent_index*len(relation_templates(intent.raw_label))
                        allowed,source_scores=activity_relation_mask(np.asarray([context_vectors[claim.text]]),np.asarray(query[offset:offset+len(relation_templates(intent.raw_label))],dtype=np.float32),permitted=match['permitted_relations'])
                        if not allowed[0]:continue
                        source_relations=source_scores[0].tolist()
                        if len(match['span'].split())==1:
                            source_scores=self.reference_vectors@context_vectors[claim.excerpt]
                            ref=match['reference_index'];best_ref=int(np.argmax(source_scores))
                            task_support=float(source_scores[ref]);competition=float(source_scores[best_ref])-task_support
                            reference_alignment=float(self.reference_vectors[ref]@self.reference_vectors[best_ref])
                            if task_support<.30 and competition>.15 and reference_alignment<.40:continue
                            whole_source_support={'task_similarity':task_support,'competing_reference_margin':competition,'reference_alignment':reference_alignment}
                    explicit=list({key(s):s for s in [s.label for s in profile.skills]+profile.certifications}.values())
                    hits=[s for s in explicit if contains(match['span'],s)]
                    task=min(1.,len(hits)/3.)
                    preference=.5
                    if employer.workplace_locations and profile.location.preferred_regions:preference=float(any(contains(loc,p) for loc in employer.workplace_locations for p in profile.location.preferred_regions))
                    q=QUALITY[claim.source_kind];action=1. if any(c.kind in {'email','careers'} for c in channels) else .6
                    alignment=max(match['role_similarity'],match['task_alignment'])
                    score=q*(.40*alignment+.25*task+.20*max(0.,match['context_similarity'])+.10*preference)+.05*action
                    basis=claim.kind
                    prefix={'historical_role':'Recorded role history','function':'Recorded professional function','activity':'Recorded business activity'}[basis]
                    display_span=claim.text if claim.kind=='activity' and len(match['span'].split())<2 else match['span']
                    reason=f"{prefix}: {display_span.rstrip('. ')}. This work is related to your interest in {intent.raw_label.lower()}."
                    explanation={'text':reason,'basis':basis,'claim_ids':[claim.id],'evidence_ids':[digest(['claim',employer.id,claim.model_dump(mode='json')])],'sources':[{'url':claim.source_url,'excerpt':claim.excerpt,'matched_spans':[match['raw_span']],'kind':claim.source_kind,'observed_at':claim.observed_at.isoformat() if claim.observed_at else None}],'skill_hits':hits,'derived_relationship':{'kind':'semantic_professional_alignment','occupation_reference':match['occupation_reference'],'model_version':self.manifest['version'],'reviewed':False}}
                    features={'intent':intent.raw_label,'role':alignment,'task':task,'semantic':match['context_similarity'],'preference':preference,'quality':q,'action':action,'verified_matching_vacancy':False,'role_similarity':match['role_similarity'],'occupation_task_similarity':match['task_alignment'],'evidence_relation_scores':dict(zip(['professional_work','education_about','products_for','membership_for'],match['relation_scores'])),'source_context_relation_scores':source_relations,'evidence_alternative_rank':evidence_rank}
                    features.update(role_specificity_margin=match['specificity_margin'],generic_role_labels=match['generic_role_labels'],whole_source_support=whole_source_support)
                    features['title_competition']=match['title_competition']
                    result=Ranked(employer.id,'direct',score,features,explanation,employer.version)
                    if best is None or result.score>best.score:best=result
            if best:results.append(best)
        source_scores=source_tie_scores(results,np.asarray(query[len(labels)],dtype=np.float32),{e.id:e.name for e in employers},self.context_store)
        for result in results:
            result.features['source_context_tie_similarity']=source_scores.get(result.employer_id)
        shortlist=profile_tie_shortlist(results,profile,100,source_scores)
        if audit is not None:
            saved={r.employer_id for r in shortlist}
            audit.update(candidate_employers=len(candidates),retrieval_employer_cap=len(candidates)>1500,
                         eligible_before_shortlist_limit=len(results),
                         eligible_below_shortlist_limit=[r.employer_id for r in results if r.employer_id not in saved])
            if audit.get('include_eligible_results'):audit['eligible_results']=results
        return shortlist,'experimental_semantic_evidence',versions
