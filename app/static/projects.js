// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const $ = id => document.getElementById(id), space = window.C0Space;
  if (!$('project-content') || !space) return;
  let sequence = 0;
  function clear() {
    ++sequence; $('project-content').hidden = true;
    $('project-title').textContent = 'Project unavailable.';
    for (const id of ['project-description','project-purpose','project-scope','project-config','project-topics-note','project-work-status','project-report-status','project-status','project-sources-status','project-monitoring-status']) $(id).textContent = '';
    for (const id of ['project-topics','project-work','project-reports','project-sources','project-monitoring']) $(id).replaceChildren();
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
      const [stored, topics, sources, work, runs, monitoring] = await Promise.all([read('project'), read('project/records?kind=topic_v1&limit=100'), read('project/records?kind=connector_sync_v1&limit=100'), read('project/records?kind=queue_v1&limit=100'), read('project/records?kind=run_v1&limit=100&descending=true'), read('project/records?kind=monitor_cycle_v1&limit=100&descending=true')]);
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
      for (const entry of sources.objects) {
        const source = entry.data, item = document.createElement('li');
        item.textContent = source.connector_id + ' · ' + source.status + ' · ' + source.verified_items + '/' + source.discovered_items + ' items verified' + (source.last_success_at ? ' · last success ' + source.last_success_at : ' · no successful synchronization') + (source.last_error ? ' · ' + source.last_error : '') + (source.retry_after ? ' · retry after ' + source.retry_after : '');
        $('project-sources').append(item);
      }
      $('project-sources-status').textContent = sources.objects.length === 100 ? 'Incomplete connector status. Continue through the project API.' : sources.objects.length ? 'Collector observations cover only the configured bounded source selection.' : 'No source synchronization receipt yet.';
      for (const entry of work.objects) {
        const queued = entry.data, item = document.createElement('li');
        item.textContent = queued.question + ' · ' + queued.status + ' · priority ' + queued.priority + ' · expansion ' + queued.expansion_priority + ' · attempts ' + queued.attempt_count + (queued.defer_reason ? ' · ' + queued.defer_reason : '');
        $('project-work').append(item);
      }
      for (const entry of runs.objects) {
        const run = entry.data, item = document.createElement('li');
        item.textContent = run.workflow_type + ' · ' + run.local_cycle_date + ' · ' + run.state + ' · phase ' + run.current_phase + (run.finished_at ? ' · finished ' + run.finished_at : '') + (run.error_code ? ' · ' + run.error_code : '');
        $('project-work').append(item);
      }
      $('project-work-status').textContent = work.objects.length === 100 || runs.objects.length === 100 ? 'Incomplete work inventory. Continue through the project API.' : work.objects.length || runs.objects.length ? 'Stored workflow observations. A reservation or active lease does not prove successful external execution.' : 'No queued research or workflow observation yet.';
      const labels = new Map(topics.objects.map(entry => [entry.data.topic_id, entry.data.label]));
      for (const entry of monitoring.objects) {
        const cycle = entry.data, item = document.createElement('li');
        item.textContent = (labels.get(cycle.topic_id) || cycle.topic_id) + ' · ' + cycle.local_date + ' · ' + cycle.status + ' · queries ' + cycle.queries_used + '/' + cycle.max_queries + ' · sources ' + cycle.sources_used + '/' + cycle.max_sources + (cycle.successful_watermark ? ' · covered through ' + cycle.successful_watermark : ' · successful watermark not advanced') + (cycle.summary ? ' · ' + cycle.summary : '');
        $('project-monitoring').append(item);
      }
      $('project-monitoring-status').textContent = monitoring.objects.length === 100 ? 'Incomplete monitoring history. Continue through the project API.' : monitoring.objects.length ? 'Recent stored coverage; monitoring uses no queued research slots.' : config.primary_topic_ids.length ? 'Primary-topic monitoring has no stored coverage yet.' : 'No primary topics configured.';
      $('project-report-status').textContent = 'Read saved project reports in Knowledge. Report persistence and external notification are separate observations.';
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
