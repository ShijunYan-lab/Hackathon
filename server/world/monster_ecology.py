"""Canonical monster species, client-visible appearance keys and combat stat budgets.

Actual hits/ownership remain authoritative in combat.py / world transaction logic.
The Godot client interprets appearance keys only for animation and short-range steering.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Species:
    title: str
    hp: int
    armor: int
    damage: int
    cooldown_s: float
    weapon: str = 'sword'
    tags: tuple[str, ...] = ()

SPECIES: dict[str, Species] = {
    'wolf': Species('灰狼', 25, 0, 3, 1.20, 'sword', ('pack', 'melee')),
    'boar': Species('野猪', 34, 1, 5, 1.65, 'sword', ('charge', 'melee')),
    'spider': Species('巨蛛', 20, 0, 4, 0.85, 'sword', ('ambush', 'melee')),
    'ghoul': Species('食尸鬼', 35, 1, 5, 1.20, 'sword', ('pursuit', 'melee')),
    'swamp': Species('沼泽潜伏兽', 42, 2, 6, 1.45, 'sword', ('slow', 'heavy')),
    'raven': Species('腐鸦', 17, 0, 3, 0.92, 'sword', ('skittish', 'melee')),
    'wisp': Species('林地幽灵', 24, 0, 4, 1.35, 'staff', ('ranged',)),
    'hostile_0': Species('强盗', 42, 1, 6, 0.80, 'sword', ('human', 'melee')),
    'hostile_1': Species('盗猎者', 34, 0, 5, 1.05, 'bow', ('human', 'ranged')),
    'hostile_2': Species('掠夺者', 52, 1, 7, 0.90, 'axe', ('human', 'melee')),
    'hostile_3': Species('沼泽女巫', 36, 0, 6, 1.10, 'staff', ('human', 'ranged')),
    'hostile_4': Species('异端教徒', 38, 0, 5, 1.10, 'staff', ('human', 'ranged')),
}

# Weighted starting/wilderness appearances. Town safety is enforced separately.
SPAWN_POOL = (
    'wolf', 'wolf', 'wolf', 'wolf', 'wisp', 'boar', 'boar',
    'spider', 'ghoul', 'swamp', 'raven',
    'hostile_0', 'hostile_0', 'hostile_1', 'hostile_2', 'hostile_3', 'hostile_4',
)
ELITE_POOL = ('wolf', 'boar', 'spider', 'ghoul', 'swamp', 'raven')


def get_species(appearance: str) -> Species:
    return SPECIES[appearance.removeprefix('elite_')]


def apply_species(actor, weapon) -> None:
    """Set health/weapon for a fresh spawn; never alter actor IDs or inventory ownership."""
    species = get_species(actor.appearance_key)
    elite = actor.appearance_key.startswith('elite_')
    actor.name = ('精英' if elite else '') + species.title
    goal_hp = round(species.hp * (2 if elite else 1))
    # Pydantic validates each assignment, so shrink hp before shrinking max_hp.
    if actor.hp > goal_hp:
        actor.hp = goal_hp
    actor.max_hp = goal_hp
    actor.hp = goal_hp
    actor.armor = species.armor + (2 if elite else 0)
    weapon.name = '天生攻击' if 'human' not in species.tags else species.title + '的武器'
    weapon.stats.damage = species.damage + (3 if elite else 0)
    weapon.stats.cooldown_s = species.cooldown_s


def is_hostile_human(appearance: str) -> bool:
    return appearance.startswith('hostile_')
