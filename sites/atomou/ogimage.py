"""atomou: the share picture of each public day (og/<id>.png, 1200x630), drawn with Pillow.

What a chat app or a social feed shows when somebody sends the link of a day: the day's name and date, and the field, in the colour of its genre.
(The count "あと○日" changes every day, so the picture carries the date, not the count; the visitor's own "画像で保存" button makes a picture with today's count.)
The font is looked up on the machine (BIZ UD Gothic, Noto Sans JP, Noto Sans CJK: all SIL OFL).  Without Pillow or a Japanese font `available()` is False and the pages
keep the one common picture (no broken og:image tags).  The same input gives the same bytes.
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
INK, MUTED, PAPER = (26, 26, 26), (90, 90, 85), (247, 247, 245)


def find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if p and Path(p).is_file():
            return p
    return None


def available() -> bool:
    if os.environ.get("ATOMOU_NO_OG"):
        return False
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return find_font() is not None


def _fit(draw, text: str, path: str, size: int, max_w: int, floor: int = 28):
    from PIL import ImageFont
    while size > floor:
        font = ImageFont.truetype(path, size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 4
    return ImageFont.truetype(path, floor)


def _lines(draw, text: str, font, max_w: int, rows: int) -> list[str]:
    out, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w and cur:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    if len(out) > rows:
        out = out[:rows]
        out[-1] = out[-1][:-1] + "…"
    return out


@functools.lru_cache(maxsize=1024)
def card(*, title: str, date_text: str, field: str, colour: tuple) -> bytes:
    from PIL import Image, ImageDraw
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 28, H], fill=colour)
    pad = 90
    head = "あと何日、もう何日  /  出典と確認日つきの公式の日付"
    d.text((pad, 96), head, font=_fit(d, head, path, 34, W - pad - 70), fill=MUTED, anchor="ls")
    tf = _fit(d, title[:60], path, 68, W - pad - 70, floor=44)
    rows = _lines(d, title, tf, W - pad - 70, 3)
    y = 210
    for r in rows:
        d.text((pad, y), r, font=tf, fill=INK, anchor="ls")
        y += int(tf.size * 1.3)
    d.text((pad, max(y + 90, 430)), date_text, font=_fit(d, date_text, path, 92, W - pad - 70, floor=48), fill=colour, anchor="ls")
    d.text((pad, H - 62), field, font=_fit(d, field, path, 34, W - pad - 420), fill=MUTED, anchor="ls")
    d.text((W - 70, H - 62), "atomou.com", font=_fit(d, "atomou.com", path, 32, 300), fill=MUTED, anchor="rs")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
