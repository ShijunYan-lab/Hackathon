const $=id=>document.getElementById(id);let state=null,session=null,busy=false,pending=null,lastLog=[],majorTrigger=null,nextAdvance=0,saved=JSON.parse(localStorage.getItem('c-world-saves')||'[]');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function log(s){lastLog.unshift(s);$('log').textContent=lastLog.slice(0,12).join('\n')}
async function api(path,body){let start=performance.now(),r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});let result=await r.json();$('latency').textContent=Math.round(performance.now()-start)+' ms';log(`${r.status} ${path}`);if(!result.ok){let e=Error(result.error.code+' · '+result.error.message);e.definite=result.error.code!=='REQUEST_IN_PROGRESS';throw e;}return result.data}
function adopt(s){if(s){if(state?.world_id!==s.world_id){majorTrigger=null;nextAdvance=Date.now()+20000;}state=s;}render();syncControls()}
async function write(path,body){if(pending)throw Error('上次请求结果未确认，请先重试原请求');body={request_id:crypto.randomUUID(),...body};pending={path,body};try{let data=await api(path,body);pending=null;return data}catch(e){if(e.definite)pending=null;throw e}}
async function action(fn){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);try{$('notice').textContent='正在处理…';await fn();$('notice').textContent='已完成';await refresh()}catch(e){$('notice').textContent=e.message;log(e.message)}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);$('retry').hidden=!pending;syncControls()}}
const need=()=>{if(!state)throw Error('请先创建世界');return '/v1/worlds/'+state.world_id};
const cmd=async(kind,payload)=>{let d=await write(need()+'/commands',{expected_world_version:state.world_version,kind,payload});adopt(d.state);const hit=d.events?.find(e=>e.type==='actor_died')||d.events?.find(e=>e.type==='hit_applied');if(hit){majorTrigger=hit.id;nextAdvance=Date.now()+2000;}return d};
function selected(){return state?.actors.find(a=>a.id===$('actors').value)}
function options(el,values){let old=el.value;el.innerHTML=values.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');if(values.some(v=>v[0]===old))el.value=old}
function render(){options($('saves'),saved.map(s=>[s.id,s.label]));if(!state)return;$('tick').textContent=state.tick;$('version').textContent=state.world_version;$('population').textContent=state.actors.filter(a=>a.alive).length;$('worldId').textContent=state.world_id;options($('actors'),state.actors.filter(a=>a.id!==state.player_id).map(a=>[a.id,a.name+(a.alive?'':' · 已死亡')]));options($('items'),state.items.map(i=>[i.id,i.name+' · '+(i.owner_id===state.player_id?'本人':i.owner_id?'他人持有':'地面')]));let a=selected();$('actorInfo').textContent=a?`${a.hp}/${a.max_hp} HP · 护甲 ${a.armor} · ${a.behavior}`:'';$('tasks').innerHTML=state.tasks.filter(t=>['pending','running'].includes(t.status)).map(t=>`<div class="entry">${esc(t.kind)} · ${esc(t.actor_id)}<br>${esc(t.status)}${t.kind==='MOVE'?`<button data-task="${esc(t.id)}" data-status="succeeded">模拟到达</button><button data-task="${esc(t.id)}" data-status="failed">模拟执行失败</button>`:'跟随商人的持续护卫任务'}</div>`).join('')||'暂无未完成任务';draw()}
function draw(){let c=$('map'),g=c.getContext('2d'),w=c.width,h=c.height;g.fillStyle='#253e34';g.fillRect(0,0,w,h);g.strokeStyle='#304a3c';for(let x=0;x<w;x+=20){g.beginPath();g.moveTo(x,0);g.lineTo(x,h);g.stroke()}for(let y=0;y<h;y+=20){g.beginPath();g.moveTo(0,y);g.lineTo(w,y);g.stroke()}[['村庄 A',130,120,'#a58c60'],['村庄 B',740,330,'#a58c60'],['森林',400,320,'#4e7752'],['遗迹',720,90,'#7e8c89']].forEach(([name,x,y,color])=>{g.fillStyle=color;for(let i=0;i<6;i++)g.fillRect(x+i%3*24,y+Math.floor(i/3)*26,18,19);g.font='16px Microsoft YaHei';g.fillText(name+'（示意）',x,y-12)});if(!state)return;let player=state.actors.find(a=>a.id===state.player_id),sx=w/48,sy=h/32;g.fillStyle='rgba(8,18,23,.45)';g.fillRect(0,0,w,h);state.sites.forEach(s=>{g.fillStyle='#a8bb70';g.fillRect(s.tile.x*sx-3,s.tile.y*sy-3,6,6)});state.actors.forEach(a=>{let x=a.tile.x*sx,y=a.tile.y*sy;g.fillStyle=!a.alive?'#706568':a.id===state.player_id?'#f6d18c':a.kind==='monster'?'#df7a65':'#85c6bb';g.fillRect(x-5,y-10,10,15);g.fillStyle='#eee7cc';g.font='12px Microsoft YaHei';g.fillText(a.name,x+9,y);if(selected()?.id===a.id){g.strokeStyle='#eed392';g.strokeRect(x-9,y-14,18,23)}})}
async function refresh(){if(!state)return;let path=need();adopt((await api(path+'/state')).state);await refreshDirector(path);const book=await api(path+'/story/chapters?latest=true&limit=6');$('chapters').innerHTML=book.chapters.map(c=>`<div class="entry"><strong>${esc(c.title)}</strong><p>${esc(c.narrative)}</p>${c.open_question?`<p>${esc(c.open_question)}</p>`:''}<small>AI 叙事 · 来源 ${esc(c.source_event_ids.join(', '))}</small></div>`).join('')||'关键事件发生后，世界会在后台整理成章节。';let story=await api(path+'/story');$('story').innerHTML=story.memories.slice(-12).reverse().map(m=>`<div class="entry">${esc(m.summary)}<br><small>${esc(m.source_event_ids.join(', '))}</small></div>`).join('')||'尚无可见记忆';let econ=await api(path+'/economy');$('wallet').textContent='玩家金币：'+econ.wallets[state.player_id];$('config').textContent=JSON.stringify({world_id:state.world_id,seed:state.seed,region:state.current_region_id,recipes:econ.recipes,offers:econ.offers},null,2);if(session){let d=await api('/v1/evaluations/'+session.evaluation_id);session=d.session;if(d.state)adopt(d.state);let report=await api('/v1/evaluations/'+session.evaluation_id+'/report');let p=await api('/v1/evaluations/'+session.evaluation_id+'/profile');$('phase').textContent=phaseInfo(session.status).title;$('evaluationView').innerHTML=`<div class="evaluation-guide"><strong>${esc(phaseInfo(session.status).title)}</strong><p>${esc(phaseInfo(session.status).help)}</p>${phaseInfo(session.status).next?`<button data-next="${phaseInfo(session.status).next}" class="primary">${esc(phaseInfo(session.status).button)}</button>`:''}</div><p>策略 V${p.active_profile.version} · direct ${p.active_profile.values.direct.toFixed(2)} / escort ${p.active_profile.values.escort.toFixed(2)}</p><table><tr><th>轮次</th><th>策略</th><th>交付</th><th>费用</th><th>耗时</th></tr>${report.runs.map(r=>`<tr><td>${esc(r.kind)}</td><td>${esc(r.strategy)}</td><td>${r.metrics?Math.round(r.metrics.delivered_ratio*100)+'%':r.status==='running'?'执行中':'已取消'}</td><td>${r.metrics?.gold_spent??'—'}</td><td>${r.metrics? (r.metrics.duration_ms/1000).toFixed(1)+'s':'—'}</td></tr>`).join('')}</table><p>比较：${esc(report.improvement)} · 当前模式 ${esc(session.mode)}</p><p class="muted">本页上报的任务结果属于模拟输入，不能证明真实游戏表现。</p>`}}
$('create').onclick=()=>action(async()=>{pending=null;session=null;adopt((await write('/v1/worlds',{seed:Number($('seed').value),player_name:'旅人'})).state);$('phase').textContent='普通世界'});
async function advanceWorld(manual){
 const trigger=majorTrigger;
 const d=await write(need()+'/advance',{expected_world_version:state.world_version,
  reason:trigger?'major_event':manual?'debug_step':'idle_timer',trigger_event_ids:trigger?[trigger]:[]});
 majorTrigger=null;
 nextAdvance=Date.now()+(d.director?.retry_next_turn?4000:20000);
 adopt(d.state);
}
$('advance').onclick=()=>action(()=>advanceWorld(true));
async function autoAdvance(){
 if(!state||session||busy||pending||!$('autoAdvance').checked||document.hidden||
    document.activeElement===$('text')||Date.now()<nextAdvance)return;
 nextAdvance=Date.now()+20000;
 // Serialize through the same mutation path as the manual control.
 await action(()=>advanceWorld(false));
}
setInterval(autoAdvance,1000);
$('refresh').onclick=()=>action(refresh);$('actors').onchange=render;
$('approach').onclick=()=>action(async()=>{let a=selected();if(!a)throw Error('请选择目标');await cmd('CHECKPOINT',{region_id:a.region_id,positions:[{actor_id:state.player_id,tile:a.tile}]})});
$('attack').onclick=()=>action(async()=>{let a=selected(),p=state.actors.find(a=>a.id===state.player_id);await cmd('HIT',{attack_id:crypto.randomUUID(),attacker_id:p.id,target_id:a.id,weapon_id:p.equipped_item_id,region_id:p.region_id,attacker_tile:p.tile,target_tile:a.tile})});
$('dialogue').onclick=()=>action(async()=>{let d=await write(need()+'/dialogue',{expected_world_version:state.world_version,npc_id:selected().id,text:$('text').value});adopt(d.state);$('reply').textContent=`${d.mode} · ${d.reply}`});
for(let kind of ['pickup','equip','give'])$(kind).onclick=()=>action(()=>cmd(kind.toUpperCase(),{actor_id:state.player_id,item_id:$('items').value,...(kind==='give'?{target_id:selected().id}:{})}));
$('save').onclick=()=>action(async()=>{let d=await write(need()+'/saves',{expected_world_version:state.world_version,label:$('saveName').value});saved.push({id:d.save_id,label:$('saveName').value});localStorage.setItem('c-world-saves',JSON.stringify(saved));adopt(d.state)});
$('load').onclick=()=>action(async()=>{if(!$('saves').value)throw Error('请先保存世界');let d=await write('/v1/saves/'+$('saves').value+'/load',{});session=null;adopt(d.state)});
$('evaluation').onclick=()=>action(async()=>{let d=await write('/v1/evaluations',{seed:Number($('seed').value)});session=d.session;adopt(d.state)});
for(let kind of ['first','second'])$(kind).onclick=()=>action(async()=>{if(!session)throw Error('请先建立评审');let d=await write('/v1/evaluations/'+session.evaluation_id+'/runs',{expected_evaluation_version:session.evaluation_version,kind});session=d.session;adopt(d.state)});
$('rollback').onclick=()=>action(async()=>{if(!session)throw Error('请先建立评审');let d=await write('/v1/evaluations/'+session.evaluation_id+'/rollback',{expected_evaluation_version:session.evaluation_version});session=d.session;adopt(d.state)});
$('tasks').onclick=e=>{let b=e.target.closest('[data-task]');if(!b)return;action(async()=>{let t=state.tasks.find(t=>t.id===b.dataset.task);await cmd('TASK_REPORT',{task_id:t.id,actor_id:t.actor_id,status:b.dataset.status,region_id:t.target_region_id,tile:t.target_tile,...(b.dataset.status==='failed'?{failure_code:'DEMO_SYNTHETIC_FAILURE'}:{})})})};
$('retry').onclick=()=>action(async()=>{if(!pending)return;let d;try{d=await api(pending.path,pending.body)}catch(e){if(e.definite)pending=null;throw e}pending=null;if(d.session)session=d.session;
 if(d.director){majorTrigger=null;nextAdvance=Date.now()+(d.director.retry_next_turn?4000:20000);}
 const hit=d.events?.find(e=>e.type==='actor_died')||d.events?.find(e=>e.type==='hit_applied');
 if(hit){majorTrigger=hit.id;nextAdvance=Date.now()+2000;}
 adopt(d.state)});
$('map').onclick=e=>{if(!state||busy)return;let rect=e.target.getBoundingClientRect(),tile={x:(e.clientX-rect.left)/rect.width*48,y:(e.clientY-rect.top)/rect.height*32};let a=state.actors.find(a=>a.id!==state.player_id&&Math.hypot(a.tile.x-tile.x,a.tile.y-tile.y)<1);if(a){$('actors').value=a.id;render()}else action(()=>cmd('CHECKPOINT',{region_id:state.current_region_id,positions:[{actor_id:state.player_id,tile}]}))};
setInterval(pollEvaluation,1500);api('/health').then(h=>{$('health').textContent=`后端在线 · ${h.mode}`}).catch(e=>{$('health').textContent='后端连接失败';log(e.message)});render();draw();


function phaseInfo(phase){
 return ({
 ready:{title:'① 会话已建立 · 等待开始',help:'现在还没有运输任务。点击“开始首轮运输”，商人才会获得任务。',next:'first',button:'开始首轮运输 →'},
 first_running:{title:'② 首轮运输中',help:'这是模拟客户端，不会自动替角色行走。请在右侧“执行中的任务”中选择“模拟到达”或“模拟执行失败”。45 秒未完成会超时。'},
 learning:{title:'③ 自动学习中',help:'首轮已经结算，后端正在自动更新本次策略。请稍候，无需反复点击。'},
 ready_for_second:{title:'④ 学习完成 · 可以再次出发',help:'下方可查看新策略值。点击第二轮，从相同初始世界与资金开始。',next:'second',button:'开始同条件第二轮 →'},
 second_running:{title:'⑤ 第二轮运输中',help:'请在右侧任务区提交模拟到达或失败。护卫持续任务不需要单独报告。结果不会预先指定。'},
 complete:{title:'⑥ 两轮结束 · 查看成绩',help:'下方对比交付率、费用和耗时。可以回退，恢复完整的学习前状态。',next:'rollback',button:'恢复学习前状态'},
 rolled_back:{title:'已恢复学习前状态',help:'当前策略和经验已恢复 P0，旧成绩保留审计。可建立新会话重新演示。'},
 rollback_running:{title:'回退验证中',help:'在右侧任务区报告执行结果。'},
 failed:{title:'会话执行失败',help:'请查看请求错误；可以恢复学习前状态后建立新会话。',next:'rollback',button:'恢复学习前状态'}
 })[phase]||{title:phase||'尚未建立',help:'点击左侧“建立评审会话”开始。'};
}
function syncControls(){
 const phase=session?.status;
 $('first').disabled=busy||phase!=='ready';
 $('second').disabled=busy||phase!=='ready_for_second';
 $('rollback').disabled=busy||!session;
 for(const id of ['advance','save','dialogue','give','equip','pickup','approach'])$(id).disabled=busy||!state||!!session;
 $('attack').disabled=busy||!state||(!!session&&!['first_running','second_running','rollback_running'].includes(phase));
 document.querySelectorAll('[data-next]').forEach(b=>b.disabled=busy);
}
$('evaluationView').onclick=e=>{const button=e.target.closest('[data-next]');if(button&&!busy)$(button.dataset.next).click()};
let polling=false;
async function pollEvaluation(){
 if(!session||busy||polling||!['first_running','learning','second_running','rollback_running'].includes(session.status))return;
 polling=true;const id=session.evaluation_id,version=session.evaluation_version,world=state?.world_id,worldVersion=state?.world_version;
 try{
  const response=await fetch('/v1/evaluations/'+id);
  const result=await response.json();
  if(!result.ok)throw Error(result.error.message);
  if(busy||session?.evaluation_id!==id||session.evaluation_version!==version||state?.world_id!==world||state?.world_version!==worldVersion)return;
  const d=result.data;
  if(d.session.evaluation_version!==version||d.state?.world_version!==worldVersion){await action(refresh)}
 }catch(e){if(!busy){$('notice').textContent='状态同步暂时失败，可点击“刷新当前数据”：'+e.message}}
 finally{polling=false}
}
syncControls();

const directorLabels={
 NO_ACTION_PROPOSED:'已评估，暂无新行动',PARTIAL_DECISION:'已评估，部分内容未采用',
 AWAITING_WORLD_VALIDATION:'已评估，建议已交给世界规则校验',
 INVALID_DECISION:'旧版记录：模型输出未通过校验',
 SUMMARY_EVIDENCE_INVALID:'摘要缺少可核对的来源',UNKNOWN_EVENT_REFERENCE:'建议引用了未知事件',
 UNKNOWN_LOCATION:'地点 ID 无效',FOLLOW_UP_TARGET_INVALID:'跟进对象须为存活 NPC',
 ORGANIZATION_INVALID:'组织不存在或不活跃',MIGRATION_ENTRY_INVALID:'迁入入口未配置或无效',
 PROPOSAL_DISABLED:'该动作当前不可用',PROPOSAL_FORMAT_INVALID:'单条建议格式不符合约定',
 PROPOSALS_FORMAT_INVALID:'建议列表格式不符合约定',RESOURCE_LIMIT:'超过资源配置上限',
 POPULATION_LIMIT:'已达到人口上限',MIGRATION_TARGET_INVALID:'迁入必须生成新人物',
 PROPOSAL_BUDGET_EXCEEDED:'超过本回合建议数量上限',MODEL_TIMEOUT:'模型响应超时',REQUEST_BUDGET_EXHAUSTED:'等待模型调用额度超时'
};
const directorLabel=code=>directorLabels[code]||code;
async function refreshDirector(path){
 const health=await api('/health');
 $('health').textContent=`世界导演 ${health.component_modes.director} · NPC ${health.component_modes.npc}`;
 if(!health.debug_views){$('director').textContent='全局审计未开放。导演已配置：'+health.director_configured;return}
 const data=await api(path+'/director/debug');
 const assessed=data.runs.filter(r=>r.result.status!=='skipped').slice(-5).reverse();
 $('director').innerHTML=`<p>模型：${esc(health.director_model||'未配置')} · 以下为开发者全局视图，不会传给所有 NPC。</p>`+assessed.map(r=>`<div class="entry"><strong>回合 ${r.tick} · ${esc(r.result.mode)} · ${esc(directorLabel(r.result.reason_code))}</strong>${r.retry_next_turn?'<p class="muted">已保留事件，下一个回合会提前重试一次。</p>':''}<p>${esc(r.result.decision?.summary||(r.result.mode==='live'?'本次没有可展示的摘要。':'本回合没有执行模型建议。'))}</p>${r.result.issues?.length?`<p class="muted">${esc(r.result.issues.map(directorLabel).join('；'))}</p>`:''}${(r.result.decision?.proposals||[]).map((p,i)=>`<p>${esc(p.kind)}：${esc(p.reason_summary)}<br>执行：${r.executions[i]?.accepted?'已接受':'未接受'} · ${esc(r.executions[i]?.event_id||'无')}<br>依据：${esc(p.source_event_ids.join(', '))}</p>`).join('')}<small>摘要来源：${esc(r.result.decision?.source_event_ids.join(', ')||'无')}</small></div>`).join('');
 const statuses={queued:'等待 NPC 规划',consumed:'NPC 已返回规划',cancelled:'已取消'};
 if(data.focus.length)$('director').innerHTML+=data.focus.slice(0,5).map(f=>`<p>${esc(statuses[f.status]||f.status)} · ${esc(state.actors.find(a=>a.id===f.npc_id)?.name||f.npc_id)}</p>`).join('');
 if(!assessed.length)$('director').innerHTML+='<p>还未到评估回合，请继续推进。</p>';
}
