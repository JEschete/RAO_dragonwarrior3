from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from retroarch_overlay.core.contracts import MemoryReader
from retroarch_overlay.core.retroachievements import RAProgress
from retroarch_overlay.models import GameDisplaySpec, MapDocument, MapOverlay, MapPosition, MapWaypoint, OverlaySnapshot, PanelAction, PanelRow, PanelSection, RetroArchStatus
from retroarch_overlay.retroarch import RetroArchError
from .achievements import ACHIEVEMENTS, ACHIEVEMENTS_BY_ID
from .battle import EnemyProfile, SPELL_FLAGS_ADDRESS, learned_battle_spells, selected_battle_spell
from .manifest import RA_GAME_ID, RA_HASHES


RAM_SIZE = 0x0800
SRAM_ADDRESS = 0x6000
SRAM_READ_SIZE = 0x0ACC
CHEST_FLAGS_START = 0x8E
CHEST_FLAGS_END = 0xA8
NPC_POSITIONS_START = 0x0110
NPC_POSITIONS_END = 0x0174

JOBS = ("Hero", "Wizard", "Pilgrim", "Sage", "Soldier", "Merchant", "Fighter", "Goof-off")
TOWNS = (
    "Aliahan", "Reeve", "Romaly", "Kanave", "Noaniels", "Assaram", "Isis", "Portoga",
    "Baharata", "Dhama", "Lancel", "Jipang", "Eginbear", "Samanao", "Soo", "Tantegel",
    "Hauksness", "Cantlin", "Kol", "Rimuldar",
)
ITEM_NAMES = {
    0x08: "Poison Needle",
    0x16: "Sword of Illusion",
    0x1B: "Staff of Thunder",
    0x1C: "Sword of Kings",
    0x3B: "Shield of Heroes",
    0x47: "Sacred Amulet",
    0x4C: "Book of Satori",
    0x4E: "Wizard's Ring",
    0x4F: "Black Pepper",
    0x52: "Vase of Drought",
    0x53: "Lamp of Darkness",
    0x54: "Staff of Change",
    0x58: "Thief's Key",
    0x59: "Magic Key",
    0x5A: "Final Key",
    0x69: "Leaf of the World Tree",
    0x6D: "Water Blaster",
    0x6F: "Echoing Flute",
    0x71: "Silver Harp",
    0x72: "Sphere of Light",
    0x76: "Rainbow Drop",
    0x77: "Silver Orb",
    0x78: "Red Orb",
    0x79: "Yellow Orb",
    0x7A: "Purple Orb",
    0x7B: "Blue Orb",
    0x7C: "Green Orb",
}
ITEM_ACHIEVEMENTS = {
    0x08: 50421,
    0x16: 50436,
    0x1B: 50427,
    0x1C: 50433,
    0x3B: 50430,
    0x47: 50457,
    0x4C: 50464,
    0x4E: 50463,
    0x4F: 50445,
    0x52: 50423,
    0x53: 50422,
    0x54: 50451,
    0x58: 50439,
    0x59: 50443,
    0x5A: 50446,
    0x69: 50431,
    0x6D: 50429,
    0x6F: 50425,
    0x71: 50426,
    0x77: 50454,
    0x78: 50450,
    0x79: 50452,
    0x7A: 50448,
    0x7B: 50449,
    0x7C: 50447,
}
EXACT_DETECTOR_COUNT = len(ITEM_ACHIEVEMENTS) + 7
ORB_ITEMS = (0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C)
KEY_ITEMS = (0x58, 0x59, 0x5A, 0x4F, 0x52, 0x53, 0x54, 0x6D, 0x6F, 0x71, 0x72, 0x76)
KEY_ITEM_UNLOCKS = {
    0x58: ("Thief's Key doors", "Early Aliahan and Reeve checks"),
    0x59: ("Magic Key doors", "Pyramid, Portoga, and midgame locked rooms"),
    0x5A: ("Final Key doors", "Jails, late-game shrines, and final key checks"),
    0x4F: ("Portoga ship trade", "Turn in Black Pepper to unlock world sailing"),
    0x52: ("Shoals access", "Use the Vase of Drought for the Final Key route"),
    0x53: ("Night control", "Force night checks without resting"),
    0x54: ("Samanao route", "Expose the false king and continue the orb chain"),
    0x6D: ("New Town chain", "Merchantville progression and Yellow Orb route"),
    0x6F: ("Orb search aid", "Echoing Flute helps identify orb locations"),
    0x71: ("Encounter control", "Silver Harp forces fights when grinding"),
    0x72: ("Zoma safety", "Sphere of Light weakens Zoma"),
    0x76: ("Final dungeon access", "Rainbow bridge to Zoma's Castle"),
}
ORB_HINTS = {
    0x77: "Necrogond shrine reward",
    0x78: "Pirates / hidden route",
    0x79: "Merchantville rebellion",
    0x7A: "Orochi / Jipang chain",
    0x7B: "Lancel / Gaia's Navel route",
    0x7C: "Tedanki / prisoner route",
}
ROUTE_PLAN = (
    ("Recruit a full party", "Build four active characters before leaving Aliahan."),
    ("Thief's Key", "Go to Reeve and unlock early locked-door checks."),
    ("Magic Key", "Push toward Isis and Pyramid."),
    ("Black Pepper", "Resolve Baharata and return to Portoga for the ship."),
    ("Final Key", "Use the ship and Vase of Drought route."),
    ("Orb hunt", "Collect all six orbs and place them in Liamland."),
    ("Ramia", "Finish Liamland after all orbs are placed."),
    ("Baramos", "Use Ramia to reach Baramos Castle."),
    ("Alefgard", "After Baramos, push the underworld route."),
    ("Rainbow Drop", "Build the bridge to Zoma's Castle."),
    ("Zoma", "Finish the final route."),
)
SHOPPING_GOALS = (
    (0, "Save for early key and gear checks."),
    (1000, "Comfortable early-game buffer."),
    (5000, "Good midgame equipment fund."),
    (15000, "Late-game purchases and recovery buffer."),
)
TIME_WINDOWS = (
    "Sunrise/Morning: travel visibility and normal town access",
    "Afternoon/Evening: continue overworld routing before night checks",
    "Dusk/Night: use for night-only NPC and town state checks",
    "Lamp of Darkness: force night when a route expects it",
)


@dataclass(frozen=True, slots=True)
class GameState:
    levels: tuple[int, ...]
    jobs: tuple[int, ...]
    party_ids: tuple[int, ...]
    items: tuple[int, ...]
    orb_flags: int
    pyramid_chests: int
    samanao_chests: int
    orbs_found: int
    orbs_placed: int
    pedestals: int
    arena_active: bool
    arena_winner: int
    arena_pick: int
    chest_flags: bytes
    rainbow_bridge: bool
    rainbow_drop_obtained: bool
    alefgard_open: bool
    baramos_defeated: bool
    game_complete: bool
    ship_granted: bool
    ship_owned: bool


class DragonWarrior3Adapter:
    name = "Dragon Warrior III"
    ra_game_id = RA_GAME_ID
    ra_hashes = RA_HASHES

    def __init__(
        self,
        account_progress: RAProgress | None = None,
        map_document: MapDocument | None = None,
        save_path: Path | None = None,
        enemy_name: Callable[[int], str] | None = None,
        collectible_overlays: Callable[
            [bytes, bytes, bytes, tuple[int, ...]], tuple[MapOverlay, ...]
        ] | None = None,
        npc_metadata: Callable[
            [int, int, bytes, tuple[int, ...]], tuple[object, ...]
        ] | None = None,
        item_name: Callable[[int], str] | None = None,
        decode_text: Callable[[bytes], str] | None = None,
        enemy_profile: Callable[[int], EnemyProfile] | None = None,
    ) -> None:
        self._previous: GameState | None = None
        self._unlocked: set[int] = set()
        self._recent_items: deque[int] = deque(maxlen=8)
        self._account_progress = account_progress
        self._map_document = map_document
        self._save_path = save_path
        self._enemy_name = enemy_name
        self._collectible_overlays = collectible_overlays
        self._npc_metadata = npc_metadata
        self._item_name = item_name
        self._decode_text = decode_text
        self._enemy_profile = enemy_profile

    def supports(self, status: RetroArchStatus, content_hash: str | None = None) -> bool:
        core = status.core.casefold().replace(" ", "_")
        if not any(name in core for name in ("mesen", "nestopia", "fceumm", "fceux", "nes")):
            return False
        if content_hash is not None:
            return content_hash.casefold() in self.ra_hashes
        content = status.content.casefold()
        return "dragon warrior iii" in content or "dragon quest iii" in content

    def snapshot(self, memory: MemoryReader) -> OverlaySnapshot:
        try:
            ram = memory.read_memory(0, RAM_SIZE)
        except RetroArchError as error:
            if "no descriptor" in str(error).casefold():
                raise RetroArchError(
                    "The active NES core does not expose readable memory; "
                    "launch Dragon Warrior III with Mesen or FCEUmm"
                ) from error
            raise
        sram = memory.read_memory(SRAM_ADDRESS, SRAM_READ_SIZE)
        merged_sram = self._merge_save_sram(sram)
        state = self._state(ram, merged_sram)
        self._observe(state)

        map_id = ram[0x008B]
        map_bank = ram[0x002F]
        if map_bank in {0, 2}:
            coordinates = (ram[0x002A], ram[0x002B])
            area = "World" if map_bank == 0 else "Underworld"
        else:
            coordinates = (ram[0x0030], ram[0x0031])
            area = "Dungeon / town"
        map_name = self._map_name(area, map_id)
        location = f"{map_name} · ({coordinates[0]},{coordinates[1]})"

        battle = ram[0x0032] == 0xFD
        if battle:
            sections = [
                self._battle_section(ram),
                self._battle_party_section(ram, sram, state),
                self._battle_spell_section(ram, state),
            ]
        else:
            sections = [
                self._objective_section(ram, state, area),
                self._party_section(ram, state),
                self._achievement_section(),
            ]
            sections.extend(
                (
                    self._unlock_section(state),
                    self._orb_section(state),
                    self._resource_section(ram, state),
                    self._progress_section(merged_sram, state),
                    self._world_section(ram),
                )
            )
        if self._recent_items and not battle:
            sections.append(
                PanelSection(
                    "New items observed",
                    tuple(
                        PanelRow(self._item_label(item_id))
                        for item_id in self._recent_items
                    ),
                    actions=(
                        PanelAction(
                            "OPEN RECENT ITEMS",
                            "Recent Items Observed",
                            tuple(
                                PanelRow(self._item_detail(item_id), item_id in ITEM_ACHIEVEMENTS)
                                for item_id in self._recent_items
                            ),
                        ),
                    ),
                )
            )
        map_overlays = list(
            self._collectible_overlays(
                state.chest_flags, ram, merged_sram, state.items
            )
            if self._collectible_overlays is not None
            else ()
        )
        metadata = (
            self._npc_metadata(map_id, ram[0x06DF], merged_sram, state.items)
            if self._npc_metadata is not None
            else ()
        )
        npc_overlay = self._npc_overlay(ram, map_id, map_bank, map_name, metadata)
        if npc_overlay is not None:
            map_overlays.append(npc_overlay)
        return OverlaySnapshot(
            self.name,
            f"Battle · {location}" if battle else location,
            tuple(sections),
            MapPosition(area, map_id, *coordinates, map_bank in {0, 2}),
            supports_caught_filter=True,
            map_document=self._map_document,
            map_overlays=tuple(map_overlays),
            display_spec=GameDisplaySpec("nes-4-3", 4, 3),
        )

    def _map_name(self, area: str, map_id: int) -> str:
        if area == "World":
            return "Main World"
        if area == "Underworld":
            return "Alefgard"
        if self._map_document is not None:
            layer = next(
                (layer for layer in self._map_document.layers if layer.map_id == map_id),
                None,
            )
            if layer is not None:
                return layer.title
        return "Unknown indoor location"

    @staticmethod
    def _npc_overlay(
        ram: bytes,
        map_id: int,
        map_bank: int,
        map_name: str,
        metadata: tuple[object, ...] = (),
    ) -> MapOverlay | None:
        if map_bank in {0, 2}:
            return None
        waypoints = []
        for slot, offset in enumerate(
            range(NPC_POSITIONS_START, NPC_POSITIONS_END, 4)
        ):
            x, y = ram[offset:offset + 2]
            if x == 0xFF:
                break
            if (x == 0 and y == 0) or x >= 0xF0 or y >= 0xF0:
                continue
            npc = metadata[slot] if slot < len(metadata) else None
            title = getattr(npc, "title", "Townsperson")
            purpose = getattr(npc, "detail", "Talk for dialogue")
            completed = bool(getattr(npc, "completed", False))
            marker = str(getattr(npc, "marker", "person"))
            waypoints.append(
                MapWaypoint(
                    x,
                    y,
                    str(title),
                    f"{purpose}\nLive position in {map_name}",
                    "npcs",
                    completed,
                    marker,
                )
            )
        if not waypoints:
            return None
        return MapOverlay(f"area-{map_id:02x}", tuple(waypoints))

    def _objective_section(self, ram: bytes, state: GameState, area: str) -> PanelSection:
        objective, detail = self._current_objective(state, area)
        rows = [PanelRow(objective), PanelRow(detail)]
        warnings = self._party_warnings(ram, state)
        if warnings:
            rows.append(PanelRow("Risk: " + " · ".join(warnings), False))
        return PanelSection(
            "Current objective",
            tuple(rows),
            alert=bool(warnings),
            actions=(
                PanelAction("OPEN ROUTE PLAN", "Dragon Warrior III Route Plan", self._route_plan_rows(state, area)),
                PanelAction("OPEN KEY ITEM UNLOCKS", "Key Item Unlocks", self._key_item_rows(state)),
                PanelAction("OPEN RA PRIORITIES", "RetroAchievements Priorities", self._ra_priority_rows(state)),
            ),
        )

    def _current_objective(self, state: GameState, area: str) -> tuple[str, str]:
        if state.game_complete:
            return "Adventure complete", "Zoma is defeated and the Erdrick ending flag is set."
        if self._active_count(state) < 4:
            return "Next: recruit a full party", "Build four active party members before committing to the overworld."
        if not self._has_item(state, 0x58):
            return "Next: Reeve · Thief's Key", "Unlock the first door tier and early item checks."
        if not self._has_item(state, 0x59):
            return "Next: Isis / Pyramid · Magic Key", "Push the desert route and open the midgame door tier."
        if not state.ship_granted and self._has_item(state, 0x4F):
            return "Next: Portoga · deliver Black Pepper", "Complete the trade with the king to receive the ship."
        if state.ship_granted and not state.ship_owned:
            return "Next: Portoga · board the ship", "The ship has been granted and is waiting to be picked up."
        if not state.ship_granted:
            return "Next: Baharata · Black Pepper", "Finish the trade chain that leads to the ship."
        if not self._has_item(state, 0x5A):
            return "Next: Final Key route", "Use ship access and the Vase of Drought chain to open jail doors."
        if state.orbs_found < 6:
            return f"Next: orb hunt · {state.orbs_found}/6 found", "Use key-item access to clean up the six orb routes."
        if state.orbs_placed < 6 or state.pedestals < 6:
            return "Next: Liamland · place the orbs", "Place every orb and light the pedestals to hatch Ramia."
        if not state.baramos_defeated:
            return "Next: Baramos", "Use Ramia to reach Baramos Castle and defeat him."
        if not state.alefgard_open:
            return "Next: Aliahan · report victory", "Finish the celebration sequence to open the Alefgard passage."
        if not state.rainbow_drop_obtained:
            return "Next: Rainbow Drop", "Gather Alefgard requirements and build the bridge to Zoma's Castle."
        if not state.rainbow_bridge:
            return "Next: use the Rainbow Drop", "Create the bridge to Zoma's Castle."
        if not self._has_item(state, 0x72):
            return "Next: Sphere of Light", "Collect it unless you are routing the no-Sphere challenge."
        return "Next: Zoma", "Final route is open; prepare resources and finish the game."

    def _route_plan_rows(self, state: GameState, area: str) -> tuple[PanelRow, ...]:
        checks = {
            "Recruit a full party": self._active_count(state) >= 4,
            "Thief's Key": self._has_item(state, 0x58),
            "Magic Key": self._has_item(state, 0x59),
            "Black Pepper": state.ship_granted,
            "Final Key": self._has_item(state, 0x5A),
            "Orb hunt": state.orbs_found >= 6,
            "Ramia": state.orbs_placed >= 6 and state.pedestals >= 6,
            "Baramos": state.baramos_defeated,
            "Alefgard": state.alefgard_open,
            "Rainbow Drop": state.rainbow_drop_obtained,
            "Zoma": state.game_complete,
        }
        return tuple(
            PanelRow(f"{name}: {detail}", checks.get(name, False))
            for name, detail in ROUTE_PLAN
        )

    def _key_item_rows(self, state: GameState) -> tuple[PanelRow, ...]:
        rows = []
        for item_id in KEY_ITEMS:
            name = ITEM_NAMES[item_id]
            unlock, detail = KEY_ITEM_UNLOCKS[item_id]
            owned = self._key_item_completed(state, item_id)
            rows.append(PanelRow(f"{name}: {unlock} · {detail}", owned))
        missing_orbs = [ITEM_NAMES[item_id] for item_id in ORB_ITEMS if not self._orb_collected(state, item_id)]
        rows.append(PanelRow("Missing orbs: " + (", ".join(missing_orbs) if missing_orbs else "none")))
        return tuple(rows)

    def _ra_priority_rows(self, state: GameState) -> tuple[PanelRow, ...]:
        unlocked = self._unlocked | (
            self._account_progress.unlocked_ids if self._account_progress is not None else frozenset()
        )
        rows = []
        for item_id, achievement_id in ITEM_ACHIEVEMENTS.items():
            achievement = ACHIEVEMENTS_BY_ID[achievement_id]
            if achievement_id in unlocked:
                rows.append(PanelRow(f"{achievement.title}: done", True))
            elif self._has_item(state, item_id):
                rows.append(PanelRow(f"{achievement.title}: item held, not observed this session", False))
            else:
                rows.append(PanelRow(f"{achievement.title}: {achievement.description}", False))
        for achievement in ACHIEVEMENTS:
            if achievement.id not in ITEM_ACHIEVEMENTS.values() and achievement.id not in unlocked:
                rows.append(PanelRow(f"{achievement.title}: {achievement.description}", False))
        return tuple(rows)

    @staticmethod
    def _has_item(state: GameState, item_id: int) -> bool:
        return item_id in state.items

    @staticmethod
    def _key_item_completed(state: GameState, item_id: int) -> bool:
        if item_id == 0x4F:
            return state.ship_granted or item_id in state.items
        if item_id == 0x76:
            return state.rainbow_bridge or state.rainbow_drop_obtained
        return item_id in state.items

    @staticmethod
    def _orb_collected(state: GameState, item_id: int) -> bool:
        return bool(state.orb_flags & (1 << (item_id - ORB_ITEMS[0])))

    @staticmethod
    def _active_count(state: GameState) -> int:
        return sum(character_id != 0xFF for character_id in state.party_ids)

    def _item_detail(self, item_id: int) -> str:
        name = self._item_label(item_id)
        achievement_id = ITEM_ACHIEVEMENTS.get(item_id)
        if achievement_id is not None:
            achievement = ACHIEVEMENTS_BY_ID[achievement_id]
            return f"{name}: {achievement.title} · {achievement.description}"
        unlock = KEY_ITEM_UNLOCKS.get(item_id)
        if unlock is not None:
            return f"{name}: {unlock[0]} · {unlock[1]}"
        return name

    def _item_label(self, item_id: int) -> str:
        if self._item_name is not None:
            name = self._item_name(item_id)
            if name:
                return name
        return ITEM_NAMES.get(item_id, "Unknown item")

    def _party_name(self, ram: bytes, index: int) -> str:
        encoded = bytes(ram[0x075C + index * 8:0x0764 + index * 8])
        if self._decode_text is not None:
            name = self._decode_text(encoded).strip()
            if name:
                return name
        return f"P{index + 1}"

    def _party_warnings(self, ram: bytes, state: GameState) -> tuple[str, ...]:
        warnings = []
        active = 0
        low_hp = 0
        bad_status = 0
        no_mp = 0
        for index, character_id in enumerate(state.party_ids):
            if character_id == 0xFF:
                continue
            active += 1
            hp = int.from_bytes(ram[0x071C + index * 2:0x071E + index * 2], "little")
            max_hp = int.from_bytes(ram[0x0724 + index * 2:0x0726 + index * 2], "little")
            mp = int.from_bytes(ram[0x072C + index * 2:0x072E + index * 2], "little")
            status = ram[0x073D + index * 2]
            if max_hp and hp * 4 <= max_hp:
                low_hp += 1
            if status & 0x60 or not status & 0x80:
                bad_status += 1
            if state.jobs[index] in {1, 2, 3} and not mp:
                no_mp += 1
        if active < 4:
            warnings.append(f"{4 - active} party slot(s) open")
        if low_hp:
            warnings.append(f"{low_hp} low HP")
        if bad_status:
            warnings.append(f"{bad_status} status/down")
        if no_mp:
            warnings.append(f"{no_mp} caster(s) dry")
        return tuple(warnings)

    def _unlock_section(self, state: GameState) -> PanelSection:
        owned = [
            ITEM_NAMES[item_id]
            for item_id in KEY_ITEMS
            if self._key_item_completed(state, item_id)
        ]
        next_missing = next(
            (
                item_id
                for item_id in KEY_ITEMS
                if not self._key_item_completed(state, item_id)
            ),
            None,
        )
        rows = [PanelRow(f"Key items {len(owned)}/{len(KEY_ITEMS)}")]
        if next_missing is not None:
            unlock, detail = KEY_ITEM_UNLOCKS[next_missing]
            rows.append(PanelRow(f"Next unlock: {ITEM_NAMES[next_missing]} · {unlock}"))
            rows.append(PanelRow(detail))
        else:
            rows.append(PanelRow("All tracked key-item unlocks are covered", True))
        return PanelSection(
            "Unlocks",
            tuple(rows),
            actions=(
                PanelAction("OPEN UNLOCK DETAILS", "Key Item Unlocks", self._key_item_rows(state)),
            ),
        )

    def _orb_section(self, state: GameState) -> PanelSection:
        rows = [PanelRow(f"Found {state.orbs_found}/6 · placed {state.orbs_placed}/6 · lit {state.pedestals}/6")]
        missing = [item_id for item_id in ORB_ITEMS if not self._orb_collected(state, item_id)]
        if missing:
            rows.append(PanelRow("Missing: " + ", ".join(ITEM_NAMES[item_id] for item_id in missing), False))
        else:
            rows.append(PanelRow("All six orbs have been collected", True))
        detail_rows = tuple(
            PanelRow(f"{ITEM_NAMES[item_id]}: {ORB_HINTS[item_id]}", self._orb_collected(state, item_id))
            for item_id in ORB_ITEMS
        )
        return PanelSection(
            "Orb route",
            tuple(rows),
            alert=state.orbs_found >= 6 and state.orbs_placed < 6,
            actions=(PanelAction("OPEN ORB CHECKLIST", "Orb Checklist", detail_rows),),
        )

    def _resource_section(self, ram: bytes, state: GameState) -> PanelSection:
        gold = int.from_bytes(ram[0x07BC:0x07BF], "little")
        alive = 0
        total_hp = 0
        total_max_hp = 0
        total_mp = 0
        total_max_mp = 0
        for index, character_id in enumerate(state.party_ids):
            if character_id == 0xFF:
                continue
            hp = int.from_bytes(ram[0x071C + index * 2:0x071E + index * 2], "little")
            max_hp = int.from_bytes(ram[0x0724 + index * 2:0x0726 + index * 2], "little")
            mp = int.from_bytes(ram[0x072C + index * 2:0x072E + index * 2], "little")
            max_mp = int.from_bytes(ram[0x0734 + index * 2:0x0736 + index * 2], "little")
            alive += bool(ram[0x073D + index * 2] & 0x80)
            total_hp += hp
            total_max_hp += max_hp
            total_mp += mp
            total_max_mp += max_mp
        hp_text = f"HP pool {total_hp}/{total_max_hp}" if total_max_hp else "HP pool unknown"
        mp_text = f"MP pool {total_mp}/{total_max_mp}" if total_max_mp else "MP pool unknown"
        next_goal = next((goal for goal, _ in SHOPPING_GOALS if gold < goal), None)
        rows = [PanelRow(f"Alive {alive}/4 · {hp_text}"), PanelRow(mp_text)]
        if next_goal is not None:
            rows.append(PanelRow(f"Gold {gold:,} · need {next_goal - gold:,} for {next_goal:,} buffer"))
        else:
            rows.append(PanelRow(f"Gold {gold:,} · late-game buffer ready", True))
        detail_rows = tuple(PanelRow(f"{goal:,} gold: {detail}", gold >= goal) for goal, detail in SHOPPING_GOALS)
        return PanelSection(
            "Resources",
            tuple(rows),
            alert=bool(self._party_warnings(ram, state)),
            actions=(PanelAction("OPEN RESOURCE PLAN", "Resource Plan", detail_rows),),
        )

    def _achievement_detail_rows(self) -> tuple[PanelRow, ...]:
        unlocked = self._unlocked | (
            self._account_progress.unlocked_ids if self._account_progress is not None else frozenset()
        )
        return tuple(
            PanelRow(f"{achievement.title}: {achievement.description}", achievement.id in unlocked)
            for achievement in ACHIEVEMENTS
        )

    def _class_plan_rows(self, state: GameState) -> tuple[PanelRow, ...]:
        active_jobs = [
            state.jobs[index]
            for index, character_id in enumerate(state.party_ids)
            if character_id != 0xFF
        ]
        rows = [PanelRow("Class mix: " + ", ".join(JOBS[job] for job in active_jobs) if active_jobs else "No active party")]
        if 3 not in active_jobs:
            rows.append(PanelRow("No Sage present · Book of Satori or Goof-off route can unlock one", False))
        if sum(job == 3 for job in active_jobs) >= 2:
            rows.append(PanelRow("Two Sage setup active for So Much Magic", True))
        eligible = [
            f"P{index + 1} {JOBS[state.jobs[index]]} Lv {level}"
            for index, level in enumerate(state.levels)
            if state.party_ids[index] != 0xFF and level >= 20 and state.jobs[index] not in {0, 3}
        ]
        rows.append(PanelRow("Dhama candidates: " + (", ".join(eligible) if eligible else "none yet")))
        return tuple(rows)

    def _recovery_rows(self, ram: bytes, state: GameState) -> tuple[PanelRow, ...]:
        warnings = self._party_warnings(ram, state)
        if not warnings:
            return (PanelRow("Recovery state: no immediate HP/status/MP warning", True),)
        return tuple(PanelRow(f"Recovery warning: {warning}", False) for warning in warnings)

    def _completion_rows(self, state: GameState, vault_count: int) -> tuple[PanelRow, ...]:
        return (
            PanelRow(f"Orbs found {state.orbs_found}/6", state.orbs_found >= 6),
            PanelRow(f"Orbs placed {state.orbs_placed}/6", state.orbs_placed >= 6),
            PanelRow(f"Liamland pedestals lit {state.pedestals}/6", state.pedestals >= 6),
            PanelRow(f"Pyramid chests {state.pyramid_chests}/24", state.pyramid_chests >= 24),
            PanelRow(f"Samanao cave chests {state.samanao_chests}/23", state.samanao_chests >= 23),
            PanelRow(f"Vault slots used {vault_count}/128"),
            PanelRow("Rainbow bridge ready" if self._has_item(state, 0x76) else "Rainbow bridge not ready", self._has_item(state, 0x76)),
            PanelRow("Sphere of Light owned" if self._has_item(state, 0x72) else "Sphere of Light missing", self._has_item(state, 0x72)),
        )

    def _chest_rows(self, state: GameState) -> tuple[PanelRow, ...]:
        pyramid_left = 24 - state.pyramid_chests
        samanao_left = 23 - state.samanao_chests
        return (
            PanelRow(f"Pyramid: {pyramid_left} chest(s) left", pyramid_left == 0),
            PanelRow(f"Samanao cave: {samanao_left} chest(s) left", samanao_left == 0),
            PanelRow("Pyramid completion detects Archaeologist when all 24 are opened"),
            PanelRow("Samanao cave completion detects Spelunker when all 23 are opened"),
        )

    def _vault_rows(self, sram: bytes) -> tuple[PanelRow, ...]:
        counts = Counter(
            value & 0x7F for value in sram[0x0D:0x8D] if value != 0xFF
        )
        if not counts:
            return (PanelRow("Vault is empty"),)
        return tuple(
            PanelRow(
                f"{self._item_label(item_id)} ×{count}",
                item_id in ITEM_ACHIEVEMENTS,
            )
            for item_id, count in sorted(counts.items())
        )

    @staticmethod
    def _return_rows(town_names: list[str]) -> tuple[PanelRow, ...]:
        if not town_names:
            return (PanelRow("No Return destinations recorded"),)
        known = set(town_names)
        return tuple(PanelRow(town, town in known) for town in TOWNS)

    def _travel_aid_rows(self, ram: bytes) -> tuple[PanelRow, ...]:
        repel_steps = ram[0x00AD]
        time = self._time_of_day(ram[0x06DF])
        rows = [
            PanelRow(f"Repel: {repel_steps} steps remaining" if repel_steps else "Repel inactive"),
            PanelRow(f"Time: {time}"),
            PanelRow("Use Return for fast town routing once destinations are registered"),
            PanelRow("Use Echoing Flute during orb cleanup if available"),
            PanelRow("Use Lamp of Darkness for night checks if available"),
        ]
        return tuple(rows)

    def _state(self, ram: bytes, sram: bytes) -> GameState:
        levels = tuple(ram[0x0700:0x0704])
        jobs = tuple(value & 0x07 for value in ram[0x0718:0x071C])
        party_ids = tuple(ram[0x07C1:0x07C5])
        carried_items = tuple(
            value & 0x7F for value in ram[0x077C:0x079C] if value != 0xFF
        )
        vault_items = tuple(
            value & 0x7F for value in sram[0x0D:0x8D] if value != 0xFF
        )
        return GameState(
            levels=levels,
            jobs=jobs,
            party_ids=party_ids,
            items=carried_items + vault_items,
            orb_flags=sram[0xCE] & 0x3F,
            pyramid_chests=self._bit_count(sram, ((0x92, 0x3F), (0x93, 0xC0), (0x9F, 0x07), (0xA0, 0xFF), (0xA1, 0xF8))),
            samanao_chests=self._bit_count(sram, ((0x9B, 0x3F), (0x9C, 0xFF), (0x9D, 0xFF), (0x9E, 0x80))),
            orbs_found=(sram[0xCE] & 0x3F).bit_count(),
            orbs_placed=(sram[0xCF] & 0x3F).bit_count(),
            pedestals=(sram[0xD0] & 0x3F).bit_count(),
            arena_active=bool(sram[0xA64]),
            arena_winner=sram[0xA65],
            arena_pick=sram[0xA67],
            chest_flags=bytes(sram[CHEST_FLAGS_START:CHEST_FLAGS_END]),
            rainbow_bridge=bool(sram[0xB6] & 0x80),
            rainbow_drop_obtained=bool(sram[0xBF] & 0x08) or 0x76 in carried_items + vault_items,
            alefgard_open=bool(sram[0xCB] & 0x10),
            baramos_defeated=bool(sram[0xCB] & 0x80),
            game_complete=bool(sram[0xB7] & 0x01),
            ship_granted=bool(sram[0xB8] & 0x80),
            ship_owned=bool(sram[0xB8] & 0x80) and not bool(sram[0xB8] & 0x40),
        )

    def _merge_save_sram(self, live_sram: bytes) -> bytes:
        if self._save_path is None:
            return live_sram
        try:
            saved_sram = self._save_path.read_bytes()
        except OSError:
            return live_sram
        if len(saved_sram) > 0x2000:
            saved_sram = saved_sram[-0x2000:]
        if len(saved_sram) < SRAM_READ_SIZE:
            return live_sram
        if not live_sram[0xC8] & 0x80 and saved_sram[0xC8] & 0x80:
            merged = bytearray(saved_sram[:len(live_sram)])
        else:
            merged = bytearray(live_sram)
        for offset in range(CHEST_FLAGS_START, CHEST_FLAGS_END):
            merged[offset] |= saved_sram[offset]
        for offset, mask in (
            (0xB6, 0x80),
            (0xB7, 0x01),
            (0xBF, 0x08),
            (0xCB, 0x90),
            (0xCE, 0x3F),
            (0xCF, 0x3F),
            (0xD0, 0x3F),
        ):
            merged[offset] |= saved_sram[offset] & mask
        ship_values = (live_sram[0xB8], saved_sram[0xB8])
        if any(value & 0xC0 == 0x80 for value in ship_values):
            merged[0xB8] = (merged[0xB8] & 0x3F) | 0x80
        elif any(value & 0x80 for value in ship_values):
            merged[0xB8] = (merged[0xB8] & 0x3F) | 0xC0
        return bytes(merged)

    def _observe(self, state: GameState) -> None:
        previous = self._previous
        if previous is None:
            self._previous = state
            return
        if self._active_count(previous) < 4 == self._active_count(state):
            self._unlocked.add(50465)
        if any(
            old_job != new_job and old_id == new_id and new_id != 0xFF
            for old_job, new_job, old_id, new_id in zip(
                previous.jobs, state.jobs, previous.party_ids, state.party_ids
            )
        ):
            self._unlocked.add(50467)
        previous_sages = sum(
            job == 3 and character_id != 0xFF
            for job, character_id in zip(previous.jobs, previous.party_ids)
        )
        current_sages = sum(
            job == 3 and character_id != 0xFF
            for job, character_id in zip(state.jobs, state.party_ids)
        )
        if previous_sages < 2 <= current_sages:
            self._unlocked.add(50434)
        if previous.pyramid_chests < 24 == state.pyramid_chests:
            self._unlocked.add(50526)
        if previous.samanao_chests < 23 == state.samanao_chests:
            self._unlocked.add(50527)
        if previous.pedestals < 6 == state.pedestals:
            self._unlocked.add(50455)
        if previous.arena_active and not state.arena_active and state.arena_winner == state.arena_pick:
            self._unlocked.add(50466)
        gained = Counter(state.items) - Counter(previous.items)
        for item_id, count in gained.items():
            self._recent_items.extend([item_id] * count)
            achievement_id = ITEM_ACHIEVEMENTS.get(item_id)
            if achievement_id is not None:
                self._unlocked.add(achievement_id)
        self._previous = state

    def _achievement_section(self) -> PanelSection:
        account_ids = (
            self._account_progress.unlocked_ids & ACHIEVEMENTS_BY_ID.keys()
            if self._account_progress is not None
            else frozenset()
        )
        combined_ids = account_ids | self._unlocked
        rows = []
        if self._account_progress is not None and not self._account_progress.message:
            rows.append(
                PanelRow(
                    f"{len(combined_ids)}/50 unlocked · {self._account_progress.username}"
                )
            )
            rows.append(PanelRow(f"{len(self._unlocked)} detected this session"))
        else:
            rows.append(PanelRow(f"{len(self._unlocked)}/50 detected this session"))
            if self._account_progress is not None and self._account_progress.message:
                rows.append(PanelRow(self._account_progress.message))
        rows.extend(
            PanelRow(
                f"{ACHIEVEMENTS_BY_ID[achievement_id].title} · "
                f"{'detected' if achievement_id in self._unlocked else 'account'}",
                True,
            )
            for achievement_id in sorted(combined_ids)
        )
        if not combined_ids:
            rows.append(PanelRow(f"{EXACT_DETECTOR_COUNT} exact detectors active · fresh baseline"))
        return PanelSection(
            "RetroAchievements",
            tuple(rows),
            preview_limit=7,
            actions=(PanelAction("OPEN ACHIEVEMENTS", "RetroAchievements", self._achievement_detail_rows()),),
        )

    def _party_section(self, ram: bytes, state: GameState) -> PanelSection:
        rows = []
        detail_rows = []
        for index, character_id in enumerate(state.party_ids):
            if character_id == 0xFF:
                continue
            level = state.levels[index]
            hp = int.from_bytes(ram[0x071C + index * 2:0x071E + index * 2], "little")
            max_hp = int.from_bytes(ram[0x0724 + index * 2:0x0726 + index * 2], "little")
            mp = int.from_bytes(ram[0x072C + index * 2:0x072E + index * 2], "little")
            max_mp = int.from_bytes(ram[0x0734 + index * 2:0x0736 + index * 2], "little")
            status = ram[0x073D + index * 2]
            condition = self._condition(status)
            name = self._party_name(ram, index)
            rows.append(
                PanelRow(
                    f"{name} · {JOBS[state.jobs[index]]} Lv {level} · "
                    f"HP {hp}/{max_hp} · MP {mp}/{max_mp}{condition}"
                )
            )
            detail_rows.append(
                PanelRow(
                    f"{name}: {JOBS[state.jobs[index]]} Lv {level} · "
                    f"HP {hp}/{max_hp} · MP {mp}/{max_mp}{condition}"
                )
            )
            if level >= 20 and state.jobs[index] not in {0, 3}:
                detail_rows.append(
                    PanelRow(f"{name}: eligible for Dhama class change", False)
                )
        if not detail_rows:
            detail_rows.append(PanelRow("Waiting for a loaded save"))
        detail_rows.extend(self._class_plan_rows(state))
        detail_rows.extend(self._recovery_rows(ram, state))
        return PanelSection(
            "Party",
            tuple(rows) or (PanelRow("Waiting for a loaded save"),),
            actions=(PanelAction("OPEN PARTY PLAN", "Party Plan", tuple(detail_rows)),),
        )

    def _battle_section(self, ram: bytes) -> PanelSection:
        rows = []
        enemy_slots = []
        groups = []
        group_details = []
        for enemy_id, count in zip(ram[0x056D:0x0571], ram[0x0571:0x0575]):
            if not count:
                continue
            name = self._enemy_label(enemy_id)
            groups.append(f"{name} ×{count}")
            profile = self._enemy_profile_for(enemy_id)
            if profile is None:
                group_details.append(f"{name} ×{count}")
            else:
                group_details.append(
                    f"{name} ×{count} · Lv {profile.level} · "
                    f"HP {profile.max_hp} · ATK {profile.attack} · "
                    f"EXP {profile.experience} · {profile.gold} G each"
                )
            enemy_slots.extend(((enemy_id, name),) * count)
        if groups:
            rows.append(
                PanelRow(
                    "Groups · " + " · ".join(groups),
                    tooltip="Encounter groups\n" + "\n".join(group_details),
                )
            )
        for index in range(8):
            hp = int.from_bytes(
                ram[0x0500 + index * 2:0x0502 + index * 2], "little"
            )
            if not hp:
                continue
            mp = ram[0x0510 + index]
            agility = ram[0x0518 + index]
            defense = int.from_bytes(
                ram[0x0520 + index * 2:0x0522 + index * 2], "little"
            )
            effects = self._battle_effects(
                ram[0x0530 + index * 2], ram[0x0531 + index * 2]
            )
            enemy_id, enemy_name = (
                enemy_slots[index] if index < len(enemy_slots) else (-1, "Monster")
            )
            profile = self._enemy_profile_for(enemy_id)
            statuses = self._battle_effect_labels(
                ram[0x0530 + index * 2], ram[0x0531 + index * 2]
            )
            details = [
                f"E{index + 1} · {enemy_name}",
                f"Current HP {hp} · MP {mp} · AGI {agility} · DEF {defense}",
                f"Status: {' / '.join(statuses) if statuses else 'Normal'}",
            ]
            if profile is not None:
                details.extend(
                    (
                        f"ROM base: Lv {profile.level} · HP {profile.max_hp} · "
                        f"MP {profile.max_mp} · ATK {profile.attack} · "
                        f"AGI {profile.agility} · DEF {profile.defense}",
                        f"Reward: {profile.experience} EXP · {profile.gold} G",
                    )
                )
            rows.append(
                PanelRow(
                    f"E{index + 1} {enemy_name} · HP {hp} · MP {mp} · AGI {agility} · "
                    f"DEF {defense}{effects}",
                    tooltip="\n".join(details),
                )
            )
        damage = ram[0x063F]
        if damage:
            attacker = ram[0x0051]
            attacker_name = f"P{attacker + 1}" if attacker < 4 else f"E{attacker - 3}"
            if attacker < 4:
                actor_detail = self._party_name(ram, attacker)
            else:
                enemy_index = attacker - 4
                actor_detail = (
                    enemy_slots[enemy_index][1]
                    if enemy_index < len(enemy_slots)
                    else "Monster"
                )
            rows.append(
                PanelRow(
                    f"Last hit · {attacker_name} · {damage} damage",
                    tooltip=(
                        f"Last recorded hit\nAttacker: {attacker_name} · "
                        f"{actor_detail}\nDamage: {damage}"
                    ),
                )
            )
        party_effects = []
        for index in range(4):
            effects = self._battle_effects(
                ram[0x073C + index * 2], ram[0x073D + index * 2]
            )
            if effects:
                party_effects.append(f"P{index + 1}{effects}")
        if party_effects:
            rows.append(
                PanelRow(
                    "Party effects · " + " · ".join(party_effects),
                    tooltip="Live party effects\n" + "\n".join(party_effects),
                )
            )
        return PanelSection(
            "Battle",
            tuple(rows) or (PanelRow("Battle starting"),),
            priority=1,
            role="urgent",
        )

    def _battle_party_section(
        self, ram: bytes, live_sram: bytes, state: GameState
    ) -> PanelSection:
        rows = []
        active_actor = ram[0x0051]
        for index, character_id in enumerate(state.party_ids):
            if character_id == 0xFF:
                continue
            name = self._party_name(ram, index)
            job = JOBS[state.jobs[index]]
            level = state.levels[index]
            hp = int.from_bytes(ram[0x071C + index * 2:0x071E + index * 2], "little")
            max_hp = int.from_bytes(ram[0x0724 + index * 2:0x0726 + index * 2], "little")
            mp = int.from_bytes(ram[0x072C + index * 2:0x072E + index * 2], "little")
            max_mp = int.from_bytes(ram[0x0734 + index * 2:0x0736 + index * 2], "little")
            combat = ram[0x073C + index * 2]
            condition = ram[0x073D + index * 2]
            statuses = list(self._battle_effect_labels(combat, condition))
            if not condition & 0x80:
                statuses.insert(0, "Dead")
            battle_agility = live_sram[0xA9F + index]
            battle_defense = int.from_bytes(
                live_sram[0xAA3 + index * 2:0xAA5 + index * 2], "little"
            )
            battle_attack = int.from_bytes(
                live_sram[0xAAB + index * 2:0xAAD + index * 2], "little"
            )
            action = self._battle_action_label(ram, index)
            active = active_actor == index
            rows.append(
                PanelRow(
                    f"{'> ' if active else ''}{name} · {job} Lv {level} · "
                    f"HP {hp}/{max_hp} · MP {mp}/{max_mp}",
                    tooltip=(
                        f"{name} · {job} Lv {level}\n"
                        f"HP {hp}/{max_hp} · MP {mp}/{max_mp}\n"
                        f"Battle ATK {battle_attack} · DEF {battle_defense} · "
                        f"AGI {battle_agility}\n"
                        f"Base STR {ram[0x0704 + index]} · AGI {ram[0x0708 + index]} · "
                        f"INT {ram[0x070C + index]} · VIT {ram[0x0714 + index]} · "
                        f"LUCK {ram[0x0710 + index]}\n"
                        f"Status: {' / '.join(statuses) if statuses else 'Normal'}\n"
                        f"Command: {action}"
                    ),
                )
            )
        return PanelSection(
            "Party",
            tuple(rows) or (PanelRow("Waiting for party data"),),
            priority=2,
            role="urgent",
        )

    def _battle_spell_section(self, ram: bytes, state: GameState) -> PanelSection:
        active_actor = ram[0x0051]
        party_indexes = [
            index
            for index, character_id in enumerate(state.party_ids)
            if character_id != 0xFF
        ]
        if active_actor in party_indexes:
            party_indexes.remove(active_actor)
            party_indexes.insert(0, active_actor)
        chosen_rows = []
        available_rows = []
        for index in party_indexes:
            name = self._party_name(ram, index)
            mp = int.from_bytes(ram[0x072C + index * 2:0x072E + index * 2], "little")
            spell_flags = ram[
                SPELL_FLAGS_ADDRESS + index * 8:SPELL_FLAGS_ADDRESS + (index + 1) * 8
            ]
            selected = selected_battle_spell(ram, index)
            spells = learned_battle_spells(spell_flags, state.jobs[index])
            if selected in spells:
                spells = (selected,) + tuple(spell for spell in spells if spell != selected)
            for spell in spells:
                chosen = selected == spell
                row = PanelRow(
                    f"{'CHOSEN · ' if chosen else ''}{name} · {spell.name} · "
                    f"{spell.mp_cost} MP",
                    tooltip=(
                        f"{name} · {JOBS[state.jobs[index]]} Lv {state.levels[index]}"
                        f"{' · Chosen this round' if chosen else ''}\n"
                        f"{spell.tooltip(mp)}"
                    ),
                )
                (chosen_rows if chosen else available_rows).append(row)
        rows = chosen_rows + available_rows
        return PanelSection(
            "Battle spells",
            tuple(rows) or (PanelRow("No battle spells learned"),),
            preview_limit=12,
            priority=3,
            role="urgent",
        )

    def _enemy_label(self, enemy_id: int) -> str:
        if self._enemy_name is None:
            return f"Enemy 0x{enemy_id:02X}"
        return self._enemy_name(enemy_id)

    def _enemy_profile_for(self, enemy_id: int) -> EnemyProfile | None:
        if enemy_id < 0 or self._enemy_profile is None:
            return None
        try:
            return self._enemy_profile(enemy_id)
        except (IndexError, ValueError):
            return None

    @staticmethod
    def _battle_action_label(ram: bytes, player_index: int) -> str:
        action = ram[0x054C + player_index] & 0x70
        selected = selected_battle_spell(ram, player_index)
        if selected is not None:
            return f"Cast {selected.name}"
        return {
            0x00: "Attack",
            0x20: "Parry",
            0x30: "Use item",
            0x60: "Equip and attack",
            0x70: "No action",
        }.get(action, "Choosing")

    @staticmethod
    def _battle_effects(combat: int, condition: int) -> str:
        effects = DragonWarrior3Adapter._battle_effect_labels(combat, condition)
        return f" · {'/'.join(effects)}" if effects else ""

    @staticmethod
    def _battle_effect_labels(combat: int, condition: int) -> tuple[str, ...]:
        effects = []
        if combat & 0x03:
            effects.append("Sleep")
        for mask, label in (
            (0x04, "Barrier"),
            (0x08, "Bikill"),
            (0x10, "Surround"),
            (0x20, "Stopspell"),
            (0x40, "BeDragon"),
        ):
            if combat & mask:
                effects.append(label)
        if condition & 0x0F:
            effects.append("Bounce")
        for mask, label in ((0x10, "Confused"), (0x20, "Poison"), (0x40, "Numb")):
            if condition & mask:
                effects.append(label)
        return tuple(effects)

    def _progress_section(self, sram: bytes, state: GameState) -> PanelSection:
        vault_count = sum(value != 0xFF for value in sram[0x0D:0x8D])
        return PanelSection(
            "Adventure progress",
            (
                PanelRow(f"Orbs found {state.orbs_found}/6 · placed {state.orbs_placed}/6 · lit {state.pedestals}/6"),
                PanelRow(f"Pyramid chests {state.pyramid_chests}/24"),
                PanelRow(f"Samanao cave chests {state.samanao_chests}/23"),
                PanelRow(f"Vault items {vault_count}/128"),
            ),
            actions=(
                PanelAction("OPEN COMPLETION PLAN", "Completion Plan", self._completion_rows(state, vault_count)),
                PanelAction("OPEN CHEST CHECKLISTS", "Chest Checklists", self._chest_rows(state)),
                PanelAction("OPEN VAULT AUDIT", "Vault Audit", self._vault_rows(sram)),
            ),
        )

    def _world_section(self, ram: bytes) -> PanelSection:
        visited = ram[0x0750] | (ram[0x0751] << 8) | ((ram[0x0752] & 0x0F) << 16)
        town_names = [name for index, name in enumerate(TOWNS) if visited & (1 << index)]
        gold = int.from_bytes(ram[0x07BC:0x07BF], "little")
        return PanelSection(
            "Travel",
            (
                PanelRow(f"Gold {gold:,} · Repel {ram[0x00AD]} steps · {self._time_of_day(ram[0x06DF])}"),
                PanelRow(f"Return destinations {len(town_names)}/20"),
                PanelRow(", ".join(town_names) if town_names else "No Return destinations recorded"),
            ),
            preview_limit=3,
            actions=(
                PanelAction("OPEN RETURN LIST", "Return Destinations", self._return_rows(town_names)),
                PanelAction("OPEN TRAVEL AIDS", "Travel Aids", self._travel_aid_rows(ram)),
                PanelAction("OPEN TIME WINDOWS", "Time Windows", tuple(PanelRow(row) for row in TIME_WINDOWS)),
            ),
        )

    @staticmethod
    def _bit_count(data: bytes, fields: tuple[tuple[int, int], ...]) -> int:
        return sum((data[offset] & mask).bit_count() for offset, mask in fields)

    @staticmethod
    def _condition(status: int) -> str:
        labels = []
        if not status & 0x80:
            labels.append("DEAD")
        if status & 0x20:
            labels.append("PSN")
        if status & 0x40:
            labels.append("NUMB")
        return f" · {'/'.join(labels)}" if labels else ""

    @staticmethod
    def _time_of_day(value: int) -> str:
        if value <= 0x1E:
            return "Sunrise"
        if value <= 0x3C:
            return "Morning"
        if value <= 0x5A:
            return "Afternoon"
        if value <= 0x78:
            return "Evening"
        if value <= 0x96:
            return "Dusk"
        if value <= 0xB4:
            return "Night"
        return "Dawn"


assert len(ACHIEVEMENTS) == 50