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
      if (role === 'admin' && (!window.C0 || window.C0.params.get('view') === 'account' || document.body.dataset.page === 'admin')) { sharing.hidden = false; }
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
