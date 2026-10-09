"""Share-card images (1200x630 PNG) for LINE / X previews: the page title and the site name on a plain card, drawn with Pillow.

One card per page, so a link shared from any page looks like that page.  Deterministic.  When Pillow or a Japanese font is missing,
`available()` is False and the pages fall back to the one default image.
"""
from __future__ import annotations

import functools
import io
from pathlib import Path

from sites.saichin.ogimage import find_font

W, H = 1200, 630
INK, PINK, WHITE, CREAM, LINE = (43, 27, 20), (232, 80, 111), (255, 255, 255), (255, 246, 223), (216, 198, 163)
ASSETS = Path(__file__).resolve().parent / "assets" / "img"


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return find_font() is not None


def _wrap(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w and cur:
            k = cur.rfind("、")                      # break after a comma when it is far enough along: 「…選びを、/もっと楽に」, not 「…もっ/と楽に」
            if k >= 0 and draw.textlength(cur[:k + 1], font=font) > max_w * 0.45:
                lines.append(cur[:k + 1])
                cur = cur[k + 1:] + ch
            else:
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
def card(*, title: str, tag: str, site: str) -> bytes:
    """One card: `tag` is the small label, `title` the headline."""
    from PIL import Image, ImageDraw, ImageFont
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([30, 30, W - 30, H - 30], radius=36, outline=LINE, width=3, fill=WHITE)
    d.rounded_rectangle([30, 30, 52, H - 30], radius=11, fill=PINK)              # a pink edge on the left, the site's accent
    # sticker
    f_tag = ImageFont.truetype(path, 34)
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([86, 92, 86 + tw + 56, 92 + 62], radius=31, fill=PINK)
    d.text((86 + 28, 123), tag, font=f_tag, fill=WHITE, anchor="lm")
    # title, up to 3 lines, as large as fits the left column
    col_w = W - 86 - 110
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
        d.text((86, y), line, font=font, fill=INK)
        y += int(size * 1.25)
    f_site = ImageFont.truetype(path, 34)
    d.rounded_rectangle([86, H - 128, 86 + d.textlength(site, font=f_site) + 48, H - 66], radius=31, fill=CREAM, outline=LINE, width=2)
    d.text((86 + 24, H - 97), site, font=f_site, fill=INK, anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
