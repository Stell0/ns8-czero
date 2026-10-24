// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const helpers = import(pathToFileURL(path.join(__dirname,'../../ui/src/connection-policy.mjs')));

test('connection inactivity round-trips whole days and defaults to thirty',async()=>{
  const {connectionPolicyForm,connectionPolicyPayload} = await helpers;
  assert.equal(connectionPolicyPayload(connectionPolicyForm()),2592000);
  for (const days of [1,14,365]) assert.equal(connectionPolicyPayload(connectionPolicyForm(days*86400)),days*86400);
});

test('invalid inactivity drafts are rejected without rounding',async()=>{
  const {connectionPolicyPayload} = await helpers;
  for (const value of ['',0,'1.5','366','NaN','Infinity',true,null,[1]]) assert.throws(()=>connectionPolicyPayload(value),/invalid_connection_policy/);
});
