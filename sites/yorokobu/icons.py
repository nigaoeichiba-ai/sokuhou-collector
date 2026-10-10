"""The site's icons: Phosphor duotone pictures for the occasions (phosphor_icons.py, MIT), and a serif character in a pale circle for each person.

`icon(kind, slug, size)` is a `<use>` of one symbol; `sprite(html)` writes the sheet of only the symbols a page uses (so a page does not carry sixty pictures).
"""
from __future__ import annotations

import re
from html import escape

from sites.yorokobu.phosphor_icons import ICONS

# the picture for each occasion (names of Phosphor icons)
OCCASION = {
    "birthday": "cake", "mothers-day": "flower-tulip", "fathers-day": "watch", "respect-for-aged-day": "tea-bag", "christmas": "tree-evergreen",
    "valentine": "heart", "white-day": "cookie", "wedding-gift": "diamond", "wedding-anniversary": "champagne", "birth-gift": "baby",
    "school-entrance": "backpack", "graduation": "graduation-cap", "coming-of-age": "flower-lotus", "new-job": "briefcase", "promotion": "trend-up",
    "retirement": "sun-horizon", "farewell": "paper-plane-tilt", "housewarming": "house", "longevity": "plant", "oseibo": "package", "ochugen": "sun",
    "year-end-gathering": "beer-stein", "homecoming": "suitcase-rolling", "thanks": "hand-heart",
}
GENERIC = "gift"
# the character shown for each person (the full name is always written beside it)
RECIPIENT = {"boyfriend": "彼", "girlfriend": "彼女", "husband": "夫", "wife": "妻", "father": "父", "mother": "母", "grandfather": "祖父", "grandmother": "祖母",
             "friend-female": "友", "friend-male": "友", "colleague": "同僚", "boss": "上司", "teacher": "先生", "baby": "赤", "toddler": "幼", "child": "小",
             "teen": "中高", "in-laws": "義"}
USED = re.compile(r'href="#p-([a-z-]+)"')


def symbol(name: str) -> str:
    return f'<symbol id="p-{name}" viewBox="0 0 256 256">{ICONS[name]}</symbol>'


def sprite(html: str = "") -> str:
    """The hidden sheet with the symbols that `html` refers to (written once per page)."""
    names = sorted({n for n in USED.findall(html) if n in ICONS})
    if not names:
        return ""
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>{"".join(symbol(n) for n in names)}</defs></svg>'


def glyph(name: str, size: int = 24, cls: str = "") -> str:
    """A Phosphor picture by its name (UI marks: magnifying-glass, share-network ...); needs sprite() on the page."""
    return (f'<svg class="{"ic duo " + cls if cls else "ic duo"}" width="{size}" height="{size}" viewBox="0 0 256 256" aria-hidden="true" focusable="false" '
            f'fill="currentColor"><use href="#p-{name}"/></svg>')


def icon(kind: str, slug: str, size: int = 96) -> str:
    if kind == "recipient":
        ch = RECIPIENT.get(slug) or slug[:1]
        return f'<span class="ic badge b{len(ch)}" aria-hidden="true" style="--s:{size}px">{escape(ch)}</span>'
    name = OCCASION.get(slug, GENERIC)
    return (f'<svg class="ic duo" width="{size}" height="{size}" viewBox="0 0 256 256" aria-hidden="true" focusable="false" fill="currentColor">'
            f'<use href="#p-{name}"/></svg>')
