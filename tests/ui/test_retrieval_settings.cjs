// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const helpers = import(pathToFileURL(path.join(__dirname, '../../ui/src/retrieval-settings.mjs')));

test('retrieval form never copies a saved credential into inputs', async () => {
  const { retrievalForm, retrievalPayload } = await helpers;
  const form = retrievalForm({embedding:{enabled:true,api_key:'unexpected-secret',api_key_configured:true}});
  assert.equal(form.embedding.api_key,'');
  assert.equal(form.embedding.api_key_configured,true);
  const payload = retrievalPayload(form);
  assert.equal(payload.embedding.enabled,true);
  assert.equal(payload.embedding.api_key,'');
  assert.equal('api_key_configured' in payload.embedding,false);
  assert.equal(JSON.stringify(payload).includes('unexpected-secret'),false);
});

test('numeric fields serialize as numbers and clear keys is explicit', async () => {
  const { retrievalForm, retrievalPayload, clearRetrievalKeys } = await helpers;
  const form = retrievalForm();
  form.scorer.threshold='0.8';form.embedding.dimensions='3';form.limits.candidates='16';
  form.scorer.api_key='private-fixture-key';form.embedding.clear_api_key=true;
  const payload=retrievalPayload(form);
  assert.equal(payload.scorer.threshold,.8);
  assert.equal(payload.embedding.dimensions,3);
  assert.equal(payload.limits.candidates,16);
  assert.equal(payload.embedding.clear_api_key,true);
  clearRetrievalKeys(form);
  assert.equal(form.scorer.api_key,'');assert.equal(form.embedding.clear_api_key,false);
  assert.equal(payload.scorer.api_key,'private-fixture-key');
});
