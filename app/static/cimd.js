// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id), panel = el('cimd-administration');
  if (!panel) return;
  let profile = null, enabled = false, epoch = 0, listSeq = 0, previewSeq = 0, draft = 0;
  let selected = null, reviewed = null, busy = false;
  let knownClients = [];
  const allowed = () => profile?.role === 'admin';
  const node = (tag, text) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; return value; };
  const message = text => { el('cimd-form-status').textContent = text; };
  function controls() {
    el('cimd-preview').disabled = busy || !enabled || !allowed();
    el('cimd-approve').disabled = busy || !enabled || !allowed() || !reviewed;
  }
  function invalidate() {
    ++previewSeq; reviewed = null; el('cimd-review').replaceChildren(); controls();
  }
  function clear() {
    ++epoch; ++listSeq; ++draft; profile = null; selected = null; enabled = false; busy = false; knownClients = [];
    invalidate(); panel.hidden = true; el('cimd-clients').replaceChildren();
    el('cimd-url').value = ''; el('cimd-url').readOnly = false;
    el('cimd-list-status').textContent = ''; message('');
    for (const scope of ['read', 'write', 'admin']) { el('cimd-' + scope).checked = false; el('cimd-' + scope).disabled = true; }
  }
  if (window.C0Space) window.C0Space.onClear(clear);
  async function api(path, method = 'GET', body = null) {
    if (!allowed()) throw new Error('Application Admin access is required.');
    const captured = epoch, headers = body === null ? {} : {'Content-Type': 'application/json'};
    if (method !== 'GET') headers['X-C0-CSRF'] = profile.csrf_token;
    let response;
    try { response = await fetch('./api/v1/' + path, {method, headers, cache: 'no-store', body: body === null ? null : JSON.stringify(body)}); }
    catch { throw new Error('The request did not complete. Refresh saved state before trying again.'); }
    if (captured !== epoch || !allowed()) throw new Error('Access changed.');
    if ([401, 403].includes(response.status)) {
      if (window.C0Space) window.C0Space.clear('Application access changed. Refresh your account.');
      else clear();
      throw new Error('Access changed. Refresh your account.');
    }
    if (!response.ok) {
      const errors = {404: 'Client metadata discovery needs hostname-root sign-in.',
        409: 'Policy or client metadata changed. Refresh and review before approving again.',
        422: 'Check the exact HTTPS URL, declared permissions and metadata fields.',
        503: 'Metadata is unavailable. Try another review later; existing grants keep their local limits.'};
      throw new Error(errors[response.status] || 'The request did not complete.');
    }
    let value;
    try { value = await response.json(); } catch { throw new Error('The response is unavailable. Refresh saved state.'); }
    if (captured !== epoch || !allowed()) throw new Error('Access changed.');
    return value;
  }
  function choose(client = null) {
    ++draft; selected = client; invalidate();
    el('cimd-url').value = client?.metadata_url || ''; el('cimd-url').readOnly = Boolean(client);
    for (const scope of ['read', 'write', 'admin']) {
      el('cimd-' + scope).checked = client ? client.allowed_scopes.includes('c0:' + scope) : scope === 'read';
      el('cimd-' + scope).disabled = false;
    }
    message(client ? 'Review the current document before reapproving. Its URL stays fixed.' : 'Enter the exact metadata URL shown by your client.');
  }
  async function clients() {
    const sequence = ++listSeq, captured = epoch;
    try {
      const value = await api('oauth/cimd');
      if (sequence !== listSeq || captured !== epoch) return;
      enabled = value.enabled;
      knownClients = value.clients;
      el('cimd-list-status').textContent = enabled ? 'Enabled in NethServer settings. Only individually approved URLs can connect.' :
        'Disabled in NethServer settings. Metadata clients cannot connect; manually approved clients remain available.';
      el('cimd-clients').replaceChildren();
      for (const client of value.clients) {
        const item = node('li'), title = node('p', client.client_name + ' · ' + (client.enabled ? 'enabled' : 'disabled') +
          ' · revision ' + client.revision + (client.review_required ? ' · reapproval required' : ''));
        item.append(title, node('p', client.metadata_url), node('pre', JSON.stringify({
          administration_id: client.client_id, allowed_scopes: client.allowed_scopes,
          approved_descriptor: client.approved_descriptor, verified_at: client.verified_at, fresh_until: client.fresh_until}, null, 2)));
        const review = node('button', 'Review this client'); review.type = 'button';
        review.addEventListener('click', () => { if (allowed() && !busy) choose(client); });
        const toggle = node('button', client.enabled ? 'Disable metadata client' : 'Enable metadata client'); toggle.type = 'button';
        toggle.addEventListener('click', async () => {
          if (!allowed() || toggle.disabled || sequence !== listSeq || captured !== epoch) return;
          toggle.disabled = true;
          try {
            await api('oauth/clients/' + encodeURIComponent(client.client_id), 'PUT', {enabled: !client.enabled, expected_revision: client.revision});
            if (captured !== epoch || sequence !== listSeq) return;
            if (selected?.client_id === client.client_id) { selected = null; invalidate(); }
            await clients();
          } catch (error) { if (captured === epoch && sequence === listSeq) el('cimd-list-status').textContent = error.message; }
          finally { if (captured === epoch) toggle.disabled = false; }
        });
        item.append(review, toggle); el('cimd-clients').append(item);
      }
      if (!enabled) invalidate();
      controls();
    } catch (error) { if (sequence === listSeq && captured === epoch) el('cimd-list-status').textContent = error.message; }
  }
  el('cimd-url').addEventListener('input', () => { ++draft; selected = null; invalidate(); });
  if (document.addEventListener) document.addEventListener('c0:review-client', event => {
    if (!allowed() || busy || typeof event.detail?.metadata_url !== 'string') return;
    const client = knownClients.find(item => item.metadata_url === event.detail.metadata_url);
    choose(client || null);
    if (!client) el('cimd-url').value = event.detail.metadata_url;
    el('cimd-url').focus();
  });
  for (const scope of ['read', 'write', 'admin']) el('cimd-' + scope).addEventListener('change', () => { ++draft; });
  el('cimd-new').addEventListener('click', () => { if (allowed() && !busy) choose(); });
  el('cimd-refresh').addEventListener('click', () => { if (allowed()) clients(); });
  el('cimd-form').addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !allowed() || !enabled) return;
    const url = el('cimd-url').value, generation = draft, sequence = ++previewSeq, captured = epoch;
    busy = true; reviewed = null; controls(); message('Fetching metadata for review…');
    try {
      const value = await api('oauth/cimd/preview', 'POST', {metadata_url: url});
      if (captured !== epoch || sequence !== previewSeq || generation !== draft) return;
      reviewed = {url, digest: value.metadata_digest}; el('cimd-review').replaceChildren();
      el('cimd-review').append(node('h3', value.descriptor.client_name), node('pre', JSON.stringify(value.descriptor, null, 2)));
      const ceiling = value.descriptor.scope_ceiling;
      for (const scope of ['read', 'write', 'admin']) {
        const input = el('cimd-' + scope); input.disabled = ceiling !== null && !ceiling.includes('c0:' + scope);
        if (input.disabled) input.checked = false;
      }
      message('Review the exact client URL, name, callbacks and permissions. Approval fetches the document again.');
    } catch (error) { if (captured === epoch && sequence === previewSeq && generation === draft) message(error.message); }
    finally { if (captured === epoch) { busy = false; controls(); } }
  });
  el('cimd-approve').addEventListener('click', async () => {
    if (busy || !allowed() || !enabled || !reviewed) return;
    const scopes = ['read', 'write', 'admin'].filter(scope => el('cimd-' + scope).checked).map(scope => 'c0:' + scope);
    if (!scopes.length) { message('Select at least one declared permission.'); return; }
    const generation = draft, captured = epoch, choice = selected;
    const path = choice ? 'oauth/cimd/clients/' + encodeURIComponent(choice.client_id) : 'oauth/cimd/clients';
    const body = {metadata_digest: reviewed.digest, allowed_scopes: scopes};
    if (choice) body.expected_revision = choice.revision; else body.metadata_url = reviewed.url;
    busy = true; controls(); message('Approving reviewed metadata…');
    try {
      const result = await api(path, choice ? 'PUT' : 'POST', body);
      if (captured !== epoch) return;
      if (generation === draft) { selected = result; el('cimd-url').readOnly = true; invalidate(); }
      await clients();
      if (captured === epoch) message(generation === draft ? 'Approval saved. Users must sign in and consent; disabled clients stay disabled.' :
        'Earlier approval saved. Your newer draft is preserved.');
    } catch (error) { if (captured === epoch && generation === draft) { invalidate(); message(error.message); } }
    finally { if (captured === epoch) { busy = false; controls(); } }
  });
  (async () => {
    const captured = epoch;
    try {
      const response = await fetch('./api/v1/me', {cache: 'no-store'});
      if (!response.ok) return;
      const current = await response.json(); if (captured !== epoch) return;
      profile = current; if (!allowed()) return;
      panel.hidden = false; choose(); await clients();
    } catch { if (captured === epoch) el('cimd-list-status').textContent = 'Metadata client administration is unavailable.'; }
  })();
})();
