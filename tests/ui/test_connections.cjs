// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'),vm = require('node:vm');
const {fixture,tick,reply,id} = require('./reader_dom.js');
function harness(search='?view=account') {
  const h = fixture('index',search);
  h.window.C0Space = {onClear(fn) {h.clear=fn;}};
  vm.runInContext(fs.readFileSync('app/static/connections.js','utf8'),h.context);
  return h;
}
const connection = (name='<img> client',n=1) => ({id:id(n),client_name:name,scopes:['c0:read'],persistent:true,
  expires_at:null,idle_until:'2026-11-23T00:00:00Z',last_used_at:'2026-10-23T00:00:00Z'});
async function ready() {
  const h = harness();h.requests[0].resolve(reply({connections:[connection()],csrf_token:'first-csrf'}));await tick();return h;
}
test('ordinary readers do not request account connections',()=>{
  assert.equal(harness('').requests.length,0);
});
test('connection names remain literal and disconnect captures the current CSRF once',async()=>{
  const h = await ready();
  assert.equal(h.node('connections-list').children[0].children[0].textContent,'<img> client');
  const button = h.node('connections-list').children[0].children[2];
  assert.equal(button.attributes['aria-label'],'Disconnect <img> client');
  button.listeners.click();button.listeners.click();
  assert.equal(h.requests.length,2);
  assert.equal(h.requests[1].options.method,'DELETE');
  assert.equal(h.requests[1].options.headers['X-C0-CSRF'],'first-csrf');
  h.requests[1].resolve(reply(null,204));await tick();
  h.requests[2].resolve(reply({connections:[],csrf_token:'next-csrf'}));await tick();
  assert.equal(h.node('connections-list').children.length,0);
  assert.match(h.node('connections-message').textContent,/No active/);
});
test('a stale disconnect reply cannot replace a refreshed account view',async()=>{
  const h = await ready();h.node('connections-list').children[0].children[2].listeners.click();
  h.node('refresh-connections').listeners.click();
  h.requests[2].resolve(reply({connections:[connection('Latest',2)],csrf_token:'latest-csrf'}));await tick();
  h.requests[1].resolve(reply(null,204));await tick();
  assert.equal(h.requests.length,3);
  assert.equal(h.node('connections-list').children[0].children[0].textContent,'Latest');
});
test('access loss clears private connections and ignores a late list',async()=>{
  const h = await ready();h.node('refresh-connections').listeners.click();h.clear();
  h.requests[1].resolve(reply({connections:[connection('Private stale')],csrf_token:'stale-csrf'}));await tick();
  assert.equal(h.node('connections-list').children.length,0);
  assert.match(h.node('connections-message').textContent,/Refresh connections/);
});
test('sign-out clears connections before a pending reply arrives',async()=>{
  const h = harness();h.node('sign-out').listeners.click();
  h.requests[0].resolve(reply({connections:[connection()],csrf_token:'stale-csrf'}));await tick();
  assert.equal(h.node('connections-list').children.length,0);
});
test('authorization loss during disconnect clears the account list',async()=>{
  const h = await ready();h.node('connections-list').children[0].children[2].listeners.click();
  h.requests[1].resolve(reply(null,403));await tick();
  assert.equal(h.node('connections-list').children.length,0);
  assert.match(h.node('connections-message').textContent,/Sign in again/);
});
