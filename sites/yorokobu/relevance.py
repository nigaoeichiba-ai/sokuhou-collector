"""Does a product fit the person it is shown for?  Cheap, deterministic title rules (no AI): gender, age group, memorial goods.

The Rakuten search returns anything that matches the words, so "母 誕生日 財布" can return men's wallets.  These rules run at fetch time
and again at build time, so a rule change shows up without refetching.
"""
from __future__ import annotations

# (gender, age group) of each recipient; gender None = mixed or unknown, age "kids" for children
PROFILE = {
    "boyfriend": ("m", "adult"), "girlfriend": ("f", "adult"), "husband": ("m", "adult"), "wife": ("f", "adult"),
    "father": ("m", "adult"), "mother": ("f", "adult"), "grandfather": ("m", "senior"), "grandmother": ("f", "senior"),
    "friend-female": ("f", "adult"), "friend-male": ("m", "adult"), "colleague": (None, "adult"), "boss": (None, "adult"),
    "teacher": (None, "adult"), "baby": (None, "baby"), "toddler": (None, "kids"), "child": (None, "kids"), "teen": (None, "teen"),
    "in-laws": (None, "senior"),
}
UNISEX = ("兼用", "ユニセックス", "男女", "メンズ レディース", "メンズ・レディース", "レディース メンズ", "レディース・メンズ")
FOR_MEN = ("メンズ", "男性用", "男性向け", "紳士", "ボーイズ", "男の子", "男児", "パパ")
FOR_WOMEN = ("レディース", "女性用", "女性向け", "婦人", "ガールズ", "女の子", "女児", "ママ", "マタニティ", "ウィメンズ")
FOR_KIDS = ("キッズ", "子供用", "子ども用", "子供向け", "ベビー", "幼児", "ジュニア", "赤ちゃん", "新生児")
FOR_SENIOR = ("シニア", "高齢者", "介護", "老眼")
ADULT_GENDERED = ("メンズ", "レディース", "紳士", "婦人", "男性用", "女性用", "男性向け", "女性向け")
MEMORIAL = ("香典", "お供え", "仏壇", "線香", "法事", "法要", "供花", "喪中", "喪服", "お悔やみ", "忌明け", "一周忌", "三回忌", "初盆", "新盆")
ADULT_ONLY = ("アダルト", "大人のおもちゃ", "セクシー", "ランジェリー", "下着")


HEAD_LIMIT = 50      # about what a card shows of a title


def _head(name: str, limit: int = HEAD_LIMIT) -> str:
    """The front of a title as a card shows it: the shop's bracketed sales words taken off, cut at `limit` characters."""
    import re
    return " ".join(re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name).split())[:limit]


def fits(name: str, recipient: str | None) -> bool:
    gender, age = PROFILE.get(recipient, (None, "adult"))
    if any(w in name for w in MEMORIAL + ADULT_ONLY):
        return False
    unisex = any(w in name for w in UNISEX)
    if gender == "f" and any(w in name for w in FOR_MEN) and not unisex:
        return False
    if gender == "m" and any(w in name for w in FOR_WOMEN) and not unisex:
        return False
    # what a card shows is the front of the title: a title that opens "女性用 レディース ..." reads as made for women even when the shop writes ユニセックス further back
    head = _head(name)
    if gender == "m" and any(w in head for w in FOR_WOMEN) and not any(w in head for w in FOR_MEN + UNISEX):
        return False
    if gender == "f" and any(w in head for w in FOR_MEN) and not any(w in head for w in FOR_WOMEN + UNISEX):
        return False
    if age in ("adult", "senior", "teen") and any(w in name for w in FOR_KIDS) and "大人" not in name:
        return False
    if age in ("baby", "kids") and any(w in name for w in ADULT_GENDERED + FOR_SENIOR) and not unisex:
        return False
    if age == "teen" and any(w in name for w in FOR_SENIOR):
        return False
    return True


# Titles that name another, narrower occasion (a winter-gift listing on a birthday page, a baby-shower pouch for a mother's birthday)
OCCASION_ONLY = {
    "oseibo": ("お歳暮", "御歳暮"), "ochugen": ("お中元", "御中元"), "birth-gift": ("母子手帳",),
    "homecoming": (), "new-year": ("お年賀",),
}
OCCASION_ONLY_ALL = tuple(w for ws in OCCASION_ONLY.values() for w in ws) + ("ハロウィン", "お年賀")


OCCASION_WORDS = ("誕生日", "母の日", "父の日", "敬老の日", "クリスマス", "バレンタイン", "ホワイトデー", "結婚祝い", "出産祝い", "退職祝い", "内祝い", "お歳暮", "御歳暮",
                  "お中元", "御中元", "ハロウィン", "お年賀", "入学祝い", "卒業祝い", "就職祝い", "新築祝い", "長寿祝い", "還暦祝い", "引越し祝い", "快気祝い", "お見舞い")


# Occasions held in the cold season, and goods that are only for summer
WINTER_OCCASIONS = ("oseibo", "year-end-gathering", "christmas", "new-year")
SUMMER_ONLY = ("夏用", "甚平", "甚兵衛", "浴衣", "水着", "うちわ", "団扇", "かき氷", "夏向け", "夏物")


def fits_occasion(name: str, occasion: str, occasion_name: str = "") -> bool:
    """False when the title is made for a different, narrower occasion than the page's.  A title that names this page's own occasion, or that
    lists three or more occasions (keyword stuffing: a generic gift), is fine; one that names only another narrow occasion is not."""
    if occasion in WINTER_OCCASIONS and any(w in name for w in SUMMER_ONLY):
        return False                                # a summer garment on a year-end page (the grandfather's 甚平, weekly review 2026-10-12)
    if occasion_name and occasion_name in name:
        return True
    own = OCCASION_ONLY.get(occasion, ())
    if not any(w in name and w not in own for w in OCCASION_ONLY_ALL):
        return True
    return sum(1 for w in OCCASION_WORDS if w in name) >= 3


def _norm(text: str) -> str:
    """Titles are written in full-width and half-width forms and in any case; compare them as one."""
    import unicodedata
    return unicodedata.normalize("NFKC", text).lower().replace(" ", "")


def fits_idea(name: str, must: list[str] | tuple[str, ...] | None) -> bool:
    """Is this product the kind of thing the idea is about?  `must` is the idea's list of words (any one is enough; spelling variants are in the list):
    "保温タンブラー" lists タンブラー, ボトル, 水筒, so a card case that the search returned for it is not shown.  An idea without a list accepts everything."""
    if not must:
        return True
    n = _norm(name)
    return any(_norm(w) in n for w in must)


def head_position(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> int | None:
    """Where in the head of the title (see fits_head) the first of the words stands: 0 is the very front; None when none of them is there."""
    import re
    head = re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name)
    head = _norm(" ".join(head.split())[:limit])
    hits = [head.find(_norm(w)) for w in (must or []) if _norm(w) and _norm(w) in head]
    return min(hits) if hits else None


def fits_head(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> bool:
    """Like fits_idea, but the word has to be near the front of the title, once the shop's bracketed sales words are taken off: the kind of thing a product is comes
    first in its title ("ハンドクリーム ギフト ..."), while a word far behind is often only one of the keywords the shop stuffed in ("... 花柄").  For the product lists
    that are made from every product of the site (ask/rec.json), where an idea of a page does not already tell what the product is."""
    import re
    head = re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name)
    head = " ".join(head.split())[:limit]
    return fits_idea(head, must)
