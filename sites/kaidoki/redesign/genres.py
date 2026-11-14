"""The genres of the calendar ('ジャンルで探す'): one page each (家電・デジタル is /kaden/, the others are /<id>/), the shop and product pages under it, and the sales that belong to it.

The facts of a genre page are the same kind as everywhere on the site: a rate, an amount off, a perk or a date, each with its check day and an official link.  No price, no ranking, no 'cheapest'.
The malls' sales (楽天・Amazon・Yahoo!) belong to every genre, the shops' own sales (schedule.py entries) to the genre of the shop.
"""
from __future__ import annotations

# genre id -> (page path, the shops of schedule.ENT that sell in it, the word of the Amazon search link on the page, the page's own title and description)
GENRES: dict[str, dict] = {
    "electronics": {"path": "/kaden/", "brands": ("yamada", "sonystore", "google", "asus", "lg", "sharp", "panasonic", "nec", "dyson"), "amazon": "家電", "crumb": "家電・デジタル"},
    "food": {"path": "/food/", "brands": (), "amazon": "食品", "crumb": "食品・飲料"},
    "daily": {"path": "/daily/", "brands": (), "amazon": "日用品", "crumb": "日用品"},
    "fashion": {"path": "/fashion/", "brands": ("uniqlo", "zozo"), "amazon": "ファッション", "crumb": "ファッション"},
    "beauty": {"path": "/beauty/", "brands": ("dhc",), "amazon": "美容", "crumb": "美容・健康"},
    "home": {"path": "/home/", "brands": ("nitori",), "amazon": "インテリア", "crumb": "家具・暮らし"},
    "hobby": {"path": "/hobby/", "brands": ("playstation",), "amazon": "スポーツ アウトドア", "crumb": "趣味・レジャー"},
    "service": {"path": "/service/", "brands": ("xserver", "xdomain", "stardomain"), "amazon": "", "crumb": "WEBサービス"},
}
GENRE_PATH = {k: v["path"] for k, v in GENRES.items()}
GENRE_OF_BRAND = {b: k for k, v in GENRES.items() for b in v["brands"]}
GENRE_PREFIXES = tuple(v["path"] for k, v in GENRES.items())

# the programmes we are partners of, per genre: the shop's own page behind our link (no claim about a sale; the sales stay in the tables above).  ("a8" | "vctext", key, link text)
PARTNERS: dict[str, list[tuple[str, str, str]]] = {
    "electronics": [("vctext", "lenovo", "Lenovo公式オンラインストアを見る"), ("vctext", "minisforum", "MINISFORUMのサイトを見る")],
    "food": [("a8", "oisix", "Oisixのおためしセットのページを見る")],
    "hobby": [("a8", "alpen", "スポーツデポ・ゴルフ5・アルペンの公式オンラインストアを見る")],
    "service": [("a8", "xserver", "エックスサーバーを見る"), ("a8", "xdomain", "XServerドメインを見る"), ("a8", "onamae", "お名前.comを見る"), ("a8", "muumuu", "ムームードメインを見る"),
                ("a8", "lolipop", "ロリポップ！を見る"), ("a8", "mixhost", "mixhostを見る"), ("a8", "sakura", "さくらのレンタルサーバを見る"), ("a8", "stardomain", "スタードメインを見る")],
}

# a page that was published and then merged into another: its old address answers 301 to the new one (written into .htaccess by render.apply)
REDIRECTS = {"/hobby/steam/": "/hobby/game-sales/"}
