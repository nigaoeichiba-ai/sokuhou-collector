"""The site's icons: one-colour line drawings for the occasions and lettered badges for the people, replacing the cartoon pictures (2026-10-09).

The sprite (`sprite()`) is written once into every page; `icon(kind, slug, size)` is a `<use>` of one symbol, or a badge with the person's character.
"""
from __future__ import annotations

import re
from html import escape

# 24x24, drawn with a 1.6 stroke, round caps; the colour comes from CSS (currentColor)
OCCASION = {
    "birthday": '<path d="M4 20v-6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6z"/><path d="M4 16.5c1.3 1.2 2.7 1.2 4 0s2.7-1.2 4 0 2.7 1.2 4 0 2.7-1.2 4 0"/><path d="M12 12V8.500"/><path d="M12 4c1.200 1 1.200 2.500 0 3.500-1.200-1-1.200-2.500 0-3.500z"/><path d="M3 20h18"/>',
    "mothers-day": '<circle cx="12" cy="6.500" r="2.600"/><circle cx="16.300" cy="9.700" r="2.600"/><circle cx="14.700" cy="14.600" r="2.600"/><circle cx="9.300" cy="14.600" r="2.600"/><circle cx="7.700" cy="9.700" r="2.600"/><circle cx="12" cy="11.300" r="1.500"/>',
    "fathers-day": '<path d="M9.500 3h5l-1 3h-3z"/><path d="M10.500 6 8.500 19l3.500 2.500 3.500-2.500-2-13"/>',
    "respect-for-aged-day": '<path d="M5 9h11v4a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z"/><path d="M16 10h1.500a2.500 2.500 0 0 1 0 5H15.500"/><path d="M4 21h14"/><path d="M8 3c-1 1.500 1 2.500 0 4M12 3c-1 1.500 1 2.500 0 4"/>',
    "christmas": '<path d="M12 3 6.500 10h3L5 16h14l-4.500-6h3z"/><path d="M12 16v5"/>',
    "valentine": '<path d="M12 20.500C5 16 3.500 12.500 3.500 9.500a4.500 4.500 0 0 1 8.500-2 4.500 4.500 0 0 1 8.500 2c0 3-1.500 6.500-8.500 11z"/>',
    "white-day": '<ellipse cx="12" cy="12" rx="4.500" ry="3.500"/><path d="M7.500 12 3 9v6z"/><path d="M16.500 12 21 9v6z"/><path d="M10.500 9.200c1 2 1 3.600 0 5.600"/>',
    "wedding-gift": '<circle cx="9" cy="14" r="5"/><circle cx="15" cy="14" r="5"/><path d="M12 3v3M10.500 4.500h3"/>',
    "wedding-anniversary": '<circle cx="12" cy="15" r="5.500"/><path d="M9 6l1.500-2.500h3L15 6l-3 3.200z"/>',
    "birth-gift": '<path d="M10.500 6V4.500a1.500 1.500 0 0 1 3 0V6"/><path d="M8.500 6h7v2h-7z"/><path d="M9 8h6v12a1.500 1.500 0 0 1-1.500 1.500h-3A1.500 1.500 0 0 1 9 20z"/><path d="M12 12h3M12 15h3"/>',
    "school-entrance": '<rect x="5" y="5" width="14" height="16" rx="3"/><path d="M5 11h14"/><rect x="10.500" y="9.500" width="3" height="3" rx=".5"/><path d="M9 5V3.500h6V5"/>',
    "graduation": '<path d="M2.500 9 12 4.500 21.500 9 12 13.500z"/><path d="M6.500 11.200V16c0 1.500 2.500 3 5.500 3s5.500-1.500 5.500-3v-4.800"/><path d="M21.500 9v6"/>',
    "coming-of-age": '<path d="M12 19 4 8.500a11 11 0 0 1 16 0z"/><path d="M12 19 8 7.500M12 19l4-11.500M12 19V6.800"/>',
    "new-job": '<rect x="3.500" y="8" width="17" height="12" rx="2"/><path d="M9 8V6a1.500 1.500 0 0 1 1.500-1.500h3A1.500 1.500 0 0 1 15 6v2"/><path d="M3.500 13h17"/><path d="M12 12v2.500"/>',
    "promotion": '<path d="M3 20h5v-5h5v-5h5"/><path d="M14 5h5v5"/><path d="M19 5 11 13"/>',
    "retirement": '<path d="M12 21 7.500 12h9z"/><circle cx="9.500" cy="8.500" r="2.500"/><circle cx="14.500" cy="8.500" r="2.500"/><circle cx="12" cy="5.500" r="2.500"/>',
    "farewell": '<path d="M21 3 3 10.500l7 3 3 7z"/><path d="M21 3 10 13.500"/>',
    "housewarming": '<path d="M3.500 11 12 4l8.500 7"/><path d="M6 10v10h12V10"/><path d="M10 20v-5h4v5"/>',
    "longevity": '<path d="M12 21c-4.500 0-7-3-7-6.500C5 10 8 7.500 12 7.500s7 2.500 7 7c0 3.500-2.500 6.500-7 6.500z"/><path d="M12 7.500c0-2 1.500-3.500 4-3.500-.2 2-1.800 3.500-4 3.500z"/><path d="M12 10.500c-1.500 2.500-1.500 6 0 10"/>',
    "oseibo": '<rect x="4" y="9" width="16" height="11" rx="1.500"/><path d="M4 13.500h16M12 9v11"/><path d="M12 9C9 9 8 5 10.500 5S12 7.500 12 9zm0 0c3 0 4-4 1.500-4S12 7.500 12 9z"/>',
    "ochugen": '<circle cx="12" cy="12" r="4"/><path d="M12 3v2.500M12 18.500V21M3 12h2.500M18.500 12H21M5.600 5.600l1.800 1.800M16.600 16.600l1.800 1.800M5.600 18.400l1.800-1.800M16.600 7.400l1.800-1.800"/>',
    "year-end-gathering": '<path d="M8 3h8l-.5 5a3.500 3.500 0 0 1-7 0z"/><path d="M12 11.500V19M8.500 20.500h7"/>',
    "homecoming": '<path d="M5 8h14l1 13H4z"/><path d="M9 8V6.500a3 3 0 0 1 6 0V8"/>',
    "thanks": '<path d="M5 5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-6l-4 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/><path d="M12 13.500s-3-1.800-3-3.800a1.700 1.700 0 0 1 3-1 1.700 1.700 0 0 1 3 1c0 2-3 3.800-3 3.800z"/>',
}
for _k, _v in list(OCCASION.items()):          # a stroke of the same thickness at every size (a 24-unit drawing shown at 54px would otherwise get a 3px line)
    OCCASION[_k] = re.sub(r"<(path|circle|rect|ellipse)\b", r'<\1 vector-effect="non-scaling-stroke"', _v)
GENERIC = '<rect vector-effect="non-scaling-stroke" x="4" y="9" width="16" height="11" rx="1.500"/><path vector-effect="non-scaling-stroke" d="M4 13.500h16M12 9v11"/>'

# the character shown for each person (the full name is always written beside it)
RECIPIENT = {"boyfriend": "彼", "girlfriend": "彼女", "husband": "夫", "wife": "妻", "father": "父", "mother": "母", "grandfather": "祖父", "grandmother": "祖母",
             "friend-female": "友", "friend-male": "友", "colleague": "同僚", "boss": "上司", "teacher": "先生", "baby": "赤", "toddler": "幼", "child": "小",
             "teen": "中高", "in-laws": "義"}


def sprite() -> str:
    """The hidden sheet of occasion symbols, written once per page."""
    syms = "".join(f'<symbol id="o-{s}" viewBox="0 0 24 24">{p}</symbol>' for s, p in OCCASION.items())
    return (f'<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>{syms}</defs></svg>')


def icon(kind: str, slug: str, size: int = 96) -> str:
    if kind == "recipient":
        ch = RECIPIENT.get(slug) or slug[:1]
        return f'<span class="ic badge b{len(ch)}" aria-hidden="true" style="--s:{size}px">{escape(ch)}</span>'
    sym = f"o-{slug}" if slug in OCCASION else None
    inner = f'<use href="#{sym}"/>' if sym else GENERIC
    return (f'<svg class="ic line" width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')
