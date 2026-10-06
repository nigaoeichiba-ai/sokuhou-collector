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


def fits(name: str, recipient: str) -> bool:
    gender, age = PROFILE.get(recipient, (None, "adult"))
    if any(w in name for w in MEMORIAL + ADULT_ONLY):
        return False
    unisex = any(w in name for w in UNISEX)
    if gender == "f" and any(w in name for w in FOR_MEN) and not unisex:
        return False
    if gender == "m" and any(w in name for w in FOR_WOMEN) and not unisex:
        return False
    if age in ("adult", "senior", "teen") and any(w in name for w in FOR_KIDS) and "大人" not in name:
        return False
    if age in ("baby", "kids") and any(w in name for w in ADULT_GENDERED + FOR_SENIOR) and not unisex:
        return False
    if age == "teen" and any(w in name for w in FOR_SENIOR):
        return False
    return True
