// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {fixture,tick,reply,id,page}=require('./reader_dom.js');
const shared={id:id(100),name:'Shared',shared:true,role:'editor'},privateSpace={id:id(101),name:'<img src=x> Private',shared:false,role:'editor'};
function spaces(kind='wiki',search='?space_id='+id(101)){
  const h=fixture(kind,search);h.navigations=[];h.reloads=0;
  h.window.document.addEventListener=(name,handler)=>{h.events['document:'+name]=handler;};
  h.window.setInterval=(handler,ms)=>{h.interval=handler;assert.equal(ms,30000);};
  h.window.location.assign=value=>h.navigations.push(value);h.window.location.reload=()=>{h.reloads++;};
  vm.runInContext(fs.readFileSync('app/static/spaces.js','utf8'),h.context);
  h.scope=h.window.C0Space;return h;
}
async function ready(h,entries=[shared,privateSpace]){h.requests[0].resolve(reply({spaces:entries}));await tick();}

test('space URLs preserve the legacy prefix, shared schemas and authentication URLs',async()=>{
  const h=spaces();await ready(h);
  assert.equal(h.node('space-selector').value,privateSpace.id);
  assert(h.node('space-selector').textContent.includes('<img src=x> Private'));
  assert(!h.node('space-selector').children.some(c=>c.tagName==='IMG'));
  assert.match(h.scope.apiURL('wiki/pages?limit=5'),new RegExp('/czero/czero17/api/v1/wiki/pages\\?limit=5&space_id='+privateSpace.id));
  assert(!h.scope.apiURL('object-types').includes('space_id'));
  assert.equal(h.scope.pageURL('./auth/login'),'./auth/login');
  assert.equal(h.scope.pageURL('https://elsewhere.test/wiki'),'https://elsewhere.test/wiki');
  assert.equal(h.scope.pageURL('./wiki?space_id='+shared.id),'./wiki?space_id='+shared.id);
  assert.match(h.C.pageURL(id(1),2),new RegExp('space_id='+privateSpace.id));
  assert.match(h.C.task('read'),new RegExp('Knowledge space ID: '+privateSpace.id));
  const legacy=spaces('wiki','');await ready(legacy);assert.equal(legacy.scope.apiURL('wiki/pages'),'./api/v1/wiki/pages');
});

test('space change clears private views before navigation and drops old resource identities',async()=>{
  const h=spaces('wiki','?space_id='+privateSpace.id+'&page='+id(1)+'&revision=2&view=tools');await ready(h);
  let privateContent='Private article';h.scope.onClear(()=>{privateContent='';});
  h.window.location.assign=value=>{assert.equal(privateContent,'');h.navigations.push(value);};
  h.node('space-selector').value=shared.id;h.node('space-selector').listeners.change();
  assert.equal(h.navigations.length,1);const target=new URL(h.navigations[0]);
  assert.equal(target.searchParams.get('view'),'tools');
  for(const name of ['space_id','page','revision'])assert(!target.searchParams.has(name));
});

test('late JSON and late response headers are rejected after the space epoch changes',async()=>{
  const h=spaces();await ready(h);
  let finishBody;const body=new Promise(resolve=>finishBody=resolve);
  const first=h.scope.request('wiki/pages').then(response=>response.json());
  h.requests[1].resolve({ok:true,status:200,json:()=>body});await tick();
  h.scope.clear();finishBody({pages:[{title:'Private delayed content'}]});
  await assert.rejects(first,/Space access changed/);
  const next=spaces();await ready(next);const pending=next.scope.request('wiki/pages');next.scope.clear();
  next.requests[1].resolve(reply({pages:[{title:'Private late headers'}]}));await assert.rejects(pending,/Space access changed/);
});

test('invalid and duplicate selectors never request content or select Shared automatically',async()=>{
  for(const query of ['?space_id=invalid','?space_id=','?space_id='+id(101)+'&space_id='+id(100)]){
    const h=spaces('wiki',query);await ready(h,[shared]);
    assert.equal(h.node('space-selector').value,'unavailable');
    const before=h.requests.length;await assert.rejects(h.scope.request('wiki/pages'),/unavailable/);assert.equal(h.requests.length,before);
    assert(!h.navigations.length);
  }
});

test('role changes reload only after clearing the private view',async()=>{
  const h=spaces();await ready(h);let visible='Private content';h.scope.onClear(()=>visible='');
  const pending=h.interval();h.requests[1].resolve(reply({...privateSpace,role:'reader'}));await pending;
  assert.equal(visible,'');assert.equal(h.reloads,1);
});

test('revocation clears article headings, bodies, citations and private export links',async()=>{
  const h=spaces();await ready(h);const reader=h.reader();
  const privatePage={...page(),title:'Private title',content:{...page().content,title:'Private title',body:'Private body'}};
  const loading=reader.loadArticle(id(1));h.requests[1].resolve(reply(privatePage));await tick();
  h.requests[2].resolve(reply({claims:[]}));await loading;
  assert.equal(h.node('page-title').textContent,'Private title');assert.match(h.node('reader-export').href,new RegExp(privateSpace.id));
  const checking=h.interval();h.requests[3].resolve(reply({},403));await checking;
  assert.equal(h.node('page-title').textContent,'Knowledge');
  for(const key of ['reader-content','reader-facts','reader-evidence','reader-breadcrumbs','reader-technical'])assert.equal(h.node(key).textContent,'');
  assert(!h.node('reader-export').href);assert.equal(h.node('reader-root').hidden,true);
});

for(const [kind,script,setup,call,result,list,input] of [
  ['objects','objects.js',"el('record-type').value='inventory'",'loadRecords()',{objects:[{id:id(1),type_name:'inventory',data:{name:'Private record'},revision:1,tags:[]}]},'record-list','record-data'],
  ['wiki','wiki.js','', 'loadPages()',{pages:[page()]},'wiki-pages','wiki-body'],
  ['sources','sources.js','', 'loadSources()',{sources:[{id:id(1),title:'Private source'}]},'source-list','upload-title'],
])test(kind+' maintenance clears private forms and rejects a late list after space change',async()=>{
  const h=spaces(kind,'?space_id='+privateSpace.id+'&view=tools');await ready(h);
  vm.runInContext(fs.readFileSync('app/static/'+script,'utf8'),h.context);
  if(setup)vm.runInContext(setup,h.context);
  let index=h.requests.length;const first=vm.runInContext(call,h.context);h.requests[index].resolve(reply(result));await first;
  assert(h.node(list).children.length>0);h.node(input).value='Private draft';
  index=h.requests.length;const late=vm.runInContext(call,h.context);h.scope.clear();
  h.requests[index].resolve(reply(result));await assert.rejects(late,/Space access changed/);
  assert.equal(h.node(list).children.length,0);assert.equal(h.node(input).value,'');
});

test('private headings, navigation and typed drafts clear when space access is lost',async()=>{
  for(const [kind,script,fields,texts] of [
    ['wiki','wiki.js',['entity-kind','claim-predicate','knowledge-relation-kind'],['graph-status','entity-status','claim-status']],
    ['sources','sources.js',['source-query'],['source-heading','sources-status','upload-status']],
    ['objects','objects.js',['relation-kind','type-name','type-label','type-schema','type-unique'],['record-heading','relation-targets-status','type-status']],
  ]){
    const h=spaces(kind,'?space_id='+privateSpace.id+'&view=tools');await ready(h);
    vm.runInContext(fs.readFileSync('app/static/'+script,'utf8'),h.context);
    for(const field of fields)h.node(field).value='Private draft';
    for(const field of texts)h.node(field).textContent='Private metadata';
    h.scope.clear();
    for(const field of fields)assert.equal(h.node(field).value,'',kind+' '+field);
    for(const field of texts)assert.equal(h.node(field).textContent,'',kind+' '+field);
  }
  const h=spaces();await ready(h);h.reader();h.node('reader-toc').textContent='Private article heading';h.scope.clear();assert.equal(h.node('reader-toc').textContent,'');
});

test('space guide uses effective role and drops a late capability response after revocation',async()=>{
  const h=spaces('agents');await ready(h);const reader=h.reader(),pending=reader.guide();
  h.requests[1].resolve(reply({authenticated:true,role:'editor',interfaces:{mcp:true},mcp_url:'https://c0.test/mcp'}));await tick();
  assert(h.requests[2], 'Guide must request the effective space role');h.requests[2].resolve(reply({role:'reader'}));await pending;
  assert.doesNotMatch(h.node('guide-tasks').textContent,/Create an article|Update knowledge|Import a document/);
  const next=reader.guide();h.scope.clear();h.requests[3].resolve(reply({authenticated:true,role:'editor',interfaces:{mcp:true}}));await next;
  assert.equal(h.node('guide-tasks').textContent,'');
});

test('revocation removes private catalog labels and header query drafts',async()=>{
  const h=spaces();await ready(h);h.node('site-query').value='Private investigation';h.scope.clear();
  assert(!h.node('space-selector').textContent.includes('Private'));
  assert.equal(h.node('site-query').value,'');
});

test('late Administration bootstrap cannot reopen private global panels after a space change',async()=>{
  const h=spaces('admin');await ready(h);h.node('admin-workspace').hidden=true;
  vm.runInContext(fs.readFileSync('app/static/admin.js','utf8'),h.context);
  h.node('admin-account').textContent='Signed in as Private operator';h.node('client-status').textContent='17 private clients';
  h.scope.clear();h.requests[1].resolve(reply({role:'admin',username:'Private operator'}));await tick();
  assert.equal(h.node('admin-workspace').hidden,true);
  assert(!h.node('admin-account').textContent.includes('Private operator'));
  assert.equal(h.node('client-status').textContent,'');
  assert.equal(h.requests.length,2);
});
