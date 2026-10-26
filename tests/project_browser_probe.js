// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
async () => {
  const space = new URL(location.href).searchParams.get('space_id');
  if (!/^[0-9a-f-]{36}$/.test(space || '')) throw Error('Synthetic project selector missing');
  const me = await fetch('./api/v1/me?space_id=' + space, {cache:'no-store'});
  if (!me.ok) throw Error('Synthetic project identity unavailable');
  const profile = await me.json();
  const headers = {'Content-Type':'application/json', 'X-C0-CSRF':profile.csrf_token};
  async function write(path, data, method='POST') {
    const response = await fetch('./api/v1/project' + path + '?space_id=' + space,
      {method, headers, body:JSON.stringify(data), cache:'no-store'});
    if (!response.ok) throw Error('Synthetic project mutation failed');
    return response.json();
  }
  const manifest = {schema_version:1, project_id:space, space_id:space,
    name:'<img src=x> Synthetic research', purpose:'Test reusable research projects', scope:'Fabricated browser records only',
    timezone:'Europe/Rome', language:'en'};
  const setup = {manifest, authorization_ref:'synthetic-browser:setup', idempotency_key:'browser-project-setup'};
  const first = await write('/initialize', setup);
  const replay = await write('/initialize', setup);
  if (replay.id !== first.id || replay.revision !== first.revision) throw Error('Synthetic project replay failed');
  await write('/topics', {topic:{topic_id:'anchor', label:'<script> synthetic topic', classification:'user',
    authorization_ref:'synthetic-browser:track'}, expected_revision:0, idempotency_key:'browser-project-anchor'});
  const connector = await write('/connectors', {definition:{id:'browser-source',adapter:'local_files',root:'synthetic-inputs',
    enabled:true,include:[],max_items:100,max_requests:40,max_bytes:8388608,max_pages:5,max_depth:2,timeout:15},
    authorization_ref:'synthetic-browser:source-approval',idempotency_key:'browser-source-config'},'PUT');
  const complete = {...first.data.manifest, primary_topic_ids:['anchor'],connector_ids:['browser-source'], state:{initialized:true,migration_status:'not_started'}};
  const saved = await write('', {manifest:complete, expected_revision:first.revision,
    authorization_ref:'synthetic-browser:configure', idempotency_key:'browser-project-config'}, 'PUT');
  if (saved.revision !== 2 || saved.data.version !== 2) throw Error('Synthetic project revision failed');
  await write('/connector-status',{data:{connector_id:'browser-source',definition_hash:connector.data.definition_hash,
    last_attempt_at:new Date().toISOString(),last_success_at:'',status:'partial',last_error:'coverage_incomplete',retry_after:'',
    remote_cursor:'{}',progress_cursor:'{}',attempt_count:0,verified_items:0,discovered_items:1},
    idempotency_key:'browser-source-coverage'},'PUT');
  const claimed=await write('/runs/claim',{workflow_type:'daily',lease_owner:'synthetic-browser-worker',config_version:2,idempotency_key:'browser-run'});
  const run=claimed.records[0].data,lease={run_id:run.run_id,lease_owner:run.lease_owner,fencing_generation:run.fencing_generation};
  const cycle=(await write('/monitoring/begin',{lease,topic_id:'anchor',idempotency_key:'browser-monitor-begin'})).records[0].data;
  const call=(await write('/monitoring/reserve',{lease,cycle_id:cycle.cycle_id,kind:'query',request_id:'browser-query',
    request_text:'Synthetic bounded primary-topic check',idempotency_key:'browser-monitor-reserve'})).records[0].data;
  await write('/monitoring/observe',{lease,call_id:call.call_id,state:'started',idempotency_key:'browser-monitor-start'});
  await write('/monitoring/observe',{lease,call_id:call.call_id,state:'succeeded',external_reference:'synthetic-browser:fake-search',
    summary:'Synthetic response with no selected sources',idempotency_key:'browser-monitor-observe'});
  const coverage=await write('/monitoring/finish',{lease,cycle_id:cycle.cycle_id,status:'no_material_update',
    summary:'Synthetic bounded coverage; no real provider executed',idempotency_key:'browser-monitor-finish'});
  const success=coverage.records.find(row=>row.type_name==='c0_project_monitor_success_v1');
  await write('/runs/checkpoint',{lease,phase:'monitoring',status:'SAVED',references:[success.id],
    summary:'Synthetic coverage read back',idempotency_key:'browser-monitor-phase'});
  await write('/queue',{candidate:{stable_id:'browser-investigation',topic_id:'anchor',question:'<script> synthetic queued investigation',
    kind:'investigation',origin:'user',origin_reference:'synthetic-browser:user',priority:20,priority_reason:'Approved scope',
    urgency_reason:'',parent_ids:[],related_pages:[],not_before:'',due_at:'',question_conditions:'',entity_version:'',time_window:'',
    assessment_ref:'synthetic-browser:assessment',direct_contribution:'Tests the approved anchor',anchor_ids:['anchor'],
    novelty_key:'browser-event',novelty_refs:['synthetic-browser:evidence'],root_reason:'user_request',authorization_ref:'synthetic-browser:user',
    excluded:false,semantic_matches:[],independent_parents:[]},idempotency_key:'browser-admission'});
  const reservation=await write('/attempts/reserve',{lease,idempotency_key:'browser-attempt'});
  if (reservation.status!=='SAVED') throw Error('Synthetic project reservation failed');
  await write('/runs/checkpoint',{lease,phase:'research',status:'PARTIAL',summary:'Synthetic interrupted investigation',idempotency_key:'browser-partial'});
  const stale=await fetch('./api/v1/project/attempts/reserve?space_id='+space,{method:'POST',headers,
    body:JSON.stringify({lease,idempotency_key:'browser-stale'}),cache:'no-store'});
  if(stale.status!==409) throw Error('Inactive project lease was accepted');
  return {initialized:true, replay:true, revision:saved.revision, workflows:true,monitoring:true};
}
