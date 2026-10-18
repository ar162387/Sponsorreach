"""Replay reviewed, version-checked register-linkage repairs without merging IDs."""
import argparse,json
from pathlib import Path
from sponsor_match.config import Settings,embedding_column
from sponsor_match.db import Database
from sponsor_match.ingest import register_identity_attributable,reconcile_memberships,REGISTER_LINKAGE_VERSION
from sponsor_match.intelligence import digest
from sponsor_match.ranking import sponsor_valid
from sponsor_match.taxonomy import key


def factual_payload(employer):
    p=employer.model_dump(mode='json',exclude={'version','memberships'})
    for field in ['claims','channels','vacancies']:p[field]=sorted(p[field],key=lambda item:json.dumps(item,sort_keys=True))
    return p


def private_checks(db):
    # Keep identities and ownership tokens in memory only; reports contain
    # digests/counts, never private rows or account identifiers.
    sessions=db.rows("select to_jsonb(s)-'versions' payload from sm_private.match_sessions s order by id")
    results=db.rows('select to_jsonb(r) payload from sm_private.match_results r order by session_id,rank')
    return {'sessions':len(sessions),'results':len(results),'sessions_hash':digest(sessions),'results_hash':digest(results)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--proposal',required=True);p.add_argument('--model-folder',required=True)
    p.add_argument('--expected-snapshot',required=True);p.add_argument('--output',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    settings=Settings.from_env();db=Database(settings.database_url)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    try:
        db.pool.open(wait=True,timeout=30)
        snapshot=db.active_snapshot()
        if snapshot!=args.expected_snapshot:raise ValueError('Register snapshot changed; regenerate the proposal')
        expected=json.loads((Path(args.model_folder)/'employer-versions.json').read_text())
        proposal=json.loads(Path(args.proposal).read_text());ids=sorted(r['id'] for r in proposal['rows'] if r['decision']=='recoverable_register_linkage')
        if len(ids)!=len(set(ids)) or not ids:raise ValueError('Proposal must contain unique targets')
        employers={e.id:e for e in db.employers(ids)}
        if len(employers)!=len(ids):raise ValueError('A proposed employer is missing')
        pending=[];already=[]
        for eid in ids:
            e=employers[eid]
            if e.matching_basis!='provided_csv' or e.is_demo or e.identity_status!='accepted':raise ValueError('Target is outside accepted CSV identities')
            if sponsor_valid(e,snapshot):already.append(eid);continue
            if e.version!=expected.get(eid):raise ValueError('An employer version changed; re-review before repair')
            rows=db.rows('select payload from sm.register_entries where artifact_id=%s and name_key=%s and town_key=%s',(snapshot,key(e.name),key(e.town)))
            count=db.one("select count(*) n from sm.employers where name_key=%s and town_key=%s and not is_demo and identity_status<>'quarantined' and (identity_status='accepted' or company_number is not null)",(key(e.name),key(e.town)))['n']
            if not e.town or not rows or not register_identity_attributable(e.identity_status,e.county,[r['payload'].get('County','') for r in rows],count):raise ValueError('Current evidence does not support the proposed linkage')
            preview=e.model_copy(deep=True)
            preview.memberships=[m.model_copy(update={'attribution':'accepted'}) for m in preview.memberships]
            if not sponsor_valid(preview,snapshot):raise ValueError('Repair would not establish current policy-eligible membership')
            pending.append(eid)
        column=embedding_column(settings)
        index=db.one('select id from sm.search_index_versions where active')
        def vectors():
            return db.rows(f'select document_id,content_hash,md5({column}::text) vector_hash from sm.search_index_documents where index_id=%s and employer_id=any(%s::uuid[]) order by document_id',(index['id'],ids))
        before_private=private_checks(db);before_vectors=digest(vectors())
        backup={'policy_version':REGISTER_LINKAGE_VERSION,'snapshot':snapshot,'target_ids':ids,'employers':[employers[eid].model_dump(mode='json') for eid in ids],
                'membership_rows':db.rows('select * from sm.sponsor_memberships where employer_id=any(%s::uuid[]) order by employer_id,artifact_id,record_key',(ids,)),
                'index_id':str(index['id']),'vector_digest':before_vectors,'private_checks':before_private}
        backup_path=out/'before.json'
        if args.apply:
            if backup_path.exists():
                prior=json.loads(backup_path.read_text())
                if prior['snapshot']!=snapshot or prior['target_ids']!=ids:raise ValueError('Backup belongs to a different repair')
            else:
                backup_path.write_text(json.dumps(backup,default=str,indent=2));backup_path.chmod(0o600)
            reconcile_memberships(db,pending)
        if db.active_snapshot()!=snapshot:raise ValueError('Register changed during repair; do not publish this verification')
        after={e.id:e for e in db.employers(ids)};after_private=private_checks(db)
        verified=all(sponsor_valid(after[eid],snapshot) for eid in ids) if args.apply else False
        unchanged=all(factual_payload(employers[eid])==factual_payload(after[eid]) for eid in ids)
        same_vectors=before_vectors==digest(vectors());same_private=before_private==after_private
        if not unchanged or not same_vectors or not same_private:raise ValueError('Repair verification found an unexpected change; inspect the preserved backup')
        if args.apply and not verified:raise ValueError('Some targets remain ineligible after repair')
        result={'policy_version':REGISTER_LINKAGE_VERSION,'applied':args.apply,'snapshot':snapshot,'targets':len(ids),'newly_reconciled':len(pending) if args.apply else 0,'already_eligible':len(already),'eligible_after':verified,'business_facts_and_ids_unchanged':unchanged,'embeddings_unchanged':same_vectors,'private_sessions_and_results_unchanged':same_private,'employer_rows_merged_or_deleted':0}
        (out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    finally:db.close()


if __name__=='__main__':main()
