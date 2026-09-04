import tempfile
from pathlib import Path

from retroarch_overlay.core.contracts import GameContext
from retroarch_overlay.core.models import RetroArchStatus
from retroarch_overlay.infrastructure.plugin_discovery import parse_plugin_manifest
from retroarch_overlay.infrastructure.plugin_loader import RepositoryAdapter


REPOSITORY = Path(__file__).parents[1]


def test_manifest() -> None:
    manifest = parse_plugin_manifest(REPOSITORY)
    assert manifest.slug == 'dragonwarrior3'


def test_factory_loads_plugin_adapter() -> None:
    repository = type(
        "Repository",
        (),
        {"repository_root": REPOSITORY, "manifest": parse_plugin_manifest(REPOSITORY)},
    )()
    adapter = RepositoryAdapter(
        repository,
        GameContext(repository_root=REPOSITORY),
    )._load_adapter()

    assert type(adapter).__name__ == "DragonWarrior3Adapter"
    assert adapter.name == "Dragon Warrior III"
    assert type(adapter).__module__.startswith("_retroarch_overlay_plugin_")


def test_repository_matches_retroarch_nes_status() -> None:
    repository = type(
        "Repository",
        (),
        {"repository_root": REPOSITORY, "manifest": parse_plugin_manifest(REPOSITORY)},
    )()
    adapter = RepositoryAdapter(repository, GameContext(repository_root=REPOSITORY))

    assert adapter.supports(
        RetroArchStatus("PLAYING", "nes", "Dragon Warrior III (USA)"),
        None,
    )


def test_factory_resolves_optional_maps_from_context_repository() -> None:
    repository = type(
        "Repository",
        (),
        {"repository_root": REPOSITORY, "manifest": parse_plugin_manifest(REPOSITORY)},
    )()
    with tempfile.TemporaryDirectory() as directory:
        context_root = Path(directory)
        resources = context_root / "resources"
        resources.mkdir()
        (resources / "world.png").write_bytes(b"local map")
        (resources / "underworld.png").write_bytes(b"local map")

        adapter = RepositoryAdapter(
            repository,
            GameContext(repository_root=context_root),
        )._load_adapter()

    document = adapter._map_document
    assert document is not None
    assert tuple(layer.key for layer in document.layers) == ("world", "underworld")
    assert document.overlay_kinds == ("collectibles", "npcs")
    assert (document.layers[0].offset_x, document.layers[0].offset_y) == (-3, -4)
    assert (document.layers[1].anchor_x, document.layers[1].anchor_y) == (24, 24)
