// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {fixture,tick,reply,id}=require('./reader_dom.js');
function setup(){
  const h=fixture('admin','?space_id='+id(101));h.clearers=[];h.navigations=[];
  h.window.C0Space={identifier:id(101),onClear:fn=>h.clearers.push(fn),clear(){for(const fn of h.clearers)fn();}};
  h.window.location.assign=target=>h.navigations.push(target);h.node('space-administration').hidden=true;
  vm.runInContext(fs.readFileSync('app/static/space-admin.js','utf8'),h.context);return h;
}
const account={id:id(1),username:'member',display_name:'<img src=x> Member',role:'editor'};
async function ready(){
  const h=setup();h.requests[0].resolve(reply({role:'admin',csrf_token:'fixture-only'}));await tick();
  h.requests[1].resolve(reply({id:id(101),name:'<svg> Private',shared:false}));await tick();
  h.requests[2].resolve(reply({grants:[{account_id:account.id,role:'reader',revision:4}]}));await tick();
  h.requests[3].resolve(reply({accounts:[account,{id:id(2),username:'reader',display_name:'Reader',role:'reader'},{id:id(3),username:'admin',role:'admin'}]}));await tick();return h;
}
const controls=(h,index=0)=>{const row=h.node('space-grant-list').children[index];return {row,select:row.children[1].children[0],save:row.children[2].children[0],status:row.children[2].children[1]};};

test('Readers and Editors never fetch private space grants or Admin accounts',async()=>{
  for(const role of ['reader','editor']){const h=setup();h.requests[0].resolve(reply({role}));await tick();assert.equal(h.requests.length,1);assert.equal(h.node('space-administration').hidden,true);}
});

test('grant controls render literal metadata, cap target roles and distinguish implicit Admin access',async()=>{
  const h=await ready();assert.equal(h.node('managed-space').textContent,'Protected space: <svg> Private');
  assert.match(controls(h).row.children[0].textContent,/<img src=x> Member/);
  assert.equal(controls(h,1).select.children.find(n=>n.value==='editor').disabled,true);
  assert.match(h.node('space-grant-list').children[2].children[1].textContent,/implicit access/);
  assert(h.requests[3].url.includes('access/accounts?limit=1000'));
});

test('uncertain grant retries reuse the exact key and expected revision while preserving newer choices',async()=>{
  const h=await ready(),c=controls(h);c.select.value='editor';const first=c.save.listeners.click();
  const submitted=JSON.parse(h.requests[4].options.body);assert.equal(submitted.expected_revision,4);assert.equal(h.requests[4].options.headers['X-C0-CSRF'],'fixture-only');
  h.requests[4].reject(new Error('private transport diagnostic'));await first;
  assert(!c.status.textContent.includes('private transport diagnostic'));
  const retry=c.save.listeners.click();assert.deepEqual(JSON.parse(h.requests[5].options.body),submitted);
  c.select.value='reader';h.requests[5].resolve(reply({revision:5,role:'editor'}));await retry;
  assert.equal(c.select.value,'reader');assert.match(c.status.textContent,/newer selection is not saved/);
  const next=c.save.listeners.click();const nextBody=JSON.parse(h.requests[6].options.body);
  assert.equal(nextBody.expected_revision,5);assert.notEqual(nextBody.idempotency_key,submitted.idempotency_key);
  h.requests[6].resolve(reply({},409));await next;assert.match(c.status.textContent,/Refresh before/);
});

test('late grant responses cannot restore the table after access loss',async()=>{
  const h=await ready(),c=controls(h);c.select.value='editor';const pending=c.save.listeners.click();
  h.window.C0Space.clear();assert.equal(h.node('space-grant-list').children.length,0);assert.equal(h.node('space-administration').hidden,true);
  h.requests[4].resolve(reply({revision:5,role:'editor'}));await pending;
  assert.equal(h.node('space-grant-list').children.length,0);assert.equal(h.node('managed-space').textContent,'');
});

test('space creation keeps uncertain replay identity and navigates only after private views clear',async()=>{
  const h=await ready();h.node('space-name').value='New private';
  const submit=()=>h.node('space-create-form').listeners.submit({preventDefault(){}});
  const first=submit();const request=JSON.parse(h.requests[4].options.body);h.requests[4].reject(Error('lost'));await first;
  const retry=submit();assert.deepEqual(JSON.parse(h.requests[5].options.body),request);
  h.requests[5].resolve(reply({id:id(777)}));await retry;
  assert.equal(h.node('space-administration').hidden,true);assert.match(h.navigations[0],new RegExp('space_id='+id(777)));
});
