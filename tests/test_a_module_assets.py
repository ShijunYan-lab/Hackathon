"""Static integration tests only: does not execute the Godot engine."""
from pathlib import Path
import re
import struct
import hashlib

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'game'


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    return struct.unpack('>II', data[16:24])


def test_player_animation_sheet_has_seven_rows():
    assert png_dimensions(GAME/'actors/assets/sprites/knight.png') == (128, 224)


def test_two_weapons_have_distinct_valid_textures():
    sword = GAME/'actors/assets/weapons/sword.png'
    axe = GAME/'actors/assets/weapons/axe.png'
    assert png_dimensions(sword) == (32, 32)
    assert png_dimensions(axe) == (32, 32)
    assert hashlib.sha256(sword.read_bytes()).digest() != hashlib.sha256(axe.read_bytes()).digest()


def test_embedded_script_resources_exist():
    source = [p for p in GAME.rglob('*.tscn')] + [p for p in GAME.rglob('*.gd')]
    missing = []
    for path in source:
        content = path.read_text(encoding='utf-8')
        for rel in re.findall(r'res://([A-Za-z0-9_./-]+\.(?:gd|tscn|png))', content):
            if not (GAME/rel).is_file():
                missing.append((str(path.relative_to(ROOT)), rel))
    assert not missing, missing


def test_hit_and_task_fields_align_with_v1():
    from shared.protocol import HitPayload, TaskReportPayload
    assert {'attack_id','attacker_id','target_id','weapon_id','region_id','attacker_tile','target_tile'} == set(HitPayload.model_fields)
    assert {'task_id','actor_id','status','region_id','tile','failure_code'} == set(TaskReportPayload.model_fields)
    code = (GAME/'actors/player.gd').read_text(encoding='utf-8')
    for field in HitPayload.model_fields:
        assert f'"{field}"' in code
    npc = (GAME/'actors/npc.gd').read_text(encoding='utf-8')
    for field in TaskReportPayload.model_fields:
        assert f'"{field}"' in npc


def test_client_never_uses_old_agent_command_names():
    for p in (GAME/'actors/player.gd', GAME/'actors/npc.gd'):
        content = p.read_text(encoding='utf-8')
        for invalid in ('COMBAT_HIT', 'REPORT_INTENT', 'START_DODGE', 'expected_revision'):
            assert invalid not in content


def test_starter_scene_files_and_input_labels_present():
    assert (GAME/'tests/a_combat_demo.tscn').is_file()
    assert (GAME/'tests/a_forest_demo.tscn').is_file()
    player = (GAME/'actors/player.gd').read_text(encoding='utf-8')
    mapping = (GAME/'controllers/input_defaults.gd').read_text(encoding='utf-8')
    assert '"sprint"' in player and '"dodge"' in player
    assert 'KEY_SHIFT' in mapping and 'MOUSE_BUTTON_LEFT' in mapping
