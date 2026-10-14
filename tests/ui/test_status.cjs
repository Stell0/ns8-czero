// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const { test }=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){const status={textContent:''},button={disabled:false,addEventListener(_,fn){this.click=fn;}};const pending=[];
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../app/static/status.js'),'utf8'),{
document:{getElementById(id){return id==='database-status'?status:button;}},fetch(){return new Promise((resolve,reject)=>pending.push({resolve,reject}));}});
return {status,button,pending};}
const reply=(state,ok=true)=>({ok,json:async()=>({status:state,database:{status:state==='ok'?'ok':'unavailable'}})});
test('workspace reports non-success health as unavailable',async()=>{const h=setup();h.pending[0].resolve(reply('ok',false));await tick();assert.match(h.status.textContent,/Workspace unavailable/);assert.equal(h.button.disabled,false);});
test('older success cannot replace the latest unavailable result',async()=>{const h=setup();h.button.click();h.pending[1].resolve(reply('degraded',false));await tick();h.pending[0].resolve(reply('ok'));await tick();assert.match(h.status.textContent,/Workspace unavailable/);});
test('older network error cannot replace latest ready result',async()=>{const h=setup();h.button.click();h.pending[1].resolve(reply('ok'));await tick();h.pending[0].reject(new Error('network'));await tick();assert.equal(h.status.textContent,'Workspace ready');assert.equal(h.button.disabled,false);});
