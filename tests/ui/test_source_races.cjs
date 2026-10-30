// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
// Execute the actual source UI with controllable asynchronous responses.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
function harness() {
  const nodes = new Map(), requests = [];
  function node() {return {children:[],value:'',textContent:'',listeners:{},files:[],
    addEventListener(event,callback){this.listeners[event]=callback;},
    replaceChildren(...children){this.children=children;},append(...children){this.children.push(...children);}};}
  const document = {getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
  for(const match of fs.readFileSync(path.join(__dirname,'../../app/static/sources.html'),'utf8').matchAll(/id="([^"]+)"/g))document.getElementById(match[1]);
  class FormData {constructor(){this.values=[];}append(...value){this.values.push(value);}}
  const context = vm.createContext({document,URLSearchParams,FormData,console,setTimeout(){},clearTimeout(){},
    fetch(url,options){return new Promise((resolve,reject)=>{if(!url.includes('/auth/status'))requests.push({url,options,resolve,reject});});}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../app/static/sources.js'),'utf8'),context);
  return {context,nodes,requests,run:code=>vm.runInContext(code,context)};
}
const reply = data => ({ok:true,status:200,json:async()=>data});
const source = id => ({id,title:id,revision:1,metadata:{},deleted:false});
const history = id => ({versions:[{id,number:1,state:'ready',original_present:false,retain_original:false}]});

test('source refresh ignores older replies and never duplicates rows', async()=>{
  const h=harness(),first=h.run('loadSources()'),second=h.run('loadSources()');
  h.requests[1].resolve(reply({sources:[source('new')]}));await second;
  h.requests[0].resolve(reply({sources:[source('old')]}));await first;
  assert.equal(h.nodes.get('source-list').children.length,1);
  assert.equal(h.nodes.get('source-list').children[0].children[0].textContent,'new');
});
test('late source history cannot replace the latest selection', async()=>{
  const h=harness(),first=h.run("selectSource('old')"),second=h.run("selectSource('new')");
  h.requests[2].resolve(reply(source('new')));h.requests[3].resolve(reply(history('new')));await second;
  h.requests[0].resolve(reply(source('old')));h.requests[1].resolve(reply(history('old')));await first;
  assert.equal(h.nodes.get('source-heading').textContent,'new');
  assert.match(h.nodes.get('source-identity').textContent,/^new ·/);
  assert.equal(h.nodes.get('source-versions').children.length,1);
});
test('late extracted text cannot replace a newer version', async()=>{
  const h=harness(),first=h.run("loadDocument('old')"),second=h.run("loadDocument('new')");
  h.requests[1].resolve(reply({id:'new-doc',body:'new evidence',text_hash:'new'}));
  await new Promise(setImmediate);h.requests[2].resolve(reply({chunks:[]}));await second;
  h.requests[0].resolve(reply({id:'old-doc',body:'old evidence',text_hash:'old'}));await first;
  assert.equal(h.nodes.get('document-text').textContent,'new evidence');
});
test('late search cannot replace a changed query', async()=>{
  const h=harness();h.nodes.get('source-query').value='old';const first=h.run('searchSources()');
  h.nodes.get('source-query').value='new';const second=h.run('searchSources()');
  const results=name=>({citations:[{title:name,version:1,body:name}]});
  h.requests[1].resolve(reply(results('new')));await second;
  h.requests[0].resolve(reply(results('old')));await first;
  assert.equal(h.nodes.get('source-results').children[0].children[1].textContent,'new');
});
test('upload captures its inputs and preserves a later source selection', async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture-only'}");
  h.nodes.get('upload-file').files=[{name:'old.txt',size:10}];h.nodes.get('upload-title').value='old title';
  h.nodes.get('upload-media').value='text/plain';h.nodes.get('upload-metadata').value='{}';h.nodes.get('upload-source').value='old';
  const submitting=h.nodes.get('upload-form').listeners.submit({preventDefault(){}});
  h.nodes.get('upload-title').value='new draft';h.nodes.get('upload-source').value='new';
  h.run("++selectionSequence;currentSource={id:'new'}");
  h.requests[0].resolve(reply(source('old')));await new Promise(setImmediate);
  assert.equal(h.requests[1].options.body.values.find(v=>v[0]==='title')[1],'old title');
  h.requests[1].resolve(reply({id:'uploaded',source_id:'old'}));await new Promise(setImmediate);
  h.requests[2].resolve(reply({sources:[source('new'),source('old')]}));await submitting;
  assert.equal(h.run('currentSource.id'),'new');assert.equal(h.nodes.get('upload-title').value,'new draft');
});


test('older citations and errors cannot replace the most recently clicked chunk',async()=>{
  for(const fail of [false,true]){
    const h=harness();h.run("currentDocument={id:'doc'}");const chunks=h.run('loadChunks()');
    h.requests[0].resolve(reply({chunks:[{id:'first',ordinal:0,start_offset:0,end_offset:5},{id:'second',ordinal:1,start_offset:5,end_offset:9}]}));await chunks;
    const controls=h.nodes.get('source-chunks').children.map(row=>row.children[0]);controls[0].listeners.click();controls[1].listeners.click();
    h.requests[2].resolve(reply({chunk_id:'second'}));await new Promise(setImmediate);
    if(fail)h.requests[1].reject(new Error('private transport'));else h.requests[1].resolve(reply({chunk_id:'first'}));await new Promise(setImmediate);
    assert.equal(JSON.parse(h.nodes.get('source-citation').textContent).chunk_id,'second');
  }
});
test('query edits clear old evidence and reject earlier source-search errors',async()=>{
  const h=harness();h.nodes.get('source-query').value='old';const pending=h.run('searchSources()');
  h.nodes.get('source-results').append({textContent:'Earlier evidence'});h.nodes.get('source-query').value='new';h.nodes.get('source-query').listeners.input();
  h.requests[0].reject(new Error('private transport detail'));await pending;
  assert.equal(h.nodes.get('source-results').children.length,0);assert.match(h.nodes.get('search-status').textContent,/Query changed/);
});
test('upload metadata lookup preserves text typed after the source was chosen',async()=>{
  const h=harness();h.nodes.get('upload-source').value='existing';const pending=h.nodes.get('upload-source').listeners.change();
  h.nodes.get('upload-title').value='New draft';h.nodes.get('upload-title').listeners.input();
  h.requests[0].resolve(reply(source('existing')));await pending;assert.equal(h.nodes.get('upload-title').value,'New draft');
});
test('duplicate busy upload submissions never issue a second POST',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'}");h.nodes.get('upload-file').files=[{name:'new.txt',size:10}];h.nodes.get('upload-metadata').value='{}';
  const first=h.nodes.get('upload-form').listeners.submit({preventDefault(){}});await h.nodes.get('upload-form').listeners.submit({preventDefault(){}});
  assert.equal(h.requests.length,1);h.requests[0].resolve({ok:false,status:409});await first;assert.equal(h.nodes.get('upload-submit').disabled,false);
});

test('existing-source upload waits for metadata and preserves identity on file selection',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'}");
  h.nodes.get('upload-source').value='existing';
  const pending=h.nodes.get('upload-source').listeners.change();
  h.nodes.get('upload-file').files=[{name:'sample.txt',size:10}];
  h.nodes.get('upload-file').listeners.change();
  assert.equal(h.nodes.get('upload-title').value,'');
  assert.equal(h.nodes.get('upload-submit').disabled,true);
  await h.nodes.get('upload-form').listeners.submit({preventDefault(){}});
  assert.equal(h.requests.length,1);
  h.requests[0].resolve(reply({...source('existing'),title:'Authored title',metadata:{fixture:'browser'}}));await pending;
  assert.equal(h.nodes.get('upload-title').value,'Authored title');
  assert.equal(h.nodes.get('upload-metadata').value,'{"fixture":"browser"}');
  assert.equal(h.nodes.get('upload-submit').disabled,false);
});
test('only the latest metadata lookup releases upload readiness',async()=>{
  const h=harness();h.nodes.get('upload-source').value='same';
  const first=h.nodes.get('upload-source').listeners.change();
  h.nodes.get('upload-source').value='other';const second=h.nodes.get('upload-source').listeners.change();
  h.nodes.get('upload-source').value='same';const third=h.nodes.get('upload-source').listeners.change();
  h.requests[0].resolve(reply(source('same')));await first;
  h.requests[1].resolve(reply(source('other')));await second;
  assert.equal(h.nodes.get('upload-submit').disabled,true);
  h.requests[2].reject(new Error('transport'));await third;
  assert.equal(h.nodes.get('upload-submit').disabled,true);
  h.nodes.get('upload-source').value='';await h.nodes.get('upload-source').listeners.change();
  assert.equal(h.nodes.get('upload-submit').disabled,false);
});
test('metadata responses cannot release an upload still in flight',async()=>{
  const h=harness();h.run("profile={role:'editor',csrf_token:'fixture'}");
  h.nodes.get('upload-file').files=[{name:'new.txt',size:10}];h.nodes.get('upload-metadata').value='{}';
  h.nodes.get('upload-status').textContent='Upload accepted.';
  const submitting=h.nodes.get('upload-form').listeners.submit({preventDefault(){}});
  assert.equal(h.nodes.get('upload-status').textContent,'Uploading...');
  h.nodes.get('upload-source').value='existing';const lookup=h.nodes.get('upload-source').listeners.change();
  h.requests[1].resolve(reply(source('existing')));await lookup;
  assert.equal(h.nodes.get('upload-submit').disabled,true);
  h.requests[0].resolve({ok:false,status:409});await submitting;
  assert.equal(h.nodes.get('upload-submit').disabled,false);
});
