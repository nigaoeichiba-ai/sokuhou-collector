"""Genres and art touches of みんなのイラスト, and the style text each touch sends to the image generator.

A series (sites/minna/specs/<slug>.json) names one genre and one touch; the build groups items by both, so a visitor can browse
"どうぶつ" (genre) or "水彩" (touch) and every combination is a page of its own once it holds enough items.
"""
from __future__ import annotations

# (slug, name, one-line description, search-word hint shown on the genre page)
GENRES = [
    ("animals", "どうぶつ", "犬・猫・うさぎ・ひつじなど、表情ゆたかなどうぶつのイラスト。", ["動物", "かわいい", "キャラクター"]),
    ("eto", "干支・年賀状", "十二支のどうぶつと、お正月・年賀状に使えるイラスト。", ["干支", "年賀状", "お正月", "未年"]),
    ("season", "季節・行事", "クリスマス・ハロウィン・節分・花見など、季節の行事のイラスト。", ["季節", "行事", "イベント"]),
    ("food", "たべもの", "ごはん・おやつ・くだもの・飲みものなど、おいしそうなイラスト。", ["食べ物", "料理", "スイーツ"]),
    ("nature", "花・自然", "花・木・空・天気など、自然のモチーフのイラスト。", ["花", "植物", "天気"]),
    ("life", "くらし・もの", "家・文房具・家電・乗りものなど、身のまわりのものを表すイラスト。", ["日用品", "道具", "暮らし"]),
    ("school", "学校・保育", "おたより・掲示・行事に使える、学校や園のイラスト。", ["学校", "保育園", "おたより"]),
    ("work", "仕事・ビジネス", "資料・チラシ・サイトに使える、仕事まわりのイラスト。", ["ビジネス", "会社", "資料"]),
    ("people", "人物", "いろいろな職業・年代・場面の、やさしいタッチの人物イラスト。", ["人物", "職業", "アイコン"]),
    ("deco", "フレーム・かざり", "フレーム、吹き出し、リボンなど、文字や写真を飾る素材。", ["フレーム", "飾り枠", "吹き出し"]),
    ("icon", "アイコン・マーク", "矢印・ハート・星・チェックなど、わかりやすいマークとアイコン。", ["アイコン", "マーク", "ピクトグラム"]),
    ("shimaenaga", "シマエナガ", "表情・衣装・行事のシマエナガ。赤いマフラーと青いマフラーのふたり。", ["シマエナガ", "鳥", "かわいい"]),
]

# (slug, name, one-line description, style text for the generator)
TOUCHES = [
    ("kawaii", "ゆるかわ", "太めの茶色い線と、ふんわりした色のやさしいタッチ。",
     "kawaii Japanese mascot style. Soft rounded chubby shapes. Uniform dark warm-brown outline (#5B3A29), medium-thick, smooth, closed contours. "
     "Flat colours with at most ONE subtle soft tone for cheeks/belly; no gradients, no textures, no shading, no cast shadow, no glow. "
     "Eyes: large glossy dark-brown ovals with two white highlights (or happy closed arcs); tiny simple nose and mouth; rosy cheeks (#FF9DB0)."),
    ("watercolor", "やわらか水彩", "にじみのある、やわらかい水彩画のタッチ。",
     "soft watercolour illustration: gentle translucent washes, light uneven pigment edges, a thin delicate pencil-like outline in a slightly darker tone of each colour, "
     "airy and warm, pastel-leaning palette, clean cut-out look (no paper texture, no background splashes, no drop shadow)."),
    ("crayon", "クレヨン・手描き", "クレヨンや色鉛筆で描いたような、あたたかい手描きのタッチ。",
     "hand-drawn crayon and coloured-pencil illustration: wobbly friendly outlines, visible gentle crayon grain inside colour areas but clean edges, "
     "bright childlike colours, simple shapes, like a picture drawn by a cheerful kindergarten teacher (no paper texture, no shadow)."),
    ("lineart", "ぬりえ・線画", "黒い線だけで描いた、ぬりえにも使える線画。",
     "clean black line art for colouring pages: one uniform smooth black outline (about 6 px at 512 px), NO fills, NO grey, NO shading, "
     "shapes are closed so they can be coloured, plain white inside every shape, simple cute rounded designs suitable for children."),
    ("flat", "シンプルフラット", "線をつかわない、すっきりした色面のタッチ。",
     "simple modern flat vector illustration: solid colour shapes with no outlines, a limited bright but friendly palette of 4 to 6 colours per item, "
     "geometric rounded shapes, no gradients, no textures, no shadow, easy to read at small sizes."),
    ("wa", "和風・和柄", "和柄と日本の伝統色をいかした、和のタッチ。",
     "Japanese traditional (wa) illustration: elegant simplified shapes, traditional colours (vermilion, indigo, matcha green, gold, ivory), "
     "flat colour with fine decorative patterns such as seigaiha, asanoha and sakura, thin dark-indigo outline, gentle and festive, no shadow."),
    ("papercut", "切り絵・ペーパークラフト", "紙を切って重ねたような、切り絵のタッチ。",
     "layered paper-cut craft illustration: flat coloured paper shapes stacked with soft thin drop shadows between layers only (no shadow outside the object), "
     "slightly rounded cut edges, bright colours, handmade charm, clean cut-out look."),
    ("pixel", "ドット絵", "ゲームのような、ドットで描いたタッチ。",
     "retro pixel art, 64x64 style scaled up with crisp square pixels, limited palette, 1-pixel dark outline, no anti-aliasing blur, cute and readable."),
    ("clay", "ぷっくり立体風", "粘土やぬいぐるみのような、ぷっくりした立体風のタッチ。",
     "cute soft 3D clay/plush look: puffy rounded forms, matte surface, soft studio lighting with gentle highlights, subtle rounded shading ONLY on the object itself, "
     "no cast shadow, no reflection, clean cut-out."),
    ("retro", "昭和レトロ", "昭和の広告やパッケージのような、レトロなタッチ。",
     "Showa-era retro Japanese illustration: slightly muted warm colours (mustard, tomato red, teal, cream), simple shapes with thick off-register-style outlines, "
     "nostalgic poster and packaging feel, no halftone background, no shadow."),
    ("silhouette", "シルエット", "ひとつの色でつくった、シルエットのタッチ。",
     "solid single-colour silhouette illustration (deep navy #24304A) with crisp edges and a clearly readable outline shape; "
     "only tiny cut-out white details allowed (eyes, small patterns); no gradients, no shadow."),
]

GENRE_BY_SLUG = {g[0]: g for g in GENRES}
TOUCH_BY_SLUG = {t[0]: t for t in TOUCHES}
