// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const el = id => document.getElementById(id);
  if (!el('access-people')) return;
  const capabilities = [['read','Read','c0:read'],['write','Write','c0:write'],['manage','Manage','c0:admin']];
  const labels = {needs_approval:'Needs application approval',needs_permissions:'Needs additional application permissions',
    waiting_for_consent:'Waiting for user consent',connected:'Connected',renewal_required:'Connected · renewal needed',needs_reconnect:'Needs reconnect'};
  const node = (tag, text) => { const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n; };
  const button = (text, action) => {const n=node('button',text);n.type='button';n.addEventListener('click',action);return n;};
  let epoch=0,sequence=0,editSequence=0,profile=null,offset=0,choice=null,confirmation=null,review=null,busy=false,returnFocus=null;
  const allowed=()=>profile?.role==='admin';
  const message=text=>{el('access-message').textContent=text;};
  function closeEditors(restore=false){const target=returnFocus;returnFocus=null;++editSequence;choice=null;confirmation=null;review=null;for(const id of ['access-editor','access-confirm','access-review'])el(id).hidden=true;el('access-review-info').replaceChildren();if(restore && target?.isConnected)target.focus();}
  function clear(text='Access changed. Refresh your account.'){
    ++epoch;++sequence;profile=null;busy=false;closeEditors();el('access-people').replaceChildren();
    el('access-workspace').hidden=true;el('admin-account').textContent=text;el('pending-summary').textContent='';
    el('admin-signin').hidden=false;
    el('access-editor-title').textContent='Change permissions';el('access-review-title').textContent='Review application';
    for(const id of ['access-confirm-title','access-confirm-text','access-page','access-message'])el(id).textContent='';
    el('access-role').value='reader';for(const [key] of capabilities)el('access-approve-'+key).checked=false;
  }
  if(window.C0Space)window.C0Space.onClear(()=>clear());
  async function api(path,method='GET',body=null){
    if(!allowed())throw Error('Application Admin access is required.');
    const captured=epoch,headers=body===null?{}:{'Content-Type':'application/json'};
    if(method!=='GET')headers['X-C0-CSRF']=profile.csrf_token;
    let response;
    try{response=await fetch('./api/v1/'+path,{method,headers,credentials:'same-origin',cache:'no-store',body:body===null?null:JSON.stringify(body)});}
    catch{throw Error('The request was not confirmed. Refresh saved access before retrying.');}
    if(captured!==epoch || !allowed())throw Error('Access changed.');
    if([401,403].includes(response.status)){clear();throw Error('Access changed. Sign in again or ask an administrator.');}
    if(!response.ok){const errors={404:'This item is no longer available. Refresh access.',409:'Access, policy or application approval changed. Refresh and review again.',
      410:'This request expired or was declined. The user can start connecting again.',422:'Check the selected permissions.',503:'The service is unavailable. Refresh before trying again.'};
      throw Error(errors[response.status] || 'The request did not complete. Refresh saved access.');}
    let value;try{value=response.status===204?null:await response.json();}
    catch{throw Error('The response was not confirmed. Refresh saved access before retrying.');}
    if(captured!==epoch || !allowed())throw Error('Access changed.');return value;
  }
  function details(values){const d=node('details'),summary=node('summary','Details');d.append(summary);
    for(const [name,value] of Object.entries(values)){if(value!==null && value!==undefined)d.append(node('p',name+': '+(Array.isArray(value)?value.join(', '):String(value))));}return d;}
  function permissionCells(row,person,item=null){
    for(const [key,title,scope] of capabilities){const cell=node('td');
      if(!item)cell.textContent=person.permissions[key]?'Yes':'No';
      else if(item.kind==='request')cell.append(node('span','Requested: '+(item.scopes.includes(scope)?'Yes':'No')),node('small','Effective: No · awaiting consent'));
      else cell.append(node('span','Consented: '+(item.scopes.includes(scope)?'Yes':'No')),
        node('small','Effective: '+(item.status==='renewal_required' && person.permissions[key] && item.scopes.includes(scope)?'Requires renewal':item.permissions[key]?'Yes · authorized spaces':'No')));
      row.append(cell);
    }
  }
  function openRole(person){
    closeEditors();returnFocus=document.activeElement;choice=person;el('access-editor-title').textContent=(person.blocked?'Unblock user: ':'Change permissions: ')+person.username;
    el('access-role').value=person.role || 'reader';el('access-role-save').textContent=person.blocked?'Unblock user':'Save permissions';
    el('access-editor').hidden=false;el('access-editor-title').focus();
  }
  function confirm(title,text,label,action){closeEditors();returnFocus=document.activeElement;confirmation=action;el('access-confirm-title').textContent=title;
    el('access-confirm-text').textContent=text;el('access-confirm-save').textContent=label;el('access-confirm').hidden=false;el('access-confirm-title').focus();}
  async function mutation(action,success,draftUnchanged=()=>true){
    if(busy || !allowed())return;busy=true;const captured=epoch;
    for(const id of ['access-role-save','access-confirm-save','access-approve-save'])el(id).disabled=true;
    try{await action();if(captured!==epoch)return;if(!draftUnchanged()){message('Earlier selection saved. Your newer selection is preserved. Refresh access before saving it.');return;}closeEditors();await load();if(captured===epoch){message(success);el('access-message').focus();}}
    catch(error){if(captured===epoch)message(error.message);}
    finally{if(captured===epoch){busy=false;for(const id of ['access-role-save','access-confirm-save','access-approve-save'])el(id).disabled=false;}}
  }
  async function openReview(item,person,generation){
    if(busy || generation!==sequence || !allowed())return;
    closeEditors();returnFocus=document.activeElement;const edit=editSequence,captured=epoch;el('access-review').hidden=false;el('access-review-title').textContent='Review application for '+person.username;
    el('access-review-info').append(node('p','Loading verified application information…'));el('access-approve-save').disabled=true;
    try{
      const value=await api('access/requests/'+encodeURIComponent(item.id)+'/preview','POST');
      if(captured!==epoch || edit!==editSequence || generation!==sequence)return;
      review={...value,id:item.id};const old=value.client,info=el('access-review-info');info.replaceChildren();
      info.append(node('h3',value.descriptor.client_name),node('p','Application origin: '+new URL(value.request.metadata_url).origin),
        node('p','Requested: '+capabilities.filter(([, ,scope])=>value.request.scopes.includes(scope)).map(([,title])=>title).join(', ')),
        node('p','Current user permissions: '+capabilities.filter(([key])=>value.request.account.permissions[key]).map(([,title])=>title).join(', ')));
      info.append(node('p',old?.review_required?'This application needs a new review. Its previous connections may already be stopped. Users must consent again after approval.':old?'Updating this application approval disconnects its existing connections for all users. Users must consent again.':'This approves the application; it gives no user additional permissions.'));
      if(value.request.scopes.some(scope=>!value.request.account.permissions[capabilities.find(c=>c[2]===scope)?.[0]]))
        info.append(node('p','Some requested permissions exceed this person’s access. Change permissions separately if appropriate.'));
      info.append(details({'Exact metadata URL':value.request.metadata_url,'Callback':value.request.callback,'Metadata digest':value.metadata_digest}));
      for(const [key,,scope] of capabilities){const field=el('access-approve-'+key),existing=old?.allowed_scopes.includes(scope) || false;
        field.checked=existing || (scope==='c0:read' && value.request.scopes.includes(scope));
        field.disabled=existing || !value.request.scopes.includes(scope) || (value.descriptor.scope_ceiling!==null && !value.descriptor.scope_ceiling.includes(scope));
      }
      el('access-approve-save').disabled=Boolean(old && !old.enabled);
      if(value.descriptor.redirect_uris && !value.descriptor.redirect_uris.includes(value.request.callback)){
        el('access-approve-save').disabled=true;info.append(node('p','This request’s return address is no longer supported. Ask the user to start connecting again.'));
      }
      if(old && value.descriptor.scope_ceiling!==null && old.allowed_scopes.some(scope=>!value.descriptor.scope_ceiling.includes(scope))){
        el('access-approve-save').disabled=true;info.append(node('p','This application changed which permissions it supports. Review its permissions under Advanced.'));
      }
      if(old && !old.enabled)info.append(node('p','This application is disabled. Review it under Advanced before enabling it for everyone.'));
      el('access-review-title').focus();
    }catch(error){if(captured===epoch && edit===editSequence){review=null;el('access-review-info').replaceChildren(node('p',error.message));}}
  }
  function applicationRow(person,item,generation){
    const row=node('tr');row.className='access-application'+(item.kind==='request'?' access-pending':'');row.dataset.accountId=person.id;row.dataset.applicationId=item.id;
    const name=node('td',person.username),origin=item.metadata_url?new URL(item.metadata_url).hostname:'';
    name.append(node('small',item.client_name || 'Application awaiting review'),...(origin?[node('small',origin)]:[]));
    row.append(name,node('td',person.display_name || '—'));permissionCells(row,person,item);
    const status=node('td',labels[item.status] || 'Refresh access');
    if(item.kind==='connection')status.append(node('small',item.persistent?'Background connection':'Session connection'));
    const actions=node('td');
    if(item.kind==='request'){
      if(item.status!=='waiting_for_consent' && !person.blocked && person.role)
        actions.append(button('Approve',()=>{if(!busy)openReview(item,person,generation);}));
      actions.append(button('Decline',()=>{if(generation!==sequence || busy)return;confirm('Decline application request',
        'Cancel this request for '+person.username+'. Existing connections, user permissions and application approval stay in place.',
        'Decline request',()=>api('access/requests/'+encodeURIComponent(item.id),'DELETE'));}));
    }else actions.append(button('Disconnect application connection',()=>{if(generation!==sequence || busy)return;
      confirm('Disconnect application connection','Stop this connection for '+person.username+'. Other connections and user permissions stay in place. The user can connect again.',
        'Disconnect application connection',()=>api('access/connections/'+encodeURIComponent(item.id),'DELETE'));}));
    actions.append(details({'Request or connection ID':item.id,'Application ID':item.client_id,'Metadata URL':item.metadata_url,
      'Callback':item.callback,'OAuth scopes':item.scopes,'Last used':item.last_used_at,'Expires':item.expires_at,'Inactivity deadline':item.idle_until}));
    for(const control of actions.children)if(control.tagName==='BUTTON')control.setAttribute('aria-label',control.textContent+' for '+person.username+' · '+(item.client_name || 'application request'));
    row.append(status,actions);return row;
  }
  function personRows(person,generation){
    const body=document.createDocumentFragment(),row=node('tr');row.className='access-person';row.dataset.accountId=person.id;
    row.append(node('th',person.username),node('td',person.display_name || '—'));row.children[0].scope='row';permissionCells(row,person);
    row.append(node('td',person.is_owner?'Owner':person.blocked?'Blocked':person.role?'Access enabled':'No access'));
    const actions=node('td');
    if(!person.is_owner){actions.append(button(person.blocked?'Unblock user':person.role?'Change permissions':'Grant permissions',()=>{
      if(generation===sequence && !busy)openRole(person);}));
      if(!person.blocked)actions.append(button('Block user',()=>{if(generation!==sequence || busy)return;confirm('Block '+person.username,
        'Block all C0 access and disconnect every application connection for this user. Later sign-ins will remain blocked until an administrator explicitly unblocks the user.',
        'Block user',()=>api('access/accounts/'+encodeURIComponent(person.id),'PUT',{role:null,expected_revision:person.access_revision}));}));}
    actions.append(details({'Account ID':person.id,'Last seen':person.last_seen,'Permission revision':person.access_revision}));
    for(const control of actions.children)if(control.tagName==='BUTTON')control.setAttribute('aria-label',control.textContent+' for '+person.username);
    row.append(actions);body.append(row);
    return body;
  }
  async function loadApplications(person,generation,after,appOffset=0){
    const captured=epoch;
    try{
      const value=await api('access/accounts/'+encodeURIComponent(person.id)+'/applications?offset='+appOffset);
      if(captured!==epoch || generation!==sequence)return;
      let last=after;
      for(const item of value.applications){const row=applicationRow(person,item,generation);last.after(row);last=row;}
      if(value.has_more){const row=node('tr'),cell=node('td');cell.colSpan=7;const more=button('More applications for '+person.username,async()=>{
        if(generation!==sequence || more.disabled)return;more.disabled=true;await loadApplications(person,generation,row,appOffset+value.applications.length);row.remove();});
        cell.append(more);row.append(cell);last.after(row);}
    }catch(error){if(captured===epoch && generation===sequence){const row=node('tr'),cell=node('td',error.message);cell.colSpan=7;row.append(cell);after.after(row);}}
  }
  async function load(){
    const generation=++sequence,captured=epoch;closeEditors();el('access-people').replaceChildren();message('Loading people and application requests…');
    try{
      const value=await api('access/workspace?offset='+offset);
      if(captured!==epoch || generation!==sequence)return;
      const pending=value.pending_count?value.pending_count+' pending application request'+(value.pending_count===1?'':'s')+'. People with pending requests appear first.':'No pending application requests.';
      const setup=value.connections_available===false?' Ask your NethServer administrator to configure the application hostname to connect ChatGPT.':value.discovery_enabled===false?' New application discovery is off. Use Advanced to set up ChatGPT connections.':'';
      el('pending-summary').textContent=pending+setup;
      const loads=[];
      for(const person of value.accounts){const rows=personRows(person,generation),after=rows.firstChild;el('access-people').append(rows);loads.push(loadApplications(person,generation,after));}
      el('access-previous').disabled=offset===0;el('access-next').disabled=!value.has_more;
      el('access-page').textContent=value.accounts.length?'People '+(offset+1)+'–'+(offset+value.accounts.length):'No people to show.';
      await Promise.all(loads);if(captured===epoch && generation===sequence)message('Access checked. Application approval, user permissions and connection access are separate.');
    }catch(error){if(captured===epoch && generation===sequence)message(error.message);}
  }
  el('access-role-form').addEventListener('submit',event=>{event.preventDefault();if(!choice || busy)return;const person=choice,role=el('access-role').value;
    if(!person.blocked && role===person.role){closeEditors(true);message('Permissions are unchanged. Connections stay in place.');return;}
    mutation(()=>api('access/accounts/'+encodeURIComponent(person.id),'PUT',{role,expected_revision:person.access_revision}),'Permissions saved. The user must sign in and consent again.',()=>el('access-role').value===role);});
  el('access-confirm-save').addEventListener('click',()=>{if(confirmation)mutation(confirmation,'Access updated.');});
  el('access-approval-form').addEventListener('submit',event=>{event.preventDefault();if(!review || busy)return;const value=review;
    const scopes=capabilities.filter(([key])=>el('access-approve-'+key).checked).map(([, ,scope])=>scope);
    if(!scopes.length){message('Choose at least one permission.');return;}
    if(value.client && !value.client.review_required && value.client.metadata_digest===value.metadata_digest &&
      JSON.stringify([...scopes].sort())===JSON.stringify([...value.client.allowed_scopes].sort())){
      message('No application permissions changed. Choose additional requested permissions, or cancel.');return;
    }
    mutation(()=>api('access/requests/'+encodeURIComponent(value.id)+'/approve','POST',{metadata_digest:value.metadata_digest,allowed_scopes:scopes,
      client_id:value.client?.client_id || null,expected_revision:value.client?.revision || null}),'Application approved. The user must continue and consent; their permissions have not changed.',()=>JSON.stringify(capabilities.filter(([key])=>el('access-approve-'+key).checked).map(([, ,scope])=>scope))===JSON.stringify(scopes));});
  for(const id of ['access-role-cancel','access-confirm-cancel','access-review-cancel'])el(id).addEventListener('click',()=>{if(!busy)closeEditors(true);});
  el('access-refresh').addEventListener('click',()=>{if(!busy)start();});
  el('access-next').addEventListener('click',()=>{if(!busy){offset+=25;load();}});
  el('access-previous').addEventListener('click',()=>{if(!busy){offset=Math.max(0,offset-25);load();}});
  async function start(){const captured=++epoch;++sequence;profile=null;closeEditors();el('access-people').replaceChildren();el('access-workspace').hidden=true;
    try{const response=await fetch('./api/v1/me',{credentials:'same-origin',cache:'no-store'});if(captured!==epoch)return;
      if(!response.ok){clear('Sign in with a C0 administrator account.');return;}
      const user=await response.json();if(captured!==epoch)return;
      if(user.role!=='admin'){clear('Only C0 administrators can manage workspace access.');return;}
      profile=user;el('admin-account').textContent='Signed in as '+user.username;el('admin-signin').hidden=true;el('access-workspace').hidden=false;await load();
    }catch(_){if(captured===epoch)clear('Workspace access is unavailable. Sign in or try again.');}
  }
  start();
})();
