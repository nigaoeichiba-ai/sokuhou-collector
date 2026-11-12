"""The schedule data and the calendars of sale-calendar.com (2026-11-12): every mall in one monthly calendar, and one calendar per mall.

Four kinds of entries, always told apart by a word, a symbol and a style (never by colour alone):
  confirmed  (確定)       a date the organiser published, or that two independent reports agree on.  From gen/facts.py (read on the organiser's page) plus the entries of EXTRA_CONFIRMED.
  expected   (例年の予想)  not announced yet, but held every year.  Each carries the dates of the past years it rests on (basis).  A year seen only once is not listed.
  regular    (毎月の定例)  the days that come every month (5と0のつく日, ワンダフルデー, ...), and the dated days of a campaign the mall lists by date.
  notice     (発表予定日)  the day the organiser said it will publish the details.
Only dates, names and conditions in a sentence.  No product, no price, no commission.  The words "ごろ" and "予想" are used for every entry that is not confirmed.

How it is drawn: the month grid and the list of months are written into the page (so the page reads without a script); sites/kaidoki/redesign/static/scripts/calendar.js moves the grid
from month to month, filters by mall and kind, and writes "開催中" / "あとN日" from the visitor's own clock (never from the build time).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from html import escape

from sites.kaidoki.gen.common import CHECKED, hm, ev_span

WD = "月火水木金土日"
MIN_YM, MAX_YM = "2026-01", "2027-12"          # the months the calendar can show
REGULAR_FROM = date(2026, 11, 1)                 # a monthly day is listed from this month on (the older months show announced sales only)
REGULAR_TO = date(2027, 6, 30)                   # ... and up to this day (a campaign's rules can change; the page says so)
VERIFIED = "2026-11-12"                          # the day the entries below were read again

MALLS = {"rakuten": ("楽天市場", "楽"), "amazon": ("Amazon", "A"), "yahoo": ("Yahoo!ショッピング", "Y")}      # the three malls: each has its own calendar page
SEGMENTS = {"mall": "大型モール", "ec": "そのほか大手EC", "brand": "ブランド公式EC", "web": "WEBサービス"}
# every shop the calendar lists: id -> (name, one letter for the grid, segment).  A shop is listed only when a sale of it is confirmed (the malls: or expected).
ENT = {"rakuten": ("楽天市場", "楽", "mall"), "amazon": ("Amazon", "A", "mall"), "yahoo": ("Yahoo!ショッピング", "Y", "mall"),
       "yamada": ("ヤマダウェブコム", "ヤ", "ec"), "nitori": ("ニトリ", "ニ", "brand"), "dyson": ("ダイソン", "ダ", "brand"), "playstation": ("PlayStation公式", "P", "brand"),
       "sonystore": ("ソニーストア", "ソ", "brand"), "xserver": ("エックスサーバー", "X", "web"), "xdomain": ("XServerドメイン", "ド", "web")}
MALL_OF = {"楽天": "rakuten", "Amazon": "amazon", "Yahoo!ショッピング": "yahoo"}
MALL_PAGE = {"rakuten": "/rakuten/", "amazon": "/amazon/sale-calendar/", "yahoo": "/yahoo/"}
CAL_PATH = {"rakuten": "/calendar/rakuten/", "amazon": "/calendar/amazon/", "yahoo": "/calendar/yahoo/"}
KINDS = {"confirmed": ("確定", "●", "主催者が発表した日程です。"),
         "expected": ("例年の予想", "◇", "まだ発表がありません。毎年開かれているので、過去の日付をもとに「ごろ」で示しています。"),
         "regular": ("毎月の定例", "↻", "毎月決まった日に開かれる企画です。"),
         "notice": ("発表予定日", "▲", "主催者が、詳細を公表すると案内した日です。")}
GROUP_PAGE = {"rsup": "/rakuten/super-sale/", "rmar": "/rakuten/marathon/", "rbf": "/rakuten/black-friday/", "rhat": "/rakuten/hatsuuri/",
              "apd": "/amazon/prime-day/", "apde": "/amazon/prime-day-early/", "akan": "/amazon/prime-appreciation/", "akane": "/amazon/prime-appreciation/",
              "abf": "/amazon/black-friday/", "abfe": "/amazon/black-friday/", "ashin": "/amazon/sale-calendar/", "ahat": "/amazon/sale-calendar/",
              "ypp": "/yahoo/", "ybaku": "/yahoo/", "ybf": "/yahoo/"}

SRC_OFFICIAL = "主催者の公式発表"
SRC_PAGE = "公式ページの表示"
SRC_PRESS = "報道・解説記事(2件以上が一致)"


def d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(x)


def jpd(x, year=False) -> str:
    x = d(x)
    return (f"{x.year}年" if year else "") + f"{x.month}月{x.day}日({WD[x.weekday()]})"


def _t(t: str) -> str:
    return hm(t) if t else ""


def ev_item(ev: dict) -> dict:
    mall = MALL_OF[ev["mall"]]
    return {"id": ev["id"], "kind": "confirmed", "mall": mall, "title": ev["name"], "s": ev["start"], "e": ev["end"], "when": ev_span(ev), "note": ev.get("note", ""),
            "basis": [], "src": SRC_OFFICIAL if ev.get("read") != "summary" else SRC_PAGE, "checked": CHECKED, "announce": "", "href": GROUP_PAGE[ev["group"]]}


def C(id, mall, title, s, e, when, href, note="", src=SRC_PAGE, checked=VERIFIED):
    return {"id": id, "kind": "confirmed", "mall": mall, "title": title, "s": s, "e": e, "when": when, "note": note, "basis": [], "src": src, "checked": checked, "announce": "", "href": href}


def X(id, mall, title, when, href, basis, src=SRC_PRESS, s=None, e=None, month=None, note="", announce=""):
    """An expected entry: a day marker (s) with the words "ごろ", or a month only (month 'YYYY-MM') when the day moves from year to year."""
    return {"id": id, "kind": "expected", "mall": mall, "title": title, "s": s, "e": e or s, "mo": month, "when": when, "note": note, "basis": basis, "src": src,
            "checked": VERIFIED, "announce": announce, "href": href}


def N(id, mall, title, day, when, href, src, note=""):
    return {"id": id, "kind": "notice", "mall": mall, "title": title, "s": day, "e": day, "when": when, "note": note, "basis": [], "src": src, "checked": VERIFIED, "announce": "", "href": href}


def R(id, mall, title, rule, href, note, src, days=None, pattern=None, skip=(), checked=VERIFIED):
    """A regular entry: pattern = the days of the month (1, 5, 15 ...), or days = the dated days the mall lists."""
    return {"id": id, "kind": "regular", "mall": mall, "title": title, "when": rule, "note": note, "basis": [], "src": src, "checked": checked, "announce": "", "href": href,
            "pattern": pattern, "days": days, "skip": list(skip), "s": None, "e": None}


# The confirmed entries the site did not have before (the Yahoo! official guide read on VERIFIED).
EXTRA_CONFIRMED = [
    C("ybrand-2027-02", "yahoo", "ヤフショ Brand Weekクーポン・ポイントキャンペーン", "2027-02-09", "2027-02-15", "2027年2月9日(火)12時から2月15日(月)23時59分まで", "/yahoo/",
      note="ポイント企画のページは、2月9日12時に公開の予定です。"),
]

def _span(a: str, b: str, ta: str = "", tb: str = "") -> str:
    return f"{jpd(a, True)}{_t(ta)}から{jpd(b, a[:4] != b[:4])}{_t(tb)}まで"


PRESS2 = "報道(2件以上が一致)"
# Other shops (the daily report of the desk, 2026-11-12 pm; only the end day where the start day was not read).
EXTRA_CONFIRMED += [
    C("c-nitori-bf", "nitori", "ニトリ ブラックフライデー", "2026-10-30", "2026-11-24", _span("2026-10-30", "2026-11-24"), "", src=PRESS2),
    C("c-dyson-bf", "dyson", "ダイソン ブラックフライデー", "2026-10-30", "2026-12-01", _span("2026-10-30", "2026-12-01", "10:00", "10:00"), "", src=PRESS2),
    C("c-ps-1", "playstation", "PlayStation 第1弾", "2026-11-04", "2026-11-20", _span("2026-11-04", "2026-11-20"), "", src=PRESS2),
    C("c-ps-2", "playstation", "PlayStation 第2弾", "2026-11-16", "2026-11-30", _span("2026-11-16", "2026-11-30"), "", src=PRESS2),
    C("c-yamada-bf", "yamada", "ヤマダウェブコム セール", "2026-10-31", "2026-12-04", _span("2026-10-31", "2026-12-04"), "", src=PRESS2),
    C("c-sony-thanks", "sonystore", "ソニーストア Thanks Lot", "2026-10-01", "2027-01-13", _span("2026-10-01", "2027-01-13"), "", src=SRC_PAGE),
    C("c-xs-wp", "xserver", "エックスサーバー for WordPress キャンペーン(終了日)", "2026-12-15", "2026-12-15", f"{jpd('2026-12-15')}まで(開始日は確認していません)", "", src=PRESS2),
    C("c-xs-init", "xserver", "エックスサーバー Business 初期費用無料(終了日)", "2026-12-09", "2026-12-09", f"{jpd('2026-12-09')}まで(開始日は確認していません)", "", src=PRESS2),
    C("c-xd-jp", "xdomain", "XServerドメイン .jp キャンペーン(終了日)", "2027-01-29", "2027-01-29", f"{jpd('2027-01-29', True)}まで(開始日は確認していません)", "", src=PRESS2,
      note="価格の表記が情報源で食い違うため、日付だけを載せています。"),
]

EXPECTED = [
    X("x-rsup-2026-12", "rakuten", "楽天スーパーSALE 2026年12月", "12月4日(金)20時ごろから12月11日(金)1時59分ごろまで", "/rakuten/super-sale/",
      ["2025年12月は、4日(木)20時から11日(木)1時59分", "2026年は、3月・6月・9月とも4日の20時から11日の1時59分(6月は楽天の公式ページで確認)", "2024年は、3月・6月・9月・12月とも4日から11日"],
      s="2026-12-04", note="開催の日程は、まだ楽天の公式ページに出ていません。"),
    X("x-rsup-2027-03", "rakuten", "楽天スーパーSALE 2027年3月", "3月4日(木)20時ごろから3月11日(木)1時59分ごろまで", "/rakuten/super-sale/",
      ["2024年から2026年まで、3月は4日20時から11日1時59分"], s="2027-03-04"),
    X("x-rsup-2027-06", "rakuten", "楽天スーパーSALE 2027年6月", "6月4日(金)20時ごろから6月11日(金)1時59分ごろまで", "/rakuten/super-sale/",
      ["2024年から2026年まで、6月は4日20時から11日1時59分"], s="2027-06-04"),
    X("x-rsup-2027-09", "rakuten", "楽天スーパーSALE 2027年9月", "9月4日(土)20時ごろから9月11日(土)1時59分ごろまで", "/rakuten/super-sale/",
      ["2024年から2026年まで、9月は4日20時から11日1時59分"], s="2027-09-04"),
    X("x-rsup-2027-12", "rakuten", "楽天スーパーSALE 2027年12月", "12月4日(土)20時ごろから12月11日(土)1時59分ごろまで", "/rakuten/super-sale/",
      ["2024年と2025年の12月は、4日から11日"], s="2027-12-04"),
    X("x-rbf-2026", "rakuten", "楽天ブラックフライデー 2026", "11月20日(金)20時ごろから、およそ1週間", "/rakuten/black-friday/",
      ["2024年は、11月21日(木)20時から27日(水)1時59分", "2025年は、11月20日(木)20時から27日(木)1時59分", "告知は開始の1週間前から数日前でした(2024年は11月18日、2025年は11月12日)"],
      src="楽天の公式ニュース(過去2年の実績)", s="2026-11-20", note="2026年の日程は、まだ発表がありません。"),
    X("x-rbf-2027", "rakuten", "楽天ブラックフライデー 2027", "11月ごろ", "/rakuten/black-friday/", ["2024年と2025年は、どちらも11月下旬の20時に始まりました"],
      src="楽天の公式ニュース(過去2年の実績)", month="2027-11"),
    X("x-rhat-2027", "rakuten", "Rakuten初売り 2027", "1月1日(金)0時ごろから1月15日(金)9時59分ごろまで", "/rakuten/hatsuuri/",
      ["2024年と2025年は、1月1日0時から1月15日9時59分", "2026年は、1月1日0時から1月15日9時59分(楽天の公式ページで確認)"], s="2027-01-01"),
    X("x-abf-2026", "amazon", "Amazon ブラックフライデー 2026", "11月ごろ(日程は未発表)", "/amazon/black-friday/",
      ["Amazonは「11月に実施」と告知済みです。開催期間などは、11月19日(木)の午前に公開される予定です", "2025年は、先行セールが11月21日から23日、本セールが11月24日から12月1日", "2024年は、11月29日から12月6日"],
      src="Amazonの告知を伝える報道(2件)", month="2026-11", announce="11月19日(木)の午前(開催期間などの公開)", note="開催の月は告知済みですが、日付は発表されていません。"),
    X("x-abf-2027", "amazon", "Amazon ブラックフライデー 2027", "11月ごろ", "/amazon/black-friday/", ["2024年と2025年は、どちらも11月下旬に始まりました"], src=SRC_OFFICIAL + "(過去2年の実績)", month="2027-11"),
    X("x-ahat-2027", "amazon", "Amazon 初売り 2027", "1月3日(日)9時ごろから、およそ5日間", "/amazon/sale-calendar/",
      ["2025年は、1月3日(金)9時から7日(火)23時59分", "2026年は、1月3日(土)9時から7日(水)23時59分"], s="2027-01-03"),
    X("x-ashin-2027", "amazon", "Amazon 新生活セール 2027", "2月下旬から3月ごろ", "/amazon/sale-calendar/",
      ["2025年は、2月28日から3月4日と、3月28日から4月1日の2回", "2026年は、本セールが3月6日から9日"], month="2027-03"),
    X("x-apd-2027", "amazon", "プライムデー 2027", "7月10日(土)ごろ(先行セールは本セールの3日前から)", "/amazon/prime-day/",
      ["2025年は、本セールが7月11日から14日、先行セールが7月8日から", "2026年は、本セールが7月10日から13日、先行セールが7月7日から"], src=SRC_OFFICIAL + "(過去2年の実績)", s="2027-07-10",
      note="2026年の日程の発表は、開始の3週間ほど前の6月16日でした。"),
    X("x-akan-2027", "amazon", "プライム感謝祭 2027", "10月上旬から中旬ごろ", "/amazon/prime-appreciation/",
      ["2025年は、先行セールが10月4日から、本セールが10月7日から10日", "2026年は、先行セールが10月13日から、本セールが10月16日から19日"], month="2027-10"),
    X("x-ypp-2027-03", "yahoo", "超PayPay祭 2027年3月", "3月3日(水)12時ごろから、3週間ほど", "/yahoo/",
      ["2025年は、3月3日12時から23日", "2026年は、3月3日12時から22日"], s="2027-03-03"),
    X("x-ypp-2026-12", "yahoo", "Yahoo!ショッピング 12月の大型企画(名称は未発表)", "12月(日程は未発表)", "/yahoo/",
      ["公式のお得ガイドに「2026/12〜 大型企画 最大25%」と書かれています。日程と内容は、変更の可能性ありと添えられています", "2025年12月の超PayPay祭は、12月1日12時から15日"],
      src="Yahoo!ショッピングの公式ページ(お得ガイド)", month="2026-12", note="日付は、公式にもまだ出ていません。"),
    X("x-ypp-2027-07", "yahoo", "超PayPay祭 2027年夏", "6月下旬から7月上旬ごろ", "/yahoo/",
      ["2025年は、7月1日から27日", "2026年は、6月26日12時から7月12日"], month="2027-07"),
]

NOTICES = [
    N("n-ybf-2026", "yahoo", "ブラックフライデー 2026 の条件・上限などを事前公開", "2026-11-16", "11月16日(月)12時", "/yahoo/", "報道(スマートウォッチライフ)",
      note="一部の目玉商品も、この時刻から特設ページで先に公開される予定と伝えられています。"),
    N("n-abf-2026", "amazon", "ブラックフライデー 2026 の開催期間などを公開", "2026-11-19", "11月19日(木)の午前", "/amazon/black-friday/", "Amazonの告知を伝える報道(2件)",
      note="Amazonは「11月に実施」とだけ告知しています。"),
]

REGULAR = [
    R("r-rak-50", "rakuten", "5と0のつく日", "毎月5・10・15・20・25・30日", "/rakuten/pointday/",
      "楽天のクレジット払いで楽天市場を使うと、特典の1倍が足されます。エントリーが必要で、特典の上限は月1,000ポイントです。2月に30日はありません。", "楽天の案内", pattern=[5, 10, 15, 20, 25, 30],
      checked=CHECKED),
    R("r-rak-w", "rakuten", "ワンダフルデー", "毎月1日", "/rakuten/", "エントリーして、合計の購入額が条件に届くと、全ショップのポイントが3倍になります。条件の金額は、楽天の公式ページにあります。クーポンは前日の朝10時から配られます。",
      "楽天の公式ページ", pattern=[1]),
    R("r-yah-1", "yahoo", "ファーストデイ", "毎月1日", "/yahoo/", "「プレミアムな日曜日」や「爆買WEEK」と重なる月は開かれません。", "Yahoo!ショッピングの公式ページ(お得ガイド)", pattern=[1]),
    R("r-yah-5", "yahoo", "5のつく日", "毎月5・15・25日", "/yahoo/", "2026年9月5日から、期間限定PayPayポイントの上限が、1人あたりの額で決まっています。額は、公式のお得ガイドにあります。2026年11月25日は、ブラックフライデーのため開かれません。",
      "Yahoo!ショッピングの公式ページ(お得ガイド)", pattern=[5, 15, 25], skip=["2026-11-25"]),
    R("r-yah-29", "yahoo", "ニクの日キャンペーン", "原則毎月29日", "/yahoo/", "不定期の開催で、中止になる月があります。", "Yahoo!ショッピングの公式ページ(お得ガイド)", pattern=[29]),
    R("r-yah-sun", "yahoo", "プレミアムな日曜日", "公式が日付を挙げている日", "/yahoo/", "公式は、2026年12月の6日・13日・27日を挙げています。", "Yahoo!ショッピングの公式ページ(お得ガイド)",
      days=["2026-12-06", "2026-12-13", "2026-12-27"]),
    R("r-yah-kan", "yahoo", "ヤフショ感謝デー", "公式が日付を挙げている日", "/yahoo/", "公式は、2026年12月の11日・22日を挙げています。エントリーが必要です。", "Yahoo!ショッピングの公式ページ(お得ガイド)",
      days=["2026-12-11", "2026-12-22"]),
]


# ------------------------------------------------------------------ assembling
def all_items() -> list[dict]:
    from sites.kaidoki.gen import facts
    items = [ev_item(ev) for ev in facts.EVENTS if ev["end"] >= "2026-01-01"] + [dict(x) for x in EXTRA_CONFIRMED] + [dict(x) for x in EXPECTED] + [dict(x) for x in NOTICES]
    for r in REGULAR:
        r = dict(r)
        if r["pattern"]:
            days, x = [], REGULAR_FROM
            while x <= REGULAR_TO:
                if x.day in r["pattern"] and x.isoformat() not in r["skip"]:
                    days.append(x.isoformat())
                x += timedelta(days=1)
            r["days"] = days
        items.append(r)
    for it in items:
        it.setdefault("mo", None)
        it.setdefault("days", None)
    return items


def for_mall(items: list[dict], mall: str | None) -> list[dict]:
    return [i for i in items if not mall or i["mall"] == mall]


def covers(it: dict, day: date) -> bool:
    if it.get("days") is not None:
        return day.isoformat() in it["days"]
    if it.get("s"):
        return d(it["s"]) <= day <= d(it["e"] or it["s"])
    return False


def months() -> list[str]:
    y, m = map(int, MIN_YM.split("-"))
    out = []
    while f"{y}-{m:02d}" <= MAX_YM:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def payload(items: list[dict]) -> str:
    rows = []
    for it in items:
        row = {"id": it["id"], "k": it["kind"], "m": it["mall"], "g": ENT[it["mall"]][2], "t": it["title"], "w": it["when"], "h": it["href"]}
        if it.get("days") is not None:
            row["d"] = it["days"]
        elif it.get("s"):
            row["s"], row["e"] = it["s"], it["e"] or it["s"]
        if it["kind"] == "expected" and it.get("s"):
            row["e"] = it["s"]                          # an expected entry marks its first day only
        rows.append(row)
    return json.dumps({"items": rows, "min": MIN_YM, "max": MAX_YM, "ent": {k: [v[0], v[1]] for k, v in ENT.items()}, "seg": SEGMENTS}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ------------------------------------------------------------------ html
def e(v) -> str:
    return escape(str(v), quote=True)


def mark(it: dict) -> str:
    label, sym, _ = KINDS[it["kind"]]
    mall_title, letter, _ = ENT[it["mall"]]
    return (f'<li class="cal-mk k-{it["kind"]}" title="{e(mall_title)} {e(label)} {e(it["title"])}"><span aria-hidden="true">{letter}{sym}</span>'
            f'<span class="sr">{e(mall_title)} {e(label)} {e(it["title"])}</span></li>')


def grid(ym: str, items: list[dict], today: date) -> str:
    y, m = map(int, ym.split("-"))
    first = date(y, m, 1)
    start = first - timedelta(days=first.weekday())
    rows = ""
    cur = start
    while cur <= date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1) or cur.weekday() != 0:
        if cur.weekday() == 0:
            rows += "<tr>"
        inm = cur.month == m
        todays = [it for it in items if covers(it, cur)] if inm else []
        todays.sort(key=lambda it: 0 if (it.get("days") is not None or it.get("s") == cur.isoformat()) else 1)      # the sales that start on the day first, the ones running on after
        marks = "".join(mark(it) for it in todays[:3]) + (f'<li class="cal-more">+{len(todays) - 3}</li>' if len(todays) > 3 else "")
        cls = "cal-day" + ("" if inm else " is-out") + (" is-today" if cur == today else "") + (" has-ev" if todays else "")
        label = f"{cur.month}月{cur.day}日" if inm else ""
        rows += (f'<td class="{cls}" data-date="{cur.isoformat()}"' + (f' aria-label="{label}"' if inm else ' aria-hidden="true"') + f'><span class="cal-num">{cur.day if inm else ""}</span>'
                 + (f'<ul class="cal-mks">{marks}</ul>' if marks else "") + "</td>")
        if cur.weekday() == 6:
            rows += "</tr>"
        cur += timedelta(days=1)
    head = "".join(f'<th scope="col" class="{"sat" if i == 5 else "sun" if i == 6 else ""}">{c}</th>' for i, c in enumerate(WD))
    return f'<table class="cal-grid"><caption class="sr">{y}年{m}月のカレンダー</caption><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def legend() -> str:
    return ('<ul class="cal-legend" aria-label="凡例">' + "".join(
        f'<li><span class="cal-mk k-{k}"><span aria-hidden="true">{sym}</span></span><strong>{e(label)}</strong><span>{e(txt)}</span></li>' for k, (label, sym, txt) in KINDS.items())
        + '<li class="cal-legend-mall"><span class="cal-mk k-letters"><span aria-hidden="true">楽 A Y</span></span><span>マークの文字は店名の頭文字です(楽は楽天市場、AはAmazon、YはYahoo!ショッピング)。マークに触れると、正式な名前が表示されます。</span></li></ul>')


def controls(mall: str | None, items: list[dict]) -> str:
    kinds = "".join(f'<label><input type="checkbox" data-kind="{k}" checked> {sym} {e(label)}</label>' for k, (label, sym, _) in KINDS.items())
    present = {it["mall"] for it in items}
    segs = "" if mall else "".join(f'<label><input type="checkbox" data-seg="{k}" checked> {e(t)}</label>' for k, t in SEGMENTS.items() if any(ENT[m][2] == k for m in present))
    malls = "" if mall else ("".join(f'<label><input type="checkbox" data-mall="{k}" checked> {e(t)}</label>' for k, (t, _) in MALLS.items()))
    return (f'<div class="cal-controls" hidden><fieldset><legend>種類</legend>{kinds}</fieldset>' + (f'<fieldset><legend>区分</legend>{segs}</fieldset>' if segs else "") + (f'<fieldset><legend>大型モール</legend>{malls}</fieldset>' if malls else "") + "</div>")


def item_li(it: dict) -> str:
    label, sym, _ = KINDS[it["kind"]]
    mall_title = ENT[it["mall"]][0]
    dates = ""
    if it.get("s") and it["kind"] != "regular":
        dates = f' data-s="{it["s"]}" data-e="{it["e"] or it["s"]}"'
    extra = f'<p class="cal-note">{e(it["note"])}</p>' if it.get("note") else ""
    ann = f'<p class="cal-note">公式が発表を予定している日時は、{e(it["announce"])}です。</p>' if it.get("announce") else ""
    basis = ""
    if it.get("basis"):
        basis = '<details class="cal-basis"><summary>予想の根拠(過去の実績)</summary><ul>' + "".join(f"<li>{e(b)}</li>" for b in it["basis"]) + "</ul></details>"
    return (f'<li class="cal-item k-{it["kind"]}" data-mall="{it["mall"]}" data-seg="{ENT[it["mall"]][2]}" data-kind="{it["kind"]}"{dates}><div class="cal-head"><span class="cal-badge k-{it["kind"]}">{sym} {e(label)}</span>'
            f'<span class="cal-mall">{e(mall_title)}</span><span class="cal-seg">{e(SEGMENTS[ENT[it["mall"]][2]])}</span><span class="cal-live" data-live></span></div>'
            f'<h4>{f'<a href="{e(it["href"])}">{e(it["title"])}</a>' if it["href"] else e(it["title"])}</h4><p class="cal-when">{e(it["when"])}</p>{extra}{ann}{basis}'
            f'<p class="cal-src">出典の種類: {e(it["src"])} ／ 確認日 {e(it["checked"].replace("-", "/"))}</p></li>')


def month_section(ym: str, items: list[dict], shown: bool) -> str:
    y, m = map(int, ym.split("-"))
    a, b = date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    dated, regs, undated = [], [], []
    for it in items:
        if it["kind"] == "regular":
            ds = [x for x in (it["days"] or []) if a <= d(x) <= b]
            if ds:
                regs.append((it, ds))
        elif it.get("s"):
            if d(it["s"]) <= b and d(it["e"] or it["s"]) >= a:
                dated.append(it)
        elif it.get("mo") == ym:
            undated.append(it)
    dated.sort(key=lambda it: (it["s"], it["title"]))
    out = ""
    if dated:
        out += '<ul class="cal-list">' + "".join(item_li(it) for it in dated) + "</ul>"
    if regs:
        out += '<h4 class="cal-sub">毎月の定例</h4><ul class="cal-list">' + "".join(
            item_li(dict(it, when=it["when"] + ": この月は " + "・".join(f"{d(x).day}日" for x in ds))) for it, ds in regs) + "</ul>"
    if undated:
        out += '<h4 class="cal-sub">日付が決まっていないもの</h4><ul class="cal-list">' + "".join(item_li(it) for it in undated) + "</ul>"
    if not out:
        out = '<p class="cal-empty">この月に載せられる予定は、いまのところありません。未発表の予定は推測しません。</p>'
    return f'<section class="cal-month" id="m-{ym}" data-month="{ym}"' + ("" if shown else " hidden") + f'><h3>{y}年{m}月の予定</h3>{out}</section>'


def calendar_block(items: list[dict], mall: str | None, today: date) -> str:
    """The month grid (first view: the month of `today`), the controls the script shows, the list of every month (the script shows one) and the data."""
    ym = f"{today.year}-{today.month:02d}"
    y, m = today.year, today.month
    its = for_mall(items, mall)
    name = MALLS[mall][0] if mall else "全モール・全ショップ"
    bar = (f'<div class="cal-bar"><button type="button" class="small-btn cal-prev" aria-label="前の月">← 前の月</button><h3 class="cal-title" aria-live="polite">{y}年{m}月</h3>'
           f'<button type="button" class="small-btn cal-next" aria-label="次の月">次の月 →</button><button type="button" class="small-btn cal-today">今月へ</button></div>')
    secs = "".join(month_section(x, its, x == ym) for x in months())
    return (f'<div class="cal" data-cal data-mall="{mall or "all"}" data-ym="{ym}" data-min="{MIN_YM}" data-max="{MAX_YM}"><p class="cal-name">{e(name)}のカレンダー</p>{bar}{controls(mall, its)}'
            f'<div class="tablewrap cal-scroll">{grid(ym, its, today)}</div>{legend()}'
            f'<div class="cal-detail" aria-live="polite" hidden></div>'
            f'<div class="cal-lists"><p class="cal-listlead">下の一覧は、カレンダーの月に合わせて切り替わります。スクリプトが動かないときは、すべての月の予定が日付順に続きます。</p>'
            f'<p class="cal-all" hidden><button type="button" class="small-btn cal-showall">すべての月を表示する</button></p>{secs}</div>'
            f'<script type="application/json" class="cal-data">{payload(its)}</script></div>')


def regular_table(items: list[dict], mall: str | None) -> str:
    rows = ""
    for it in for_mall(items, mall):
        if it["kind"] != "regular":
            continue
        nxt = " ".join(it["days"] or [])
        rows += (f'<tr data-next="{e(nxt)}"><th scope="row">{f'<a href="{e(it["href"])}">{e(it["title"])}</a>' if it["href"] else e(it["title"])}<br><small>{e(ENT[it["mall"]][0])}</small></th><td>{e(it["when"])}</td>'
                 f'<td>{e(it["note"])}</td><td><span class="cal-next-day" data-next-day></span></td><td>{e(it["src"])}<br><small>確認日 {e(it["checked"].replace("-", "/"))}</small></td></tr>')
    if not rows:
        return ""
    return ('<div class="tablewrap"><table class="cal-table"><caption>毎月の定例</caption><thead><tr><th scope="col">名前</th><th scope="col">開かれる日</th><th scope="col">条件</th>'
            '<th scope="col">次の日</th><th scope="col">出典の種類</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def basis_table(items: list[dict], mall: str | None) -> str:
    rows = ""
    for it in for_mall(items, mall):
        if it["kind"] != "expected":
            continue
        rows += (f'<tr><th scope="row">{f'<a href="{e(it["href"])}">{e(it["title"])}</a>' if it["href"] else e(it["title"])}<br><small>{e(ENT[it["mall"]][0])}</small></th><td>{e(it["when"])}</td>'
                 f'<td><ul>{"".join(f"<li>{e(b)}</li>" for b in it["basis"])}</ul></td><td>{e(it["src"])}</td></tr>')
    if not rows:
        return ""
    return ('<div class="tablewrap"><table class="cal-table"><caption>例年の予想と、その根拠</caption><thead><tr><th scope="col">名前</th><th scope="col">予想</th><th scope="col">過去の実績</th>'
            '<th scope="col">出典の種類</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def counts(items: list[dict]) -> dict:
    out: dict = {}
    for it in items:
        out.setdefault(it["mall"], {}).setdefault(it["kind"], 0)
        out[it["mall"]][it["kind"]] += 1
        if it["kind"] == "regular":
            out[it["mall"]]["regular_days"] = out[it["mall"]].get("regular_days", 0) + len(it["days"] or [])
    return out
