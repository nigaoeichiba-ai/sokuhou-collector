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
INK, ACCENT, ACCENT_S, WHITE, CREAM, LINE = (43, 38, 33), (200, 58, 42), (253, 232, 227), (255, 255, 255), (251, 246, 238), (233, 223, 208)
ASSETS = Path(__file__).resolve().parent / "assets"
PHOTO_W = 440


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return find_font() is not None


def _word_char(ch: str) -> bool:
    """A character of a katakana word or a number: a line is not broken inside one (「プレゼ/ント」, 「10/月」)."""
    return "ァ" <= ch <= "ヺ" or ch in "ー・" or ch.isdigit()


def _wrap(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_w and cur:
            if _word_char(cur[-1]) and _word_char(ch):                  # inside a word: break before the whole word instead
                j = len(cur)
                while j > 0 and _word_char(cur[j - 1]):
                    j -= 1
                if j > 0:
                    lines.append(cur[:j])
                    cur = cur[j:] + ch
                    continue
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


BAR = {"s1": (229, 154, 126), "s2": (127, 179, 198), "s3": (155, 194, 131)}
RANGE_BAND, TRACK = (240, 195, 179), (244, 238, 228)


@functools.lru_cache(maxsize=256)
def chart_card(*, title: str, finding: str, rows: tuple, source: str, site: str, tall: bool = False, series: str = "s1", ranges: bool = False) -> bytes:
    """A chart as a picture to send or keep: the title, the one sentence the chart shows, up to eight bars, the source and the site name.

    rows: ((label, value, text), ...) for bars; ((label, low, median, high, text), ...) when `ranges` (the pale band is low..high, the tick the median).
    1200x630 for link previews, 1080x1350 (`tall`) for saving, or Stories.
    """
    from PIL import Image, ImageDraw, ImageFont
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    w, h = (1080, 1350) if tall else (W, H)
    img = Image.new("RGB", (w, h), CREAM)
    d = ImageDraw.Draw(img)
    pad = 54
    d.rounded_rectangle([24, 24, w - 24, h - 24], radius=32, outline=LINE, width=3, fill=WHITE)
    rows = tuple(rows)[:8]
    x0 = pad + 24
    inner_w = w - 2 * x0
    f_tag = ImageFont.truetype(path, 28 if not tall else 30)
    d.rounded_rectangle([x0, 64, x0 + d.textlength("データ室", font=f_tag) + 44, 64 + 50], radius=25, fill=ACCENT_S)
    d.text((x0 + 22, 89), "データ室", font=f_tag, fill=ACCENT, anchor="lm")
    # title
    tsize = 46 if not tall else 58
    f_title = ImageFont.truetype(path, tsize)
    lines = _wrap(d, title, f_title, inner_w, 3 if tall else 2)
    y = 138
    for line in lines:
        d.text((x0, y), line, font=f_title, fill=INK)
        y += int(tsize * 1.28)
    # the one sentence
    f_find = ImageFont.truetype(path, 27 if not tall else 34)
    for line in _wrap(d, finding, f_find, inner_w, 2):
        d.text((x0, y + 6), line, font=f_find, fill=(110, 100, 90))
        y += int((27 if not tall else 34) * 1.45)
    y += 22
    # bars
    foot = 110 if not tall else 150
    avail = h - 24 - foot - y
    n = max(1, len(rows))
    row_h = min(70 if not tall else 120, avail // n)
    y += max(0, (avail - row_h * n) // 3) if tall else 0
    f_lab = ImageFont.truetype(path, 26 if not tall else 34)
    f_val = ImageFont.truetype(path, 25 if not tall else 32)
    lab_w = int(max([d.textlength(r[0], font=f_lab) for r in rows] + [120]))
    lab_w = min(lab_w, int(inner_w * 0.34))
    val_w = int(max([d.textlength(r[-1], font=f_val) for r in rows] + [60]))
    val_w = min(val_w, int(inner_w * 0.30))
    tx0 = x0 + lab_w + 20
    tx1 = x0 + inner_w - val_w - 18
    bar_h = int(row_h * 0.5)
    top = max([r[1] for r in rows] + [1]) if not ranges else max([r[3] for r in rows] + [1])
    for i, r in enumerate(rows):
        cy = y + i * row_h + row_h // 2
        label = r[0]
        while d.textlength(label, font=f_lab) > lab_w and len(label) > 2:
            label = label[:-2] + "…"
        d.text((x0, cy), label, font=f_lab, fill=INK, anchor="lm")
        d.rounded_rectangle([tx0, cy - bar_h // 2, tx1, cy + bar_h // 2], radius=bar_h // 2, fill=TRACK)
        if ranges:
            _, lo, med, hi, text = r
            a = tx0 + (tx1 - tx0) * lo / top
            b = max(a + 8, tx0 + (tx1 - tx0) * hi / top)
            d.rounded_rectangle([a, cy - bar_h // 2, b, cy + bar_h // 2], radius=bar_h // 2, fill=RANGE_BAND)
            m = tx0 + (tx1 - tx0) * med / top
            d.rounded_rectangle([m - 2, cy - bar_h // 2 - 4, m + 2, cy + bar_h // 2 + 4], radius=2, fill=INK)
        else:
            _, v, text = r
            e = max(tx0 + bar_h, tx0 + (tx1 - tx0) * v / top)
            d.rounded_rectangle([tx0, cy - bar_h // 2, e, cy + bar_h // 2], radius=bar_h // 2, fill=BAR.get(series, BAR["s1"]))
        d.text((x0 + inner_w, cy), text, font=f_val, fill=INK, anchor="rm")
    # source and site
    f_src = ImageFont.truetype(path, 21 if not tall else 26)
    src_lines = _wrap(d, source, f_src, inner_w - 260, 2)
    sy = h - 24 - (foot - 30) if tall else h - 24 - 84
    for j, line in enumerate(src_lines):
        d.text((x0, sy + j * int((21 if not tall else 26) * 1.4)), line, font=f_src, fill=(130, 120, 108))
    f_site = ImageFont.truetype(path, 26 if not tall else 30)
    sw = d.textlength(site, font=f_site)
    d.rounded_rectangle([w - x0 - sw - 40, h - 24 - 74, w - x0, h - 24 - 22], radius=26, fill=CREAM, outline=LINE, width=2)
    d.text((w - x0 - sw - 20, h - 24 - 48), site, font=f_site, fill=INK, anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@functools.lru_cache(maxsize=64)
def persona_card(*, name: str, tagline: str, likes: tuple, avoid: tuple, line: str, site: str, photo: str = "") -> bytes:
    """The result of the 診断 as a picture to keep or send (1080x1350): the type's name, what pleases that person, what to be careful with, the line to say when handing it over."""
    from PIL import Image, ImageDraw, ImageFont
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    w, h = 1080, 1350
    img = Image.new("RGB", (w, h), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 24, w - 24, h - 24], radius=32, outline=LINE, width=3, fill=WHITE)
    x0, inner = 78, w - 156
    y = 70
    photo_file = ASSETS / "mood" / f"{photo}.webp" if photo else None
    if photo_file and photo_file.exists():                                  # a mood photograph across the top, rounded
        ph = Image.open(photo_file).convert("RGB")
        ph_w, ph_h = w - 96, 300
        scale = max(ph_w / ph.width, ph_h / ph.height)
        ph = ph.resize((int(ph.width * scale) + 1, int(ph.height * scale) + 1), Image.LANCZOS)
        left, top = (ph.width - ph_w) // 2, (ph.height - ph_h) // 2
        ph = ph.crop((left, top, left + ph_w, top + ph_h))
        mask = Image.new("L", (ph_w, ph_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, ph_w - 1, ph_h - 1], radius=26, fill=255)
        img.paste(ph, (48, 48), mask)
        y = 48 + ph_h + 34
    f_tag = ImageFont.truetype(path, 28)
    d.rounded_rectangle([x0, y, x0 + d.textlength("プレゼント診断の結果", font=f_tag) + 44, y + 50], radius=25, fill=ACCENT_S)
    d.text((x0 + 22, y + 25), "プレゼント診断の結果", font=f_tag, fill=ACCENT, anchor="lm")
    y += 80
    f_name = ImageFont.truetype(path, 62)
    for ln in _wrap(d, name, f_name, inner, 2):
        d.text((x0, y), ln, font=f_name, fill=INK)
        y += 78
    f_tg = ImageFont.truetype(path, 31)
    for ln in _wrap(d, tagline, f_tg, inner, 2):
        d.text((x0, y), ln, font=f_tg, fill=(110, 100, 90))
        y += 44
    y += 22
    f_h = ImageFont.truetype(path, 30)
    f_row = ImageFont.truetype(path, 34)
    d.text((x0, y), "よろこびやすいもの", font=f_h, fill=ACCENT)
    y += 52
    for i, t in enumerate(likes[:3], 1):
        d.ellipse([x0, y + 4, x0 + 44, y + 48], fill=ACCENT_S)
        d.text((x0 + 22, y + 26), str(i), font=f_h, fill=ACCENT, anchor="mm")
        d.text((x0 + 66, y + 26), _fit(d, t, f_row, inner - 66), font=f_row, fill=INK, anchor="lm")
        y += 64
    y += 18
    d.text((x0, y), "ちょっと外しやすいもの", font=f_h, fill=(110, 100, 90))
    y += 52
    for t in avoid[:2]:
        d.text((x0 + 4, y + 22), "・" + _fit(d, t, f_row, inner - 40), font=f_row, fill=(90, 82, 74), anchor="lm")
        y += 58
    y += 20
    d.line([x0, y, w - x0, y], fill=LINE, width=2)
    y += 28
    f_line = ImageFont.truetype(path, 30)
    for ln in _wrap(d, f"渡すときのひとこと: 「{line}」", f_line, inner, 3):
        d.text((x0, y), ln, font=f_line, fill=INK)
        y += 44
    f_site = ImageFont.truetype(path, 30)
    sw = d.textlength(site, font=f_site)
    d.rounded_rectangle([w - x0 - sw - 40, h - 24 - 84, w - x0, h - 24 - 30], radius=27, fill=CREAM, outline=LINE, width=2)
    d.text((w - x0 - sw - 20, h - 24 - 57), site, font=f_site, fill=INK, anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fit(draw, text: str, font, max_w: int) -> str:
    while draw.textlength(text, font=font) > max_w and len(text) > 2:
        text = text[:-2] + "…"
    return text


@functools.lru_cache(maxsize=1024)
def card(*, title: str, tag: str, site: str, photo: str = "") -> bytes:
    """One card: `tag` is the small label, `title` the headline, `photo` the name of a mood photograph in assets/mood (without .webp; none = text only)."""
    from PIL import Image, ImageDraw, ImageFont
    path = find_font()
    if path is None:
        raise RuntimeError("no Japanese font found")
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([30, 30, W - 30, H - 30], radius=36, outline=LINE, width=3, fill=WHITE)
    photo_file = ASSETS / "mood" / f"{photo}.webp" if photo else None
    has_photo = bool(photo_file and photo_file.exists())
    if has_photo:                                           # a mood photograph on the right, rounded to the card's corners
        ph = Image.open(photo_file).convert("RGB")
        ph_w, ph_h = PHOTO_W, H - 60
        scale = max(ph_w / ph.width, ph_h / ph.height)
        ph = ph.resize((int(ph.width * scale) + 1, int(ph.height * scale) + 1), Image.LANCZOS)
        left, top = (ph.width - ph_w) // 2, (ph.height - ph_h) // 2
        ph = ph.crop((left, top, left + ph_w, top + ph_h))
        mask = Image.new("L", (ph_w, ph_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([-60, 0, ph_w - 1, ph_h - 1], radius=36, fill=255)
        img.paste(ph, (W - 30 - ph_w, 30), mask)
    # label: pale, with the accent only in its text
    f_tag = ImageFont.truetype(path, 32)
    tag_w = W - 86 - 60 - (PHOTO_W if has_photo else 0)
    while d.textlength(tag, font=f_tag) + 56 > tag_w and len(tag) > 4:
        tag = tag[:-2] + "…"
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([86, 92, 86 + tw + 56, 92 + 62], radius=31, fill=ACCENT_S)
    d.text((86 + 28, 123), tag, font=f_tag, fill=ACCENT, anchor="lm")
    # title, up to 3 lines, as large as fits the left column
    col_w = W - 86 - 60 - (PHOTO_W if has_photo else 50)
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
