// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const $=id=>document.getElementById(id), panel=$('extraction-work');
  if(!panel)return;
  let profile=null,epoch=0,listSequence=0,detailSequence=0,offset=0,unitOffset=0,selected=null,busy=false,pending=null;
  const node=(tag,text)=>{const value=document.createElement(tag);value.textContent=text;return value;};
  const message=text=>{$('extraction-status').textContent=text;};
  function clear(){++epoch;++listSequence;++detailSequence;profile=null;selected=null;pending=null;panel.hidden=true;
    for(const id of ['extraction-list','extraction-units','extraction-summary','extraction-parser','extraction-warning','extraction-status'])$(id).replaceChildren();
    $('extraction-source').removeAttribute('href');$('extraction-detail').hidden=true;
  }
  window.C0Space?.onClear(clear);
  async function api(path,method='GET',body=null){
    const captured=epoch;
    if(profile?.role!=='admin')throw new Error('Only Admins can inspect extraction units.');
    let response;
    try{response=await fetch(window.C0Space?window.C0Space.apiURL(path):'./api/v1/'+path,
      {method,cache:'no-store',headers:body?{'Content-Type':'application/json','X-C0-CSRF':profile.csrf_token}:{},body:body?JSON.stringify(body):null});}
    catch{throw new Error('Cannot update extraction. Refresh to check saved state before retrying.');}
    if(captured!==epoch)throw new Error('Space access changed.');
    if(response.status===404 && path.startsWith('extraction-runs?'))panel.hidden=true;
    if([401,403].includes(response.status)){
      if(window.C0Space?.clear)window.C0Space.clear('Your access changed. Choose a permitted space.');else clear();
      throw new Error('Your access changed. Sign in or choose a permitted space.');
    }
    let value;try{value=await response.json();}catch{throw new Error('Cannot read extraction status. Refresh to try again.');}
    if(captured!==epoch)throw new Error('Space access changed.');
    if(!response.ok)throw new Error(value.detail==='staging_expired'?'Saved results expired. Restart the full extraction.':response.status===409?'Extraction changed. Refresh before trying again.':'Cannot update extraction. Refresh to check its current state.');
    return value;
  }
  async function listing(){
    const sequence=++listSequence,position=offset;
    try{const result=await api('extraction-runs?limit=20&offset='+position);
      if(sequence!==listSequence)return;
      $('extraction-list').replaceChildren();
      for(const run of result.runs){const row=node('li',''),label=node('span',run.id+' · '+run.state+' '),button=node('button','Inspect extraction');button.type='button';
        button.addEventListener('click',()=>{unitOffset=0;detail(run.id);});row.append(label,button);$('extraction-list').append(row);}
      $('extractions-previous').disabled=!position;$('extractions-next').disabled=result.runs.length<20;
      message(result.runs.length?'Extractions loaded.':'No extractions in this space.');
    }catch(error){if(sequence===listSequence)message(error.message);}
  }
  async function detail(id){
    const sequence=++detailSequence;selected=null;$('extraction-detail').hidden=true;
    for(const key of ['retry-extraction','cancel-extraction','restart-extraction'])$(key).disabled=true;
    try{const data=await api('extraction-runs/'+id+'/units?limit=20&offset='+unitOffset);
      if(sequence!==detailSequence)return;selected=data;$('extraction-detail').hidden=false;
      const run=data.run;
      $('extraction-summary').textContent=run.state+' · '+run.succeeded+' of '+run.expected_units+' successful unit attempts · revision '+run.revision;
      $('extraction-parser').textContent='Parser: '+Object.entries(data.parser).map(([key,value])=>key+' '+value).join(' · ');
      $('extraction-warning').textContent=run.error_code==='staging_expired'?'Saved results expired. Full extraction processes every unit again.':run.error_code==='cancelled'?'Extraction cancelled. Successful private results were discarded.':'Cancel discards private results. Retry preserves successful units. Full restart processes every unit again. The previous complete document stays available.';
      $('extraction-source').href=(window.C0Space?.pageURL('./sources?document='+data.source_id) || './sources?document='+data.source_id);
      $('extraction-units').replaceChildren();
      for(const unit of data.units){const range=unit.locator.kind==='page'?' · page '+unit.locator.first:'';
        const next=unit.state==='retry_wait'?' · next retry '+new Date(unit.available_at).toISOString():'';
        $('extraction-units').append(node('li','Unit '+unit.ordinal+range+' · '+unit.state+' · attempts '+unit.attempts+' (total '+unit.lifetime_attempts+')'+(unit.error_code?' · '+unit.error_code:'')+(unit.duration_ms===null?'':' · '+unit.duration_ms+' ms')+next));}
      $('units-previous').disabled=!unitOffset;$('units-next').disabled=data.units.length<20;
      $('retry-extraction').disabled=busy || run.state!=='failed' || run.error_code==='staging_expired';
      $('cancel-extraction').disabled=busy || ['ready','superseded'].includes(run.state);
      $('restart-extraction').disabled=busy || !['failed','superseded'].includes(run.state);
    }catch(error){if(sequence===detailSequence){$('extraction-detail').hidden=true;message(error.message);}}
  }
  async function recover(action){
    if(!selected || busy)return;
    const data=selected,run=data.run,captured=detailSequence;
    busy=true;for(const key of ['retry-extraction','cancel-extraction','restart-extraction'])$(key).disabled=true;
    try{
      const fingerprint=run.id+':'+run.revision+':'+action;
      if(pending?.fingerprint!==fingerprint)pending={fingerprint,key:crypto.randomUUID()};
      const path=action==='restart'?'source-versions/'+run.version_id+'/retry':'extraction-runs/'+run.id+'/'+action;
      const body=action==='restart'?{expected_generation:run.processing_generation}:{expected_revision:run.revision,...(action==='retry'?{idempotency_key:pending.key}:{})};
      await api(path,'POST',body);pending=null;
      if(captured===detailSequence)message(action==='restart'?'Full extraction queued. Refresh the source to follow progress.':'Extraction updated.');
    }catch(error){if(captured===detailSequence)message(error.message);}
    finally{busy=false;if(selected && captured===detailSequence)await detail(run.id);}
  }
  $('refresh-extractions').addEventListener('click',listing);
  for(const [id,delta]of [['extractions-previous',-20],['extractions-next',20]])$(id).addEventListener('click',()=>{offset=Math.max(0,offset+delta);listing();});
  for(const [id,delta]of [['units-previous',-20],['units-next',20]])$(id).addEventListener('click',()=>{if(selected){unitOffset=Math.max(0,unitOffset+delta);detail(selected.run.id);}});
  for(const [id,action]of [['retry-extraction','retry'],['cancel-extraction','cancel'],['restart-extraction','restart']])$(id).addEventListener('click',()=>recover(action));
  window.addEventListener('pagehide',clear);
  (async()=>{const captured=epoch;try{const response=await fetch('./api/v1/me',{cache:'no-store'});if(!response.ok)return;
    const value=await response.json();if(captured!==epoch || value.role!=='admin')return;profile=value;panel.hidden=false;await listing();
  }catch{if(captured===epoch)message('Cannot load extractions. Refresh to try again.');}})();
})();
