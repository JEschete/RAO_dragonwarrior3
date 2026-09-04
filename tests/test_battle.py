from game.battle import SPELLS, learned_battle_spells, selected_battle_spell


def test_spell_knowledge_uses_rom_costs_targets_and_ranges() -> None:
    assert SPELLS[0x00].name == "Blaze"
    assert SPELLS[0x00].mp_cost == 2
    assert SPELLS[0x00].target == "One enemy"
    assert "8-13 damage" in SPELLS[0x00].effect
    assert SPELLS[0x11].name == "Lightning"
    assert SPELLS[0x11].mp_cost == 30
    assert SPELLS[0x11].target == "All enemies"
    assert "175-224 damage" in SPELLS[0x11].effect


def test_hero_spell_bits_follow_battle_menu_order() -> None:
    spells = learned_battle_spells(
        bytes((0b10000011, 0b00000001, 0, 0, 0, 0, 0, 0)),
        job=0,
    )

    assert [spell.name for spell in spells] == ["Blaze", "Heal", "Sleep", "Zap"]


def test_changed_class_retains_wizard_and_pilgrim_spells() -> None:
    spells = learned_battle_spells(
        bytes((0b01000001, 0, 0, 0, 0b00000011, 0, 0, 0)),
        job=3,
    )

    assert [spell.name for spell in spells] == ["Blaze", "Bang", "Sap", "Heal"]


def test_goof_off_cannot_use_retained_spells() -> None:
    assert learned_battle_spells(bytes((0xFF,)) * 8, job=7) == ()


def test_selected_spell_requires_a_committed_spell_action() -> None:
    ram = bytearray(0x800)
    ram[0x054C] = 0x91
    ram[0x0558] = 0x32

    assert selected_battle_spell(ram, 0) == SPELLS[0x32]

    ram[0x054C] = 0x80
    assert selected_battle_spell(ram, 0) is None
