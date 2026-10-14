// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const byId = (id) => document.getElementById(id);
  let csrf = null;
  let busy = false;
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
    try {
      const response = await fetch('/oauth/consent', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-C0-CSRF': csrf },
        body: JSON.stringify({ approve, scopes }) });
      if (!response.ok) throw new Error('consent_failed');
      const result = await response.json();
      // The server returns only an exact administrator-approved callback.
      window.location.assign(result.redirect_uri);
    } catch (_) {
      message('Authorization did not complete. Return to the client and start again.');
    }
  }
  byId('consent-form').addEventListener('submit', (event) => { event.preventDefault(); choose(true); });
  byId('deny').addEventListener('click', () => choose(false));
  (async () => {
    try {
      const response = await fetch('/oauth/consent/request', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('request_failed');
      const value = await response.json();
      csrf = value.csrf_token;
      byId('profile').textContent = 'Signed in as ' + value.profile.username;
      byId('client').textContent = value.client_name;
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
