const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let requests=0,writes=0,elements=new Map();
function element(id){if(!elements.has(id)){let html='';elements.set(id,{value:'',disabled:false,hidden:false,textContent:'',get innerHTML(){return html},set innerHTML(v){html=v;writes++},getContext(){return new Proxy({},{get:()=>()=>{}})}})}return elements.get(id)}
const context=vm.createContext({document:{getElementById:element,querySelectorAll:()=>[]},localStorage:{getItem:()=>null},setInterval:()=>0,performance:{now:()=>0},crypto:{randomUUID:()=> 'test'},console,fetch:async()=>({json:async()=>({ok:true,data:{mode:'fallback'}})})});
vm.runInContext(fs.readFileSync('server/api/demo/app.js','utf8'),context);
(async()=>{
 await Promise.resolve();
 vm.runInContext("session={evaluation_id:'e1',evaluation_version:0,status:'ready'};state={world_id:'w1',world_version:0};syncControls()",context);
 assert.equal(element('first').disabled,false);assert.equal(element('second').disabled,true);
 assert.match(vm.runInContext("phaseInfo('ready').help",context),/点击/);
 context.fetch=async()=>{requests++;return {json:async()=>({ok:true,data:{session:{evaluation_id:'e1',evaluation_version:0,status:'first_running'},state:{world_id:'w1',world_version:0}}})}};
 await vm.runInContext('pollEvaluation()',context);assert.equal(requests,0,'ready must not continuously poll');
 vm.runInContext("session.status='first_running'",context);
 const before=writes;await vm.runInContext('pollEvaluation()',context);
 assert.equal(requests,1);assert.equal(writes,before,'unchanged poll must not redraw');assert.equal(vm.runInContext('busy',context),false);
 let resolve;context.fetch=()=>new Promise(r=>{resolve=r});
 let pending=vm.runInContext('pollEvaluation()',context);
 await vm.runInContext('pollEvaluation()',context);
 vm.runInContext("session={evaluation_id:'e2',evaluation_version:0,status:'ready'};state={world_id:'w2',world_version:0}",context);
 resolve({json:async()=>({ok:true,data:{session:{evaluation_id:'e1',evaluation_version:99},state:{world_id:'w1',world_version:99}}})});await pending;
 assert.equal(vm.runInContext('state.world_id',context),'w2');assert.equal(writes,before);
 console.log('PASS ready guidance, phase buttons, quiet polling, single in-flight poll and stale-response isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
