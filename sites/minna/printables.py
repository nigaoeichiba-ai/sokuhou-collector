"""Printable calendars (A4 PDF) drawn with Pillow: an illustration on top, the month below, Japanese holidays in red.

Holidays are computed (no table to keep up to date): fixed dates, "n-th Monday" holidays, the two equinoxes (the standard formula, right for 1980-2099),
the sandwiched "national holiday" and the substitute holiday when a holiday falls on a Sunday.  Valid from 2022 on (the rules of the sports day and the
mountain day changed around 2020).
"""
from __future__ import annotations

import calendar
import functools
import io
import os
from datetime import date, timedelta
from pathlib import Path

FONT_CANDIDATES = [
    os.environ.get("SOKUHOU_FONT", ""),
    "C:/Windows/Fonts/BIZ-UDGothicB.ttc",
    "C:/Windows/Fonts/NotoSansJP-VF.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]
PAGE_W, PAGE_H, DPI = 1654, 2339, 200            # A4 portrait
RED, BLUE, INK, LINE = (214, 58, 74), (42, 111, 214), (43, 27, 20), (214, 200, 176)
WEEKDAYS = "日月火水木金土"


def find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if p and Path(p).is_file():
            return p
    return None


def nth_monday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    first = d + timedelta(days=(7 - d.weekday()) % 7)      # weekday(): Monday = 0
    return first + timedelta(weeks=n - 1)


def equinox(year: int, spring: bool) -> int:
    base = 20.8431 if spring else 23.2488
    return int(base + 0.242194 * (year - 1980) - ((year - 1980) // 4))


def holidays(year: int) -> dict[date, str]:
    h: dict[date, str] = {}
    fixed = [(1, 1, "元日"), (2, 11, "建国記念の日"), (2, 23, "天皇誕生日"), (4, 29, "昭和の日"), (5, 3, "憲法記念日"), (5, 4, "みどりの日"), (5, 5, "こどもの日"),
             (8, 11, "山の日"), (11, 3, "文化の日"), (11, 23, "勤労感謝の日")]
    for m, d, name in fixed:
        h[date(year, m, d)] = name
    h[nth_monday(year, 1, 2)] = "成人の日"
    h[nth_monday(year, 7, 3)] = "海の日"
    h[nth_monday(year, 9, 3)] = "敬老の日"
    h[nth_monday(year, 10, 2)] = "スポーツの日"
    h[date(year, 3, equinox(year, True))] = "春分の日"
    h[date(year, 9, equinox(year, False))] = "秋分の日"
    # a day sandwiched between two holidays is a holiday too (never a Sunday)
    d = date(year, 1, 2)
    while d < date(year, 12, 31):
        if d not in h and d.weekday() != 6 and (d - timedelta(days=1)) in h and (d + timedelta(days=1)) in h:
            h[d] = "国民の休日"
        d += timedelta(days=1)
    # a holiday on Sunday moves to the next day that is not a holiday
    for day in sorted(list(h)):
        if day.weekday() == 6 and h[day] != "振替休日":
            n = day + timedelta(days=1)
            while n in h:
                n += timedelta(days=1)
            h[n] = "振替休日"
    return dict(sorted(h.items()))


@functools.lru_cache(maxsize=32)
def _font(path: str, size: int):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def month_page(illustration: Path, year: int, month: int, font_path: str):
    """One A4 page as a Pillow RGB image."""
    from PIL import Image, ImageDraw
    hol = holidays(year)
    page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 253, 247))
    d = ImageDraw.Draw(page)
    # heading
    d.text((110, 70), f"{month}月", font=_font(font_path, 230), fill=INK)
    d.text((PAGE_W - 110, 150), f"{year}年", font=_font(font_path, 84), fill=INK, anchor="ra")
    d.text((PAGE_W - 110, 255), f"令和{year - 2018}年", font=_font(font_path, 50), fill=(111, 90, 78), anchor="ra")
    # illustration
    im = Image.open(illustration).convert("RGBA")
    box_w, box_h = 1100, 760
    sc = min(box_w / im.width, box_h / im.height)
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    page.paste(im, ((PAGE_W - im.width) // 2, 360 + (box_h - im.height) // 2), im)
    # grid
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
    left, top, width = 100, 1230, PAGE_W - 200
    cw = width / 7
    head_h = 96
    row_h = min(170, (PAGE_H - top - head_h - 150) // len(weeks))
    for i, ch in enumerate(WEEKDAYS):
        x = left + cw * i
        col = RED if i == 0 else BLUE if i == 6 else INK
        d.rounded_rectangle([x + 4, top, x + cw - 4, top + head_h - 8], radius=16, fill=(255, 240, 184) if i not in (0, 6) else ((255, 224, 232) if i == 0 else (217, 241, 255)))
        d.text((x + cw / 2, top + head_h / 2 - 4), ch, font=_font(font_path, 54), fill=col, anchor="mm")
    y0 = top + head_h
    for r, week in enumerate(weeks):
        for i, day in enumerate(week):
            x, y = left + cw * i, y0 + row_h * r
            d.rectangle([x, y, x + cw, y + row_h], outline=LINE, width=2)
            if not day:
                continue
            dt = date(year, month, day)
            col = RED if (i == 0 or dt in hol) else BLUE if i == 6 else INK
            d.text((x + 16, y + 8), str(day), font=_font(font_path, 66), fill=col)
            if dt in hol:
                name = hol[dt]
                size = 30 if len(name) <= 5 else 25
                d.text((x + 16, y + 86), name, font=_font(font_path, size), fill=RED)
    d.text((PAGE_W // 2, PAGE_H - 70), "minna-no-illust.com  無料・商用OK", font=_font(font_path, 32), fill=(111, 90, 78), anchor="mm")
    return page


def month_pdf(illustration: Path, year: int, month: int, font_path: str) -> bytes:
    buf = io.BytesIO()
    month_page(illustration, year, month, font_path).save(buf, format="PDF", resolution=DPI, quality=90)
    return buf.getvalue()


def year_pdf(illustrations: list[Path], year: int, font_path: str) -> bytes:
    pages = [month_page(ill, year, m, font_path) for m, ill in enumerate(illustrations, 1)]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", resolution=DPI, quality=88, save_all=True, append_images=pages[1:])
    return buf.getvalue()
