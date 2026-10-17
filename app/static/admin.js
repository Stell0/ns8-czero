// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id);
  let profile = null, clientSeq = 0, jobSeq = 0, scheduleSeq = 0, adminEpoch = 0;
  let jobDetailSeq = 0, scheduleDetailSeq = 0, selectedSchedule = null, pendingJob = null;
  const allowed = () => profile && profile.role === 'admin';
  if(typeof window!=='undefined' && window.C0Space)window.C0Space.onClear(()=>{
    ++adminEpoch;++clientSeq;++jobSeq;++scheduleSeq;++jobDetailSeq;++scheduleDetailSeq;
    profile=null;selectedSchedule=null;pendingJob=null;el('admin-workspace').hidden=true;
    for(const id of ['client-list','job-list','schedule-list','job-handler','schedule-handler'])el(id).replaceChildren();
    el('admin-account').textContent='Space access changed. Choose a permitted space.';
    for(const id of ['client-status','job-status','schedule-status','job-data','job-runs','schedule-runs','schedule-identity'])el(id).textContent='';
    for(const id of ['client-name','client-callbacks','job-payload','schedule-name','schedule-payload'])el(id).value='';
  });
  const message = (id, text) => { el(id).textContent = text; };
  const jsonObject = text => {
    const value = JSON.parse(text);
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Enter a JSON object.');
    return value;
  };
  const inputError = error => error instanceof SyntaxError ? 'Enter valid JSON.' : error.message;
  async function api(path, method = 'GET', body = null) {
    if (!allowed()) throw new Error('Only application Admins can manage these settings.');
    const captured=adminEpoch;
    const headers = body === null ? {} : {'Content-Type': 'application/json'};
    if (method !== 'GET') headers['X-C0-CSRF'] = profile.csrf_token;
    let response;
    try {
      response = await fetch('./api/v1/' + path, {
        method, headers, cache: 'no-store', body: body === null ? null : JSON.stringify(body)
      });
    } catch (_) { throw new Error('The request did not complete. Refresh to check saved state before retrying.'); }
    if(captured!==adminEpoch || !allowed())throw new Error('Access changed. Refresh your account.');
    if (!response.ok) {
      if ([401, 403].includes(response.status)) {
        if(typeof window!=='undefined' && window.C0Space)window.C0Space.clear('Application access changed. Refresh your account.');
        profile = null;
        el('admin-workspace').hidden = true;
        el('admin-signin').hidden = false;
        message('admin-account', 'Access changed. Sign in again or ask an Admin.');
        for (const id of ['client-list', 'job-list', 'schedule-list']) el(id).replaceChildren();
        for (const id of ['job-data', 'job-runs', 'schedule-runs']) message(id, '');
      }
      const errors = {
        401: 'Sign in again.', 403: 'Your account cannot perform this operation.',
        409: 'The saved data changed or this request conflicts. Refresh before retrying.',
        422: 'Check the fields, JSON input and limits.', 503: 'The service is unavailable. Try again later.'
      };
      throw new Error(errors[response.status] || 'The request did not complete.');
    }
    let value;try{value=response.status===204?null:await response.json();}catch{throw new Error('The response is unavailable. Refresh to check saved state.');}
    if(captured!==adminEpoch || !allowed())throw new Error('Access changed. Refresh your account.');
    return value;
  }
  function item(title) {
    const li = document.createElement('li'), text = document.createElement('p');
    text.textContent = title; li.append(text); return li;
  }
  function button(text, action) {
    const node = document.createElement('button'); node.type = 'button';
    node.textContent = text; node.addEventListener('click', action); return node;
  }
  async function clients() {
    const seq = ++clientSeq;
    message('client-status', 'Loading clients...');
    try {
      const result = await api('oauth/clients');
      if (seq !== clientSeq || !allowed()) return;
      el('client-list').replaceChildren();
      for (const client of result.clients) {
        const row = item(client.client_name + ' · ' + (client.enabled ? 'enabled' : 'disabled') + ' · revision ' + client.revision);
        const details = document.createElement('pre');
        details.textContent = JSON.stringify({client_id: client.client_id, redirect_uris: client.redirect_uris, allowed_scopes: client.allowed_scopes}, null, 2);
        row.append(details);
        const toggle = button(client.enabled ? 'Disable client' : 'Enable client', async () => {
          if (toggle.disabled || !allowed()) return;
          toggle.disabled = true;
          try {
            await api('oauth/clients/' + client.client_id, 'PUT', {enabled: !client.enabled, expected_revision: client.revision});
            if (seq === clientSeq) await clients();
          } catch (error) { if (seq === clientSeq) message('client-status', error.message); }
          finally { toggle.disabled = false; }
        });
        row.append(toggle); el('client-list').append(row);
      }
      message('client-status', result.clients.length ? result.clients.length + ' approved clients.' : 'No approved clients.');
    } catch (error) { if (seq === clientSeq) message('client-status', error.message); }
  }
  async function jobs() {
    const seq = ++jobSeq;
    message('job-status', 'Loading jobs...');
    try {
      const result = await api('jobs?limit=50');
      if (seq !== jobSeq || !allowed()) return;
      el('job-list').replaceChildren();
      for (const job of result.jobs) {
        const row = item(job.id + ' · ' + job.handler + ' · ' + job.state + ' · attempts ' + job.attempts + '/' + job.max_attempts);
        row.append(button('Inspect job', () => jobDetail(job.id))); el('job-list').append(row);
      }
      message('job-status', result.jobs.length ? result.jobs.length + ' latest jobs shown.' : 'No jobs yet.');
    } catch (error) { if (seq === jobSeq) message('job-status', error.message); }
  }
  async function jobDetail(id) {
    const seq = ++jobDetailSeq;
    try {
      const [data, runs] = await Promise.all([api('jobs/' + id), api('jobs/' + id + '/runs')]);
      if (seq !== jobDetailSeq || !allowed()) return;
      el('job-detail').hidden = false;
      message('job-data', JSON.stringify(data, null, 2)); message('job-runs', JSON.stringify(runs.runs, null, 2));
    } catch (error) { if (seq === jobDetailSeq) message('job-status', error.message); }
  }
  async function schedules() {
    const seq = ++scheduleSeq;
    message('schedule-status', 'Loading schedules...');
    try {
      const result = await api('schedules?limit=50');
      if (seq !== scheduleSeq || !allowed()) return;
      el('schedule-list').replaceChildren();
      for (const schedule of result.schedules) {
        const row = item(schedule.name + ' · ' + (schedule.enabled ? 'enabled' : 'paused') + ' · every ' + schedule.interval_seconds + ' seconds · next ' + schedule.next_run_at + ' UTC');
        row.append(button('Inspect schedule', () => scheduleDetail(schedule))); el('schedule-list').append(row);
      }
      message('schedule-status', result.schedules.length ? result.schedules.length + ' schedules shown.' : 'No schedules yet.');
    } catch (error) { if (seq === scheduleSeq) message('schedule-status', error.message); }
  }
  async function scheduleDetail(schedule) {
    const seq = ++scheduleDetailSeq;
    selectedSchedule = schedule;
    el('schedule-detail').hidden = false;
    message('schedule-identity', schedule.name + ' · ' + schedule.id);
    el('schedule-enabled').checked = schedule.enabled;
    el('schedule-edit-interval').value = schedule.interval_seconds;
    el('save-schedule').disabled = false;
    message('schedule-runs', 'Loading runs...');
    try {
      const runs = await api('schedules/' + schedule.id + '/runs');
      if (seq === scheduleDetailSeq && allowed()) message('schedule-runs', JSON.stringify(runs.runs, null, 2));
    } catch (error) { if (seq === scheduleDetailSeq) message('schedule-status', error.message); }
  }
  for (const [id, action] of [['refresh-clients', clients], ['refresh-jobs', jobs], ['refresh-schedules', schedules]]) {
    el(id).addEventListener('click', action);
  }
  el('client-form').addEventListener('submit', async event => {
    event.preventDefault(); const save = el('approve-client');
    if (save.disabled || !allowed()) return;
    const name = el('client-name').value, callbacks = el('client-callbacks').value;
    const scopes = ['read', 'write', 'admin'].filter(s => el('client-' + s).checked).map(s => 'c0:' + s);
    if (!scopes.length) { message('client-status', 'Select at least one permission.'); return; }
    save.disabled = true;
    try {
      await api('oauth/clients', 'POST', {client_name: name, redirect_uris: callbacks.split('\n').map(s => s.trim()).filter(Boolean), allowed_scopes: scopes});
      // Keep all captured fields: identical approval is replay safe and this preserves newer drafts.
      await clients();
    } catch (error) { message('client-status', error.message); }
    finally { save.disabled = false; }
  });
  el('job-form').addEventListener('submit', async event => {
    event.preventDefault(); const save = el('enqueue-job');
    if (save.disabled || !allowed()) return;
    const selection = jobDetailSeq;
    save.disabled = true;
    try {
      const body = {handler: el('job-handler').value, payload: jsonObject(el('job-payload').value)};
      const fingerprint = JSON.stringify(body);
      if (!pendingJob || pendingJob.fingerprint !== fingerprint) pendingJob = {fingerprint, key: crypto.randomUUID()};
      const key = pendingJob.key;
      const job = await api('jobs', 'POST', {...body, idempotency_key: key});
      if (pendingJob && pendingJob.key === key) pendingJob = null;
      await jobs();
      if (selection === jobDetailSeq) await jobDetail(job.id);
    } catch (error) { message('job-status', inputError(error)); }
    finally { save.disabled = false; }
  });
  el('schedule-form').addEventListener('submit', async event => {
    event.preventDefault(); const save = el('create-schedule');
    if (save.disabled || !allowed()) return;
    const selection = scheduleDetailSeq;
    save.disabled = true;
    try {
      const body = {name: el('schedule-name').value, handler: el('schedule-handler').value,
        payload: jsonObject(el('schedule-payload').value), interval_seconds: Number(el('schedule-interval').value)};
      const schedule = await api('schedules', 'POST', body);
      await schedules();
      if (selection === scheduleDetailSeq) await scheduleDetail(schedule);
    } catch (error) { message('schedule-status', inputError(error)); }
    finally { save.disabled = false; }
  });
  el('schedule-edit').addEventListener('submit', async event => {
    event.preventDefault(); const save = el('save-schedule');
    if (save.disabled || !selectedSchedule || !allowed()) return;
    const seq = scheduleDetailSeq, id = selectedSchedule.id;
    const body = {enabled: el('schedule-enabled').checked, interval_seconds: Number(el('schedule-edit-interval').value)};
    save.disabled = true;
    try {
      const updated = await api('schedules/' + id, 'PUT', body);
      if (seq === scheduleDetailSeq) selectedSchedule = updated;
      await schedules();
    } catch (error) { if (seq === scheduleDetailSeq) message('schedule-status', error.message); }
    finally { if (seq === scheduleDetailSeq) save.disabled = false; }
  });
  (async () => {
    const captured=adminEpoch;
    try {
      const response = await fetch('./api/v1/me', {cache: 'no-store'});
      if (!response.ok) throw new Error('Sign in with an admitted application Admin account.');
      const current=await response.json();if(captured!==adminEpoch)return;profile=current;
      message('admin-account', 'Signed in as ' + profile.username + ' · ' + profile.role);
      if (!allowed()) { message('admin-account', 'Only application Admins can manage clients and tasks.'); return; }
      el('admin-workspace').hidden = false;
      await Promise.all([clients(), jobs(), schedules()]);
      const result = await api('jobs/handlers');
      if (!allowed()) return;
      for (const id of ['job-handler', 'schedule-handler']) {
        el(id).replaceChildren();
        for (const handler of result.handlers) {
          const option = document.createElement('option'); option.value = handler.name;
          option.textContent = handler.name + ' · ' + handler.timeout_seconds + ' second limit'; el(id).append(option);
        }
      }
    } catch (_) { if(captured!==adminEpoch)return;message('admin-account', 'Administration is unavailable. Sign in or try again later.'); el('admin-signin').hidden = false; }
  })();
})();
