from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from retroarch_overlay.models import MapLayer, MapOverlay, MapRegion, MapWaypoint

from .battle import EnemyProfile
from .manifest import RA_HASHES


EXTRACTOR_VERSION = 4
AREA_MAP_COUNT = 256
MAX_MAP_DIMENSION = 128
MAX_DECODE_OPERATIONS = 1_000_000
AREA_DESCRIPTOR_TABLE_OFFSET = 0x23F1
AREA_TILE_OVERRIDE_TABLE_OFFSET = 0x2D30
AREA_TILE_OVERRIDE_COUNT = 17
AREA_EXPLICIT_PATTERN_REFS_OFFSET = 0x2DD4
AREA_PATTERN_DELTAS_OFFSET = 0x3456
AREA_PALETTE_DATA1_OFFSET = 0x251B
AREA_PALETTE_DATA2_OFFSET = 0x251F
AREA_PALETTE_DATA0_OFFSET = 0x2521
AREA_PALETTE_LIBRARY_OFFSET = 0x2543
AREA_PALETTE_DATA4_OFFSET = 0x2633
AREA_PALETTE_DATA3_OFFSET = 0x268D
AREA_PALETTE_DATA5_OFFSET = 0x26FA
AREA_COMMON_PALETTE_SIZE = 12
WORLD_MAP_SPECS = {
    "world": ("Main World", "World", 0x0018, 256, 256),
    "underworld": ("Alefgard", "Underworld", 0x1A95, 139, 160),
}
WORLD_TRIGGER_TABLE_OFFSET = 0x3242
WORLD_TRIGGER_COUNT = 65
ALEFGARD_TRIGGER_IDS = frozenset(
    (0x07, 0x08, 0x10, 0x11, 0x12, 0x1A, 0x22, 0x28, 0x2A, 0x38, 0x39, 0x3A, 0x40)
)
WORLD_DESCRIPTOR_OFFSET = 0x25A1
WORLD_DESCRIPTOR_COUNT = 32
WORLD_PATTERN_BASE = 0x8D
WORLD_RAW_PATTERN_BASE = 0xE3
WORLD_RAW_PATTERN_COUNT = 27
WORLD_DESCRIPTOR_DELTAS_OFFSET = 0x3456
WORLD_EXPLICIT_METATILES_OFFSET = 0x2D74
WORLD_EXPLICIT_METATILE_COUNT = 23
WORLD_EXPLICIT_PATTERNS_OFFSET = 0x32E4
WORLD_DAY_PALETTE_OFFSET = 0x3755
WORLD_ENCOUNTER_GRID_OFFSET = 0x0946
ENCOUNTER_RECORDS_OFFSET = 0x0ADB
ENCOUNTER_RECORD_SIZE = 15
ENEMY_RECORDS_OFFSET = 0x32D3
ENEMY_RECORD_SIZE = 23
STRING_TABLE_DIRECTORY_OFFSET = 0xAA0E
NPC_LISTS_OFFSET = 0x019A
NPC_LIST_COUNT = 0xFA
NPC_RECORD_SIZES = (5, 6, 6, 7, 7, 8, 8, 9)
CHEST_COUNT_TABLE_OFFSET = 0x1197
CHEST_COUNT_RECORDS = 64
CHEST_CONTENT_COUNT = 0xC1
CHEST_WORLD_ROOTS = {
    0x46: 0x00,
    0x4E: 0x02,
    0x53: 0x29,
    0x55: 0x29,
    0x62: 0x06,
    0x69: 0x07,
    0x6A: 0x07,
    0x71: 0x0A,
    0x75: 0x72,
    0x86: 0x15,
    0x8B: 0x18,
    0x90: 0x28,
    0x9D: 0x9C,
    0x9F: 0x3C,
    0xA1: 0x98,
    0xA3: 0x2E,
    0xA4: 0x2E,
    0xA5: 0x2E,
    0xA7: 0x39,
    0xA8: 0x31,
    0xB2: 0x34,
    0xBD: 0x36,
    0xBE: 0x37,
    0xBF: 0x37,
    0xC5: 0x38,
    0xCA: 0x08,
    0xCB: 0x08,
    0xD1: 0x3B,
    0xD2: 0x3B,
    0xD3: 0x3B,
    0xD4: 0x3B,
    0xD6: 0x3C,
    0xD7: 0x3C,
    0xDB: 0x3D,
    0xDC: 0x3D,
    0xDE: 0x3D,
    0xE5: 0x3E,
    0xE7: 0x3E,
    0xE9: 0x3F,
    0xEB: 0x3F,
    0xEE: 0x3F,
    0xF0: 0x40,
    0xF1: 0x40,
    0xF2: 0x40,
}
EXTENDED_WORLD_ANCHORS = {
    0x72: ("world", 0xED, 0x4B),
    0x98: ("world", 0xBE, 0xD1),
}
AREA_MAP_NAMES = {
    0x00: "Aliahan Town",
    0x01: "Romaly",
    0x02: "Eginbear",
    0x03: "Castle of Baramos",
    0x04: "Final Key Shrine",
    0x06: "Samanao",
    0x07: "Brecconaly",
    0x08: "Castle of Zoma 1F",
    0x09: "Reeve",
    0x0A: "Portoga Town",
    0x0B: "Noaniels",
    0x0C: "Assaram",
    0x0E: "Baharata",
    0x0F: "Lancel",
    0x10: "Cantlin",
    0x11: "Rimuldar",
    0x12: "Haukness",
    0x13: "Luzami",
    0x14: "Kanave",
    0x15: "Tedanki",
    0x16: "Muor",
    0x17: "Jipang",
    0x18: "House of Pirates",
    0x19: "Soo",
    0x1A: "Kol",
    0x1B: "Reeve Magic Ball Room",
    0x1C: "Southern Travel Shrine",
    0x1D: "Gaia's Sword Shrine",
    0x1E: "Swamp Shrine",
    0x1F: "Small Travel Shrine",
    0x20: "Silver Orb Shrine",
    0x21: "Promontory of Olivia Shrine",
    0x22: "Ortega's Companion Shrine",
    0x23: "Castle of the Dragon Queen",
    0x24: "Orochi Travel Shrine",
    0x25: "Shrine of Liamland",
    0x26: "Two-way Travel Shrine",
    0x27: "Three-way Travel Shrine",
    0x28: "Garinham Silver Harp Hut",
    0x29: "Isis Castle Throne Room",
    0x2A: "Shrine of Honor",
    0x2B: "Romaly Shrine East",
    0x2C: "Romaly Shrine West",
    0x2D: "Cave on Promontory B1",
    0x2E: "Cave West of Noaniels",
    0x2F: "Cave by Assaram West",
    0x30: "Cave by Assaram East",
    0x31: "Cave of Necrogond B1",
    0x32: "Cave of Necrogond B5",
    0x33: "Shrine of Dhama",
    0x34: "Cave Northeast of Baharata",
    0x35: "Cave of Jipang",
    0x36: "Navel of the Earth",
    0x37: "Cave Southeast of Samanao",
    0x38: "Cave Northwest of Tantegel",
    0x39: "Cave Southwest of Tantegel",
    0x3A: "Tunnel to Rimuldar",
    0x3B: "Pyramid 1F",
    0x3C: "Tower of Najima 1F",
    0x3D: "Tower of Garuna 1F",
    0x3E: "Tower of Arp 1F",
    0x3F: "Tower of Shanpane 1F",
    0x40: "Tower West of Kol 1F",
    0x41: "Aliahan Hero's Home 2F",
    0x44: "Aliahan Hall of Registration",
    0x46: "Aliahan Castle",
    0x47: "Aliahan Castle Throne Room",
    0x48: "Romaly Fight Ring Basement",
    0x4A: "Romaly Castle 2F",
    0x4B: "Romaly Castle West Tower 3F",
    0x4C: "Romaly Castle West Tower 4F",
    0x4D: "Romaly Castle East Tower 4F",
    0x4E: "Eginbear Boulder Puzzle Basement",
    0x50: "Isis Town",
    0x53: "Isis Castle B2",
    0x55: "Isis Castle",
    0x58: "Baramos's Lair",
    0x61: "Samanao Castle",
    0x62: "Samanao Castle 2F",
    0x69: "Tantegel Castle",
    0x6A: "Tantegel Castle Treasure Room",
    0x71: "Portoga Castle",
    0x72: "New Town Stage 1",
    0x73: "New Town Stage 2",
    0x74: "New Town Stage 3",
    0x75: "New Town Stage 4",
    0x84: "Hidden Village of the Elves",
    0x86: "Tedanki Weapon Shop",
    0x8B: "House of Pirates B1",
    0x90: "Garinham Basement",
    0x91: "Alefgard Landing",
    0x98: "Cave of Enticement Drop Entrance",
    0x9B: "Romaly Castle East Tower 3F",
    0x9C: "Phantom Ship 1F",
    0x9D: "Phantom Ship B1",
    0x9F: "Tower of Najima B1",
    0xA0: "Cave of Enticement B1",
    0xA1: "Cave of Enticement B2",
    0xA2: "Cave of Enticement B3",
    0xA3: "Cave West of Noaniels B2",
    0xA4: "Cave West of Noaniels B3",
    0xA5: "Cave West of Noaniels B4",
    0xA7: "Cave Southwest of Tantegel B2",
    0xA8: "Cave of Necrogond B4",
    0xB2: "Cave Northeast of Baharata B2",
    0xBB: "Cave of Jipang B2",
    0xBC: "Navel of the Earth B2",
    0xBD: "Navel of the Earth B3",
    0xBE: "Cave Southeast of Samanao B2",
    0xBF: "Cave Southeast of Samanao B3",
    0xC3: "Cave Northwest of Tantegel B2",
    0xC5: "Cave Northwest of Tantegel B3",
    0xC8: "Castle of Zoma B1",
    0xC9: "Castle of Zoma B2",
    0xCA: "Castle of Zoma B3",
    0xCB: "Castle of Zoma B4",
    0xCC: "Castle of Zoma B5",
    0xCF: "Pyramid Golden Claw Room",
    0xD0: "Pyramid B1",
    0xD1: "Pyramid 2F",
    0xD2: "Pyramid 3F",
    0xD3: "Pyramid 4F",
    0xD4: "Pyramid 5F",
    0xD5: "Pyramid Peak",
    0xD6: "Tower of Najima 2F",
    0xD7: "Tower of Najima 3F",
    0xD8: "Tower of Najima 4F",
    0xDB: "Tower of Garuna 2F",
    0xDC: "Tower of Garuna 3F",
    0xDD: "Tower of Garuna 4F",
    0xDE: "Tower of Garuna 5F and 6F",
    0xE4: "Tower of Arp 2F",
    0xE5: "Tower of Arp 3F",
    0xE6: "Tower of Arp 4F",
    0xE7: "Tower of Arp 5F",
    0xE8: "Tower of Shanpane 2F",
    0xE9: "Tower of Shanpane 3F",
    0xEB: "Tower of Shanpane 4F",
    0xEC: "Tower of Shanpane 5F",
    0xEE: "Tower of Shanpane 6F",
    0xEF: "Tower West of Kol 5F",
    0xF0: "Tower West of Kol 2F",
    0xF1: "Tower West of Kol 3F",
    0xF2: "Tower West of Kol 4F",
}


@dataclass(frozen=True, slots=True)
class AreaMapDescriptor:
    map_id: int
    tileset: int
    width: int
    height: int
    data_offset: int


@dataclass(frozen=True, slots=True)
class WorldGraphics:
    metatiles: tuple[tuple[int, int, int, int], ...]
    attributes: tuple[int, ...]
    patterns: tuple[bytes, ...]
    palette: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AreaGraphics:
    metatiles: tuple[tuple[int, int, int, int], ...]
    attributes: tuple[int, ...]
    patterns: tuple[bytes, ...]
    palette: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ChestRecord:
    global_index: int
    map_id: int
    local_index: int
    description: str
    collectible: bool


@dataclass(frozen=True, slots=True)
class ScriptedCollectible:
    map_id: int | None
    x: int
    y: int
    item_id: int
    world_root: int | None
    flag_index: int | None = None


@dataclass(frozen=True, slots=True)
class NpcMetadata:
    title: str
    detail: str
    completed: bool = False
    marker: str = "person"


NPC_SERVICE_THRESHOLDS = (
    (0x3C0, "special"),
    (0x226, "dialogue"),
    (0x21C, "dialogue"),
    (0x1FE, "Item shop"),
    (0x1EA, "Equipment shop"),
    (0x1E0, "Innkeeper"),
    (0x168, "special"),
    (0x050, "Townsperson"),
    (0x03C, "Townsperson"),
    (0x032, "Item shop"),
    (0x028, "Equipment shop"),
    (0x00A, "Innkeeper"),
    (0x006, "Priest"),
    (0x005, "Monster Arena attendant"),
    (0x004, "Vocation master"),
    (0x003, "Registration clerk"),
    (0x002, "Vault clerk"),
    (0x001, "Tavern host"),
)

NPC_SPECIAL_ROLES = {
    0x00: ("Hero's mother", "Rest and story dialogue"),
    0x01: ("Hero's mother", "Rest and story dialogue"),
    0x02: ("Reeve elder", "Quest item giver: Magic Ball"),
    0x03: ("New Town founder", "Quest actor: recruit a Merchant"),
    0x0D: ("Arena challenger", "Starts a scripted battle"),
    0x0E: ("Fortune teller", "Fortune-telling event"),
    0x13: ("Elven item shop", "Item shop; requires a non-human form"),
    0x16: ("Elf Queen", "Quest actor: Dream Ruby and Wake-up Powder"),
    0x17: ("Elf elder", "Dream Ruby quest dialogue"),
    0x18: ("Baharata grandfather", "Quest actor: rescue Tania and Galen"),
    0x19: ("Pepper shopkeeper", "Quest item giver: Black Pepper"),
    0x1C: ("Muor resident", "Item giver: Water Blaster"),
    0x1E: ("Green Orb guardian", "Quest item giver: Green Orb"),
    0x22: ("Greenland trader", "Trades Staff of Change for Sailor's Thigh Bone"),
    0x25: ("Silver Orb guardian", "Quest item giver: Silver Orb"),
    0x27: ("Dragon Queen", "Quest item giver: Sphere of Light"),
    0x28: ("Liamland elf", "Quest actor: hatch Ramia after placing the orbs"),
    0x29: ("Baramos", "Boss encounter"),
    0x2B: ("Meteorite Armband guardian", "Treasure-room quest actor"),
    0x2C: ("King of Aliahan", "Post-Baramos story quest"),
    0x2D: ("Sword of Illusion giver", "Quest item giver: Sword of Illusion"),
    0x2E: ("Himiko", "Boss encounter: Orochi"),
    0x42: ("King of Romaly", "Golden Crown quest and save service"),
    0x43: ("Former King of Romaly", "Romaly throne quest actor"),
    0x47: ("King", "Save and adventure-log service"),
    0x5C: ("King of Portoga", "Black Pepper trade and ship quest"),
    0x64: ("Guardian", "Starts a scripted battle"),
    0x65: ("Magic healer", "Restores party MP"),
    0x67: ("Shrine of Honor priest", "Quest item giver: Rainbow Drop"),
    0x68: ("Rubiss's servant", "Quest item giver: Staff of Rain"),
    0x6C: ("Reeve dreamer", "Quest item giver: Thief's Key"),
}


SCRIPTED_COLLECTIBLES = (
    ScriptedCollectible(0x75, 4, 2, 0x79, 0x72, 200),
    ScriptedCollectible(0x1D, 14, 16, 0x11, 0x1D, 201),
    ScriptedCollectible(0x1A, 11, 12, 0x70, 0x1A, 202),
    ScriptedCollectible(0x19, 15, 16, 0x1B, 0x19, 203),
    ScriptedCollectible(0x12, 23, 35, 0x5E, 0x12, 204),
    ScriptedCollectible(0x85, 4, 5, 0x64, 0x15, 205),
    ScriptedCollectible(0x13, 18, 13, 0x63, 0x13, 206),
    ScriptedCollectible(0x57, 6, 5, 0x4E, 0x29, 207),
    ScriptedCollectible(0xCF, 22, 12, 0x4A, 0x3B),
    ScriptedCollectible(None, 0x7B, 0x4C, 0x69, None),
)


class _BitReader:
    def __init__(self, data: bytes, offset: int) -> None:
        self._data = data
        self._bit_offset = offset * 8

    def read(self, count: int) -> int:
        if count < 0 or self._bit_offset + count > len(self._data) * 8:
            raise ValueError("Truncated MDEC bitstream")
        value = 0
        for _ in range(count):
            byte_offset, bit = divmod(self._bit_offset, 8)
            value = (value << 1) | ((self._data[byte_offset] >> (7 - bit)) & 1)
            self._bit_offset += 1
        return value


class MdecDecoder:
    def __init__(self, data: bytes, offset: int) -> None:
        if offset < 0 or offset + 3 > len(data):
            raise ValueError("MDEC offset is outside the ROM")
        self._reader = _BitReader(data, offset)
        self.width = self._reader.read(8)
        self.height = self._reader.read(8)
        header = self._reader.read(8)
        if not 0 < self.width <= MAX_MAP_DIMENSION or not 0 < self.height <= MAX_MAP_DIMENSION:
            raise ValueError(f"Invalid MDEC dimensions: {self.width}x{self.height}")
        self._pointer_bits = max(1, (self.width * self.height - 1).bit_length())
        self._tile_bits = ((header >> 6) & 0x03) + 2
        clear_tile = self._reader.read(self._tile_bits)
        self.tiles = [[clear_tile for _ in range(self.width)] for _ in range(self.height)]
        self._operations = 0

    def decode(self) -> tuple[tuple[int, ...], ...]:
        self._run(False)
        overlay_bits = self._reader.read(2)
        if overlay_bits:
            self._tile_bits = overlay_bits
            self._run(True)
        return tuple(tuple(row) for row in self.tiles)

    def _run(self, overlay: bool) -> None:
        brush = (0,)
        large = False
        stack: list[tuple[int, int, int]] = []
        while True:
            command = self._reader.read(2)
            if command == 0:
                brush = (self._reader.read(self._tile_bits),)
                large = False
                command = self._reader.read(2)
                if command:
                    pass
                elif self._reader.read(1):
                    return
                else:
                    brush = brush + tuple(self._reader.read(self._tile_bits) for _ in range(3))
                    large = True
                    continue
            if command == 1:
                left, top = self._point()
                right, bottom = self._point()
                if right < left or bottom < top:
                    raise ValueError("Invalid MDEC fill rectangle")
                step = 2 if large else 1
                for y in range(top, bottom + 1, step):
                    for x in range(left, right + 1, step):
                        self._emit(x, y, brush, large, overlay)
                continue
            if command == 2:
                x, y = self._point()
                self._emit(x, y, brush, large, overlay)
                direction = self._reader.read(2)
                while True:
                    if self._reader.read(1):
                        operation = self._reader.read(2)
                        if operation == 0:
                            direction = (direction + 1) & 3
                        elif operation == 1:
                            direction = (direction - 1) & 3
                        elif operation == 2:
                            stack.append((x, y, direction))
                            direction = (direction + (1 if self._reader.read(1) == 0 else -1)) & 3
                        elif self._reader.read(1) == 0:
                            x, y = self._point()
                            self._emit(x, y, brush, large, overlay)
                            direction = self._reader.read(2)
                            continue
                        elif stack:
                            x, y, direction = stack.pop()
                            continue
                        else:
                            break
                    if direction == 0:
                        y -= 1
                    elif direction == 1:
                        x += 1
                    elif direction == 2:
                        y += 1
                    else:
                        x -= 1
                    self._emit(x, y, brush, large, overlay)
                continue
            if command == 3:
                x, y = self._point()
                self._emit(x, y, brush, large, overlay)

    def _point(self) -> tuple[int, int]:
        pointer = self._reader.read(self._pointer_bits)
        return pointer % self.width, pointer // self.width

    def _emit(
        self,
        x: int,
        y: int,
        brush: tuple[int, ...],
        large: bool,
        overlay: bool,
    ) -> None:
        points = ((x, y, brush[0]),)
        if large:
            points = (
                (x, y, brush[0]),
                (x + 1, y, brush[1]),
                (x, y + 1, brush[2]),
                (x + 1, y + 1, brush[3]),
            )
        for target_x, target_y, tile in points:
            self._operations += 1
            if self._operations > MAX_DECODE_OPERATIONS:
                raise ValueError("MDEC operation limit exceeded")
            if not 0 <= target_x < self.width or not 0 <= target_y < self.height:
                raise ValueError("MDEC write is outside map bounds")
            if overlay:
                self.tiles[target_y][target_x] = (self.tiles[target_y][target_x] & 0x1F) | (tile << 5)
            else:
                self.tiles[target_y][target_x] = tile


def decode_world_row(data: bytes, offset: int, width: int) -> tuple[int, ...]:
    tiles = []
    while len(tiles) < width:
        if offset >= len(data):
            raise ValueError("Truncated world map row")
        value = data[offset]
        offset += 1
        terrain = value >> 5
        run_length = (value & 0x1F) + 1
        if terrain == 7:
            literal = value & 0x1F
            if literal >= 8:
                terrain = literal
                run_length = 1
        tiles.extend((terrain,) * min(run_length, width - len(tiles)))
    return tuple(tiles)


class DragonWarrior3RomAssets:
    def __init__(
        self,
        rom_path: Path,
        state_directory: Path,
        renderer: Callable[
            [tuple[tuple[int, ...], ...], AreaGraphics, Path], None
        ],
        world_renderer: Callable[
            [tuple[tuple[int, ...], ...], WorldGraphics, Path], None
        ],
    ) -> None:
        data = rom_path.read_bytes()
        if len(data) < 16 or data[:4] != b"NES\x1a":
            raise ValueError("Configured file is not an iNES ROM")
        trainer_size = 512 if data[6] & 0x04 else 0
        prg_offset = 16 + trainer_size
        prg_size = data[4] * 0x4000
        if prg_size < 0x80000 or prg_offset + prg_size > len(data):
            raise ValueError("Configured ROM does not contain the expected 512 KiB PRG data")
        content_hash = hashlib.md5(data[16:], usedforsecurity=False).hexdigest()
        if content_hash not in RA_HASHES:
            raise ValueError(f"Unsupported Dragon Warrior III ROM hash: {content_hash}")
        self._data = data
        self._prg_offset = prg_offset
        self.content_hash = content_hash
        self.cache_directory = state_directory / "generated-assets" / content_hash / f"v{EXTRACTOR_VERSION}"
        self._renderer = renderer
        self._world_renderer = world_renderer
        self._descriptors = self._index_area_maps()
        self._chests = self._index_chests()
        self._npc_lists = self._index_npc_lists()

    @property
    def area_maps(self) -> tuple[AreaMapDescriptor, ...]:
        return self._descriptors

    def map_layers(self) -> tuple[MapLayer, ...]:
        return tuple(
            MapLayer(
                f"area-{descriptor.map_id:02x}",
                AREA_MAP_NAMES.get(descriptor.map_id, "Unknown location"),
                "Dungeon / town",
                self.cache_directory / "maps" / f"area-{descriptor.map_id:02x}.png",
                credit="Generated locally from the configured ROM",
                wrap_width=descriptor.width,
                wrap_height=descriptor.height,
                anchor_x=8,
                anchor_y=8,
                map_id=descriptor.map_id,
                image_loader=lambda map_id=descriptor.map_id: self.render_area_map(map_id),
            )
            for descriptor in self._descriptors
        )

    def world_layers(self) -> tuple[MapLayer, ...]:
        return tuple(
            MapLayer(
                key,
                title,
                area,
                self.cache_directory / "maps" / f"{key}.png",
                credit="Generated locally from the configured ROM",
                wrap_width=width,
                wrap_height=height,
                anchor_x=8,
                anchor_y=8,
                image_loader=lambda map_key=key: self.render_world_map(map_key),
                waypoints=self._world_waypoints(area),
                regions=self._world_encounter_regions(area),
            )
            for key, (title, area, _, height, width) in WORLD_MAP_SPECS.items()
        )

    def _world_waypoints(self, area: str) -> tuple[MapWaypoint, ...]:
        table = self._address(6, WORLD_TRIGGER_TABLE_OFFSET)
        waypoints = []
        for map_id in range(WORLD_TRIGGER_COUNT):
            offset = table + map_id * 5
            x, y, entry_x, entry_y, flags = self._data[offset:offset + 5]
            is_alefgard = map_id in ALEFGARD_TRIGGER_IDS
            if (area == "Underworld") != is_alefgard or (x == 0 and y == 0):
                continue
            title = AREA_MAP_NAMES.get(map_id, "Unknown location")
            waypoints.append(
                MapWaypoint(
                    x,
                    y,
                    title,
                    f"Entrance at ({entry_x},{entry_y})",
                    "entrance",
                )
            )
        return tuple(waypoints)

    def _world_encounter_regions(self, area: str) -> tuple[MapRegion, ...]:
        if area != "World":
            return ()
        grid = self._address(0, WORLD_ENCOUNTER_GRID_OFFSET)
        regions = []
        for zone_y in range(16):
            for zone_x in range(16):
                encounter_set = self._data[grid + zone_y * 16 + zone_x] & 0x3F
                enemies = self._encounter_enemies(encounter_set)
                levels = [level for _, level in enemies]
                if not levels:
                    difficulty = "No direct enemy entries"
                elif max(levels) <= 5:
                    difficulty = "Low"
                elif max(levels) <= 15:
                    difficulty = "Moderate"
                elif max(levels) <= 25:
                    difficulty = "High"
                else:
                    difficulty = "Severe"
                enemy_text = ", ".join(f"{name} (Lv {level})" for name, level in enemies)
                enemy_names = [name for name, _ in enemies]
                compact_label = (
                    enemy_names[0]
                    + (f"\n+{len(enemy_names) - 1}" if len(enemy_names) > 1 else "")
                    if enemy_names
                    else "No foes"
                )
                visible_enemies = [
                    f"{name} Lv {level}" for name, level in enemies[:4]
                ]
                if len(enemies) > len(visible_enemies):
                    visible_enemies.append(f"+{len(enemies) - len(visible_enemies)} more")
                label = "\n".join(visible_enemies) if visible_enemies else "No foes"
                color = {
                    "No direct enemy entries": "#6b7280",
                    "Low": "#27824a",
                    "Moderate": "#c58a18",
                    "High": "#d05a2a",
                    "Severe": "#b83232",
                }[difficulty]
                regions.append(
                    MapRegion(
                        zone_x * 16,
                        zone_y * 16,
                        16,
                        16,
                        f"Enemies near ({zone_x * 16 + 8},{zone_y * 16 + 8})",
                        f"{difficulty}\n{enemy_text}",
                        "encounters",
                        color,
                        label,
                        compact_label,
                    )
                )
        return tuple(regions)

    def _encounter_enemies(self, encounter_set: int) -> tuple[tuple[str, int], ...]:
        record = self._address(0, ENCOUNTER_RECORDS_OFFSET + encounter_set * ENCOUNTER_RECORD_SIZE)
        enemy_ids = []
        for enemy_id in self._data[record + 1:record + 12]:
            if enemy_id != 0xFF and enemy_id not in enemy_ids:
                enemy_ids.append(enemy_id)
        return tuple((self._enemy_name(enemy_id), self._enemy_level(enemy_id)) for enemy_id in enemy_ids)

    def _enemy_level(self, enemy_id: int) -> int:
        offset = self._prg_offset + ENEMY_RECORDS_OFFSET + enemy_id * ENEMY_RECORD_SIZE
        return self._data[offset] & 0x3F

    def _enemy_name(self, enemy_id: int) -> str:
        table_pair = (2, 3) if enemy_id < 0x40 else (10, 11)
        index = enemy_id if enemy_id < 0x40 else enemy_id - 0x40
        fragments = [
            self._translate_text(self._string_table_entry(table, index)).strip()
            for table in table_pair
        ]
        return " ".join(fragment for fragment in fragments if fragment) or f"Enemy ${enemy_id:02X}"

    def enemy_name(self, enemy_id: int) -> str:
        return self._enemy_name(enemy_id)

    def enemy_profile(self, enemy_id: int) -> EnemyProfile:
        offset = self._prg_offset + ENEMY_RECORDS_OFFSET + enemy_id * ENEMY_RECORD_SIZE
        record = self._data[offset:offset + ENEMY_RECORD_SIZE]
        if len(record) != ENEMY_RECORD_SIZE:
            raise ValueError(f"Enemy record 0x{enemy_id:02X} is outside ROM data")
        return EnemyProfile(
            level=record[0] & 0x3F,
            max_hp=record[7] | (record[0x15] & 0x03) << 8,
            max_mp=record[8],
            attack=record[5] | (record[0x13] & 0x03) << 8,
            agility=record[3],
            defense=record[6] | (record[0x14] & 0x03) << 8,
            experience=int.from_bytes(record[1:3], "little"),
            gold=record[4] | (record[0x12] & 0x03) << 8,
        )

    def item_name(self, item_id: int) -> str:
        return self._item_name(item_id)

    def decode_text(self, encoded: bytes) -> str:
        terminator = next(
            (index for index, value in enumerate(encoded) if value in {0x00, 0xFF}),
            len(encoded),
        )
        return self._translate_text(encoded[:terminator])

    def npc_metadata(
        self,
        map_id: int,
        time_value: int,
        sram: bytes,
        items: tuple[int, ...],
    ) -> tuple[NpcMetadata, ...]:
        if not 0 <= map_id < len(self._npc_lists):
            return ()
        night = time_value >= 0x78
        active_mask = 0x08 if night else 0x10
        records = tuple(
            record
            for record in self._npc_lists[map_id]
            if record[0] & active_mask
        )
        return tuple(
            self._npc_record_metadata(record, night, sram, items)
            for record in records
        )

    def _npc_record_metadata(
        self,
        record: bytes,
        night: bool,
        sram: bytes,
        items: tuple[int, ...],
    ) -> NpcMetadata:
        message_id = self._npc_message_id(record, night)
        special_handler = self._npc_special_handler(message_id)
        if special_handler is not None and special_handler in NPC_SPECIAL_ROLES:
            title, purpose = NPC_SPECIAL_ROLES[special_handler]
            status = self._npc_quest_status(special_handler, sram, items)
            detail = purpose if status is None else f"{purpose}\n{status}"
            marker = self._npc_special_marker(special_handler)
            return NpcMetadata(title, detail, status == "Completed", marker)
        role = next(
            (
                name
                for threshold, name in NPC_SERVICE_THRESHOLDS
                if message_id >= threshold
            ),
            "Townsperson",
        )
        if role in {"special", "dialogue"}:
            role = "Townsperson"
        marker = (
            "shop"
            if "shop" in role.casefold()
            else "service"
            if role != "Townsperson"
            else "person"
        )
        return NpcMetadata(role, "Talk for dialogue", marker=marker)

    @staticmethod
    def _npc_special_marker(handler: int) -> str:
        if handler in {0x0D, 0x29, 0x2E, 0x64}:
            return "boss"
        if handler in {0x02, 0x19, 0x1C, 0x1E, 0x25, 0x27, 0x2D, 0x67, 0x68, 0x6C}:
            return "item"
        if handler == 0x13:
            return "shop"
        if handler in {0x00, 0x01, 0x47, 0x65}:
            return "service"
        return "quest"

    @staticmethod
    def _npc_message_id(record: bytes, night: bool) -> int:
        flags = record[0]
        high = flags >> 6
        low_index = 2
        if night and flags & 0x02:
            high = (flags >> 5) & 0x01
            low_index = (2, 2, 5, 6)[flags & 0x03]
        if low_index >= len(record):
            return 0
        return (high << 8) | record[low_index]

    @staticmethod
    def _npc_special_handler(message_id: int) -> int | None:
        if 0x168 <= message_id < 0x1E0:
            return message_id - 0x168
        if message_id >= 0x3C0:
            return 0x4D + message_id - 0x3C0
        return None

    @staticmethod
    def _npc_quest_status(
        handler: int, sram: bytes, items: tuple[int, ...]
    ) -> str | None:
        checks = {
            0x02: (0xBF, 0x20),
            0x03: (0xCD, 0x01),
            0x16: (0xB7, 0x04),
            0x19: (0xBF, 0x80),
            0x1E: (0xCE, 0x20),
            0x22: (0xB9, 0x08),
            0x25: (0xCE, 0x01),
            0x27: (0xCA, 0x40),
            0x29: (0xCB, 0x80),
            0x2C: (0xCB, 0x10),
            0x2D: (0xBF, 0x10),
            0x2E: (0xB9, 0x80),
            0x42: (0xBA, 0x04),
            0x5C: (0xB8, 0x80),
            0x67: (0xBF, 0x08),
            0x68: (0xBF, 0x04),
            0x6C: (0xBF, 0x02),
        }
        item_checks = {0x1C: 0x6D}
        field = checks.get(handler)
        if field is not None:
            offset, mask = field
            return "Completed" if len(sram) > offset and sram[offset] & mask else "Available"
        item_id = item_checks.get(handler)
        if item_id is not None:
            return "Obtained" if item_id in items else "Available"
        return None

    def _index_npc_lists(self) -> tuple[tuple[bytes, ...], ...]:
        offset = self._address(0x0D, NPC_LISTS_OFFSET)
        bank_end = self._address(0x0E, 0)
        lists = []
        for _ in range(NPC_LIST_COUNT):
            records = []
            while offset < bank_end and self._data[offset] != 0:
                size = NPC_RECORD_SIZES[self._data[offset] & 0x07]
                if offset + size > bank_end:
                    raise ValueError("Truncated NPC record table")
                records.append(bytes(self._data[offset:offset + size]))
                offset += size
                if len(records) > 64:
                    raise ValueError("NPC record limit exceeded")
            if offset >= bank_end:
                raise ValueError("Truncated NPC list table")
            offset += 1
            lists.append(tuple(records))
        return tuple(lists)

    def collectible_overlays(
        self,
        chest_flags: bytes,
        ram: bytes = b"",
        sram: bytes = b"",
        items: tuple[int, ...] = (),
    ) -> tuple[MapOverlay, ...]:
        if len(chest_flags) < 26:
            return ()
        table = self._address(6, WORLD_TRIGGER_TABLE_OFFSET)
        grouped: dict[int, list[ChestRecord]] = {}
        for chest in self._chests:
            if not chest.collectible:
                continue
            root_id = (
                chest.map_id
                if chest.map_id < WORLD_TRIGGER_COUNT
                else CHEST_WORLD_ROOTS.get(chest.map_id)
            )
            if root_id is not None:
                grouped.setdefault(root_id, []).append(chest)
        overlays: dict[str, list[MapWaypoint]] = {"world": [], "underworld": []}
        offsets = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1))
        for root_id, chests in grouped.items():
            if root_id == 0x9C:
                if len(ram) <= 0x9C:
                    continue
                x, y = ram[0x9B:0x9D]
                layer_key = "world"
            elif root_id in EXTENDED_WORLD_ANCHORS:
                layer_key, x, y = EXTENDED_WORLD_ANCHORS[root_id]
            else:
                trigger = table + root_id * 5
                x, y = self._data[trigger:trigger + 2]
                layer_key = (
                    "underworld" if root_id in ALEFGARD_TRIGGER_IDS else "world"
                )
            if x == 0 and y == 0:
                continue
            by_map: dict[int, list[ChestRecord]] = {}
            for chest in chests:
                by_map.setdefault(chest.map_id, []).append(chest)
            for group_index, (map_id, map_chests) in enumerate(by_map.items()):
                offset_x, offset_y = offsets[group_index % len(offsets)]
                statuses = [
                    self._chest_is_open(chest_flags, chest.global_index)
                    for chest in map_chests
                ]
                remaining = statuses.count(False)
                detail = "\n".join(
                    f"{'Collected' if opened else 'Available'}: {chest.description}"
                    for chest, opened in zip(map_chests, statuses)
                )
                title = AREA_MAP_NAMES.get(map_id, "Treasure")
                overlays[layer_key].append(
                    MapWaypoint(
                        x + offset_x,
                        y + offset_y,
                        f"{title} treasure ({remaining} remaining)",
                        detail,
                        "collectibles",
                        not remaining,
                    )
                )
        self._append_scripted_collectibles(overlays, chest_flags, sram, items)
        return tuple(
            MapOverlay(layer_key, tuple(waypoints))
            for layer_key, waypoints in overlays.items()
            if waypoints
        )

    def _append_scripted_collectibles(
        self,
        overlays: dict[str, list[MapWaypoint]],
        chest_flags: bytes,
        sram: bytes,
        items: tuple[int, ...],
    ) -> None:
        table = self._address(6, WORLD_TRIGGER_TABLE_OFFSET)
        for collectible in SCRIPTED_COLLECTIBLES:
            if collectible.flag_index is not None:
                completed = self._chest_is_open(
                    chest_flags, collectible.flag_index
                )
            elif collectible.map_id == 0xCF:
                completed = len(sram) > 0xCA and bool(sram[0xCA] & 0x02)
            else:
                completed = collectible.item_id in items
            item_name = self._item_name(collectible.item_id)
            status = "Collected" if completed else "Available"

            if collectible.map_id is not None:
                local_title = AREA_MAP_NAMES.get(
                    collectible.map_id, "Hidden item"
                )
                overlays.setdefault(
                    f"area-{collectible.map_id:02x}", []
                ).append(
                    MapWaypoint(
                        collectible.x,
                        collectible.y,
                        item_name,
                        f"{status} in {local_title}",
                        "collectibles",
                        completed,
                    )
                )

            if collectible.world_root is None:
                layer_key, world_x, world_y = "world", collectible.x, collectible.y
                location = "World Tree grove"
            elif collectible.world_root in EXTENDED_WORLD_ANCHORS:
                layer_key, world_x, world_y = EXTENDED_WORLD_ANCHORS[
                    collectible.world_root
                ]
                location = AREA_MAP_NAMES.get(
                    collectible.map_id or collectible.world_root,
                    "Hidden location",
                )
            else:
                trigger = table + collectible.world_root * 5
                world_x, world_y = self._data[trigger:trigger + 2]
                layer_key = (
                    "underworld"
                    if collectible.world_root in ALEFGARD_TRIGGER_IDS
                    else "world"
                )
                location = AREA_MAP_NAMES.get(
                    collectible.map_id or collectible.world_root,
                    "Hidden location",
                )
            overlays.setdefault(layer_key, []).append(
                MapWaypoint(
                    world_x + 2,
                    world_y + 1,
                    f"{location} hidden item",
                    f"{status}: {item_name}",
                    "collectibles",
                    completed,
                )
            )

    @staticmethod
    def _chest_is_open(chest_flags: bytes, global_index: int) -> bool:
        return bool(
            chest_flags[global_index >> 3] & (0x80 >> (global_index & 0x07))
        )

    def _index_chests(self) -> tuple[ChestRecord, ...]:
        table = self._address(0x0A, CHEST_COUNT_TABLE_OFFSET)
        pairs = tuple(
            self._data[table + index * 2:table + index * 2 + 2]
            for index in range(CHEST_COUNT_RECORDS)
        )
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError("Truncated chest count table")
        if sum(pair[1] for pair in pairs) != CHEST_CONTENT_COUNT:
            raise ValueError("Unexpected chest count table")
        contents = table + CHEST_COUNT_RECORDS * 2
        records = []
        global_index = 0
        for map_id, count in pairs:
            for local_index in range(count):
                value = self._data[contents + global_index]
                description, collectible = self._chest_description(value)
                records.append(
                    ChestRecord(
                        global_index,
                        map_id,
                        local_index,
                        description,
                        collectible,
                    )
                )
                global_index += 1
        return tuple(records)

    def _chest_description(self, value: int) -> tuple[str, bool]:
        if value == 0xFF:
            return "Empty chest", False
        if value == 0xFE:
            return "Mimic", False
        if value == 0xFD:
            return "Man-eater", False
        if value == 0xFC:
            return "Meteorite Armband", True
        if value & 0x80 or value == 0x7F:
            return f"{(value & 0x7F) * 8} gold", True
        return self._item_name(value), True

    def _item_name(self, item_id: int) -> str:
        table_pair = (0, 1) if item_id < 0x40 else (8, 9)
        index = item_id if item_id < 0x40 else item_id - 0x40
        fragments = [
            self._translate_text(self._string_table_entry(table, index)).strip()
            for table in table_pair
        ]
        return " ".join(fragment for fragment in fragments if fragment) or "Unknown item"

    def _string_table_entry(self, table: int, index: int) -> bytes:
        directory = self._prg_offset + STRING_TABLE_DIRECTORY_OFFSET
        pointer = int.from_bytes(self._data[directory + table * 2:directory + table * 2 + 2], "little")
        offset = self._prg_offset + pointer
        for _ in range(index):
            terminator = self._data.index(0xFF, offset)
            offset = terminator + 1
        terminator = self._data.index(0xFF, offset)
        return bytes(self._data[offset:terminator])

    @staticmethod
    def _translate_text(encoded: bytes) -> str:
        text = []
        for value in encoded:
            if 0x01 <= value <= 0x0A:
                text.append(chr(ord("0") + value - 1))
            elif 0x0B <= value <= 0x24:
                text.append(chr(ord("a") + value - 0x0B))
            elif 0x25 <= value <= 0x3E:
                text.append(chr(ord("A") + value - 0x25))
            elif value in (0x50, 0x60, 0xA5):
                text.append(" ")
            elif value == 0x57:
                text.append(".")
            elif value in (0x58, 0x6B):
                text.append("-")
            elif value in (0x62, 0x66, 0x67, 0x68, 0x72):
                text.append("'")
            elif value == 0x6A:
                text.append(",")
        return "".join(text)

    def render_world_map(self, key: str) -> Path:
        try:
            _, _, table_offset, height, width = WORLD_MAP_SPECS[key]
        except KeyError as error:
            raise ValueError(f"Unknown world map: {key}") from error
        output = self.cache_directory / "maps" / f"{key}.png"
        if output.is_file():
            return output
        table = self._address(5, table_offset)
        rows = []
        for row in range(height):
            pointer_offset = table + row * 2
            pointer = int.from_bytes(self._data[pointer_offset:pointer_offset + 2], "little")
            if not 0x8000 <= pointer < 0xC000:
                raise ValueError(f"{key} row {row} has an invalid pointer")
            rows.append(decode_world_row(self._data, self._address(5, pointer - 0x8000), width))
        graphics = self._world_graphics()
        self._world_renderer(tuple(rows), graphics, output)
        self._write_manifest()
        return output

    def _world_graphics(self) -> WorldGraphics:
        bank5 = self._address(5, 0)
        bank9 = self._address(9, 0)
        metatiles = []
        attributes = []
        source_patterns: list[int] = []
        patterns: list[bytes] = []
        for tile in range(WORLD_DESCRIPTOR_COUNT):
            offset = bank5 + WORLD_DESCRIPTOR_OFFSET + tile * 3
            flags, pattern, attribute = self._data[offset:offset + 3]
            references = []
            shape = flags >> 4
            if shape == 0x0F:
                template = bank5 + WORLD_EXPLICIT_PATTERNS_OFFSET + pattern * 5
                rotations = self._data[template]
                for index in range(4):
                    references.append(
                        self._data[template + index + 1]
                        | ((rotations >> (index * 2) & 0x03) << 8)
                    )
            else:
                high = flags & 0x03
                delta = bank5 + WORLD_DESCRIPTOR_DELTAS_OFFSET + shape * 3
                for index in range(4):
                    references.append(pattern | (high << 8))
                    change = int.from_bytes(self._data[delta + index:delta + index + 1], "little", signed=True)
                    combined = (pattern | (high << 8)) + change
                    pattern, high = combined & 0xFF, (combined >> 8) & 0x03
            rendered = []
            for reference in references:
                if reference not in source_patterns:
                    source_patterns.append(reference)
                    source = bank9 + reference * 16
                    patterns.append(bytes(self._data[source:source + 16]))
                rendered.append(WORLD_PATTERN_BASE + source_patterns.index(reference))
            metatiles.append(tuple(rendered))
            attributes.append((flags >> 2) & 0x03)
        if WORLD_PATTERN_BASE + len(patterns) != WORLD_RAW_PATTERN_BASE:
            raise ValueError("World metatile synthesis produced an unexpected pattern count")
        raw_start = bank9
        patterns.extend(
            bytes(self._data[raw_start + index * 16:raw_start + (index + 1) * 16])
            for index in range(WORLD_RAW_PATTERN_COUNT)
        )
        explicit = bank5 + WORLD_EXPLICIT_METATILES_OFFSET
        metatiles.extend(
            tuple(self._data[explicit + index * 4:explicit + (index + 1) * 4])
            for index in range(WORLD_EXPLICIT_METATILE_COUNT)
        )
        attributes.extend((0,) * WORLD_EXPLICIT_METATILE_COUNT)
        palette_source = self._address(6, WORLD_DAY_PALETTE_OFFSET)
        source_colors = self._data[palette_source:palette_source + 12]
        palette = tuple(
            source_colors[column + row * 4]
            for column in range(4)
            for row in range(3)
        )
        return WorldGraphics(
            tuple(metatiles),
            tuple(attributes),
            tuple(patterns),
            palette,
        )

    def render_area_map(self, map_id: int) -> Path:
        descriptor = next((item for item in self._descriptors if item.map_id == map_id), None)
        if descriptor is None:
            raise ValueError(f"Area map 0x{map_id:02X} is unavailable")
        output = self.cache_directory / "maps" / f"area-{map_id:02x}.png"
        if output.is_file():
            return output
        tiles = MdecDecoder(self._data, descriptor.data_offset).decode()
        self._renderer(tiles, self._area_graphics(descriptor), output)
        self._write_manifest()
        return output

    def _area_graphics(self, descriptor: AreaMapDescriptor) -> AreaGraphics:
        bank5 = self._address(5, 0)
        records = []
        if descriptor.tileset < 9:
            groups = (
                descriptor.tileset * 2,
                0,
                descriptor.tileset * 2 + 1,
                1,
            )
            for group in groups:
                start = bank5 + AREA_DESCRIPTOR_TABLE_OFFSET + group * 24
                records.extend(
                    tuple(self._data[start + index * 3:start + index * 3 + 3])
                    for index in range(8)
                )
        else:
            group = (descriptor.tileset - 8) * 4 + 0x12
            start = bank5 + AREA_DESCRIPTOR_TABLE_OFFSET + group * 24
            records.extend(
                tuple(self._data[start + index * 3:start + index * 3 + 3])
                for index in range(32)
            )

        for extra in self._area_extra_descriptors(descriptor.tileset, descriptor.map_id):
            start = bank5 + AREA_DESCRIPTOR_TABLE_OFFSET + 0x900 + extra
            records.append(tuple(self._data[start:start + 3]))

        references: list[int] = []
        metatiles = []
        attributes = []
        for flags, base_pattern, _ in records:
            attributes.append((flags >> 2) & 0x03)
            if flags >> 4 == 0x0F:
                explicit = (
                    bank5 + AREA_EXPLICIT_PATTERN_REFS_OFFSET + base_pattern * 5
                )
                high_bits = self._data[explicit]
                tile_references = [
                    self._data[explicit + index + 1]
                    | (((high_bits >> (index * 2)) & 0x03) << 8)
                    for index in range(4)
                ]
            else:
                reference = base_pattern | ((flags & 0x03) << 8)
                tile_references = []
                for index in range(4):
                    tile_references.append(reference)
                    if index < 3:
                        delta_offset = (
                            bank5
                            + AREA_PATTERN_DELTAS_OFFSET
                            + (flags >> 4) * 3
                            + index
                        )
                        delta = int.from_bytes(
                            self._data[delta_offset:delta_offset + 1],
                            "little",
                            signed=True,
                        )
                        reference = (reference + delta) & 0x03FF
            rendered = []
            for reference in tile_references:
                if reference not in references:
                    references.append(reference)
                rendered.append(references.index(reference))
            metatiles.append(tuple(rendered))

        override_table = bank5 + AREA_TILE_OVERRIDE_TABLE_OFFSET
        for index in range(AREA_TILE_OVERRIDE_COUNT):
            offset = override_table + index * 4
            map_id, source, target, _ = self._data[offset:offset + 4]
            if map_id == descriptor.map_id:
                metatiles[target] = metatiles[source]
                attributes[target] = attributes[source]
                break

        bank9 = self._address(9, 0)
        patterns = tuple(
            bytes(self._data[bank9 + reference * 16:bank9 + (reference + 1) * 16])
            for reference in references
        )
        return AreaGraphics(
            tuple(metatiles[:32]),
            tuple(attributes[:32]),
            patterns,
            self._area_palette(descriptor.map_id, descriptor.tileset),
        )

    @staticmethod
    def _area_extra_descriptors(tileset: int, map_id: int) -> tuple[int, int]:
        if tileset < 9 or tileset == 0x0B:
            if map_id in {0x17, 0x18, 0x8D, 0x91}:
                return 0x36, 0x30
            if map_id in {0x45, 0x49, 0x4E, 0x59, 0x5F, 0x7A, 0x1D, 0x94}:
                return 0x30, 0x30
            return 0x33, 0x30
        if tileset < 0x0B:
            return 0x39, 0x30
        if tileset < 0x19:
            return 0x30, 0x30
        return 0x3C, 0x3C

    def _area_palette(self, map_id: int, tileset: int) -> tuple[int, ...]:
        bank7 = self._address(7, 0)
        palette_library = bank7 + AREA_PALETTE_LIBRARY_OFFSET
        day = 0

        if map_id == 0x08:
            palette_index = 0
        elif map_id < 0x2D:
            palette_index = self._packed_area_palette_index(bank7, map_id, day)
            return tuple(
                self._data[
                    palette_library + palette_index:
                    palette_library + palette_index + AREA_COMMON_PALETTE_SIZE
                ]
            )
        elif map_id < 0x41:
            palette_index = map_id - 0x2C
        elif map_id == 0x58:
            palette_index = 0x15
        elif map_id == 0x5B:
            palette_index = 0x16
        elif map_id == 0x85:
            palette_index = 0x17
        elif map_id < 0x9C:
            adjusted = map_id - 0x14
            palette_index = self._packed_area_palette_index(bank7, adjusted, day)
            return tuple(
                self._data[
                    palette_library + palette_index:
                    palette_library + palette_index + AREA_COMMON_PALETTE_SIZE
                ]
            )
        elif map_id < 0x9F:
            palette_index = self._data[bank7 + AREA_PALETTE_DATA2_OFFSET + day]
            return tuple(
                self._data[
                    palette_library + palette_index:
                    palette_library + palette_index + AREA_COMMON_PALETTE_SIZE
                ]
            )
        else:
            palette_index = map_id - 0x87

        palette_group = self._data[bank7 + AREA_PALETTE_DATA3_OFFSET + palette_index]
        if map_id == 0xD5 or tileset >= 0x19:
            palette_group += day
        pair_offset = bank7 + AREA_PALETTE_DATA4_OFFSET + palette_group * 2
        packed_groups = self._data[pair_offset:pair_offset + 2]
        groups = tuple(
            value
            for packed in packed_groups
            for value in (packed >> 4, packed & 0x0F)
        )
        base = self._data[bank7 + AREA_PALETTE_DATA5_OFFSET + tileset - 0x0C]
        colors = []
        for group in groups:
            start = palette_library + base + group * 3
            colors.extend(self._data[start:start + 3])
        return tuple(colors)

    def _packed_area_palette_index(self, bank7: int, map_index: int, day: int) -> int:
        packed = self._data[
            bank7 + AREA_PALETTE_DATA0_OFFSET + (map_index >> 2)
        ]
        shift_count = ((map_index * 2 + day) & 0x07) + 1
        selected = (packed >> (8 - shift_count)) & 0x01
        selector = day * 2 + selected
        return self._data[bank7 + AREA_PALETTE_DATA1_OFFSET + selector]

    def _index_area_maps(self) -> tuple[AreaMapDescriptor, ...]:
        global_bank_table = self._address(0x1F, 0xE917 - 0xC000)
        global_file_table = self._address(0x1F, 0xE9ED - 0xC000)
        file_id = 0x1E
        bank_byte = self._data[global_bank_table + (file_id >> 1)]
        bank = (bank_byte >> ((1 - (file_id & 1)) * 4)) & 0x0F
        local_id = self._data[global_file_table + file_id]
        local_pointer = int.from_bytes(
            self._data[self._address(bank, 0) + local_id * 2:self._address(bank, 0) + local_id * 2 + 2],
            "little",
        )
        directory_file = self._address(bank, local_pointer - 0x8000)
        directory_pointer = int.from_bytes(self._data[directory_file:directory_file + 2], "little")
        directory = self._address(7, directory_pointer - 0x8000)
        descriptors = []
        for map_id in range(AREA_MAP_COUNT):
            entry = directory + map_id * 3
            pointer = int.from_bytes(self._data[entry:entry + 2], "little")
            tileset = self._data[entry + 2]
            if pointer == 0:
                continue
            if not 0x8000 <= pointer < 0xC000:
                break
            data_offset = self._address(6 if tileset < 0x0C else 7, pointer - 0x8000)
            if data_offset + 3 > len(self._data):
                raise ValueError(f"Area map 0x{map_id:02X} points outside the ROM")
            width, height = self._data[data_offset:data_offset + 2]
            if not 0 < width <= MAX_MAP_DIMENSION or not 0 < height <= MAX_MAP_DIMENSION:
                raise ValueError(f"Area map 0x{map_id:02X} has invalid dimensions")
            descriptors.append(AreaMapDescriptor(map_id, tileset, width, height, data_offset))
        return tuple(descriptors)

    def _address(self, bank: int, offset: int) -> int:
        address = self._prg_offset + bank * 0x4000 + offset
        if address < self._prg_offset or address >= len(self._data):
            raise ValueError("ROM bank address is outside PRG data")
        return address

    def _write_manifest(self) -> None:
        manifest = self.cache_directory / "metadata.json"
        if manifest.is_file():
            return
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "extractor_version": EXTRACTOR_VERSION,
                    "rom_hash": self.content_hash,
                    "area_maps": [asdict(item) for item in self._descriptors],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

