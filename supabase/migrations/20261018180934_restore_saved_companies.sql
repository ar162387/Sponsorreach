-- Preserve the old Save button's recorded choices when introducing bookmarks.
-- That endpoint already restricted saves to owner-authorized visible results.
insert into sm_private.employer_bookmarks(user_id,employer_id,session_id,result,created_at)
select distinct on (s.user_id,f.employer_id)
 s.user_id,f.employer_id,s.id,
 jsonb_build_object('group_name',r.group_name,'explanation',r.explanation),f.created_at
from sm_private.feedback_events f
join sm_private.match_sessions s on s.id=f.session_id
join sm_private.match_results r on r.session_id=s.id and r.employer_id=f.employer_id
where f.event='save' and s.user_id is not null and s.expires_at>now()
order by s.user_id,f.employer_id,f.created_at desc
on conflict(user_id,employer_id) do nothing;
