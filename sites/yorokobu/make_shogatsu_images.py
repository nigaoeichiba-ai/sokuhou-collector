"""The pictures of the New Year feature (assets/shogatsu/<name>.webp 1200x800, <name>-480.webp for phones and the small cards, <name>-og.webp 1200x630 for sharing), made from the 1536x1024 PNGs
the image generator wrote (sokuhou-sites/work/shogatsu_images/).  The generator's picture is saved as it was returned; only the sizes are made here, nothing is retouched.

    python -m sites.yorokobu.make_shogatsu_images [SOURCE_DIR]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets" / "shogatsu"
SRC = HERE.parents[2] / "sokuhou-sites" / "work" / "shogatsu_images"
SIZES = (("", (1200, 800), 82), ("-480", (480, 320), 72))
OG = (1200, 630)


def make(src: Path = SRC, out: Path = OUT) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for p in sorted(src.glob("*.png")):
        with Image.open(p) as im:
            im = im.convert("RGB")
            for suffix, size, q in SIZES:
                im.resize(size, Image.LANCZOS).save(out / f"{p.stem}{suffix}.webp", "WEBP", quality=q, method=6)
            w, h = im.size                                                   # the share card: the middle band of the picture, cropped to 1.91:1, then scaled
            ch = round(w * OG[1] / OG[0])
            top = (h - ch) // 2
            im.crop((0, top, w, top + ch)).resize(OG, Image.LANCZOS).save(out / f"{p.stem}-og.webp", "WEBP", quality=82, method=6)
        done.append(p.stem)
    return done


if __name__ == "__main__":
    print(make(Path(sys.argv[1]) if len(sys.argv) > 1 else SRC))
