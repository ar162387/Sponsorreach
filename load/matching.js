import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const ready = new Trend('match_ready_ms');
const completed = new Rate('match_completed');
const prospects = JSON.parse(open(__ENV.PROSPECTS_FILE));
export const options = {
  vus: Number(__ENV.LOAD_VUS || 2), duration: __ENV.LOAD_DURATION || '15s',
  thresholds: { checks: ['rate==1'], match_completed: ['rate==1'], match_ready_ms: ['p(95)<3000'], http_req_failed: ['rate<0.01'] },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
};

export default function () {
  const token = `${__ENV.LOAD_RUN_ID}-${__VU}-${__ITER}`.padEnd(64, '0');
  const headers = { 'Content-Type': 'application/json', 'X-API-Secret': __ENV.LOAD_API_SECRET, 'X-Session-Token': token };
  const profile = prospects[(__ITER * Number(__ENV.LOAD_VUS || 2) + __VU - 1) % prospects.length].profile;
  // Unique synthetic summary exercises uncached requests; no personal data or emails sent.
  profile.experience_summary = `Synthetic load probe ${__ENV.LOAD_RUN_ID} ${__VU} ${__ITER}`;
  const body = { profile, identity: { name: 'Synthetic load probe', email: `load-${__ENV.LOAD_RUN_ID}@example.invalid` }, idempotency_key: token };
  const begin = Date.now();
  const response = http.post(`${__ENV.LOAD_BASE}/api/matches`, JSON.stringify(body), { headers, tags: { name: 'create_match' } });
  if (!check(response, { 'match accepted': r => r.status === 202 })) { completed.add(false); return; }
  const id = response.json().session_id;
  let status;
  while (Date.now() - begin < 15000) {
    const poll = http.get(`${__ENV.LOAD_BASE}/api/matches/${id}`, { headers, tags: { name: 'poll_match' } });
    if (poll.status !== 200) { completed.add(false); return; }
    status = poll.json();
    if (status.status === 'ready' || status.status === 'failed') break;
    sleep(0.2);
  }
  const success = status && status.status === 'ready';
  completed.add(Boolean(success));
  check(status, { 'worker completes shortlist': s => s && s.status === 'ready', 'unverified result data withheld': s => s && s.verification_required && !s.preview && s.total_count === undefined });
  if (success) ready.add(Date.now() - begin);
  const locked = http.get(`${__ENV.LOAD_BASE}/api/matches/${id}/results`, { headers, responseCallback: http.expectedStatuses(403), tags: { name: 'locked_results' } });
  check(locked, { 'email gate enforced': r => r.status === 403 });
  const stranger = http.get(`${__ENV.LOAD_BASE}/api/matches/${id}`, { headers: { ...headers, 'X-Session-Token': token + '-other' }, responseCallback: http.expectedStatuses(404), tags: { name: 'owner_isolation' } });
  check(stranger, { 'other browser cannot access shortlist': r => r.status === 404 });
  sleep(0.25);
}
