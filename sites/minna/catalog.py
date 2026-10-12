"""The illustration catalogue of みんなのイラスト: every item with its id, title, category, search words and a one-line description.

Source files are the transparent WebP images in sites/minna/assets/src/ (copied once by prepare.py); the build derives the PNG downloads.
"""
from __future__ import annotations

CATEGORIES = [
    ("expressions", "しまエナガの表情", "笑顔・ウインク・驚き・ハート目など、感情を伝えやすいシマエナガの表情素材です。赤いマフラーと青いマフラーの2羽をそろえています。"),
    ("jobs", "しまエナガの仕事", "ソムリエ・コンシェルジュ・ナビゲーターの装いをしたシマエナガです。案内や紹介のページに使えます。"),
    ("seasons", "しまエナガの季節と行事", "サンタ、お正月、バレンタイン、母の日など、季節行事に合わせた衣装のシマエナガです。"),
    ("event-icons", "イベントのイラスト", "誕生日、結婚祝い、お歳暮など、24種類のイベントを表すシンプルなイラストです。"),
    ("people-icons", "人物のアイコン", "彼氏、母、同僚、赤ちゃんなど、18種類の人物を表す穏やかなタッチのアイコンです。"),
]

R, B = "赤いマフラー", "青いマフラー"
EXPR = {"joy": ("大よろこび", "笑顔で喜んで"), "sparkle": ("きらきらの目", "目を輝かせて"), "wink": ("ウインク", "ウインクして"),
        "love": ("ハートの目", "ハートの目をして"), "surprise": ("おどろき", "驚いた表情をして"), "thanks": ("ありがとう", "お礼を伝えるようにお辞儀をして")}
PAIR = {"love": ("ふたりでハート", "2羽でハートの気持ちを伝えて"), "thanks": ("ふたりでありがとう", "2羽で感謝を伝えて"),
        "jump": ("ふたりでジャンプ", "2羽でジャンプして喜びを表して"), "surprise": ("ふたりでびっくり", "2羽で驚きを表して"),
        "gift": ("プレゼントを持って", "プレゼントを一緒に持って"), "wave": ("手をふる", "手を振って挨拶して")}
JOBS = {
    "sommelier-gift": ("ソムリエ(プレゼントを持つ)", "ソムリエの服でプレゼントを持って"), "sommelier-taste": ("ソムリエ(味見)", "ソムリエの服で味見をして"),
    "sommelier-tray": ("ソムリエ(トレイで運ぶ)", "ソムリエの服でトレイにプレゼントをのせて"), "sommelier-spin": ("ソムリエ(くるくる)", "ソムリエの服でトレイを持って回って"),
    "concierge-bell": ("コンシェルジュ(ベル)", "コンシェルジュの帽子でベルを鳴らして"), "concierge-bow": ("コンシェルジュ(おじぎ)", "コンシェルジュの服で丁寧にお辞儀をして"),
    "concierge-note": ("コンシェルジュ(メモ)", "コンシェルジュの服でメモを取って"), "concierge-run": ("コンシェルジュ(いそぐ)", "コンシェルジュの服で荷物を持って急いで"),
    "navi-scope": ("ナビゲーター(望遠鏡)", "船長の帽子で望遠鏡をのぞく2羽"), "navi-flags": ("ナビゲーター(旗)", "船長の帽子で旗を持つ2羽"),
    "navi-map": ("ナビゲーター(地図)", "船長の帽子で地図とコンパスを持つ2羽"), "navi-jump": ("ナビゲーター(ジャンプ)", "船長の帽子でジャンプして指さす2羽"),
}
SEASONS = {
    "season-christmas": ("サンタのシマエナガ", "サンタ帽をかぶり、プレゼントの袋を持って", ["クリスマス", "サンタ", "冬"]),
    "season-newyear": ("お正月のシマエナガ", "羽織を着て、小づちと凧を持って", ["お正月", "年賀状", "新年", "冬"]),
    "season-birthday": ("誕生日のシマエナガ", "パーティー帽をかぶり、ケーキを持って", ["誕生日", "お祝い", "ケーキ"]),
    "season-valentine": ("バレンタインのシマエナガ", "ハートのチョコとバッグを持って", ["バレンタイン", "チョコ", "2月"]),
    "season-mothers": ("母の日のシマエナガ", "エプロン姿でカーネーションを持って", ["母の日", "カーネーション", "5月"]),
    "season-fathers": ("父の日のシマエナガ", "ネクタイを見せ、プレゼントを持って", ["父の日", "ネクタイ", "6月"]),
    "season-summer": ("夏のシマエナガ", "浴衣を着て、うちわとスイカを持って", ["夏", "ゆかた", "お中元", "スイカ"]),
    "season-party": ("パーティーのふたり", "クラッカーを鳴らし、プレゼントを囲んで", ["パーティー", "お祝い", "忘年会", "クラッカー"]),
}


def build_catalog(occasions: dict[str, str], recipients: dict[str, str]) -> list[dict]:
    """[{id, src, title, category, tags, desc}] in display order.  `occasions` / `recipients` map slug -> Japanese name."""
    out = []
    for key, (t, d) in EXPR.items():
        for pre, scarf in (("r", R), ("b", B)):
            out.append({"id": f"{pre}-{key}", "src": f"{pre}-{key}", "title": f"しまエナガ({scarf}) {t}", "category": "expressions",
                        "tags": ["しまエナガ", "シマエナガ", "鳥", "かわいい", t, scarf], "desc": f"{scarf}のシマエナガが{d}いるイラスト。"})
    for key, (t, d) in PAIR.items():
        out.append({"id": f"pair-{key}", "src": f"pair-{key}", "title": f"しまエナガ {t}", "category": "expressions",
                    "tags": ["しまエナガ", "シマエナガ", "ふたり", "つがい", "鳥", t], "desc": f"赤いマフラーと青いマフラーのシマエナガが{d}いるイラスト。"})
    for key, (t, d) in JOBS.items():
        out.append({"id": key, "src": key, "title": f"しまエナガ {t}", "category": "jobs",
                    "tags": ["しまエナガ", "シマエナガ", "鳥", "コスチューム", t.split("(")[0]], "desc": f"シマエナガが{d}いるイラスト。"})
    for key, (t, d, tags) in SEASONS.items():
        out.append({"id": key, "src": key, "title": t, "category": "seasons", "tags": ["しまエナガ", "シマエナガ", "鳥", "行事", *tags], "desc": f"シマエナガが{d}いるイラスト。"})
    for slug, name in occasions.items():
        out.append({"id": f"event-{slug}", "src": f"occasion/{slug}", "title": f"{name}のイラスト", "category": "event-icons",
                    "tags": [name, "イベント", "アイコン", "お祝い"], "desc": f"「{name}」を表す、ふちどりのあるイラスト。招待状、案内、SNS画像などに使えます。"})
    for slug, name in recipients.items():
        out.append({"id": f"person-{slug}", "src": f"recipient/{slug}", "title": f"{name}のアイコン", "category": "people-icons",
                    "tags": [name, "人物", "アイコン", "似顔絵風"], "desc": f"「{name}」を表す、穏やかなタッチの人物アイコン。"})
    return out
