"""Frozen, pooled relevance evaluation. No model-generated ground truth or network IO."""
from collections import Counter, defaultdict
import math
import random
from statistics import mean
from .intelligence import digest

LABELS = {'unjudged', 'direct', 'related', 'insufficient_evidence', 'irrelevant', 'wrong_entity'}
FAILURES = {'wrong_entity', 'wrong_profession', 'weak_evidence', 'skill_ignored',
            'role_ambiguity', 'channel_issue', 'explanation_issue', 'ranking_order', 'other'}


def freeze(runs, depth=10):
    """Pool the same inputs across runs; hide run identity/position in review UI."""
    if depth < 1 or not runs:
        raise ValueError('Provide runs and a positive pooling depth')
    profiles = {}; pairs = {}; normalized = {}; source_versions={}
    for name, rows in sorted(runs.items()):
        seen = set(); normalized[name] = []
        for row in rows:
            pid = row['id']
            if pid in seen:
                raise ValueError('Duplicate profile in run: '+pid)
            seen.add(pid)
            profile = row['profile']; signature = digest(profile)
            if pid in profiles and profiles[pid]['profile_hash'] != signature:
                raise ValueError('A comparison changed its profile: '+pid)
            for field in ['catalogue','snapshot']:
                value=row.get('versions',{}).get(field)
                if value is not None:
                    if (pid,field) in source_versions and source_versions[pid,field]!=value:
                        raise ValueError('Compared runs changed their source snapshot: '+pid)
                    source_versions[pid,field]=value
            profiles[pid] = {'profile': profile, 'profile_hash': signature,
                             'family': row.get('family', pid.split(':')[0]),
                             'split': row.get('split', 'development')}
            results = row.get('results', [])
            ids = [r['employer_id'] for r in results]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate employer in ranking')
            direct = [r for r in results if r.get('group', 'direct') == 'direct'][:depth]
            related = [r for r in results if r.get('group') == 'related'][:depth]
            normalized[name].append({'id': pid, 'ranking': [r['employer_id'] for r in direct],
                                     'status':row.get('status','completed'),'error_type':row.get('error_type'),
                                     'related_ranking': [r['employer_id'] for r in related],
                                     'count': row.get('count', len(results)),
                                     'elapsed_ms': row.get('elapsed_ms'),
                                     'versions': row.get('versions', {}),
                                     'retrieval_ids': row.get('retrieval_ids'),
                                     'branch_ids': sorted({eid for branch in row.get('branches',[]) for eid in branch['employer_ids']} | set(row.get('graph_ids',[]))),
                                     'gate_rejections': row.get('gate_rejections')})
            for group in [direct, related]:
                for rank, result in enumerate(group, 1):
                    key = (pid, result['employer_id'])
                    pair = pairs.setdefault(key, {'profile_id': pid, 'employer_id': key[1],
                        'employer_name': result.get('name', result.get('employer_name', key[1])),
                        'profile': profile, 'contexts': {}})
                    pair['contexts'][name] = {'rank': rank, 'group': result.get('group', 'direct'),
                        'explanation': result.get('explanation', {}), 'claims': result.get('claims', []),
                        'channels': result.get('channels', []), 'versions': row.get('versions', {}),
                        'score': result.get('score'), 'features': result.get('features', {})}
    profile_sets = [{r['id'] for r in rows} for rows in normalized.values()]
    if any(ids != profile_sets[0] for ids in profile_sets):
        raise ValueError('Compared runs must contain exactly the same profiles')
    packet = []
    for key, pair in sorted(pairs.items()):
        packet.append({**pair, 'review_hash': digest(pair), 'label': 'unjudged',
                       'reviewer_type': None, 'reviewer_id': '', 'failure': '', 'note': '',
                       'explanation_supported': None, 'channel_useful': None,'task_fit':None})
    frozen = {'schema': 'relevance-lab-1', 'depth': depth, 'profiles': profiles,
              'runs': normalized, 'packet': packet}
    frozen['hash'] = digest(frozen)
    return frozen


def validate_reviews(frozen, reviews):
    expected = {(p['profile_id'], p['employer_id']): p for p in frozen['packet']}
    accepted = {}
    for review in reviews:
        pair = (review.get('profile_id'), review.get('employer_id')); original = expected.get(pair)
        if not original or review.get('review_hash') != original['review_hash']:
            raise ValueError('Stale or unknown review; use the exact frozen packet')
        if review.get('label') not in LABELS:
            raise ValueError('Unknown relevance label')
        if review.get('failure', '') not in FAILURES | {''}:
            raise ValueError('Unknown failure reason')
        if review.get('task_fit') not in {None,'specific','broad','contradicted'}:
            raise ValueError('Unknown explicit task fit')
        if review['label'] != 'unjudged' and (review.get('reviewer_type') not in {'human', 'ai_development'} or not isinstance(review.get('reviewer_id'),str) or not review['reviewer_id'].strip()):
            raise ValueError('Judgments require a reviewer ID and explicit reviewer type')
        for field in ['explanation_supported', 'channel_useful']:
            if review.get(field) is not None and type(review[field]) is not bool:
                raise ValueError('Support judgments must be boolean or unreviewed')
        value = {k: review.get(k) for k in ['profile_id', 'employer_id', 'review_hash', 'label',
            'reviewer_type', 'reviewer_id', 'failure', 'note', 'explanation_supported', 'channel_useful','task_fit']}
        if pair in accepted and accepted[pair] != value:
            raise ValueError('Conflicting duplicate reviews require adjudication')
        accepted[pair] = value
    return accepted


def per_query(ranking, pool, labels, k, task_labels=None):
    if k<1:raise ValueError('Metric depth must be positive')
    top = ranking[:k]; judged = [e for e in top if e in labels]
    good = sum(labels[e] == 'direct' for e in judged)
    complete_top = len(judged) == len(top)
    complete_pool = all(e in labels for e in pool)
    positives = {e for e in pool if labels.get(e) == 'direct'}
    gains = {'direct': 3, 'related': 1}
    ideal = sorted((gains.get(labels[e], 0) for e in pool if e in labels), reverse=True)[:k]
    idcg = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(ideal))
    dcg = sum((2**gains.get(labels.get(e), 0)-1)/math.log2(i+2) for i, e in enumerate(top))
    tasks_judged=task_labels is not None and complete_top and all(labels[e]!='direct' or task_labels.get(e) is not None for e in top)
    task_pool_judged=task_labels is not None and complete_pool and all(labels[e]!='direct' or task_labels.get(e) is not None for e in pool)
    def task_gain(e):return (7 if task_labels.get(e)=='specific' else 3 if task_labels.get(e)=='broad' else 0) if labels.get(e)=='direct' else 1 if labels.get(e)=='related' else 0
    task_ideal=sum(g/math.log2(i+2) for i,g in enumerate(sorted([task_gain(e) for e in pool],reverse=True)[:k])) if task_pool_judged else 0
    task_dcg=sum(task_gain(e)/math.log2(i+2) for i,e in enumerate(top)) if task_pool_judged else 0
    return {'precision_fixed_slots': good/k if complete_top else None,
            'precision_returned': good/len(top) if complete_top and top else None,
            'precision_lower_bound': good/k,
            'precision_upper_bound': (good+len(top)-len(judged))/k,
            'ndcg': dcg/idcg if complete_pool and idcg else None,
            'task_precision_fixed_slots':sum(labels[e]=='direct' and task_labels.get(e)=='specific' for e in top)/k if tasks_judged else None,
            'task_ndcg':task_dcg/task_ideal if task_ideal else None,
            'pool_recall_at_saved_depth': len(positives.intersection(ranking))/len(positives) if complete_pool and positives else None,
            'judged_items': len(judged), 'returned_items': len(top),
            'complete_pool': complete_pool, 'no_positive_in_judged_pool': complete_pool and not positives}


def aggregate(rows, names):
    return {name: {'value': mean([r[name] for r in rows if r[name] is not None]) if any(r[name] is not None for r in rows) else None,
                   'profiles': sum(r[name] is not None for r in rows)} for name in names}


def bootstrap_delta(values, seed=41, samples=2000):
    """Paired family-cluster bootstrap; diagnostic CI, never a promotion decision."""
    if not values:
        return {'delta': None, 'ci95': None, 'profiles': 0, 'families': 0}
    groups = defaultdict(list)
    for family, delta in values:
        groups[family].append(delta)
    keys = sorted(groups); rng = random.Random(seed)
    draws = sorted(mean([d for key in rng.choices(keys, k=len(keys)) for d in groups[key]]) for _ in range(samples))
    return {'delta': mean([d for _, d in values]),
            'ci95': [draws[int(.025*samples)], draws[min(samples-1, int(.975*samples))]] if len(keys) >= 2 else None,
            'profiles': len(values), 'families': len(keys),
            'small_sample_warning':len(keys)<20,
            'method': 'paired family-cluster bootstrap; development sample unless split says held_out'}


def score(frozen, reviews, reviewer_type='human', split=None):
    if reviewer_type not in {'human','ai_development'}:raise ValueError('Unknown reviewer type')
    if digest({k:v for k,v in frozen.items() if k!='hash'}) != frozen['hash']:
        raise ValueError('Frozen benchmark was modified')
    labels = validate_reviews(frozen, reviews)
    labels = {key: r for key, r in labels.items() if r['label'] != 'unjudged' and r['reviewer_type'] == reviewer_type}
    pools = defaultdict(set)
    for pair in frozen['packet']:
        pools[pair['profile_id']].add(pair['employer_id'])
    selected = {pid: p for pid, p in frozen['profiles'].items() if split is None or p['split'] == split}
    names = ['precision_fixed_slots', 'precision_returned', 'precision_lower_bound', 'precision_upper_bound', 'ndcg', 'task_precision_fixed_slots','task_ndcg','pool_recall_at_saved_depth']
    runs = {}; diagnostics = []; by_run = {}
    for name, all_rows in frozen['runs'].items():
        rows = [r for r in all_rows if r['id'] in selected]; query_scores = {}; slices = defaultdict(list)
        for row in rows:
            pid = row['id']; judgments = {eid: r['label'] for (p, eid), r in labels.items() if p == pid}
            task_labels={eid:r['task_fit'] for (p,eid),r in labels.items() if p==pid} if selected[pid]['profile'].get('skills') else None
            scores = {str(k): per_query(row['ranking'], pools[pid], judgments, k,task_labels) for k in [3, 10]}
            if not judgments or row['status']!='completed':
                # Empty results do not turn an entirely unjudged search into
                # a labelled negative. Availability is counted separately.
                for values in scores.values():
                    for metric in names:
                        if metric not in {'precision_lower_bound','precision_upper_bound'}:values[metric]=None
                    values['complete_pool']=False
            query_scores[pid] = scores; slices[selected[pid]['family']].append(pid)
            positives = {e for e in pools[pid] if judgments.get(e) == 'direct'}
            for eid in positives - set(row['ranking']):
                retrieved = row['retrieval_ids']
                stage = ('fusion_pruning' if eid in row['branch_ids'] else 'retrieval_miss') if retrieved is not None and eid not in retrieved else 'gate_rejection' if eid in (row['gate_rejections'] or {}) else 'ranking_or_saved_depth' if retrieved is not None else 'stage_not_instrumented'
                diagnostics.append({'run': name, 'profile_id': pid, 'employer_id': eid, 'failure': stage,
                                    'gate_reason':(row['gate_rejections'] or {}).get(eid)})
        by_run[name] = query_scores
        latencies = sorted(r['elapsed_ms'] for r in rows if r['elapsed_ms'] is not None)
        runs[name] = {'profiles': len(rows), 'abstentions': sum(not r['ranking'] and r['status']=='completed' for r in rows),
                      'failures':[{'profile_id':r['id'],'error_type':r['error_type']} for r in rows if r['status']!='completed'],
                      'with_three_results': sum(len(r['ranking']) >= 3 for r in rows),
                      'profiles_with_any_judgment':sum(any(p==r['id'] for p,_ in labels) for r in rows),
                      'latency_ms': {'p50': latencies[len(latencies)//2] if latencies else None,
                                     'p95': latencies[min(len(latencies)-1, math.ceil(.95*len(latencies))-1)] if latencies else None,
                                     'scope': 'local engine; caching may be warm; excludes HTTP and queue'},
                      'metrics': {str(k): aggregate([s[str(k)] for s in query_scores.values()], names) for k in [3, 10]},
                      'slices': {family: {str(k): aggregate([query_scores[pid][str(k)] for pid in ids], names) for k in [3, 10]} for family, ids in slices.items()},
                      'per_query': query_scores}
    comparisons = []
    ordered = list(runs)
    if ordered:
        baseline = ordered[0]
        for name in ordered[1:]:
            for k in [3, 10]:
                for metric in ['precision_fixed_slots', 'ndcg','task_precision_fixed_slots','task_ndcg']:
                    values = [(selected[pid]['family'], by_run[name][pid][str(k)][metric]-by_run[baseline][pid][str(k)][metric]) for pid in selected
                              if by_run[name][pid][str(k)][metric] is not None and by_run[baseline][pid][str(k)][metric] is not None]
                    paired_ids=[pid for pid in selected if by_run[name][pid][str(k)][metric] is not None and by_run[baseline][pid][str(k)][metric] is not None]
                    comparisons.append({'baseline': baseline, 'candidate': name, 'k': k, 'metric': metric,
                                        'baseline_paired_mean':mean(by_run[baseline][pid][str(k)][metric] for pid in paired_ids) if paired_ids else None,
                                        'candidate_paired_mean':mean(by_run[name][pid][str(k)][metric] for pid in paired_ids) if paired_ids else None,
                                        **bootstrap_delta(values)})
    relevant_labels = [r for (pid, _), r in labels.items() if pid in selected]
    support=[r['explanation_supported'] for r in relevant_labels if r['explanation_supported'] is not None]
    channels=[r['channel_useful'] for r in relevant_labels if r['channel_useful'] is not None]
    return {'schema': 'relevance-scorecard-1', 'status': 'evaluated' if relevant_labels else 'not_evaluated',
            'frozen_hash': frozen['hash'], 'reviewer_type': reviewer_type,
            'split': split or 'all', 'judged_pairs': len(relevant_labels), 'pool_pairs': sum(len(pools[pid]) for pid in selected),
            'labels': dict(Counter(r['label'] for r in relevant_labels)), 'runs': runs, 'comparisons': comparisons,
            'all_presentations_explanation_support':{'value':mean(support) if support else None,'reviewed_pairs':len(support)},
            'channel_usefulness':{'value':mean(channels) if channels else None,'reviewed_pairs':len(channels)},
            'wrong_entity_rate':mean(r['label']=='wrong_entity' for r in relevant_labels) if relevant_labels else None,
            'failure_counts': dict(Counter(r['failure'] for r in relevant_labels if r['failure'])), 'diagnostics': diagnostics,
            'review_failures':[r for r in relevant_labels if r['failure']],
            'release_ready': False,
            'limitations': ['Self-reported reviewers are not independently authenticated.',
                'AI development scores are not independent human validation.',
                'Pool recall is not catalogue recall; saved depth is not retrieval depth.',
                'NDCG requires the complete frozen pool judged and a positive gain.',
                'Fixed-slot precision counts unfilled slots; returned precision is reported separately.',
                'Promotion additionally requires held-out occupational coverage, identity, channel and explanation audits.']}


def agreement(frozen, first, second):
    """Cohen's nominal kappa and the exact pairs needing adjudication."""
    a=validate_reviews(frozen,first); b=validate_reviews(frozen,second)
    keys=[key for key in a.keys() & b.keys() if a[key]['label']!='unjudged' and b[key]['label']!='unjudged']
    if any(a[key]['reviewer_id']==b[key]['reviewer_id'] for key in keys):
        raise ValueError('Agreement requires distinct reviewer IDs')
    if not keys:return {'pairs':0,'agreement':None,'cohen_kappa':None,'disagreements':[]}
    ca=Counter(a[key]['label'] for key in keys);cb=Counter(b[key]['label'] for key in keys)
    observed=mean(a[key]['label']==b[key]['label'] for key in keys)
    chance=sum(ca[label]*cb[label] for label in LABELS)/len(keys)**2
    return {'pairs':len(keys),'agreement':observed,'cohen_kappa':(observed-chance)/(1-chance) if chance<1 else None,
            'reviewer_types':sorted({a[key]['reviewer_type'] for key in keys}|{b[key]['reviewer_type'] for key in keys}),
            'disagreements':[{'profile_id':p,'employer_id':e,'first':a[p,e],'second':b[p,e]} for p,e in sorted(keys) if a[p,e]['label']!=b[p,e]['label']]}
