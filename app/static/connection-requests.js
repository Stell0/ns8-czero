// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id);
  if (!el('cimd-requests')) return;
  let epoch = 0, profile = null;
  const node = (tag, text) => { const value = document.createElement(tag); value.textContent = text; return value; };
  function clear() {
    ++epoch; profile = null; el('cimd-requests').replaceChildren();
    el('cimd-requests-status').textContent = ''; el('cimd-requests-refresh').disabled = true;
  }
  if (window.C0Space) window.C0Space.onClear(clear);
  async function refresh() {
    const captured = ++epoch; profile = null;
    el('cimd-requests-refresh').disabled = true; el('cimd-requests').replaceChildren();
    try {
      const response = await fetch('./api/v1/me', {cache: 'no-store'});
      if (!response.ok || captured !== epoch) return;
      const user = await response.json(); if (captured !== epoch || user.role !== 'admin') return;
      profile = user;
      const pending = await fetch('./api/v1/oauth/connection-requests', {cache: 'no-store'});
      if (captured !== epoch) return;
      if ([401, 403].includes(pending.status)) { clear(); return; }
      if (pending.status === 409) { el('cimd-requests-status').textContent = 'Enable Client metadata discovery in NethServer C0 settings to accept new ChatGPT connections.'; return; }
      if (!pending.ok) throw Error();
      const value = await pending.json(); if (captured !== epoch || profile?.role !== 'admin') return;
      const seen = new Set();
      for (const request of value.requests) {
        if ((request.approved && request.scopes.every(scope => request.allowed_scopes.includes(scope))) || seen.has(request.metadata_url)) continue;
        seen.add(request.metadata_url);
        const item = node('li', ''), button = node('button', 'Review connection'); button.type = 'button';
        item.append(node('p', request.username + ' · ' + request.metadata_url),
          node('p', 'Callback: ' + request.callback), node('p', 'Requested: ' + request.scopes.join(', ')));
        button.addEventListener('click', () => {
          if (captured !== epoch || profile?.role !== 'admin') return;
          document.dispatchEvent(new CustomEvent('c0:review-client', {detail: {metadata_url: request.metadata_url}}));
        });
        item.append(button); el('cimd-requests').append(item);
      }
      el('cimd-requests-status').textContent = seen.size ? 'Review the client, preview its metadata and approve only the permissions needed. Requests expire after five minutes; users can start Connect again.' :
        'No unapproved connection requests. Users appear here after signing in during a new ChatGPT connection.';
    } catch { if (captured === epoch) el('cimd-requests-status').textContent = 'Connection requests are unavailable. Refresh to try again.'; }
    finally { if (captured === epoch) el('cimd-requests-refresh').disabled = profile?.role !== 'admin'; }
  }
  el('cimd-requests-refresh').addEventListener('click', refresh);
  refresh();
})();
