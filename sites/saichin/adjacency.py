"""Which prefectures share a land border (the sea does not count: Hokkaido and Okinawa have no neighbour here).

Written out by hand from the map; tests require the table to be symmetric and to give the known number of neighbours of the best-known cases.
"""
from __future__ import annotations

_RAW = """
北海道:
青森: 岩手 秋田
岩手: 青森 秋田 宮城
宮城: 岩手 秋田 山形 福島
秋田: 青森 岩手 宮城 山形
山形: 秋田 宮城 福島 新潟
福島: 宮城 山形 新潟 群馬 栃木 茨城
茨城: 福島 栃木 埼玉 千葉
栃木: 福島 群馬 埼玉 茨城
群馬: 福島 新潟 長野 埼玉 栃木
埼玉: 群馬 栃木 茨城 千葉 東京 山梨 長野
千葉: 茨城 埼玉 東京
東京: 埼玉 千葉 神奈川 山梨
神奈川: 東京 山梨 静岡
新潟: 山形 福島 群馬 長野 富山
富山: 新潟 長野 岐阜 石川
石川: 富山 岐阜 福井
福井: 石川 岐阜 滋賀 京都
山梨: 埼玉 東京 神奈川 静岡 長野
長野: 新潟 群馬 埼玉 山梨 静岡 愛知 岐阜 富山
岐阜: 富山 石川 福井 滋賀 三重 愛知 長野
静岡: 神奈川 山梨 長野 愛知
愛知: 静岡 長野 岐阜 三重
三重: 愛知 岐阜 滋賀 京都 奈良 和歌山
滋賀: 福井 岐阜 三重 京都
京都: 福井 滋賀 三重 奈良 大阪 兵庫
大阪: 京都 兵庫 奈良 和歌山
兵庫: 京都 大阪 鳥取 岡山
奈良: 京都 大阪 和歌山 三重
和歌山: 大阪 奈良 三重
鳥取: 兵庫 岡山 島根 広島
島根: 鳥取 広島 山口
岡山: 兵庫 鳥取 広島
広島: 岡山 鳥取 島根 山口
山口: 島根 広島
徳島: 香川 愛媛 高知
香川: 徳島 愛媛
愛媛: 香川 徳島 高知
高知: 徳島 愛媛
福岡: 佐賀 熊本 大分
佐賀: 福岡 長崎
長崎: 佐賀
熊本: 福岡 大分 宮崎 鹿児島
大分: 福岡 熊本 宮崎
宮崎: 大分 熊本 鹿児島
鹿児島: 熊本 宮崎
沖縄:
"""

NEIGHBOURS: dict[str, list[str]] = {}
for _line in _RAW.strip().splitlines():
    _name, _, _rest = _line.partition(":")
    NEIGHBOURS[_name.strip()] = _rest.split()
