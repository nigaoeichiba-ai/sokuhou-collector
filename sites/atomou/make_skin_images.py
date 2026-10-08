"""Turn the generator's originals (white background, one panoramic band per picture) into the transparent webp strips in assets/skins/.

    python sites/atomou/make_skin_images.py [--inbox out/atomou_img/inbox] [--out sites/atomou/assets/skins]

The pictures were ordered from Codex (see out/atomou_img/briefs); this script only cuts the band, makes the white outside transparent (white that is
enclosed by the artwork, e.g. a ghost, stays), softens the cut edge and saves a small webp.  No text and no people are in the pictures.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
WIDTHS = {"halloween_dots": 900}  # everything else: 960
MAX_BYTES = 58_000


def cut(src: Path, width: int) -> Image.Image:
    im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    near_white = im.min(axis=2) >= 246
    lab, n = ndimage.label(near_white)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(border))
    # the picture is one band: crop to the non-outside rows/columns
    rows = np.where(~outside.all(axis=1))[0]
    cols = np.where(~outside.all(axis=0))[0]
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, 0, im.shape[1]
    pad = 6
    y0, y1 = max(0, y0 - pad), min(im.shape[0], y1 + pad)
    im, outside = im[y0:y1, x0:x1], outside[y0:y1, x0:x1]
    edge = ndimage.binary_dilation(outside, iterations=2) & ~outside
    alpha = np.where(outside, 0.0, 1.0)
    soft = np.clip((1.0 - im.min(axis=2) / 255.0) * 1.7, 0, 1)
    alpha[edge] = soft[edge]
    a = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.where(edge[..., None], (im - 255.0 * (1 - a)) / a, im)
    rgb = np.clip(rgb, 0, 255)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    h = round(img.height * width / img.width)
    return img.resize((width, h), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(HERE.parents[1] / "out" / "atomou_img" / "inbox"))
    ap.add_argument("--out", default=str(HERE / "assets" / "skins"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for src in sorted(Path(a.inbox).glob("*.png")):
        name = src.stem.replace("_", "-")
        full = cut(src, 1100)
        done = False
        for w in (WIDTHS.get(src.stem, 960), 840, 720, 640):
            img = full.resize((w, round(full.height * w / full.width)), Image.LANCZOS)
            for q in (80, 70, 60, 50, 40):
                dest = out / f"{name}.webp"
                img.save(dest, "WEBP", quality=q, method=4)
                if dest.stat().st_size <= MAX_BYTES:
                    done = True
                    break
            if done:
                break
        total += dest.stat().st_size
        print(f"{dest.name}: {img.size[0]}x{img.size[1]} {dest.stat().st_size // 1024} KB (q{q})")
    print(f"total {total // 1024} KB")


if __name__ == "__main__":
    main()
