"""The 47 prefectures in JIS order: short names (as most government tables write them), URL names and regions.

Shared by the sites; sites/saichin still has its own copy and will move here when it is next touched.
"""
from __future__ import annotations

SHORT = (
    "北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 "
    "新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 "
    "鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄"
).split()
assert len(SHORT) == 47

SLUG = dict(zip(SHORT, (
    "hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa "
    "niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama "
    "tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita "
    "miyazaki kagoshima okinawa"
).split()))

_SUFFIX = {"北海道": "", "東京": "都", "大阪": "府", "京都": "府"}

REGIONS = [
    ("hokkaido-tohoku", "北海道・東北", "北海道 青森 岩手 宮城 秋田 山形 福島".split()),
    ("kanto", "関東", "茨城 栃木 群馬 埼玉 千葉 東京 神奈川".split()),
    ("chubu", "中部", "新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知".split()),
    ("kinki", "近畿", "三重 滋賀 京都 大阪 兵庫 奈良 和歌山".split()),
    ("chugoku", "中国", "鳥取 島根 岡山 広島 山口".split()),
    ("shikoku", "四国", "徳島 香川 愛媛 高知".split()),
    ("kyushu-okinawa", "九州・沖縄", "福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄".split()),
]
assert sorted(p for _, _, ps in REGIONS for p in ps) == sorted(SHORT)


def full(short: str) -> str:
    """'青森' -> '青森県', '東京' -> '東京都'."""
    return short + _SUFFIX.get(short, "県")


def region_of(short: str) -> tuple[str, str]:
    for slug, name, members in REGIONS:
        if short in members:
            return slug, name
    raise KeyError(short)
