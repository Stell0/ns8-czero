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
async function complete(h) {h.requests[0].resolve(reply(config()));h.requests[1].resolve(reply({objects:[{data:{label:'<script>topic',classification:'user',lifecycle:'active',topic_id:'anchor'}}]}));await tick();}

test('project reader renders literal stored data and uses no mutation requests',async()=>{
  const h=setup();await complete(h);assert.equal(h.node('project-content').hidden,false);
  assert.equal(h.node('project-title').textContent,'<img src=x> project');
  assert.match(h.node('project-topics').textContent,/<script>topic/);
  assert(h.requests.every(request=>request.options===undefined));
  assert.match(h.node('project-config').textContent,/disabled/);
});
test('no explicit project never fetches Shared',()=>{const h=setup(null);assert.equal(h.requests.length,0);assert(h.node('project-content').hidden);});
test('revocation clears private content and rejects delayed replies',async()=>{
  const h=setup();await complete(h);h.node('project-refresh').listeners.click();const requests=h.requests.slice(2);h.clear();
  requests[0].resolve(reply(config()));requests[1].resolve(reply({objects:[]}));await tick();
  assert(h.node('project-content').hidden);assert.equal(h.node('project-description').textContent,'');assert.equal(h.node('project-topics').children.length,0);
});
test('wrong project identity cannot populate the view',async()=>{
  const h=setup();h.requests[0].resolve(reply(config(id(102))));h.requests[1].resolve(reply({objects:[]}));await tick();
  assert(h.node('project-content').hidden);assert.equal(h.node('project-description').textContent,'');
});
test('new refresh rejects an older error',async()=>{
  const h=setup();h.node('project-refresh').listeners.click();h.requests[2].resolve(reply(config()));h.requests[3].resolve(reply({objects:[]}));await tick();
  h.requests[0].reject(Error('late'));h.requests[1].resolve(reply({objects:[]}));await tick();assert(!h.node('project-content').hidden);
});
