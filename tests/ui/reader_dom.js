// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
// Small literal DOM fixture for the real scripts; HTTP tests separately check actual template IDs.
const fs=require('node:fs'), vm=require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.attributes={};this._text='';this.value='';this.hidden=false;this.disabled=false;this.open=false;}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent || '').join('');}
  append(...nodes){this.children.push(...nodes);}
  prepend(...nodes){this.children.unshift(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  addEventListener(name,handler){this.listeners[name]=handler;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name] ?? null;}
  focus(){this.focused=true;}
  select(){this.selected=true;}
  set innerHTML(_){throw new Error('Untrusted HTML assignment');}
}
function fixture(kind='wiki',search='') {
  const nodes=new Map(),requests=[],events={};
  const document={body:{dataset:{page:kind}},documentElement:{dataset:{}},querySelectorAll:()=>[],
    getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
    createElement:tag=>new Element(tag),createTextNode:value=>({textContent:value})};
  const sandbox={document,URL,URLSearchParams,Map,Set,atob,btoa,TextDecoder,TextEncoder,crypto:require('node:crypto'),setTimeout,clearTimeout,
    navigator:{clipboard:{writeText:async()=>{}}},location:{href:'https://c0.test/czero/czero17/'+(kind==='index'?'':kind)+search,search,pathname:'/czero/czero17/'+kind,reload(){}},
    history:{replaceState(){}},addEventListener(name,handler){events[name]=handler;},fetch(url,options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));}};
  sandbox.window=sandbox;const context=vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync('app/static/vendor/markdown-it-15.0.2.min.js','utf8'),context);
  vm.runInContext(fs.readFileSync('app/static/site.js','utf8'),context);
  function reader(){const source=fs.readFileSync('app/static/reader.js','utf8').replace('  initialize();',
    'window.readerTest={initialize,home,loadIndex,loadArticle,loadFacts,loadHistory,loadSource,loadVersion,loadVersions,library,guide};');vm.runInContext(source,context);return sandbox.readerTest;}
  return {nodes,requests,events,context,window:sandbox,C:sandbox.C0,node:id=>document.getElementById(id),reader};
}
const tick=()=>new Promise(setImmediate);
const reply=(data,status=200)=>({ok:status>=200 && status<300,status,json:async()=>data});
const id=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const page=(n=1,slug='guides/start')=>({id:id(n),slug,title:'Article '+n,revision:2,updated_at:'2026-10-15T12:00:00Z',content:{number:2,title:'Article '+n,body:'# Getting started\n\nRead **carefully**.',created_at:'2026-10-15T12:00:00Z',metadata:{},content_hash:'hash'}});
function descendants(node){return [node,...(node.children || []).flatMap(descendants)];}
module.exports={fixture,tick,reply,id,page,descendants};
