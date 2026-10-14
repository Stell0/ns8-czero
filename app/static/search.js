// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const $ = id => document.getElementById(id);
let searchSequence = 0;
function options() {
  return {query:$('knowledge-query').value,mode:$('knowledge-mode').value,
    kind:$('knowledge-kind').value,rerank:$('knowledge-rerank').value,graph_depth:$('knowledge-depth').value};
}
async function read(path) {
  const response = await fetch('./api/v1/' + path, {cache:'no-store'});
  if (!response.ok) throw new Error([401,403].includes(response.status) ? 'Sign-in or permitted access is required.' :
    response.status===422 ? 'The selected options exceed instance policy or are invalid.' : 'Search is unavailable. Try again.');
  return response.json();
}
function text(tag,value) {const node=document.createElement(tag);node.textContent=value;return node;}
async function searchKnowledge() {
  const sequence=++searchSequence, captured=options();
  $('knowledge-search-status').textContent='Searching...';
  const query=new URLSearchParams(captured);if(!captured.rerank)query.delete('rerank');
  try {
    const result=await read('knowledge/search?'+query);
    if(sequence!==searchSequence || JSON.stringify(captured)!==JSON.stringify(options()))return;
    $('knowledge-results').replaceChildren();
    for(const hit of result.hits) {
      const row=document.createElement('article');
      row.append(text('h2',hit.title),text('pre',hit.excerpt));
      row.append(text('p',`${hit.kind} · revision ${hit.revision} · offsets ${hit.start_offset}–${hit.end_offset}`));
      row.append(text('pre',JSON.stringify(hit.citation || hit.wiki,null,2)));
      if(hit.relevance_score!==null && hit.relevance_score!==undefined)row.append(text('p','Model relevance: '+hit.relevance_score));
      $('knowledge-results').append(row);
    }
    const fallback=result.fallback_reasons.length ? ' Fallback: '+result.fallback_reasons.join(', ')+'.' : '';
    $('knowledge-search-status').textContent=`${result.hits.length} results · ${result.retrieval_method} · ${result.candidate_count} candidates · ${result.scored_count} scored.${fallback}`;
    $('search-graphs').textContent=result.graphs.length ? JSON.stringify(result.graphs,null,2) : 'No supplemental graph.';
  } catch(error) {
    if(sequence!==searchSequence || JSON.stringify(captured)!==JSON.stringify(options()))return;
    $('knowledge-results').replaceChildren();$('search-graphs').textContent='';
    $('knowledge-search-status').textContent=error.message;
  }
}
$('knowledge-search-form').addEventListener('submit',event=>{event.preventDefault();searchKnowledge();});
for(const id of ['knowledge-query','knowledge-mode','knowledge-kind','knowledge-rerank','knowledge-depth']) {
  $(id).addEventListener('input',()=>{++searchSequence;$('knowledge-results').replaceChildren();$('search-graphs').textContent='';$('knowledge-search-status').textContent='Options changed. Search to refresh results.';});
}
async function initialize() {
  try {
    const profile=await read('me');$('search-account').textContent=profile.username+' · '+profile.role;
    $('search-workspace').hidden=false;
    try {const index=await read('knowledge/index/status');$('knowledge-index-status').textContent=index.configured ?
      `${index.indexed} derivative chunks indexed for the configured profile. Indexing may be pending.` : 'Embeddings are disabled; text search is available.';
    } catch { $('knowledge-index-status').textContent='Optional index status is unavailable; text search remains available.'; }
  } catch(error) {$('search-account').textContent=error.message;$('search-signin').hidden=false;}
}
initialize();
