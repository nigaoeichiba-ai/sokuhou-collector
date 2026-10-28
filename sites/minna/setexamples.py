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


def christmas_card() -> None:
    """The example of the guide /guide/christmas-card/ (not of a set page): one picture of a set at its own size on a postcard."""
    s = "christmas-animals-kawaii"
    im, d = paper(592, 876)
    centered(d, "Merry Christmas", 296, 50, font(56, 800), ACCENT)
    p = pic(s, "christmas-animals-kawaii-cat")
    put(im, p, 296, 170)
    centered(d, "今年も一年、ありがとう。\nあたたかい冬をお過ごしください。", 296, 700, font(28, 500), INK, 10)
    centered(d, "○○より", 296, 810, font(26, 600), SOFT)
    save(im, "christmas-card-1")


def silhouette(im: Image.Image, colour=(40, 40, 40)) -> Image.Image:
    """The shape of a picture in one colour (its own alpha, nothing drawn)."""
    out = Image.new("RGBA", im.size, colour + (0,))
    out.putalpha(im.split()[3])
    return out


def fit_text(d: ImageDraw.ImageDraw, text: str, width: int, size: int, weight: int) -> ImageFont.FreeTypeFont:
    """The biggest font (from `size` down) in which the text is not wider than `width`."""
    while size > 10:
        f = font(size, weight)
        if d.textlength(text, font=f) <= width:
            return f
        size -= 2
    return font(10, weight)


def tropical() -> None:
    s = "tropical-fruits-flat"
    im, d = paper(592, 876)
    centered(d, "南国フルーツ", 296, 40, font(54, 800), ACCENT)
    centered(d, "お品書き", 296, 108, font(34, 700), INK)
    items = [("dragonfruit", "ドラゴンフルーツ"), ("mango", "マンゴー"), ("pineapple", "パイナップル"), ("coconut", "ココナッツ")]
    for k, (key, name) in enumerate(items):
        p = pic(s, f"{s}-{key}", 0.5)
        cx, top = 160 + (k % 2) * 272, 190 + (k // 2) * 330
        put(im, p, cx, top)
        centered(d, name, cx, top + 262, font(28, 700), INK, 4)
        centered(d, "○○円", cx, top + 298, font(26, 500), SOFT, 4)
    save(im, f"{s}-1")
    im, d = paper(876, 592)
    centered(d, "中は どうなっているかな?", 438, 24, font(40, 800), INK)
    for k, key in enumerate(["dragonfruit", "passionfruit", "durian"]):
        p = pic(s, f"{s}-{key}", 0.5)
        cx = 150 + k * 288
        put(im, p, cx, 130)
        d.rounded_rectangle([cx - 120, 440, cx + 120, 520], radius=14, outline=(214, 214, 214, 255), width=3)
        centered(d, "?", cx, 450, font(52, 800), ACCENT)
    centered(d, "ゆびさして こたえよう", 438, 540, font(26, 500), SOFT)
    save(im, f"{s}-2")


def undokai() -> None:
    s = "animals-undokai-kawaii"
    im, d = paper(592, 876)
    centered(d, "運動会プログラム", 296, 36, font(46, 800), ACCENT)
    centered(d, "○月○日(○)", 296, 100, font(28, 600), INK)
    rows = [("rabbit-run", "かけっこ"), ("bear-tsunahiki", "綱引き"), ("monkey-tamaire", "玉入れ"), ("cat-hurdle", "ハードル走"), ("elephant-ball", "大玉ころがし"), ("pig-bread", "パン食い競走")]
    for k, (key, name) in enumerate(rows):
        y = 160 + k * 112
        p = pic(s, f"{s}-{key}", 0.3)
        put(im, p, 100, y + 56 - p.height // 2)
        d.text((190, y + 22), name, font=font(34, 700), fill=INK)
        d.text((190, y + 66), "○時○分", font=font(24, 500), fill=SOFT)
        d.line([(60, y + 108), (532, y + 108)], fill=(228, 228, 228, 255), width=2)
    save(im, f"{s}-1")
    from sites.minna.setguides import blank_box
    im, d = paper(876, 592)
    lion = pic(s, f"{s}-lion-medal")
    b = blank_box(lion, "cream")
    pos = put(im, lion, 240, 40)
    cx = pos[0] + (b[0] + b[2]) // 2
    cy = pos[1] + (b[1] + b[3]) // 2
    f = font(64, 800)
    d.text((cx - d.textlength("1", font=f) / 2, cy - 44), "1", font=f, fill=ACCENT)
    centered(d, "よくがんばりました", 640, 170, font(40, 800), INK)
    centered(d, "○○さん", 640, 260, font(46, 800), ACCENT)
    centered(d, "○月○日 運動会", 640, 360, font(28, 500), SOFT)
    save(im, f"{s}-2")


def newyear_eve() -> None:
    s = "newyear-eve-cool-sumi"
    im, d = paper(592, 876)
    centered(d, "大みそかの よる", 296, 40, font(52, 800), ACCENT)
    d.line([(60, 120), (532, 120)], fill=(214, 214, 214, 255), width=2)
    rows = [("joya-bell", "除夜の鐘"), ("toshikoshi-soba", "年越しそば"), ("clock-midnight", "0時を まつ")]
    for k, (key, name) in enumerate(rows):
        y = 150 + k * 230
        p = pic(s, f"{s}-{key}", 0.42)
        put(im, p, 120, y + 100 - p.height // 2)
        d.text((260, y + 60), name, font=font(40, 800), fill=INK)
        d.text((260, y + 120), "○時から", font=font(30, 500), fill=SOFT)
    centered(d, "どなたでも どうぞ", 296, 820, font(26, 500), SOFT, 8)
    save(im, f"{s}-1")
    im, d = paper(592, 876)
    centered(d, "謹賀新年", 296, 44, font(76, 800), ACCENT)
    p = pic(s, f"{s}-hatsuhinode")
    put(im, p, 296, 190)
    centered(d, "2027年 元旦", 296, 730, font(34, 700), INK)
    centered(d, "旧年中はお世話になりました。\n本年もよろしくお願いいたします。", 296, 782, font(24, 500), INK, 10)
    save(im, f"{s}-2")


def office() -> None:
    s = "office-worker-middleaged-flat"
    im, d = paper(876, 592)
    p = pic(s, f"{s}-meeting")
    put(im, p, 200, 60)
    centered(d, "定例会議の お知らせ", 650, 60, font(40, 800), INK)
    centered(d, "○月○日(○) ○時から\n会議室○", 650, 160, font(34, 700), ACCENT, 12)
    centered(d, "資料は 前日までに\n共有フォルダへ お願いします。", 650, 320, font(26, 500), INK, 10)
    save(im, f"{s}-1")
    im, d = paper(1168, 592)
    centered(d, "ある会社員の 一日", 584, 20, font(40, 800), INK)
    for k, (key, name) in enumerate([("commute", "通勤"), ("pc-work", "作業"), ("lunch", "昼食"), ("back-home", "帰宅")]):
        p = pic(s, f"{s}-{key}", 0.5)
        cx = 146 + k * 292
        put(im, p, cx, 110 + (300 - p.height) // 2)
        centered(d, name, cx, 440, font(34, 700), INK, 4)
        centered(d, "○時", cx, 490, font(28, 500), SOFT, 4)
    save(im, f"{s}-2")


def nametags() -> None:
    from sites.minna.setguides import blank_box
    s = "animal-nametags-kawaii"

    def name_on(base, d, key, cx, top, name, scale):
        p = pic(s, f"{s}-{key}")
        b = blank_box(p, "cream")
        if scale != 1.0:
            q = pic(s, f"{s}-{key}", scale)
        else:
            q = p
        pos = put(base, q, cx, top)
        bx0, by0, bx1, by1 = [round(v * scale) for v in b]
        f = fit_text(d, name, int((bx1 - bx0) * 0.8), 40, 800)
        tx = pos[0] + (bx0 + bx1) // 2
        ty = pos[1] + (by0 + by1) // 2
        d.text((tx - d.textlength(name, font=f) / 2, ty - f.size * 0.6), name, font=f, fill=INK)

    im, d = paper(592, 876)
    centered(d, "ロッカー", 296, 30, font(44, 800), ACCENT)
    names = [("cat", "あおい"), ("dog", "そうた"), ("bear", "ひなた"), ("fox", "れん"), ("panda", "ゆいな"), ("lion", "はると")]
    for k, (key, nm) in enumerate(names):
        name_on(im, d, key, 160 + (k % 2) * 272, 110 + (k // 2) * 245, nm, 0.5)
    save(im, f"{s}-1")
    im, d = paper(876, 592)
    centered(d, "おせき", 438, 20, font(36, 800), INK)
    name_on(im, d, "penguin", 230, 90, "やまださま", 1.0)
    name_on(im, d, "sheep", 640, 90, "さとうさま", 1.0)
    save(im, f"{s}-2")


def oshogatsu_sumi() -> None:
    s = "oshogatsu-sumi-cool"
    im, d = paper(592, 876)
    centered(d, "賀正", 296, 40, font(84, 800), ACCENT)
    p = pic(s, f"{s}-shishimai")
    put(im, p, 296, 200)
    centered(d, "2027年 元旦", 296, 730, font(34, 700), INK)
    centered(d, "本年も どうぞ よろしく お願いいたします。", 296, 790, font(24, 500), INK, 10)
    save(im, f"{s}-1")
    im, d = paper(876, 592)
    centered(d, "新春 あそびの会", 438, 24, font(46, 800), ACCENT)
    for k, (key, name) in enumerate([("hagoita", "羽根つき"), ("koma", "こま回し"), ("daruma", "だるま落とし")]):
        p = pic(s, f"{s}-{key}", 0.5)
        cx = 146 + k * 292
        put(im, p, cx, 120 + (270 - p.height) // 2)
        centered(d, name, cx, 420, font(32, 700), INK, 4)
    centered(d, "○月○日(○) ○時から", 438, 500, font(30, 600), SOFT)
    save(im, f"{s}-2")


def zoo() -> None:
    s = "realistic-zoo-field-guide"
    im, d = paper(592, 876)
    centered(d, "どうぶつカード", 296, 30, font(44, 800), INK)
    p = pic(s, f"{s}-panda")
    put(im, p, 296, 110)
    d.text((70, 640), "なまえ", font=font(26, 700), fill=SOFT)
    d.text((200, 636), "パンダ", font=font(40, 800), fill=INK)
    for k, label in enumerate(["すんでいる ところ", "たべもの", "しらべて わかったこと"]):
        y = 710 + k * 52
        d.text((70, y), label, font=font(24, 600), fill=SOFT)
        d.line([(70, y + 40), (522, y + 40)], fill=(190, 190, 190, 255), width=2)
    save(im, f"{s}-1")
    im, d = paper(1168, 592)
    centered(d, "これは だれかな?", 584, 20, font(42, 800), INK)
    names = [("giraffe", "キリン"), ("zebra", "シマウマ"), ("elephant", "アフリカゾウ")]
    for k, (key, nm) in enumerate(names):
        p = pic(s, f"{s}-{key}", 0.55)
        cx = 195 + k * 389
        put(im, silhouette(p), cx, 100 + (330 - p.height) // 2)
        centered(d, "こたえ: " + nm, cx, 480, font(28, 700), SOFT, 4)
    save(im, f"{s}-2")


if __name__ == "__main__":
    event_frames()
    bowing()
    winter()
    eto()
    christmas_card()
    tropical()
    undokai()
    newyear_eve()
    office()
    nametags()
    oshogatsu_sumi()
    zoo()
