// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const params=new URLSearchParams(window.location.search), supplied=params.has('space_id');
  const raw=params.get('space_id'), valid=value=>/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value || '');
  const invalid=supplied && (params.getAll('space_id').length!==1 || !valid(raw));
  const identifier=supplied && valid(raw)?raw.toLowerCase():raw;
  const callbacks=new Set();let epoch=0,blocked=invalid,role=null,active=null,entries=[],refreshSequence=0;
  const $=id=>document.getElementById(id), status=message=>{if($('space-status'))$('space-status').textContent=message;};
  function clear(message='Space access changed. Choose a space or refresh access.') {
    ++epoch;blocked=true;active=null;role=null;entries=[];
    if($('site-query'))$('site-query').value='';
    const select=$('space-selector');if(select){select.replaceChildren();const option=document.createElement('option');option.value='unavailable';option.textContent='Unavailable selected space';select.append(option);select.value='unavailable';select.disabled=false;}
    for(const callback of callbacks){try{callback();}catch{/* A missing view cannot retain another private view. */}}
    status(message);
  }
  function apiURL(path) {
    const value=path.startsWith('./api/v1/')?path:'./api/v1/'+path;
    if(!supplied)return value;
    const url=new URL(value,window.location.href), base=new URL('./api/v1/',window.location.href);
    const local=url.pathname.slice(base.pathname.length);
    if(url.origin===base.origin && url.pathname.startsWith(base.pathname) && /^(?:me|wiki|sources|source-versions|documents|chunks|entities|claims|knowledge|objects|object-relations|object-events|references)(?:\/|$)/.test(local))url.searchParams.set('space_id',identifier);
    return url.pathname+url.search+url.hash;
  }
  function pageURL(value) {
    if(!supplied)return value;
    const url=new URL(value,window.location.href), base=new URL('./',window.location.href);
    if(url.origin!==base.origin || !url.pathname.startsWith(base.pathname) ||
       !['','wiki','sources','objects','search','agents','admin'].includes(url.pathname.slice(base.pathname.length)) || url.searchParams.has('space_id'))return value;
    url.searchParams.set('space_id',identifier);return url.pathname+url.search+url.hash;
  }
  async function request(path,options={}) {
    if(blocked)throw new Error('Selected space is unavailable. Choose a space or refresh access.');
    const captured=epoch;let response;
    try{response=await fetch(apiURL(path),{cache:'no-store',...options});}
    catch{throw new Error('Content is unavailable. Try again.');}
    if(captured!==epoch)throw new Error('Space access changed. Refresh to continue.');
    if([401,403].includes(response.status)){clear('Space access is unavailable. Choose a permitted space or sign in again.');refresh();}
    return {ok:response.ok,status:response.status,json:async()=>{
      let value;try{value=await response.json();}catch{throw new Error('Content is unavailable. Try again.');}
      if(captured!==epoch)throw new Error('Space access changed. Refresh to continue.');
      return value;
    }};
  }
  function render() {
    const select=$('space-selector');if(!select)return;
    const permitted=entries,chosen=supplied?entries.find(s=>s.id===identifier):entries.find(s=>s.shared);
    if(!chosen || invalid){clear(invalid?'The space selector is invalid. Choose a permitted space.':'Selected space is unavailable. Choose a permitted space.');entries=permitted;}
    select.replaceChildren();
    for(const entry of entries){const option=document.createElement('option');option.value=entry.id;option.textContent=entry.name+(entry.shared?' (shared)':'');select.append(option);}
    if(chosen && !invalid){select.value=chosen.id;active=chosen;role=chosen.role;status(chosen.shared?'Shared space · '+role:'Protected space · '+role);}
    else{const option=document.createElement('option');option.value='unavailable';option.textContent='Unavailable selected space';select.append(option);select.value='unavailable';}
    select.disabled=false;
  }
  async function refresh() {
    const sequence=++refreshSequence,captured=epoch;let collected=[];
    try{
      for(let offset=0;offset<1000;offset+=100){
        const response=await fetch('./api/v1/spaces?limit=100&offset='+offset,{cache:'no-store'});
        if(!response.ok){if([401,403].includes(response.status))clear('Sign in with a permitted account to choose a space.');throw new Error('Space discovery is unavailable.');}
        const result=await response.json();if(sequence!==refreshSequence || captured!==epoch)return;
        collected.push(...result.spaces);if(result.spaces.length<100)break;
      }
      const next=supplied?collected.find(s=>s.id===identifier):collected.find(s=>s.shared);
      if(active && next && next.role!==role){clear('Your access changed. Reloading this space…');window.location.reload();return;}
      entries=collected;render();
      if(blocked && active && !invalid){window.location.reload();return;}
    }catch{if(sequence===refreshSequence && captured===epoch)status('Space discovery is unavailable. Refresh access to try again.');}
  }
  async function verify() {
    if(!active || blocked || document.hidden)return;
    const captured=epoch,previous=role;
    try{
      const response=await fetch('./api/v1/spaces/'+active.id,{cache:'no-store'});
      if(captured!==epoch)return;
      if([401,403].includes(response.status)){clear('Space access was removed. Choose a permitted space.');refresh();return;}
      if(!response.ok)return;
      const value=await response.json();if(captured!==epoch)return;
      if(value.role!==previous){clear('Your access changed. Reloading this space…');window.location.reload();}
    }catch{/* An outage is not proof of a different grant. */}
  }
  window.C0Space={apiURL,pageURL,request,identifier:supplied?identifier:null,
    generation:()=>epoch,current:value=>!blocked && value===epoch,onClear:callback=>callbacks.add(callback),clear,refresh};
  const select=$('space-selector');
  if(select)select.addEventListener('change',()=>{
    const chosen=entries.find(s=>s.id===select.value);if(!chosen)return;
    const target=new URL(window.location.href);
    for(const key of ['page','revision','source','version','chunk','section','query'])target.searchParams.delete(key);
    if(chosen.shared)target.searchParams.delete('space_id');else target.searchParams.set('space_id',chosen.id);
    clear('Changing space…');window.location.assign(target.href);
  });
  if($('refresh-space'))$('refresh-space').addEventListener('click',()=>{if(blocked && active && !invalid)window.location.reload();else refresh();});
  for(const anchor of document.querySelectorAll('a[href]'))anchor.href=pageURL(anchor.getAttribute('href'));
  for(const form of document.querySelectorAll('form.header-search'))if(supplied){const hidden=document.createElement('input');hidden.type='hidden';hidden.name='space_id';hidden.value=identifier;form.append(hidden);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)verify();});
  if(typeof window.setInterval==='function')window.setInterval(verify,30000);
  refresh();
})();
