// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const nodes = new Map(), requests = [];
  function node() {return {children:[],value:'',textContent:'',listeners:{},hidden:false,
    addEventListener(e,fn){this.listeners[e]=fn;},replaceChildren(...rows){this.children=rows;},append(...rows){this.children.push(...rows);}};}
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
  for(const [id,value] of Object.entries({'knowledge-query':'first','knowledge-mode':'text','knowledge-kind':'all','knowledge-depth':'0'}))document.getElementById(id).value=value;
  const context=vm.createContext({document,URLSearchParams,console,fetch(url){return new Promise(resolve=>{if(url.includes('knowledge/search?'))requests.push({url,resolve});});}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../app/static/search.js'),'utf8'),context);
  return {nodes,requests,context,search:()=>vm.runInContext('searchKnowledge()',context)};
}
const response = title => ({ok:true,status:200,json:async()=>({hits:[{title,excerpt:'<script>hostile evidence</script>',kind:'wiki_revision',revision:2,start_offset:0,end_offset:34,wiki:{revision_id:'revision'},relevance_score:null}],retrieval_method:'text',candidate_count:1,scored_count:0,fallback_reasons:['embeddings_not_configured'],graphs:[]})});

test('search renders only newest response and preserves literal untrusted evidence',async()=>{
  const h=harness(),first=h.search();h.nodes.get('knowledge-query').value='second';const second=h.search();
  h.requests[1].resolve(response('New'));await second;h.requests[0].resolve(response('Old'));await first;
  assert.equal(h.nodes.get('knowledge-results').children.length,1);
  assert.equal(h.nodes.get('knowledge-results').children[0].children[0].textContent,'New');
  assert.equal(h.nodes.get('knowledge-results').children[0].children[1].textContent,'<script>hostile evidence</script>');
  assert.match(h.nodes.get('knowledge-search-status').textContent,/ordinary search results/);
});

test('editing options invalidates an in-flight result without another search',async()=>{
  const h=harness(),pending=h.search();h.nodes.get('knowledge-kind').value='wiki';h.nodes.get('knowledge-kind').listeners.input();
  h.requests[0].resolve(response('Old'));await pending;
  assert.equal(h.nodes.get('knowledge-results').children.length,0);
  assert.match(h.nodes.get('knowledge-search-status').textContent,/Options changed/);
});

test('a stale request error cannot clear a later successful result',async()=>{
  const h=harness(),first=h.search(),second=h.search();
  h.requests[1].resolve(response('Current'));await second;h.requests[0].resolve({ok:false,status:503});await first;
  assert.equal(h.nodes.get('knowledge-results').children[0].children[0].textContent,'Current');
});

test('current policy rejection clears previous evidence and reports bounded error',async()=>{
  const h=harness(),first=h.search();h.requests[0].resolve(response('Earlier'));await first;
  const next=h.search();h.requests[1].resolve({ok:false,status:422});await next;
  assert.equal(h.nodes.get('knowledge-results').children.length,0);
  assert.match(h.nodes.get('knowledge-search-status').textContent,/instance policy/);
});
