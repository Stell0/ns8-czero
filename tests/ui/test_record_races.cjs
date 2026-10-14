// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
// Execute the real UI script against controllable, out-of-order HTTP replies.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const nodes = new Map(), requests = [];
  function node() {
    return { children: [], value: '', textContent: '', listeners: {},
      addEventListener(event, callback) { this.listeners[event] = callback; },
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); } };
  }
  const document = { getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id);
  }, createElement: node };
  document.getElementById('record-type').value = 'inventory';
  const context = vm.createContext({ document, URLSearchParams, console,
    fetch(url) {
      return new Promise(resolve => {
        // Leave automatic identity bootstrap parked; only exercise listing.
        if (url.includes('/objects')) requests.push({ url, resolve });
      });
    } });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/static/objects.js'), 'utf8'), context);
  return { context, nodes, requests, load: () => vm.runInContext('loadRecords()', context) };
}
const response = name => ({ ok: true, status: 200, json: async () => ({ objects: [
  { id: 'fixture-id', data: { name }, revision: 1, tags: [] } ] }) });
const recordName = h => h.nodes.get('record-list').children[0].children[0].children[0].textContent;

test('overlapping refreshes never append duplicate record rows', async () => {
  const h = harness(), first = h.load(), second = h.load();
  h.requests[0].resolve(response('Rack')); await first;
  h.requests[1].resolve(response('Rack')); await second;
  assert.equal(h.nodes.get('record-list').children.length, 1);
  assert.equal(recordName(h), 'Rack');
});

test('a late response cannot overwrite the newest selected type', async () => {
  const h = harness(), first = h.load();
  h.nodes.get('record-type').value = 'projects';
  const second = h.load();
  h.requests[1].resolve(response('Project')); await second;
  h.requests[0].resolve(response('Old inventory')); await first;
  assert.equal(h.nodes.get('record-list').children.length, 1);
  assert.equal(recordName(h), 'Project');
});


test('late relation replies cannot replace the newly selected record edges', async () => {
  const h = harness();
  vm.runInContext("current = {id:'rack'}", h.context);
  const first = vm.runInContext('loadRelations()', h.context);
  vm.runInContext("current = {id:'project'}", h.context);
  const second = vm.runInContext('loadRelations()', h.context);
  const edge = (source, target) => ({ok:true,status:200,json:async()=>({relations:[
    {id:'relation',source_id:source,target_id:target,kind:'linked'}]})});
  h.requests[1].resolve(edge('project','new-target')); await second;
  h.requests[0].resolve(edge('rack','old-target')); await first;
  assert.equal(h.nodes.get('record-relations').children[0].children[0].textContent, 'linked → new-target');
});

test('late detail replies cannot switch back to an earlier selection', async () => {
  const h = harness();
  vm.runInContext("definitions = [{name:'inventory',label:'Inventory',schema:{type:'object'}}]",h.context);
  const first = vm.runInContext("selectRecord('old')",h.context);
  const second = vm.runInContext("selectRecord('new')",h.context);
  const record = id => ({ok:true,status:200,json:async()=>({id,type_name:'inventory',data:{name:id},tags:[],revision:1})});
  h.requests[1].resolve(record('new'));
  // Finish the detail response's subsequent relation request.
  await new Promise(setImmediate);
  h.requests[2].resolve({ok:true,status:200,json:async()=>({relations:[]})});
  await second;
  h.requests[0].resolve(record('old')); await first;
  assert.match(h.nodes.get('record-identity').textContent,/^new · revision 1$/);
});


test('an earlier save completion preserves a new unsaved draft', async () => {
  const h = harness();
  vm.runInContext("profile={role:'editor',csrf_token:'fixture-only'}; definitions=[{name:'inventory',label:'Inventory',schema:{type:'object'}}]; displayRecord({id:'old',type_name:'inventory',data:{name:'old'},tags:[],revision:1})", h.context);
  h.nodes.get('record-data').value = '{"name":"edited old"}';
  const saving = h.nodes.get('record-form').listeners.submit({preventDefault(){}});
  vm.runInContext('displayRecord(null)', h.context);
  h.nodes.get('record-data').value = '{"name":"unsaved new draft"}';
  h.requests[0].resolve({ok:true,status:200,json:async()=>({id:'old',type_name:'inventory',data:{name:'edited old'},tags:[],revision:2})});
  await new Promise(setImmediate);
  h.requests[1].resolve(response('edited old'));
  await saving;
  assert.equal(h.nodes.get('record-heading').textContent,'New record');
  assert.equal(h.nodes.get('record-data').value,'{"name":"unsaved new draft"}');
});

test('a save preserves newer edits to the same record and advances its revision', async () => {
  const h = harness();
  vm.runInContext("profile={role:'editor',csrf_token:'fixture-only'}; definitions=[{name:'inventory',label:'Inventory',schema:{type:'object'}}]; displayRecord({id:'same',type_name:'inventory',data:{name:'old'},tags:[],revision:1})", h.context);
  h.nodes.get('record-data').value='{"name":"first edit"}';
  const saving=h.nodes.get('record-form').listeners.submit({preventDefault(){}});
  h.nodes.get('record-data').value='{"name":"newer draft"}';h.nodes.get('record-data').listeners.input();
  h.requests[0].resolve({ok:true,status:200,json:async()=>({id:'same',type_name:'inventory',data:{name:'first edit'},tags:[],revision:2})});
  await new Promise(setImmediate);h.requests[1].resolve(response('first edit'));await saving;
  assert.equal(h.nodes.get('record-data').value,'{"name":"newer draft"}');
  assert.match(h.nodes.get('record-status').textContent,/newer edits are preserved/);
  assert.equal(vm.runInContext('current.revision',h.context),2);
});

test('late relation targets cannot replace another selected target type', async()=>{
  const h=harness();vm.runInContext("profile={role:'editor',csrf_token:'fixture-only'}; current={id:'source'}",h.context);
  h.nodes.get('relation-type').value='inventory';const first=vm.runInContext('loadRelationTargets()',h.context);
  h.nodes.get('relation-type').value='projects';h.nodes.get('relation-type').listeners.change();
  const second=vm.runInContext('loadRelationTargets()',h.context);h.requests[1].resolve(response('New project'));await second;
  h.requests[0].resolve(response('Old target'));await first;
  assert.match(h.nodes.get('relation-picker').children[1].textContent,/New project/);
});
test('relation target replies preserve a newer manually entered ID',async()=>{
  const h=harness();vm.runInContext("profile={role:'editor',csrf_token:'fixture-only'}; current={id:'source'}",h.context);
  h.nodes.get('relation-type').value='inventory';const pending=vm.runInContext('loadRelationTargets()',h.context);
  h.nodes.get('relation-target').value='new-manual-id';h.requests[0].resolve(response('Target'));await pending;
  assert.equal(h.nodes.get('relation-target').value,'new-manual-id');
});
