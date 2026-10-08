"""atomou: the skins (きせかえ).  A skin is not only a palette: it also names the *shape* of the page (header, buttons, spacing, numbers, decoration, menu, genre tiles, card list).

colours / sizes: the site CSS reads only the custom properties listed in VARS.  css() returns one `:root[data-skin="<id>"]{...}` block per skin; `basic` is also
the default and its values are written to `:root{...}`.  The page is ALWAYS light unless the visitor picks a dark skin: there is no prefers-color-scheme rule.

shapes: every skin has `attrs`, one value per key of ATTR_VALUES.  The page puts them on <html> as data-head / data-btn / data-density / data-num / data-deco /
data-nav / data-cat / data-list (assets/design.css styles them; `basic` gets none of them, and the first value of each key is the base look that style.css has).
Each skin also names a `card` kind (plain / sticky / panel / ring) for data-card.

season: a seasonal skin has `"season": {"from": "MM-DD", "to": "MM-DD", "label": ...}` (a period may cross New Year).  Seasonal skins come after the normal ones in SKINS.

--bg-image is a CSS gradient (or none) laid over --bg.  System fonts only, no external fonts.  skins.css has no url(): images are only in design.css, under the
selector of their skin, so a picture is fetched only when that skin is chosen.  Contrast of every pairing is checked by tests/test_atomou_skins.py (WCAG ratios).
"""
from __future__ import annotations

from datetime import date

VARS = (
    "bg", "bg2", "surface", "surface2", "text", "muted", "line", "accent", "on-accent", "ato", "on-ato", "mou", "on-mou",
    "ato-soft", "ato-ink", "mou-soft", "mou-ink",
    "quiet-bg", "quiet-text", "quiet-line", "focus", "head-bg", "head-text", "foot-bg", "foot-text",
    "g1", "g2", "g3", "g4", "g5", "g6", "band-bg", "band-text", "deco", "deco2", "wm-ato", "wm-mou", "wm-ink",
    "radius", "shadow", "font", "font-head", "font-num", "size", "num-weight", "bw", "bg-image",
)
NON_COLOUR_VARS = ("radius", "shadow", "font", "font-head", "font-num", "size", "num-weight", "bw", "bg-image")
CARDS = ("plain", "sticky", "panel", "ring")

# the first value of each key is the base look (what style.css draws without any attribute)
ATTR_VALUES = {
    "head": ("left", "center", "band", "stripe"),
    "btn": ("pill", "square", "soft", "outline", "sticker", "underline"),
    "density": ("cozy", "compact", "airy"),
    "num": ("plain", "outline", "shadow", "mono", "badge"),
    "deco": ("none", "dots", "grid", "stripes", "waves", "stars", "paper", "leaves", "sunburst", "confetti"),
    "nav": ("pill", "tab", "underline", "boxed"),
    "cat": ("card", "chip", "circle", "ribbon", "plain"),
    "list": ("grid", "list", "masonry"),
}
ATTR_ORDER = tuple(ATTR_VALUES)

FONT_SANS = '"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic UI","BIZ UDPGothic","Yu Gothic","Meiryo","Noto Sans JP",system-ui,-apple-system,"Segoe UI",sans-serif'
FONT_ROUND = '"Hiragino Maru Gothic ProN","BIZ UDPGothic","Yu Gothic UI","Hiragino Sans","Meiryo",system-ui,sans-serif'
FONT_UD = '"BIZ UDPGothic","BIZ UDGothic","Hiragino Sans","Yu Gothic UI","Meiryo","Noto Sans JP",system-ui,sans-serif'
FONT_MINCHO = '"Hiragino Mincho ProN","Yu Mincho","YuMincho","Noto Serif JP","MS PMincho",serif'
FONT_MONO = 'ui-monospace,"Cascadia Mono","SFMono-Regular",Consolas,"BIZ UDGothic","Courier New",monospace'

DEFAULTS = {
    "radius": "12px",
    "shadow": "0 2px 8px rgba(0,0,0,.10)",
    "font": FONT_SANS,
    "size": "16px",
    "num-weight": "700",
    "bw": "1px",
    "bg-image": "none",
}


def _rgb(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _mix(a: str, b: str, t: float) -> str:
    """a + (b - a) * t, as #RRGGBB."""
    ca, cb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


def _lum(h: str) -> float:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _soft_and_ink(colour: str, surface: str, text: str) -> tuple:
    """A pale face made of `colour` on `surface` (12%) and an ink of the same hue readable on it (>= 5:1): the colour is pushed towards the text colour."""
    soft = _mix(surface, colour, 0.12)
    ink = colour
    for step in range(1, 21):
        if _ratio(ink, soft) >= 5.0:
            break
        ink = _mix(colour, text, step * 0.08)
    return soft, ink


def _toward(colour: str, target: str, bg: str, need: float) -> str:
    """`colour`, pulled towards `target` just far enough to reach the contrast `need` against `bg` (colour itself when it already does)."""
    for step in range(0, 13):
        c = _mix(colour, target, step / 12)
        if _ratio(c, bg) >= need:
            return c
    return target


def _v(spec: str) -> dict:
    """'bg #FFF; text #000; ...' -> {'bg': '#FFF', ...}; the style variables not given take DEFAULTS, and the new ones follow their parents."""
    out = dict(DEFAULTS)
    for part in spec.split(";"):
        part = part.strip()
        if part:
            k, val = part.split(None, 1)
            out[k] = val.strip()
    for name in ("ato", "mou"):
        soft, ink = _soft_and_ink(out[name], out["surface"], out["text"])
        out.setdefault(f"{name}-soft", soft)
        out.setdefault(f"{name}-ink", ink)
    # the wordmark in the header: its two colours and its ink must read on the header's own background
    out.setdefault("wm-ink", out["head-text"])
    out.setdefault("wm-ato", _toward(out["ato"], out["head-text"], out["head-bg"], 3.5))
    out.setdefault("wm-mou", _toward(out["mou"], out["head-text"], out["head-bg"], 3.5))
    out.setdefault("band-bg", out["head-bg"])
    out.setdefault("band-text", out["head-text"])
    out.setdefault("deco", out["accent"])
    out.setdefault("deco2", out["ato"])
    out.setdefault("font-head", out["font"])
    out.setdefault("font-num", out["font"])
    return out


def _attrs(spec: str) -> dict:
    """'left pill cozy plain none pill card grid' -> {'head': 'left', ...} (the order of ATTR_ORDER)."""
    vals = spec.split()
    return dict(zip(ATTR_ORDER, vals)) if len(vals) == len(ATTR_ORDER) else {"?": spec}


def _skin(id, name, desc, mood, audience, card, dark, attrs, spec, **extra):
    d = {"id": id, "name": name, "desc": desc, "mood": mood, "audience": audience, "card": card, "dark": dark, "attrs": _attrs(attrs), "vars": _v(spec)}
    d.update(extra)
    return d


def _season(frm: str, to: str, label: str) -> dict:
    return {"from": frm, "to": to, "label": label}


SKINS = [
    _skin("basic", "ベーシック", "いちばんシンプル。いつも明るい見た目", "中立・すっきり・見やすい", "どなたでも。迷ったらこれ", "plain", False,
          "left pill cozy plain none pill card grid",
          "bg #F7F7F5; bg2 #EFEFEB; surface #FFFFFF; surface2 #F0F0EC; text #1A1A1A; muted #5A5A55; line #E2E2DC;"
          "accent #1A56B8; on-accent #FFFFFF; ato #1A56B8; on-ato #FFFFFF; mou #A8420A; on-mou #FFFFFF;"
          "ato-soft #E4ECFA; ato-ink #14439A; mou-soft #FBEBDD; mou-ink #A8420A;"
          "quiet-bg #EDEDEB; quiet-text #4A4F4D; quiet-line #CFCFCB; focus #1A56B8;"
          "head-bg #FFFFFF; head-text #1A1A1A; foot-bg #2B2F36; foot-text #F2F2F2;"
          "g1 #1D4ED8; g2 #C2410C; g3 #BE123C; g4 #0B7A3F; g5 #6D28D9; g6 #0E7490"),
    _skin("dark", "ダーク", "目にやさしい紺黒。夜でもまぶしくない", "静か・落ち着き", "夜に使う方。まぶしさが苦手な方", "plain", True,
          "left soft cozy plain none pill card grid",
          "bg #0F1720; bg2 #162230; surface #1B2938; surface2 #243649; text #EAF1F8; muted #AEBDCC; line #34495F;"
          "accent #5AA9FF; on-accent #04182E; ato #7DBBFF; on-ato #04182E; mou #FFB26B; on-mou #2B1300;"
          "quiet-bg #1E2630; quiet-text #B7C0CA; quiet-line #38424E; focus #7DBBFF;"
          "head-bg #0B1219; head-text #EAF1F8; foot-bg #070C11; foot-text #C7D2DD;"
          "g1 #7DBBFF; g2 #FFA36B; g3 #FF8FA8; g4 #6FD59A; g5 #B9A0FF; g6 #5CD0E6;"
          "shadow 0 2px 10px rgba(0,0,0,.5)"),
    _skin("contrast", "ハイコントラスト", "黒地に白と黄。くっきり読める", "くっきり・強い", "弱視の方、文字をはっきり読みたい方", "plain", True,
          "left square cozy plain none boxed card list",
          "bg #000000; bg2 #141414; surface #0A0A0A; surface2 #1F1F1F; text #FFFFFF; muted #E0E0E0; line #FFFFFF;"
          "accent #FFE600; on-accent #000000; ato #FFE600; on-ato #000000; mou #FFFFFF; on-mou #000000;"
          "quiet-bg #1A1A1A; quiet-text #D9D9D9; quiet-line #8C8C8C; focus #FFE600;"
          "head-bg #000000; head-text #FFE600; foot-bg #000000; foot-text #FFFFFF;"
          "g1 #FFE600; g2 #FF9F43; g3 #FF7AA8; g4 #5CFF9A; g5 #C9A8FF; g6 #5CE1FF;"
          f"radius 6px; shadow none; size 18px; num-weight 900; bw 3px; font {FONT_UD}"),
    _skin("large", "大きな文字", "文字を大きく、濃く。ゆったり見える", "ゆったり・はっきり", "文字が小さいと読みにくい方、シニア世代", "plain", False,
          "left pill airy plain none pill card list",
          "bg #FFFDF7; bg2 #F3EFE3; surface #FFFFFF; surface2 #F1EEE4; text #111111; muted #3F3F3F; line #A8A59A;"
          "accent #0B3D91; on-accent #FFFFFF; ato #0B3D91; on-ato #FFFFFF; mou #8A2F00; on-mou #FFFFFF;"
          "quiet-bg #EDEDEA; quiet-text #3F4443; quiet-line #B5B5AF; focus #0B3D91;"
          "head-bg #FFFFFF; head-text #111111; foot-bg #1F2430; foot-text #FFFFFF;"
          "g1 #0B3D91; g2 #9A3A00; g3 #9E1033; g4 #0B6B36; g5 #5B21B6; g6 #0B5E73;"
          f"radius 14px; size 20px; num-weight 800; bw 2px; font {FONT_UD}; shadow 0 2px 6px rgba(0,0,0,.14)"),
    _skin("notebook", "手帳", "あたたかい紙に、付箋とテープ", "ぬくもり・手書き風", "毎日の記録を楽しみたい方。幅広い年代", "sticky", False,
          "left soft cozy plain paper tab ribbon masonry",
          "bg #FBF4E2; bg2 #F6EBCB; surface #FFFCF3; surface2 #F6EBCB; text #23302F; muted #4B5754; line #E3D5AE;"
          "accent #B23A07; on-accent #FFFFFF; ato #B23A07; on-ato #FFFFFF; mou #13585A; on-mou #FFFFFF;"
          "quiet-bg #ECE9E0; quiet-text #4F5A57; quiet-line #C9C6BA; focus #13585A;"
          "head-bg #FBF4E2; head-text #23302F; foot-bg #1E4B4A; foot-text #F6EFDC;"
          "g1 #8A5A00; g2 #B23A07; g3 #A3294A; g4 #2E6B3A; g5 #6B3F8A; g6 #13585A;"
          f"deco #D9A441; deco2 #13585A; radius 6px; shadow 3px 3px 0 rgba(120,90,30,.18); font {FONT_ROUND};"
          "bg-image repeating-linear-gradient(180deg,transparent 0,transparent 35px,#EBDDB6 35px,#EBDDB6 36px)"),
    _skin("pop", "ポップ", "鮮やかな青と色面。元気で楽しい", "元気・はっきり", "10代〜40代。にぎやかなのが好きな方", "panel", False,
          "band sticker cozy badge dots boxed card grid",
          "bg #EEF3FB; bg2 #E1EAF8; surface #FFFFFF; surface2 #E6EDF9; text #0F172A; muted #475569; line #CFD9EA;"
          "accent #1D4ED8; on-accent #FFFFFF; ato #1D4ED8; on-ato #FFFFFF; mou #C2410C; on-mou #FFFFFF;"
          "quiet-bg #E9EDF3; quiet-text #44506A; quiet-line #B9C3D4; focus #1D4ED8;"
          "head-bg #1D4ED8; head-text #FFFFFF; foot-bg #0B1B4A; foot-text #E8EEFF;"
          "g1 #1D4ED8; g2 #C2410C; g3 #BE123C; g4 #0B7A3F; g5 #6D28D9; g6 #0E7490;"
          "band-bg #FFD84D; band-text #0F172A; deco #1D4ED8; deco2 #FF4D8D; radius 16px; num-weight 900; bw 3px; shadow 0 2px 0 rgba(15,23,42,.06),0 8px 22px rgba(15,23,42,.10)"),
    _skin("ring", "すっきり", "白と淡い青。円のリングで日数を見せる", "軽い・さわやか", "アプリのような見た目が好きな方", "ring", False,
          "left pill airy plain none underline circle grid",
          "bg #F6F8FE; bg2 #E9EEFB; surface #FFFFFF; surface2 #EDF0FA; text #1D2540; muted #485272; line #E4E8F4;"
          "accent #3652D0; on-accent #FFFFFF; ato #1B5BA8; on-ato #FFFFFF; mou #A5432A; on-mou #FFFFFF;"
          "quiet-bg #EFF0F5; quiet-text #454C62; quiet-line #C9CDDA; focus #3652D0;"
          "head-bg #FFFFFF; head-text #1D2540; foot-bg #1D2540; foot-text #E8ECFA;"
          "g1 #2B3A8C; g2 #9A5B00; g3 #B0254F; g4 #1C6B3C; g5 #6240A8; g6 #10695E;"
          "radius 18px; num-weight 600; shadow 0 1px 2px rgba(44,60,120,.06),0 8px 28px rgba(44,60,120,.10);"
          "bg-image linear-gradient(180deg,#E3EDFF 0,#F6F8FE 340px)"),
    _skin("pastel-pink", "パステルピンク", "ほんのりピンクのやさしい色", "やさしい・かわいい", "かわいい雰囲気が好きな方。幅広い年代", "sticky", False,
          "center soft cozy plain stars pill chip masonry",
          "bg #FFF1F4; bg2 #FFE3EA; surface #FFFFFF; surface2 #FFE9EE; text #3A2330; muted #5A3A4A; line #F0C9D3;"
          "accent #B0285F; on-accent #FFFFFF; ato #B0285F; on-ato #FFFFFF; mou #6A3FA0; on-mou #FFFFFF;"
          "quiet-bg #F1ECED; quiet-text #5B5154; quiet-line #D9CDD1; focus #B0285F;"
          "head-bg #FFD9E3; head-text #3A2330; foot-bg #5A2A40; foot-text #FFEFF4;"
          "g1 #B0285F; g2 #B4531A; g3 #C0183F; g4 #1F7A4F; g5 #6A3FA0; g6 #17708A;"
          f"deco #F28DAA; deco2 #B79BE0; radius 20px; font {FONT_ROUND}; shadow 0 3px 10px rgba(176,40,95,.12);"
          "bg-image radial-gradient(circle,#FFD0DC 1.5px,transparent 2px)"),
    _skin("mint", "ミント", "すっきりした緑。気持ちが落ち着く", "さわやか・清潔", "すっきりした色が好きな方。幅広い年代", "plain", False,
          "band pill cozy plain leaves pill chip grid",
          "bg #EAF8F2; bg2 #D6F0E5; surface #FFFFFF; surface2 #E3F5EC; text #12302A; muted #2F5D50; line #BFE3D3;"
          "accent #0B6B55; on-accent #FFFFFF; ato #0B6B55; on-ato #FFFFFF; mou #A64B14; on-mou #FFFFFF;"
          "quiet-bg #E9EEEC; quiet-text #4A5753; quiet-line #CBD5D1; focus #0B6B55;"
          "head-bg #0B6B55; head-text #FFFFFF; foot-bg #0F3B31; foot-text #E2F6EE;"
          "g1 #1D5FB0; g2 #B4530F; g3 #B8284E; g4 #0B6B55; g5 #6B46B0; g6 #0E7490;"
          "deco #6CCBAA; deco2 #0B6B55; radius 14px; shadow 0 2px 8px rgba(11,107,85,.12)"),
    _skin("chic-navy", "シック紺と金", "濃い紺に金色。上品で大人っぽい", "上品・落ち着き", "30代以上。大人っぽい雰囲気が好きな方", "plain", True,
          "center outline cozy plain stars underline plain grid",
          "bg #0E1A2E; bg2 #14233D; surface #1E3254; surface2 #27406A; text #F3EEDD; muted #C6CCDA; line #3A5078;"
          "accent #D4A93A; on-accent #14203A; ato #E3BC5A; on-ato #14203A; mou #9FC1F0; on-mou #0E1A2E;"
          "quiet-bg #1C2638; quiet-text #BDC3CF; quiet-line #364258; focus #E3BC5A;"
          "head-bg #09121F; head-text #E3BC5A; foot-bg #060D18; foot-text #D9D4C3;"
          "g1 #E3BC5A; g2 #FF9F6B; g3 #FF8FA8; g4 #6FD59A; g5 #B9A0FF; g6 #5CC8E0;"
          f"deco #D4A93A; deco2 #9FC1F0; radius 8px; num-weight 700; font {FONT_SANS}; font-head {FONT_MINCHO}; shadow 0 4px 14px rgba(0,0,0,.45)"),
    _skin("monochrome", "モノクロ", "白と黒と灰色だけ。形でわかる", "硬質・すっきり", "色が気になる方。文字中心で見たい方", "plain", False,
          "left square compact mono grid boxed plain list",
          "bg #F2F2F2; bg2 #E6E6E6; surface #FFFFFF; surface2 #EEEEEE; text #111111; muted #4D4D4D; line #C8C8C8;"
          "accent #222222; on-accent #FFFFFF; ato #1A1A1A; on-ato #FFFFFF; mou #595959; on-mou #FFFFFF;"
          "quiet-bg #EDEDED; quiet-text #4D4D4D; quiet-line #CFCFCF; focus #000000;"
          "head-bg #111111; head-text #FFFFFF; foot-bg #1A1A1A; foot-text #E6E6E6;"
          "g1 #1A1A1A; g2 #4D4D4D; g3 #6B6B6B; g4 #333333; g5 #808080; g6 #5C5C5C;"
          f"deco #888888; deco2 #444444; radius 2px; num-weight 800; bw 1px; font {FONT_UD}; font-num {FONT_MONO}; shadow 0 1px 3px rgba(0,0,0,.14)"),
    _skin("wafuu", "和風", "藍と朱、生成り色。落ち着いた和の色", "和・端正", "和の雰囲気が好きな方。40代以上にも", "plain", False,
          "stripe soft cozy plain waves underline ribbon grid",
          "bg #F4EDDC; bg2 #EADFC6; surface #FBF7EA; surface2 #EFE6CF; text #1F2A38; muted #4A5361; line #D3C4A0;"
          "accent #1F3F6B; on-accent #FFFFFF; ato #1F3F6B; on-ato #FFFFFF; mou #B3261E; on-mou #FFFFFF;"
          "quiet-bg #E8E6DF; quiet-text #4C5258; quiet-line #CCC8BB; focus #1F3F6B;"
          "head-bg #1F3F6B; head-text #F4EDDC; foot-bg #232B3A; foot-text #EFE8D6;"
          "g1 #1F3F6B; g2 #B3261E; g3 #8E2F5C; g4 #2F6B3F; g5 #5B3E8A; g6 #7A5200;"
          f"deco #1F3F6B; deco2 #B3261E; radius 4px; num-weight 700; font {FONT_SANS}; font-head {FONT_MINCHO}; shadow 0 1px 3px rgba(31,42,56,.18)"),
    _skin("nordic", "北欧", "淡い灰色と木の色。すっきり静か", "素朴・静か", "シンプルで落ち着いた部屋が好きな方", "plain", False,
          "left underline cozy plain none underline circle masonry",
          "bg #F1F2F3; bg2 #E6E8EA; surface #FFFFFF; surface2 #EEF0F1; text #2A2F33; muted #565E64; line #D5D9DC;"
          "accent #7A5A3A; on-accent #FFFFFF; ato #3F6577; on-ato #FFFFFF; mou #8A5A2E; on-mou #FFFFFF;"
          "quiet-bg #EBECEC; quiet-text #50565B; quiet-line #D0D3D5; focus #3F6577;"
          "head-bg #FFFFFF; head-text #2A2F33; foot-bg #3B3F43; foot-text #ECEDEE;"
          "g1 #3F6577; g2 #A0522D; g3 #A23B52; g4 #3F7A55; g5 #6C5A9A; g6 #2F7A80;"
          "deco #A9B79A; deco2 #7A5A3A; radius 10px; num-weight 600; shadow 0 1px 3px rgba(42,47,51,.10)"),
    _skin("mediterranean", "地中海", "白い壁と青い海。明るく開放的", "明るい・さわやか", "明るい色が好きな方。幅広い年代", "panel", False,
          "band pill cozy plain waves tab ribbon grid",
          "bg #F4F9FD; bg2 #E1EFFA; surface #FFFFFF; surface2 #E8F2FB; text #0F2A4A; muted #3E5B7C; line #BBD3EA;"
          "accent #0D5CA8; on-accent #FFFFFF; ato #0D5CA8; on-ato #FFFFFF; mou #B5481A; on-mou #FFFFFF;"
          "quiet-bg #EAEEF2; quiet-text #4A5663; quiet-line #CBD3DB; focus #0D5CA8;"
          "head-bg #0D5CA8; head-text #FFFFFF; foot-bg #0A2E55; foot-text #E6F1FB;"
          "g1 #0D5CA8; g2 #B5481A; g3 #B02A55; g4 #1B7A52; g5 #5E4BA6; g6 #0F7C8C;"
          "band-bg #DCEEFA; band-text #0F2A4A; deco #5BB4E8; deco2 #0D5CA8; radius 14px; shadow 0 3px 12px rgba(13,92,168,.14)"),
    _skin("tropical", "南国", "黄色と深い緑。日ざしのような明るさ", "元気・明るい", "気分を上げたい方。幅広い年代", "panel", False,
          "band pill cozy badge leaves pill circle masonry",
          "bg #FFF9E8; bg2 #FFEFC2; surface #FFFFFF; surface2 #FFF1CC; text #1E2B24; muted #3A4A40; line #F0DC9C;"
          "accent #00796B; on-accent #FFFFFF; ato #00796B; on-ato #FFFFFF; mou #C6321A; on-mou #FFFFFF;"
          "quiet-bg #EFEDE4; quiet-text #55564C; quiet-line #D5D2C2; focus #00796B;"
          "head-bg #FFC933; head-text #1E2B24; foot-bg #0B4F46; foot-text #FFF4D6;"
          "g1 #00796B; g2 #C25100; g3 #C2185B; g4 #2E7D32; g5 #7B3FBF; g6 #0277BD;"
          f"band-bg #FFEFB0; band-text #1E2B24; deco #2E9E5B; deco2 #F28C1B; radius 18px; num-weight 900; font {FONT_ROUND}; shadow 0 3px 10px rgba(180,120,0,.18)"),
    _skin("kids", "こども", "まるくて大きい。にぎやかな色", "にぎやか・まるい", "こども、親子で使う方。小学生〜", "panel", False,
          "center sticker cozy badge confetti pill circle grid",
          "bg #FFF8E1; bg2 #FFEDB8; surface #FFFFFF; surface2 #FFF3C8; text #2A2340; muted #4A4468; line #F0DC9C;"
          "accent #C2255C; on-accent #FFFFFF; ato #1971C2; on-ato #FFFFFF; mou #C2410C; on-mou #FFFFFF;"
          "quiet-bg #EEECE6; quiet-text #55524D; quiet-line #D6D3CA; focus #1971C2;"
          "head-bg #FFD43B; head-text #2A2340; foot-bg #3B2F6B; foot-text #FFF6D6;"
          "g1 #1971C2; g2 #C2410C; g3 #C2255C; g4 #2B8A3E; g5 #7048E8; g6 #0C8599;"
          f"deco #FF8FB1; deco2 #4DABF7; radius 22px; size 17px; num-weight 900; bw 2px; font {FONT_ROUND}; shadow 0 3px 0 rgba(42,35,64,.18)"),
    _skin("retro", "レトロ", "昭和の喫茶店。茶色とえんじ色", "なつかしい・渋い", "50代以上。なつかしい雰囲気が好きな方", "sticky", False,
          "band square cozy mono stripes tab ribbon list",
          "bg #F3E6CC; bg2 #E4CFA6; surface #FCF4E2; surface2 #EEDDB8; text #3A2214; muted #4A3324; line #CDB48A;"
          "accent #8C2F1B; on-accent #FFFFFF; ato #1F5F5B; on-ato #FFFFFF; mou #8C2F1B; on-mou #FFFFFF;"
          "quiet-bg #E6DFD0; quiet-text #5A4F44; quiet-line #CBBFA8; focus #1F5F5B;"
          "head-bg #5B2A1A; head-text #F7E8C8; foot-bg #3A1F14; foot-text #EBD9B5;"
          "g1 #1F5F5B; g2 #A0431C; g3 #9C2A4A; g4 #4A6B1F; g5 #6B3F7A; g6 #1F5A86;"
          f"band-bg #F7E8C8; band-text #3A2214; deco #B8860B; deco2 #8C2F1B; radius 4px; num-weight 800; bw 2px; font {FONT_SANS}; font-head {FONT_MINCHO}; font-num {FONT_MONO}; shadow 3px 3px 0 rgba(58,34,20,.18)"),
    _skin("neon", "ネオン", "暗い夜にピンクと水色の光", "未来的・派手", "10代〜30代。派手な色が好きな方", "ring", True,
          "left outline cozy outline grid boxed chip grid",
          "bg #0B0A14; bg2 #14122A; surface #181533; surface2 #231F47; text #F5F3FF; muted #B9B4DD; line #3C3670;"
          "accent #FF4FD8; on-accent #1A0016; ato #3DF2FF; on-ato #00161A; mou #FFE14D; on-mou #1A1500;"
          "quiet-bg #1D1C2C; quiet-text #B5B3C8; quiet-line #3A3950; focus #3DF2FF;"
          "head-bg #07060F; head-text #3DF2FF; foot-bg #050409; foot-text #D8D4F5;"
          "g1 #3DF2FF; g2 #FFB347; g3 #FF6FB5; g4 #6BFF9E; g5 #B794FF; g6 #7FB5FF;"
          "deco #FF4FD8; deco2 #3DF2FF; radius 14px; num-weight 800; bw 1px; shadow 0 0 10px rgba(61,242,255,.16);"
          "bg-image radial-gradient(circle at 20% 0%,rgba(255,79,216,.12),transparent 40%)"),
    _skin("forest", "深緑", "深い森の緑。しっとり落ち着く", "しっとり・自然", "落ち着いた暗めの色が好きな方", "plain", True,
          "band soft cozy shadow leaves tab card masonry",
          "bg #0F1F18; bg2 #15291F; surface #223B2D; surface2 #2C4A39; text #EDF3E8; muted #C2D3C2; line #3C5A47;"
          "accent #A8D672; on-accent #10200A; ato #A8D672; on-ato #10200A; mou #F0B96B; on-mou #2A1A00;"
          "quiet-bg #222B26; quiet-text #B7C1BB; quiet-line #3A453F; focus #A8D672;"
          "head-bg #0A1712; head-text #D9EBC8; foot-bg #07110C; foot-text #C9D8C6;"
          "g1 #8CC8FF; g2 #F0A56B; g3 #F28DA6; g4 #A8D672; g5 #C3A8F0; g6 #6FD3C4;"
          "deco #A8D672; deco2 #6FD3C4; radius 12px; shadow 0 3px 12px rgba(0,0,0,.45)"),
    _skin("sunset", "夕焼け", "オレンジから紫へ。あたたかい夕方", "あたたかい・ロマンチック", "やわらかい暖色が好きな方", "panel", False,
          "band pill cozy shadow sunburst pill chip grid",
          "bg #FFF6EE; bg2 #FFE0CC; surface #FFFFFF; surface2 #FFE9DA; text #3A1F1A; muted #5E3A32; line #F0CDB8;"
          "accent #B3361A; on-accent #FFFFFF; ato #B3361A; on-ato #FFFFFF; mou #5B3A8E; on-mou #FFFFFF;"
          "quiet-bg #F0EAE6; quiet-text #5A4C48; quiet-line #D8CCC5; focus #5B3A8E;"
          "head-bg #FF8A5B; head-text #3A1F1A; foot-bg #4A2340; foot-text #FFE9DA;"
          "g1 #5B3A8E; g2 #B3361A; g3 #B02A5E; g4 #2F7A4F; g5 #7A3FB0; g6 #1E6E8C;"
          "band-bg #FFE0CA; band-text #3A1F1A; deco #FF8A5B; deco2 #8E5BC8; radius 16px; shadow 0 2px 8px rgba(179,54,26,.10);"
          "bg-image linear-gradient(180deg,#FFE6D3 0,#FFF6EE 220px)"),
    _skin("cb-safe", "色覚サポート", "青とオレンジ中心。色だけに頼らない", "くっきり・実用的", "色の見分けが苦手な方。どなたでも", "plain", False,
          "left outline cozy plain none boxed card grid",
          "bg #F7F9FB; bg2 #E9EEF3; surface #FFFFFF; surface2 #EDF1F5; text #14202B; muted #44525F; line #C8D1DA;"
          "accent #0B5CAD; on-accent #FFFFFF; ato #0B5CAD; on-ato #FFFFFF; mou #B35900; on-mou #FFFFFF;"
          "quiet-bg #EEF0F2; quiet-text #4B545D; quiet-line #CDD2D7; focus #0B5CAD;"
          "head-bg #0B5CAD; head-text #FFFFFF; foot-bg #14202B; foot-text #E7EDF3;"
          "g1 #0072B2; g2 #B35900; g3 #8C3B73; g4 #007A5E; g5 #6B6B6B; g6 #8F6B00;"
          f"radius 12px; size 17px; num-weight 800; bw 2px; font {FONT_UD}"),
    # ---- seasonal skins (after the normal ones; `season` is what tells them apart) ----
    _skin("halloween", "ハロウィン", "オレンジと紫。かぼちゃとコウモリ", "かわいい・にぎやか", "ハロウィンを楽しみたい方。10月〜11月初め", "panel", False,
          "band sticker cozy shadow confetti pill circle grid",
          "bg #FFF3E4; bg2 #FFE2C2; surface #FFFFFF; surface2 #FFEBD6; text #231433; muted #54406B; line #F0C79B;"
          "accent #5B2C8F; on-accent #FFFFFF; ato #C2410C; on-ato #FFFFFF; mou #5B2C8F; on-mou #FFFFFF;"
          "quiet-bg #EEEBF0; quiet-text #4E4858; quiet-line #CFC9D6; focus #5B2C8F;"
          "head-bg #2A1640; head-text #FFB347; foot-bg #1B0F2B; foot-text #FFE9CF;"
          "g1 #6B2FA8; g2 #C2410C; g3 #B3245C; g4 #3F7D20; g5 #7A3FBF; g6 #0E7490;"
          f"deco #F28C1B; deco2 #7B3FC4; radius 18px; num-weight 900; bw 3px; font {FONT_ROUND}; shadow 0 3px 0 rgba(42,22,64,.18)",
          season=_season("10-10", "11-02", "ハロウィン")),
    _skin("christmas", "クリスマス", "赤と緑と金。ツリーとプレゼント", "わくわく・あたたかい", "クリスマスの前後に。12月", "panel", False,
          "band pill cozy badge stars tab ribbon grid",
          "bg #FBF7F0; bg2 #F3EAD8; surface #FFFFFF; surface2 #F6EFE0; text #1F2A24; muted #4A5A50; line #E0D6C4;"
          "accent #B3122B; on-accent #FFFFFF; ato #B3122B; on-ato #FFFFFF; mou #1E6B3C; on-mou #FFFFFF;"
          "quiet-bg #EDEEEA; quiet-text #4A524E; quiet-line #CDD1CB; focus #1E6B3C;"
          "head-bg #165A38; head-text #FFF4D6; foot-bg #0F3A24; foot-text #F4EBD2;"
          "g1 #1E6B3C; g2 #B3122B; g3 #8E3B96; g4 #1E5FA8; g5 #8A5A00; g6 #0E7490;"
          "band-bg #E4F0E6; band-text #14402A; deco #C99A2E; deco2 #B3122B; radius 14px; num-weight 800; shadow 0 3px 10px rgba(30,60,40,.15)",
          season=_season("12-01", "12-26", "クリスマス")),
    _skin("newyear", "お正月", "朱と金と松。おめでたい新年", "おめでたい・晴れやか", "年末年始に。12月末〜1月10日ごろ", "plain", False,
          "center square airy plain sunburst underline plain grid",
          "bg #FFF8EC; bg2 #F8EBD0; surface #FFFEFA; surface2 #F8EDD6; text #2A1A12; muted #5C4636; line #EBD7B0;"
          "accent #B3171B; on-accent #FFFFFF; ato #B3171B; on-ato #FFFFFF; mou #1F4E3D; on-mou #FFFFFF;"
          "quiet-bg #EEEBE6; quiet-text #52493F; quiet-line #D3CCBF; focus #1F4E3D;"
          "head-bg #B3171B; head-text #FFF3D6; foot-bg #3A0F10; foot-text #FBE8C8;"
          "g1 #1F4E3D; g2 #B3171B; g3 #8E2F5C; g4 #2F6B3F; g5 #5B3E8A; g6 #7A5200;"
          f"deco #C9A227; deco2 #B3171B; radius 6px; num-weight 700; font {FONT_MINCHO}; shadow 0 2px 6px rgba(120,60,20,.16)",
          season=_season("12-27", "01-10", "お正月")),
    _skin("valentine", "バレンタイン", "ピンクとチョコ。ハートがいっぱい", "あまい・かわいい", "バレンタインの前後に。2月", "plain", False,
          "center soft cozy shadow dots pill chip masonry",
          "bg #FFF2F4; bg2 #FFE0E6; surface #FFFFFF; surface2 #FFE8EC; text #3B1D26; muted #6B4452; line #F2C6D0;"
          "accent #A8123E; on-accent #FFFFFF; ato #A8123E; on-ato #FFFFFF; mou #6F3B24; on-mou #FFFFFF;"
          "quiet-bg #F0EBEC; quiet-text #594D51; quiet-line #D8CDD1; focus #A8123E;"
          "head-bg #FFD3DC; head-text #3B1D26; foot-bg #4A1A2A; foot-text #FFE8EE;"
          "g1 #A8123E; g2 #B4531A; g3 #8E2F5C; g4 #1F7A4F; g5 #6A3FA0; g6 #17708A;"
          f"deco #E84A6F; deco2 #6F3B24; radius 20px; font {FONT_ROUND}; shadow 0 3px 10px rgba(168,18,62,.14)",
          season=_season("02-01", "02-14", "バレンタイン")),
    _skin("sakura", "さくら", "淡いピンクの花びら。春の入り口", "やさしい・春らしい", "お花見や入学・新生活のころに。3月下旬〜4月", "plain", False,
          "center soft airy plain confetti pill chip grid",
          "bg #FFF6F8; bg2 #FDE6EC; surface #FFFFFF; surface2 #FDEEF2; text #33262C; muted #61494F; line #F3D5DB;"
          "accent #B8325E; on-accent #FFFFFF; ato #B8325E; on-ato #FFFFFF; mou #2F6B3C; on-mou #FFFFFF;"
          "quiet-bg #F1EDEE; quiet-text #564D50; quiet-line #D9D0D3; focus #B8325E;"
          "head-bg #FFFFFF; head-text #33262C; foot-bg #4A2A36; foot-text #FFEDF2;"
          "g1 #B8325E; g2 #B4531A; g3 #8E2F5C; g4 #2F6B3C; g5 #6A3FA0; g6 #17708A;"
          "deco #F4A3BA; deco2 #7DBE86; radius 18px; shadow 0 3px 12px rgba(184,50,94,.12);"
          "bg-image linear-gradient(180deg,#FFE4EC 0,#FFF6F8 320px)",
          season=_season("03-20", "04-15", "さくら")),
    _skin("summer", "夏まつり", "ちょうちんと花火。夏の夜", "にぎやか・すずしい", "夏休みやお祭りのころに。7月〜8月", "panel", False,
          "band sticker cozy badge waves pill chip grid",
          "bg #F0FAFF; bg2 #D9F0FA; surface #FFFFFF; surface2 #E3F4FB; text #0F2740; muted #38546E; line #BFE0EF;"
          "accent #0B4F9C; on-accent #FFFFFF; ato #C8281E; on-ato #FFFFFF; mou #0B4F9C; on-mou #FFFFFF;"
          "quiet-bg #ECEFF2; quiet-text #4A5560; quiet-line #CCD3D9; focus #0B4F9C;"
          "head-bg #0F3D7A; head-text #FFFFFF; foot-bg #0A2547; foot-text #E4F1FB;"
          "g1 #0B4F9C; g2 #C8281E; g3 #B02A55; g4 #1B7A52; g5 #5E4BA6; g6 #0F7C8C;"
          "band-bg #D6EFFA; band-text #0F2740; deco #3DA9DC; deco2 #E8402E; radius 16px; num-weight 900; bw 3px; shadow 0 3px 0 rgba(15,61,122,.16)",
          season=_season("07-01", "08-31", "夏まつり")),
    _skin("tsukimi", "お月見", "満月とススキ。秋の夜", "しっとり・風流", "お月見のころに。9月中旬〜10月初め", "plain", False,
          "center outline airy plain stars underline circle grid",
          "bg #FBF6E4; bg2 #F3EAC8; surface #FFFEF8; surface2 #F5EDD2; text #1B2A44; muted #45526B; line #E3D7AC;"
          "accent #1F3A5F; on-accent #FFFFFF; ato #8A5300; on-ato #FFFFFF; mou #1F3A5F; on-mou #FFFFFF;"
          "quiet-bg #ECEBE6; quiet-text #4D4F52; quiet-line #CFCDC4; focus #1F3A5F;"
          "head-bg #1F3A5F; head-text #FFE9A8; foot-bg #14253F; foot-text #F3E9C6;"
          "g1 #1F3A5F; g2 #8A5300; g3 #8E2F5C; g4 #2F6B3F; g5 #5B3E8A; g6 #0E6E7A;"
          f"deco #E8C45A; deco2 #1F3A5F; radius 12px; num-weight 600; font {FONT_MINCHO}; shadow 0 2px 8px rgba(27,42,68,.14)",
          season=_season("09-10", "10-05", "お月見")),
]


def ids() -> list[str]:
    return [s["id"] for s in SKINS]


def get(skin_id: str) -> dict:
    for s in SKINS:
        if s["id"] == skin_id:
            return s
    raise KeyError(skin_id)


def is_seasonal(skin: dict) -> bool:
    return bool(skin.get("season"))


def normal_skins() -> list[dict]:
    return [s for s in SKINS if not is_seasonal(s)]


def seasonal_skins() -> list[dict]:
    return [s for s in SKINS if is_seasonal(s)]


def in_season(skin: dict, today: date) -> bool:
    """True when `today` is inside the skin's period (inclusive; a period such as 12-27..01-10 crosses New Year)."""
    s = skin.get("season")
    if not s:
        return False
    md = f"{today.month:02d}-{today.day:02d}"
    a, b = s["from"], s["to"]
    return a <= md <= b if a <= b else (md >= a or md <= b)


def current_seasons(today: date) -> list[dict]:
    return [s for s in seasonal_skins() if in_season(s, today)]


def attr_problems(skin: dict) -> list[str]:
    """What is wrong with a skin's `attrs` (empty = fine): every key of ATTR_VALUES present, only known values, no stray keys."""
    sid = skin.get("id", "?")
    a = skin.get("attrs")
    if not isinstance(a, dict):
        return [f"{sid}: attrs is missing"]
    out = []
    for k, vals in ATTR_VALUES.items():
        if k not in a:
            out.append(f"{sid}: attrs.{k} is missing")
        elif a[k] not in vals:
            out.append(f"{sid}: attrs.{k}={a[k]!r} is not one of {'/'.join(vals)}")
    out += [f"{sid}: attrs.{k} is not a known key" for k in a if k not in ATTR_VALUES]
    return out


def _decls(values: dict) -> str:
    return ";".join(f"--{k}:{values[k]}" for k in VARS if k in values)


def css() -> str:
    """All skin blocks.  `basic` is also the default (:root).  There is no prefers-color-scheme rule: the page is dark only when a dark skin is chosen."""
    out = []
    for s in SKINS:
        decl = _decls(s["vars"])
        if s["id"] == "basic":
            out.append(":root{" + decl + "}")
        out.append(':root[data-skin="' + s["id"] + '"]{' + decl + "}")
    return "\n".join(out) + "\n"
