// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const $ = id => document.getElementById(id), space = window.C0Space;
  if (!$('project-content') || !space) return;
  let sequence = 0;
  function clear() {
    ++sequence; $('project-content').hidden = true;
    $('project-title').textContent = 'Project unavailable.';
    for (const id of ['project-description','project-purpose','project-scope','project-config','project-topics-note','project-work-status','project-report-status','project-status']) $(id).textContent = '';
    for (const id of ['project-topics','project-work','project-reports']) $(id).replaceChildren();
  }
  space.onClear(clear);
  async function read(path) {
    const response = await space.request(path);
    if (!response.ok) throw new Error('unavailable');
    return response.json();
  }
  async function refresh() {
    clear(); const current = sequence, generation = space.generation();
    if (!space.identifier) { $('project-status').textContent = 'Choose a protected space configured as a research project.'; return; }
    $('project-status').textContent = 'Reading project…';
    try {
      const [stored, topics] = await Promise.all([read('project'), read('project/records?kind=topic_v1&limit=100')]);
      if (current !== sequence || !space.current(generation)) return;
      const config = stored.data.manifest;
      if (config.space_id !== space.identifier || config.project_id !== space.identifier) throw new Error('binding');
      $('project-title').textContent = config.name;
      $('project-description').textContent = config.description;
      $('project-purpose').textContent = config.purpose;
      $('project-scope').textContent = config.scope;
      $('project-config').textContent = 'Configuration ' + stored.data.version + ' · ' + config.language + ' · ' + config.timezone + ' · external schedule ' + (config.schedule.enabled ? 'requested; execution requires separate verification' : 'disabled');
      for (const entry of topics.objects) {
        const topic = entry.data, item = document.createElement('li');
        item.textContent = topic.label + ' · ' + topic.classification + ' · ' + topic.lifecycle + (config.primary_topic_ids.includes(topic.topic_id) ? ' · primary monitoring' : '');
        $('project-topics').append(item);
      }
      $('project-topics-note').textContent = topics.objects.length === 100 ? 'Navigation is incomplete. More topics may exist; use the project API to continue.' : (topics.objects.length ? '' : 'No tracked topics yet.');
      $('project-content').hidden = false;
      $('project-status').textContent = 'Saved project configuration. Workflow completion and external scheduling require separate receipts.';
    } catch {
      if (current !== sequence || !space.current(generation)) return;
      clear(); $('project-status').textContent = 'Project is unavailable or not initialized in this space. Refresh access or ask an authorized project maintainer.';
    }
  }
  $('project-refresh').addEventListener('click', refresh);
  refresh();
})();
