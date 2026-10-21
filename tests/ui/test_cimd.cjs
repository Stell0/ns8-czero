// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=(data,status=200)=>({ok:status<400,status,json:async()=>data});
const URL='https://client.example.test/client.json',ID='00000000-0000-4000-8000-000000000001';
const descriptor={client_id:URL,client_name:'<img> literal name',redirect_uris:['https://client.example.test/callback'],
  token_endpoint_auth_method:'none',grant_types:['authorization_code','refresh_token'],response_types:['code'],scope_ceiling:null};
const client=(revision=2)=>({client_id:ID,metadata_url:URL,client_name:'<svg> Client',allowed_scopes:['c0:read'],
  enabled:true,revision,review_required:false,approved_descriptor:descriptor});
function setup(){
  const nodes=new Map(),requests=[],clearers=[];
  const element=()=>({children:[],listeners:{},hidden:true,disabled:false,checked:false,value:'',readOnly:false,textContent:'',
    append(...values){this.children.push(...values);},replaceChildren(...values){this.children=values;},
    addEventListener(event,fn){this.listeners[event]=fn;},set innerHTML(_){throw new Error('Untrusted HTML');}});
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element};
  const window={C0Space:{onClear:fn=>clearers.push(fn),clear(){for(const fn of clearers)fn();}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../app/static/cimd.js'),'utf8'),{
    document,window,fetch(url,options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));},encodeURIComponent});
  return{requests,el:id=>document.getElementById(id),clear:()=>window.C0Space.clear()};
}
async function ready(enabled=true,clients=[]){const h=setup();h.requests[0].resolve(response({role:'admin',csrf_token:'fixture-only'}));await tick();
  h.requests[1].resolve(response({enabled,clients}));await tick();return h;}
const preview=h=>h.el('cimd-form').listeners.submit({preventDefault(){}});
async function reviewed(h){h.el('cimd-url').value=URL;const pending=preview(h);h.requests.at(-1).resolve(response({descriptor,metadata_digest:'a'.repeat(64)}));await pending;}
test('Reader and Editor never fetch approved metadata or show controls',async()=>{
  for(const role of ['reader','editor']){const h=setup();h.requests[0].resolve(response({role}));await tick();assert.equal(h.requests.length,1);assert(h.el('cimd-administration').hidden);}
});
test('default-off status leaves review and approval disabled',async()=>{
  const h=await ready(false);assert(h.el('cimd-preview').disabled);assert(h.el('cimd-approve').disabled);
  await preview(h);assert.equal(h.requests.length,2);assert.match(h.el('cimd-list-status').textContent,/Disabled/);
});
test('preview displays literal metadata and enforces the declared permission ceiling',async()=>{
  const h=await ready();h.el('cimd-url').value=URL;h.el('cimd-admin').checked=true;
  const pending=preview(h);h.requests[2].resolve(response({descriptor:{...descriptor,scope_ceiling:['c0:read']},metadata_digest:'a'.repeat(64)}));await pending;
  assert.equal(h.el('cimd-review').children[0].textContent,'<img> literal name');
  assert(h.el('cimd-review').children[1].textContent.includes(URL));assert(h.el('cimd-admin').disabled);assert(!h.el('cimd-admin').checked);
  assert(!h.el('cimd-approve').disabled);
});
test('late preview cannot overwrite a newer URL or permission draft',async()=>{
  const h=await ready();h.el('cimd-url').value=URL;const pending=preview(h);
  h.el('cimd-url').value='https://new.example.test/client.json';h.el('cimd-url').listeners.input();h.el('cimd-admin').checked=true;h.el('cimd-admin').listeners.change();
  h.requests[2].resolve(response({descriptor,metadata_digest:'a'.repeat(64)}));await pending;
  assert.equal(h.el('cimd-review').children.length,0);assert(h.el('cimd-admin').checked);assert(h.el('cimd-approve').disabled);
  assert.equal(h.el('cimd-url').value,'https://new.example.test/client.json');
});
test('approval captures the reviewed URL hash scopes and CSRF and preserves newer drafts',async()=>{
  const h=await ready();await reviewed(h);const pending=h.el('cimd-approve').listeners.click();h.el('cimd-approve').listeners.click();
  assert.equal(h.requests.length,4);assert.deepEqual(JSON.parse(h.requests[3].options.body),{metadata_url:URL,metadata_digest:'a'.repeat(64),allowed_scopes:['c0:read']});
  assert.equal(h.requests[3].options.headers['X-C0-CSRF'],'fixture-only');h.el('cimd-url').value='https://new.example.test/client.json';h.el('cimd-url').listeners.input();
  h.requests[3].resolve(response(client(),201));await tick();h.requests[4].resolve(response({enabled:true,clients:[client()]}));await pending;
  assert.equal(h.el('cimd-url').value,'https://new.example.test/client.json');assert(!h.el('cimd-url').readOnly);assert.match(h.el('cimd-form-status').textContent,/newer draft is preserved/);
});
test('reapproval keeps binding URL immutable and captures the expected client revision',async()=>{
  const h=await ready(true,[client()]);const row=h.el('cimd-clients').children[0];assert.match(row.children[0].textContent,/<svg>/);
  row.children[3].listeners.click();assert(h.el('cimd-url').readOnly);const pending=preview(h);
  h.requests[2].resolve(response({descriptor,metadata_digest:'b'.repeat(64)}));await pending;
  const saving=h.el('cimd-approve').listeners.click();assert.equal(h.requests[3].url,'./api/v1/oauth/cimd/clients/'+ID);assert.equal(h.requests[3].options.method,'PUT');
  assert.deepEqual(JSON.parse(h.requests[3].options.body),{metadata_digest:'b'.repeat(64),allowed_scopes:['c0:read'],expected_revision:2});
  h.requests[3].resolve(response(client(3)));await tick();h.requests[4].resolve(response({enabled:true,clients:[client(3)]}));await saving;
});
test('revision-protected disable suppresses double clicks and cannot reenable implicitly',async()=>{
  const h=await ready(true,[client()]);const toggle=h.el('cimd-clients').children[0].children[4];const pending=toggle.listeners.click();toggle.listeners.click();
  assert.equal(h.requests.length,3);assert.deepEqual(JSON.parse(h.requests[2].options.body),{enabled:false,expected_revision:2});
  h.requests[2].resolve(response({},409));await pending;assert.match(h.el('cimd-list-status').textContent,/changed/);assert(!toggle.disabled);
});
test('access loss clears metadata and drafts and rejects a late successful preview',async()=>{
  const h=await ready(true,[client()]);h.el('cimd-url').value=URL;const pending=preview(h);h.el('cimd-refresh').listeners.click();
  h.requests[3].resolve(response({},403));await tick();h.requests[2].resolve(response({descriptor,metadata_digest:'a'.repeat(64)}));await pending;
  assert(h.el('cimd-administration').hidden);assert.equal(h.el('cimd-clients').children.length,0);assert.equal(h.el('cimd-review').children.length,0);assert.equal(h.el('cimd-url').value,'');
});
test('a failed metadata fetch never renders private transport diagnostics',async()=>{
  const h=await ready();h.el('cimd-url').value=URL;const pending=preview(h);h.requests[2].reject(new Error('private resolver diagnostics'));await pending;
  assert(!h.el('cimd-form-status').textContent.includes('private'));assert(h.el('cimd-approve').disabled);assert.equal(h.el('cimd-url').value,URL);
});
