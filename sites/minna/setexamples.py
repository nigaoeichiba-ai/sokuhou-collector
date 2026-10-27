"""みんなのイラスト: the 完成例 pictures of the featured sets (/series/<slug>/), made only from the pictures that are already in the library.

    python sites/minna/setexamples.py            # writes sites/minna/assets/examples/<slug>-<n>.webp

The pictures are put on the page at their own size (never enlarged), the words are set in Noto Sans JP (SIL Open Font License), and every date is a blank (○) so that no picture says
anything that is not true.  The result is committed (the build only copies it); run this again when a set or an example changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from sites.minna.setguides import inner_box   # noqa: E402

LIB = HERE / "library"
OUT = HERE / "assets" / "examples"
FONT_PATHS = ["C:/Windows/Fonts/NotoSansJP-VF.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf", "/usr/share/fonts/truetype/noto/NotoSansJP-VF.ttf"]
INK = (51, 51, 51, 255)
SOFT = (110, 110, 110, 255)
ACCENT = (200, 60, 50, 255)


def font(size: int, weight: int = 500) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            f = ImageFont.truetype(p, size)
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
            return f
    raise SystemExit("Noto Sans JP not found")


def pic(slug: str, item: str, scale: float = 1.0) -> Image.Image:
    im = Image.open(LIB / slug / f"{item}.webp").convert("RGBA")
    if scale != 1.0:
        assert scale < 1.0, "never enlarge a picture"
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    return im


def paper(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(214, 214, 214, 255), width=2)
    return im, d


def put(base: Image.Image, im: Image.Image, cx: int, top: int) -> tuple[int, int, int, int]:
    x = cx - im.width // 2
    base.alpha_composite(im, (x, top))
    return x, top, x + im.width, top + im.height


def centered(d: ImageDraw.ImageDraw, text: str, cx: int, y: int, f, fill=INK, spacing: int = 8) -> int:
    """Draw (possibly several lines of) text centred on cx from y; returns the y under the last line."""
    for line in text.split("\n"):
        w = d.textlength(line, font=f)
        d.text((cx - w / 2, y), line, font=f, fill=fill)
        y += f.size + spacing
    return y


def inside_frame(d: ImageDraw.ImageDraw, frame: tuple[int, int, int, int], box: tuple[int, int, int, int], lines: list[tuple[str, int, int, tuple]]) -> None:
    """Text lines [(text, size, weight, colour)] stacked in the middle of the frame's empty part (box is the empty part in the picture's own pixels)."""
    fx, fy, _, _ = frame
    bx0, by0, bx1, by1 = box
    cx = fx + (bx0 + bx1) // 2
    total = sum(s + 10 for _, s, _, _ in lines) - 10
    y = fy + (by0 + by1) // 2 - total // 2
    for text, size, weight, col in lines:
        f = font(size, weight)
        w = d.textlength(text, font=f)
        assert w <= (bx1 - bx0) - 8, f"'{text}' ({w:.0f}px) does not fit the empty part ({bx1 - bx0}px)"
        d.text((cx - w / 2, y), text, font=f, fill=col)
        y += size + 10


def save(im: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)
    print(name, im.size)


def event_frames() -> None:
    s = "event-frames-flat"
    # 1: a notice on a postcard (100x148mm at 150dpi = 592x876)
    im, d = paper(592, 876)
    fr = pic(s, "event-frames-flat-undokai")
    box = inner_box(fr)
    pos = put(im, fr, 296, 40)
    inside_frame(d, pos, box, [("運動会", 64, 800, ACCENT), ("○月○日(○)", 32, 600, INK)])
    centered(d, "雨のときは\n○月○日(○)に行います", 296, 540, font(30, 500))
    centered(d, "お弁当と水筒を\nお持ちください", 296, 680, font(30, 500))
    d.line([(90, 840), (502, 840)], fill=(214, 214, 214, 255), width=2)
    save(im, f"{s}-1")
    # 2: a lunch-letter title (square)
    im, d = paper(592, 592)
    fr = pic(s, "event-frames-flat-kyushoku")
    box = inner_box(fr)
    pos = put(im, fr, 296, 30)
    inside_frame(d, pos, box, [("給食だより", 46, 800, INK), ("○月号", 34, 600, SOFT)])
    centered(d, "今月の献立は、うらの面にあります。", 296, 520, font(24, 500), SOFT)
    save(im, f"{s}-2")


def bowing() -> None:
    s = "bowing-greetings-flat"
    im, d = paper(876, 592)
    p = pic(s, "bowing-greetings-flat-hoikushi")
    put(im, p, 150, 40)
    centered(d, "ご来園の方へ", 590, 90, font(48, 800), ACCENT)
    centered(d, "受付は 正面入口です。\n出入りのときは、\n上ばきにはきかえてください。", 590, 190, font(34, 500), INK, 14)
    save(im, f"{s}-1")
    im, d = paper(876, 592)
    p = pic(s, "bowing-greetings-flat-newbie")
    put(im, p, 150, 40)
    centered(d, "新入社員のごあいさつ", 590, 90, font(44, 800), INK)
    centered(d, "○月○日から\n○○課に配属になりました。\n一日も早く仕事をおぼえます。\nどうぞよろしくお願いいたします。", 590, 180, font(30, 500), INK, 14)
    save(im, f"{s}-2")


def winter() -> None:
    s = "winter-prep-year-end-flat"
    im, d = paper(592, 876)
    centered(d, "12月の おたより", 296, 40, font(52, 800), ACCENT)
    d.line([(60, 120), (532, 120)], fill=(214, 214, 214, 255), width=2)
    row = [("winter-prep-year-end-flat-osouji", "大掃除", "12月○日"), ("winter-prep-year-end-flat-mochitsuki", "餅つき", "12月○日"), ("winter-prep-year-end-flat-toji", "冬至", "12月○日")]
    y = 140
    for item, name, day in row:
        p = pic(s, item, 0.42)
        put(im, p, 110, y)
        d.text((230, y + 60), name, font=font(40, 800), fill=INK)
        d.text((230, y + 118), day, font=font(30, 500), fill=SOFT)
        y += 215
    centered(d, "持ち物は 各クラスの連絡帳で\nお知らせします。", 296, 800, font(26, 500), SOFT, 8)
    save(im, f"{s}-1")
    im, d = paper(876, 592)
    p = pic(s, "winter-prep-year-end-flat-kagamimochi", 0.7)
    put(im, p, 190, 110)
    centered(d, "年末年始\n休業のお知らせ", 620, 60, font(40, 800), INK, 8)
    centered(d, "○月○日(○)から\n○月○日(○)まで", 620, 210, font(36, 800), ACCENT, 10)
    centered(d, "営業は ○月○日(○)から\n再開します。\nお急ぎの連絡は\nメールでお願いします。", 620, 360, font(26, 500), INK, 10)
    save(im, f"{s}-2")


def eto() -> None:
    s = "eto-lineup-kawaii"
    im, d = paper(592, 876)
    centered(d, "謹賀新年", 296, 50, font(76, 800), ACCENT)
    p = pic(s, "eto-lineup-kawaii-sheep")
    put(im, p, 296, 190)
    centered(d, "2027年 元旦", 296, 700, font(34, 700), INK)
    centered(d, "旧年中はお世話になりました。\n本年もよろしくお願いいたします。", 296, 752, font(26, 500), INK, 10)
    save(im, f"{s}-1")
    names = [("rat", "子", "ね"), ("ox", "丑", "うし"), ("tiger", "寅", "とら"), ("rabbit", "卯", "う"), ("dragon", "辰", "たつ"), ("snake", "巳", "み"),
             ("horse", "午", "うま"), ("sheep", "未", "ひつじ"), ("monkey", "申", "さる"), ("rooster", "酉", "とり"), ("dog", "戌", "いぬ"), ("boar", "亥", "い")]
    cw, ch = 292, 330
    im, d = paper(cw * 4, 100 + ch * 3)
    centered(d, "十二支の動物", cw * 2, 22, font(44, 800), INK)
    for k, (en, kanji, yomi) in enumerate(names):
        p = pic(s, f"eto-lineup-kawaii-{en}", 0.5)
        x0, y0 = (k % 4) * cw, 100 + (k // 4) * ch
        put(im, p, x0 + cw // 2, y0 + 8)
        centered(d, f"{kanji}({yomi})", x0 + cw // 2, y0 + 8 + p.height + 4, font(32, 700), INK, 4)
    save(im, f"{s}-2")


if __name__ == "__main__":
    event_frames()
    bowing()
    winter()
    eto()
