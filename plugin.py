from pathlib import Path

from retroarch_overlay.core.contracts import GameContext
from retroarch_overlay.models import MapDocument, MapLayer

from .game.adapter import DragonWarrior3Adapter
from .game.manifest import RA_GAME_ID
from .game.rom_assets import DragonWarrior3RomAssets
from .map_renderer import render_area_map, render_world_map


class DragonWarrior3Plugin:
    def create(self, context: GameContext) -> DragonWarrior3Adapter:
        progress = (
            context.ra_progress_provider(RA_GAME_ID)
            if context.ra_progress_provider is not None
            else None
        )
        assets = self._rom_assets(context)
        save_path = context.settings.get("save_path")
        return DragonWarrior3Adapter(
            progress,
            self._map_document(context, assets),
            save_path if isinstance(save_path, Path) else None,
            assets.enemy_name if assets is not None else None,
            assets.collectible_overlays if assets is not None else None,
            assets.npc_metadata if assets is not None else None,
            assets.item_name if assets is not None else None,
            assets.decode_text if assets is not None else None,
            assets.enemy_profile if assets is not None else None,
        )

    @staticmethod
    def _rom_assets(context: GameContext) -> DragonWarrior3RomAssets | None:
        rom_path = context.settings.get("rom_path")
        if not isinstance(rom_path, Path) or context.state_directory is None:
            return None
        try:
            return DragonWarrior3RomAssets(
                rom_path,
                context.state_directory,
                render_area_map,
                render_world_map,
            )
        except (OSError, ValueError):
            return None

    @staticmethod
    def _map_document(
        context: GameContext, assets: DragonWarrior3RomAssets | None = None
    ) -> MapDocument | None:
        if context.repository_root is None:
            return None
        resources = context.repository_root / "resources"
        world = resources / "world.png"
        underworld = resources / "underworld.png"
        credit = "Map by Rick N. Bruns · VGMaps · v1.5 (2012)"
        layers = []
        if assets is not None:
            layers.extend(assets.world_layers())
            layers.extend(assets.map_layers())
        if not layers:
            if world.is_file():
                layers.append(
                    MapLayer(
                        "world",
                        "Main World",
                        "World",
                        world,
                        "https://www.vgmaps.com/Atlas/NES/DragonWarriorIII-MainWorld.png",
                        credit,
                        offset_x=-3,
                        offset_y=-4,
                        anchor_x=8,
                        anchor_y=8,
                    )
                )
            if underworld.is_file():
                layers.append(
                    MapLayer(
                        "underworld",
                        "Alefgard",
                        "Underworld",
                        underworld,
                        "https://www.vgmaps.com/Atlas/NES/DragonWarriorIII-WorldOfDarkness-Alefgard.png",
                        credit,
                        anchor_x=24,
                        anchor_y=24,
                    )
                )
        if not layers:
            return None
        return MapDocument(
            "Dragon Warrior III",
            tuple(layers),
            ("collectibles", "npcs"),
        )


PLUGIN = DragonWarrior3Plugin()
