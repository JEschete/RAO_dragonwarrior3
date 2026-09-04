import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from retroarch_overlay.adapters import ContentHashResolver
from game.adapter import (
    RAM_SIZE,
    SRAM_ADDRESS,
    SRAM_READ_SIZE,
    DragonWarrior3Adapter,
)
from game.battle import EnemyProfile
from retroarch_overlay.core.retroachievements import RAProgress
from retroarch_overlay.infrastructure.retroachievements import load_ra_progress
from retroarch_overlay.models import MapOverlay, MapWaypoint, PanelRow, RetroArchStatus
from retroarch_overlay.retroarch import RetroArchError


class FakeMemory:
    def __init__(self) -> None:
        self.ram = bytearray(RAM_SIZE)
        self.sram = bytearray(SRAM_READ_SIZE)
        self.ram[0x002F] = 0
        self.ram[0x002A:0x002C] = bytes((12, 34))
        self.ram[0x008A:0x008C] = bytes((0x12, 0x34))
        self.ram[0x0700:0x0704] = bytes((20, 18, 17, 0))
        self.ram[0x0718:0x071C] = bytes((0, 1, 2, 0))
        self.ram[0x07C1:0x07C5] = bytes((0, 1, 2, 0xFF))
        self.ram[0x077C:0x079C] = bytes((0xFF,)) * 32
        self.ram[0x071C:0x071E] = (100).to_bytes(2, "little")
        self.ram[0x0724:0x0726] = (120).to_bytes(2, "little")
        self.ram[0x072C:0x072E] = (30).to_bytes(2, "little")
        self.ram[0x0734:0x0736] = (40).to_bytes(2, "little")
        self.ram[0x073D:0x0744:2] = bytes((0x80, 0x80, 0x80, 0))
        self.ram[0x07BC:0x07BF] = (12345).to_bytes(3, "little")
        self.sram[0x0D:0x8D] = bytes((0xFF,)) * 128

    def read_memory(self, address: int, size: int) -> bytes:
        if (address, size) == (0, RAM_SIZE):
            return bytes(self.ram)
        if (address, size) == (SRAM_ADDRESS, SRAM_READ_SIZE):
            return bytes(self.sram)
        raise AssertionError(f"Unexpected read: 0x{address:04X}, {size}")


class DescriptorlessMemory:
    def read_memory(self, _address: int, _size: int) -> bytes:
        raise RetroArchError("RetroArch core has no descriptor for that address")


class DragonWarrior3AdapterTests(unittest.TestCase):
    def test_loads_account_achievement_progress(self) -> None:
        response = BytesIO(
            b'{"Achievements":{"50439":{"DateEarned":"2024-01-01"},'
            b'"50440":{"DateEarned":null}}}'
        )
        response.__enter__ = lambda: response
        response.__exit__ = lambda *_: None
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "retroarch.cfg"
            config.write_text('cheevos_username = "PlayerOne"\n', encoding="utf-8")
            progress = load_ra_progress(
                config, 1667, "web-api-key", lambda *_args, **_kwargs: response
            )
        self.assertEqual(progress.username, "PlayerOne")
        self.assertEqual(progress.unlocked_ids, {50439})

    def test_account_unlocks_are_shown_with_session_detections(self) -> None:
        progress = RAProgress("PlayerOne", frozenset({50439}))
        snapshot = DragonWarrior3Adapter(progress).snapshot(FakeMemory())
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "1/50 unlocked · PlayerOne")
        self.assertIn("Now You Can Open Doors · account", achievements.rows[2].text)

    def test_supports_official_normalized_hash(self) -> None:
        adapter = DragonWarrior3Adapter()
        status = RetroArchStatus("PLAYING", "Mesen", "Dragon Warrior III", "a86a5318")
        self.assertTrue(adapter.supports(status, "16a03048ce659d3d733026b6b72f2470"))
        self.assertFalse(adapter.supports(status, "0" * 32))

    def test_supports_title_when_rom_is_outside_search_roots(self) -> None:
        adapter = DragonWarrior3Adapter()
        status = RetroArchStatus(
            "PLAYING", "nes", "Dragon Warrior III (USA)", "5716bd04"
        )

        self.assertTrue(adapter.supports(status))
        self.assertFalse(adapter.supports(status, "0" * 32))

    def test_nes_hash_resolver_ignores_ines_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "Dragon Warrior III.nes"
            rom.write_bytes(b"NES\x1a" + bytes(12) + b"cartridge")
            status = RetroArchStatus("PLAYING", "Mesen", rom.name)
            resolved = ContentHashResolver((Path(directory),)).resolve(status)
        import hashlib

        self.assertEqual(resolved, hashlib.md5(b"cartridge", usedforsecurity=False).hexdigest())

    def test_nes_hash_resolver_normalizes_hash_when_status_uses_raw_crc(self) -> None:
        import hashlib
        import zlib

        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "Dragon Warrior III.nes"
            data = b"NES\x1a" + bytes(12) + b"cartridge"
            rom.write_bytes(data)
            status = RetroArchStatus("PLAYING", "Mesen", rom.name, f"{zlib.crc32(data):08x}")
            resolved = ContentHashResolver((Path(directory),)).resolve(status)
        self.assertEqual(resolved, hashlib.md5(b"cartridge", usedforsecurity=False).hexdigest())

    def test_first_snapshot_starts_at_zero_and_shows_useful_state(self) -> None:
        memory = FakeMemory()
        snapshot = DragonWarrior3Adapter().snapshot(memory)
        self.assertEqual(snapshot.location, "Main World · (12,34)")
        self.assertEqual(snapshot.map_position.x, 12)
        self.assertEqual(snapshot.map_position.y, 34)
        self.assertTrue(snapshot.map_position.is_world)
        self.assertTrue(snapshot.supports_caught_filter)
        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: recruit a full party")
        self.assertEqual(
            tuple(action.label for action in objective.actions),
            ("OPEN ROUTE PLAN", "OPEN KEY ITEM UNLOCKS", "OPEN RA PRIORITIES"),
        )
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "0/50 detected this session")
        self.assertEqual(achievements.rows[1].text, "32 exact detectors active · fresh baseline")
        party = next(section for section in snapshot.sections if section.title == "Party")
        self.assertIn("Hero Lv 20", party.rows[0].text)
        resources = next(section for section in snapshot.sections if section.title == "Resources")
        self.assertIn("Gold 12,345", resources.rows[2].text)

    def test_party_uses_rom_decoded_character_names(self) -> None:
        memory = FakeMemory()
        memory.ram[0x075C:0x0764] = b"JACOB\xff\xff\xff"
        adapter = DragonWarrior3Adapter(
            decode_text=lambda encoded: encoded.rstrip(b"\xff").decode("ascii").title()
        )

        snapshot = adapter.snapshot(memory)

        party = next(section for section in snapshot.sections if section.title == "Party")
        self.assertTrue(party.rows[0].text.startswith("Jacob · Hero Lv 20"))

    def test_snapshot_has_no_map_document_without_plugin_resources(self) -> None:
        snapshot = DragonWarrior3Adapter().snapshot(FakeMemory())

        self.assertIsNone(snapshot.map_document)

    def test_descriptorless_core_reports_compatible_core_options(self) -> None:
        with self.assertRaisesRegex(RetroArchError, "Mesen or FCEUmm"):
            DragonWarrior3Adapter().snapshot(DescriptorlessMemory())

    def test_observed_full_party_and_two_sages_increment_counter(self) -> None:
        adapter = DragonWarrior3Adapter()
        memory = FakeMemory()
        adapter.snapshot(memory)
        memory.ram[0x0703] = 10
        memory.ram[0x07C4] = 3
        memory.ram[0x0743] = 0x80
        memory.ram[0x0719:0x071C] = bytes((3, 3, 4))
        snapshot = adapter.snapshot(memory)
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "3/50 detected this session")
        detected = " ".join(row.text for row in achievements.rows)
        self.assertIn("With a Little Help from My Friends", detected)
        self.assertIn("A New Line of Work", detected)
        self.assertIn("So Much Magic", detected)

    def test_new_unique_item_is_named_and_detects_achievement(self) -> None:
        adapter = DragonWarrior3Adapter()
        memory = FakeMemory()
        adapter.snapshot(memory)
        memory.ram[0x077C] = 0x58
        snapshot = adapter.snapshot(memory)
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "1/50 detected this session")
        self.assertIn("Now You Can Open Doors", achievements.rows[1].text)
        self.assertEqual(snapshot.sections[-1].rows[0].text, "Thief's Key")

    def test_recent_and_vault_items_use_complete_rom_name_lookup(self) -> None:
        memory = FakeMemory()
        adapter = DragonWarrior3Adapter(item_name=lambda item_id: f"Named {item_id:02X}")
        adapter.snapshot(memory)
        memory.ram[0x077C] = 0x3D
        memory.sram[0x0D] = 0x40

        snapshot = adapter.snapshot(memory)

        recent = next(section for section in snapshot.sections if section.title == "New items observed")
        self.assertEqual(recent.rows[0].text, "Named 3D")
        progress = next(section for section in snapshot.sections if section.title == "Adventure progress")
        vault = next(action for action in progress.actions if action.label == "OPEN VAULT AUDIT")
        self.assertEqual(vault.rows[0].text, "Named 40 ×1")

    def test_empty_slots_are_not_reported_as_items_but_cypress_stick_is_valid(self) -> None:
        memory = FakeMemory()
        memory.ram[0x077C] = 0x00

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        progress = next(section for section in snapshot.sections if section.title == "Adventure progress")
        self.assertEqual(progress.rows[3].text, "Vault items 0/128")
        vault = next(action for action in progress.actions if action.label == "OPEN VAULT AUDIT")
        self.assertEqual(vault.rows, (PanelRow("Vault is empty"),))

    def test_moving_item_to_vault_does_not_detect_it_twice(self) -> None:
        adapter = DragonWarrior3Adapter()
        memory = FakeMemory()
        memory.ram[0x077C] = 0x58
        adapter.snapshot(memory)
        memory.ram[0x077C] = 0
        memory.sram[0x0D] = 0x58
        snapshot = adapter.snapshot(memory)
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "0/50 detected this session")

    def test_swapping_party_members_is_not_a_profession_change(self) -> None:
        adapter = DragonWarrior3Adapter()
        memory = FakeMemory()
        adapter.snapshot(memory)
        memory.ram[0x0719:0x071B] = bytes((2, 1))
        memory.ram[0x07C2:0x07C4] = bytes((2, 1))
        snapshot = adapter.snapshot(memory)
        achievements = next(section for section in snapshot.sections if section.title == "RetroAchievements")
        self.assertEqual(achievements.rows[0].text, "0/50 detected this session")

    def test_key_items_drive_objective_unlock_and_orb_guidance(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0703] = 10
        memory.ram[0x07C4] = 3
        memory.ram[0x0743] = 0x80
        for slot, item_id in enumerate((0x58, 0x59, 0x4F, 0x5A, 0x77, 0x78)):
            memory.ram[0x077C + slot] = item_id
        memory.sram[0xB8] = 0x80
        memory.sram[0xCE] = 0x03
        snapshot = DragonWarrior3Adapter().snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: orb hunt · 2/6 found")
        unlocks = next(section for section in snapshot.sections if section.title == "Unlocks")
        self.assertEqual(unlocks.rows[0].text, "Key items 4/12")
        orbs = next(section for section in snapshot.sections if section.title == "Orb route")
        self.assertIn("Purple Orb", orbs.rows[1].text)
        self.assertEqual(orbs.actions[0].label, "OPEN ORB CHECKLIST")

    def test_placed_orb_is_not_reported_missing_after_item_is_consumed(self) -> None:
        memory = FakeMemory()
        memory.sram[0xCE] = 0x01
        memory.sram[0xCF] = 0x01

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        orbs = next(section for section in snapshot.sections if section.title == "Orb route")
        self.assertNotIn("Silver Orb", orbs.rows[1].text)
        silver = orbs.actions[0].rows[0]
        self.assertTrue(silver.caught)

    def test_formation_and_live_flag_override_stale_stats(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0703] = 25
        memory.ram[0x0722:0x0724] = (200).to_bytes(2, "little")
        memory.ram[0x072A:0x072C] = (200).to_bytes(2, "little")

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: recruit a full party")
        resources = next(section for section in snapshot.sections if section.title == "Resources")
        self.assertIn("Alive 3/4", resources.rows[0].text)

        memory.ram[0x07C4] = 3
        party = DragonWarrior3Adapter().snapshot(memory)
        fourth_member = next(section for section in party.sections if section.title == "Party").rows[3]
        self.assertIn("DEAD", fourth_member.text)

    def test_battle_lists_enemy_groups_and_hp(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0032] = 0xFD
        memory.ram[0x056D] = 0x44
        memory.ram[0x0571] = 3
        memory.ram[0x0500:0x0502] = (77).to_bytes(2, "little")
        memory.ram[0x0510] = 12
        memory.ram[0x0518] = 28
        memory.ram[0x0520:0x0522] = (64).to_bytes(2, "little")
        memory.ram[0x0530] = 0x21
        memory.ram[0x0051] = 5
        memory.ram[0x063F] = 19
        snapshot = DragonWarrior3Adapter().snapshot(memory)
        self.assertTrue(snapshot.location.startswith("Battle"))
        self.assertEqual(snapshot.sections[0].title, "Battle")
        battle = next(section for section in snapshot.sections if section.title == "Battle")
        self.assertEqual(battle.rows[0].text, "Groups · Enemy 0x44 ×3")
        self.assertEqual(
            battle.rows[1].text,
            "E1 Enemy 0x44 · HP 77 · MP 12 · AGI 28 · DEF 64 · Sleep/Stopspell",
        )
        self.assertEqual(battle.rows[2].text, "Last hit · E2 · 19 damage")
        self.assertIn("Attacker: E2 · Enemy 0x44", battle.rows[2].tooltip)
        self.assertIn("Damage: 19", battle.rows[2].tooltip)

    def test_battle_uses_rom_derived_enemy_name(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0032] = 0xFD
        memory.ram[0x056D] = 0x44
        memory.ram[0x0571] = 2
        memory.ram[0x0500:0x0502] = (20).to_bytes(2, "little")

        snapshot = DragonWarrior3Adapter(enemy_name=lambda enemy_id: "Slime").snapshot(memory)

        self.assertEqual(snapshot.sections[0].rows[0].text, "Groups · Slime ×2")
        self.assertTrue(snapshot.sections[0].rows[1].text.startswith("E1 Slime · HP 20"))

    def test_battle_switches_to_hoverable_combat_dashboard(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0032] = 0xFD
        memory.ram[0x0051] = 0
        memory.ram[0x054C] = 0x91
        memory.ram[0x0558] = 0x00
        memory.ram[0x056D] = 0x44
        memory.ram[0x0571] = 1
        memory.ram[0x0500:0x0502] = (77).to_bytes(2, "little")
        memory.ram[0x0510] = 12
        memory.ram[0x0518] = 28
        memory.ram[0x0520:0x0522] = (64).to_bytes(2, "little")
        memory.ram[0x0530] = 0x21
        memory.ram[0x073C] = 0x0C
        memory.ram[0x079C] = 0b00000011
        memory.sram[0xA9F] = 44
        memory.sram[0xAA3:0xAA5] = (91).to_bytes(2, "little")
        memory.sram[0xAAB:0xAAD] = (137).to_bytes(2, "little")
        profile = EnemyProfile(19, 140, 30, 82, 35, 70, 333, 88)

        snapshot = DragonWarrior3Adapter(
            enemy_name=lambda _enemy_id: "Marine Slime",
            enemy_profile=lambda _enemy_id: profile,
        ).snapshot(memory)

        self.assertEqual(
            tuple(section.title for section in snapshot.sections),
            ("Battle", "Party", "Battle spells"),
        )
        battle = snapshot.sections[0]
        self.assertIn("Lv 19", battle.rows[0].tooltip)
        self.assertIn("Current HP 77 · MP 12 · AGI 28 · DEF 64", battle.rows[1].tooltip)
        self.assertIn("Status: Sleep / Stopspell", battle.rows[1].tooltip)
        self.assertIn("ROM base: Lv 19 · HP 140 · MP 30 · ATK 82", battle.rows[1].tooltip)
        self.assertIn("Reward: 333 EXP · 88 G", battle.rows[1].tooltip)

        party = snapshot.sections[1]
        self.assertTrue(party.rows[0].text.startswith("> P1 · Hero Lv 20"))
        self.assertIn("Battle ATK 137 · DEF 91 · AGI 44", party.rows[0].tooltip)
        self.assertIn("Status: Barrier / Bikill", party.rows[0].tooltip)
        self.assertIn("Command: Cast Blaze", party.rows[0].tooltip)

        spells = snapshot.sections[2]
        self.assertEqual(spells.rows[0].text, "CHOSEN · P1 · Blaze · 2 MP")
        self.assertEqual(spells.rows[1].text, "P1 · Heal · 3 MP")
        self.assertIn("Chosen this round", spells.rows[0].tooltip)
        self.assertIn("Target: One enemy", spells.rows[0].tooltip)
        self.assertIn("Deals 8-13 damage before resistance", spells.rows[0].tooltip)
        self.assertIn("Caster MP: 30", spells.rows[0].tooltip)

    def test_battle_action_labels_ignore_the_target_bit(self) -> None:
        ram = bytearray(RAM_SIZE)
        for action, expected in (
            (0x00, "Attack"),
            (0x80, "Attack"),
            (0x20, "Parry"),
            (0xA0, "Parry"),
            (0x30, "Use item"),
            (0xB0, "Use item"),
            (0x70, "No action"),
            (0xF0, "No action"),
        ):
            ram[0x054C] = action
            self.assertEqual(
                DragonWarrior3Adapter._battle_action_label(ram, 0), expected
            )

    def test_chosen_spell_is_visible_before_the_preview_cutoff(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0032] = 0xFD
        memory.ram[0x0051] = 1
        memory.ram[0x054C] = 0x91
        memory.ram[0x0558] = 0x00
        memory.ram[0x079C] = 0b00000001
        memory.ram[0x079C + 8:0x079C + 11] = bytes((0xFF, 0xFF, 0xFF))

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        spells = next(
            section for section in snapshot.sections if section.title == "Battle spells"
        )
        self.assertEqual(spells.rows[0].text, "CHOSEN · P1 · Blaze · 2 MP")

    def test_baramos_progress_uses_save_flag_not_current_world(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0703] = 10
        memory.ram[0x07C4] = 3
        memory.ram[0x0743] = 0x80
        memory.ram[0x002F] = 2
        memory.ram[0x077C:0x0780] = bytes((0x58, 0x59, 0x5A, 0x76))
        memory.sram[0xB8] = 0x80
        memory.sram[0xCE:0xD1] = bytes((0x3F, 0x3F, 0x3F))

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: Baramos")

    def test_ending_flag_overrides_consumed_progress_items(self) -> None:
        memory = FakeMemory()
        memory.sram[0xB7] = 0x01

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Adventure complete")

    def test_snapshot_passes_exact_chest_flags_to_collectible_overlay(self) -> None:
        memory = FakeMemory()
        memory.sram[0x8E] = 0x80
        expected = (MapOverlay("world", (MapWaypoint(1, 2, "Treasure"),)),)
        received = []

        def overlays(
            flags: bytes,
            _ram: bytes,
            _sram: bytes,
            _items: tuple[int, ...],
        ) -> tuple[MapOverlay, ...]:
            received.append(flags)
            return expected

        snapshot = DragonWarrior3Adapter(collectible_overlays=overlays).snapshot(memory)

        self.assertEqual(received, [bytes((0x80,)) + bytes(25)])
        self.assertEqual(snapshot.map_overlays, expected)

    def test_indoor_snapshot_exposes_live_npc_positions(self) -> None:
        memory = FakeMemory()
        memory.ram[0x002F] = 1
        memory.ram[0x0110:0x0116] = bytes((5, 7, 2, 0, 0xFF, 0))

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        overlay = snapshot.map_overlays[0]
        self.assertEqual(overlay.layer_key, "area-34")
        self.assertEqual((overlay.waypoints[0].x, overlay.waypoints[0].y), (5, 7))
        self.assertEqual(overlay.waypoints[0].kind, "npcs")
        self.assertEqual(overlay.waypoints[0].title, "Townsperson")
        self.assertEqual(overlay.waypoints[0].marker, "person")

    def test_stale_save_cannot_turn_owned_ship_back_into_unfound_ship(self) -> None:
        memory = FakeMemory()
        memory.sram[0xB8] = 0x80
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory) / "Dragon Warrior III.srm"
            saved_sram = bytearray(0x2000)
            saved_sram[0xB8] = 0xC0
            save.write_bytes(saved_sram)

            state = DragonWarrior3Adapter(save_path=save)._state(
                bytes(memory.ram),
                DragonWarrior3Adapter(save_path=save)._merge_save_sram(bytes(memory.sram)),
            )

        self.assertTrue(state.ship_owned)

    def test_owned_ship_skips_consumed_black_pepper_objective(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0703] = 10
        memory.ram[0x07C4] = 3
        memory.ram[0x0743] = 0x80
        memory.ram[0x077C:0x077E] = bytes((0x58, 0x59))
        memory.sram[0xB8] = 0x80

        snapshot = DragonWarrior3Adapter().snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: Final Key route")
        key_items = objective.actions[1].rows
        black_pepper = next(row for row in key_items if row.text.startswith("Black Pepper:"))
        self.assertTrue(black_pepper.caught)

    def test_configured_save_supplements_live_ship_progress(self) -> None:
        memory = FakeMemory()
        memory.ram[0x0703] = 10
        memory.ram[0x07C4] = 3
        memory.ram[0x0743] = 0x80
        memory.ram[0x077C:0x077E] = bytes((0x58, 0x59))
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory) / "Dragon Warrior III.srm"
            saved_sram = bytearray(0x2000)
            saved_sram[0xB8] = 0x80
            save.write_bytes(saved_sram)

            snapshot = DragonWarrior3Adapter(save_path=save).snapshot(memory)

        objective = next(section for section in snapshot.sections if section.title == "Current objective")
        self.assertEqual(objective.rows[0].text, "Next: Final Key route")


if __name__ == "__main__":
    unittest.main()