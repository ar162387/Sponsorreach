const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
function harness(options = {}) {
  const calls = [];
  const client = { auth: {
    signInWithOtp: async value => { calls.push(['send', value]); return { error: options.sendError || null }; },
    verifyOtp: async value => { calls.push(['verify', value]); return { data: { session: options.invalid ? null : { access_token: 'test' } }, error: options.invalid ? {} : null }; },
  } };
  const file = path.resolve(__dirname, '../app/api/auth/otp/route.ts');
  const mod = new Module(file, module);
  mod.filename = file;
  mod.paths = module.paths;
  mod.require = name => name === '@/lib/server' ? {
    sameOrigin: () => !options.badOrigin,
    supabase: async () => client,
    apiBase: () => 'https://backend.invalid',
    gatewayHeaders: async () => ({ 'X-Session-Token': 'owner-proof', Authorization: 'Bearer test' }),
  } : require(name);
  mod._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, file);
  global.fetch = async (url, init) => {
    calls.push([url, init]);
    return new Response(JSON.stringify(url.endsWith('/confirmation') ? { email: 'owner@example.com' } : { associated: 1 }), { status: options.missing && url.endsWith('/confirmation') ? 404 : 200 });
  };
  const request = body => new Request('https://app.invalid/api/auth/otp', { method: 'POST', body: JSON.stringify(body) });
  return { calls, send: body => mod.exports.POST(request(body)), verify: body => mod.exports.PUT(request(body)) };
}
test('sends code using existing provider without callback dependency', async () => {
  const h = harness(); assert.equal((await h.send({ email: ' User@example.com ' })).status, 200);
  assert.deepEqual(h.calls, [['send', { email: 'user@example.com', options: { shouldCreateUser: true } }]]);
});
test('verifies code then associates using browser ownership proof', async () => {
  const h = harness(); const response = await h.verify({ email: 'user@example.com', token: '012345' });
  assert.deepEqual(await response.json(), { next: '/account?new=1' });
  assert.deepEqual(h.calls[0], ['verify', { email: 'user@example.com', token: '012345', type: 'email' }]);
  assert.equal(h.calls[1][1].headers['X-Session-Token'], 'owner-proof');
});
test('pending shortlist uses server-owned email, ignores submitted email and destination', async () => {
  const h = harness(); const id = '12345678-1234-1234-1234-123456789abc';
  const response = await h.verify({ session_id: id, email: 'other@example.com', token: '012345', next: 'https://evil.invalid' });
  assert.equal((await response.json()).next, '/results/' + id);
  assert.equal(h.calls[1][1].email, 'owner@example.com');
});
test('invalid or expired code does not associate an account', async () => {
  const h = harness({ invalid: true }); assert.equal((await h.verify({ email: 'user@example.com', token: '123456' })).status, 400);
  assert.equal(h.calls.length, 1);
});
test('rejects bad origins, malformed codes and missing owned shortlists', async () => {
  let h = harness({ badOrigin: true }); assert.equal((await h.send({ email: 'user@example.com' })).status, 403); assert.equal(h.calls.length, 0);
  h = harness(); assert.equal((await h.verify({ email: 'user@example.com', token: 'abc' })).status, 422); assert.equal(h.calls.length, 0);
  h = harness({ missing: true }); assert.equal((await h.verify({ session_id: '12345678-1234-1234-1234-123456789abc', token: '123456' })).status, 404); assert.equal(h.calls.length, 1);
});
test('send limits are surfaced without pretending mail was sent', async () => {
  const h = harness({ sendError: {} }); assert.equal((await h.send({ email: 'user@example.com' })).status, 429);
});
