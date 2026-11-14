"""Fast playable-world turns with bounded asynchronous *proposals*.

Model jobs never mutate the world. Their results are revalidated and committed
only on the next client heartbeat, so combat does not wait on model latency.
The explicit /advance endpoint and formal evaluation remain unchanged.
"""
import asyncio
import json
import os
from uuid import uuid4
from shared.protocol import StateView
from server.storage.sqlite import response
from server.world.commands import WorldError
from server.world.agent_runtime import build_context
from server.world.director import WorldDirector, DirectorConfig
from server.world.director_context import build as director_context
from server.world.director_execution import execute
from server.world.tasks import event
from server.world import living_world as life, chronicle, economy


class AmbientTurns:
    def __init__(self, turns):
        self.turns, self.agents, self.store = turns, turns.agents, turns.store
        self.jobs = {}
        self.ready = {}
        self.generation = 0

    async def close(self):
        self.generation += 1
        jobs = list(self.jobs.values())
        self.jobs.clear()
        self.ready.clear()
        for job in jobs:job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

    async def _think(self, world_id, context, director, config, generation):
        async def plan():
            return await self.agents.gateway.call('plan', context, []) if context else (None, 'fallback')
        async def assess():
            if director is None:return None
            async with self.agents.gateway.semaphore:
                return await WorldDirector(config,self.turns.provider).assess(director,last_assessed_tick=-100)
        try:
            (decision,mode), result = await asyncio.gather(plan(), assess())
            if generation==self.generation:
                self.ready[world_id] = (context,decision,mode,result)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Providers expose sanitized failure modes; never log key or payload.
            self.ready[world_id] = (None,None,'fallback',None)
        finally:
            self.jobs.pop(world_id,None)

    async def heartbeat(self, world_id, body):
        scope=world_id+'/heartbeat'
        plan_context=None;world_context=None;config=None
        with self.store.connection(write=True) as c:
            cached=self.store.cached(c,scope,body)
            if cached is not None:return cached
            row=self.store.world_row(c,world_id)
            self.store.require_ordinary(c,world_id)
            state=StateView.model_validate_json(row['state']);region=json.loads(row['region'])
            if state.world_version!=body.expected_world_version:
                raise WorldError('VERSION_CONFLICT','World changed; refresh before advancing.',409)
            if not life.read(c,world_id):raise WorldError('FEATURE_DISABLED','Start a new R6 world.')
            if body.trigger_event_ids:
                for source in body.trigger_event_ids:
                    if not c.execute('SELECT 1 FROM events WHERE world_id=? AND id=?',(world_id,source)).fetchone():
                        raise WorldError('UNKNOWN_EVENT','Trigger is outside this world.')
            runtime=self.turns.runtime(c,world_id)
            config=DirectorConfig.model_validate_json(runtime['config'])
            state.tick+=1
            seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE world_id=?',(world_id,)).fetchone()[0]
            emitted=[];summaries=[]
            pending=self.ready.get(world_id)
            if pending:
                context,decision,mode,result=pending
                actor=next((a for a in state.actors if context and a.id==context.npc_id and a.alive and not a.task_id),None)
                if actor and decision and mode=='live':
                    fresh=build_context(c,state,actor.id)
                    state,changes,tasks,status=self.agents.apply_decision(c,state,fresh,decision,mode,region,seq+len(emitted))
                    emitted.extend(changes)
                    summaries.append({'npc_id':actor.id,'mode':mode,'intent_status':status,'task_ids':tasks})
                    if decision.reply:
                        emitted.append(event(state,'npc_speech',seq+len(emitted),actor.id,None,
                            {'text':decision.reply,'mode':'live','source_type':'report'},[e.id for e in changes],life.near_witnesses(state,actor.tile)))
                if result:
                    self.turns.last_mode=result.mode
                    executions=[]
                    emitted.append(event(state,'director_assessed',seq+len(emitted),None,None,
                        {'mode':result.mode,'status':result.status,'reason_code':result.reason_code,'summary':result.decision.summary if result.decision else ''},
                        result.decision.source_event_ids if result.decision else [],[]))
                    if result.decision:
                        for proposal in result.decision.proposals:
                            if proposal.kind=='FOLLOW_UP':
                                target=next((a for a in state.actors if a.id==proposal.target_id and a.alive and a.kind=='npc'),None)
                                duplicate=c.execute("SELECT 1 FROM director_focus WHERE world_id=? AND npc_id=? AND status='queued'",(world_id,proposal.target_id)).fetchone()
                                if target and not duplicate:
                                    follow=event(state,'director_follow_up_queued',seq+len(emitted),None,target.id,
                                        {'reason_summary':proposal.reason_summary},proposal.source_event_ids,[])
                                    emitted.append(follow)
                                    c.execute("INSERT INTO director_focus VALUES (?,?,?,?, 'queued')",(world_id,'focus_'+uuid4().hex,target.id,follow.id))
                                    executions.append({'event_id':follow.id,'accepted':True})
                            else:
                                state,outcome,accepted=execute(c,state,proposal,config,region,seq+len(emitted))
                                emitted.append(outcome);executions.append({'event_id':outcome.id,'accepted':accepted})
                    c.execute('INSERT INTO director_runs VALUES (?,?,?)',(world_id,'director_'+uuid4().hex,json.dumps({'tick':state.tick,'result':result.model_dump(mode='json'),'executions':executions})))
            emitted.extend(life.tick(c,state,region,seq+len(emitted),body.trigger_event_ids))
            emitted.append(event(state,'world_advanced',seq+len(emitted),None,None,{'reason':body.reason,'model_pending':world_id in self.jobs},body.trigger_event_ids,[]))
            economy.reconcile(c,state,emitted)
            state.world_version+=1
            state=StateView.model_validate(state.model_dump())
            c.execute('UPDATE worlds SET state=? WHERE id=?',(state.model_dump_json(),world_id))
            for value in emitted:self.store.append_event(c,world_id,value)
            evidence=chronicle.candidates(c,state)
            chapter=chronicle.record(c,state,evidence,chronicle.factual_draft(evidence),mode='rules') if evidence else None
            # Only a bounded shared worker; background computation has no state authority.
            model_enabled=bool(os.environ.get('LLM_API_KEY')) or self.agents.gateway.plan_provider is not None
            if world_id not in self.jobs and len(self.jobs)<2 and model_enabled:
                eligible=[a for a in state.actors if a.kind=='npc' and a.alive and not a.task_id]
                focus=c.execute("SELECT id,npc_id FROM director_focus WHERE world_id=? AND status='queued' ORDER BY rowid",(world_id,)).fetchall()
                chosen=next((f for f in focus if any(a.id==f['npc_id'] for a in eligible)),None)
                if eligible:
                    npc_id=chosen['npc_id'] if chosen else eligible[(state.tick-1)%len(eligible)].id
                    plan_context=build_context(c,state,npc_id)
                    if chosen:c.execute("UPDATE director_focus SET status='consumed' WHERE world_id=? AND id=?",(world_id,chosen['id']))
                if self.turns.provider and state.tick%config.interval_ticks==0:
                    world_context=director_context(c,state,config,body.trigger_event_ids)
            output=response(body.request_id,state,{'state':state.model_dump(mode='json'),'tick':state.tick,'chapter':chapter,
                'decision_summaries':summaries,'events':[e.model_dump(mode='json') for e in emitted if state.player_id in e.witness_ids],
                'ambient':{'rules':'active','model_pending':plan_context is not None or world_id in self.jobs}})
            self.store.remember(c,scope,body,output)
        self.ready.pop(world_id,None)
        if plan_context is not None or world_context is not None:
            self.jobs[world_id]=asyncio.create_task(self._think(world_id,plan_context,world_context,config,self.generation))
        return output
