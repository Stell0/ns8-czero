(
// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
// Browser-only smoke check. Return counts, never DOM text, URLs or identities.
() => {
  const visible = element => element.type !== 'hidden' &&
    element.getClientRects().length > 0 &&
    getComputedStyle(element).visibility !== 'hidden' &&
    !element.closest('[aria-hidden="true"]');
  const text = element => (element?.textContent || '').trim();
  const name = element => {
    const explicit = (element.getAttribute('aria-label') || '').trim();
    if (explicit) return explicit;
    const references = (element.getAttribute('aria-labelledby') || '').trim();
    if (references) {
      const labels = references.split(/\s+/).map(id => text(document.getElementById(id))).join(' ').trim();
      if (labels) return labels;
    }
    const labels = Array.from(element.labels || []).map(text).join(' ').trim();
    if (labels) return labels;
    if (['BUTTON', 'A'].includes(element.tagName)) {
      return text(element) || (element.querySelector('img[alt]')?.alt || '').trim();
    }
    if (['button', 'submit', 'reset'].includes(element.type)) return (element.value || '').trim();
    return '';
  };
  const controls = Array.from(document.querySelectorAll('input,select,textarea,button')).filter(visible);
  const links = Array.from(document.querySelectorAll('a[href]')).filter(visible);
  const skip = document.querySelector('.skip-link');
  const target = skip?.getAttribute('href') || '';
  let localSkipTarget = false;
  try {
    const current = new URL(window.location.href);
    const destination = new URL(target, document.baseURI || current.href);
    localSkipTarget = Boolean(target && destination.origin === current.origin &&
      destination.pathname === current.pathname && destination.search === current.search &&
      destination.hash && document.getElementById(decodeURIComponent(destination.hash.slice(1))));
  } catch { /* Malformed links must fail the same numeric guard. */ }
  return {
    controls_checked: controls.length,
    links_checked: links.length,
    unnamed_controls: controls.filter(element => !name(element)).length,
    unnamed_links: links.filter(element => !name(element)).length,
    missing_language: document.documentElement.lang.trim() ? 0 : 1,
    missing_main: document.querySelector('main') ? 0 : 1,
    missing_h1: document.querySelectorAll('h1').length === 1 ? 0 : 1,
    missing_navigation: document.querySelector('nav[aria-label="C0 navigation"]') ? 0 : 1,
    missing_skip_target: localSkipTarget ? 0 : 1,
  };
}

)
