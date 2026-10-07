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


# ---------------------------------------------------------------- certificates, name tags and a weekly timetable (A4 PDF, fill in by hand)
LAND_W, LAND_H = PAGE_H, PAGE_W            # A4 landscape


def _paste_fit(page, illustration: Path, box: tuple[int, int, int, int], flip: bool = False):
    from PIL import Image, ImageOps
    im = Image.open(illustration).convert("RGBA")
    if flip:
        im = ImageOps.mirror(im)
    x0, y0, x1, y1 = box
    sc = min((x1 - x0) / im.width, (y1 - y0) / im.height)
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    page.paste(im, (x0 + (x1 - x0 - im.width) // 2, y0 + (y1 - y0 - im.height) // 2), im)


def certificate_page(illustration: Path, font_path: str):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", (LAND_W, LAND_H), (255, 252, 240))
    d = ImageDraw.Draw(page)
    gold, brown = (214, 160, 40), (91, 58, 41)
    d.rounded_rectangle([60, 60, LAND_W - 60, LAND_H - 60], radius=40, outline=gold, width=14)
    d.rounded_rectangle([100, 100, LAND_W - 100, LAND_H - 100], radius=28, outline=brown, width=4)
    d.text((LAND_W // 2, 330), "賞　状", font=_font(font_path, 250), fill=brown, anchor="mm")
    d.line([(420, 640), (1500, 640)], fill=brown, width=5)
    d.text((1560, 640), "さん", font=_font(font_path, 90), fill=brown, anchor="lm")
    d.text((LAND_W // 2, 800), "あなたは　いつも　とても　がんばりました", font=_font(font_path, 80), fill=brown, anchor="mm")
    d.text((LAND_W // 2, 930), "よって　ここに　ほめたたえます", font=_font(font_path, 80), fill=brown, anchor="mm")
    d.text((900, 1240), "　　　　年　　　月　　　日", font=_font(font_path, 70), fill=brown, anchor="mm")
    d.line([(1250, 1420), (2050, 1420)], fill=brown, width=4)
    d.text((2090, 1420), "より", font=_font(font_path, 70), fill=brown, anchor="lm")
    _paste_fit(page, illustration, (150, 930, 620, 1530))
    _paste_fit(page, illustration, (LAND_W - 620, 930, LAND_W - 150, 1530), flip=True)
    d.text((LAND_W // 2, LAND_H - 150), "minna-no-illust.com", font=_font(font_path, 36), fill=(150, 130, 115), anchor="mm")
    return page


def nametag_page(illustration: Path, font_path: str):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(page)
    cols, rows = 2, 5
    mx, my = 60, 70
    cw, ch = (PAGE_W - 2 * mx) // cols, (PAGE_H - 2 * my) // rows
    for r in range(rows):
        for c in range(cols):
            x, y = mx + c * cw, my + r * ch
            d.rectangle([x, y, x + cw, y + ch], outline=(150, 150, 150), width=2)         # cut line
            d.rounded_rectangle([x + 16, y + 16, x + cw - 16, y + ch - 16], radius=26, outline=(91, 58, 41), width=5, fill=(255, 252, 240))
            _paste_fit(page, illustration, (x + 30, y + 30, x + 30 + ch - 60, y + ch - 30))
            d.text((x + ch + 10, y + 70), "なまえ", font=_font(font_path, 36), fill=(120, 100, 90))
            d.line([(x + ch + 10, y + ch - 90), (x + cw - 40, y + ch - 90)], fill=(91, 58, 41), width=4)
    d.text((PAGE_W // 2, PAGE_H - 30), "minna-no-illust.com  切りとって、つかってね", font=_font(font_path, 28), fill=(140, 120, 105), anchor="mm")
    return page


def timetable_page(illustration: Path, font_path: str):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", (LAND_W, LAND_H), (255, 253, 247))
    d = ImageDraw.Draw(page)
    brown = (91, 58, 41)
    d.text((110, 100), "じかんわり", font=_font(font_path, 150), fill=brown)
    d.text((1250, 190), "なまえ", font=_font(font_path, 56), fill=brown, anchor="lm")
    d.line([(1420, 215), (2160, 215)], fill=brown, width=4)
    _paste_fit(page, illustration, (780, 40, 1180, 330))
    days = "月火水木金"
    left, top = 110, 380
    cw0, cw = 190, (LAND_W - 220 - 190) // 5
    head_h = 110
    row_h = (LAND_H - top - head_h - 150) // 6
    d.rectangle([left, top, left + cw0, top + head_h], fill=(255, 240, 184), outline=brown, width=3)
    for i, ch in enumerate(days):
        x = left + cw0 + i * cw
        d.rectangle([x, top, x + cw, top + head_h], fill=(255, 240, 184), outline=brown, width=3)
        d.text((x + cw / 2, top + head_h / 2), ch, font=_font(font_path, 70), fill=brown, anchor="mm")
    for r in range(6):
        y = top + head_h + r * row_h
        d.rectangle([left, y, left + cw0, y + row_h], fill=(217, 241, 255), outline=brown, width=3)
        d.text((left + cw0 / 2, y + row_h / 2), f"{r + 1}", font=_font(font_path, 70), fill=brown, anchor="mm")
        for i in range(5):
            x = left + cw0 + i * cw
            d.rectangle([x, y, x + cw, y + row_h], fill="white", outline=brown, width=3)
    d.text((LAND_W // 2, LAND_H - 70), "minna-no-illust.com  無料・商用OK", font=_font(font_path, 32), fill=(111, 90, 78), anchor="mm")
    return page


PRINTABLE_KINDS = {
    "shojo": ("賞状", certificate_page, "賞状テンプレート"),
    "nafuda": ("名札", nametag_page, "名札"),
    "jikanwari": ("時間割", timetable_page, "時間割"),
}


def printable_pdf(kind: str, illustration: Path, font_path: str) -> bytes:
    buf = io.BytesIO()
    PRINTABLE_KINDS[kind][1](illustration, font_path).save(buf, format="PDF", resolution=DPI, quality=90)
    return buf.getvalue()


def printable_preview(kind: str, illustration: Path, font_path: str) -> bytes:
    page = PRINTABLE_KINDS[kind][1](illustration, font_path)
    w = 480
    im = page.resize((w, round(page.height * w / page.width)))
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=80)
    return buf.getvalue()
