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
  const complete = {...first.data.manifest, primary_topic_ids:['anchor'], state:{initialized:true,migration_status:'not_started'}};
  const saved = await write('', {manifest:complete, expected_revision:first.revision,
    authorization_ref:'synthetic-browser:configure', idempotency_key:'browser-project-config'}, 'PUT');
  if (saved.revision !== 2 || saved.data.version !== 2) throw Error('Synthetic project revision failed');
  return {initialized:true, replay:true, revision:saved.revision};
}
