// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function definition(file){
  let source=fs.readFileSync(path.join(__dirname,'../../ui/src/'+file),'utf8').split('<script>')[1].split('</script>')[0];
  source=source.replace(/import[\s\S]*?from\s+["'][^"']+["'];/g,'').replace('export default','module.exports =');
  const module={exports:{}};vm.runInNewContext(source,{module,mapState:()=>({}),TaskService:{},UtilService:{},QueryParamService:{},IconService:{},PageTitleService:{},RuntimeStatus:{},setTimeout,clearTimeout,clearInterval,to:async promise=>{try{return [null,await promise];}catch(error){return [error];}}});return module.exports;
}
function setup(file='components/RuntimeStatus.vue'){
  const def=definition(file),events=new Map(),requests=[],removed=[];let id=0;
  const ctx={...def.data(),$t:key=>key,instanceName:'czero7',core:{$root:{
    $once(event,callback){events.set(event,callback);},$off(event,callback){assert.equal(events.get(event),callback);events.delete(event);removed.push(event);}}},
    $set(obj,key,value){obj[key]=value;},$delete(obj,key){delete obj[key];},getUuid(){return 'task-'+(++id);},
    createModuleTaskForApp(instance,task){return new Promise((resolve,reject)=>requests.push({instance,task,resolve,reject}));},
    createClusterTaskForApp(task){return new Promise((resolve,reject)=>requests.push({task,resolve,reject}));},
    getErrorMessage(){return 'generic';},sortByProperty(){return ()=>0;}};
  for(const [key,fn] of Object.entries(def.methods))ctx[key]=fn.bind(ctx);
  for(const [key,fn] of Object.entries(def.computed))Object.defineProperty(ctx,key,{get:()=>fn.call(ctx)});
  return{def,ctx,events,requests,removed};
}
function complete(h,index,output){const task=h.requests[index].task;const event=task.action+'-completed-'+task.extra.eventId;h.events.get(event)({}, {output});}
test('native readiness uses only the three safe module actions and cleans terminal listeners',()=>{
  const h=setup();h.def.created.call(h.ctx);assert.equal(h.events.size,6);assert.equal(h.ctx.busy,true);
  assert.deepEqual(h.requests.map(r=>r.task.action),['get-runtime-status','get-authentication-status','get-scheduler-status']);
  complete(h,0,{database:{status:'ok',schema_revision:'0013',vector_version:'0.8.7'},retrieval:{configuration_valid:true,embeddings_configured:false,scorer_mode:'off'}});
  assert.equal(h.events.size,4);assert.equal(h.ctx.cards[0].title,'status.database_ready');assert.equal(h.ctx.cards[3].title,'status.text_search');
  complete(h,1,{status:'disabled'});complete(h,2,{timer_active:true,worker_running:false,worker_failed:false});
  assert.equal(h.events.size,0);assert.equal(h.ctx.busy,false);assert.equal(h.ctx.cards[2].title,'status.timer_ready');
});
test('late native completion and creation failures cannot affect a newer refresh',async()=>{
  const h=setup();h.ctx.refresh();const old=[...h.events.values()][0];h.ctx.refresh();
  assert.equal(h.events.size,6);old({}, {output:{database:{status:'ok'}}});assert.equal(h.ctx.values['get-runtime-status'],undefined);
  h.requests[0].reject(new Error('old private task error'));await tick();assert.equal(h.events.size,6);assert.equal(h.ctx.errors['get-runtime-status'],false);
  h.requests[3].reject(new Error('new private task error'));await tick();assert.equal(h.events.size,4);assert.equal(h.ctx.errors['get-runtime-status'],true);assert.equal(h.ctx.cards[0].title,'status.unknown');
});
test('Vue 2 destruction removes every native readiness listener and ignores callbacks',()=>{
  const h=setup();h.ctx.refresh();const old=[...h.events.values()][0];h.def.beforeDestroy.call(h.ctx);
  assert.equal(h.events.size,0);old({}, {output:{database:{status:'ok'}}});h.ctx.refresh();assert.equal(h.requests.length,3);assert.equal(h.ctx.values['get-runtime-status'],undefined);
});
test('native aborted status is unknown and worker idle differs from failure or pause',()=>{
  const h=setup();h.ctx.refresh();const task=h.requests[0].task;h.events.get('get-runtime-status-aborted-'+task.extra.eventId)({private:'must not be shown'});
  assert.equal(h.ctx.errors['get-runtime-status'],true);assert.equal(h.ctx.cards[0].title,'status.unknown');
  for(const [scheduler,expected] of [[{worker_failed:true},'worker_failed'],[{worker_running:true},'worker_running'],[{timer_active:false},'timer_paused'],[{timer_active_state:'failed'},'timer_failed']]){
    h.ctx.values['get-scheduler-status']=scheduler;assert.equal(h.ctx.cards[2].title,'status.'+expected);
  }
});
test('existing Status task listeners clean on failure completion and Vue 2 destruction',async()=>{
  const h=setup('views/Status.vue');h.ctx.getStatus();assert.equal(h.events.size,2);
  h.requests[0].reject(new Error('private'));await tick();assert.equal(h.events.size,0);assert.equal(h.ctx.loading.getStatus,false);
  h.ctx.listBackupRepositories();complete(h,1,{repositories:[]});assert.equal(h.events.size,2); // follow-up backup listing
  complete(h,2,{backups:[]});assert.equal(h.events.size,0);
  h.ctx.getStatus();h.def.beforeDestroy.call(h.ctx);assert.equal(h.events.size,0);
});

test('a late task-creation rejection cannot undo a completed readiness result',async()=>{
  const h=setup();h.ctx.refresh();complete(h,0,{database:{status:'ok',schema_revision:'0013',vector_version:'0.8.7'},retrieval:{configuration_valid:true,embeddings_configured:false,scorer_mode:'off'}});
  h.requests[0].reject(new Error('late'));await tick();assert.equal(h.ctx.cards[0].title,'status.database_ready');assert.equal(h.ctx.errors['get-runtime-status'],false);
});
