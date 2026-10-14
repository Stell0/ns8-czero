// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){const nodes=new Map(),requests=[],redirects=[];
const element=()=>({children:[],listeners:{},hidden:true,disabled:false,value:'',textContent:'',attributes:{},
append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(k,v){this.attributes[k]=v;},
addEventListener(k,fn){this.listeners[k]=fn;},set innerHTML(_){throw new Error('Untrusted HTML');}});
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../app/static/auth.js'),'utf8'),{document,encodeURIComponent,
window:{location:{assign(v){redirects.push(v);}}},fetch(url,options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));}});
return{nodes,requests,redirects};}
const response=(data,status=200)=>({ok:status===200,status,json:async()=>data});
const member=(id='member')=>({id,username:id,display_name:'<img src=x>',role:'reader',is_owner:false,last_seen:'2026-01-01T00:00:00Z'});
async function identity(h,role='admin',offset=0){h.requests[offset].resolve(response({configured:true}));await tick();h.requests[offset+1].resolve(response({username:'Alice',role,is_owner:role==='admin',csrf_token:'fixture-only'}));await tick();}
async function ready(){const h=setup();await identity(h);h.requests[2].resolve(response({accounts:[member()]}));await tick();return h;}
const select=(h,row=0)=>h.nodes.get('accounts').children[row].children[1].children[0];
const button=(h,row=0)=>h.nodes.get('accounts').children[row].children[2].children[0];
test('sharing uses literal profile data and labelled controls',async()=>{const h=await ready();assert.equal(h.nodes.get('accounts').children[0].children[0].textContent,'<img src=x>');assert.equal(select(h).attributes['aria-label'],'Access for member');});
test('stale Admin list cannot render after latest Reader identity',async()=>{const h=setup();await identity(h);h.nodes.get('refresh-account').listeners.click();await identity(h,'reader',3);h.requests[2].resolve(response({accounts:[member()]}));await tick();assert.equal(h.nodes.get('sharing').hidden,true);assert.equal(h.nodes.get('accounts').children.length,0);assert.match(h.nodes.get('account-status').textContent,/reader/);});
test('membership write captures selection and retains a newer draft',async()=>{const h=await ready(),field=select(h),save=button(h);save.listeners.click();save.listeners.click();assert.equal(h.requests.length,4);assert.deepEqual(JSON.parse(h.requests[3].options.body),{role:'reader'});assert.equal(h.requests[3].options.headers['X-C0-CSRF'],'fixture-only');field.value='editor';h.requests[3].resolve(response(null));await tick();assert.equal(field.value,'editor');assert.match(h.nodes.get('sharing-status').textContent,/Earlier selection saved/);assert.equal(h.requests.length,4);assert.equal(save.disabled,false);});
test('older list response cannot replace the latest saved memberships',async()=>{const h=setup();await identity(h);h.requests[2].resolve(response({accounts:[member('first'),member('second')]}));await tick();const first=button(h,0),second=button(h,1);first.listeners.click();h.requests[3].resolve(response(null));await tick();second.listeners.click();h.requests[5].resolve(response(null));await tick();h.requests[6].resolve(response({accounts:[member('latest')]}));await tick();h.requests[4].resolve(response({accounts:[member('old')]}));await tick();assert.equal(select(h).attributes['aria-label'],'Access for latest');});
test('old sign-out response cannot redirect a refreshed identity',async()=>{const h=await ready();h.nodes.get('sign-out').listeners.click();h.nodes.get('refresh-account').listeners.click();await identity(h,'reader',4);h.requests[3].resolve(response({logout_url:'https://idp.example.test/logout'}));await tick();assert.deepEqual(h.redirects,[]);assert.match(h.nodes.get('account-status').textContent,/reader/);});
