"""atomou: the colour skins (着せ替え).

The site CSS reads only the custom properties listed in VARS.  css() returns one `:root[data-skin="<id>"]{...}` block per skin; the first skin
(`basic`) is also the default: its light values are written to `:root{...}` and its dark values are applied automatically through
`@media (prefers-color-scheme: dark){:root:not([data-skin]){...}}`.

Each skin also names a `card` kind (plain / sticky / panel / ring).  That is meta information for the page template (data-card), not a CSS variable.
--bg-image is a CSS gradient (or none) laid over --bg; the page decides background-size.  System fonts only, no external fonts or images.
Contrast of every pairing is checked by tests/test_atomou_skins.py (WCAG ratios).
"""
from __future__ import annotations

VARS = (
    "bg", "bg2", "surface", "surface2", "text", "muted", "line", "accent", "on-accent", "ato", "on-ato", "mou", "on-mou",
    "quiet-bg", "quiet-text", "quiet-line", "focus", "head-bg", "head-text", "foot-bg", "foot-text",
    "g1", "g2", "g3", "g4", "g5", "g6", "radius", "shadow", "font", "size", "num-weight", "bg-image",
)
CARDS = ("plain", "sticky", "panel", "ring")

FONT_SANS = '"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic UI","BIZ UDPGothic","Yu Gothic","Meiryo","Noto Sans JP",system-ui,-apple-system,"Segoe UI",sans-serif'
FONT_ROUND = '"Hiragino Maru Gothic ProN","BIZ UDPGothic","Yu Gothic UI","Hiragino Sans","Meiryo",system-ui,sans-serif'
FONT_UD = '"BIZ UDPGothic","BIZ UDGothic","Hiragino Sans","Yu Gothic UI","Meiryo","Noto Sans JP",system-ui,sans-serif'
FONT_MINCHO = '"Hiragino Mincho ProN","Yu Mincho","YuMincho","Noto Serif JP","MS PMincho",serif'

DEFAULTS = {
    "radius": "12px",
    "shadow": "0 2px 8px rgba(0,0,0,.10)",
    "font": FONT_SANS,
    "size": "16px",
    "num-weight": "700",
    "bg-image": "none",
}


def _v(spec: str) -> dict:
    """'bg #FFF; text #000; ...' -> {'bg': '#FFF', ...}; the style variables not given take DEFAULTS."""
    out = dict(DEFAULTS)
    for part in spec.split(";"):
        part = part.strip()
        if part:
            k, val = part.split(None, 1)
            out[k] = val.strip()
    return out


def _skin(id, name, desc, mood, audience, card, dark, spec, **extra):
    d = {"id": id, "name": name, "desc": desc, "mood": mood, "audience": audience, "card": card, "dark": dark, "vars": _v(spec)}
    d.update(extra)
    return d


_BASIC_DARK = _v(
    "bg #121316; bg2 #1A1C20; surface #1E2024; surface2 #292C32; text #F2F2F2; muted #B4B8C0; line #3A3D44;"
    "accent #7FB0FF; on-accent #0A1A33; ato #8DB8FF; on-ato #0A1A33; mou #FFB073; on-mou #2B1200;"
    "quiet-bg #24262A; quiet-text #B9BDBF; quiet-line #3C3F42; focus #8DB8FF;"
    "head-bg #17181B; head-text #F2F2F2; foot-bg #0C0D0F; foot-text #D6D8DC;"
    "g1 #8DB8FF; g2 #FFA066; g3 #FF8FA8; g4 #6FD59A; g5 #B9A0FF; g6 #5CD0E6;"
    "shadow 0 2px 8px rgba(0,0,0,.45)"
)

SKINS = [
    _skin("basic", "ベーシック", "いちばんシンプル。OSのダークにも対応", "中立・すっきり・見やすい", "どなたでも。迷ったらこれ", "plain", False,
          "bg #F7F7F5; bg2 #EEEEEA; surface #FFFFFF; surface2 #F0F0EC; text #1A1A1A; muted #555555; line #D4D4CE;"
          "accent #1A56B8; on-accent #FFFFFF; ato #1A56B8; on-ato #FFFFFF; mou #A8420A; on-mou #FFFFFF;"
          "quiet-bg #EDEDEB; quiet-text #4A4F4D; quiet-line #CFCFCB; focus #1A56B8;"
          "head-bg #FFFFFF; head-text #1A1A1A; foot-bg #2B2F36; foot-text #F2F2F2;"
          "g1 #1D4ED8; g2 #C2410C; g3 #BE123C; g4 #0B7A3F; g5 #6D28D9; g6 #0E7490",
          dark_vars=_BASIC_DARK),
    _skin("dark", "ダーク", "目にやさしい紺黒。夜でもまぶしくない", "静か・落ち着き", "夜に使う方。まぶしさが苦手な方", "plain", True,
          "bg #0F1720; bg2 #162230; surface #1B2938; surface2 #243649; text #EAF1F8; muted #AEBDCC; line #34495F;"
          "accent #5AA9FF; on-accent #04182E; ato #7DBBFF; on-ato #04182E; mou #FFB26B; on-mou #2B1300;"
          "quiet-bg #1E2630; quiet-text #B7C0CA; quiet-line #38424E; focus #7DBBFF;"
          "head-bg #0B1219; head-text #EAF1F8; foot-bg #070C11; foot-text #C7D2DD;"
          "g1 #7DBBFF; g2 #FFA36B; g3 #FF8FA8; g4 #6FD59A; g5 #B9A0FF; g6 #5CD0E6;"
          "shadow 0 2px 10px rgba(0,0,0,.5)"),
    _skin("contrast", "ハイコントラスト", "黒地に白と黄。くっきり読める", "くっきり・強い", "弱視の方、文字をはっきり読みたい方", "plain", True,
          "bg #000000; bg2 #141414; surface #0A0A0A; surface2 #1F1F1F; text #FFFFFF; muted #E0E0E0; line #FFFFFF;"
          "accent #FFE600; on-accent #000000; ato #FFE600; on-ato #000000; mou #FFFFFF; on-mou #000000;"
          "quiet-bg #1A1A1A; quiet-text #D9D9D9; quiet-line #8C8C8C; focus #FFE600;"
          "head-bg #000000; head-text #FFE600; foot-bg #000000; foot-text #FFFFFF;"
          "g1 #FFE600; g2 #FF9F43; g3 #FF7AA8; g4 #5CFF9A; g5 #C9A8FF; g6 #5CE1FF;"
          f"radius 6px; shadow none; size 18px; num-weight 900; font {FONT_UD}"),
    _skin("large", "大きな文字", "文字を大きく、濃く。ゆったり見える", "ゆったり・はっきり", "文字が小さいと読みにくい方、シニア世代", "plain", False,
          "bg #FFFDF7; bg2 #F3EFE3; surface #FFFFFF; surface2 #F1EEE4; text #111111; muted #3F3F3F; line #A8A59A;"
          "accent #0B3D91; on-accent #FFFFFF; ato #0B3D91; on-ato #FFFFFF; mou #8A2F00; on-mou #FFFFFF;"
          "quiet-bg #EDEDEA; quiet-text #3F4443; quiet-line #B5B5AF; focus #0B3D91;"
          "head-bg #FFFFFF; head-text #111111; foot-bg #1F2430; foot-text #FFFFFF;"
          "g1 #0B3D91; g2 #9A3A00; g3 #9E1033; g4 #0B6B36; g5 #5B21B6; g6 #0B5E73;"
          f"radius 14px; size 20px; num-weight 800; font {FONT_UD}; shadow 0 2px 6px rgba(0,0,0,.14)"),
    _skin("notebook", "手帳", "あたたかい紙に、付箋とテープ", "ぬくもり・手書き風", "毎日の記録を楽しみたい方。幅広い年代", "sticky", False,
          "bg #FBF4E2; bg2 #F6EBCB; surface #FFFCF3; surface2 #F6EBCB; text #23302F; muted #4B5754; line #E3D5AE;"
          "accent #B23A07; on-accent #FFFFFF; ato #B23A07; on-ato #FFFFFF; mou #13585A; on-mou #FFFFFF;"
          "quiet-bg #ECE9E0; quiet-text #4F5A57; quiet-line #C9C6BA; focus #13585A;"
          "head-bg #FBF4E2; head-text #23302F; foot-bg #1E4B4A; foot-text #F6EFDC;"
          "g1 #8A5A00; g2 #B23A07; g3 #A3294A; g4 #2E6B3A; g5 #6B3F8A; g6 #13585A;"
          f"radius 6px; shadow 3px 3px 0 rgba(120,90,30,.18); font {FONT_ROUND};"
          "bg-image radial-gradient(circle,#E4D6B0 1.2px,transparent 1.6px)"),
    _skin("pop", "ポップ", "鮮やかな青と色面。元気で楽しい", "元気・はっきり", "10代〜40代。にぎやかなのが好きな方", "panel", False,
          "bg #EEF3FB; bg2 #E1EAF8; surface #FFFFFF; surface2 #E6EDF9; text #0F172A; muted #475569; line #CFD9EA;"
          "accent #1D4ED8; on-accent #FFFFFF; ato #1D4ED8; on-ato #FFFFFF; mou #C2410C; on-mou #FFFFFF;"
          "quiet-bg #E9EDF3; quiet-text #44506A; quiet-line #B9C3D4; focus #1D4ED8;"
          "head-bg #1D4ED8; head-text #FFFFFF; foot-bg #0B1B4A; foot-text #E8EEFF;"
          "g1 #1D4ED8; g2 #C2410C; g3 #BE123C; g4 #0B7A3F; g5 #6D28D9; g6 #0E7490;"
          "radius 16px; num-weight 900; shadow 0 2px 0 rgba(15,23,42,.06),0 8px 22px rgba(15,23,42,.10)"),
    _skin("ring", "すっきり", "白と淡い青。円のリングで日数を見せる", "軽い・さわやか", "アプリのような見た目が好きな方", "ring", False,
          "bg #F6F8FE; bg2 #E9EEFB; surface #FFFFFF; surface2 #EDF0FA; text #1D2540; muted #485272; line #E4E8F4;"
          "accent #3652D0; on-accent #FFFFFF; ato #1B5BA8; on-ato #FFFFFF; mou #A5432A; on-mou #FFFFFF;"
          "quiet-bg #EFF0F5; quiet-text #454C62; quiet-line #C9CDDA; focus #3652D0;"
          "head-bg #FFFFFF; head-text #1D2540; foot-bg #1D2540; foot-text #E8ECFA;"
          "g1 #2B3A8C; g2 #9A5B00; g3 #B0254F; g4 #1C6B3C; g5 #6240A8; g6 #10695E;"
          "radius 18px; num-weight 600; shadow 0 1px 2px rgba(44,60,120,.06),0 8px 28px rgba(44,60,120,.10);"
          "bg-image linear-gradient(180deg,#E3EDFF 0,#F6F8FE 340px)"),
    _skin("pastel-pink", "パステルピンク", "ほんのりピンクのやさしい色", "やさしい・かわいい", "かわいい雰囲気が好きな方。幅広い年代", "sticky", False,
          "bg #FFF1F4; bg2 #FFE3EA; surface #FFFFFF; surface2 #FFE9EE; text #3A2330; muted #6B4A5A; line #F0C9D3;"
          "accent #B0285F; on-accent #FFFFFF; ato #B0285F; on-ato #FFFFFF; mou #6A3FA0; on-mou #FFFFFF;"
          "quiet-bg #F1ECED; quiet-text #5B5154; quiet-line #D9CDD1; focus #B0285F;"
          "head-bg #FFD9E3; head-text #3A2330; foot-bg #5A2A40; foot-text #FFEFF4;"
          "g1 #B0285F; g2 #B4531A; g3 #C0183F; g4 #1F7A4F; g5 #6A3FA0; g6 #17708A;"
          f"radius 20px; font {FONT_ROUND}; shadow 0 3px 10px rgba(176,40,95,.12);"
          "bg-image radial-gradient(circle,#FFD0DC 1.5px,transparent 2px)"),
    _skin("mint", "ミント", "すっきりした緑。気持ちが落ち着く", "さわやか・清潔", "すっきりした色が好きな方。幅広い年代", "plain", False,
          "bg #EAF8F2; bg2 #D6F0E5; surface #FFFFFF; surface2 #E3F5EC; text #12302A; muted #2F5D50; line #BFE3D3;"
          "accent #0B6B55; on-accent #FFFFFF; ato #0B6B55; on-ato #FFFFFF; mou #A64B14; on-mou #FFFFFF;"
          "quiet-bg #E9EEEC; quiet-text #4A5753; quiet-line #CBD5D1; focus #0B6B55;"
          "head-bg #0B6B55; head-text #FFFFFF; foot-bg #0F3B31; foot-text #E2F6EE;"
          "g1 #1D5FB0; g2 #B4530F; g3 #B8284E; g4 #0B6B55; g5 #6B46B0; g6 #0E7490;"
          "radius 14px; shadow 0 2px 8px rgba(11,107,85,.12)"),
    _skin("chic-navy", "シック紺と金", "濃い紺に金色。上品で大人っぽい", "上品・落ち着き", "30代以上。大人っぽい雰囲気が好きな方", "plain", True,
          "bg #0E1A2E; bg2 #14233D; surface #182A47; surface2 #213659; text #F3EEDD; muted #BFC6D6; line #33496E;"
          "accent #D4A93A; on-accent #14203A; ato #E3BC5A; on-ato #14203A; mou #9FC1F0; on-mou #0E1A2E;"
          "quiet-bg #1C2638; quiet-text #BDC3CF; quiet-line #364258; focus #E3BC5A;"
          "head-bg #09121F; head-text #E3BC5A; foot-bg #060D18; foot-text #D9D4C3;"
          "g1 #E3BC5A; g2 #FF9F6B; g3 #FF8FA8; g4 #6FD59A; g5 #B9A0FF; g6 #5CC8E0;"
          f"radius 8px; num-weight 600; font {FONT_MINCHO}; shadow 0 4px 14px rgba(0,0,0,.45)"),
    _skin("monochrome", "モノクロ", "白と黒と灰色だけ。形でわかる", "硬質・すっきり", "色が気になる方。文字中心で見たい方", "plain", False,
          "bg #F2F2F2; bg2 #E6E6E6; surface #FFFFFF; surface2 #EEEEEE; text #111111; muted #4D4D4D; line #C8C8C8;"
          "accent #222222; on-accent #FFFFFF; ato #1A1A1A; on-ato #FFFFFF; mou #595959; on-mou #FFFFFF;"
          "quiet-bg #EDEDED; quiet-text #4D4D4D; quiet-line #CFCFCF; focus #000000;"
          "head-bg #111111; head-text #FFFFFF; foot-bg #1A1A1A; foot-text #E6E6E6;"
          "g1 #1A1A1A; g2 #4D4D4D; g3 #6B6B6B; g4 #333333; g5 #808080; g6 #5C5C5C;"
          f"radius 2px; num-weight 800; font {FONT_UD}; shadow none"),
    _skin("wafuu", "和風", "藍と朱、生成り色。落ち着いた和の色", "和・端正", "和の雰囲気が好きな方。40代以上にも", "plain", False,
          "bg #F4EDDC; bg2 #EADFC6; surface #FBF7EA; surface2 #EFE6CF; text #1F2A38; muted #4A5361; line #D3C4A0;"
          "accent #1F3F6B; on-accent #FFFFFF; ato #1F3F6B; on-ato #FFFFFF; mou #B3261E; on-mou #FFFFFF;"
          "quiet-bg #E8E6DF; quiet-text #4C5258; quiet-line #CCC8BB; focus #1F3F6B;"
          "head-bg #1F3F6B; head-text #F4EDDC; foot-bg #232B3A; foot-text #EFE8D6;"
          "g1 #1F3F6B; g2 #B3261E; g3 #8E2F5C; g4 #2F6B3F; g5 #5B3E8A; g6 #7A5200;"
          f"radius 4px; num-weight 600; font {FONT_MINCHO}; shadow 0 1px 3px rgba(31,42,56,.18);"
          "bg-image repeating-linear-gradient(90deg,rgba(31,63,107,.05) 0,rgba(31,63,107,.05) 1px,transparent 1px,transparent 26px)"),
    _skin("nordic", "北欧", "淡い灰色と木の色。すっきり静か", "素朴・静か", "シンプルで落ち着いた部屋が好きな方", "plain", False,
          "bg #F1F2F3; bg2 #E6E8EA; surface #FFFFFF; surface2 #EEF0F1; text #2A2F33; muted #565E64; line #D5D9DC;"
          "accent #7A5A3A; on-accent #FFFFFF; ato #3F6577; on-ato #FFFFFF; mou #8A5A2E; on-mou #FFFFFF;"
          "quiet-bg #EBECEC; quiet-text #50565B; quiet-line #D0D3D5; focus #3F6577;"
          "head-bg #FFFFFF; head-text #2A2F33; foot-bg #3B3F43; foot-text #ECEDEE;"
          "g1 #3F6577; g2 #A0522D; g3 #A23B52; g4 #3F7A55; g5 #6C5A9A; g6 #2F7A80;"
          "radius 10px; num-weight 600; shadow 0 1px 3px rgba(42,47,51,.10)"),
    _skin("mediterranean", "地中海", "白い壁と青い海。明るく開放的", "明るい・さわやか", "明るい色が好きな方。幅広い年代", "panel", False,
          "bg #F4F9FD; bg2 #E1EFFA; surface #FFFFFF; surface2 #E8F2FB; text #0F2A4A; muted #3E5B7C; line #BBD3EA;"
          "accent #0D5CA8; on-accent #FFFFFF; ato #0D5CA8; on-ato #FFFFFF; mou #B5481A; on-mou #FFFFFF;"
          "quiet-bg #EAEEF2; quiet-text #4A5663; quiet-line #CBD3DB; focus #0D5CA8;"
          "head-bg #0D5CA8; head-text #FFFFFF; foot-bg #0A2E55; foot-text #E6F1FB;"
          "g1 #0D5CA8; g2 #B5481A; g3 #B02A55; g4 #1B7A52; g5 #5E4BA6; g6 #0F7C8C;"
          "radius 14px; shadow 0 3px 12px rgba(13,92,168,.14)"),
    _skin("tropical", "南国", "黄色と深い緑。日ざしのような明るさ", "元気・明るい", "気分を上げたい方。幅広い年代", "panel", False,
          "bg #FFF9E8; bg2 #FFEFC2; surface #FFFFFF; surface2 #FFF1CC; text #1E2B24; muted #44554A; line #F0DC9C;"
          "accent #00796B; on-accent #FFFFFF; ato #00796B; on-ato #FFFFFF; mou #C6321A; on-mou #FFFFFF;"
          "quiet-bg #EFEDE4; quiet-text #55564C; quiet-line #D5D2C2; focus #00796B;"
          "head-bg #FFC933; head-text #1E2B24; foot-bg #0B4F46; foot-text #FFF4D6;"
          "g1 #00796B; g2 #C25100; g3 #C2185B; g4 #2E7D32; g5 #7B3FBF; g6 #0277BD;"
          f"radius 18px; num-weight 900; font {FONT_ROUND}; shadow 0 3px 10px rgba(180,120,0,.18)"),
    _skin("kids", "こども", "まるくて大きい。にぎやかな色", "にぎやか・まるい", "こども、親子で使う方。小学生〜", "panel", False,
          "bg #FFF6D6; bg2 #FFE9A8; surface #FFFFFF; surface2 #FFF0B8; text #2A2340; muted #4F4870; line #FFD36B;"
          "accent #C2255C; on-accent #FFFFFF; ato #1971C2; on-ato #FFFFFF; mou #C2410C; on-mou #FFFFFF;"
          "quiet-bg #EEECE6; quiet-text #55524D; quiet-line #D6D3CA; focus #1971C2;"
          "head-bg #FFD43B; head-text #2A2340; foot-bg #3B2F6B; foot-text #FFF6D6;"
          "g1 #1971C2; g2 #C2410C; g3 #C2255C; g4 #2B8A3E; g5 #7048E8; g6 #0C8599;"
          f"radius 24px; size 18px; num-weight 900; font {FONT_ROUND}; shadow 0 4px 0 rgba(255,180,0,.45);"
          "bg-image radial-gradient(circle,#FFE08A 3px,transparent 3.5px)"),
    _skin("retro", "レトロ", "昭和の喫茶店。茶色とえんじ色", "なつかしい・渋い", "50代以上。なつかしい雰囲気が好きな方", "sticky", False,
          "bg #F0E0C0; bg2 #E4CFA6; surface #FBF1DA; surface2 #EEDDB8; text #3A2214; muted #5E4533; line #CDB48A;"
          "accent #8C2F1B; on-accent #FFFFFF; ato #1F5F5B; on-ato #FFFFFF; mou #8C2F1B; on-mou #FFFFFF;"
          "quiet-bg #E6DFD0; quiet-text #5A4F44; quiet-line #CBBFA8; focus #1F5F5B;"
          "head-bg #5B2A1A; head-text #F7E8C8; foot-bg #3A1F14; foot-text #EBD9B5;"
          "g1 #1F5F5B; g2 #A0431C; g3 #9C2A4A; g4 #4A6B1F; g5 #6B3F7A; g6 #1F5A86;"
          f"radius 4px; num-weight 800; font {FONT_MINCHO}; shadow 3px 3px 0 rgba(58,34,20,.25)"),
    _skin("neon", "ネオン", "暗い夜にピンクと水色の光", "未来的・派手", "10代〜30代。派手な色が好きな方", "ring", True,
          "bg #0B0A14; bg2 #14122A; surface #181533; surface2 #231F47; text #F5F3FF; muted #B9B4DD; line #3C3670;"
          "accent #FF4FD8; on-accent #1A0016; ato #3DF2FF; on-ato #00161A; mou #FFE14D; on-mou #1A1500;"
          "quiet-bg #1D1C2C; quiet-text #B5B3C8; quiet-line #3A3950; focus #3DF2FF;"
          "head-bg #07060F; head-text #3DF2FF; foot-bg #050409; foot-text #D8D4F5;"
          "g1 #3DF2FF; g2 #FFB347; g3 #FF6FB5; g4 #6BFF9E; g5 #B794FF; g6 #7FB5FF;"
          "radius 14px; num-weight 800; shadow 0 0 14px rgba(61,242,255,.25);"
          "bg-image radial-gradient(circle at 20% 0%,rgba(255,79,216,.18),transparent 45%)"),
    _skin("forest", "深緑", "深い森の緑。しっとり落ち着く", "しっとり・自然", "落ち着いた暗めの色が好きな方", "plain", True,
          "bg #0F1F18; bg2 #15291F; surface #1B3226; surface2 #24412F; text #EDF3E8; muted #B5C7B6; line #35513F;"
          "accent #A8D672; on-accent #10200A; ato #A8D672; on-ato #10200A; mou #F0B96B; on-mou #2A1A00;"
          "quiet-bg #222B26; quiet-text #B7C1BB; quiet-line #3A453F; focus #A8D672;"
          "head-bg #0A1712; head-text #D9EBC8; foot-bg #07110C; foot-text #C9D8C6;"
          "g1 #8CC8FF; g2 #F0A56B; g3 #F28DA6; g4 #A8D672; g5 #C3A8F0; g6 #6FD3C4;"
          "radius 12px; shadow 0 3px 12px rgba(0,0,0,.45)"),
    _skin("sunset", "夕焼け", "オレンジから紫へ。あたたかい夕方", "あたたかい・ロマンチック", "やわらかい暖色が好きな方", "panel", False,
          "bg #FFF1E6; bg2 #FFE0CC; surface #FFFFFF; surface2 #FFE9DA; text #3A1F1A; muted #6A433B; line #F3C4A8;"
          "accent #B3361A; on-accent #FFFFFF; ato #B3361A; on-ato #FFFFFF; mou #5B3A8E; on-mou #FFFFFF;"
          "quiet-bg #F0EAE6; quiet-text #5A4C48; quiet-line #D8CCC5; focus #5B3A8E;"
          "head-bg #FF8A5B; head-text #3A1F1A; foot-bg #4A2340; foot-text #FFE9DA;"
          "g1 #5B3A8E; g2 #B3361A; g3 #B02A5E; g4 #2F7A4F; g5 #7A3FB0; g6 #1E6E8C;"
          "radius 16px; shadow 0 3px 12px rgba(179,54,26,.15);"
          "bg-image linear-gradient(180deg,#FFD9BF 0,#FFF1E6 360px)"),
    _skin("cb-safe", "色覚サポート", "青とオレンジ中心。色だけに頼らない", "くっきり・実用的", "色の見分けが苦手な方。どなたでも", "plain", False,
          "bg #F7F9FB; bg2 #E9EEF3; surface #FFFFFF; surface2 #EDF1F5; text #14202B; muted #44525F; line #C8D1DA;"
          "accent #0B5CAD; on-accent #FFFFFF; ato #0B5CAD; on-ato #FFFFFF; mou #B35900; on-mou #FFFFFF;"
          "quiet-bg #EEF0F2; quiet-text #4B545D; quiet-line #CDD2D7; focus #0B5CAD;"
          "head-bg #0B5CAD; head-text #FFFFFF; foot-bg #14202B; foot-text #E7EDF3;"
          "g1 #0072B2; g2 #B35900; g3 #8C3B73; g4 #007A5E; g5 #6B6B6B; g6 #8F6B00;"
          f"radius 12px; size 17px; num-weight 800; font {FONT_UD}"),
]


def ids() -> list[str]:
    return [s["id"] for s in SKINS]


def get(skin_id: str) -> dict:
    for s in SKINS:
        if s["id"] == skin_id:
            return s
    raise KeyError(skin_id)


def _decls(values: dict) -> str:
    return ";".join(f"--{k}:{values[k]}" for k in VARS if k in values)


def css() -> str:
    """All skin blocks.  `basic` is also the default (:root) and follows the OS dark mode while no data-skin is set."""
    out = []
    for s in SKINS:
        decl = _decls(s["vars"])
        if s["id"] == "basic":
            out.append(":root{" + decl + "}")
            if s.get("dark_vars"):
                out.append("@media (prefers-color-scheme: dark){:root:not([data-skin]){" + _decls(s["dark_vars"]) + "}}")
        out.append(':root[data-skin="' + s["id"] + '"]{' + decl + "}")
    return "\n".join(out) + "\n"
