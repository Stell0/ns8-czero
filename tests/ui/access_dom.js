// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.attributes={};this.value='';this._text='';this.hidden=false;this.disabled=false;this.checked=false;}
  set textContent(value){this._text=String(value);this.children=[];}get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...nodes){for(const n of nodes){if(n.tagName==='#FRAGMENT')this.append(...n.children);else{n.parent=this;this.children.push(n);}}}
  replaceChildren(...nodes){this._text='';this.children=[];this.append(...nodes);}
  get firstChild(){return this.children[0];}
  after(n){const index=this.parent.children.indexOf(this);n.parent=this.parent;this.parent.children.splice(index+1,0,n);}
  remove(){const index=this.parent.children.indexOf(this);this.parent.children.splice(index,1);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  addEventListener(name,fn){this.listeners[name]=fn;}
  focus(){this.focused=true;}
  set innerHTML(_){throw Error('Untrusted HTML');}
}
function setup(script='workspace-access.js'){
  const nodes=new Map(),requests=[];let clear;
  const document={body:{dataset:{page:'admin'}},getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
    createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('#fragment')};
  const window={C0Space:{onClear(fn){clear=fn;}},location:{assign(){}}};
  vm.runInNewContext(fs.readFileSync('app/static/'+script,'utf8'),{document,window,URL,Date,encodeURIComponent,
    fetch(url,options){return new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));}});
  return {nodes,requests,clear:()=>clear(),el:id=>document.getElementById(id)};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=(data,status=200)=>({ok:status>=200 && status<300,status,json:async()=>data});
const descendants=n=>[n,...n.children.flatMap(descendants)];
const action=(row,text)=>descendants(row).find(n=>n.tagName==='BUTTON' && n.textContent===text);
const person=(changes={})=>({id:'person-id',username:'alice',display_name:'<img src=x>',role:'reader',is_owner:false,blocked:false,access_revision:3,permissions:{read:true,write:false,manage:false},...changes});
async function ready(applications=[],changes={}){const h=setup();h.requests[0].resolve(response({username:'owner',role:'admin',csrf_token:'private-fixture'}));await tick();
 h.requests[1].resolve(response({accounts:[person(changes)],pending_count:applications.filter(a=>a.kind==='request').length,has_more:false}));await tick();
 h.requests[2].resolve(response({applications,has_more:false}));await tick();return h;}
module.exports={setup,tick,response,descendants,action,person,ready};
