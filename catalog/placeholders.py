"""Placeholder images for the demo catalog.

The demo shop has no real photos, and a storefront without images looks
broken. So seed_catalog draws a picture for every product with Pillow: a
soft background in the bouquet's colour and stylised "flowers" — circles
with petals. Files go to media/products/ and the owner replaces them with
real photos in the admin.

No external fonts or files: only Pillow from the dependencies.
"""

from __future__ import annotations

import math
import random
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = (900, 1100)

# colour slug → (background, petals, centre)
PALETTES = {
    "red": ("#FBEDEF", "#C8324B", "#7A1B2C"),
    "pink": ("#FCEEF3", "#E58AAE", "#B23A5E"),
    "white": ("#F4F1EC", "#FFFFFF", "#E7D7A3"),
    "yellow": ("#FCF6E4", "#F2C94C", "#C98A1E"),
    "purple": ("#F1ECF7", "#9B7BC7", "#5B3E8A"),
    "mix": ("#F6F1EA", "#E58AAE", "#F2C94C"),
    "green": ("#EDF3EA", "#6FA36A", "#3F6E3B"),
}
DEFAULT = PALETTES["pink"]


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _flower(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float,
            petals: str, core: str, count: int = 6) -> None:
    """One flower: petals in a circle and a centre."""
    for i in range(count):
        angle = 2 * math.pi * i / count
        px = cx + math.cos(angle) * radius * 0.55
        py = cy + math.sin(angle) * radius * 0.55
        r = radius * 0.5
        draw.ellipse((px - r, py - r, px + r, py + r), fill=_hex(petals))
    r = radius * 0.32
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_hex(core))


def render(seed: str, color: str = "pink", stems: int = 9) -> bytes:
    """PNG picture of a bouquet. Same seed — same picture."""
    background, petals, core = PALETTES.get(color, DEFAULT)
    rnd = random.Random(seed)
    image = Image.new("RGB", SIZE, _hex(background))
    draw = ImageDraw.Draw(image)

    width, height = SIZE
    # stems: a bunch of lines converging at the bottom
    base_x, base_y = width / 2, height * 0.93
    for _ in range(max(stems, 5)):
        top_x = rnd.uniform(width * 0.25, width * 0.75)
        top_y = rnd.uniform(height * 0.28, height * 0.55)
        draw.line((base_x, base_y, top_x, top_y), fill=_hex("#5E8A57"), width=6)

    # flowers: larger towards the centre, smaller at the edges
    count = min(max(stems, 5), 15)
    for _ in range(count):
        cx = rnd.uniform(width * 0.2, width * 0.8)
        cy = rnd.uniform(height * 0.22, height * 0.58)
        distance = math.hypot(cx - width / 2, cy - height * 0.4) / (width / 2)
        radius = rnd.uniform(60, 95) * (1.15 - 0.4 * min(distance, 1))
        if color == "mix":
            petals = rnd.choice(["#E58AAE", "#F2C94C", "#C8324B", "#FFFFFF", "#9B7BC7"])
        _flower(draw, cx, cy, radius, petals, core, count=rnd.choice((5, 6, 8)))

    # wrapping: a light cone at the bottom
    draw.polygon(
        [(width * 0.3, height * 0.6), (width * 0.7, height * 0.6),
         (width * 0.58, height * 0.95), (width * 0.42, height * 0.95)],
        fill=_hex("#EFE3D3"),
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def write(path: Path, seed: str, color: str = "pink", stems: int = 9) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render(seed, color, stems))
    return path
