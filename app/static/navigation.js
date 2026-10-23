// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const adminLinks = document.querySelectorAll('a[data-admin-link]');
  if (adminLinks.length) {
    fetch('./api/v1/me', {cache: 'no-store'}).then(async response => {
      if (!response.ok) return;
      const profile = await response.json();
      for (const link of adminLinks) link.hidden = profile.role !== 'admin';
    }).catch(() => {});
  }
  const clean = (path) => path.replace(/\/+$/, '') || '/';
  for (const link of document.querySelectorAll('nav[aria-label="C0 navigation"] a')) {
    const destination = new URL(link.href, window.location.href);
    const current = new URL(window.location.href);
    if (clean(destination.pathname) === clean(current.pathname) && (destination.searchParams.get('view') || '') === (current.searchParams.get('view') || '')) {
      link.setAttribute('aria-current', 'page');
    }
  }
  for (const button of document.querySelectorAll('button[data-copy-target]')) {
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      const field = document.getElementById(button.dataset.copyTarget);
      const status = document.getElementById(button.dataset.copyStatus || 'copy-status');
      const value = field.value;
      const label = button.dataset.copyName || 'Server URL';
      button.disabled = true;
      try {
        await navigator.clipboard.writeText(value);
        if (field.value === value) status.textContent = label + ' copied.';
      } catch (_) {
        if (field.value === value) {
          field.focus(); field.select();
          status.textContent = 'Select and copy the ' + label.toLowerCase() + ' above.';
        }
      } finally { button.disabled = false; }
    });
  }
})();
