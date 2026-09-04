# Dragon Warrior III Overlay Plugin

Standalone Dragon Warrior III integration for RetroArch Overlay. The plugin reads NES RAM and SRAM to present party state, route objectives, key-item and orb progress, battle details, travel status, and RetroAchievements progress.

## Development

Game behavior lives in `game/adapter.py`; achievement definitions and RA identity live beside it. The optional `decomp_reference/DragonWarrior3` submodule is pinned research material and is not required at runtime.

When a supported ROM is configured in the plugin manager, the plugin extracts the overworld, Alefgard, town, and dungeon map structures locally. Maps are decoded only when opened and cached under the framework's local plugin-state directory, keyed by ROM hash and extractor version. ROM bytes and generated images are never written into this repository.

Optional map images may be placed in `resources/world.png` and `resources/underworld.png`. Their contents are ignored by Git and are used only as a compatibility fallback when ROM extraction is unavailable. They are not selected when a supported ROM and writable plugin-state directory are configured.

The overworld, Alefgard, towns, and dungeons render from the ROM's native NES patterns, synthesized metatiles, attributes, and palettes. Generated images are cached by extractor version, so renderer updates automatically replace older diagnostic maps.

The map toolbar exposes independent checkboxes for the player, Hero's path, entrances, collectibles, NPCs, and enemy regions. Entrance and enemy names come from the ROM; treasure markers combine all 193 chest records with scripted search items and use SRAM flags to mark collected items. The Phantom Ship marker follows its live world coordinates. Local NPC markers use the active map's live NPC positions.

## Battle dashboard

During battle, route and collection sections are replaced by focused enemy, party, and spell sections. Hover an enemy or party row for live combat stats and statuses. When a supported ROM is configured, enemy hover details also include base stats and rewards decoded from its enemy records.

The spell section follows each character's learned-spell bits, including magic retained after a class change. Hover a spell for its base MP cost, target scope, and effect or damage range. A spell is marked `CHOSEN` after the game commits that character's command for the round.

Run the plugin tests from this repository with the framework source available on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "..\..\src;."
..\..\.venv\Scripts\python.exe -m pytest -q tests
```
