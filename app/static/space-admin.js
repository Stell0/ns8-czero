// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const $=id=>document.getElementById(id),panel=$('space-administration');if(!panel)return;
  let profile=null,epoch=0,listSequence=0,pendingCreate=null;
  const pendingGrants=new Map(),allowed=()=>profile?.role==='admin';
  const node=(tag,text)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;return item;};
  function clear(){++epoch;++listSequence;profile=null;pendingCreate=null;pendingGrants.clear();panel.hidden=true;$('space-grant-list').replaceChildren();$('managed-space').textContent='';$('space-grant-status').textContent='';$('space-create-status').textContent='';$('space-name').value='';}
  if(window.C0Space)window.C0Space.onClear(clear);
  async function api(path,method='GET',body=null){
    if(!allowed())throw new Error('Application Admin access is required.');
    const captured=epoch,headers=body===null?{}:{'Content-Type':'application/json'};
    if(method!=='GET')headers['X-C0-CSRF']=profile.csrf_token;
    let response;
    try{response=await fetch('./api/v1/'+path,{method,headers,cache:'no-store',body:body===null?null:JSON.stringify(body)});}
    catch{throw new Error('The request did not complete. Retry an unchanged uncertain request to recover its receipt.');}
    if(captured!==epoch || !allowed())throw new Error('Access changed.');
    if([401,403].includes(response.status)){clear();throw new Error('Access changed. Refresh your account.');}
    if(!response.ok)throw new Error(response.status===409?'Saved state changed or this request conflicts. Refresh before saving again.':'The request did not complete. Check access and input, then retry an unchanged uncertain request.');
    let value;try{value=await response.json();}catch{throw new Error('The response is unavailable. Retry an unchanged uncertain request.');}
    if(captured!==epoch || !allowed())throw new Error('Access changed.');return value;
  }
  async function grants(){
    if(!allowed())return;const sequence=++listSequence,captured=epoch,identifier=window.C0Space?.identifier;
    $('space-grant-list').replaceChildren();$('space-grant-status').textContent='';
    if(!identifier){$('managed-space').textContent='Shared space uses application roles. Choose a protected space above to manage its grants.';return;}
    try{
      const selected=await api('spaces/'+identifier);if(sequence!==listSequence || captured!==epoch)return;
      if(selected.shared){$('managed-space').textContent='Shared space uses application roles; its policy is fixed.';return;}
      $('managed-space').textContent='Protected space: '+selected.name;
      let saved=[];
      for(let offset=0;offset<1000;offset+=100){const result=await api('spaces/'+identifier+'/grants?limit=100&offset='+offset);if(sequence!==listSequence || captured!==epoch)return;saved.push(...result.grants);if(result.grants.length<100)break;}
      const accounts=(await api('access/accounts?limit=1000')).accounts;
      if(sequence!==listSequence || captured!==epoch)return;
      const byId=new Map(saved.map(row=>[row.account_id,row]));
      for(const account of accounts){
        const row=node('tr'),label=node('td',account.display_name || account.username),access=node('td'),action=node('td');
        label.append(node('small',account.username));row.append(label,access,action);
        const old=byId.get(account.id);byId.delete(account.id);
        if(account.role==='admin'){access.textContent='Admin: implicit access to every space.';}
        else{
          const select=node('select');select.setAttribute('aria-label','Space access for '+account.username);
          for(const [value,title] of [['','No access'],['reader','Reader'],['editor','Editor']]){const option=node('option',title);option.value=value;option.disabled=(!account.role && value!=='') || (account.role==='reader' && value==='editor');select.append(option);}
          select.value=old?.role || '';access.append(select);
          let revision=old?.revision || 0;
          const save=node('button','Save grant'),status=node('p');save.type='button';status.setAttribute('role','status');
          save.setAttribute('aria-label','Save space access for '+account.username);action.append(save,status);
          save.addEventListener('click',async()=>{
            if(save.disabled || !allowed() || sequence!==listSequence || captured!==epoch)return;
            const chosen=select.value,values={role:chosen || null,expected_revision:revision};
            const fingerprint=JSON.stringify([identifier,account.id,values]);
            if(pendingGrants.get(account.id)?.fingerprint!==fingerprint)pendingGrants.set(account.id,{fingerprint,key:crypto.randomUUID()});
            const attempt=pendingGrants.get(account.id);save.disabled=true;status.textContent='Saving grant…';
            try{
              const result=await api('spaces/'+identifier+'/grants/'+account.id,'PUT',{...values,idempotency_key:attempt.key});
              if(sequence!==listSequence || captured!==epoch)return;
              revision=result.revision;if(pendingGrants.get(account.id)===attempt)pendingGrants.delete(account.id);
              status.textContent=select.value===chosen?'Grant saved. Affected delegated tokens require fresh consent.':'Earlier choice saved. Your newer selection is not saved yet.';
            }catch(error){if(sequence===listSequence && captured===epoch)status.textContent=error.message;}
            finally{if(sequence===listSequence && captured===epoch)save.disabled=false;}
          });
        }
        $('space-grant-list').append(row);
      }
      for(const retained of byId.values()){const row=node('tr');row.append(node('td','Account unavailable'),node('td','Retained grant revision '+retained.revision),node('td','Review application identity configuration.'));$('space-grant-list').append(row);}
      $('space-grant-status').textContent=accounts.length+' verified accounts shown. Grants never exceed current application roles.';
    }catch(error){if(sequence===listSequence && captured===epoch)$('space-grant-status').textContent=error.message;}
  }
  $('refresh-space-grants').addEventListener('click',()=>grants());
  $('space-create-form').addEventListener('submit',async event=>{
    event.preventDefault();if(!allowed() || $('create-space').disabled)return;
    const name=$('space-name').value.trim(),captured=epoch;
    if(!pendingCreate || pendingCreate.name!==name)pendingCreate={name,key:crypto.randomUUID()};
    const attempt=pendingCreate;$('create-space').disabled=true;
    try{
      const result=await api('spaces','POST',{name,idempotency_key:attempt.key});if(captured!==epoch)return;
      pendingCreate=null;const target=new URL('./admin/spaces',document.baseURI || window.location.href);target.searchParams.set('space_id',result.id);
      if(window.C0Space)window.C0Space.clear('Opening the new protected space…');window.location.assign(target.href);
    }catch(error){if(captured===epoch)$('space-create-status').textContent=error.message;}
    finally{if(captured===epoch)$('create-space').disabled=false;}
  });
  (async()=>{
    const captured=epoch;
    try{const response=await fetch('./api/v1/me',{cache:'no-store'});if(!response.ok)return;const current=await response.json();if(captured!==epoch)return;profile=current;if(!allowed())return;panel.hidden=false;await grants();}
    catch{if(captured===epoch)$('space-grant-status').textContent='Space administration is unavailable. Refresh your account.';}
  })();
})();
