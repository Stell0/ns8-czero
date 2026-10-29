// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
(() => {
  const C = window.C0, $ = id => document.getElementById(id), kind = document.body.dataset.page;
  if (!C || C.toolsMode || !['index','wiki','sources','agents'].includes(kind)) return;
  const {node,link,button} = C;
  let profile=null, epoch=0, selection=0, article=null, capabilities={}, pages=new Map(), pageOffset=0, indexFlight=false;
  let factsOffset=0, factFlight=false, source=null, versions=[], versionOffset=0, versionSequence=0, sourceOffset=0, librarySequence=0, pollTimer, logical=null;
  const openPaths=new Set(), evidence=new Map(), sectionPath=C.params.get('section') || '';
  if(/^[a-z0-9][a-z0-9/-]{0,127}$/.test(sectionPath)){let path='';for(const part of sectionPath.split('/')){path+=(path?'/':'')+part;openPaths.add(path);}}
  const writable=()=>profile && ['editor','admin'].includes(profile.role);
  function status(message) {if($('reader-status'))$('reader-status').textContent=message;}
  function revoke() {
    document.title='C0 — Knowledge';status('Sign-in or permitted access is required.');
    C.stopMarkdown();logical=null;
    ++epoch;++selection;++versionSequence;profile=null;article=null;source=null;pages.clear();versions=[];evidence.clear();clearTimeout(pollTimer);
    if($('reader-root'))$('reader-root').hidden=true;
    for(const id of ['tree-status','facts-status','library-status','reader-tree','reader-toc','reader-content','reader-facts','reader-evidence','reader-related','article-task','reader-document','reader-document-toc','reader-provenance','reader-document-version','reader-excerpt','reader-source-metadata','home-recent','home-sections','reader-sources','guide-tasks','guide-rules','guide-workflows','reader-breadcrumbs','reader-technical','reader-updated','reader-notice','reader-source-title','reader-source-description','reader-download','reader-source-notice'])if($(id))$(id).replaceChildren();
    if($('page-title'))$('page-title').textContent={index:'A place to find what we know.',wiki:'Knowledge',sources:'Sources',agents:'Use C0 with ChatGPT'}[kind];
    for(const id of ['reader-export','reader-json'])if($(id)){$(id).removeAttribute('href');$(id).hidden=true;}
    if($('article-update-task'))$('article-update-task').hidden=true;
    const account=$({wiki:'wiki-account',sources:'sources-account',agents:'guide-status',index:'reader-status'}[kind]);
    if(account)account.textContent='Sign in with a permitted account to continue.';
    const signIn=$({wiki:'wiki-signin',sources:'sources-signin',agents:'guide-signin',index:'sign-in'}[kind]);if(signIn)signIn.hidden=false;
  }
  async function read(path) {
    const captured=epoch;
    let response;
    try{response=await (window.C0Space?window.C0Space.request(path):fetch('./api/v1/'+path,{cache:'no-store'}));}
    catch{throw new Error('Content is unavailable. Try again.');}
    if([401,403].includes(response.status)){revoke();throw new Error('Sign-in or permitted access is required.');}
    if(!response.ok)throw new Error(response.status===410?'This exact evidence has been superseded and is unavailable.':response.status===404?'This item is no longer available.':'Content is unavailable. Try again.');
    let value;try{value=await response.json();}catch{throw new Error('Content is unavailable. Try again.');}
    if(captured!==epoch)throw new Error('Access changed. Refresh to continue.');return value;
  }
  if(window.C0Space)window.C0Space.onClear(revoke);
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
    const captured=++selection;article=null;factsOffset=0;evidence.clear();
    for(const key of ['reader-content','reader-facts','reader-evidence','article-task','reader-toc','reader-related'])$(key).replaceChildren();
    for(const key of ['reader-facts-panel','reader-evidence-panel','reader-actions','reader-technical-panel','reader-notice','reader-toc-panel','reader-related-panel'])$(key).hidden=true;
    $('page-title').textContent='Loading article…';status('Loading article…');
    try {
      const page=await read('wiki/pages/'+id+(revision?'?revision='+revision:''));if(captured!==selection)return;
      article=page;pages.set(page.id,page);tree();breadcrumbs(page);
      const displayed=page.content.number;
      $('page-title').textContent=page.content.title;document.title=page.content.title+' · C0';
      $('reader-updated').textContent='Updated '+C.date(page.content.created_at);
      C.markdown($('reader-content'),page.content.body,$('reader-toc'));$('reader-toc-panel').hidden=!$('reader-toc').children.length;
      $('reader-actions').hidden=false;$('article-update-task').hidden=!writable() || page.deleted;
      $('reader-technical-panel').hidden=false;$('reader-technical').textContent=JSON.stringify({id:page.id,slug:page.slug,revision:displayed,content_hash:page.content.content_hash,metadata:page.content.metadata},null,2);
      for(const [key,format] of [['reader-export','markdown'],['reader-json','json']])$(key).href=window.C0Space?window.C0Space.apiURL('wiki/pages/'+page.id+'/export?'+new URLSearchParams({format,revision:displayed})):'./api/v1/wiki/pages/'+page.id+'/export?'+new URLSearchParams({format,revision:displayed});
      if(page.deleted) {
        $('reader-notice').hidden=false;$('reader-notice').textContent='This article is archived. Its current content remains available.';
      }
      status('');await loadFacts();
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
            if(citation.status==='superseded'){citations.append(node('li','Exact evidence has been superseded and is unavailable. This fact needs verification.'));continue;}
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
      const result=await read('source-documents?limit=50&offset='+start);if(request!==librarySequence)return;
      C.sourceTree($('reader-sources'),result.documents);
      $('reader-sources-previous').disabled=!start;$('reader-sources-next').disabled=result.documents.length<50;
      $('library-status').textContent=result.documents.length?'Sources '+(start+1)+'–'+(start+result.documents.length)+'. Navigation shows this page only; use Next for more sources.':'No sources on this page.';
    }catch(error){if(request===librarySequence)$('library-status').textContent=error.message;}
  }
  async function loadSource(id,requested,chunk) {
    if(!requested){await loadLogical(id,null,chunk);return;}
    const captured=++selection,request=++versionSequence;
    C.stopMarkdown();clearTimeout(pollTimer);
    for(const key of ['reader-document','reader-document-toc','reader-excerpt','reader-download','reader-provenance','reader-source-metadata'])$(key).replaceChildren();
    $('reader-excerpt').hidden=true;$('reader-document-toc-panel').hidden=true;
    try{const doc=await read('source-versions/'+requested+'/full-document');
      if(captured!==selection || request!==versionSequence)return;
      await displayLogical(doc,chunk,captured,request);
    }catch(error){if(captured===selection && request===versionSequence){
      $('reader-document').replaceChildren();$('reader-document-toc').replaceChildren();
      $('reader-source-title').textContent='Evidence unavailable';status(error.message);
      $('reader-source-notice').hidden=false;$('reader-source-notice').replaceChildren(link('Open current document',C.documentURL(id)));
    }}
  }
  function citationDetails(citation) {
    const target=$('reader-source-metadata'),details=JSON.parse(target.textContent);
    details.citation=citation;target.textContent=JSON.stringify(details,null,2);
  }
  function sourceBase(metadata) {const saved=metadata.snapshot_provenance || metadata;return C.safeURL(saved.canonical_url || metadata.canonical_url || saved.original_url || metadata.original_url);}
  function provenance(metadata,media,number,updated,state) {
    const target=$('reader-provenance');target.replaceChildren();
    const format=({'text/markdown':'Markdown','text/plain':'Plain text','application/pdf':'PDF'})[media] || 'DOCX';
    target.append(node('p','Imported source · '+format+' · '+state));
    const saved=metadata.snapshot_provenance || metadata;let p=metadata.provenance || {};
    try{const details=JSON.parse(saved.details || 'null');if(details && typeof details==='object' && !Array.isArray(details))p=details;}
    catch{/* Older sources can have no structured snapshot details. */}
    const fields=[['Product',p.product || metadata.product],['Product version',p.product_version || p.version || metadata.product_version || metadata.version],['Path',Array.isArray(p.path)?p.path.filter(value=>typeof value==='string').join(' / '):p.path || p.relative_path || metadata.path]];
    for(const [label,value] of fields)if(typeof value==='string' || typeof value==='number')target.append(node('p',label+': '+String(value).slice(0,2048)));
    for(const [label,key] of [['Retrieved','retrieved_at'],['Published','published_at']])if(saved[key] && C.date(saved[key]))target.append(node('p',label+' '+C.date(saved[key]),'byline'));
    for(const key of ['canonical_url','original_url']){const href=C.safeURL(saved[key] || metadata[key]);if(href){const a=link(key==='canonical_url'?'Canonical document':'Original source',href);a.rel='noopener noreferrer';a.referrerPolicy='no-referrer';target.append(a);}}
    $('reader-document-version').textContent=(number?'Version '+number:'Document snapshot')+' · Updated '+C.date(updated)+' · '+state;
    if(!['text/plain','text/markdown'].includes(media))target.append(node('p','Extracted text; the original page layout is not reproduced.','muted'));
  }
  async function displayLogical(doc,chunk,captured,request) {
    if(captured!==selection || request!==versionSequence)return;
    logical=doc.id;
    $('reader-source-title').textContent=doc.title;document.title=doc.title+' · Source · C0';
    $('reader-source-description').textContent='Imported source'+(doc.deleted?' · Archived':'');
    $('reader-source-details').hidden=false;
    provenance(doc.metadata,doc.media_type,doc.number,doc.updated_at,doc.state);
    $('reader-source-metadata').textContent=JSON.stringify({logical_document_id:doc.id,revision_id:doc.revision_id,content_hash:doc.content_hash,text_hash:doc.text_hash,provenance:doc.metadata,parts:doc.parts},null,2);
    $('reader-source-notice').hidden=false;
    $('reader-source-notice').textContent=doc.state==='ready'?'Rendering the complete source document…':'This document is '+doc.state+'. A complete verified body is not available.';
    $('reader-download').replaceChildren();
    for(const id of doc.original_version_ids || [])if(C.uuid(id))$('reader-download').append(link('Download retained original','./api/v1/source-versions/'+id+'/original'));
    if(captured!==selection || request!==versionSequence)return;
    if(doc.state!=='ready' || typeof doc.body!=='string'){status('Complete document unavailable: '+doc.state+'.');
      if(doc.state==='queued' || doc.state==='incomplete')pollTimer=setTimeout(()=>{if(captured===selection && request===versionSequence)loadLogical(doc.id,doc.revision_id,chunk);},4000);return;}
    const current=()=>captured===selection && request===versionSequence;
    $('reader-document').className=doc.media_type==='text/markdown'?'article-body source-document':'document-body';
    if(doc.media_type==='text/markdown'){if(!await C.fullMarkdown($('reader-document'),doc.body,$('reader-document-toc'),current,sourceBase(doc.metadata)))return;}
    else $('reader-document').textContent=doc.body;
    $('reader-document-toc-panel').hidden=!$('reader-document-toc').children.length;
    $('reader-source-notice').textContent=doc.deleted?'Archived current source document.':'Complete current source document.';
    status('Complete document loaded.');
    if(chunk){
      const citation=await read('chunks/'+chunk+'/citation');if(!current())return;
      const part=doc.parts.find(part=>part.source_id===citation.source_id && part.version_id===citation.version_id && part.document_id===citation.document_id);
      if(!part){status('The citation does not belong to this document snapshot.');return;}
      citationDetails(citation);
      $('reader-excerpt').replaceChildren(node('strong','Cited passage · version '+citation.version),node('p',citation.body));
      $('reader-excerpt').hidden=false;$('reader-excerpt').setAttribute('tabindex','-1');
      $('reader-excerpt').focus();$('reader-excerpt').scrollIntoView?.({block:'start'});
    }
  }
  async function loadLogical(id,revision,chunk) {
    if(!C.uuid(id) || (revision && !C.uuid(revision)) || (chunk && !C.uuid(chunk))){status('This document link is invalid.');return;}
    const captured=++selection,request=++versionSequence;C.stopMarkdown();clearTimeout(pollTimer);logical=null;source=null;versions=[];
    for(const key of ['reader-document','reader-document-toc','reader-excerpt','reader-download','reader-provenance','reader-source-metadata','reader-document-version','reader-source-notice','reader-source-description'])$(key).replaceChildren();
    $('reader-document-toc-panel').hidden=true;$('reader-excerpt').hidden=true;$('reader-source-details').hidden=true;$('reader-source-title').textContent='Loading source…';status('Loading document…');
    try{const doc=await read('source-documents/'+id+(revision?'?revision_id='+revision:''));if(captured!==selection || request!==versionSequence)return;await displayLogical(doc,chunk,captured,request);}
    catch(error){if(captured===selection && request===versionSequence){$('reader-document').replaceChildren();$('reader-document-toc').replaceChildren();$('reader-document-toc-panel').hidden=true;$('reader-source-title').textContent='Source unavailable';$('reader-source-notice').textContent='The complete document could not be displayed. Try again.';status(error.message);}}
  }
  async function guide() {
    const captured=epoch;
    const response=await fetch('./agents/capabilities.json',{cache:'no-store'});if(captured!==epoch)return;if([401,403].includes(response.status)){revoke();throw new Error('Sign-in or permitted access is required.');}if(!response.ok)throw new Error('Connection details are unavailable.');
    let described;try{described=await response.json();}catch{throw new Error('Connection details are unavailable.');}
    if(captured!==epoch)return;capabilities=described;
    $('guide-connection-status').textContent=capabilities.interfaces.mcp?'MCP is available. Connect a compatible external assistant using the server URL below.':'MCP is unavailable until NS8 sign-in and hostname-root routing are configured.';
    if(capabilities.mcp_url){$('agent-mcp-url').value=capabilities.mcp_url;$('guide-mcp').hidden=false;}
    if(!capabilities.authenticated){$('guide-status').textContent='Sign in to see instructions for your current permissions.';$('guide-signin').hidden=false;return;}
    profile=window.C0Space?await read('me'):{role:capabilities.role};if(captured!==epoch)return;
    $('guide-status').textContent='Your current access: '+profile.role+'.';
    const choices=[['read','Read and research']];if(writable())choices.push(['create','Create an article'],['update','Update knowledge'],['ingest','Import a document']);
    const workflows=(capabilities.guidance?.workflows || []).filter(flow=>writable() || ['research','structured-research'].includes(flow.id));
    for(const [id,kind,title]of [['evidence','evidence','Save selected text evidence'],['investigation','investigate','Private sourced investigation'],['consolidate','consolidate','Consolidate and supersede']])if(workflows.some(flow=>flow.id===id))choices.push([kind,title]);
    if($('guide-rules'))$('guide-rules').replaceChildren(...(capabilities.guidance?.rules || []).map(rule=>node('li',rule)));
    if($('guide-workflows')){$('guide-workflows').replaceChildren();for(const flow of workflows){const section=node('details'),summary=node('summary',flow.title),steps=node('ol');for(const instruction of flow.steps)steps.append(node('li',instruction));section.append(summary,steps);$('guide-workflows').append(section);}}
    $('guide-tasks').replaceChildren();for(const [kind,title]of choices){const panel=node('details');panel.append(node('summary',title));const body=node('div');C.copyPanel(body,C.task(kind,null,capabilities));panel.append(body);$('guide-tasks').append(panel);}
  }
  async function initialize() {
    try {
      if(kind==='agents'){await guide();return;}
      if(kind==='index' && C.params.get('view')==='account')return;
      profile=await read('me');
      const account=$({wiki:'wiki-account',sources:'sources-account'}[kind]);if(account)account.textContent='Signed in as '+profile.username;
      const signIn=$({wiki:'wiki-signin',sources:'sources-signin'}[kind]);if(signIn)signIn.hidden=true;
      showRoot();
      if(kind==='index'){if(C.params.get('view')!=='account')await home();else{$('reader-root').hidden=true;$('page-title').textContent='Account and shared access';}return;}
      if(kind==='wiki') {
        if(sectionPath && (!/^[a-z0-9][a-z0-9/-]{0,127}$/.test(sectionPath) || sectionPath.includes('//') || sectionPath.endsWith('/'))){status('This section link is invalid.');return;}
        $('tree-more').addEventListener('click',loadIndex);$('facts-more').addEventListener('click',loadFacts);
        for(const [id,kind] of [['article-read-task','read'],['article-update-task','update']])$(id).addEventListener('click',()=>{if(article && (kind==='read'||writable()))C.copyPanel($('article-task'),C.task(kind,article,capabilities));});
        const jobs=[loadIndex()];
        if(!C.params.has('page') && C.params.get('category')!=='articles'){
          $('knowledge-sources').hidden=false;
          for(const [id,delta]of [['reader-sources-previous',-50],['reader-sources-next',50]])$(id).addEventListener('click',()=>{sourceOffset=Math.max(0,sourceOffset+delta);library();});
          jobs.push(library());
        }
        if(C.params.has('page'))jobs.push(loadArticle(C.params.get('page'),C.params.get('revision')));
        await Promise.all(jobs);return;
      }
      if(kind==='sources') {
        for(const [id,delta]of [['reader-sources-previous',-50],['reader-sources-next',50]])$(id).addEventListener('click',()=>{sourceOffset=Math.max(0,sourceOffset+delta);library();});
        const jobs=[library()];if(C.params.has('document'))jobs.push(loadLogical(C.params.get('document'),C.params.get('snapshot'),C.params.get('chunk')));else if(C.params.has('source'))jobs.push(loadSource(C.params.get('source'),C.params.get('version'),C.params.get('chunk')));await Promise.all(jobs);
      }
    }catch(error){status(error.message);if(kind==='agents')$('guide-status').textContent=error.message;}
  }
  window.addEventListener('pagehide',()=>{C.stopMarkdown();++epoch;++selection;clearTimeout(pollTimer);});
  window.addEventListener('pageshow',event=>{if(event.persisted)window.location.reload();});
  initialize();
})();
