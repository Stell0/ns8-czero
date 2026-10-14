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
    return { children: [], value: '', textContent: '', addEventListener() {},
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
        if (url.includes('/objects?')) requests.push({ url, resolve });
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
