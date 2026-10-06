"""Share-card images (1200x630 PNG) for LINE / X previews: a costume bird, the page title and the site name, drawn with Pillow.

One card per page, so a link shared from any page looks like that page.  Deterministic.  When Pillow or a Japanese font is missing,
`available()` is False and the pages fall back to the one default image.
"""
from __future__ import annotations

import functools
import io
from pathlib import Path

from sites.saichin.ogimage import find_font

W, H = 1200, 630
INK, YELLOW, PINK, WHITE, DOT = (43, 27, 20), (255, 201, 60), (255, 77, 109), (255, 255, 255), (255, 222, 130)
ASSETS = Path(__file__).resolve().parent / "assets" / "img"


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return find_font() is not None and (ASSETS / "mascot-pair.webp").exists()


def _wrap(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-1] + "…"
    return lines


@functools.lru_cache(maxsize=1024)
def card(*, title: str, tag: str, bird: str, site: str) -> bytes:
    """One card: `tag` is the small sticker text, `title` the headline, `bird` the file name (without .webp) of a transparent mascot image."""
    from PIL import Image, ImageDraw, ImageFont
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    img = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(img)
    for y in range(24, H, 40):                       # the dotted background of the site
        for x in range(24 + (y // 40 % 2) * 20, W, 40):
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=DOT)
    d.rounded_rectangle([30, 30, W - 30, H - 30], radius=44, outline=INK, width=6)
    # the bird, bottom right
    b = Image.open(ASSETS / f"{bird}.webp").convert("RGBA")
    scale = min(500 / b.width, 430 / b.height)
    b = b.resize((int(b.width * scale), int(b.height * scale)), Image.LANCZOS)
    img.paste(b, (W - b.width - 70, H - b.height - 70), b)
    # sticker
    f_tag = ImageFont.truetype(path, 34)
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([86, 92, 86 + tw + 56, 92 + 62], radius=31, fill=PINK, outline=INK, width=5)
    d.text((86 + 28, 123), tag, font=f_tag, fill=WHITE, anchor="lm")
    # title, up to 3 lines, as large as fits the left column
    col_w = W - 86 - 500
    chosen = None
    for limit in (2, 3):                                  # prefer two lines at the largest size that fits
        for size in (84, 76, 68, 60, 54, 48):
            font = ImageFont.truetype(path, size)
            lines = _wrap(d, title, font, col_w, 9)
            if len(lines) <= limit:
                chosen = (font, size, lines)
                break
        if chosen:
            break
    font, size, lines = chosen or (font, size, _wrap(d, title, font, col_w, 3))
    y = 190
    for line in lines:
        d.text((86 + 4, y + 4), line, font=font, fill=WHITE)    # hard shadow, like the site's headings
        d.text((86, y), line, font=font, fill=INK)
        y += int(size * 1.25)
    f_site = ImageFont.truetype(path, 34)
    d.rounded_rectangle([86, H - 128, 86 + d.textlength(site, font=f_site) + 48, H - 66], radius=31, fill=WHITE, outline=INK, width=4)
    d.text((86 + 24, H - 97), site, font=f_site, fill=INK, anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
