"""The illustration catalogue of みんなのイラスト: every item with its id, title, category, search words and a one-line description.

Source files are the transparent WebP images in sites/minna/assets/src/ (copied once by prepare.py); the build derives the PNG downloads.
"""
from __future__ import annotations

CATEGORIES = [
    ("expressions", "しまエナガの表情", "笑顔・ウインク・おどろき・ハート目など、気持ちが伝わる表情のシマエナガ。赤いマフラーと青いマフラーのふたりです。"),
    ("jobs", "しまエナガのお仕事", "ソムリエ・コンシェルジュ・ナビゲーターに変身したシマエナガ。案内や紹介のページに。"),
    ("seasons", "しまエナガの季節と行事", "サンタ、お正月、バレンタイン、母の日など、行事の衣装のシマエナガ。"),
    ("event-icons", "イベントのイラスト", "誕生日、結婚祝い、お歳暮など、24のイベントを表す、かんたんなイラスト。"),
    ("people-icons", "人物のアイコン", "彼氏、母、同僚、赤ちゃんなど、18人の、やさしいタッチの人物アイコン。"),
]

R, B = "赤いマフラー", "青いマフラー"
EXPR = {"joy": ("大よろこび", "わらって大よろこび"), "sparkle": ("きらきらの目", "目をきらきらさせて"), "wink": ("ウインク", "ウインクして"),
        "love": ("ハートの目", "ハートの目で"), "surprise": ("おどろき", "おどろいて"), "thanks": ("ありがとう", "ありがとうと、おじぎをして")}
PAIR = {"love": ("ふたりでハート", "ふたりでハートの気持ちを伝えて"), "thanks": ("ふたりでありがとう", "ふたりで、ありがとうを伝えて"),
        "jump": ("ふたりでジャンプ", "ふたりでジャンプして大よろこび"), "surprise": ("ふたりでびっくり", "ふたりで、びっくりして"),
        "gift": ("プレゼントを持って", "プレゼントを、はんぶんこにして"), "wave": ("手をふる", "手をふって、あいさつして")}
JOBS = {
    "sommelier-gift": ("ソムリエ(プレゼントを持つ)", "ソムリエの服で、プレゼントを持って"), "sommelier-taste": ("ソムリエ(味見)", "ソムリエの服で、味見をして"),
    "sommelier-tray": ("ソムリエ(トレイで運ぶ)", "ソムリエの服で、トレイに、プレゼントをのせて"), "sommelier-spin": ("ソムリエ(くるくる)", "ソムリエの服で、トレイをもって、くるっと回って"),
    "concierge-bell": ("コンシェルジュ(ベル)", "コンシェルジュの帽子で、ベルを鳴らして"), "concierge-bow": ("コンシェルジュ(おじぎ)", "コンシェルジュの服で、ていねいにおじぎをして"),
    "concierge-note": ("コンシェルジュ(メモ)", "コンシェルジュの服で、メモを取って"), "concierge-run": ("コンシェルジュ(いそぐ)", "コンシェルジュの服で、荷物をもって、いそいで"),
    "navi-scope": ("ナビゲーター(望遠鏡)", "船長の帽子で、望遠鏡をのぞくふたり"), "navi-flags": ("ナビゲーター(旗)", "船長の帽子で、旗をもつふたり"),
    "navi-map": ("ナビゲーター(地図)", "船長の帽子で、地図とコンパスを持つふたり"), "navi-jump": ("ナビゲーター(ジャンプ)", "船長の帽子で、ジャンプして指さすふたり"),
}
SEASONS = {
    "season-christmas": ("サンタのシマエナガ", "サンタ帽をかぶって、プレゼントの袋をもって", ["クリスマス", "サンタ", "冬"]),
    "season-newyear": ("お正月のシマエナガ", "羽織を着て、小づちと凧をもって", ["お正月", "年賀状", "新年", "冬"]),
    "season-birthday": ("誕生日のシマエナガ", "パーティー帽をかぶって、ケーキをもって", ["誕生日", "お祝い", "ケーキ"]),
    "season-valentine": ("バレンタインのシマエナガ", "ハートのチョコと、ハートのバッグをもって", ["バレンタイン", "チョコ", "2月"]),
    "season-mothers": ("母の日のシマエナガ", "エプロン姿で、カーネーションをもって", ["母の日", "カーネーション", "5月"]),
    "season-fathers": ("父の日のシマエナガ", "ネクタイを見せて、プレゼントをもって", ["父の日", "ネクタイ", "6月"]),
    "season-summer": ("夏のシマエナガ", "ゆかたを着て、うちわとスイカをもって", ["夏", "ゆかた", "お中元", "スイカ"]),
    "season-party": ("パーティーのふたり", "クラッカーを鳴らして、プレゼントをかこんで", ["パーティー", "お祝い", "忘年会", "クラッカー"]),
}


def build_catalog(occasions: dict[str, str], recipients: dict[str, str]) -> list[dict]:
    """[{id, src, title, category, tags, desc}] in display order.  `occasions` / `recipients` map slug -> Japanese name."""
    out = []
    for key, (t, d) in EXPR.items():
        for pre, scarf in (("r", R), ("b", B)):
            out.append({"id": f"{pre}-{key}", "src": f"{pre}-{key}", "title": f"しまエナガ({scarf}) {t}", "category": "expressions",
                        "tags": ["しまエナガ", "シマエナガ", "鳥", "かわいい", t, scarf], "desc": f"{scarf}のシマエナガが、{d}いるイラスト。"})
    for key, (t, d) in PAIR.items():
        out.append({"id": f"pair-{key}", "src": f"pair-{key}", "title": f"しまエナガ {t}", "category": "expressions",
                    "tags": ["しまエナガ", "シマエナガ", "ふたり", "つがい", "鳥", t], "desc": f"赤いマフラーと青いマフラーのシマエナガが、{d}いるイラスト。"})
    for key, (t, d) in JOBS.items():
        out.append({"id": key, "src": key, "title": f"しまエナガ {t}", "category": "jobs",
                    "tags": ["しまエナガ", "シマエナガ", "鳥", "コスチューム", t.split("(")[0]], "desc": f"シマエナガが、{d}いるイラスト。"})
    for key, (t, d, tags) in SEASONS.items():
        out.append({"id": key, "src": key, "title": t, "category": "seasons", "tags": ["しまエナガ", "シマエナガ", "鳥", "行事", *tags], "desc": f"シマエナガが、{d}いるイラスト。"})
    for slug, name in occasions.items():
        out.append({"id": f"event-{slug}", "src": f"occasion/{slug}", "title": f"{name}のイラスト", "category": "event-icons",
                    "tags": [name, "イベント", "アイコン", "お祝い"], "desc": f"「{name}」を表す、ふちどりのあるイラスト。招待状、案内、SNSの画像などに。"})
    for slug, name in recipients.items():
        out.append({"id": f"person-{slug}", "src": f"recipient/{slug}", "title": f"{name}のアイコン", "category": "people-icons",
                    "tags": [name, "人物", "アイコン", "似顔絵風"], "desc": f"「{name}」を表す、やさしいタッチの人物アイコン。"})
    return out
