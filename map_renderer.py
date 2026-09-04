from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from game.rom_assets import AreaGraphics, WorldGraphics


WORLD_PATTERN_BASE = 0x8D


NES_PALETTE = (
    (84, 84, 84), (0, 30, 116), (8, 16, 144), (48, 0, 136),
    (68, 0, 100), (92, 0, 48), (84, 4, 0), (60, 24, 0),
    (32, 42, 0), (8, 58, 0), (0, 64, 0), (0, 60, 0),
    (0, 50, 60), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (152, 150, 152), (8, 76, 196), (48, 50, 236), (92, 30, 228),
    (136, 20, 176), (160, 20, 100), (152, 34, 32), (120, 60, 0),
    (84, 90, 0), (40, 114, 0), (8, 124, 0), (0, 118, 40),
    (0, 102, 120), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (236, 238, 236), (76, 154, 236), (120, 124, 236), (176, 98, 236),
    (228, 84, 236), (236, 88, 180), (236, 106, 100), (212, 136, 32),
    (160, 170, 0), (116, 196, 0), (76, 208, 32), (56, 204, 108),
    (56, 180, 204), (60, 60, 60), (0, 0, 0), (0, 0, 0),
    (236, 238, 236), (168, 204, 236), (188, 188, 236), (212, 178, 236),
    (236, 174, 236), (236, 174, 212), (236, 180, 176), (228, 196, 144),
    (204, 210, 120), (180, 222, 120), (168, 226, 144), (152, 226, 180),
    (160, 214, 228), (160, 162, 160), (0, 0, 0), (0, 0, 0),
)


def render_area_map(
    tiles: tuple[tuple[int, ...], ...],
    graphics: AreaGraphics,
    output: Path,
) -> None:
    image = Image.new("RGB", (len(tiles[0]) * 16, len(tiles) * 16))
    pixels = image.load()
    assert pixels is not None
    for map_y, row in enumerate(tiles):
        for map_x, encoded_tile in enumerate(row):
            tile = encoded_tile & 0x1F
            patterns = graphics.metatiles[tile]
            colors = (0x0F,) + graphics.palette[
                graphics.attributes[tile] * 3:graphics.attributes[tile] * 3 + 3
            ]
            for quadrant, pattern_id in enumerate(patterns):
                _draw_pattern(
                    pixels,
                    map_x * 16 + (quadrant & 1) * 8,
                    map_y * 16 + (quadrant >> 1) * 8,
                    graphics.patterns[pattern_id],
                    colors,
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def render_world_map(
    tiles: tuple[tuple[int, ...], ...],
    graphics: WorldGraphics,
    output: Path,
) -> None:
    image = Image.new("RGB", (len(tiles[0]) * 16, len(tiles) * 16))
    pixels = image.load()
    assert pixels is not None
    for map_y, row in enumerate(tiles):
        for map_x, tile in enumerate(row):
            patterns = graphics.metatiles[tile]
            colors = (0x0F,) + graphics.palette[graphics.attributes[tile] * 3:graphics.attributes[tile] * 3 + 3]
            for quadrant, pattern_id in enumerate(patterns):
                pattern = graphics.patterns[pattern_id - WORLD_PATTERN_BASE]
                origin_x = map_x * 16 + (quadrant & 1) * 8
                origin_y = map_y * 16 + (quadrant >> 1) * 8
                _draw_pattern(pixels, origin_x, origin_y, pattern, colors)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def _draw_pattern(pixels, origin_x: int, origin_y: int, pattern: bytes, colors) -> None:
    for y in range(8):
        low, high = pattern[y], pattern[y + 8]
        for x in range(8):
            shift = 7 - x
            color = ((low >> shift) & 1) | (((high >> shift) & 1) << 1)
            pixels[origin_x + x, origin_y + y] = NES_PALETTE[colors[color] & 0x3F]