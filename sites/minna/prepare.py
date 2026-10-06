"""One-off: copy the illustration sources from the gift site into sites/minna/assets/src/ so the two sites stay independent.

    python -m sites.minna.prepare
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sites.minna.catalog import build_catalog  # noqa: E402
from sites.yorokobu import content as ct  # noqa: E402

SRC = ROOT / "sites" / "yorokobu" / "assets" / "img"
HERE = ROOT / "sites" / "minna"
DST = HERE / "src"


def main() -> None:
    c = ct.load()
    cat = build_catalog({o["slug"]: o["name"] for o in c["occasions"]}, {r["slug"]: r["name"] for r in c["recipients"]})
    n = 0
    for item in cat:
        s = SRC / f"{item['src']}.webp"
        d = DST / f"{item['src']}.webp"
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
        n += 1
    print(f"copied {n} files into {DST}")
    chrome()


def chrome() -> None:
    """Logo, favicons, the top-page image and the default share image (written once; delete a file to draw it again)."""
    from PIL import Image
    assets = HERE / "assets"
    (assets / "img").mkdir(parents=True, exist_ok=True)
    pair = Image.open(SRC / "mascot-pair.webp")
    pair.save(assets / "img" / "mascot-pair.webp", "WEBP", quality=92, method=6)
    head = Image.open(SRC / "r-joy.webp").convert("RGBA")
    head = head.crop((0, 0, head.width, int(head.height * 0.8)))
    side = max(head.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(head, ((side - head.width) // 2, (side - head.height) // 2))
    sq.resize((144, 144), Image.LANCZOS).save(assets / "img" / "logo-mark.webp", "WEBP", quality=92, method=6)
    bg = Image.new("RGBA", (512, 512), (47, 208, 155, 255))
    bg.alpha_composite(sq.resize((430, 430), Image.LANCZOS), (41, 50))
    bg = bg.convert("RGB")
    bg.save(assets / "icon-512.png")
    bg.resize((192, 192), Image.LANCZOS).save(assets / "icon-192.png")
    bg.resize((180, 180), Image.LANCZOS).save(assets / "apple-touch-icon.png")
    bg.resize((32, 32), Image.LANCZOS).save(assets / "favicon-32.png")
    bg.resize((48, 48), Image.LANCZOS).save(assets / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    og = Image.new("RGB", (1200, 630), (47, 208, 155))
    p2 = pair.convert("RGBA")
    p2 = p2.resize((900, int(p2.height * 900 / p2.width)), Image.LANCZOS)
    og.paste(p2, (150, 330), p2)
    og.save(assets / "img" / "og.webp", "WEBP", quality=90)
    css = assets / "style.css"
    if not css.exists():
        shutil.copyfile(ROOT / "sites" / "yorokobu" / "assets" / "style.css", css)
    print("chrome images written")


if __name__ == "__main__":
    main()
