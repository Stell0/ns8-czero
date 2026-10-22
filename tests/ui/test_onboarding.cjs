// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
const tick=()=>new Promise(setImmediate);
function setup(script) {
  const nodes=new Map(), requests=[], events={}, downloads=[], revoked=[], dispatched=[];
  class Element {
    constructor(tag='div'){this.tagName=tag;this.children=[];this.listeners={};this.attributes={};this.hidden=false;this.disabled=false;this.checked=false;this.value='';this.textContent='';}
    addEventListener(name,fn){this.listeners[name]=fn;}
    append(...children){this.children.push(...children);}
    replaceChildren(...children){this.children=children;}
    setAttribute(k,v){this.attributes[k]=v;}
    click(){downloads.push(this);}
    remove(){this.removed=true;}
    set innerHTML(_){throw Error('HTML assignment');}
  }
  const node=id=>{if(!nodes.has(id)) nodes.set(id,new Element());return nodes.get(id);};
  const document={getElementById:node,body:new Element(),querySelectorAll:()=>[],createElement:tag=>new Element(tag),dispatchEvent:event=>dispatched.push(event)};
  class TestURL extends URL {}
  TestURL.createObjectURL=()=> 'blob:fixture'; TestURL.revokeObjectURL=url=>revoked.push(url);
  const window={C0Space:{onClear(fn){events.clear=fn;}},addEventListener(name,fn){events[name]=fn;},location:{assign(url){events.destination=url;},reload(){events.reloaded=true;}}};
  const context={document,window,URL:TestURL,CustomEvent:class{constructor(type,value){this.type=type;this.detail=value.detail;}},setTimeout:fn=>{events.timeout=fn;},
    fetch:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
  node('connect-read').checked=true;
  vm.runInNewContext(fs.readFileSync('app/static/'+script,'utf8'),context);
  const reply=(index,data,status=200,headers={})=>requests[index].resolve({ok:status>=200&&status<300,status,json:async()=>data,blob:async()=>({archive:true}),headers:{get:key=>headers[key]||null}});
  const click=(id,name='click')=>node(id).listeners[name]({preventDefault(){}});
  return {node,requests,events,downloads,revoked,dispatched,reply,click};
}
const profile={role:'admin',username:'Alice',csrf_token:'private-csrf'};
const metadata={available:true,name:'C0',hostname:'memory.example.org',description:'C0 Knowledge Storage on memory.example.org',mcp_url:'https://memory.example.org/mcp',client_metadata_enabled:true};
const view={profile,csrf_token:'private-csrf',metadata_url:'https://chatgpt.com/client.json',callback:'https://chatgpt.com/callback',scopes:['c0:read','c0:write','c0:admin'],approved:false,allowed_scopes:[]};
async function agents(){const h=setup('agents.js');h.reply(0,metadata);h.reply(1,profile);await tick();return h;}
async function connect(value=view){const h=setup('connect.js');h.reply(0,profile);await tick();h.reply(1,value);await tick();return h;}
test('setup shows canonical public details even when the browser session expired',async()=>{
  const h=setup('agents.js');h.reply(0,metadata);h.reply(1,{},401);await tick();
  assert.equal(h.node('agent-description').value,metadata.description);assert.equal(h.node('agent-mcp-url').value,metadata.mcp_url);
  assert.equal(h.node('download-skill').href,'./agents/c0-memory.skill');assert.equal(h.node('download-plugin').disabled,true);
  assert.equal(h.node('onboarding-signin').hidden,false);
});
test('plugin download has CSRF, suppresses duplicate submits and revokes its object URL',async()=>{
  const h=await agents();h.node('chatgpt-connection').value='asdk_app_fixture';
  h.click('plugin-download-form','submit');h.click('plugin-download-form','submit');
  assert.equal(h.requests.length,3);assert.equal(h.requests[2].options.headers['X-C0-CSRF'],'private-csrf');
  h.reply(2,{},200,{'Content-Type':'application/zip','Content-Disposition':'attachment; filename="c0-fixture.zip"'});await tick();
  assert.equal(h.downloads.length,1);assert.equal(h.downloads[0].download,'c0-fixture.zip');assert.equal(h.downloads[0].removed,true);
  h.events.timeout();assert.deepEqual(h.revoked,['blob:fixture']);
});
test('editing connection details suppresses an earlier archive and leaves useful feedback',async()=>{
  const h=await agents();h.node('chatgpt-connection').value='asdk_app_first';h.click('plugin-download-form','submit');
  h.node('chatgpt-connection').value='asdk_app_second';h.click('chatgpt-connection','input');
  h.reply(2,{},200,{'Content-Type':'application/zip'});await tick();
  assert.equal(h.downloads.length,0);assert.match(h.node('plugin-download-status').textContent,/changed/);assert.equal(h.node('download-plugin').disabled,false);
});
test('access loss clears private download state and rejects late success',async()=>{
  const h=await agents();h.node('chatgpt-connection').value='asdk_app_fixture';h.click('plugin-download-form','submit');h.events.clear();
  h.reply(2,{},200,{'Content-Type':'application/zip'});await tick();assert.equal(h.downloads.length,0);
  assert.equal(h.node('chatgpt-connection').value,'');assert.equal(h.node('download-plugin').disabled,true);
  assert.equal(h.node('agent-mcp-url').value,metadata.mcp_url);
});
test('non-ZIP server response cannot become a plugin download',async()=>{
  const h=await agents();h.click('plugin-download-form','submit');h.reply(2,{},200,{'Content-Type':'text/html'});await tick();
  assert.equal(h.downloads.length,0);assert.match(h.node('plugin-download-status').textContent,/did not complete/);
});
test('new connection does not fetch metadata or enable consent before deliberate Admin review',async()=>{
  const h=await connect();assert.equal(h.requests.length,2);assert.equal(h.node('connect-read').checked,true);
  assert.equal(h.node('connect-write').checked,false);assert.equal(h.node('connect-admin').checked,false);
  assert.equal(h.node('connect-next').disabled,true);assert.equal(h.node('connect-approve').disabled,true);
  assert.equal(h.requests[1].options.headers['X-C0-CSRF'],'private-csrf');
});
test('metadata review renders hostile names as text and binds the current callback',async()=>{
  const h=await connect();h.click('connect-preview');
  h.reply(2,{metadata_digest:'digest',descriptor:{client_id:view.metadata_url,client_name:'<img src=x>',redirect_uris:[view.callback],scope_ceiling:['c0:read']}});await tick();
  h.reply(3,{clients:[]});await tick();
  assert.equal(h.node('connect-review').children[0].textContent,'<img src=x>');assert.equal(h.node('connect-approve').disabled,false);
  h.click('connect-approve');assert.deepEqual(JSON.parse(h.requests[4].options.body).allowed_scopes,['c0:read']);
  h.reply(4,{});await tick();h.reply(5,{...view,approved:true,allowed_scopes:['c0:read']});await tick();
  assert.equal(h.node('connect-next').disabled,false);
});
test('changed permissions invalidate a pending metadata preview',async()=>{
  const h=await connect();h.click('connect-preview');h.node('connect-write').checked=true;h.click('connect-write','change');
  h.reply(2,{metadata_digest:'digest',descriptor:{client_id:view.metadata_url,client_name:'Client',redirect_uris:[view.callback]}});await tick();
  h.reply(3,{clients:[]});await tick();assert.equal(h.node('connect-review').children.length,0);assert.equal(h.node('connect-approve').disabled,true);
});
test('consent handoff only accepts the fixed local destination',async()=>{
  const h=await connect({...view,approved:true,allowed_scopes:['c0:read']});h.click('connect-continue','submit');
  h.reply(2,{next:'https://outside.example.org/'});await tick();assert.equal(h.events.destination,undefined);
  assert.match(h.node('connect-status').textContent,/did not return a consent page/);
});
test('expired requests hide private identity and offer a human recovery message',async()=>{
  const h=await connect({...view,approved:true,allowed_scopes:['c0:read']});h.click('connect-continue','submit');h.reply(2,{},410);await tick();
  assert.equal(h.node('connect-client').textContent,'');assert.equal(h.node('connect-workspace').hidden,true);
  assert.match(h.node('connect-status').textContent,/expired.*ChatGPT/);
});
test('Admin queue deduplicates requests, preserves scope upgrades and never fetches metadata',async()=>{
  const h=setup('connection-requests.js');h.reply(0,profile);await tick();
  const request={username:'<Alice>',metadata_url:view.metadata_url,callback:view.callback,scopes:['c0:read','c0:write'],approved:true,allowed_scopes:['c0:read']};
  h.reply(1,{requests:[request,request,{...request,metadata_url:'https://chatgpt.com/approved.json',scopes:['c0:read']}]});await tick();
  assert.equal(h.node('cimd-requests').children.length,1);assert.equal(h.requests.length,2);
  h.node('cimd-requests').children[0].children.at(-1).listeners.click();assert.equal(h.dispatched[0].detail.metadata_url,view.metadata_url);
  h.events.clear();assert.equal(h.node('cimd-requests').children.length,0);
});
test('Reader never requests the administrative connection queue',async()=>{
  const h=setup('connection-requests.js');h.reply(0,{...profile,role:'reader'});await tick();assert.equal(h.requests.length,1);
  assert.equal(h.node('cimd-requests-refresh').disabled,true);
});
