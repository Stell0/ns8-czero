// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const byId = (id) => document.getElementById(id);
  let csrf = null;
  let busy = false;
  let backgroundReady = false;
  const background = byId('background');
  function approvalLabel() {
    byId('approve').textContent = background.checked && !backgroundReady
      ? 'Continue to background sign-in' : 'Authorize';
  }
  const labels = { 'c0:read': 'Read shared knowledge and records',
    'c0:write': 'Write knowledge and records', 'c0:admin': 'Manage application access and jobs' };
  const message = (text) => { byId('message').textContent = text; };
  function buttons(disabled) {
    byId('approve').disabled = disabled;
    byId('deny').disabled = disabled;
  }
  async function choose(approve) {
    if (busy || !csrf) return;
    const scopes = Array.from(byId('scopes').querySelectorAll('input:checked')).map((input) => input.value);
    if (approve && scopes.length === 0) {
      message('Select at least one available permission, or deny the request.');
      return;
    }
    busy = true;
    buttons(true);
    background.disabled = true;
    try {
      const persistent = approve && background.checked;
      const signIn = persistent && !backgroundReady;
      const response = await fetch(signIn ? '/oauth/consent/background' : '/oauth/consent', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-C0-CSRF': csrf },
        body: JSON.stringify(signIn ? { scopes } : { approve, scopes, persistent }) });
      if (!response.ok) throw new Error('consent_failed');
      const result = await response.json();
      // The server returns only an exact administrator-approved callback.
      if (signIn) {
        if (result.next !== '/auth/login') throw new Error('invalid_destination');
        window.location.assign('/auth/login');
      } else window.location.assign(result.redirect_uri);
    } catch (_) {
      message('Authorization did not complete. Return to the client and start again.');
    }
  }
  byId('consent-form').addEventListener('submit', (event) => { event.preventDefault(); choose(true); });
  byId('deny').addEventListener('click', () => choose(false));
  background.addEventListener('change', approvalLabel);
  (async () => {
    try {
      const response = await fetch('/oauth/consent/request', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('request_failed');
      const value = await response.json();
      csrf = value.csrf_token;
      backgroundReady = value.background_ready === true;
      byId('background-option').hidden = value.background_supported !== true;
      background.checked = value.background_supported === true && value.background_requested === true;
      background.disabled = value.background_supported !== true;
      if (value.background_supported === true) {
        const seconds = value.connection_idle_seconds;
        const duration = seconds >= 86400 && seconds % 86400 === 0
          ? `${seconds / 86400} days` : `${seconds} seconds`;
        byId('background-help').textContent = `This connection has no fixed end date while used. It ends after ${duration} without activity, or when access is revoked.`;
      }
      approvalLabel();
      byId('profile').textContent = 'Signed in as ' + value.profile.username;
      byId('client').textContent = value.client_name;
      if (typeof value.client_id === 'string' && value.client_id.toLowerCase().startsWith('https://')) {
        byId('client-identity').textContent = 'Approved client metadata URL: ' + value.client_id;
        byId('client-identity').hidden = false;
      }
      byId('callback').textContent = value.callback;
      for (const scope of value.scopes) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox'; input.value = scope;
        input.disabled = !value.eligible_scopes.includes(scope); input.checked = !input.disabled;
        label.appendChild(input); label.appendChild(document.createTextNode(labels[scope] || scope));
        byId('scopes').appendChild(label);
      }
      buttons(false);
    } catch (_) {
      message('This request is invalid or expired. Return to the client and start again.');
    }
  })();
})();
