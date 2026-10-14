// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const $ = id => document.getElementById(id);
let profile = null, currentPage = null, currentEntity = null, offset = 0;
let listSequence = 0, pageSequence = 0, historySequence = 0, entitySequence = 0, entityListSequence = 0, graphSequence = 0, revisionSequence = 0;
const canWrite = () => profile && ['editor','admin'].includes(profile.role);
const key = () => crypto.randomUUID();
async function api(path, options = {}) {
  const response = await fetch('./api/v1/' + path, {cache:'no-store', ...options});
  if (!response.ok) {
    if (response.status === 409) throw new Error('Conflict. Your draft is preserved; load the saved version before retrying.');
    if ([401,403].includes(response.status)) throw new Error('Sign-in or permitted access is required.');
    if (response.status === 413) throw new Error('Content exceeds the safe request limit.');
    throw new Error('The request failed. Check names, JSON, evidence IDs and service status.');
  }
  return response.json();
}
// Retain one uncertain attempt so an unchanged retry replays safely.
let pendingWrite = null;
async function write(path, data, method='POST') {
  const fingerprint=JSON.stringify([method,path,data]);
  if(pendingWrite?.fingerprint!==fingerprint)pendingWrite={fingerprint,key:key()};
  const attempt=pendingWrite;
  const result=await api(path,{method,headers:{'Content-Type':'application/json','X-C0-CSRF':profile.csrf_token},body:JSON.stringify({...data,idempotency_key:attempt.key})});
  if(pendingWrite===attempt)pendingWrite=null;
  return result;
}
function objectInput(id) {const value=JSON.parse($(id).value);if(!value || typeof value!=='object' || Array.isArray(value))throw new Error('Enter a JSON object.');return value;}
function button(label, action, status='page-status') {const node=document.createElement('button');node.type='button';node.textContent=label;node.addEventListener('click',()=>action().catch(error=>{$(status).textContent=error.message;}));return node;}
function displayPage(page) {
  ++pageSequence; ++historySequence; ++revisionSequence; currentPage=page;
  $('wiki-detail').hidden=false; $('wiki-heading').textContent=page ? page.title : 'New page';
  $('wiki-identity').textContent=page ? `${page.id} · revision ${page.revision}${page.deleted?' · archived':''}` : 'New authored page';
  $('wiki-slug').value=page?.slug || ''; $('wiki-title').value=page?.title || ''; $('wiki-body').value=page?.content.body || '';
  $('wiki-metadata').value=JSON.stringify(page?.content.metadata || {},null,2);
  for(const id of ['wiki-title','wiki-body','wiki-metadata'])$(id).readOnly=!canWrite() || !!page?.deleted;
  $('wiki-slug').readOnly=!!page || !canWrite(); $('save-page').hidden=!canWrite() || !!page?.deleted;
  $('archive-page').hidden=!page || !canWrite() || page.deleted; $('reload-page').hidden=!page;
  $('wiki-history').replaceChildren(); $('wiki-revision').textContent=''; $('page-status').textContent='';
  for(const [id,format] of [['export-markdown','markdown'],['export-json','json']]) {$(id).hidden=!page;if(page)$(id).href=`./api/v1/wiki/pages/${page.id}/export?format=${format}`;}
}
async function loadPages() {
  const sequence=++listSequence,start=offset,result=await api(`wiki/pages?limit=50&offset=${start}`);
  if(sequence!==listSequence || start!==offset)return;
  $('wiki-pages').replaceChildren();for(const page of result.pages){const row=document.createElement('li');row.append(button(page.title,()=>selectPage(page.id)));$('wiki-pages').append(row);}
  $('pages-previous').disabled=start===0;$('pages-next').disabled=result.pages.length<50;$('wiki-status').textContent=result.pages.length?`Showing ${start+1}–${start+result.pages.length}.`:'No pages on this page.';
}
async function selectPage(id) {
  const sequence=++pageSequence;const page=await api('wiki/pages/'+id);if(sequence!==pageSequence)return;
  displayPage(page);await loadHistory();
}
async function loadHistory() {
  if(!currentPage)return;const id=currentPage.id,selection=pageSequence,sequence=++historySequence,result=await api('wiki/pages/'+id+'/revisions?limit=100');
  if(selection!==pageSequence || sequence!==historySequence || currentPage?.id!==id)return;
  $('wiki-history').replaceChildren();for(const revision of result.revisions){const row=document.createElement('li');row.append(button('View revision '+revision.number,async()=>{const preview=++revisionSequence,page=await api(`wiki/pages/${id}?revision=${revision.number}`);if(preview===revisionSequence && selection===pageSequence && currentPage?.id===id)$('wiki-revision').textContent=JSON.stringify(page.content,null,2);}));$('wiki-history').append(row);}
}
$('wiki-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!canWrite())return;$('save-page').disabled=true;const page=currentPage,selection=pageSequence;
  try{const data={title:$('wiki-title').value,body:$('wiki-body').value,metadata:objectInput('wiki-metadata')};
    const saved=page?await write('wiki/pages/'+page.id,{...data,expected_revision:page.revision},'PUT'):await write('wiki/pages',{...data,slug:$('wiki-slug').value});
    if(selection===pageSequence){displayPage(saved);$('page-status').textContent='Page saved.';await loadHistory();}await loadPages();
  }catch(error){if(selection===pageSequence)$('page-status').textContent=error instanceof SyntaxError?'Metadata must be valid JSON.':error.message;}
  finally{$('save-page').disabled=false;}
});
$('new-page').addEventListener('click',()=>displayPage(null));
for(const [id,action] of [['refresh-pages',loadPages],['pages-previous',async()=>{offset=Math.max(0,offset-50);await loadPages();}],['pages-next',async()=>{offset+=50;await loadPages();}],['reload-page',async()=>{if(currentPage)await selectPage(currentPage.id);}],['archive-page',async()=>{const page=currentPage,selection=pageSequence;if(!page || !canWrite())return;await write('wiki/pages/'+page.id+'/archive',{expected_revision:page.revision});if(selection===pageSequence)await selectPage(page.id);await loadPages();}]])$(id).addEventListener('click',()=>action().catch(error=>{$('page-status').textContent=error.message;}));
async function loadEntities() {
  const sequence=++entityListSequence,result=await api('entities?limit=100');if(sequence!==entityListSequence)return;
  const selected=$('knowledge-entity').value;$('knowledge-entity').replaceChildren();const option=document.createElement('option');option.value='';option.textContent='Choose an entity';$('knowledge-entity').append(option);
  for(const entity of result.entities){const node=document.createElement('option');node.value=entity.id;node.textContent=entity.label;$('knowledge-entity').append(node);}if(result.entities.some(e=>e.id===selected))$('knowledge-entity').value=selected;
}
async function selectEntity(id) {
  const sequence=++entitySequence;++graphSequence;currentEntity=null;$('entity-data').textContent='';$('claim-citations').textContent='';$('knowledge-graph').textContent='';$('knowledge-claims').replaceChildren();
  if(!id)return;const [entity,result]=await Promise.all([api('entities/'+id),api('claims?'+new URLSearchParams({entity_id:id,limit:100}))]);if(sequence!==entitySequence)return;
  currentEntity=entity;$('entity-identity').textContent=`${entity.id} · revision ${entity.revision}`;$('entity-data').textContent=JSON.stringify(entity,null,2);
  for(const claim of result.claims){const row=document.createElement('li');row.textContent=`${claim.predicate}: ${JSON.stringify(claim.value)} `;
    row.append(button('Evidence for claim '+claim.id,async()=>{const data=await api('claims/'+claim.id);if(sequence===entitySequence)$('claim-citations').textContent=JSON.stringify(data.evidence,null,2);},'claim-status'));
    if(canWrite())row.append(button('Retract claim '+claim.id,async()=>{await write('claims/'+claim.id+'/retract',{expected_revision:claim.revision});if(sequence===entitySequence)await selectEntity(id);},'claim-status'));$('knowledge-claims').append(row);
  }
  $('claim-status').textContent=result.claims.length+' sourced assertions.';
}
$('knowledge-entity').addEventListener('change',()=>selectEntity($('knowledge-entity').value).catch(error=>{$('entity-status').textContent=error.message;}));
$('refresh-entities').addEventListener('click',()=>loadEntities().catch(error=>{$('entity-status').textContent=error.message;}));
$('entity-form').addEventListener('submit',async event=>{event.preventDefault();if(!canWrite())return;try{const entity=await write('entities',{kind:$('entity-kind').value,label:$('entity-label').value,aliases:$('entity-aliases').value.split(',').map(v=>v.trim()).filter(Boolean)});await loadEntities();$('knowledge-entity').value=entity.id;await selectEntity(entity.id);$('entity-status').textContent='Entity created.';}catch(error){$('entity-status').textContent=error.message;}});
$('claim-form').addEventListener('submit',async event=>{event.preventDefault();if(!currentEntity || !canWrite())return;const id=currentEntity.id,selection=entitySequence;try{const page=$('claim-page').value.trim();await write('claims',{entity_id:id,predicate:$('claim-predicate').value,value:objectInput('claim-value'),evidence_chunk_ids:$('claim-evidence').value.split(',').map(v=>v.trim()).filter(Boolean),page_id:page || null});if(selection===entitySequence){await selectEntity(id);$('claim-status').textContent='Sourced claim added.';}}catch(error){if(selection===entitySequence)$('claim-status').textContent=error instanceof SyntaxError?'Assertion value must be valid JSON.':error.message;}});
async function loadGraph() {
  if(!currentEntity)return;const id=currentEntity.id,selection=entitySequence,sequence=++graphSequence,depth=$('graph-depth').value;
  const result=await api(`knowledge/graph/${id}?depth=${depth}&limit=100`);if(selection!==entitySequence || sequence!==graphSequence || currentEntity?.id!==id)return;
  $('knowledge-graph').textContent=JSON.stringify(result,null,2);$('graph-status').textContent=`${result.nodes.length} entities · ${result.relations.length} relationships${result.truncated?' · truncated by safe limits':''}`;
}
$('graph-form').addEventListener('submit',event=>{event.preventDefault();loadGraph().catch(error=>{$('graph-status').textContent=error.message;});});
$('knowledge-relation-form').addEventListener('submit',async event=>{event.preventDefault();if(!currentEntity || !canWrite())return;const id=currentEntity.id;try{await write('knowledge/relations',{source_id:id,target_id:$('knowledge-relation-target').value,kind:$('knowledge-relation-kind').value});if(currentEntity?.id===id)await loadGraph();$('graph-status').textContent='Relationship added.';}catch(error){$('graph-status').textContent=error.message;}});
$('knowledge-reference-form').addEventListener('submit',async event=>{event.preventDefault();if(!currentEntity || !canWrite())return;const id=currentEntity.id;try{await write('entities/'+id+'/references',{target_kind:$('knowledge-reference-kind').value,target_id:$('knowledge-reference-id').value});if(currentEntity?.id===id)await loadGraph();$('graph-status').textContent='Reference linked.';}catch(error){$('graph-status').textContent=error.message;}});
async function initializeWiki() {
  try{const status=await(await fetch('./api/v1/auth/status',{cache:'no-store'})).json();if(!status.configured){$('wiki-account').textContent='Ask the NethServer administrator to configure sign-in.';return;}$('wiki-signin').hidden=false;profile=await api('me');$('wiki-signin').hidden=true;$('wiki-account').textContent=`Signed in as ${profile.username} · ${profile.role}`;$('wiki-workspace').hidden=false;
    for(const id of ['new-page','entity-create','claim-form','knowledge-relation-form','knowledge-reference-form'])$(id).hidden=!canWrite();await Promise.all([loadPages(),loadEntities()]);
  }catch(error){$('wiki-account').textContent=error.message;}
}
initializeWiki();
