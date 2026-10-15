// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tick = () => new Promise(resolve => setImmediate(resolve));
const source = fs.readFileSync(path.join(__dirname,'../../app/static/navigation.js'),'utf8');
function setup(write) {
  const links=['./','./objects','./sources'].map(href=>({href,attributes:{},setAttribute(k,v){this.attributes[k]=v;}}));
  const field={value:'https://c0.example.test/mcp',focus(){this.focused=true;},select(){this.selected=true;}};
  const status={textContent:''}; const button={dataset:{copyTarget:'url'},disabled:false,addEventListener(_,fn){this.click=fn;}};
  const document={querySelectorAll(selector){return selector.startsWith('nav')?links:selector==='a[data-admin-link]'?[]:[button];},getElementById(id){return id==='copy-status'?status:field;}};
  vm.runInNewContext(source,{document,URL,navigator:{clipboard:{writeText:write}},window:{location:{href:'https://c0.example.test/czero/czero17/objects',pathname:'/czero/czero17/objects'}}});
  return {links,field,status,button};
}
test('navigation marks only the current legacy-prefix page',()=>{
  const h=setup(async()=>{});assert.equal(h.links[1].attributes['aria-current'],'page');
  assert.equal(h.links[0].attributes['aria-current'],undefined);assert.equal(h.links[2].attributes['aria-current'],undefined);
});
test('copy captures canonical URL and prevents duplicate in-flight actions',async()=>{
  const copied=[];let finish;const h=setup(value=>{copied.push(value);return new Promise(resolve=>{finish=resolve;});});
  h.button.click();h.button.click();assert.deepEqual(copied,['https://c0.example.test/mcp']);assert.equal(h.button.disabled,true);
  finish();await tick();assert.equal(h.status.textContent,'Server URL copied.');assert.equal(h.button.disabled,false);
});
test('clipboard refusal offers manual copy without claiming success',async()=>{
  const h=setup(async()=>{throw new Error('denied');});await h.button.click();
  assert.equal(h.field.focused,true);assert.equal(h.field.selected,true);
  assert.match(h.status.textContent,/Select and copy/);assert.equal(h.button.disabled,false);
});

test('administration navigation is shown only after a verified Admin reply', async()=>{
  for(const role of ['admin','reader','editor',null]){
    const link={hidden:true};
    const document={querySelectorAll(selector){return selector==='a[data-admin-link]'?[link]:[];}};
    vm.runInNewContext(source,{document,URL,window:{location:{href:'https://c0.test/',pathname:'/'}},fetch:async()=>({ok:role!==null,json:async()=>({role})})});
    await tick();assert.equal(link.hidden,role!=='admin');
  }
});
