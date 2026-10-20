// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const helpers = import(pathToFileURL(path.join(__dirname, '../../ui/src/session-policy.mjs')));

test('policy form round-trips exact non-minute settings without copying other fields', async () => {
  const { sessionPolicyForm, sessionPolicyPayload } = await helpers;
  const saved = {absolute_seconds:121,idle_seconds:61,unexpected:'not a policy field'};
  const form = sessionPolicyForm(saved);
  assert.deepEqual(sessionPolicyPayload(form), {absolute_seconds:121,idle_seconds:61});
  form.idle_seconds='60';
  assert.equal(saved.idle_seconds,61);
  assert.deepEqual(sessionPolicyPayload(form),{absolute_seconds:121,idle_seconds:60});
});

test('invalid numeric drafts cannot be silently rounded or submitted', async () => {
  const { sessionPolicyForm, sessionPolicyPayload } = await helpers;
  for (const idle of ['', '59', '60.5', '86401', 'NaN', 'Infinity']) {
    const form=sessionPolicyForm();form.idle_seconds=idle;
    assert.throws(()=>sessionPolicyPayload(form),/invalid_session_policy/);
  }
  assert.throws(()=>sessionPolicyPayload({absolute_seconds:'60',idle_seconds:'61'}),/invalid_session_policy/);
});
