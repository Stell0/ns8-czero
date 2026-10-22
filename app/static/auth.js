// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const byId = (id) => document.getElementById(id);
  const accountStatus = byId('account-status'), signIn = byId('sign-in'), signOut = byId('sign-out');
  const sharing = byId('sharing'), accounts = byId('accounts'), sharingStatus = byId('sharing-status');
  const refreshAccount = byId('refresh-account');
  let csrfToken = null, role = null, accountGeneration = 0, listGeneration = 0;
  if(typeof window!=='undefined' && window.C0Space)window.C0Space.onClear(()=>{
    ++accountGeneration;++listGeneration;csrfToken=null;role=null;accounts.replaceChildren();sharing.hidden=true;
    accountStatus.textContent='Space access changed. Choose a permitted space or refresh access.';
  });
  const current = (generation) => generation === accountGeneration;
  async function loadAccounts(generation) {
    const sequence = ++listGeneration;
    const response = await fetch('./api/v1/access/accounts', { cache: 'no-store' });
    if (!current(generation) || role !== 'admin' || sequence !== listGeneration) return;
    if (!response.ok) throw new Error('access_unavailable');
    const result = await response.json();
    if (!current(generation) || role !== 'admin' || sequence !== listGeneration) return;
    accounts.replaceChildren();
    if (!result.accounts.length) { sharingStatus.textContent = 'No verified accounts have signed in yet.'; return; }
    for (const account of result.accounts) {
      const row = document.createElement('tr'), name = document.createElement('td');
      name.textContent = account.display_name || account.username;
      const detail = document.createElement('small');
      detail.textContent = `${account.username} · last sign-in ${new Date(account.last_seen).toLocaleString()}`;
      name.append(detail);
      const access = document.createElement('td'), action = document.createElement('td');
      if (account.is_owner) { access.textContent = 'Owner (Admin)'; }
      else {
        const select = document.createElement('select');
        select.setAttribute('aria-label', `Access for ${account.username}`);
        for (const [value, label] of [['', 'Blocked'], ['reader', 'Reader'], ['editor', 'Editor'], ['admin', 'Admin']]) {
          const option = document.createElement('option'); option.value = value; option.textContent = label; select.append(option);
        }
        select.value = account.role || '';
        const save = document.createElement('button'); save.type = 'button'; save.textContent = 'Save';
        save.setAttribute('aria-label', `Save access for ${account.username}`);
        save.addEventListener('click', async () => {
          if (save.disabled || !current(generation) || role !== 'admin') return;
          const chosen = select.value, csrf = csrfToken;
          save.disabled = true; select.disabled = true;
          try {
            const updated = await fetch(`./api/v1/access/accounts/${encodeURIComponent(account.id)}`, {
              method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-C0-CSRF': csrf },
              body: JSON.stringify({ role: chosen || null }),
            });
            if (!current(generation)) return;
            if (!updated.ok) throw new Error('access_not_saved');
            if (select.value !== chosen) {
              sharingStatus.textContent = 'Earlier selection saved. Save the current selection to apply it.'; return;
            }
            sharingStatus.textContent = 'Access saved'; await loadAccounts(generation);
          } catch (_) {
            if (current(generation)) sharingStatus.textContent = 'Access was not saved. Refresh sign-in and try again.';
          } finally { save.disabled = false; select.disabled = false; }
        });
        access.append(select); action.append(save);
      }
      row.append(name, access, action); accounts.append(row);
    }
  }
  async function checkAccount() {
    const generation = ++accountGeneration; ++listGeneration;
    csrfToken = null; role = null; accounts.replaceChildren(); sharing.hidden = true;
    signIn.hidden = true; signOut.hidden = true; refreshAccount.disabled = true;
    accountStatus.textContent = 'Checking sign-in...';
    try {
      const responseStatus = await fetch('./api/v1/auth/status', { cache: 'no-store' });
      if (!current(generation)) return;
      if (!responseStatus.ok) throw new Error('sign_in_unavailable');
      const status = await responseStatus.json();
      if (!current(generation)) return;
      if (!status.configured) { accountStatus.textContent = 'Ask the NethServer administrator to configure sign-in.'; return; }
      signIn.hidden = false;
      const response = await fetch('./api/v1/me', { cache: 'no-store' });
      if (!current(generation)) return;
      if (response.status === 401) { accountStatus.textContent = 'Sign in to use C0.'; return; }
      if (response.status === 403) { accountStatus.textContent = 'Your account has no C0 access. Ask the owner to admit it.'; return; }
      if (!response.ok) throw new Error('sign_in_unavailable');
      const user = await response.json();
      if (!current(generation)) return;
      csrfToken = user.csrf_token; role = user.role;
      accountStatus.textContent = `Signed in as ${user.username} · ${user.is_owner ? 'Owner (Admin)' : user.role}`;
      signIn.hidden = true; signOut.hidden = false;
      if (role === 'admin' && (!window.C0 || window.C0.params.get('view') === 'account' || document.body.dataset.page === 'admin')) { sharing.hidden = false; await loadAccounts(generation); }
    } catch (_) {
      if (current(generation)) accountStatus.textContent = 'Sign-in is unavailable. Try again later.';
    } finally { if (current(generation)) refreshAccount.disabled = false; }
  }
  signOut.addEventListener('click', async () => {
    if (signOut.disabled || !csrfToken) return;
    const generation = accountGeneration, csrf = csrfToken; signOut.disabled = true;
    try {
      const response = await fetch('./auth/logout', { method: 'POST', headers: { 'X-C0-CSRF': csrf } });
      if (!current(generation)) return;
      if (!response.ok) throw new Error('sign_out_unavailable');
      const result = await response.json();
      if (!current(generation)) return;
      window.location.assign(result.logout_url);
    } catch (_) {
      if (current(generation)) accountStatus.textContent = 'Sign-out did not complete. Refresh and try again.';
    } finally { if (current(generation)) signOut.disabled = false; }
  });
  refreshAccount.addEventListener('click', checkAccount);
  checkAccount();
})();
