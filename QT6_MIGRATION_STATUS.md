# Dragon Warrior III Qt Migration Status

Status: Complete under the revised correctness-only migration gate

Started: 2026-09-13

## Architecture

Dragon Warrior III remains toolkit-neutral. Production code emits immutable host
presentation and map models and imports neither PySide6 nor Tkinter. Qt widgets,
role filtering, keyed reconciliation, map rendering, and window lifecycle remain
owned by the base application.

## Completed

- Every emitted section and action has a stable key, enforced by a source-level
  regression guard.
- Non-battle sections declare semantic `area`, `party`, or `goals` roles; battle
  enemy, party, and spell sections retain deterministic priorities and the
  `urgent` role.
- Adapter activation and deactivation clear observation, achievement, recent-item,
  and shop-trust state so persisted adapter instances cannot leak between content
  sessions.
- A real overworld snapshot renders through `PanelDocumentView`; party filtering,
  expanded Party Plan state, and section widget identity survive live value
  updates.
- A representative battle snapshot materializes only the keyed urgent enemy,
  party, and learned-spell sections through the shared Qt host.
- A real indoor adapter snapshot selects its local map in `QtMapView` and renders
  the calibrated player position, live NPC metadata, and collectible overlay.
- Party summaries expose Dhama class-change readiness while preserving the empty
  party's waiting state and remaining visible when completed rows are hidden.
- The post-Baramos route now requires the exact Sphere of Light event/item state
  before directing the player to the Great Pit of Giaga.
- Existing party, inventory, equipment, vault, shop-upgrade, route, key-item,
  orb, achievement, travel, battle, retained-spell, and chosen-command behavior
  remains covered by plugin tests.
- ROM-decoded world, underworld, town, and dungeon layers remain lazy; world
  wrapping, local-map selection, waypoints, encounter regions, all chest records,
  scripted items, the mobile Phantom Ship, and live local NPCs continue through
  the generic map contracts.
- Generated PNGs use same-directory atomic replacement. Interrupted writes leave
  no apparently valid cache file, existing images are reused, and stale extractor
  versions are removed without touching the current version.
- The complete plugin suite passes with 86 tests and no warnings.

## Non-Goals

The plugin remains toolkit-neutral and has no plugin-specific renderer fork.

Installer, accessibility, native-platform, and performance acceptance are not
phase gates under decisions D-010 through D-014 in the governing migration plan.
No copyrighted ROM data is distributed; map tests use synthetic fixtures, while
runtime extraction requires the user's supported ROM.