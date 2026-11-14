"""R9 invariants: no omniscient map, truthful clues, grounded production, real aid.

The Godot request-lane assertions are static; final animation/frame tests still
need Godot 4.5.2 on a machine running the game.
"""
from pathlib import Path
from server.world import continuity as r9, living_world as life
from shared.protocol import StateView, Tile
from test_playable_r6 import game, body, route, edit
from test_continuity_r7 import heartbeat

ROOT=Path(__file__).resolve().parents[1]


def test_npc_does_not_get_omniscient_map_and_remembers_real_visits(game):
    c,app,s=game
    model=StateView.model_validate(s)
    npc=next(a for a in model.actors if a.kind=='npc')
    with app.state.store.connection() as conn:
        identity=life.read(conn,s['world_id'])['people'][npc.id]
    nearby=r9.known_places(npc,identity)
    assert len(nearby)<len(r9.LOCATIONS)
    assert all(v['id'] in {p['id'] for p in r9.LOCATIONS} for v in nearby)
    npc.tile=Tile(x=63,y=169)
    memory={'people':{npc.id:dict(identity)}}
    r9.record_visits(model,memory)
    assert 'place_0' in memory['people'][npc.id]['visited_place_ids']
    npc.tile=Tile(x=240,y=45)
    assert 'place_0' in [p['id'] for p in r9.known_places(npc,memory['people'][npc.id])]
    assert len(r9.known_places(npc,memory['people'][npc.id]))<len(r9.LOCATIONS)


def test_delivery_clue_uses_grounded_last_report_not_live_tracking(game):
    c,app,s=game
    model=StateView.model_validate(s)
    npcs=[a for a in model.actors if a.kind=='npc']
    recipient=npcs[1]
    # The issuer's last verified information is near one actual settlement.
    q={'kind':'delivery','status':'open','issuer_id':npcs[0].id,
       'recipient_id':recipient.id,'item_name':'parcel',
       'recipient_last_known_tile':{'x':63,'y':169},'title':'delivery'}
    recipient.tile=Tile(x=246,y=165)
    view=r9.quest_view(model,q)
    assert 'place_0' not in view.get('clue','')  # player prose uses names, not IDs
    assert r9.place(Tile(x=63,y=169)) in view['clue']
    assert r9.place(recipient.tile) not in view['clue']
    assert 'destination' not in view
    assert 'recipient_last_known_tile' not in view
    assert 'source_event_ids' not in view


def test_npc_forging_requires_actual_workshop_and_consumes_material(game):
    c,app,s=game
    npc=next(a for a in s['actors'] if a['kind']=='npc')
    station=next(p for p in r9.WORKSTATIONS if p['kind']=='anvil')
    def prepare(conn,state):
        actor=next(a for a in state.actors if a.id==npc['id'])
        actor.tile=Tile.model_validate(station['tile'])
        for kind in ('wood','iron','iron'):
            r9.material(state,actor.id,kind,r9.source_event(conn,state))
        for a in state.actors:
            if a.id!=actor.id and a.kind=='npc':a.task_id='busy-r9-test'
    s=edit(app,s,prepare)
    before={i['id'] for i in s['items'] if i['owner_id']==npc['id']}
    material_before={i['id'] for i in s['items'] if i['owner_id']==npc['id'] and i['material_id'] in ('wood','iron')}
    s=heartbeat(c,s)
    made=[i for i in s['items'] if i['owner_id']==npc['id'] and i['id'] not in before]
    assert made and any(i['base_type']=='sword' for i in made)
    assert any(i['origin_event_ids'] for i in made)
    material_after={i['id'] for i in s['items'] if i['owner_id']==npc['id'] and i['material_id'] in ('wood','iron')}
    assert len(material_before-material_after)==3


def test_no_magical_forging_far_from_any_real_station(game):
    c,app,s=game
    npc=next(a for a in s['actors'] if a['kind']=='npc')
    far=Tile(x=65,y=65)
    assert r9.nearest_workstation(far)[1]>36
    def prepare(conn,state):
        actor=next(a for a in state.actors if a.id==npc['id'])
        actor.tile=far
        for kind in ('wood','iron','iron'):
            r9.material(state,actor.id,kind,r9.source_event(conn,state))
        for a in state.actors:
            if a.id!=actor.id and a.kind=='npc':a.task_id='busy-r9-test'
    s=edit(app,s,prepare)
    before={i['id'] for i in s['items'] if i['owner_id']==npc['id']}
    s=heartbeat(c,s)
    assert before <= {i['id'] for i in s['items'] if i['owner_id']==npc['id']}


def test_npc_aid_has_real_consumption_and_provenance(game):
    c,app,s=game
    a,b=[actor for actor in s['actors'] if actor['kind']=='npc'][:2]
    def prepare(conn,state):
        donor=next(x for x in state.actors if x.id==a['id'])
        target=next(x for x in state.actors if x.id==b['id'])
        donor.tile=Tile(x=66,y=169);donor.hp=donor.max_hp
        target.tile=Tile(x=67,y=169);target.hp=5
        metadata=life.read(conn,state.world_id)
        metadata['people'][donor.id]['personality']['generosity']=.95
        life.write(conn,state.world_id,metadata)
        life._potion(state,donor.id,r9.source_event(conn,state))
        for x in state.actors:
            if x.kind=='npc' and x.id not in (donor.id,target.id):x.task_id='busy-r9-test'
        target.task_id='busy-r9-test'
    s=edit(app,s,prepare)
    s=heartbeat(c,s)
    assert next(x for x in s['actors'] if x['id']==b['id'])['hp']==30
    assert not any(i['owner_id']==a['id'] and i['material_id']=='healing' for i in s['items'])
    with app.state.store.connection() as conn:
        row=conn.execute("SELECT body FROM events WHERE world_id=? AND body LIKE '%npc_aided%'",(s['world_id'],)).fetchone()
        assert row is not None
        relation=life._relation(life.read(conn,s['world_id']),b['id'],a['id'])
        assert relation['trust']>=6 and relation['sources']


def test_client_uses_independent_model_lane_and_back_navigation():
    api=(ROOT/'game/net/game_api.gd').read_text(encoding='utf-8')
    screens=(ROOT/'game/ui/play_windows.gd').read_text(encoding='utf-8')
    assert 'model_http=HTTPRequest.new()' in api
    assert 'model_http.request_completed.connect(_model_response)' in api
    assert 'if operation=="dialogue":' in api
    assert 'model_queue.append(job)' in api
    assert 'elif screen == "shop": back_from_shop()' in screens


def test_model_configuration_refuses_false_success():
    settings=(ROOT/'game/ui/play_windows.gd').read_text(encoding='utf-8')
    assert settings.count('key_input = input_line(column, "API Key') == 1
    assert 'if is_instance_valid(use_model) and use_model.button_pressed and not bool(data.get("configured",false)):' in settings
