const test = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const message = 'We are not currently taking applications.';
function load(file, server, fetch) {
  const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const sandbox = {exports:{}, Request, Response, URL, AbortSignal, fetch, require(name) {
    if (name === 'next/server') return {NextResponse: {json: (body, options) => Response.json(body, options)}};
    if (name === '@/lib/server') return server;
    if (name === '@/lib/applications') return {APPLICATIONS_CLOSED_MESSAGE: message};
    throw new Error('Unexpected import: ' + name);
  }};
  vm.runInNewContext(output, sandbox);
  return sandbox.exports;
}
test('guest applications are rejected without forwarding or saving a profile', async () => {
  const route = load('app/api/[...path]/route.ts', {sameOrigin:()=>true, verifiedUser:async()=>null}, () => {throw new Error('Must not forward');});
  const response = await route.POST(new Request('https://sponsorreach.uk/api/matches', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}), {params:Promise.resolve({path:['matches']})});
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error, message);
});
test('existing members can request sign-in without creating an account', async () => {
  let credentials;
  const route = load('app/api/auth/magic-link/route.ts', {sameOrigin:()=>true, publicOrigin:()=> 'https://sponsorreach.uk', supabase:async()=>({auth:{signInWithOtp:async(value)=>{credentials=value;return {error:null};}}})});
  const response = await route.POST(new Request('https://sponsorreach.uk/api/auth/magic-link', {method:'POST',body:JSON.stringify({email:'member@example.invalid'})}));
  assert.equal(response.status, 200);
  assert.equal(credentials.options.shouldCreateUser, false);
});
test('refused sign-in displays the application closure notice', async () => {
  const route = load('app/api/auth/magic-link/route.ts', {sameOrigin:()=>true, publicOrigin:()=> 'https://sponsorreach.uk', supabase:async()=>({auth:{signInWithOtp:async()=>({error:{message:'Signups disabled'}})}})});
  const response = await route.POST(new Request('https://sponsorreach.uk/api/auth/magic-link', {method:'POST',body:JSON.stringify({email:'new@example.invalid'})}));
  assert.equal(response.status, 429);
  assert.match((await response.json()).error, /We are not currently taking applications/);
});
