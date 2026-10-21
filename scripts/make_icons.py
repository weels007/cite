"""Draw the Cite mark and write out every icon the site needs.

One geometry, four files: the vector favicon, the small PNGs for the tab
strip, the apple touch icon for the home screen, and the 512 icon for the
web manifest.

    python scripts/make_icons.py

The mark is the dial of the logo: an isobar arc, a needle at a reading, and
the pivot. Everything is drawn from the numbers below, so the vector and the
bitmaps cannot drift apart.
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"

# The palette, the same one the pages use.
INK = "#0E131C"
BORDER = "#232C39"
COLD = "#7D93A8"
SODIUM = "#E0A458"

# The dial, in the 32 unit grid the vector uses.
CENTRE = (16.0, 17.0)
RADIUS = 9.0
ARC_START = 160.0
ARC_END = 380.0
NEEDLE_LENGTH = 6.4
NEEDLE_ANGLE = -45.0
ARC_WIDTH = 2.1
NEEDLE_WIDTH = 2.4
PIVOT_RADIUS = 2.1


def _point(angle: float, radius: float) -> tuple[float, float]:
    """A point on the dial, in screen coordinates."""
    radians = math.radians(angle)
    return (
        CENTRE[0] + radius * math.cos(radians),
        CENTRE[1] + radius * math.sin(radians),
    )


def _arc_path() -> str:
    start = _point(ARC_START, RADIUS)
    end = _point(ARC_END % 360, RADIUS)
    large = 1 if (ARC_END - ARC_START) % 360 > 180 else 0
    return (
        f"M {start[0]:.2f} {start[1]:.2f} "
        f"A {RADIUS} {RADIUS} 0 {large} 1 {end[0]:.2f} {end[1]:.2f}"
    )


def _needle_path() -> str:
    tip = _point(NEEDLE_ANGLE, NEEDLE_LENGTH)
    return f"M {CENTRE[0]:.2f} {CENTRE[1]:.2f} L {tip[0]:.2f} {tip[1]:.2f}"


def svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" role="img" aria-label="Cite">
  <rect width="32" height="32" rx="8" fill="{INK}"/>
  <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" fill="none" stroke="{BORDER}"/>
  <path d="{_arc_path()}" fill="none" stroke="{COLD}" stroke-width="{ARC_WIDTH}" stroke-linecap="round"/>
  <path d="{_needle_path()}" fill="none" stroke="{SODIUM}" stroke-width="{NEEDLE_WIDTH}" stroke-linecap="round"/>
  <circle cx="{CENTRE[0]}" cy="{CENTRE[1]}" r="{PIVOT_RADIUS}" fill="{SODIUM}"/>
</svg>
"""


def png(size: int, rounded: bool = True) -> Image.Image:
    """The same mark, rasterised at the given size.

    The mark is drawn eight times larger and then reduced, because a one
    pixel arc drawn at sixteen pixels is a smudge, and the same arc drawn
    large and reduced is a line.
    """
    scale = size / 32.0
    supersample = 8
    big = size * supersample
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if rounded:
        draw.rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=int(8 * scale * supersample), fill=INK
        )
        border = max(1, int(scale * supersample))
        draw.rounded_rectangle(
            (
                0.5 * scale * supersample,
                0.5 * scale * supersample,
                big - 0.5 * scale * supersample,
                big - 0.5 * scale * supersample,
            ),
            radius=int(7.5 * scale * supersample),
            outline=BORDER,
            width=border,
        )
    else:
        draw.rectangle((0, 0, big, big), fill=INK)

    def scaled(point: tuple[float, float]) -> tuple[float, float]:
        return (
            point[0] * scale * supersample,
            point[1] * scale * supersample,
        )

    # The isobar, the long way round, over the top.
    draw.arc(
        (
            scaled((CENTRE[0] - RADIUS, CENTRE[1] - RADIUS)),
            scaled((CENTRE[0] + RADIUS, CENTRE[1] + RADIUS)),
        ),
        start=ARC_START,
        end=ARC_END % 360,
        fill=COLD,
        width=max(1, round(ARC_WIDTH * scale * supersample)),
    )

    needle_tip = scaled(_point(NEEDLE_ANGLE, NEEDLE_LENGTH))
    draw.line(
        (scaled(CENTRE), needle_tip),
        fill=SODIUM,
        width=max(1, round(NEEDLE_WIDTH * scale * supersample)),
    )
    pivot = scaled(CENTRE)
    radius = PIVOT_RADIUS * scale * supersample
    draw.ellipse(
        (pivot[0] - radius, pivot[1] - radius, pivot[0] + radius, pivot[1] + radius),
        fill=SODIUM,
    )

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)

    (PUBLIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    print(f"wrote {PUBLIC / 'favicon.svg'}")

    for size in (16, 32, 48):
        image = png(size)
        path = PUBLIC / f"favicon-{size}.png"
        image.save(path)
        print(f"wrote {path}")

    # The home screen rounds the icon itself, so it is drawn square.
    apple = png(180, rounded=False)
    apple.save(PUBLIC / "apple-touch-icon.png")
    print(f"wrote {PUBLIC / 'apple-touch-icon.png'}")

    square = png(512, rounded=False)
    square.save(PUBLIC / "icon-512.png")
    print(f"wrote {PUBLIC / 'icon-512.png'}")

    manifest = {
        "name": "Cite - prediction markets settled by evidence",
        "short_name": "Cite",
        "description": (
            "Weather prediction markets on GenLayer. Every settlement cites the "
            "web, and the contract verifies that the quote is really there."
        ),
        "icons": [
            {
                "src": "/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            }
        ],
        "theme_color": "#0A0C11",
        "background_color": "#0A0C11",
        "display": "standalone",
        "start_url": "/",
    }
    (PUBLIC / "site.webmanifest").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {PUBLIC / 'site.webmanifest'}")


if __name__ == "__main__":
    main()
