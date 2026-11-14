"""Additive repair of pre-live ordinary worlds; evaluation baselines stay immutable."""
import json
import math
from uuid import uuid4
from shared.protocol import StateView, Tile, Event

def upgrade(store, authored_region):
    with store.connection(write=True) as connection:
        for row in connection.execute('SELECT * FROM worlds').fetchall():
            region = json.loads(row['region'])
            if region.get('id') != 'overworld' or region.get('npc_runtime_version', 0) >= 2:
                continue
            runtime = connection.execute('SELECT evaluation_active FROM world_runtime WHERE world_id=?', (row['id'],)).fetchone()
            if runtime and runtime[0]:
                continue
            state = StateView.model_validate_json(row['state'])
            templates = {value['appearance_key']:value for value in authored_region['npc_spawns']}
            region.update(reactive_npcs=True, npc_runtime_version=2, npc_spawns=authored_region['npc_spawns'])
            spawn = region['spawn_tile']
            misplaced = [actor for actor in state.actors if actor.kind=='npc' and actor.alive and not actor.task_id
                and actor.appearance_key in templates
                and math.hypot(actor.tile.x-spawn['x'],actor.tile.y-spawn['y'])<6
                and math.hypot(actor.tile.x-templates[actor.appearance_key]['tile']['x'],
                               actor.tile.y-templates[actor.appearance_key]['tile']['y'])>6]
            for actor in misplaced:
                actor.tile=Tile.model_validate(templates[actor.appearance_key]['tile'])
            if misplaced:
                state.world_version+=1
            connection.execute('UPDATE worlds SET region=?,state=? WHERE id=?',
                (json.dumps(region,ensure_ascii=False),state.model_dump_json(),state.world_id))
            seq=connection.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE world_id=?',(state.world_id,)).fetchone()[0]+1
            for index,actor in enumerate(misplaced):
                store.append_event(connection,state.world_id,Event(id='evt_'+uuid4().hex,event_seq=seq+index,
                    tick=state.tick,type='npc_returned_home',actor_id=actor.id,
                    facts={'reason':'legacy_spawn_repair','tile':actor.tile.model_dump()},caused_by=[],witness_ids=[actor.id]))
