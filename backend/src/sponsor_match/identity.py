from .intelligence import digest,merge_employers
from .ingest import reconcile_memberships
from .taxonomy import key


def link_employers(db,canonical_id,duplicate_id,evidence_id,reviewed=False):
    if canonical_id==duplicate_id or not reviewed:
        raise ValueError("Two distinct employers and reviewed identity evidence are required")
    canonical,duplicate=db.employer(canonical_id),db.employer(duplicate_id)
    if not canonical or not duplicate or canonical.is_demo or duplicate.is_demo:
        raise ValueError("Choose real imported employers")
    if canonical.company_number and duplicate.company_number and canonical.company_number!=duplicate.company_number:
        raise ValueError("Different company numbers cannot be merged")
    evidence=db.one("select employer_id from sm.observations where id=%s",(evidence_id,))
    if not evidence or str(evidence["employer_id"]) not in {canonical_id,duplicate_id}:
        raise ValueError("Reference a stored identity/source observation")
    merged=duplicate.model_copy(deep=True)
    merged.id=canonical_id
    merged.name=canonical.name;merged.town=canonical.town;merged.county=canonical.county
    merged.company_number=canonical.company_number or duplicate.company_number
    merged.identity_status=canonical.identity_status
    merged.memberships=canonical.memberships
    merged.source_namespace=canonical.source_namespace;merged.source_key=canonical.source_key
    with db.transaction() as c:
        c.execute("select id from sm.employers where id=any(%s::uuid[]) order by id for update",([canonical_id,duplicate_id],))
        # Retire duplicate retrieval immediately while retaining the audit row.
        duplicate.identity_status="quarantined"
        duplicate.version=digest(duplicate.model_dump(exclude={"version"}))
        from psycopg.types.json import Jsonb
        c.execute("update sm.employers set identity_status='quarantined',payload=%s,version=%s,updated_at=now() where id=%s",(Jsonb(duplicate.model_dump(mode="json")),duplicate.version,duplicate_id))
        c.execute("update sm.search_documents set published=false,sponsor_eligible=false where employer_id=%s",(duplicate_id,))
        c.execute("delete from sm.employer_concepts where employer_id=%s",(duplicate_id,))
        c.execute("delete from sm.accepted_claims where employer_id=%s",(duplicate_id,))
        c.execute("update sm.employer_source_keys set employer_id=%s where employer_id=%s",(canonical_id,duplicate_id))
        c.execute("insert into sm.employer_relationships values(%s,%s,'same_entity_reviewed',%s) on conflict do nothing",(canonical_id,duplicate_id,evidence_id))
    db.save_employer(merged)
    reconcile_memberships(db)
    return {"canonical_employer_id":canonical_id,"retired_duplicate_id":duplicate_id}
