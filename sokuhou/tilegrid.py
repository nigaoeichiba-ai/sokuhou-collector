"""Tile positions for a compact 47-prefecture Japan grid map."""
from __future__ import annotations

from sokuhou import prefectures

GRID_COLS = 11
GRID_ROWS = 12

TILES: dict[str, tuple[int, int]] = {
    "hokkaido": (10, 0),
    "aomori": (9, 2),
    "iwate": (9, 3),
    "miyagi": (9, 4),
    "akita": (8, 3),
    "yamagata": (8, 4),
    "fukushima": (9, 5),
    "ibaraki": (10, 6),
    "tochigi": (9, 6),
    "gunma": (8, 6),
    "saitama": (9, 7),
    "chiba": (10, 8),
    "tokyo": (9, 8),
    "kanagawa": (9, 9),
    "niigata": (7, 5),
    "toyama": (6, 5),
    "ishikawa": (5, 5),
    "fukui": (5, 6),
    "yamanashi": (8, 8),
    "nagano": (7, 6),
    "gifu": (6, 7),
    "shizuoka": (8, 9),
    "aichi": (7, 8),
    "mie": (7, 9),
    "shiga": (6, 8),
    "kyoto": (5, 8),
    "osaka": (5, 9),
    "hyogo": (4, 9),
    "nara": (6, 9),
    "wakayama": (5, 10),
    "tottori": (3, 8),
    "shimane": (1, 8),
    "okayama": (3, 9),
    "hiroshima": (2, 8),
    "yamaguchi": (2, 9),
    "tokushima": (4, 11),
    "kagawa": (4, 10),
    "ehime": (3, 10),
    "kochi": (3, 11),
    "fukuoka": (1, 9),
    "saga": (0, 9),
    "nagasaki": (0, 10),
    "kumamoto": (1, 10),
    "oita": (2, 10),
    "miyazaki": (2, 11),
    "kagoshima": (1, 11),
    "okinawa": (0, 11),
}


def tiles() -> list[tuple[str, int, int]]:
    """Return tile positions in the prefecture source order."""
    return [(slug, *TILES[slug]) for slug in prefectures.SLUG.values()]
