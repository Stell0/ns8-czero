// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict');
const {fixture,tick,reply,id,page,descendants}=require('./reader_dom.js');
test('real Markdown tokens render headings, lists, tables and code without HTML or remote images',()=>{
  const h=fixture(),body=h.node('body'),toc=h.node('toc');
  h.C.markdown(body,'# Title\n\n<script>alert(1)</script>\n\n**Bold** and `code`.\n\n- First\n- Second\n\n| Field | Value |\n| --- | --- |\n| Status | Ready |\n\n![tracking](https://external.test/track)\n\n[bad](javascript:alert(1))\n\n```html\n<img onerror=evil>\n```',toc);
  const elements=descendants(body);
  for(const tag of ['H2','UL','TABLE','STRONG','CODE'])assert(elements.some(n=>n.tagName===tag),tag);
  assert(!elements.some(n=>['SCRIPT','IMG','IFRAME'].includes(n.tagName)));
  assert(!elements.some(n=>n.href?.startsWith('javascript:')));
  assert.match(body.textContent,/<script>alert/);assert.match(body.textContent,/tracking/);
  assert.equal(toc.children[0].children[0].href,'#article-heading-1');
});
test('article links reject executable, credentialed and control-character URLs',()=>{
  const h=fixture();for(const url of ['javascript:alert(1)','data:text/html,bad','https://user:secret@host.test/','https://host.test/\nsecret'])assert.equal(h.C.safeURL(url),null);
  assert.equal(h.C.safeURL('./wiki?page='+id(1)),'https://c0.test/czero/czero17/wiki?page='+id(1));
});
test('a thousand path-based pages retain literal labels, virtual groups and the selected branch',()=>{
  const h=fixture(),target=h.node('tree');const rows=Array.from({length:1000},(_,n)=>page(n+1,'section-'+Math.floor(n/100)+'/article-'+n));
  rows[500].title='<img src=x>';h.C.tree(target,rows,id(501));
  const all=descendants(target);assert.equal(all.filter(n=>n.tagName==='A').length,1000);
  const current=all.find(n=>n.attributes?.['aria-current']==='location');assert.equal(current.textContent,'<img src=x>');
  assert(all.some(n=>n.tagName==='DETAILS' && n.dataset.path==='section-5' && n.open));
  assert(!all.some(n=>n.tagName==='IMG'));
});
test('navigation groups use Maps even for prototype-named paths',()=>{
  const h=fixture();h.C.tree(h.node('tree'),[page(1,'constructor/start'),page(2,'__proto__/start')]);
  assert.equal(descendants(h.node('tree')).filter(n=>n.tagName==='A').length,2);
});
test('copy instructions captures the task and offers manual selection after clipboard refusal',async()=>{
  const h=fixture();h.window.navigator.clipboard.writeText=async()=>{throw Error('denied');};
  const panel=h.node('panel');h.C.copyPanel(panel,'Task');const [label,field,control,status]=panel.children;
  assert.equal(label.htmlFor,field.id);await control.listeners.click();assert(field.focused && field.selected);assert.match(status.textContent,/Select and copy/);
});
test('AI recipes target the article, preserve revision authority and distinguish REST ingestion',()=>{
  const h=fixture();const update=h.C.task('update',page());assert.match(update,new RegExp(id(1)));assert.match(update,/fetch its current revision/);assert.match(update,/unchanged uncertain retry/);
  assert.match(h.C.task('create'),/Slugs are fixed/);assert.match(h.C.task('ingest'),/Binary upload is not an MCP tool/);assert.match(h.C.task('read'),/Do not change any content/);
});
test('progressive index uses metadata batches, deduplicates IDs and exposes incomplete navigation',async()=>{
  const h=fixture(),r=h.reader();const first=r.loadIndex();const batch=Array.from({length:100},(_,n)=>page(n+1,'guides/article-'+n));
  assert.equal(h.requests[0].url,'./api/v1/wiki/pages?limit=100&offset=0');h.requests[0].resolve(reply({pages:batch}));await first;
  assert.equal(h.node('tree-more').hidden,false);const next=r.loadIndex();assert.match(h.requests[1].url,/offset=100/);
  h.requests[1].resolve(reply({pages:[batch[99],page(101)]}));await next;
  assert.equal(descendants(h.node('reader-tree')).filter(n=>n.tagName==='A').length,101);assert.equal(h.node('tree-more').hidden,true);
  assert(h.requests.every(r=>!r.url.includes('/wiki/pages/'+id(1))));
});
test('historical article renders immutable title/body and does not attach current linked facts',async()=>{
  const h=fixture(),r=h.reader(),pending=r.loadArticle(id(1),'1');const historical=page();historical.content={...historical.content,title:'Earlier title',number:1,body:'# Earlier text'};
  h.requests[0].resolve(reply(historical));await pending;
  assert.equal(h.node('page-title').textContent,'Earlier title');assert.match(h.node('reader-content').textContent,/Earlier text/);
  assert.match(h.node('reader-notice').textContent,/revision 1/);assert.equal(h.requests.length,1);assert.match(h.node('reader-export').href,/revision=1/);
});
test('late article responses cannot replace the newer article or its provenance',async()=>{
  const h=fixture(),r=h.reader(),old=r.loadArticle(id(1),'1'),current=r.loadArticle(id(2),'1');
  const earlier=page(1),latest=page(2);earlier.content.number=1;latest.content.number=1;
  h.requests[1].resolve(reply(latest));await current;h.requests[0].resolve(reply(earlier));await old;
  assert.equal(h.node('page-title').textContent,'Article 2');assert.match(h.node('reader-technical').textContent,new RegExp(id(2)));
});
test('page-scoped facts remain distinct and their exact source versions become reading links',async()=>{
  const h=fixture(),r=h.reader(),pending=r.loadArticle(id(1));h.requests[0].resolve(reply(page()));await tick();
  assert.match(h.requests[1].url,/claims\?page_id=/);
  h.requests[1].resolve(reply({claims:[{id:id(2),predicate:'status',value:{answer:'Ready'}},{id:id(3),predicate:'status',value:{answer:'Blocked'}}]}));await tick();
  const citation={source_id:id(4),version_id:id(5),chunk_id:id(6),title:'Manual',version:2};
  h.requests[2].resolve(reply({evidence:[citation]}));h.requests[3].resolve(reply({evidence:[citation]}));await pending;
  assert.match(h.node('reader-facts').textContent,/Ready/);assert.match(h.node('reader-facts').textContent,/Blocked/);
  assert.equal(h.node('reader-evidence').children.length,1);assert.match(h.node('reader-evidence').children[0].children[0].href,/version=/);
});
test('permission loss clears private content and rejects an earlier successful index response',async()=>{
  const h=fixture(),r=h.reader(),index=r.loadIndex(),article=r.loadArticle(id(1));
  h.node('reader-content').textContent='Private previous article';h.requests[1].resolve(reply({},403));await article;
  h.requests[0].resolve(reply({pages:[page()]}));await index;
  assert.equal(h.node('reader-root').hidden,true);assert.equal(h.node('reader-content').textContent,'');assert.equal(h.node('reader-tree').textContent,'');
});
test('article history is fetched lazily and links to pinned revisions',async()=>{
  const h=fixture(),r=h.reader(),loading=r.loadArticle(id(1),'1'),data=page();data.content.number=1;h.requests[0].resolve(reply(data));await loading;assert.equal(h.requests.length,1);
  const history=r.loadHistory();h.requests[1].resolve(reply({revisions:[{number:1,created_at:'2026-10-15T00:00:00Z'}]}));await history;
  assert.match(h.node('reader-history').children[0].children[0].href,/revision=1/);
});
test('source version races preserve the newest document and citation document identity',async()=>{
  const h=fixture('sources'),r=h.reader(),loading=r.loadSource(id(1),id(2),id(4));
  h.requests[0].resolve(reply({id:id(1),title:'Source',metadata:{}}));h.requests[1].resolve(reply({versions:[{id:id(2),number:2,state:'ready'},{id:id(3),number:1,state:'ready'}]}));await tick();
  const newer=r.loadVersion(id(3));h.requests[3].resolve(reply({id:id(10),body:'Newest selected text'}));await newer;
  h.requests[2].resolve(reply({id:id(11),body:'Late old text'}));await loading;
  assert.equal(h.node('reader-document').textContent,'Newest selected text');assert.equal(h.requests.length,4);
});
test('a citation from another document cannot appear beside the selected version',async()=>{
  const h=fixture('sources'),r=h.reader(),loading=r.loadSource(id(1),id(2),id(4));
  h.requests[0].resolve(reply({id:id(1),title:'Source',metadata:{}}));h.requests[1].resolve(reply({versions:[{id:id(2),number:1,state:'ready'}]}));await tick();
  h.requests[2].resolve(reply({id:id(5),body:'Document'}));await tick();h.requests[3].resolve(reply({document_id:id(6),source_id:id(1),version_id:id(2),body:'Wrong document'}));await loading;
  assert.equal(h.node('reader-excerpt').hidden,true);assert.match(h.node('reader-status').textContent,/does not belong/);
});
test('AI guide exposes only read tasks to Readers and makes no writes',async()=>{
  const h=fixture('agents'),r=h.reader(),loading=r.guide();h.requests[0].resolve(reply({authenticated:true,role:'reader',interfaces:{mcp:true},mcp_url:'https://c0.test/mcp'}));await loading;
  assert.match(h.node('guide-tasks').textContent,/Read and research/);assert.doesNotMatch(h.node('guide-tasks').textContent,/Create an article|Update knowledge|Import a document/);
  assert.equal(h.node('agent-mcp-url').value,'https://c0.test/mcp');assert(h.requests.every(r=>!r.options?.method));
});
test('AI guide gives Editors maintenance instructions without claiming universal file upload',async()=>{
  const h=fixture('agents'),r=h.reader(),loading=r.guide();h.requests[0].resolve(reply({authenticated:true,role:'editor',interfaces:{mcp:false}}));await loading;
  assert.match(h.node('guide-tasks').textContent,/Create an article/);assert.match(h.node('guide-tasks').textContent,/Import a document/);
  assert.match(h.node('guide-connection-status').textContent,/MCP is unavailable/);
});


test('automatic home links missing parent pages to section browsing rather than an arbitrary article',async()=>{
  const h=fixture('index'),r=h.reader(),loading=r.home();h.requests[0].resolve(reply({pages:[page(1,'operations/backups'),page(2,'operations/monitoring')]}));await loading;
  assert.equal(h.node('home-sections').children[0].href,'./wiki?section=operations');
});
test('section browsing opens the requested navigation group and lists only that section',async()=>{
  const h=fixture('wiki','?section=operations'),r=h.reader(),loading=r.loadIndex();
  h.requests[0].resolve(reply({pages:[page(1,'operations/backups'),page(2,'getting-started')]}));await loading;
  assert.match(h.node('reader-content').textContent,/Article 1/);assert.doesNotMatch(h.node('reader-content').textContent,/Article 2/);
  assert(descendants(h.node('reader-tree')).some(n=>n.tagName==='DETAILS' && n.dataset.path==='operations' && n.open));
});
test('AI research tasks pin the displayed historical revision',()=>{
  const h=fixture(),historical=page();historical.content.number=1;
  assert.match(h.C.task('read',historical),/Read article revision 1/);
});
