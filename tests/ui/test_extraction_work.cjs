// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {fixture,tick,reply,id}=require('./reader_dom');
function setup(){const h=fixture('admin-secondary');let clear;
  h.window.C0Space={apiURL:path=>'./api/v1/'+path+(path.includes('?')?'&':'?')+'space_id='+id(99),onClear:callback=>{clear=callback;},pageURL:path=>path+'&space_id='+id(99)};
  vm.runInContext(fs.readFileSync('app/static/extraction-work.js','utf8'),h.context);
  return {...h,clear:()=>clear()};
}
const run=(n=1)=>({id:id(n),version_id:id(n+10),state:'failed',revision:3,processing_generation:1,succeeded:98,expected_units:100,error_code:'parser_timeout'});
const detail=(n=1)=>({run:run(n),source_id:id(20+n),parser:{partitioner:'pdf-page-v1'},units:[{ordinal:37,locator:{kind:'page',first:37,last:37},state:'failed',attempts:3,lifetime_attempts:3,error_code:'parser_timeout',duration_ms:7}],offset:0,limit:20});
async function ready(){const h=setup();h.requests[0].resolve(reply({role:'admin',csrf_token:'fixture-only'}));await tick();h.requests[1].resolve(reply({runs:[run(1),run(2)]}));await tick();return h;}
const inspect=(h,n=0)=>h.node('extraction-list').children[n].children[1].listeners.click();
test('ordinary Reader and Editor never load Admin extraction diagnostics',async()=>{
  for(const role of ['reader','editor']){const h=setup();h.requests[0].resolve(reply({role}));await tick();assert.equal(h.requests.length,1);}
});
test('diagnostics preserve the explicit selected space and ignore late details',async()=>{
  const h=await ready();assert.match(h.requests[1].url,new RegExp('space_id='+id(99)));
  inspect(h,0);inspect(h,1);h.requests[3].resolve(reply(detail(2)));await tick();h.requests[2].resolve(reply(detail(1)));await tick();
  assert.match(h.node('extraction-source').href,new RegExp(id(22)));assert.match(h.node('extraction-units').textContent,/Unit 37 · page 37 · failed/);
});
test('uncertain retries retain their key and clear after access loss',async()=>{
  const h=await ready();inspect(h);h.requests[2].resolve(reply(detail()));await tick();
  h.node('retry-extraction').listeners.click();const first=JSON.parse(h.requests[3].options.body);
  assert.equal(h.requests[3].options.headers['X-C0-CSRF'],'fixture-only');
  h.requests[3].reject(new Error('private-path'));await tick();h.requests[4].resolve(reply(detail()));await tick();
  assert.doesNotMatch(h.node('extraction-status').textContent,/private-path/);
  h.node('retry-extraction').listeners.click();assert.equal(JSON.parse(h.requests[5].options.body).idempotency_key,first.idempotency_key);
  h.clear();h.requests[5].resolve(reply({retried_units:2}));await tick();
  assert.equal(h.node('extraction-work').hidden,true);assert.equal(h.node('extraction-units').textContent,'');assert.equal(h.node('extraction-source').getAttribute('href'),null);
});
test('expired results disable selective retry and offer full restart',async()=>{
  const h=await ready();inspect(h);const data=detail();data.run.error_code='staging_expired';h.requests[2].resolve(reply(data));await tick();
  assert.equal(h.node('retry-extraction').disabled,true);assert.equal(h.node('restart-extraction').disabled,false);assert.match(h.node('extraction-warning').textContent,/expired/);
});
