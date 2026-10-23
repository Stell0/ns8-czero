// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const nodes = new Map(), requests = [], redirects = [];
  function node() {
    return { children: [], listeners: {}, textContent: '', disabled: true,
      addEventListener(name, fn) { this.listeners[name] = fn; },
      appendChild(child) { this.children.push(child); },
      querySelectorAll() { return this.children.flatMap(label => label.children).filter(child => child.type === 'checkbox' && child.checked); },
      set innerHTML(_) { throw new Error('Untrusted HTML assignment'); } };
  }
  const document = { getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); },
    createElement: node, createTextNode: text => ({ textContent: text }) };
  const context = vm.createContext({ document, window: { location: { assign(value) { redirects.push(value); } } },
    fetch(url, options) { return new Promise(resolve => requests.push({ url, options, resolve })); } });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/static/consent.js'), 'utf8'), context);
  return { nodes, requests, redirects };
}
async function ready(h, extra = {}) {
  h.requests[0].resolve({ ok: true, json: async () => ({ client_name: '<script>client</script>', callback: 'https://client.example.test/callback',
    profile: { username: '<img>user</img>' }, scopes: ['c0:read', 'c0:write'], eligible_scopes: ['c0:read'], csrf_token: 'fixture-only', ...extra }) });
  await tick();
}

test('consent renders literal metadata and disables unavailable permissions', async () => {
  const h = harness();
  await ready(h);
  assert.equal(h.nodes.get('client').textContent, '<script>client</script>');
  assert.equal(h.nodes.get('profile').textContent, 'Signed in as <img>user</img>');
  const inputs = h.nodes.get('scopes').children.map(label => label.children[0]);
  assert.equal(inputs[0].checked, true);
  assert.equal(inputs[1].disabled, true);
  assert.equal(inputs[1].checked, false);
});

test('approval captures scope and csrf once and suppresses repeated writes', async () => {
  const h = harness();
  await ready(h);
  const submit = h.nodes.get('consent-form').listeners.submit;
  submit({ preventDefault() {} });
  submit({ preventDefault() {} });
  assert.equal(h.requests.length, 2);
  assert.deepEqual(JSON.parse(h.requests[1].options.body), { approve: true, scopes: ['c0:read'], persistent: false });
  assert.equal(h.requests[1].options.headers['X-C0-CSRF'], 'fixture-only');
  h.requests[1].resolve({ ok: false });
  await tick();
  assert.match(h.nodes.get('message').textContent, /start again/);
  assert.equal(h.nodes.get('approve').disabled, true);
  assert.equal(h.redirects.length, 0);
});

test('empty selection can deny and only successful server reply redirects', async () => {
  const h = harness();
  await ready(h);
  h.nodes.get('scopes').children[0].children[0].checked = false;
  h.nodes.get('deny').listeners.click();
  assert.deepEqual(JSON.parse(h.requests[1].options.body), { approve: false, scopes: [], persistent: false });
  h.requests[1].resolve({ ok: true, json: async () => ({ redirect_uri: 'https://client.example.test/callback?error=access_denied' }) });
  await tick();
  assert.deepEqual(h.redirects, ['https://client.example.test/callback?error=access_denied']);
});


test('metadata-client consent shows the approved URL as literal identity', async () => {
  const h = harness(), clientId = 'https://client.example.test/client.json';
  h.requests[0].resolve({ok: true, json: async () => ({client_id: clientId,
    client_name: '<svg> literal name', callback: 'https://client.example.test/callback',
    profile: {username: 'owner'}, scopes: ['c0:read'], eligible_scopes: ['c0:read'], csrf_token: 'fixture-only'})});
  await tick();
  assert.equal(h.nodes.get('client-identity').textContent, 'Approved client metadata URL: ' + clientId);
  assert.equal(h.nodes.get('client-identity').hidden, false);
  assert.equal(h.nodes.get('client').textContent, '<svg> literal name');
});

test('background access starts unchecked and selecting it stages only the chosen scopes', async () => {
  const h = harness();
  await ready(h, {background_supported: true, background_ready: false, connection_idle_seconds: 2592000});
  const choice = h.nodes.get('background');
  assert.equal(choice.checked, false);
  assert.equal(choice.disabled, false);
  assert.match(h.nodes.get('background-help').textContent, /30 days/);
  choice.checked = true; choice.listeners.change();
  assert.match(h.nodes.get('approve').textContent, /background sign-in/);
  h.nodes.get('consent-form').listeners.submit({preventDefault() {}});
  assert.equal(h.requests[1].url, '/oauth/consent/background');
  assert.deepEqual(JSON.parse(h.requests[1].options.body), {scopes: ['c0:read']});
  h.requests[1].resolve({ok: true, json: async () => ({next: '/auth/login'})});
  await tick();
  assert.deepEqual(h.redirects, ['/auth/login']);
});

test('returning background sign-in still requires final explicit authorization', async () => {
  const h = harness();
  await ready(h, {background_supported: true, background_ready: true, background_requested: true, connection_idle_seconds: 2592000});
  assert.equal(h.nodes.get('background').checked, true);
  assert.equal(h.requests.length, 1);
  h.nodes.get('consent-form').listeners.submit({preventDefault() {}});
  assert.equal(h.requests[1].url, '/oauth/consent');
  assert.deepEqual(JSON.parse(h.requests[1].options.body), {approve: true, scopes: ['c0:read'], persistent: true});
});

test('background handoff rejects a destination other than the fixed sign-in path', async () => {
  const h = harness();
  await ready(h, {background_supported: true, connection_idle_seconds: 2592000});
  h.nodes.get('background').checked = true;
  h.nodes.get('consent-form').listeners.submit({preventDefault() {}});
  h.requests[1].resolve({ok: true, json: async () => ({next: 'https://outside.example.test'})});
  await tick();
  assert.deepEqual(h.redirects, []);
  assert.match(h.nodes.get('message').textContent, /start again/);
});
