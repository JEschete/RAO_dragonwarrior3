from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from game.adapter import DragonWarrior3Adapter
from retroarch_overlay.models import MapDocument, MapLayer, MapOverlay, MapWaypoint
from retroarch_overlay.presentation.qt import (
    PanelDocumentUpdate,
    PanelDocumentView,
    QtMapView,
)

from test_adapter import FakeMemory


def test_overworld_snapshot_preserves_qt_party_state_across_value_updates(
    qtbot,
) -> None:
    adapter = DragonWarrior3Adapter()
    memory = FakeMemory()
    first = adapter.snapshot(memory)
    view = PanelDocumentView()
    view.resize(440, 760)
    qtbot.addWidget(view)
    view.show()

    view.set_snapshot(first, content_scope="dw3-test-rom")
    view.set_active_role("party")

    assert {section.section.key for section in view.state.section_views} == {
        "party",
        "resources",
    }
    party = next(
        section for section in view.state.section_views if section.section.key == "party"
    )
    party_widget = view.section_widget(party.identity)
    assert party_widget is not None
    action_widget = party_widget.action_widget(party.actions[0].identity)
    assert action_widget is not None
    action_widget.toggle_button.click()

    memory.ram[0x0700] = 21
    update = view.set_snapshot(
        adapter.snapshot(memory),
        content_scope="dw3-test-rom",
    )
    updated_party = next(
        section for section in view.state.section_views if section.section.key == "party"
    )

    assert update == PanelDocumentUpdate.VALUES
    assert view.section_widget(updated_party.identity) is party_widget
    assert updated_party.actions[0].expanded
    assert "Hero Lv 21" in updated_party.rows[0].text


def test_battle_snapshot_renders_only_keyed_urgent_sections(qtbot) -> None:
    memory = FakeMemory()
    memory.ram[0x0032] = 0xFD
    memory.ram[0x056D] = 0x44
    memory.ram[0x0571] = 1
    memory.ram[0x0500:0x0502] = (20).to_bytes(2, "little")
    snapshot = DragonWarrior3Adapter().snapshot(memory)
    view = PanelDocumentView()
    qtbot.addWidget(view)
    view.show()

    view.set_snapshot(snapshot, content_scope="dw3-battle")

    assert [section.section.key for section in view.state.section_views] == [
        "battle",
        "battle-party",
        "battle-spells",
    ]
    assert all(section.section.role == "urgent" for section in view.state.section_views)
    assert all(
        view.section_widget(section.identity) is not None
        for section in view.state.section_views
    )


def test_indoor_snapshot_renders_player_npc_and_collectible_in_qt_map(
    qtbot,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "reeve.png"
    Image.new("RGB", (64, 64), (32, 88, 48)).save(image_path)
    document = MapDocument(
        "Dragon Warrior III",
        (
            MapLayer(
                "area-09",
                "Reeve",
                "Dungeon / town",
                image_path,
                map_id=0x09,
                wrap_width=4,
                wrap_height=4,
            ),
        ),
        ("objective", "collectibles", "npcs"),
    )
    collectible = MapWaypoint(
        2,
        3,
        "Reeve treasure",
        "Available: Antidote Herb",
        "collectibles",
    )
    npc = SimpleNamespace(
        title="Reeve elder",
        detail="Magic Ball · Available",
        completed=False,
        marker="item",
    )
    adapter = DragonWarrior3Adapter(
        map_document=document,
        collectible_overlays=lambda *_args: (
            MapOverlay("area-09", (collectible,)),
        ),
        npc_metadata=lambda *_args: (npc,),
    )
    memory = FakeMemory()
    memory.ram[0x002F] = 1
    memory.ram[0x008B] = 0x09
    memory.ram[0x0030:0x0032] = bytes((1, 2))
    memory.ram[0x0110:0x0112] = bytes((3, 1))
    memory.ram[0x0114] = 0xFF

    snapshot = adapter.snapshot(memory)
    assert snapshot.location == "Reeve · (1,2)"
    view = QtMapView(snapshot.map_document)
    qtbot.addWidget(view)
    view.show()
    view.update_map(snapshot.map_position, snapshot.map_overlays)
    view.set_overlay_visible("collectibles", True)
    view.set_overlay_visible("npcs", True)

    assert view.layer_key == "area-09"
    assert view.image_item_count == 1
    assert view.player_scene_positions == ((16.0, 32.0),)
    visible = {waypoint.title: waypoint for waypoint in view.visible_waypoints()}
    assert visible["Reeve treasure"].kind == "collectibles"
    assert visible["Reeve elder"].kind == "npcs"
    assert "Live position in Reeve" in visible["Reeve elder"].detail