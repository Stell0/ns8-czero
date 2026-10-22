// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id);
  if (!el('onboarding-root') || window.C0?.toolsMode) return;
  let available = false, profile = null, accountEpoch = 0, pageEpoch = 0, draft = 0, busy = false;
  const downloads = new Set();
  const controls = () => { el('download-plugin').disabled = !available || !profile || busy; };
  function clear() {
    ++accountEpoch; ++draft; profile = null;
    el('chatgpt-connection').value = '';
    el('onboarding-signin').hidden = false;
    el('connection-account').textContent = 'Sign in to C0 to prepare your plugin.';
    el('plugin-download-status').textContent = '';
    for (const value of downloads) URL.revokeObjectURL(value);
    downloads.clear(); controls();
  }
  if (window.C0Space) window.C0Space.onClear(clear);
  async function connection() {
    const captured = pageEpoch;
    try {
      const response = await fetch('./agents/connection.json', {cache: 'no-store'});
      if (!response.ok) throw Error();
      const value = await response.json(); if (captured !== pageEpoch) return;
      if (!value.available) {
        el('connection-availability').textContent = 'Ask your administrator to configure this instance’s public HTTPS address and sign-in.';
        return;
      }
      const url = new URL(value.mcp_url);
      if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/mcp' || url.search || url.hash) throw Error();
      available = true;
      for (const [id, text] of [['agent-name', value.name], ['agent-description', value.description], ['agent-mcp-url', value.mcp_url]]) el(id).value = text;
      el('instance-host').textContent = value.hostname;
      el('guide-mcp').hidden = false;
      for (const button of document.querySelectorAll('.copy-icon')) button.disabled = false;
      el('download-skill').href = './agents/c0-memory.skill';
      el('download-skill').setAttribute('aria-disabled', 'false');
      el('connection-availability').textContent = value.client_metadata_enabled ?
        'Ready to connect. A new ChatGPT connection needs one administrator approval before your consent.' :
        'Ask your administrator to enable Client metadata discovery in NethServer C0 settings, then approve your new connection.';
    } catch {
      if (captured === pageEpoch) el('connection-availability').textContent = 'Connection details are unavailable. Refresh this page to try again.';
    } finally { if (captured === pageEpoch) controls(); }
  }
  async function account() {
    const captured = ++accountEpoch;
    try {
      const response = await fetch('./api/v1/me', {cache: 'no-store'});
      if (captured !== accountEpoch) return;
      if (!response.ok) { clear(); return; }
      const value = await response.json(); if (captured !== accountEpoch) return;
      if (!value.csrf_token) { clear(); return; }
      profile = value; el('onboarding-signin').hidden = true;
      el('connection-account').textContent = 'Signed in as ' + (value.display_name || value.username) + ' · ' + value.role;
      el('plugin-download-status').textContent = 'Paste your ChatGPT connection to prepare its plugin.';
      controls();
    } catch { if (captured === accountEpoch) clear(); }
  }
  el('chatgpt-connection').addEventListener('input', () => {
    ++draft;
    if (busy) el('plugin-download-status').textContent = 'Connection details changed. Download again when this request finishes.';
  });
  el('plugin-download-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!available || !profile || busy) return;
    const identity = el('chatgpt-connection').value.trim(), selected = draft, captured = accountEpoch, page = pageEpoch;
    const csrf = profile.csrf_token; busy = true; controls();
    el('plugin-download-status').textContent = 'Preparing your plugin…';
    const current = () => captured === accountEpoch && page === pageEpoch && selected === draft && profile;
    try {
      const response = await fetch('./agents/plugin.zip', {method: 'POST', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-C0-CSRF': csrf},
        body: JSON.stringify({chatgpt_app_id: identity})});
      if (!current()) return;
      if ([401, 403].includes(response.status)) { clear(); return; }
      if (!response.ok) {
        el('plugin-download-status').textContent = response.status === 422 ?
          'Check the connection page address or technical app ID. Copy it from the C0 connection’s details in ChatGPT.' :
          'The plugin could not be prepared. Refresh your sign-in and connection details, then try again.';
        return;
      }
      if (response.headers.get('Content-Type')?.split(';')[0] !== 'application/zip') throw Error();
      const blob = await response.blob(); if (!current()) return;
      const address = URL.createObjectURL(blob); downloads.add(address);
      const anchor = document.createElement('a'); anchor.href = address;
      const filename = /filename="([a-z0-9.-]+)"/.exec(response.headers.get('Content-Disposition') || '');
      anchor.download = filename ? filename[1] : 'c0-plugin.zip'; anchor.hidden = true;
      document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => { URL.revokeObjectURL(address); downloads.delete(address); }, 1000);
      el('plugin-download-status').textContent = 'Plugin downloaded. Upload the ZIP in ChatGPT and verify its C0 connection.';
    } catch {
      if (current()) el('plugin-download-status').textContent = 'The download did not complete. Try again.';
    } finally { busy = false; controls(); }
  });
  window.addEventListener('pagehide', () => { ++pageEpoch; clear(); });
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
  connection(); account();
})();
