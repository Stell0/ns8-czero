// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
function harness(){
  const nodes=new Map(),requests=[];
  const node=()=>({children:[],value:'',textContent:'',listeners:{},addEventListener(e,f){this.listeners[e]=f;},replaceChildren(...c){this.children=c;},append(...c){this.children.push(...c);}});
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
  let keys=0;
  const context=vm.createContext({document,URLSearchParams,crypto:{randomUUID:()=>String(++keys)},fetch(url,options){return new Promise((resolve,reject)=>{if(!url.includes('/auth/status'))requests.push({url,options,resolve,reject});});}});
  vm.runInContext(fs.readFileSync('app/static/wiki.js','utf8'),context);
  return {nodes,requests,run:code=>vm.runInContext(code,context)};
}
const reply=data=>({ok:true,status:200,json:async()=>data});
const page=id=>({id,slug:id,title:id,revision:1,content:{body:'# '+id,metadata:{}}});
const flush=()=>new Promise(setImmediate);
test('late page detail preserves the newer selection',async()=>{
  const h=harness(),old=h.run("selectPage('old')"),latest=h.run("selectPage('latest')");
  h.requests[1].resolve(reply(page('latest')));await flush();h.requests[2].resolve(reply({revisions:[]}));await latest;
  h.requests[0].resolve(reply(page('old')));await old;
  assert.equal(h.nodes.get('wiki-heading').textContent,'latest');
});
test('late list replies cannot duplicate or replace current pages',async()=>{
  const h=harness(),a=h.run('loadPages()'),b=h.run('loadPages()');
  h.requests[1].resolve(reply({pages:[page('<script>hostile</script>')]}));await b;
  h.requests[0].resolve(reply({pages:[page('old')]}));await a;
  const rows=h.nodes.get('wiki-pages').children;
  assert.equal(rows.length,1);assert.equal(rows[0].children[0].textContent,'<script>hostile</script>');
});
test('late entity lists preserve both newest data and current selection',async()=>{
  const h=harness(),a=h.run('loadEntities()'),b=h.run('loadEntities()');
  h.nodes.get('knowledge-entity').value='new';
  h.requests[1].resolve(reply({entities:[{id:'new',label:'New'}]}));await b;
  h.requests[0].resolve(reply({entities:[{id:'old',label:'Old'}]}));await a;
  assert.equal(h.nodes.get('knowledge-entity').value,'new');assert.equal(h.nodes.get('knowledge-entity').children[1].textContent,'New');
});
test('an older save cannot discard a new unsaved draft',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};displayPage("+JSON.stringify(page('old'))+")");
  h.nodes.get('wiki-body').value='edit old';const saving=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});
  h.run('displayPage(null)');h.nodes.get('wiki-body').value='unsaved draft';
  h.requests[0].resolve(reply({...page('old'),revision:2}));await flush();h.requests[1].resolve(reply({pages:[]}));await saving;
  assert.equal(h.nodes.get('wiki-body').value,'unsaved draft');assert.equal(h.nodes.get('wiki-heading').textContent,'New page');
});
test('a conflict preserves authored text until explicit reload',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};displayPage("+JSON.stringify(page('old'))+")");
  h.nodes.get('wiki-body').value='conflicting draft';const saving=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});
  h.requests[0].resolve({ok:false,status:409});await saving;
  assert.equal(h.nodes.get('wiki-body').value,'conflicting draft');assert.match(h.nodes.get('page-status').textContent,/draft is preserved/);
});
test('an uncertain identical retry reuses its idempotency key',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'}");
  const first=h.run("write('wiki/pages',{body:'same'})");h.requests[0].reject(new Error('network failure'));await assert.rejects(first);
  const retry=h.run("write('wiki/pages',{body:'same'})");
  assert.equal(JSON.parse(h.requests[0].options.body).idempotency_key,JSON.parse(h.requests[1].options.body).idempotency_key);
  h.requests[1].resolve(reply(page('saved')));await retry;
});

test('late revision previews cannot replace a newer chosen revision',async()=>{
  const h=harness();h.run('displayPage('+JSON.stringify(page('page'))+')');
  const history=h.run('loadHistory()');h.requests[0].resolve(reply({revisions:[{number:1},{number:2}]}));await history;
  const buttons=h.nodes.get('wiki-history').children.map(row=>row.children[0]);
  buttons[0].listeners.click();buttons[1].listeners.click();
  h.requests[2].resolve(reply({content:{body:'new revision'}}));await flush();
  h.requests[1].resolve(reply({content:{body:'old revision'}}));await flush();
  assert.match(h.nodes.get('wiki-revision').textContent,/new revision/);assert.doesNotMatch(h.nodes.get('wiki-revision').textContent,/old revision/);
});
test('Reader page fields remain read-only and mutations hidden',()=>{
  const h=harness();h.run("profile={role:'reader'};displayPage("+JSON.stringify(page('page'))+")");
  for(const id of ['wiki-title','wiki-body','wiki-metadata','wiki-slug'])assert.equal(h.nodes.get(id).readOnly,true);
  for(const id of ['save-page','archive-page'])assert.equal(h.nodes.get(id).hidden,true);
});

test('same-page save advances revision while retaining edits made during the write',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};displayPage("+JSON.stringify(page('same'))+")");
  h.nodes.get('wiki-body').value='first edit';const saving=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});
  h.nodes.get('wiki-body').value='newer draft';h.nodes.get('wiki-body').listeners.input();
  h.requests[0].resolve(reply({...page('same'),revision:2}));await flush();h.requests[1].resolve(reply({revisions:[]}));await flush();h.requests[2].resolve(reply({pages:[]}));await saving;
  assert.equal(h.nodes.get('wiki-body').value,'newer draft');assert.equal(h.run('currentPage.revision'),2);assert.match(h.nodes.get('page-status').textContent,/newer edits are preserved/);
});
test('a new selection can save independently of an earlier pending write',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};displayPage("+JSON.stringify(page('old'))+")");
  const old=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});h.run('displayPage(null)');
  assert.equal(h.nodes.get('save-page').disabled,false);h.nodes.get('wiki-slug').value='new';const latest=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});
  h.requests[0].resolve({ok:false,status:409});await old;assert.equal(h.nodes.get('save-page').disabled,true);
  h.requests[1].resolve({ok:false,status:409});await latest;assert.equal(h.nodes.get('save-page').disabled,false);
});
const graph=(label='Root')=>({nodes:[{id:'root',kind:'system',label,depth:0},{id:'target',kind:'system',label:'Target',depth:1}],relations:[{source_id:'root',target_id:'target',kind:'related-to'}],references:[],truncated:false});
test('graph lists use literal hostile labels and fixed typed reference URLs',()=>{
  const h=harness(),result=graph('<img src=x>');result.references=[
    {target_kind:'chunk',target_id:'00000000-0000-4000-8000-000000000001',label_snapshot:'<script>bad</script>'},
    {target_kind:'object',target_id:'00000000-0000-4000-8000-000000000002',label_snapshot:'Old record',missing:true},
    {target_kind:'__proto__',target_id:'javascript:alert(1)',label_snapshot:'Unsafe'},
  ];h.run('renderGraph('+JSON.stringify(result)+')');
  assert.equal(h.nodes.get('graph-nodes').children[0].children[0].textContent,'<img src=x> · system · hop 0');
  assert.match(h.nodes.get('graph-edges').children[0].textContent,/<img src=x> → related-to → Target/);
  const rows=h.nodes.get('graph-references').children;assert.match(rows[0].textContent,/<script>bad<\/script>/);
  assert.equal(rows[0].children[0].href,'./api/v1/chunks/00000000-0000-4000-8000-000000000001/citation');
  assert.match(rows[1].textContent,/missing/);assert.equal(rows[1].children.length,0);assert.equal(rows[2].children.length,0);
});
test('graph depth edits invalidate earlier successes and errors',async()=>{
  for(const fail of [false,true]){
    const h=harness();h.run("currentEntity={id:'root'}");h.nodes.get('graph-depth').value='1';const pending=h.run('loadGraph()');
    h.nodes.get('graph-depth').value='3';h.nodes.get('graph-depth').listeners.change();
    if(fail)h.requests[0].reject(new Error('private transport detail'));else h.requests[0].resolve(reply(graph('Old')));
    await pending;assert.equal(h.nodes.get('graph-nodes').children.length,0);assert.match(h.nodes.get('graph-status').textContent,/options changed/);
  }
});
test('older graph replies cannot replace a newer selected entity result',async()=>{
  const h=harness();h.run("currentEntity={id:'root'}");const first=h.run('loadGraph()');h.run("++entitySequence;currentEntity={id:'new'}");const latest=h.run('loadGraph()');
  h.requests[1].resolve(reply(graph('New')));await latest;h.requests[0].resolve(reply(graph('Old')));await first;
  assert.match(h.nodes.get('graph-nodes').children[0].children[0].textContent,/New/);
});
test('a graph node opens its entity and preserves a picker entry beyond the initial list',async()=>{
  const h=harness();h.run('renderGraph('+JSON.stringify(graph())+')');h.nodes.get('graph-nodes').children[1].children[0].listeners.click();
  assert.equal(h.requests[0].url,'./api/v1/entities/target');assert.equal(h.nodes.get('knowledge-entity').value,'target');
  h.requests[0].resolve(reply({id:'target',revision:1,label:'Target'}));h.requests[1].resolve(reply({claims:[]}));await flush();
  assert.equal(h.run('currentEntity.id'),'target');assert.equal(h.nodes.get('graph-nodes').children.length,0);
});
test('new-page save with newer edits establishes immutable slug and export links',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};displayPage(null)");h.nodes.get('wiki-slug').value='created';
  const saving=h.nodes.get('wiki-form').listeners.submit({preventDefault(){}});h.nodes.get('wiki-slug').value='too-late';h.nodes.get('wiki-slug').listeners.input();h.nodes.get('wiki-body').value='new draft';
  h.requests[0].resolve(reply(page('created')));await flush();h.requests[1].resolve(reply({revisions:[]}));await flush();h.requests[2].resolve(reply({pages:[]}));await saving;
  assert.equal(h.nodes.get('wiki-body').value,'new draft');assert.equal(h.nodes.get('wiki-slug').value,'created');assert.equal(h.nodes.get('wiki-slug').readOnly,true);
  assert.equal(h.nodes.get('export-json').hidden,false);assert.equal(h.nodes.get('export-json').href,'./api/v1/wiki/pages/created/export?format=json');
});
test('late relationship write errors do not overwrite a newer graph selection',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'};currentEntity={id:'old'}");
  const saving=h.nodes.get('knowledge-relation-form').listeners.submit({preventDefault(){}});
  h.run("++entitySequence;currentEntity={id:'new'};$('graph-status').textContent='New graph'");
  h.requests[0].resolve({ok:false,status:409});await saving;assert.equal(h.nodes.get('graph-status').textContent,'New graph');
});
