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


SHORT_KATAKANA = None     # compiled below
BOUNDARY_TAILS = ("セット", "ギフト", "ペア", "アソート", "サンド", "タイプ")        # what may follow a short katakana kind word without making it another word


def word_positions(name: str, word: str) -> list[int]:
    """Where `word` stands in `name` (compared like _norm: width, case and spaces ignored; the numbers count in the text without spaces) AS A WORD.  A short katakana word
    (up to 4 letters) that goes on into more katakana is the beginning of another word: 「トレー」 in 「トレーニング」 and 「ストレート」, 「アンテナ」 in 「アンテナショップ」, 「マグ」 in 「マグネット」
    (weekly review 2026-10-26: a ginger syrup of an antenna shop was shown as 「アンテナ」, a solar lantern as 「トレー」)."""
    import re
    import unicodedata
    n = unicodedata.normalize("NFKC", name).lower()
    keep = [i for i, ch in enumerate(n) if not ch.isspace()]
    s = "".join(n[i] for i in keep)
    w = _norm(word)
    if not w:
        return []
    short = bool(re.fullmatch(r"[ァ-ヶー]{1,4}", w))
    out, at = [], s.find(w)
    while at >= 0:
        end = at + len(w)
        ok = True
        if short and end < len(keep) and keep[end] == keep[end - 1] + 1:          # the next letter touches the word (a space between them is a border)
            rest = n[keep[end]:]
            if re.match(r"[ァ-ヶー]", rest) and not any(rest.startswith(t) for t in BOUNDARY_TAILS):
                ok = False
        if ok:
            out.append(at)
        at = s.find(w, at + 1)
    return out


def fits_idea(name: str, must: list[str] | tuple[str, ...] | None, never: list[str] | tuple[str, ...] | None = None) -> bool:
    """Is this product the kind of thing the idea is about?  `must` is the idea's list of words (any one is enough; spelling variants are in the list):
    "保温タンブラー" lists タンブラー, ボトル, 水筒, so a card case that the search returned for it is not shown.  An idea without a list accepts everything.
    `never` (optional) lists words of things that only sound like the idea (a "ピンチハンガー" for hats under 洗濯ピンチ): a title with one of them is not shown."""
    n = _norm(name)
    if never and any(_norm(w) in n for w in never if _norm(w)):
        return False
    if not must:
        return True
    return any(word_positions(name, w) for w in must)


def head_position(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> int | None:
    """Where in the head of the title (see fits_head) the first of the words stands: 0 is the very front; None when none of them is there."""
    import re
    head = re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name)
    head = " ".join(head.split())[:limit]
    hits = [p for w in (must or []) for p in word_positions(head, w)[:1]]
    return min(hits) if hits else None


def fits_head(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> bool:
    """Like fits_idea, but the word has to be near the front of the title, once the shop's bracketed sales words are taken off: the kind of thing a product is comes
    first in its title ("ハンドクリーム ギフト ..."), while a word far behind is often only one of the keywords the shop stuffed in ("... 花柄").  For the product lists
    that are made from every product of the site (ask/rec.json), where an idea of a page does not already tell what the product is."""
    import re
    head = re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name)
    head = " ".join(head.split())[:limit]
    return fits_idea(head, must)


# Kind words that do not make a product "another kind" when they stand in front of the idea's own word: a whole family of goods ("お菓子 クッキー"), a material or a brand
# ("今治 タオル"), and words of the same family as the idea's word (a "マグ" in front of "タンブラー": both are drinkware).
PARENT_KINDS = frozenset("""お菓子 菓子 スイーツ 洋菓子 和菓子 焼き菓子 コーヒー 紅茶 日本茶 緑茶 ティー ワイン 日本酒 ビール ウイスキー 焼酎 ジュース チョコ チョコレート
今治 フラワー プリザーブド アロマ フレグランス 文具 文房具 カタログ ベビー服 おもちゃ""".split())
FAMILIES = tuple(frozenset(f.split()) for f in (
    "マグ マグカップ グラス ペアグラス コップ タンブラー ボトル 水筒 湯呑み 茶碗 皿 箸",
    "タオル タオルハンカチ ハンカチ ハンドタオル バスタオル フェイスタオル ミニタオル ガーゼ マフラー ストール ブランケット ひざ掛け",
    "バッグ エコバッグ トートバッグ ポーチ リュック 財布 キーケース ペンケース 筆箱",
    "クッキー ケーキ ゼリー プリン どら焼き せんべい 羊羹 バウムクーヘン フィナンシェ マドレーヌ",
    "ディフューザー リードディフューザー ルームフレグランス キャンドル アロマキャンドル バスソルト 入浴剤 石けん",
    "ハンドクリーム ボディクリーム リップ 化粧水 美容液 香水",
    "ノート 手帳 ボールペン 万年筆 色鉛筆 クレヨン",
    "イヤホン ワイヤレスイヤホン ヘッドホン",
    "アイマスク ホットアイマスク マスク",
    "ソックス 靴下 スリッパ ルームシューズ",
    "時計 腕時計",
))


def _same_family(v: str, words: list[str]) -> bool:
    from sites.yorokobu import blurb
    return any(v in f and any(blurb.occurrences(w, m) for m in f for w in words) for f in FAMILIES)


def foreign_kind(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> str | None:
    """The word of the site's vocabulary of kinds (blurb.vocab) that stands in the head of the title BEFORE the idea's own word and names another sort of thing: a wristwatch
    titled "... 腕時計 ... カレンダー機能" is a watch, not a calendar for the fridge; a lip balm that comes with a hair "クリップ" is a lip balm.  None when the first kind word of the title is
    the idea's own (a word that contains one of the idea's words, one of the same family such as マグ for タンブラー, or a whole family such as お菓子), and when the title does not say
    where the idea's word stands."""
    import re
    import unicodedata
    from sites.yorokobu import blurb
    if not must:
        return None
    head = re.sub(r"[【\[（(][^】\]）)]*[】\]）)]", " ", name)
    h = unicodedata.normalize("NFKC", " ".join(head.split())[:limit]).lower()
    words = [unicodedata.normalize("NFKC", w).lower().replace(" ", "") for w in must if w]
    at = [h.find(w) for w in words if w and w in h]
    if not at:
        return None
    first = min(at)
    for v in blurb.vocab():
        if v in PARENT_KINDS or any(w in v for w in words) or _same_family(v, words):
            continue
        if any(p + len(v) <= first for p in blurb.occurrences(h, v)):
            return v
    return None


def fits_lead(name: str, must: list[str] | tuple[str, ...] | None, limit: int = 50) -> bool:
    """fits_head, and the product is of the idea's kind rather than of another one that the title names first (see foreign_kind): who leads a page."""
    return fits_head(name, must, limit) and not foreign_kind(name, must, limit)
