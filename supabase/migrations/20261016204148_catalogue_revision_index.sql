-- Avoid a full employer heap scan on every match/cache-version lookup.
create index if not exists employer_catalogue_revision on sm.employers(updated_at desc);
