"""Share-card images (1200x630 PNG) for social previews, drawn with Pillow.

The font is looked up on the machine (BIZ UD Gothic, Noto Sans JP: both SIL OFL). When Pillow or a Japanese
font is missing, `available()` is False and the site is built without images (no broken og:image tags).
"""
from __future__ import annotations

import functools
import io
import os
from pathlib import Path

W, H = 1200, 630
FONT_CANDIDATES = [
    os.environ.get("SOKUHOU_FONT", ""),
    "C:/Windows/Fonts/BIZ-UDGothicB.ttc",
    "C:/Windows/Fonts/NotoSansJP-VF.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]
GREEN_DARK, GREEN, WHITE, SOFT = (10, 76, 61), (14, 107, 86), (255, 255, 255), (214, 238, 229)


def find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if p and Path(p).is_file():
            return p
    return None


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return find_font() is not None


def _fit(draw, text: str, path: str, size: int, max_w: int, floor: int = 24):
    from PIL import ImageFont
    while size > floor:
        font = ImageFont.truetype(path, size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 4
    return ImageFont.truetype(path, floor)


@functools.lru_cache(maxsize=512)
def card(*, title: str, big: str, sub: str, foot: str) -> bytes:
    """Draw one card. Deterministic: the same input always gives the same bytes."""
    from PIL import Image, ImageDraw
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    img = Image.new("RGB", (W, H), GREEN)
    draw = ImageDraw.Draw(img)
    for y in range(H):  # vertical gradient
        t = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=tuple(round(GREEN[i] + (GREEN_DARK[i] - GREEN[i]) * t) for i in range(3)))
    pad = 72
    draw.rounded_rectangle([pad, 64, pad + 56, 120], radius=14, fill=WHITE)
    draw.text((pad + 28, 92), "¥", font=_fit(draw, "¥", path, 40, 40), fill=GREEN, anchor="mm")
    draw.text((pad + 76, 92), "最低賃金速報", font=_fit(draw, "最低賃金速報", path, 34, 400), fill=WHITE, anchor="lm")
    draw.text((pad, 210), title, font=_fit(draw, title, path, 64, W - 2 * pad), fill=SOFT, anchor="ls")
    draw.text((pad, 398), big, font=_fit(draw, big, path, 190, W - 2 * pad, floor=80), fill=WHITE, anchor="ls")
    draw.text((pad, 474), sub, font=_fit(draw, sub, path, 44, W - 2 * pad), fill=WHITE, anchor="ls")
    draw.line([(pad, H - 110), (W - pad, H - 110)], fill=(255, 255, 255, 90), width=2)
    draw.text((pad, H - 62), foot, font=_fit(draw, foot, path, 32, W - 2 * pad), fill=SOFT, anchor="ls")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
