"""The sales this site shows: start and end read on the organiser's own announcement (read = 'text': the page opened; 'summary': the official page seen in a search result).
Only what the organiser has published.  What it has not (Rakuten Super SALE 2026-12, Amazon Black Friday 2026, Rakuten Hatsuuri 2027) stays out and the pages say 未発表.
Hours are as the organiser writes them; '25:59' is written as the next day 1:59."""
from __future__ import annotations

from .common import CHECKED, d


def E(id, mall, name, s, st, e, et, read="text", note="", group=""):
    return {"id": id, "mall": mall, "name": name, "start": s, "start_t": st, "end": e, "end_t": et, "read": read, "note": note, "group": group or id.rsplit("-", 1)[0]}


EVENTS = [
    # --- 楽天: スーパーSALE(楽天の特設ページは回が終わると公開終了する。原文を開けたのは2026年6月分だけ。ほかの回は報道のみで、載せない)
    E("rsup-2026-06", "楽天", "楽天スーパーSALE 2026年6月", "2026-06-04", "20:00", "2026-06-11", "01:59", "text", "楽天モバイル契約者の先行セールは6月3日20時から", group="rsup"),
    # --- 楽天: お買い物マラソン
    E("rmar-2026-03", "楽天", "お買い物マラソン 2026年3月", "2026-03-20", "20:00", "2026-03-26", "01:59", group="rmar"),
    E("rmar-2026-10a", "楽天", "お買い物マラソン 2026年10月(第1弾・ジャンル祭と同時)", "2026-10-04", "20:00", "2026-10-09", "01:59", group="rmar"),
    E("rmar-2026-10b", "楽天", "お買い物マラソン 2026年10月(第2弾)", "2026-10-14", "20:00", "2026-10-17", "09:59", group="rmar"),
    E("rmar-2026-10c", "楽天", "お買い物マラソン 2026年10月(第3弾)", "2026-10-24", "20:00", "2026-10-27", "09:59", group="rmar"),
    E("rmar-2026-11", "楽天", "お買い物マラソン 2026年11月(ジャンル祭と同時)", "2026-11-04", "20:00", "2026-11-11", "01:59", note="エントリーは11月2日(月)10時から", group="rmar"),
    # --- 楽天: ブラックフライデー・初売り
    E("rbf-2024", "楽天", "楽天ブラックフライデー 2024", "2024-11-21", "20:00", "2024-11-27", "01:59", group="rbf"),
    E("rbf-2025", "楽天", "楽天ブラックフライデー 2025", "2025-11-20", "20:00", "2025-11-27", "01:59", group="rbf"),
    E("rhat-2026", "楽天", "Rakuten初売り 2026", "2026-01-01", "00:00", "2026-01-15", "09:59", group="rhat"),
    # --- Amazon
    E("apd-2025", "Amazon", "プライムデー 2025", "2025-07-11", "00:00", "2025-07-14", "23:59", group="apd"),
    E("apde-2025", "Amazon", "プライムデー先行セール 2025", "2025-07-08", "00:00", "2025-07-10", "23:59", group="apde"),
    E("apd-2026", "Amazon", "プライムデー 2026", "2026-07-10", "00:00", "2026-07-13", "23:59", "text", "日程の発表は2026年6月16日", group="apd"),
    E("apde-2026", "Amazon", "プライムデー先行セール 2026", "2026-07-07", "00:00", "2026-07-09", "23:59", group="apde"),
    E("akan-2026", "Amazon", "プライム感謝祭 2026 本セール", "2026-10-16", "00:00", "2026-10-19", "23:59", group="akan"),
    E("akane-2026", "Amazon", "プライム感謝祭 2026 先行セール", "2026-10-13", "00:00", "2026-10-15", "23:59", group="akane"),
    E("abf-2024", "Amazon", "ブラックフライデー 2024", "2024-11-29", "00:00", "2024-12-06", "23:59", group="abf"),
    E("abf-2025", "Amazon", "ブラックフライデー 2025 本セール", "2025-11-24", "00:00", "2025-12-01", "23:59", group="abf"),
    E("abfe-2025", "Amazon", "ブラックフライデー 2025 先行セール", "2025-11-21", "00:00", "2025-11-23", "23:59", group="abfe"),
    E("ashin-2026", "Amazon", "新生活セール 2026 本セール", "2026-03-06", "00:00", "2026-03-09", "23:59", group="ashin"),
    E("ahat-2026", "Amazon", "初売り 2026", "2026-01-03", "09:00", "2026-01-07", "23:59", note="12月27日12時から一部の商品を事前公開", group="ahat"),
    # --- Yahoo!ショッピング
    E("ypp-2025-03", "Yahoo!ショッピング", "超PayPay祭 2025年3月", "2025-03-03", "12:00", "2025-03-23", "", "summary", group="ypp"),
    E("ypp-2025-07", "Yahoo!ショッピング", "超PayPay祭 2025年7月", "2025-07-01", "", "2025-07-27", "", "summary", group="ypp"),
    E("ypp-2025-12", "Yahoo!ショッピング", "超PayPay祭 2025年12月", "2025-12-01", "12:00", "2025-12-15", "", group="ypp"),
    E("ypp-2026-03", "Yahoo!ショッピング", "超PayPay祭 2026年3月", "2026-03-03", "12:00", "2026-03-22", "", group="ypp"),
    E("ypp-2026-06", "Yahoo!ショッピング", "超PayPay祭 2026年夏", "2026-06-26", "12:00", "2026-07-12", "", group="ypp"),
    E("ybaku-2026-09", "Yahoo!ショッピング", "爆買ウルトラSALE 2026年9月", "2026-08-26", "12:00", "2026-09-13", "", group="ybaku"),
    E("ybf-2026", "Yahoo!ショッピング", "Yahoo!ショッピング ブラックフライデー 2026", "2026-11-22", "00:00", "2026-11-30", "01:59", note="公式は「11月29日(日)25:59まで」と表記", group="ybf"),
]
BY_ID = {e["id"]: e for e in EVENTS}

# Yahoo!ショッピングの12月の日程(公式 shopping.yahoo.co.jp/promotion/campaign/guide/ の本文で確認、2026-11-12)。カレンダー一覧には入れず、/yahoo/ の表にだけ出す。
YAHOO_DEC = [
    E("ysun-2026-12a", "Yahoo!ショッピング", "プレミアムな日曜日", "2026-12-06", "00:00", "2026-12-06", "23:59", group="ysun"),
    E("ysun-2026-12b", "Yahoo!ショッピング", "プレミアムな日曜日", "2026-12-13", "00:00", "2026-12-13", "23:59", group="ysun"),
    E("ysun-2026-12c", "Yahoo!ショッピング", "プレミアムな日曜日", "2026-12-27", "00:00", "2026-12-27", "23:59", group="ysun"),
    E("ykan-2026-12a", "Yahoo!ショッピング", "ヤフショ感謝デー", "2026-12-11", "00:00", "2026-12-11", "23:59", group="ykan"),
    E("ykan-2026-12b", "Yahoo!ショッピング", "ヤフショ感謝デー", "2026-12-22", "00:00", "2026-12-22", "23:59", group="ykan"),
]

# Not announced on the organiser's own pages on CHECKED (the pages say 未発表; this list is what --stale asks to look at again).
UNANNOUNCED = [
    ("楽天スーパーSALE 2026年12月", "楽天", "2026年の公式発表は確認できず"),
    ("Amazon ブラックフライデー 2026", "Amazon", "11月の開催は発表済み(11月5日、Amazonニュースルーム)。期間は11月19日午前に発表の予定(2026-11-12確認)"),
    ("Rakuten初売り 2027", "楽天", "公式発表は確認できず"),
    ("楽天ブラックフライデー 2026", "楽天", "公式発表は確認できず"),
    ("Amazon 初売り 2027", "Amazon", "公式発表は確認できず"),
    ("プライムデー 2027", "Amazon", "公式発表は確認できず"),
]

# Maker announcements read on the maker's own page (air conditioners, refrigerators): (maker, what, announced, on sale)
MAKER = [
    ("ダイキン", "うるさらX(エアコン)", "2026-09-24", "2026-11-01"),
    ("三菱電機", "霧ヶ峰 ZWシリーズ(エアコン)", "2026-09-09", "2026-10-30"),
]
HITACHI = [("2023-01-25", "3月上旬"), ("2024-01-18", "2月下旬"), ("2025-01-16", "2月下旬")]   # 冷蔵庫 まるごとチルド: announced, on sale (press PDF text)

# JEMA (日本電機工業会) 2025 calendar-year domestic shipments, thousand units: (name, units, % of the year before)
JEMA_2025 = [("電気冷蔵庫", 3416, 102.9), ("ルームエアコン", 9705, 103.8)]
