import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from game.rom_assets import AreaGraphics, AreaMapDescriptor, ChestRecord, DragonWarrior3RomAssets, MdecDecoder, NpcMetadata, WorldGraphics, decode_world_row
from map_renderer import NES_PALETTE, render_area_map, render_world_map


def bitstream(bits: str) -> bytes:
    padded = bits + "0" * (-len(bits) % 8)
    return bytes(int(padded[index:index + 8], 2) for index in range(0, len(padded), 8))


class MdecDecoderTests(unittest.TestCase):
    def test_decodes_clear_tile_and_direct_write(self) -> None:
        data = bytes((2, 2, 0)) + bitstream(
            "01"       # clear tile 1
            "00" "10" # select tile 2
            "11" "10" # direct write at linear position 2
            "00" "00" "00" "1" # select tile 0, then terminate
            "00"       # no overlay pass
        )

        decoder = MdecDecoder(data, 0)

        self.assertEqual(decoder.decode(), ((1, 1), (2, 1)))

    def test_rejects_out_of_bounds_direct_write(self) -> None:
        data = bytes((2, 1, 0)) + bitstream(
            "01"
            "00" "10"
            "11" "11"
        )

        with self.assertRaisesRegex(ValueError, "outside map bounds"):
            MdecDecoder(data, 0).decode()

    def test_rejects_unreasonable_dimensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid MDEC dimensions"):
            MdecDecoder(bytes((255, 1, 0)), 0)


class WorldMapDecoderTests(unittest.TestCase):
    def test_decodes_runs_and_extended_literal_tiles(self) -> None:
        data = bytes((0x02, 0x43, 0xE8, 0xE1))

        self.assertEqual(
            decode_world_row(data, 0, 10),
            (0, 0, 0, 2, 2, 2, 2, 8, 7, 7),
        )


class RomAssetLayerTests(unittest.TestCase):
    def test_enemy_profile_decodes_rom_record_stats_and_rewards(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(0x4000)
        offset = 0x32D3 + 2 * 23
        record = bytearray(23)
        record[0] = 0xC0 | 37
        record[1:3] = (1234).to_bytes(2, "little")
        record[3:9] = bytes((88, 0x56, 0x78, 0x9A, 0xBC, 77))
        record[0x12:0x16] = bytes((0x02, 0x01, 0x03, 0x02))
        assets._data[offset:offset + 23] = record

        profile = assets.enemy_profile(2)

        self.assertEqual(profile.level, 37)
        self.assertEqual(profile.max_hp, 0x2BC)
        self.assertEqual(profile.max_mp, 77)
        self.assertEqual(profile.attack, 0x178)
        self.assertEqual(profile.agility, 88)
        self.assertEqual(profile.defense, 0x39A)
        self.assertEqual(profile.experience, 1234)
        self.assertEqual(profile.gold, 0x256)

    def test_npc_metadata_classifies_services_and_item_givers(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        equipment_shop = bytes((0x10, 0, 0x28, 5, 6))
        magic_ball_giver = bytes((0x50, 0, 0x6A, 7, 8))
        assets._npc_lists = tuple(
            (equipment_shop, magic_ball_giver) if index == 1 else ()
            for index in range(2)
        )
        sram = bytearray(0xD1)

        available = assets.npc_metadata(1, 0, bytes(sram), ())
        sram[0xBF] = 0x20
        completed = assets.npc_metadata(1, 0, bytes(sram), ())

        self.assertEqual(
            available[0],
            NpcMetadata("Equipment shop", "Talk for dialogue", marker="shop"),
        )
        self.assertEqual(available[1].title, "Reeve elder")
        self.assertEqual(available[1].marker, "item")
        self.assertIn("Magic Ball", available[1].detail)
        self.assertIn("Available", available[1].detail)
        self.assertTrue(completed[1].completed)
        self.assertIn("Completed", completed[1].detail)

    def test_chest_flags_use_game_bit_order(self) -> None:
        flags = bytes((0x81,)) + bytes(25)

        self.assertTrue(DragonWarrior3RomAssets._chest_is_open(flags, 0))
        self.assertTrue(DragonWarrior3RomAssets._chest_is_open(flags, 7))
        self.assertFalse(DragonWarrior3RomAssets._chest_is_open(flags, 1))

    def test_collectibles_are_grouped_at_named_world_entrances(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(7 * 0x4000)
        table = 6 * 0x4000 + 0x3242
        assets._data[table + 3 * 5:table + 3 * 5 + 2] = bytes((51, 171))
        assets._chests = (
            ChestRecord(0, 3, 0, "Magic Key", True),
            ChestRecord(1, 3, 1, "128 gold", True),
        )
        assets._item_name = Mock(side_effect=lambda item_id: f"Item {item_id:02X}")

        overlays = assets.collectible_overlays(bytes((0x80,)) + bytes(25))

        marker = overlays[0].waypoints[0]
        self.assertEqual(overlays[0].layer_key, "world")
        self.assertEqual((marker.x, marker.y), (51, 171))
        self.assertEqual(marker.title, "Castle of Baramos treasure (1 remaining)")
        self.assertIn("Collected: Magic Key", marker.detail)
        self.assertIn("Available: 128 gold", marker.detail)
        self.assertFalse(marker.completed)

    def test_mobile_phantom_ship_treasure_uses_live_world_position(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(7 * 0x4000)
        assets._chests = (ChestRecord(0, 0x9D, 0, "Locket of Love", True),)
        assets._item_name = Mock(side_effect=lambda item_id: f"Item {item_id:02X}")
        ram = bytearray(0x800)
        ram[0x9B:0x9D] = bytes((77, 88))

        overlays = assets.collectible_overlays(bytes(26), bytes(ram))

        marker = overlays[0].waypoints[0]
        self.assertEqual((marker.x, marker.y), (77, 88))
        self.assertEqual(marker.title, "Phantom Ship B1 treasure (1 remaining)")

    def test_scripted_collectibles_include_local_and_world_markers(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(7 * 0x4000)
        table = 6 * 0x4000 + 0x3242
        assets._data[table + 0x19 * 5:table + 0x19 * 5 + 2] = bytes((80, 90))
        assets._chests = ()
        assets._item_name = Mock(side_effect=lambda item_id: f"Item {item_id:02X}")
        flags = bytearray(26)
        flags[203 >> 3] = 0x80 >> (203 & 7)

        overlays = assets.collectible_overlays(bytes(flags), items=(0x69,))

        by_layer = {overlay.layer_key: overlay.waypoints for overlay in overlays}
        soo = next(point for point in by_layer["world"] if "Soo" in point.title)
        local = by_layer["area-19"][0]
        leaf = next(point for point in by_layer["world"] if "World Tree" in point.title)
        self.assertTrue(soo.completed)
        self.assertEqual((local.x, local.y), (15, 16))
        self.assertTrue(leaf.completed)

    def test_area_layers_render_only_when_loaded(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets.cache_directory = Path("cache")
        assets._descriptors = (AreaMapDescriptor(0x34, 5, 20, 15, 0x1234),)
        assets.render_area_map = Mock(return_value=Path("rendered.png"))

        layer = assets.map_layers()[0]

        self.assertEqual(layer.map_id, 0x34)
        self.assertEqual(layer.title, "Cave Northeast of Baharata")
        self.assertEqual((layer.wrap_width, layer.wrap_height), (20, 15))
        self.assertEqual((layer.anchor_x, layer.anchor_y), (8, 8))
        assets.render_area_map.assert_not_called()
        self.assertIsNotNone(layer.image_loader)
        self.assertEqual(layer.image_loader(), Path("rendered.png"))
        assets.render_area_map.assert_called_once_with(0x34)

    def test_world_layers_render_only_when_loaded(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets.cache_directory = Path("cache")
        assets._world_waypoints = Mock(return_value=())
        assets._world_encounter_regions = Mock(return_value=())
        assets.render_world_map = Mock(return_value=Path("world.png"))

        world, underworld = assets.world_layers()

        self.assertEqual((world.area, world.wrap_width, world.wrap_height), ("World", 256, 256))
        self.assertEqual((underworld.area, underworld.wrap_width, underworld.wrap_height), ("Underworld", 160, 139))
        assets.render_world_map.assert_not_called()
        self.assertEqual(world.image_loader(), Path("world.png"))
        assets.render_world_map.assert_called_once_with("world")

    def test_world_waypoints_are_read_from_rom_trigger_records(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(7 * 0x4000)
        table = 6 * 0x4000 + 0x3242
        assets._data[table:table + 5] = bytes((0xAC, 0xDA, 0, 0x1E, 1))
        alefgard = table + 0x10 * 5
        assets._data[alefgard:alefgard + 5] = bytes((0x5C, 0x6F, 0x10, 0, 2))
        southwest_cave = table + 0x39 * 5
        assets._data[southwest_cave:southwest_cave + 5] = bytes((0x30, 0x42, 3, 0x15, 4))

        world = assets._world_waypoints("World")
        underworld = assets._world_waypoints("Underworld")

        self.assertEqual((world[0].x, world[0].y, world[0].title), (0xAC, 0xDA, "Aliahan Town"))
        self.assertEqual(world[0].kind, "entrance")
        self.assertEqual((underworld[0].x, underworld[0].y, underworld[0].title), (0x5C, 0x6F, "Cantlin"))
        self.assertEqual(underworld[1].title, "Cave Southwest of Tantegel")
        self.assertEqual(underworld[1].detail, "Entrance at (3,21)")

    def test_world_encounter_regions_follow_rom_grid(self) -> None:
        assets = DragonWarrior3RomAssets.__new__(DragonWarrior3RomAssets)
        assets._prg_offset = 0
        assets._data = bytearray(0x4000)
        assets._data[0x0946] = 0x85
        assets._data[0x0946 + 0x21] = 0x12
        assets._encounter_enemies = Mock(return_value=(("Slime", 1),))

        regions = assets._world_encounter_regions("World")

        self.assertEqual(len(regions), 256)
        self.assertEqual((regions[0].x, regions[0].y), (0, 0))
        self.assertEqual(regions[0].detail, "Low\nSlime (Lv 1)")
        self.assertEqual(regions[0].label, "Slime Lv 1")
        self.assertEqual(regions[0].compact_label, "Slime")
        self.assertEqual(regions[0].color, "#27824a")
        self.assertEqual((regions[0x21].x, regions[0x21].y), (16, 32))
        self.assertEqual(regions[0x21].detail, "Low\nSlime (Lv 1)")
        self.assertEqual(assets._world_encounter_regions("Underworld"), ())

    def test_area_renderer_uses_logical_tile_bits_and_nes_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "map.png"
            pattern = bytes((0x80,) + (0,) * 7 + (0x40,) + (0,) * 7)
            graphics = AreaGraphics(
                ((0, 0, 0, 0),),
                (0,),
                (pattern,),
                (0x30, 0x17, 0x10) * 4,
            )

            render_area_map(((0x00, 0xE0),), graphics, output)

            from PIL import Image

            with Image.open(output) as image:
                self.assertEqual(image.size, (32, 16))
                self.assertEqual(image.getpixel((0, 0)), NES_PALETTE[0x30])
                self.assertEqual(image.getpixel((1, 0)), NES_PALETTE[0x17])
                self.assertEqual(image.getpixel((16, 0)), NES_PALETTE[0x30])

    def test_world_renderer_decodes_nes_pattern_planes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "world.png"
            pattern = bytes((0x80,) + (0,) * 7 + (0x40,) + (0,) * 7)
            graphics = WorldGraphics(
                ((0x8D, 0x8D, 0x8D, 0x8D),),
                (0,),
                (pattern,),
                (0x30, 0x17, 0x10) * 4,
            )

            render_world_map(((0,),), graphics, output)

            from PIL import Image

            with Image.open(output) as image:
                self.assertEqual(image.size, (16, 16))
                self.assertEqual(image.getpixel((0, 0)), NES_PALETTE[0x30])
                self.assertEqual(image.getpixel((1, 0)), NES_PALETTE[0x17])
                self.assertEqual(image.getpixel((2, 0)), NES_PALETTE[0x0F])


if __name__ == "__main__":
    unittest.main()