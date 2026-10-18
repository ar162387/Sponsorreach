-- A claim has a stable application ID and a separate immutable evidence version.
alter table sm.accepted_claims add column observation_id text;
update sm.accepted_claims set observation_id=id;
alter table sm.accepted_claims alter column observation_id set not null;
alter table sm.accepted_claims add constraint accepted_claim_observation
 foreign key(observation_id) references sm.observations(id);
alter table sm.accepted_claims drop constraint accepted_claims_id_fkey;
alter table sm.employer_concepts drop constraint employer_concepts_claim_id_fkey;
alter table sm.employer_concepts add constraint employer_concept_claim
 foreign key(claim_id) references sm.accepted_claims(id);
