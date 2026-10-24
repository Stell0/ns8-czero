// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  if (!window.C0 || window.C0.params.get('view') !== 'account') return;
  const byId = id => document.getElementById(id);
  const panel = byId('connections-panel'), list = byId('connections-list');
  const message = byId('connections-message'), refresh = byId('refresh-connections');
  let generation = 0, csrf = null;
  function clear() {
    ++generation; csrf = null; list.replaceChildren();
    message.textContent = 'Refresh connections to check your current access.';
    refresh.disabled = false;
  }
  if (window.C0Space) window.C0Space.onClear(clear);
  byId('sign-out')?.addEventListener('click', clear);
  async function load() {
    const current = ++generation;
    csrf = null; list.replaceChildren(); panel.hidden = false; refresh.disabled = true;
    message.textContent = 'Checking your connections…';
    try {
      const response = await fetch('./api/v1/oauth/connections', {credentials:'same-origin',cache:'no-store'});
      if (current !== generation) return;
      if (!response.ok) throw new Error('connections_unavailable');
      const value = await response.json();
      if (current !== generation) return;
      csrf = value.csrf_token;
      for (const connection of value.connections) {
        const item = document.createElement('li');
        const name = document.createElement('strong'); name.textContent = connection.client_name;
        const detail = document.createElement('p');
        const expires = new Date(connection.persistent ? connection.idle_until : connection.expires_at).toLocaleString();
        const lastUse = connection.last_used_at ? new Date(connection.last_used_at).toLocaleString() : 'Not recorded';
        detail.textContent = `${connection.scopes.join(', ')} · ${connection.persistent ? 'Background access; inactivity deadline' : 'Session access; ends'} ${expires} · Last used: ${lastUse}`;
        const disconnect = document.createElement('button');
        disconnect.type = 'button'; disconnect.textContent = 'Disconnect';
        disconnect.setAttribute('aria-label', `Disconnect ${connection.client_name}`);
        disconnect.addEventListener('click', async () => {
          if (current !== generation || disconnect.disabled || !csrf) return;
          const capturedCsrf = csrf;
          disconnect.disabled = true;
          try {
            const result = await fetch(`./api/v1/oauth/connections/${encodeURIComponent(connection.id)}`, {
              method:'DELETE',credentials:'same-origin',headers:{'X-C0-CSRF':capturedCsrf},
            });
            if (current !== generation) return;
            if (result.status === 401 || result.status === 403) {
              clear(); message.textContent = 'Sign in again to manage your connections.'; return;
            }
            if (!result.ok) throw new Error('disconnect_failed');
            await load();
          } catch (_) {
            if (current === generation) message.textContent = 'Disconnect was not confirmed. Refresh connections to check before trying again.';
          } finally {
            if (current === generation) disconnect.disabled = false;
          }
        });
        item.append(name,detail,disconnect); list.append(item);
      }
      message.textContent = value.connections.length ? 'Disconnect stops further use by this connection.' : 'No active connections.';
    } catch (_) {
      if (current === generation) {
        csrf = null; list.replaceChildren();
        message.textContent = 'Connections are unavailable. Sign in or refresh access and try again.';
      }
    } finally {
      if (current === generation) refresh.disabled = false;
    }
  }
  refresh.addEventListener('click', load);
  load();
})();
