// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = (data, status=200) => ({ok:status<400, status, json:async()=>data});
function setup() {
  const nodes = new Map(), requests = [];
  const element = () => ({children:[], listeners:{}, hidden:true, disabled:false, checked:false, value:'', textContent:'',
    append(...items){this.children.push(...items);}, replaceChildren(...items){this.children=items;},
    addEventListener(k,fn){this.listeners[k]=fn;},set innerHTML(_){throw new Error('Untrusted HTML');}});
  const document = {getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element};
  let key=0;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../app/static/admin.js'),'utf8'),{
    document,crypto:{randomUUID(){return 'fixture-key-'+(++key);}},
    fetch(url, options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));}
  });
  return {nodes, requests, el:id=>document.getElementById(id)};
}
const client = (id='client', revision=3) => ({client_id:id,client_name:'<img src=x>',revision,enabled:true,redirect_uris:['https://client.test/callback'],allowed_scopes:['c0:read']});
const job = id => ({id,handler:'health.check',state:'queued',attempts:0,max_attempts:3});
const schedule = id => ({id,name:id,handler:'health.check',enabled:true,interval_seconds:3600,next_run_at:'2026-10-15T12:00:00Z'});
async function ready() {
  const h=setup();h.requests[0].resolve(response({role:'admin',username:'Owner',csrf_token:'fixture-only'}));await tick();
  h.requests[1].resolve(response({clients:[client()]}));h.requests[2].resolve(response({jobs:[job('old'),job('new')]}));
  h.requests[3].resolve(response({schedules:[schedule('first'),schedule('second')]}));await tick();
  h.requests[4].resolve(response({handlers:[{name:'health.check',timeout_seconds:10}]}));await tick();return h;
}
const submit=(h,id)=>h.el(id).listeners.submit({preventDefault(){}});
const inspect=(h,list,row=0)=>h.el(list).children[row].children.at(-1).listeners.click();
test('Reader and Editor never request administration data or show controls',async()=>{
  for(const role of ['reader','editor']){const h=setup();h.requests[0].resolve(response({role,username:'User'}));await tick();assert.equal(h.requests.length,1);assert.equal(h.el('admin-workspace').hidden,true);assert.match(h.el('admin-account').textContent,/Only application Admins/);}
});
test('literal client metadata and revision-protected disable capture CSRF',async()=>{
  const h=await ready();assert.match(h.el('client-list').children[0].children[0].textContent,/<img src=x>/);
  const toggle=h.el('client-list').children[0].children[2];toggle.listeners.click();toggle.listeners.click();
  assert.equal(h.requests.length,6);assert.equal(h.requests[5].options.headers['X-C0-CSRF'],'fixture-only');
  assert.deepEqual(JSON.parse(h.requests[5].options.body),{enabled:false,expected_revision:3});
  h.requests[5].resolve(response({},409));await tick();assert.match(h.el('client-status').textContent,/Refresh before retrying/);assert.equal(toggle.disabled,false);
});
test('newer client refresh survives both old success and old error',async()=>{
  for(const fail of [false,true]){const h=await ready();h.el('refresh-clients').listeners.click();h.el('refresh-clients').listeners.click();
    h.requests[6].resolve(response({clients:[{...client('new'),client_name:'New'}]}));await tick();
    h.requests[5].resolve(response({clients:[client('old')]},fail?503:200));await tick();
    assert.match(h.el('client-list').children[0].children[0].textContent,/New/);assert.equal(h.el('client-status').textContent,'1 approved clients.');}
});
test('client approval captures fields and retains newer name callback and scope drafts',async()=>{
  const h=await ready();h.el('client-name').value='Original';h.el('client-callbacks').value='https://client.test/callback';h.el('client-read').checked=true;
  const saving=submit(h,'client-form');h.el('client-name').value='New';h.el('client-callbacks').value='https://new.test/callback';h.el('client-admin').checked=true;
  assert.deepEqual(JSON.parse(h.requests[5].options.body),{client_name:'Original',redirect_uris:['https://client.test/callback'],allowed_scopes:['c0:read']});
  h.requests[5].resolve(response(client(),201));await tick();h.requests[6].resolve(response({clients:[client()]}));await saving;
  assert.equal(h.el('client-name').value,'New');assert.equal(h.el('client-callbacks').value,'https://new.test/callback');assert.equal(h.el('client-admin').checked,true);
});
test('uncertain job retries reuse replay key and edited payloads allocate a new key',async()=>{
  const h=await ready();h.el('job-handler').value='health.check';h.el('job-payload').value='{}';
  let saving=submit(h,'job-form');h.requests[5].reject(new Error('private transport detail'));await saving;
  assert.doesNotMatch(h.el('job-status').textContent,/private transport/);
  saving=submit(h,'job-form');assert.equal(JSON.parse(h.requests[6].options.body).idempotency_key,JSON.parse(h.requests[5].options.body).idempotency_key);
  h.requests[6].resolve(response({},503));await saving;h.el('job-payload').value='{"changed":true}';
  saving=submit(h,'job-form');assert.notEqual(JSON.parse(h.requests[7].options.body).idempotency_key,JSON.parse(h.requests[6].options.body).idempotency_key);
  h.requests[7].resolve(response({},422));await saving;
});
test('late job details cannot replace the newer job',async()=>{
  const h=await ready();inspect(h,'job-list',0);inspect(h,'job-list',1);
  h.requests[7].resolve(response(job('new')));h.requests[8].resolve(response({runs:[]}));await tick();
  h.requests[5].resolve(response(job('old')));h.requests[6].resolve(response({runs:[]}));await tick();
  assert.equal(JSON.parse(h.el('job-data').textContent).id,'new');
});
test('schedule saves preserve a new selection and newer interval drafts',async()=>{
  const h=await ready();inspect(h,'schedule-list');h.requests[5].resolve(response({runs:[]}));await tick();
  h.el('schedule-enabled').checked=false;h.el('schedule-edit-interval').value='120';const saving=submit(h,'schedule-edit');
  assert.deepEqual(JSON.parse(h.requests[6].options.body),{enabled:false,interval_seconds:120});
  inspect(h,'schedule-list',1);h.el('schedule-edit-interval').value='240';h.requests[7].resolve(response({runs:[]}));await tick();
  h.requests[6].resolve(response({...schedule('first'),enabled:false,interval_seconds:120}));await tick();
  h.requests[8].resolve(response({schedules:[schedule('first'),schedule('second')]}));await saving;
  assert.match(h.el('schedule-identity').textContent,/second/);assert.equal(h.el('schedule-edit-interval').value,'240');assert.equal(h.el('save-schedule').disabled,false);
});
test('role loss clears metadata and late successful reads cannot render it again',async()=>{
  const h=await ready();h.el('refresh-clients').listeners.click();h.el('refresh-jobs').listeners.click();
  h.requests[6].resolve(response({},403));await tick();h.requests[5].resolve(response({clients:[client()]}));await tick();
  assert.equal(h.el('admin-workspace').hidden,true);assert.equal(h.el('client-list').children.length,0);
  const count=h.requests.length;submit(h,'client-form');assert.equal(h.requests.length,count);
});
test('invalid payload JSON never sends a job request or loses the draft',async()=>{
  const h=await ready();h.el('job-payload').value='{invalid';await submit(h,'job-form');assert.equal(h.requests.length,5);
  assert.equal(h.el('job-payload').value,'{invalid');assert.equal(h.el('job-status').textContent,'Enter valid JSON.');
});
test('schedule creation captures bounded interval input and CSRF',async()=>{
  const h=await ready();h.el('schedule-name').value='health-browser';h.el('schedule-handler').value='health';h.el('schedule-payload').value='{}';h.el('schedule-interval').value='3600';
  const saving=submit(h,'schedule-form');submit(h,'schedule-form');assert.equal(h.requests.length,6);
  assert.deepEqual(JSON.parse(h.requests[5].options.body),{name:'health-browser',handler:'health',payload:{},interval_seconds:3600});
  assert.equal(h.requests[5].options.headers['X-C0-CSRF'],'fixture-only');h.el('schedule-name').value='next-draft';
  h.requests[5].resolve(response(schedule('created'),201));await tick();h.requests[6].resolve(response({schedules:[schedule('created')]}));await tick();h.requests[7].resolve(response({runs:[]}));await saving;
  assert.equal(h.el('schedule-name').value,'next-draft');assert.match(h.el('schedule-identity').textContent,/created/);
});
test('a saved schedule never overwrites edits made while its write is pending',async()=>{
  const h=await ready();inspect(h,'schedule-list');h.requests[5].resolve(response({runs:[]}));await tick();
  h.el('schedule-edit-interval').value='120';const saving=submit(h,'schedule-edit');h.el('schedule-edit-interval').value='240';
  h.requests[6].resolve(response({...schedule('first'),interval_seconds:120}));await tick();h.requests[7].resolve(response({schedules:[schedule('first')]}));await saving;
  assert.equal(h.el('schedule-edit-interval').value,'240');assert.equal(h.el('save-schedule').disabled,false);
});
