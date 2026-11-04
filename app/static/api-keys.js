// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  if (!window.C0 || window.C0.params.get('view') !== 'account') return;
  const $ = id => document.getElementById(id);
  let generation = 0, csrf = null, creating = false;
  function secretClear() { $('api-key-secret').value = ''; $('api-key-secret-panel').hidden = true; }
  function clear() {
    ++generation; csrf = null; secretClear(); $('api-key-list').replaceChildren();
    $('api-key-spaces').replaceChildren(Object.assign(document.createElement('legend'), {textContent:'Allowed spaces'}));
    $('api-keys-panel').hidden = true;
  }
  window.C0Space?.onClear(clear);
  $('sign-out')?.addEventListener('click', clear);
  window.addEventListener('pagehide', clear);
  $('api-key-dismiss').addEventListener('click', secretClear);
  $('api-key-copy').addEventListener('click', async () => {
    const current = generation;
    try { await navigator.clipboard.writeText($('api-key-secret').value);
      if (current === generation) $('api-key-status').textContent = 'Key copied.';
    } catch (_) { if (current === generation) $('api-key-status').textContent = 'Select the key and copy it manually.'; }
  });
  async function load() {
    clear(); const current = generation;
    try {
      const responses = await Promise.all(['./api/v1/api-keys', './api/v1/spaces'].map(url => fetch(url, {credentials:'same-origin',cache:'no-store'})));
      if (current !== generation) return;
      if (responses.some(r => !r.ok)) throw new Error();
      const [data, spaces] = await Promise.all(responses.map(r => r.json()));
      if (current !== generation) return;
      csrf = data.csrf_token; $('api-keys-panel').hidden = false;
      const spaceNames = new Map(spaces.spaces.map(space => [space.id,space.name]));
      for (const space of spaces.spaces) {
        const label = document.createElement('label'), input = document.createElement('input');
        input.type = 'checkbox'; input.value = space.id; input.dataset.role = space.role;
        label.append(input, document.createTextNode(space.name)); $('api-key-spaces').append(label);
      }
      for (const key of data.api_keys) {
        const item = document.createElement('li'), text = document.createElement('p'), revoke = document.createElement('button');
        text.textContent = `${key.name} · Created: ${new Date(key.created_at).toLocaleString()} · ${key.scopes.map(scope => ({'c0:read':'Read','c0:write':'Write'}[scope] || scope)).join(', ')} · Spaces: ${key.space_ids.map(id => spaceNames.get(id) || 'Unavailable space').join(', ')} · ${key.revoked_at ? 'Revoked' : key.expires_at ? 'Expires '+new Date(key.expires_at).toLocaleString() : 'No expiration'} · Last used: ${key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'Never'}`;
        revoke.type = 'button'; revoke.textContent = 'Revoke key'; revoke.setAttribute('aria-label', 'Revoke key '+key.name); revoke.disabled = !!key.revoked_at;
        revoke.addEventListener('click', async () => {
          if (current !== generation || !csrf || revoke.disabled) return;
          revoke.disabled = true; secretClear();
          try {
            const response = await fetch('./api/v1/api-keys/'+encodeURIComponent(key.id), {method:'DELETE',credentials:'same-origin',headers:{'X-C0-CSRF':csrf}});
            if (current !== generation) return;
            if (response.status===401 || response.status===403) { clear(); return; }
            if (!response.ok) throw new Error();
            await load();
          } catch (_) { if (current === generation) { $('api-key-status').textContent = 'Revocation was not confirmed. Refresh keys to check.'; revoke.disabled = false; } }
        });
        item.append(text, revoke); $('api-key-list').append(item);
      }
      $('api-key-status').textContent = data.api_keys.length ? 'Revoked keys cannot be used again.' : 'No API keys.';
      return true;
    } catch (_) { if (current === generation) { clear(); $('api-key-status').textContent = 'Sign in or refresh access to manage keys.'; } }
  }
  $('api-key-refresh').addEventListener('click', load);
  $('refresh-account')?.addEventListener('click', load);
  $('api-key-create').addEventListener('submit', async event => {
    event.preventDefault(); if (!csrf || creating) return;
    const selected = Array.from($('api-key-spaces').querySelectorAll('input:checked'));
    if (!selected.length) { $('api-key-status').textContent = 'Select at least one space.'; return; }
    if ($('api-key-permissions').value === 'write' && selected.some(input => !['editor','admin'].includes(input.dataset.role))) {
      $('api-key-status').textContent = 'Write access is required in every selected space.'; return;
    }
    creating = true;
    const current = generation, button = event.target.querySelector('button[type="submit"]');
    button.disabled = true; secretClear();
    const space_ids = selected.map(input => input.value);
    try {
      const response = await fetch('./api/v1/api-keys', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-C0-CSRF':csrf},
        body:JSON.stringify({name:$('api-key-name').value,scopes:$('api-key-permissions').value==='write' ? ['c0:read','c0:write'] : ['c0:read'],space_ids,lifetime_days:$('api-key-expiry').value ? Number($('api-key-expiry').value) : null})});
      if (current !== generation) return;
      if (response.status===401) { clear(); return; }
      if (response.status===403) {
        if (await load()) $('api-key-status').textContent = 'Key creation was denied. Review your access and key settings.';
        return;
      }
      if (response.status===422) {
        $('api-key-status').textContent = 'Check the key settings or revoke unused keys if you reached the limit.'; return;
      }
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (current !== generation) return;
      $('api-key-secret').value = result.key; $('api-key-secret-panel').hidden = false;
      $('api-key-secret').focus(); $('api-key-secret').select();
      $('api-key-status').textContent = 'Key created. Copy it before refreshing or leaving this page.';
    } catch (_) { if (current === generation) $('api-key-status').textContent = 'Creation was not confirmed. Refresh keys before retrying. Check permissions and select at least one space.'; }
    finally { creating = false; button.disabled = false; }
  });
  load();
})();
