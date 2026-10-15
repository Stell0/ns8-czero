// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const C = window.C0, $ = id => document.getElementById(id), kind = document.body.dataset.page;
  if (!C || C.toolsMode || !['index','wiki','sources','agents'].includes(kind)) return;
  const {node,link,button} = C;
  let profile=null, epoch=0, selection=0, article=null, capabilities={}, pages=new Map(), pageOffset=0, indexFlight=false;
  let factsOffset=0, factFlight=false, historyOffset=0, historyFlight=false, source=null, versions=[], versionOffset=0, versionSequence=0, sourceOffset=0, librarySequence=0, pollTimer;
  const openPaths=new Set(), evidence=new Map(), sectionPath=C.params.get('section') || '';
  if(/^[a-z0-9][a-z0-9/-]{0,127}$/.test(sectionPath)){let path='';for(const part of sectionPath.split('/')){path+=(path?'/':'')+part;openPaths.add(path);}}
  const writable=()=>profile && ['editor','admin'].includes(profile.role);
  function status(message) {if($('reader-status'))$('reader-status').textContent=message;}
  function revoke() {
    ++epoch;++selection;++versionSequence;profile=null;article=null;source=null;pages.clear();versions=[];evidence.clear();clearTimeout(pollTimer);
    if($('reader-root'))$('reader-root').hidden=true;
    for(const id of ['reader-tree','reader-content','reader-facts','reader-evidence','reader-related','reader-history','article-task','reader-document','reader-excerpt','reader-source-metadata','home-recent','home-sections','reader-sources','guide-tasks'])if($(id))$(id).replaceChildren();
    if($('article-update-task'))$('article-update-task').hidden=true;
    const account=$({wiki:'wiki-account',sources:'sources-account',agents:'guide-status',index:'reader-status'}[kind]);
    if(account)account.textContent='Sign in with a permitted account to continue.';
    const signIn=$({wiki:'wiki-signin',sources:'sources-signin',agents:'guide-signin',index:'sign-in'}[kind]);if(signIn)signIn.hidden=false;
  }
  async function read(path) {
    const captured=epoch;
    let response;
    try{response=await fetch('./api/v1/'+path,{cache:'no-store'});}
    catch{throw new Error('Content is unavailable. Try again.');}
    if([401,403].includes(response.status)){revoke();throw new Error('Sign-in or permitted access is required.');}
    if(!response.ok)throw new Error(response.status===404?'This item is no longer available.':'Content is unavailable. Try again.');
    let value;try{value=await response.json();}catch{throw new Error('Content is unavailable. Try again.');}
    if(captured!==epoch)throw new Error('Access changed. Refresh to continue.');return value;
  }
  function showRoot() {if($('reader-root'))$('reader-root').hidden=false;}
  function details(label,value) {const detail=node('details');detail.append(node('summary',label),node('pre',JSON.stringify(value,null,2)));return detail;}
  function tree() {
    if(!$('reader-tree'))return;
    C.tree($('reader-tree'),[...pages.values()],article?.id,openPaths);
    $('tree-status').textContent=pages.size ? 'Browse the loaded articles, or search the full collection.' : 'No articles yet.';
    related();
  }
  function related() {
    if(!article || !$('reader-related'))return;
    const section=article.slug.includes('/')?article.slug.slice(0,article.slug.lastIndexOf('/')):'';
    const items=[...pages.values()].filter(p=>p.id!==article.id && (p.slug.includes('/')?p.slug.slice(0,p.slug.lastIndexOf('/')):'')===section).sort((a,b)=>a.title.localeCompare(b.title)).slice(0,8);
    $('reader-related').replaceChildren();for(const page of items){const li=node('li');li.append(link(page.title,C.pageURL(page.id)));$('reader-related').append(li);}
    $('reader-related-panel').hidden=!items.length;
  }
  async function loadIndex() {
    if(indexFlight)return;
    indexFlight=true;$('tree-more').disabled=true;const captured=epoch,start=pageOffset;
    try {
      const result=await read('wiki/pages?limit=100&offset='+start);if(captured!==epoch)return;
      for(const page of result.pages)pages.set(page.id,page);
      pageOffset=start+result.pages.length;tree();$('tree-more').hidden=result.pages.length<100;
      if(!article && !C.params.has('page')) {
        const list=node('ul','', 'recent-list');
        const matching=[...pages.values()].filter(page=>!sectionPath || page.slug===sectionPath || page.slug.startsWith(sectionPath+'/'));
        if(sectionPath)$('page-title').textContent=sectionPath.split('/').pop().replace(/-/g,' ');
        for(const page of matching.slice(0,50)){const li=node('li');li.append(link(page.title,C.pageURL(page.id)),node('span','Updated '+C.date(page.updated_at),'byline'));list.append(li);}
        $('reader-content').replaceChildren(node('p',sectionPath?(matching.length?'Articles in this section. Load more navigation to discover older articles.':'No articles in this section have loaded yet. Load more articles or search the full collection.'):(pages.size?'Choose an article from the tree, or search the full knowledge collection.':'No articles yet. Use the AI connection guide to begin building your knowledge.')),list);
      }
    } catch(error){if(captured===epoch)$('tree-status').textContent=error.message;}
    finally{indexFlight=false;$('tree-more').disabled=false;}
  }
  function breadcrumbs(page) {
    const target=$('reader-breadcrumbs');target.replaceChildren(link('Knowledge','./wiki'));
    const parts=page.slug.split('/');let prefix='';
    for(const part of parts.slice(0,-1)) {
      prefix+=(prefix?'/':'')+part;const parent=[...pages.values()].find(p=>p.slug===prefix);
      target.append(node('span','/'),parent?link(parent.title,C.pageURL(parent.id)):node('span',part.replace(/-/g,' ')));
    }
  }
  async function loadArticle(id,revision) {
    if(!C.uuid(id) || (revision && !/^[1-9][0-9]{0,9}$/.test(revision))){status('This article link is invalid.');return;}
    const captured=++selection;article=null;historyOffset=0;factsOffset=0;evidence.clear();
    for(const key of ['reader-content','reader-facts','reader-evidence','reader-history','article-task','reader-toc','reader-related'])$(key).replaceChildren();
    for(const key of ['reader-facts-panel','reader-evidence-panel','reader-actions','reader-history-panel','reader-technical-panel','reader-notice','reader-toc-panel','reader-related-panel'])$(key).hidden=true;
    $('page-title').textContent='Loading article…';status('Loading article…');
    try {
      const page=await read('wiki/pages/'+id+(revision?'?revision='+revision:''));if(captured!==selection)return;
      article=page;pages.set(page.id,page);tree();breadcrumbs(page);
      const displayed=page.content.number, historical=displayed!==page.revision;
      $('page-title').textContent=page.content.title;
      $('reader-updated').textContent='Updated '+C.date(page.content.created_at)+(historical?' · revision '+displayed:'');
      C.markdown($('reader-content'),page.content.body,$('reader-toc'));$('reader-toc-panel').hidden=!$('reader-toc').children.length;
      $('reader-actions').hidden=false;$('article-update-task').hidden=!writable() || page.deleted;
      $('reader-history-panel').hidden=false;$('reader-history-panel').open=false;
      $('reader-technical-panel').hidden=false;$('reader-technical').textContent=JSON.stringify({id:page.id,slug:page.slug,revision:displayed,content_hash:page.content.content_hash,metadata:page.content.metadata},null,2);
      for(const [key,format] of [['reader-export','markdown'],['reader-json','json']])$(key).href='./api/v1/wiki/pages/'+page.id+'/export?'+new URLSearchParams({format,revision:displayed});
      if(historical || page.deleted) {
        $('reader-notice').hidden=false;$('reader-notice').replaceChildren(node('span',page.deleted?'This article is archived. Historical content remains available. ':'You are reading revision '+displayed+'. Linked facts for the current article are omitted. '),link('Open latest revision',C.pageURL(page.id)));
      }
      status('');if(!historical)await loadFacts();
    } catch(error){if(captured===selection){$('page-title').textContent='Article unavailable';status(error.message);}}
  }
  async function loadFacts() {
    if(!article || factFlight)return;
    const captured=selection,page=article,start=factsOffset;factFlight=true;$('facts-more').disabled=true;
    try {
      const result=await read('claims?'+new URLSearchParams({page_id:page.id,limit:5,offset:start}));if(captured!==selection)return;
      $('reader-facts-panel').hidden=!result.claims.length && start===0;
      $('facts-more').hidden=result.claims.length<5;factsOffset=start+result.claims.length;
      await Promise.all(result.claims.map(async claim=>{
        if(captured!==selection)return;
        const fact=node('div',undefined,'fact');fact.append(node('h3',claim.predicate.replace(/[-_]/g,' ')));C.values(fact,claim.value);
        const marker=node('span','Loading evidence…','muted');fact.append(marker);$('reader-facts').append(fact);
        try {
          const full=await read('claims/'+claim.id);if(captured!==selection)return;
          marker.textContent='';
          const citations=node('ul');
          for(const citation of full.evidence || []){
            const li=node('li');li.append(link(citation.title+' · v'+citation.version,C.sourceURL(citation)));citations.append(li);
            evidence.set(citation.source_id+':'+citation.version_id,citation);
          }
          if(citations.children.length){const panel=node('details');panel.append(node('summary','Evidence'),citations);fact.append(panel);}
          $('reader-evidence').replaceChildren();for(const citation of evidence.values()){const li=node('li');li.append(link(citation.title+' · v'+citation.version,C.sourceURL(citation)));$('reader-evidence').append(li);}
          $('reader-evidence-panel').hidden=!evidence.size;
        } catch {if(captured===selection)marker.textContent='Evidence is unavailable. Try again later.';}
      }));
      if(captured===selection)$('facts-status').textContent='';
    } catch(error){if(captured===selection){$('reader-facts-panel').hidden=false;$('facts-status').textContent=error.message;}}
    finally{factFlight=false;$('facts-more').disabled=false;}
  }
  async function loadHistory() {
    if(!article || historyFlight)return;
    const captured=selection,id=article.id,start=historyOffset;historyFlight=true;$('history-more').disabled=true;
    try {
      const result=await read('wiki/pages/'+id+'/revisions?limit=20&offset='+start);if(captured!==selection)return;
      for(const revision of result.revisions){const li=node('li');li.append(link('Revision '+revision.number+' · '+C.date(revision.created_at),C.pageURL(id,revision.number)));$('reader-history').append(li);}
      historyOffset=start+result.revisions.length;$('history-more').hidden=result.revisions.length<20;$('history-status').textContent='';
    } catch(error){if(captured===selection)$('history-status').textContent=error.message;}
    finally{historyFlight=false;$('history-more').disabled=false;}
  }
  async function home() {
    const result=await read('wiki/pages?limit=100');showRoot();
    const groups=new Map();for(const page of result.pages){const section=page.slug.split('/')[0];if(!groups.has(section))groups.set(section,{title:section.replace(/-/g,' '),path:section});if(page.slug===section)groups.set(section,{title:page.title,path:section,id:page.id});}
    for(const entry of [...groups.values()].slice(0,8))$('home-sections').append(link(entry.title,entry.id?C.pageURL(entry.id):'./wiki?'+new URLSearchParams({section:entry.path})));
    for(const item of $('home-sections').children)item.className='section-link';
    for(const page of result.pages.slice(0,8)){const li=node('li');li.append(link(page.title,C.pageURL(page.id)),node('span','Updated '+C.date(page.updated_at),'byline'));$('home-recent').append(li);}
    $('home-sections-note').textContent=result.pages.length===100?'Find more sections in Browse knowledge.':'';
    if(!result.pages.length)status('No articles yet. Connect an external AI assistant to start building the knowledge collection.');
  }
  async function library() {
    const request=++librarySequence,start=sourceOffset;
    $('reader-sources-previous').disabled=true;$('reader-sources-next').disabled=true;
    try {
      const result=await read('sources?limit=50&offset='+start);if(request!==librarySequence)return;
      $('reader-sources').replaceChildren();for(const item of result.sources){const li=node('li');li.append(link(item.title,C.sourceURL({source_id:item.id})),node('span','Updated '+C.date(item.updated_at),'byline'));$('reader-sources').append(li);}
      $('reader-sources-previous').disabled=!start;$('reader-sources-next').disabled=result.sources.length<50;
      $('library-status').textContent=result.sources.length?'Sources '+(start+1)+'–'+(start+result.sources.length):'No sources on this page.';
    }catch(error){if(request===librarySequence)$('library-status').textContent=error.message;}
  }
  function versionOptions(chosen) {
    $('reader-version').replaceChildren();for(const item of versions){const option=node('option','Version '+item.number+' · '+C.date(item.created_at)+' · '+item.state);option.value=item.id;$('reader-version').append(option);}
    $('reader-version').value=chosen || '';$('reader-version').hidden=!versions.length;$('reader-version-label').hidden=!versions.length;
    $('reader-versions-more').hidden=versionOffset%100!==0 || !versionOffset;
  }
  async function loadVersions() {
    if(!source)return;const captured=selection,id=source.id,start=versionOffset;
    $('reader-versions-more').disabled=true;
    try {
      const result=await read('sources/'+id+'/versions?limit=100&offset='+start);if(captured!==selection)return;
      for(const version of result.versions)if(!versions.some(v=>v.id===version.id))versions.push(version);
      versionOffset=start+result.versions.length;
      const requested=C.params.get('version'), chosen=$('reader-version').value || (versions.some(v=>v.id===requested)?requested:'');
      versionOptions(chosen);if(chosen && requested===chosen)await loadVersion(chosen,C.params.get('chunk'));
      $('reader-versions-more').hidden=result.versions.length<100;
    }catch(error){if(captured===selection)status(error.message);}
    finally{$('reader-versions-more').disabled=false;}
  }
  async function loadSource(id,requested,chunk) {
    if(!C.uuid(id) || (requested && !C.uuid(requested)) || (chunk && !C.uuid(chunk))){status('This source link is invalid.');return;}
    const captured=++selection;++versionSequence;clearTimeout(pollTimer);source=null;versions=[];versionOffset=0;
    $('reader-document').replaceChildren();$('reader-excerpt').hidden=true;$('reader-download').replaceChildren();$('reader-source-details').hidden=true;
    $('reader-source-title').textContent='Loading source…';$('reader-source-notice').hidden=true;status('Loading source…');
    try {
      const [item,history]=await Promise.all([read('sources/'+id),read('sources/'+id+'/versions?limit=100')]);if(captured!==selection)return;
      source=item;versions=history.versions;versionOffset=versions.length;
      $('reader-source-title').textContent=item.title;$('reader-source-description').textContent='Updated '+C.date(item.updated_at)+(item.deleted?' · archived':'');
      $('reader-source-details').hidden=false;$('reader-source-metadata').textContent=JSON.stringify(item.metadata,null,2);
      const chosen=requested || versions.find(v=>v.state==='ready')?.id || versions[0]?.id;
      versionOptions(chosen);
      if(chosen)await loadVersion(chosen,chunk);else status('This source has no document versions.');
    }catch(error){if(captured===selection){$('reader-source-title').textContent='Source unavailable';status(error.message);}}
  }
  async function loadVersion(id,chunk) {
    if(!source)return;const captured=selection,request=++versionSequence,item=source;clearTimeout(pollTimer);
    $('reader-document').replaceChildren();$('reader-excerpt').replaceChildren();$('reader-excerpt').hidden=true;$('reader-download').replaceChildren();status('Loading document…');
    let version=versions.find(v=>v.id===id);
    // A deep link may target an immutable version outside the initial history window.
    if(!version){status('This version is outside the loaded history. Load more versions to select it.');$('reader-versions-more').hidden=false;return;}
    $('reader-source-notice').hidden=false;
    $('reader-source-notice').textContent=(version.id!==versions[0]?.id?'Reading an earlier version. ':'')+(version.state==='queued'?'This version is being processed.':version.state==='failed'?'Extraction failed. The original may be available below.':'');
    $('reader-source-notice').hidden=!$('reader-source-notice').textContent;
    if(version.original_present && (version.retain_original || version.state==='failed'))$('reader-download').append(link('Download original','./api/v1/source-versions/'+id+'/original'));
    if(version.state!=='ready'){
      status(version.state==='failed'?'The document could not be extracted. An Editor can inspect it in Tools.':'Processing document. This page will check again shortly.');
      if(version.state==='queued')pollTimer=setTimeout(()=>{if(captured===selection && request===versionSequence)loadSource(item.id,id,chunk);},4000);
      return;
    }
    try {
      const doc=await read('source-versions/'+id+'/document');if(captured!==selection || request!==versionSequence)return;
      $('reader-document').textContent=doc.body;status('');
      $('reader-source-metadata').textContent=JSON.stringify({provenance:item.metadata,version:version.number,filename:version.filename,media_type:version.media_type,text_hash:doc.text_hash,source_hash:version.content_hash,document_id:doc.id},null,2);
      if(chunk){const citation=await read('chunks/'+chunk+'/citation');if(captured!==selection || request!==versionSequence)return;
        if(citation.document_id!==doc.id || citation.source_id!==item.id || citation.version_id!==id){status('The citation does not belong to this document version.');return;}
        $('reader-excerpt').replaceChildren(node('strong','Cited passage · version '+citation.version),node('p',citation.body));$('reader-excerpt').hidden=false;
      }
    }catch(error){if(captured===selection && request===versionSequence)status(error.message);}
  }
  async function guide() {
    const response=await fetch('./agents/capabilities.json',{cache:'no-store'});if(!response.ok)throw new Error('Connection details are unavailable.');
    try{capabilities=await response.json();}catch{throw new Error('Connection details are unavailable.');}
    $('guide-connection-status').textContent=capabilities.interfaces.mcp?'MCP is available. Connect a compatible external assistant using the server URL below.':'MCP is unavailable until NS8 sign-in and hostname-root routing are configured.';
    if(capabilities.mcp_url){$('agent-mcp-url').value=capabilities.mcp_url;$('guide-mcp').hidden=false;}
    if(!capabilities.authenticated){$('guide-status').textContent='Sign in to see instructions for your current permissions.';$('guide-signin').hidden=false;return;}
    profile={role:capabilities.role};$('guide-status').textContent='Your current access: '+capabilities.role+'.';
    const choices=[['read','Read and research']];if(writable())choices.push(['create','Create an article'],['update','Update knowledge'],['ingest','Import a document']);
    $('guide-tasks').replaceChildren();for(const [kind,title]of choices){const panel=node('details');panel.append(node('summary',title));const body=node('div');C.copyPanel(body,C.task(kind,null,capabilities));panel.append(body);$('guide-tasks').append(panel);}
  }
  async function initialize() {
    try {
      if(kind==='agents'){await guide();return;}
      profile=await read('me');
      const account=$({wiki:'wiki-account',sources:'sources-account'}[kind]);if(account)account.textContent='Signed in as '+profile.username;
      const signIn=$({wiki:'wiki-signin',sources:'sources-signin'}[kind]);if(signIn)signIn.hidden=true;
      showRoot();
      if(kind==='index'){if(C.params.get('view')!=='account')await home();else{$('reader-root').hidden=true;$('page-title').textContent='Account and shared access';}return;}
      if(kind==='wiki') {
        if(sectionPath && (!/^[a-z0-9][a-z0-9/-]{0,127}$/.test(sectionPath) || sectionPath.includes('//') || sectionPath.endsWith('/'))){status('This section link is invalid.');return;}
        $('tree-more').addEventListener('click',loadIndex);$('facts-more').addEventListener('click',loadFacts);$('history-more').addEventListener('click',loadHistory);
        $('reader-history-panel').addEventListener('toggle',()=>{if($('reader-history-panel').open && historyOffset===0)loadHistory();});
        for(const [id,kind] of [['article-read-task','read'],['article-update-task','update']])$(id).addEventListener('click',()=>{if(article && (kind==='read'||writable()))C.copyPanel($('article-task'),C.task(kind,article,capabilities));});
        const jobs=[loadIndex()];if(C.params.has('page'))jobs.push(loadArticle(C.params.get('page'),C.params.get('revision')));
        await Promise.all(jobs);return;
      }
      if(kind==='sources') {
        $('reader-version').addEventListener('change',()=>{const id=$('reader-version').value;window.history.replaceState(null,'',C.sourceURL({source_id:source.id,version_id:id}));loadVersion(id);});
        $('reader-versions-more').addEventListener('click',loadVersions);
        for(const [id,delta]of [['reader-sources-previous',-50],['reader-sources-next',50]])$(id).addEventListener('click',()=>{sourceOffset=Math.max(0,sourceOffset+delta);library();});
        const jobs=[library()];if(C.params.has('source'))jobs.push(loadSource(C.params.get('source'),C.params.get('version'),C.params.get('chunk')));await Promise.all(jobs);
      }
    }catch(error){status(error.message);if(kind==='agents')$('guide-status').textContent=error.message;}
  }
  window.addEventListener('pagehide',()=>{++epoch;++selection;clearTimeout(pollTimer);});
  window.addEventListener('pageshow',event=>{if(event.persisted)window.location.reload();});
  initialize();
})();
