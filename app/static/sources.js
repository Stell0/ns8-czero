// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const $ = id => document.getElementById(id);
let profile = null, currentSource = null, currentDocument = null;
let sourceOffset = 0, chunkOffset = 0, sourcesSequence = 0, selectionSequence = 0, documentSequence = 0, searchSequence = 0, pollTimer = null;
let citationSequence = 0, uploadDraftSequence = 0;
const canWrite = () => profile && ['editor', 'admin'].includes(profile.role);
const errors = {unsupported_docx:"Unsupported DOCX text structures. Convert this file; its original is retained.",invalid_text:'Invalid UTF-8 text.', no_text:'No extractable text; the original is retained.', unsupported_scan:'Scanned PDFs need OCR outside C0.', encrypted_pdf:'Encrypted PDFs are unsupported.', archive_limit:'DOCX archive expansion exceeds the safe limit.', too_large:'The file or extracted text exceeds the safe limit.', parser_timeout:'Extraction reached its time limit.', invalid_file:'The stored original is missing or changed.', invalid_docx:'Unsupported or malformed DOCX.', invalid_pdf:'Malformed PDF.'};
async function api(path, options = {}) {
  const response = await (typeof window!=='undefined' && window.C0Space ? window.C0Space.request(path, options) : fetch('./api/v1/' + path, {cache:'no-store', ...options}));
  if (!response.ok) {
    if (response.status === 409) throw new Error('Conflict. Refresh the source and retry; your upload is preserved.');
    if ([401,403].includes(response.status)) throw new Error('Sign-in or permitted access is required.');
    if (response.status === 413) throw new Error('Upload exceeds the safe limit.');
    throw new Error('The request failed. Check the format, input and service status.');
  }
  return response.json();
}
function button(label, action) {
  const node = document.createElement('button'); node.type = 'button'; node.textContent = label;
  node.addEventListener('click', () => action().catch(error => {$('source-status').textContent = error.message;})); return node;
}
function clearDocument() {
  ++documentSequence; ++citationSequence; currentDocument = null; chunkOffset = 0;
  $('document-text').textContent = ''; $('source-citation').textContent = ''; $('source-chunks').replaceChildren();
  $('document-status').textContent = 'Choose a ready version to inspect its evidence.';
  $('chunks-previous').disabled = true; $('chunks-next').disabled = true;
}
async function loadSources() {
  const sequence = ++sourcesSequence, offset = sourceOffset;
  const result = await api(`sources?limit=50&offset=${offset}`);
  if (sequence !== sourcesSequence || offset !== sourceOffset) return;
  $('source-list').replaceChildren(); const selected = $('upload-source').value;
  $('upload-source').replaceChildren(); const option = document.createElement('option'); option.value = ''; option.textContent = 'New source'; $('upload-source').append(option);
  for (const source of result.sources) {
    const row = document.createElement('li'); row.append(button(source.title, () => selectSource(source.id))); $('source-list').append(row);
    const option = document.createElement('option'); option.value = source.id; option.textContent = source.title; $('upload-source').append(option);
  }
  if (result.sources.some(source => source.id === selected)) $('upload-source').value = selected;
  $('sources-previous').disabled = offset === 0; $('sources-next').disabled = result.sources.length < 50;
  $('sources-status').textContent = result.sources.length ? `Showing ${offset+1}–${offset+result.sources.length}.` : 'No sources on this page.';
}
async function selectSource(id) {
  clearTimeout(pollTimer); const sequence = ++selectionSequence; clearDocument(); currentSource = null; $('source-detail').hidden = true;
  const [source, history] = await Promise.all([api('sources/' + id), api(`sources/${id}/versions?limit=100`)]);
  if (sequence !== selectionSequence) return false;
  currentSource = source; $('source-detail').hidden = false;
  $('source-heading').textContent = source.title; $('source-identity').textContent = `${source.id} · revision ${source.revision}${source.deleted ? ' · archived' : ''}`;
  $('source-metadata').textContent = JSON.stringify(source.metadata, null, 2);
  $('archive-source').hidden = !canWrite() || source.deleted; $('source-versions').replaceChildren();
  for (const version of history.versions) {
    const row = document.createElement('li'); const retained = version.original_present ? (version.retain_original ? 'original retained' : 'original pending or quarantined') : 'original removed';
    row.textContent = `Version ${version.number} · ${version.state} · ${retained} `;
    if (version.state === 'ready') row.append(button('View version ' + version.number, () => loadDocument(version.id)));
    if (version.error_code) {const reason = document.createElement('span'); reason.textContent = errors[version.error_code] || 'Extraction failed; inspect the retained original.'; row.append(reason);}
    if (canWrite() && (version.state === 'failed' || (version.state === 'queued' && !['queued','running'].includes(version.job_state)))) {
      row.append(button('Retry version ' + version.number, async () => {
        await api(`source-versions/${version.id}/retry`, {method:'POST',headers:{'Content-Type':'application/json','X-C0-CSRF':profile.csrf_token},body:JSON.stringify({expected_generation:version.generation})});
        if (currentSource?.id === id) await selectSource(id);
      }));
    }
    if (version.original_present && (version.retain_original || version.state === 'failed')) {
      const link = document.createElement('a'); link.textContent = 'Download original'; link.href = typeof window!=='undefined' && window.C0Space?window.C0Space.apiURL('source-versions/'+version.id+'/original'):'./api/v1/source-versions/' + version.id + '/original'; row.append(link);
    }
    $('source-versions').append(row);
  }
  $('source-status').textContent = history.versions.some(v => v.state === 'queued') ? 'Extraction queued. This history refreshes while jobs are pending.' : 'Version history loaded. Originals are removed only after successful persistence.';
  if (history.versions.some(v => v.state === 'queued' && ['queued','running'].includes(v.job_state))) pollTimer = setTimeout(() => {if (currentSource?.id === id) selectSource(id).catch(error => {$('source-status').textContent = error.message;});}, 4000);
  return true;
}
async function loadDocument(versionId) {
  clearTimeout(pollTimer); const selection = selectionSequence, sequence = ++documentSequence;
  const result = await api('source-versions/' + versionId + '/document');
  if (selection !== selectionSequence || sequence !== documentSequence) return;
  currentDocument = result; chunkOffset = 0; $('document-text').textContent = result.body;
  $('document-status').textContent = `${result.body.length} characters · text SHA-256 ${result.text_hash}`; $('source-citation').textContent = ''; await loadChunks();
}
async function loadChunks() {
  if (!currentDocument) return;
  const id = currentDocument.id, sequence = documentSequence, offset = chunkOffset;
  ++citationSequence; $('source-citation').textContent = '';
  const result = await api(`documents/${id}/chunks?limit=50&offset=${offset}`);
  if (sequence !== documentSequence || currentDocument?.id !== id || offset !== chunkOffset) return;
  $('source-chunks').replaceChildren();
  for (const chunk of result.chunks) {
    const row = document.createElement('li'); row.append(button(`Chunk ${chunk.ordinal+1} · offsets ${chunk.start_offset}–${chunk.end_offset}`, async () => {
      const request = ++citationSequence;
      const current = () => request === citationSequence && sequence === documentSequence && currentDocument?.id === id && offset === chunkOffset;
      try {const citation = await api('chunks/' + chunk.id + '/citation');if (current()) $('source-citation').textContent = JSON.stringify(citation, null, 2);}
      catch (_) {if (current()) $('source-citation').textContent = 'Cannot load this citation. Check access and try again.';}
    })); $('source-chunks').append(row);
  }
  $('chunks-previous').disabled = offset === 0; $('chunks-next').disabled = result.chunks.length < 50;
}
async function searchSources() {
  const sequence = ++searchSequence, query = $('source-query').value;
  const current = () => sequence === searchSequence && query === $('source-query').value;
  $('search-status').textContent = 'Searching source evidence...';
  try {
    const result = await api('sources/search?' + new URLSearchParams({query, limit:20}));
    if (!current()) return;
    $('source-results').replaceChildren();
    for (const citation of result.citations) {
      const row = document.createElement('li'); row.append(button(`${citation.title} · version ${citation.version}`, async () => {
        if (await selectSource(citation.source_id)) await loadDocument(citation.version_id);
      })); const excerpt = document.createElement('p'); excerpt.textContent = citation.body.slice(0,300); row.append(excerpt); $('source-results').append(row);
    }
    $('search-status').textContent = `${result.citations.length} sourced text matches (up to 20).`;
  } catch (_) {if (current()) {$('source-results').replaceChildren();$('search-status').textContent='Source search is unavailable. Check access and try again.';}}
}
$('source-query').addEventListener('input', () => {++searchSequence;$('source-results').replaceChildren();$('search-status').textContent='Query changed. Search to refresh evidence.';});
for (const id of ['upload-title','upload-metadata']) $(id).addEventListener('input', () => {++uploadDraftSequence;});
$('upload-file').addEventListener('change', () => {
  const file = $('upload-file').files[0]; if (!file) return;
  const extension = file.name.split('.').pop().toLowerCase(), formats = {txt:'text/plain',md:'text/markdown',pdf:'application/pdf',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};
  if (formats[extension]) $('upload-media').value = formats[extension]; if (!$('upload-title').value) $('upload-title').value = file.name;
});
$('upload-source').addEventListener('change', async () => {
  const id = $('upload-source').value, draft = ++uploadDraftSequence; if (!id) return;
  try {const source = await api('sources/' + id); if ($('upload-source').value === id && draft === uploadDraftSequence) {$('upload-title').value = source.title; $('upload-metadata').value = JSON.stringify(source.metadata);}}
  catch (_) {if ($('upload-source').value === id && draft === uploadDraftSequence) $('upload-status').textContent = 'Cannot load this source metadata.';}
});
$('upload-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!canWrite() || $('upload-submit').disabled) return; $('upload-submit').disabled = true;
  const selection = selectionSequence;
  try {
    const file = $('upload-file').files[0]; if (!file || file.size > 10*1024*1024) throw new Error('Choose a file up to 10 MiB.');
    const metadata = JSON.parse($('upload-metadata').value); if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object') throw new Error('Metadata must be a JSON object.');
    const id = $('upload-source').value, form = new FormData(); form.append('file', file); form.append('title', $('upload-title').value);
    form.append('media_type', $('upload-media').value); form.append('metadata', JSON.stringify(metadata)); form.append('retain_original', $('upload-retain').checked ? 'true' : 'false');
    if (id) {const source = await api('sources/' + id); form.append('source_id', source.id); form.append('expected_revision', String(source.revision));}
    const version = await api('sources/upload', {method:'POST',headers:{'X-C0-CSRF':profile.csrf_token},body:form});
    $('upload-status').textContent = 'Upload accepted. Extraction is queued or this content already exists.';
    sourceOffset = 0; await loadSources(); if (selection === selectionSequence) await selectSource(version.source_id);
  } catch (error) {$('upload-status').textContent = error instanceof SyntaxError ? 'Metadata must be valid JSON.' : error.message;}
  finally {$('upload-submit').disabled = false;}
});
for (const [id, action] of [
  ['refresh-sources', loadSources], ['refresh-source', async () => {if (currentSource) await selectSource(currentSource.id);}],
  ['sources-previous', async () => {sourceOffset=Math.max(0,sourceOffset-50); await loadSources();}], ['sources-next', async () => {sourceOffset+=50; await loadSources();}],
  ['chunks-previous', async () => {chunkOffset=Math.max(0,chunkOffset-50); await loadChunks();}], ['chunks-next', async () => {chunkOffset+=50; await loadChunks();}],
  ['archive-source', async () => {const source=currentSource; if (!source || !canWrite()) return; await api(`sources/${source.id}?expected_revision=${source.revision}`, {method:'DELETE',headers:{'X-C0-CSRF':profile.csrf_token}}); await loadSources(); if(currentSource?.id===source.id) await selectSource(source.id);}]
]) $(id).addEventListener('click', () => action().catch(error => {$('source-status').textContent = error.message;}));
$('source-search-form').addEventListener('submit', event => {event.preventDefault(); searchSources().catch(error => {$('search-status').textContent = error.message;});});
async function initializeSources() {
  if(typeof window!=='undefined' && window.C0 && !window.C0.toolsMode)return;
  try {
    const status = await (await fetch('./api/v1/auth/status', {cache:'no-store'})).json();
    if (!status.configured) {$('sources-account').textContent = 'Ask the NethServer administrator to configure sign-in.'; return;}
    $('sources-signin').hidden = false; profile = await api('me'); $('sources-account').textContent = `Signed in as ${profile.username} · ${profile.role}`;
    $('sources-signin').hidden = true; $('sources-workspace').hidden = false; $('source-upload').hidden = !canWrite(); await loadSources();
  } catch (error) {$('sources-account').textContent = error.message;}
}
initializeSources();

if(typeof window!=='undefined' && window.C0Space)window.C0Space.onClear(()=>{
  ++sourcesSequence;++selectionSequence;++documentSequence;++searchSequence;++citationSequence;++uploadDraftSequence;
  clearTimeout(pollTimer);profile=null;currentSource=null;currentDocument=null;
  $('sources-workspace').hidden=true;$('source-detail').hidden=true;
  for(const id of ['source-list','source-versions','source-chunks','source-results','upload-source']){const element=$(id);if(element)element.replaceChildren();}
  for(const id of ['source-heading','sources-status','upload-status','document-text','source-citation','source-identity','source-metadata','source-status','document-status','search-status']){const element=$(id);if(element)element.textContent='';}
  for(const id of ['source-query','upload-title','upload-metadata','upload-file']){const element=$(id);if(element)element.value='';}
  $('sources-account').textContent='Space access changed. Choose a permitted space.';
});
