from dataclasses import dataclass


SPELL_FLAGS_ADDRESS = 0x079C
SELECTED_ACTION_ADDRESS = 0x054C
SELECTED_MOVE_ADDRESS = 0x0558

HERO_BATTLE_SPELL_IDS = (
    0x00, 0x1A, 0x15, 0x2A, 0x03, 0x26, 0x24, 0x22,
    0x10, 0x1B, 0x04, 0x1C, 0x07, 0x20, 0x11, 0x1F,
)
WIZARD_BATTLE_SPELL_IDS = (
    0x00, 0x2D, 0x09, 0x2E, 0x03, 0x26, 0x06, 0x18,
    0x01, 0x17, 0x0A, 0x0C, 0x04, 0x32, 0x07, 0x30,
    0x02, 0x27, 0x0B, 0x29, 0x05, 0x28, 0x08, 0x33,
)
PILGRIM_BATTLE_SPELL_IDS = (
    0x2B, 0x1A, 0x15, 0x34, 0x0D, 0x19, 0x25, 0x22,
    0x2C, 0x1B, 0x12, 0x35, 0x0E, 0x24, 0x16, 0x23,
    0x31, 0x1C, 0x13, 0x1E, 0x0F, 0x20, 0x14, 0x21,
)

SPELL_NAMES = (
    "Blaze", "Blazemore", "Blazemost", "Firebal", "Firebane", "Firevolt",
    "Bang", "Boom", "Explodet", "IceBolt", "Snowblast", "Snowstorm",
    "IceSpears", "Infernos", "Infermore", "Infermost", "Zap", "Lightning",
    "Beat", "Defeat", "Sacrifice", "Expel", "Limbo", "RobMagic", "Slow",
    "SpeedUp", "Heal", "Healmore", "Healall", "Unused", "Healus",
    "Healusall", "Vivify", "Revive", "Sleep", "Awake", "StopSpell",
    "Surround", "Return", "Chaos", "Transform", "BeDragon", "Ironize",
    "Sap", "Defence", "Upper", "Increase", "Increase 2", "Bounce",
    "Barrier", "Bikill", "Chance", "Antidote", "NumbOff", "CurseOff",
    "Repel", "Day-Night", "Open", "X-Ray", "Outside", "Invisible",
    "StepGuard",
)
SPELL_MP_COSTS = (
    2, 6, 12, 4, 6, 12, 5, 9, 18, 3, 6, 12, 9, 4, 6, 9, 8, 30,
    7, 7, 1, 2, 7, 0, 3, 3, 3, 5, 7, 0, 18, 62, 10, 20, 3, 3,
    3, 4, 8, 5, 12, 24, 6, 3, 4, 3, 4, 4, 8, 6, 6, 20, 2, 6,
    18, 4, 12, 0, 3, 8, 15, 2,
)

_DAMAGE_SPELLS = {
    0x00: ("One enemy", 8, 6),
    0x01: ("One enemy", 70, 20),
    0x02: ("One enemy", 160, 40),
    0x03: ("Enemy group", 16, 8),
    0x04: ("Enemy group", 30, 12),
    0x05: ("Enemy group", 88, 24),
    0x06: ("All enemies", 16, 8),
    0x07: ("All enemies", 52, 16),
    0x08: ("All enemies", 120, 40),
    0x09: ("One enemy", 25, 10),
    0x0A: ("Enemy group", 42, 16),
    0x0B: ("Enemy group", 88, 24),
    0x0C: ("All enemies", 60, 20),
    0x0D: ("Enemy group", 8, 16),
    0x0E: ("Enemy group", 25, 30),
    0x0F: ("Enemy group", 60, 60),
    0x10: ("One enemy", 70, 20),
    0x11: ("All enemies", 175, 50),
}

_SPELL_BEHAVIOR = {
    0x12: ("One enemy", "Attempts to defeat one enemy instantly."),
    0x13: ("Enemy group", "Attempts to defeat an enemy group instantly."),
    0x14: ("All enemies", "The caster falls, then attempts to defeat every enemy."),
    0x15: ("Enemy group", "Attempts to expel an enemy group without battle rewards."),
    0x16: ("One enemy", "Attempts to remove one enemy from battle."),
    0x17: ("One enemy", "Steals MP from one enemy."),
    0x18: ("Enemy group", "Attempts to reduce an enemy group's agility."),
    0x19: ("All allies", "Raises the agility of the whole party."),
    0x1A: ("One ally", "Restores 30-39 HP to one ally."),
    0x1B: ("One ally", "Restores 75-94 HP to one ally."),
    0x1C: ("One ally", "Restores up to 255 HP to one ally."),
    0x1E: ("All allies", "Restores 62-77 HP to each living ally."),
    0x1F: ("All allies", "Restores a large amount of HP to each living ally."),
    0x20: ("One fallen ally", "May revive one fallen ally at half maximum HP."),
    0x21: ("One fallen ally", "Revives one fallen ally at full HP."),
    0x22: ("Enemy group", "Attempts to put an enemy group to sleep."),
    0x23: ("All allies", "Wakes sleeping party members."),
    0x24: ("Enemy group", "Attempts to prevent an enemy group from casting spells."),
    0x25: ("Enemy group", "Attempts to reduce an enemy group's physical accuracy."),
    0x26: ("Party", "Attempts to escape battle and return to a recorded town."),
    0x27: ("One enemy", "Attempts to confuse one enemy."),
    0x28: ("One ally", "Copies another party member's combat abilities."),
    0x29: ("Caster", "Turns the caster into a dragon with 300 ATK, 200 DEF, and 100 AGI."),
    0x2A: ("All allies", "Turns the party to iron, preventing actions and damage temporarily."),
    0x2B: ("One enemy", "Attempts to reduce one enemy's defense."),
    0x2C: ("Enemy group", "Attempts to reduce an enemy group's defense."),
    0x2D: ("One ally", "Raises one ally's defense."),
    0x2E: ("All allies", "Raises the whole party's defense."),
    0x2F: ("All enemies", "Raises the defense of all enemies."),
    0x30: ("Caster", "Creates a wall that reflects spells aimed at the caster."),
    0x31: ("All allies", "Reduces breath damage received by the whole party."),
    0x32: ("One ally", "Doubles one ally's attack power."),
    0x33: ("Varies", "Invokes a random battle effect."),
    0x34: ("One ally", "Cures poison on one ally."),
    0x35: ("One ally", "Cures paralysis on one ally."),
}


@dataclass(frozen=True, slots=True)
class EnemyProfile:
    level: int
    max_hp: int
    max_mp: int
    attack: int
    agility: int
    defense: int
    experience: int
    gold: int


@dataclass(frozen=True, slots=True)
class SpellInfo:
    spell_id: int
    name: str
    mp_cost: int
    target: str
    effect: str

    def tooltip(self, current_mp: int | None = None) -> str:
        availability = f"\nCaster MP: {current_mp}" if current_mp is not None else ""
        return (
            f"{self.name}\nBase MP cost: {self.mp_cost} · Target: {self.target}"
            f"{availability}\n{self.effect}"
        )


def _build_spells() -> dict[int, SpellInfo]:
    spells = {}
    for spell_id, (target, base, span) in _DAMAGE_SPELLS.items():
        spells[spell_id] = SpellInfo(
            spell_id,
            SPELL_NAMES[spell_id],
            SPELL_MP_COSTS[spell_id],
            target,
            f"Deals {base}-{base + span - 1} damage before resistance.",
        )
    for spell_id, (target, effect) in _SPELL_BEHAVIOR.items():
        spells[spell_id] = SpellInfo(
            spell_id,
            SPELL_NAMES[spell_id],
            SPELL_MP_COSTS[spell_id],
            target,
            effect,
        )
    return spells


SPELLS = _build_spells()


def learned_battle_spells(spell_flags: bytes, job: int) -> tuple[SpellInfo, ...]:
    flags = bytes(spell_flags[:8]).ljust(8, b"\x00")
    if job == 0:
        spell_ids = _known_spells(flags[:2], HERO_BATTLE_SPELL_IDS)
    elif job == 7:
        spell_ids = ()
    else:
        spell_ids = _known_spells(flags[:3], WIZARD_BATTLE_SPELL_IDS)
        spell_ids += _known_spells(flags[4:7], PILGRIM_BATTLE_SPELL_IDS)
    spells = []
    seen = set()
    for spell_id in spell_ids:
        if spell_id in SPELLS and spell_id not in seen:
            spells.append(SPELLS[spell_id])
            seen.add(spell_id)
    return tuple(spells)


def selected_battle_spell(ram: bytes, player_index: int) -> SpellInfo | None:
    if not 0 <= player_index < 4:
        return None
    if len(ram) <= SELECTED_MOVE_ADDRESS + player_index:
        return None
    action = ram[SELECTED_ACTION_ADDRESS + player_index]
    if action & 0x70 != 0x10:
        return None
    return SPELLS.get(ram[SELECTED_MOVE_ADDRESS + player_index])


def _known_spells(flags: bytes, spell_ids: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(
        spell_id
        for index, spell_id in enumerate(spell_ids)
        if index // 8 < len(flags) and flags[index // 8] & (1 << (index % 8))
    )
