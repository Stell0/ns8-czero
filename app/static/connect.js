// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id);
  let profile = null, view = null, reviewed = null, existing = null, epoch = 0, busy = false, previewSequence = 0;
  const scopes = () => ['read', 'write', 'admin'].filter(s => el('connect-' + s).checked && !el('connect-' + s).disabled).map(s => 'c0:' + s);
  const say = message => { el('connect-status').textContent = message; };
  const node = (tag, text) => { const value = document.createElement(tag); value.textContent = text; return value; };
  function controls() {
    const selected = scopes();
    el('connect-next').disabled = busy || !profile || !view?.approved || !selected.length || selected.some(s => !view.allowed_scopes.includes(s));
    el('connect-preview').disabled = busy || profile?.role !== 'admin';
    el('connect-approve').disabled = busy || profile?.role !== 'admin' || !reviewed || !selected.length || existing?.enabled === false ||
      (reviewed.descriptor.scope_ceiling && selected.some(s => !reviewed.descriptor.scope_ceiling.includes(s)));
    el('connect-refresh').disabled = busy;
  }
  function clear() {
    profile = null; view = null; reviewed = null; existing = null; ++previewSequence;
    el('connect-workspace').hidden = true; el('connect-review').replaceChildren();
    el('connect-client').textContent = ''; el('connect-callback').textContent = '';
    el('connect-account').textContent = ''; el('connect-admin-link').hidden = true;
    for (const scope of ['read', 'write', 'admin']) el('connect-' + scope).disabled = true;
    controls();
  }
  async function api(path, method = 'GET', body = null, csrf = profile?.csrf_token) {
    const captured = epoch;
    const headers = body === null ? {} : {'Content-Type': 'application/json'};
    if (method !== 'GET') headers['X-C0-CSRF'] = csrf;
    let response;
    try { response = await fetch(path, {method, headers, cache: 'no-store', body: body === null ? null : JSON.stringify(body)}); }
    catch { throw Error('The request did not complete. Refresh saved state before trying again.'); }
    if (captured !== epoch) throw Error('stale');
    if (!response.ok) {
      const messages = {401: 'Sign in to C0 to continue.', 403: 'Your account cannot perform this action. Ask your C0 administrator.',
        410: 'This connection request expired. Return to ChatGPT and start Connect again.',
        409: 'The connection or discovery setting changed. Review it again or ask your administrator.',
        422: 'Check the selected permissions and reviewed connection.',
        503: 'The sign-in or client metadata service is unavailable. Try again later.'};
      if ([401, 403, 410].includes(response.status)) clear();
      el('connect-signin').hidden = response.status !== 401;
      throw Error(messages[response.status] || 'The request did not complete. Try again.');
    }
    let result;
    try { result = await response.json(); } catch { throw Error('The response is unavailable. Refresh saved state.'); }
    if (captured !== epoch) throw Error('stale');
    return result;
  }
  function render(value) {
    view = value; profile = {...value.profile, csrf_token: value.csrf_token};
    el('connect-workspace').hidden = false; el('connect-signin').hidden = true;
    el('connect-account').textContent = 'Signed in as ' + (profile.display_name || profile.username) + ' · ' + profile.role;
    el('connect-client').textContent = value.metadata_url; el('connect-callback').textContent = value.callback;
    el('connect-admin-link').hidden = profile.role !== 'admin';
    el('connect-review-panel').hidden = profile.role !== 'admin';
    for (const scope of ['read', 'write', 'admin']) {
      const eligible = scope === 'read' || (scope === 'write' && ['editor', 'admin'].includes(profile.role)) || (scope === 'admin' && profile.role === 'admin');
      const offered = value.scopes.includes('c0:' + scope) && eligible;
      el('connect-' + scope + '-label').hidden = !offered;
      el('connect-' + scope).disabled = !offered || (profile.role !== 'admin' && !value.allowed_scopes.includes('c0:' + scope));
      if (!offered) el('connect-' + scope).checked = false;
    }
    say(value.approved ? 'Choose approved permissions and continue to your consent page.' :
      profile.role === 'admin' ? 'Review and approve this new connection below, then continue.' :
      'Your connection needs administrator approval. Ask an administrator to open C0 Administration → ChatGPT connections, then check approval here.');
    controls();
  }
  async function load() {
    const captured = ++epoch; busy = true; controls();
    reviewed = null; existing = null; ++previewSequence; el('connect-review').replaceChildren();
    try {
      const me = await api('/api/v1/me');
      if (captured !== epoch) return;
      const value = await api('/oauth/connect/request', 'POST', {}, me.csrf_token);
      if (captured === epoch) render(value);
    } catch (error) { if (captured === epoch) say(error.message === 'stale' ? 'Refresh this page to continue.' : error.message); }
    finally { if (captured === epoch) { busy = false; controls(); } }
  }
  for (const scope of ['read', 'write', 'admin']) el('connect-' + scope).addEventListener('change', () => {
    ++previewSequence; reviewed = null; el('connect-review').replaceChildren(); controls();
  });
  el('connect-refresh').addEventListener('click', () => { if (!busy) load(); });
  el('connect-preview').addEventListener('click', async () => {
    if (busy || profile?.role !== 'admin' || !view) return;
    const captured = epoch, sequence = ++previewSequence, url = view.metadata_url;
    busy = true; reviewed = null; controls();
    try {
      const result = await api('/api/v1/oauth/cimd/preview', 'POST', {metadata_url: url});
      const current = await api('/api/v1/oauth/cimd');
      if (captured !== epoch || sequence !== previewSequence || profile?.role !== 'admin') return;
      if (result.descriptor.client_id !== url || !result.descriptor.redirect_uris.includes(view.callback)) {
        say('The reviewed identity or callback does not match this request. Do not approve it.'); return;
      }
      existing = current.clients.find(client => client.metadata_url === url) || null;
      reviewed = result;
      const callbacks = node('ul', '');
      for (const callback of result.descriptor.redirect_uris) callbacks.append(node('li', callback));
      el('connect-review').replaceChildren(node('h3', result.descriptor.client_name),
        node('p', result.descriptor.client_id), node('p', 'Declared callbacks'), callbacks,
        node('p', 'Public client authentication: none. No client secret is required.'));
      say(existing?.enabled === false ? 'This connection is disabled. An administrator must enable it in Administration before fresh consent.' :
        'Check the identity and callbacks above, then approve only the selected permissions.');
    } catch (error) { if (captured === epoch && sequence === previewSequence) say(error.message); }
    finally { if (captured === epoch) { busy = false; controls(); } }
  });
  el('connect-approve').addEventListener('click', async () => {
    if (busy || !reviewed || profile?.role !== 'admin' || existing?.enabled === false) return;
    const captured = epoch, sequence = previewSequence, choice = scopes(), digest = reviewed.metadata_digest;
    if (!choice.length) return;
    busy = true; controls();
    try {
      const path = '/api/v1/oauth/cimd/clients' + (existing ? '/' + encodeURIComponent(existing.client_id) : '');
      const data = {metadata_digest: digest, allowed_scopes: choice,
        ...(existing ? {expected_revision: existing.revision} : {metadata_url: view.metadata_url})};
      await api(path, existing ? 'PUT' : 'POST', data);
      if (captured !== epoch) return;
      const value = await api('/oauth/connect/request', 'POST', {});
      render(value);
      if (sequence !== previewSequence) say('Earlier permissions were saved. Check approval before applying your new selection.');
      reviewed = null; el('connect-review').replaceChildren();
    } catch (error) {
      if (captured === epoch) { reviewed = null; el('connect-review').replaceChildren(); say(error.message); }
    }
    finally { if (captured === epoch) { busy = false; controls(); } }
  });
  el('connect-continue').addEventListener('submit', async event => {
    event.preventDefault(); if (el('connect-next').disabled || busy || !profile) return;
    const captured = epoch, choice = scopes(); busy = true; controls();
    try {
      const result = await api('/oauth/connect/continue', 'POST', {scopes: choice});
      if (captured === epoch) {
        if (result.next !== '/oauth/consent') throw Error('The connection did not return a consent page. Start Connect again.');
        window.location.assign(result.next);
      }
    } catch (error) { if (captured === epoch) say(error.message); }
    finally { if (captured === epoch) { busy = false; controls(); } }
  });
  window.addEventListener('pagehide', () => { ++epoch; clear(); });
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
  load();
})();
