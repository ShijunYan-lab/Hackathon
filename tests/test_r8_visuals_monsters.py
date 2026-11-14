"""R8 art contract / monster ecology tests (no Godot executable required)."""
import json
from pathlib import Path

import struct
import zlib

from server.world.monster_ecology import SPECIES, SPAWN_POOL, ELITE_POOL, apply_species, get_species
from shared.protocol import ActorState, ItemState, ItemStats, Tile

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'game' / 'assets' / 'r7'
ANIMS = ART / 'animations'
ACTIONS = {'idle':3, 'run':4, 'sprint':4, 'attack':5, 'hurt':2, 'death':4, 'dodge':3}
CREATURES = [f'{species}_{tier}' for species in ['wolf','boar','spider','ghoul','swamp','raven'] for tier in (0,1)] + [f'hostile_{x}' for x in range(5)]


def png_info(path: Path) -> tuple[int, int]:
    """Read/decode PNG without requiring Pillow in the game runtime environment."""
    raw = path.read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n', path
    width, height = struct.unpack('>II', raw[16:24])
    assert raw[25] == 6, path  # All new PNGs use RGBA
    cursor = 8
    idat = bytearray()
    while cursor < len(raw):
        size = struct.unpack('>I', raw[cursor:cursor+4])[0]
        kind = raw[cursor+4:cursor+8]
        data = raw[cursor+8:cursor+8+size]
        if kind == b'IDAT': idat.extend(data)
        cursor += 12 + size
        if kind == b'IEND': break
    uncompressed = zlib.decompress(idat)
    assert len(uncompressed) == height * (width*4+1), path
    # The filtered alpha channel must carry some non-transparent pixels.
    assert any(uncompressed[y * (width*4+1)+1+3::4][:width].count(0) < width for y in range(height)), path
    return width, height


def test_inventory_and_ground_loot_art_complete():
    keys = ['coin','stone','unknown_item','herb','wood','iron','potion','bandage','cloth','food','mushroom']
    keys += [f'{type_name}_{i}' for type_name in ['sword','armor','helmet','boots','bow','crossbow','axe','hammer','staff'] for i in range(5)]
    for key in keys:
        width, height = png_info(ART / f'{key}.png')
        assert width >= 32 and height >= 32, key


def test_scene_props_are_valid_and_have_art():
    doc = json.loads((ROOT / 'game/maps/scene_props.json').read_text(encoding='utf-8'))
    ids = [x['id'] for x in doc['props']]
    assert len(ids) == len(set(ids)) and len(ids) >= 15
    for prop in doc['props']:
        assert 0 <= prop['tile']['x'] < 320 and 0 <= prop['tile']['y'] < 224, prop
        assert (ART / f"{prop['kind']}.png").exists(), prop
        assert prop['description']


def test_creatures_frames_have_all_states_and_nonblank_alpha():
    for species in CREATURES:
        for action, count in ACTIONS.items():
            for i in range(count):
                assert png_info(ANIMS / f'{species}_{action}_{i}.png') == (80,80), (species,action,i)


def test_guard_frames_use_original_individual_png_files():
    for guard in range(5):
        for row, num in enumerate([3,4,5,4]):
            for i in range(num):
                assert png_info(ART / f'guard_{guard}_{row}_{i}.png') == (48,64)
    godot = (ROOT/'game/maps/network_npc.gd').read_text(encoding='utf-8')
    assert '_build_guard_visual' in godot
    for species in ('wolf','boar','spider','ghoul','swamp','raven'):
        assert f'"{species}"' in godot


def test_all_spawn_species_have_specific_stats_and_visuals():
    assert set(SPAWN_POOL).issubset(SPECIES)
    assert set(ELITE_POOL).issubset(SPECIES)
    for species in SPECIES:
        assert get_species(species).hp >= 15
        if species != 'wisp':
            name = f'{species}_0' if species in ['wolf','boar','spider','ghoul','swamp','raven'] else species
            assert (ANIMS / f'{name}_idle_0.png').exists()
    assert (ROOT/'game/actors/assets/sprites/wisp.png').exists()


def test_server_applies_distinct_monster_stats_and_elite_scaling():
    assert get_species('elite_wolf') == get_species('wolf')
    assert get_species('hostile_1').weapon == 'bow'
    assert get_species('wolf').hp < get_species('boar').hp
    for appearance in ('wolf', 'elite_wolf', 'hostile_1', 'spider', 'elite_raven'):
        actor = ActorState(id='m', kind='monster', name='X', alive=True, hp=80, max_hp=80,
                           armor=0, region_id='overworld', tile=Tile(x=10, y=15),
                           appearance_key=appearance)
        weapon = ItemState(id='blade', name='旧武器', base_type='sword', quality='common',
                           material_id='iron', owner_id='m', stats=ItemStats(damage=1, cooldown_s=1.0, armor=0))
        apply_species(actor, weapon)
        assert actor.hp == actor.max_hp
        assert actor.max_hp == get_species(appearance).hp * (2 if appearance.startswith('elite_') else 1)
        assert weapon.stats.damage == get_species(appearance).damage + (3 if appearance.startswith('elite_') else 0)
        assert weapon.stats.cooldown_s == get_species(appearance).cooldown_s
        assert actor.name != 'X'
