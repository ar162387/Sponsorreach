const test = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const output = ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname,'../lib/personalization.ts'),'utf8'), { compilerOptions:{ module:ts.ModuleKind.CommonJS } }).outputText;
const sandbox={exports:{}};vm.runInNewContext(output,sandbox);
const {loadingMessages}=sandbox.exports;
test('personalization preserves unfamiliar roles and only submitted profile facts',()=>{
 const messages=loadingMessages({roles:['Specialist glass artist'],background:'Craft',specialization:'Flameworking',skills:['Glass shaping'],locations:['Leeds'],related_roles_enabled:false});
 assert(messages.some(m=>m.includes('Specialist glass artist')));
 assert(messages.some(m=>m.includes('Flameworking')));
 assert(messages.some(m=>m.includes('Glass shaping')));
 assert(messages.some(m=>m.includes('Leeds')));
 assert(!messages.some(m=>m.includes('separate section')));
 assert(!messages.some(m=>/vacanc|\d+%|guarantee/i.test(m)));
});
test('related career message follows the explicit choice',()=>{
 assert(loadingMessages({roles:[],skills:[],locations:[],background:'',specialization:'',related_roles_enabled:true}).some(m=>m.includes('separate section')));
 assert(loadingMessages().length>=3);
});
test('display text normalizes whitespace and bounds long fields',()=>{
 const messages=loadingMessages({roles:['A'.repeat(400)],skills:[],locations:[],background:'',specialization:'',related_roles_enabled:false});
 assert(messages.every(m=>m.length<200));
});

test('matching captions leave time to read and bound long text',()=>{
 const {captionDuration}=sandbox.exports;
 assert.equal(captionDuration('A short caption.'),6000);
 assert.equal(captionDuration(Array(30).fill('word').join(' ')),9000);
 assert.equal(captionDuration(Array(100).fill('word').join(' ')),15000);
});
