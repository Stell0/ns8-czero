// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {fixture,tick,reply,id}=require('./reader_dom.js');
function setup(selected=id(101)) {
  const h=fixture('projects',selected?'?space_id='+selected:'');let generation=0, clear;
  h.window.C0Space={identifier:selected,generation:()=>generation,current:value=>value===generation,onClear:callback=>{clear=callback;},request:path=>h.window.fetch(path)};
  h.clear=()=>{++generation;clear();};
  vm.runInContext(fs.readFileSync('app/static/projects.js','utf8'),h.context);return h;
}
function config(space=id(101)) {return {data:{version:1,manifest:{project_id:space,space_id:space,name:'<img src=x> project',description:'Private description',purpose:'Research',scope:'Synthetic only',language:'en',timezone:'Europe/Rome',schedule:{enabled:false},primary_topic_ids:['anchor']}}};}
async function complete(h) {h.requests[0].resolve(reply(config()));h.requests[1].resolve(reply({objects:[{data:{label:'<script>topic',classification:'user',lifecycle:'active',topic_id:'anchor'}}]}));h.requests[2].resolve(reply({objects:[]}));for(const r of h.requests.slice(3,6)) r.resolve(reply({objects:[]}));await tick();}

test('project reader renders literal stored data and uses no mutation requests',async()=>{
  const h=setup();await complete(h);assert.equal(h.node('project-content').hidden,false);
  assert.equal(h.node('project-title').textContent,'<img src=x> project');
  assert.match(h.node('project-topics').textContent,/<script>topic/);
  assert(h.requests.every(request=>request.options===undefined));
  assert.match(h.node('project-config').textContent,/disabled/);
});
test('no explicit project never fetches Shared',()=>{const h=setup(null);assert.equal(h.requests.length,0);assert(h.node('project-content').hidden);});
test('revocation clears private content and rejects delayed replies',async()=>{
  const h=setup();await complete(h);h.node('project-refresh').listeners.click();const requests=h.requests.slice(6);h.clear();
  requests[0].resolve(reply(config()));requests[1].resolve(reply({objects:[]}));requests[2].resolve(reply({objects:[]}));for(const r of requests.slice(3)) r.resolve(reply({objects:[]}));await tick();
  assert(h.node('project-content').hidden);assert.equal(h.node('project-description').textContent,'');assert.equal(h.node('project-topics').children.length,0);
});
test('wrong project identity cannot populate the view',async()=>{
  const h=setup();h.requests[0].resolve(reply(config(id(102))));h.requests[1].resolve(reply({objects:[]}));h.requests[2].resolve(reply({objects:[]}));for(const r of h.requests.slice(3,6)) r.resolve(reply({objects:[]}));await tick();
  assert(h.node('project-content').hidden);assert.equal(h.node('project-description').textContent,'');
});
test('new refresh rejects an older error',async()=>{
  const h=setup();h.node('project-refresh').listeners.click();h.requests[6].resolve(reply(config()));for(const r of h.requests.slice(7,12)) r.resolve(reply({objects:[]}));await tick();
  h.requests[0].reject(Error('late'));h.requests[1].resolve(reply({objects:[]}));h.requests[2].resolve(reply({objects:[]}));for(const r of h.requests.slice(3,6)) r.resolve(reply({objects:[]}));await tick();assert(!h.node('project-content').hidden);
});

test('project source errors render as text and clear on access loss',async()=>{
  const h=setup();h.requests[0].resolve(reply(config()));h.requests[1].resolve(reply({objects:[]}));
  h.requests[2].resolve(reply({objects:[{data:{connector_id:'<img> connector',status:'partial',verified_items:0,discovered_items:1,last_success_at:'',last_error:'<script> private error',retry_after:''}}]}));for(const r of h.requests.slice(3,6)) r.resolve(reply({objects:[]}));await tick();
  assert.match(h.node('project-sources').textContent,/<script> private error/);
  assert.match(h.node('project-sources').textContent,/0\/1 items verified/);
  h.clear();assert.equal(h.node('project-sources').children.length,0);assert.equal(h.node('project-sources-status').textContent,'');
});


test('queue and incomplete workflow observations stay literal and private',async()=>{
  const h=setup();h.requests[0].resolve(reply(config()));
  for(const r of h.requests.slice(1,3)) r.resolve(reply({objects:[]}));
  h.requests[3].resolve(reply({objects:[{data:{question:'<script> pending research',status:'deferred',priority:20,expansion_priority:40,attempt_count:1,defer_reason:'daily_budget'}}]}));
  h.requests[4].resolve(reply({objects:[{data:{workflow_type:'daily',local_cycle_date:'2026-10-25',state:'partial',current_phase:'monitoring',finished_at:'',error_code:'phase_incomplete'}}]}));h.requests[5].resolve(reply({objects:[]}));await tick();
  assert.match(h.node('project-work').textContent,/<script> pending research/);
  assert.match(h.node('project-work').textContent,/partial/);assert.match(h.node('project-work-status').textContent,/does not prove/);
  h.clear();assert.equal(h.node('project-work').children.length,0);assert.equal(h.node('project-work-status').textContent,'');
});

test('monitoring displays incomplete checks without claiming a successful watermark',async()=>{
  const h=setup();h.requests[0].resolve(reply(config()));
  for(const r of h.requests.slice(1,5)) r.resolve(reply({objects:[]}));
  h.requests[5].resolve(reply({objects:[{data:{topic_id:'anchor',local_date:'2026-10-25',status:'partial',queries_used:1,max_queries:5,sources_used:0,max_sources:10,successful_watermark:'',summary:'<script> timed out'}}]}));await tick();
  assert.match(h.node('project-monitoring').textContent,/queries 1\/5/);
  assert.match(h.node('project-monitoring').textContent,/successful watermark not advanced/);
  assert.match(h.node('project-monitoring').textContent,/<script> timed out/);
  assert.match(h.node('project-monitoring-status').textContent,/no queued research slots/);
  h.clear();assert.equal(h.node('project-monitoring').children.length,0);
  assert.equal(h.node('project-monitoring-status').textContent,'');
});
