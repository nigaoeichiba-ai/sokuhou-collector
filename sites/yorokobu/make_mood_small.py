"""The mood pictures (assets/mood/<kind>-<n>.webp, 960x640) are shown at 190-360 px: a 480-px copy (<name>-480.webp, about a third of the size) goes to the phones and the small tiles,
the 960-px original to the large and sharp screens (srcset).  Run once after a new mood picture is added:

    python -m sites.yorokobu.make_mood_small
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

MOOD = Path(__file__).resolve().parent / "assets" / "mood"
WIDTH = 480
QUALITY = 70


def small_name(p: Path) -> Path:
    return p.with_name(p.stem + f"-{WIDTH}.webp")


def make() -> list[str]:
    done = []
    for p in sorted(MOOD.glob("*.webp")):
        if p.stem.endswith(f"-{WIDTH}"):
            continue
        out = small_name(p)
        if out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
            continue
        with Image.open(p) as im:
            im = im.convert("RGB")
            h = round(im.height * WIDTH / im.width)
            im.resize((WIDTH, h), Image.LANCZOS).save(out, "WEBP", quality=QUALITY, method=6)
        done.append(f"{out.name} {out.stat().st_size // 1024} KB (from {p.stat().st_size // 1024} KB)")
    return done


if __name__ == "__main__":
    for line in make():
        print(line)
