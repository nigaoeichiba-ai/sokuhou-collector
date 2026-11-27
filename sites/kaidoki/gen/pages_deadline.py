"""The 締切カレンダー corner: /deadline/ (all deadlines of the year-end by kind) and /deadline/december/ (the last deadlines of the year, in December).
Everything comes from deadlines.json; the days left and the move to 'すぎた締切' are computed on the day of the build."""
from __future__ import annotations

from html import escape

from . import deadlines as DL
from .common import TODAY, jp
from .kit import R, S, T, page

GROUPS = ("年賀状", "おせち", "クリスマスケーキ", "ふるさと納税", "福袋", "宅配", "旅行", "セール")


GROUP_LEAD = {
    "年賀状": "年賀状には、印刷を注文する締切と、郵便で元日に届けるための差出日の目安があります。",
    "おせち": "おせちは、店ごとに、早割・宅配・店頭受取の締切が分かれています。",
    "クリスマスケーキ": "クリスマスケーキは、早期予約の締切と、受け取る日ごとの予約の締切が別です。",
    "ふるさと納税": "ふるさと納税には、今年の控除にするための寄附の最終日と、手続きの期限があります。",
    "福袋": "福袋の締切です。",
    "宅配": "宅配の年内の受付の締切です。",
    "旅行": "旅行は、クーポンの配布期間の終わりが締切です。",
    "セール": "モールのセールは、終わる日時が締切です。",
}


def links_html(r: dict) -> str:
    from sites.kaidoki.redesign import affiliate as AFF
    links = AFF.product_links({"slug": "", "crumb": ""}, {"aff": r.get("aff", []), "name": ""})
    return AFF.lines(links)


def item_html(r: dict) -> str:
    past = DL.over(r)
    head = f"{DL.when(r)}まで({DL.KINDS[r['kind']]})" if not past else f"{DL.when(r)}で終わりました({DL.KINDS[r['kind']]})"
    left = "" if past else f"・{DL.until(r)}"
    live = "" if past or r.get("notime") else f' data-deadline="{r["dt"].strftime("%Y-%m-%dT%H:%M")}"'      # site.js turns it over on the visitor's clock
    until = "" if past else f' data-until="{r["dt"].strftime("%Y-%m-%dT%H:%M")}"'      # site.js picks the next 最も近い締切 from these
    return (f'<div class="dl-item"{live}{until}><h3>{escape(r["title"])}</h3><p><strong>{escape(head)}</strong>{escape(left)}</p><p>{escape(r["what"])}</p>'
            f'{"" if past else links_html(r)}<p class="stamp">確認日 {escape(jp(r["checked"]))}</p></div>')


def table(rows: list[dict], caption: str) -> dict:
    return T(caption, ["締切", "種類", "内容", "残り"], [[DL.when_short(r), DL.KINDS[r["kind"]], r["title"], DL.until(r)] for r in rows])


def groups_html(rows: list[dict], group_links: bool = True) -> str:
    from sites.kaidoki.redesign import affiliate as AFF
    ga = DL.group_aff()
    out = ""
    for g in GROUPS:
        items = [r for r in rows if r.get("group") == g]
        if items:
            out += f"<h3>{escape(g)}</h3><p>{escape(GROUP_LEAD[g])}</p>" + "".join(item_html(r) for r in items)
            if group_links and g in ga:
                out += AFF.lines(AFF.product_links({"slug": "", "crumb": ""}, {"aff": ga[g], "name": ""}))
    return out


KIND_TEXT = (
    ("早割終了", "早割の割引が付く、予約・注文の最後の日のことです。過ぎると値段が戻るので、買うと決めているなら、この日が実質の期限になります。"),
    ("キャンセル・変更期限", "無料で取り消しや変更ができる、最後の日のことです。過ぎるとキャンセル料や手数料がかかる場合があります。"),
    ("受付終了", "予約・注文そのものができなくなる日のことです。年内に受け取りたい物や、年内に済ませたい手続きの最終日にあたります。"),
)


def pages() -> list[dict]:
    rows = DL.load()
    up = DL.coming(rows)
    gone = DL.passed(rows)
    dec = DL.of_month(up, 2026, 12)
    first = up[0] if up else None
    n = len(up)
    lead = (f"最も近い締切は、{first['title']}({DL.when_short(first)}、{DL.until(first)})です。" if first else "いま、確認できている年内の締切はありません。")
    by_kind = {k: [r for r in up if r["kind"] == k] for k in DL.KIND_ORDER}

    hub_secs = [
        S("これから近づく締切を日付順に", f"{jp(TODAY)}の時点で、公式ページで確かめた年内の締切を、近い順に並べました。種類は「早割終了」「キャンセル・変更期限」「受付終了」の3つです。締切の日付は、各社の表記どおりの最後の時刻です。",
          table=table(up, f"年内の締切(これから{n}件)")),
        S("3つの種類のちがい", *[f"「{k}」とは、{t}" for k, t in KIND_TEXT]),
    ]
    for k in DL.KIND_ORDER:
        if by_kind[k]:
            hub_secs.append(S(f"{DL.KINDS[k]}の締切", "", html=groups_html(by_kind[k], False)))
    if gone:
        hub_secs.append(S("すぎた締切", "締切が過ぎたものは、ここに移ります。来年の目安にもなるので、日付は残しています。", table=table(gone, f"すぎた締切({len(gone)}件)")))
    for s in hub_secs:
        if s.get("paras") == [""]:
            s.pop("paras")
    hub = page(
        "/deadline/", "hub", "/", "年内の締切", "年内の締切カレンダー|早割終了・キャンセル期限・受付終了を日付順に",
        "年内の締切カレンダー(早割・キャンセル期限・受付終了)",
        "年賀状、おせち、クリスマスケーキ、ふるさと納税などの年内の締切を、早割終了・キャンセル期限・受付終了の3種に分けて日付順に並べました。公式ページで確かめた日付だけを載せています。",
        lead, hub_secs,
        [R("/deadline/december/", "12月の年内最後の締切"), R("/calendar/", "セール日程の一覧"), R("/calc/", "実質価格の計算ツール"), R("/buytime/", "買い時のハブ")],
        intent=1, secondary=["年賀状 締切", "おせち 予約 締切", "ふるさと納税 年内 いつまで"], basis=f"各社の公式ページ({jp(TODAY)}時点)",
    )
    over_all = not dec
    if over_all:
        dec = DL.of_month(rows, 2026, 12)      # every December deadline has passed: the page keeps them (dates stay useful next year) instead of becoming empty
    dec_title = (f"12月の締切{len(dec)}本" if not over_all else "12月の締切(終了分)") if dec else "12月の締切"
    dec_secs = [
        S("日付順の一覧", (f"12月に締切が来るものを、近い順に{len(dec)}本並べました。今日は{jp(TODAY)}です。残りの日数は、日付から計算しています。" if not over_all
                      else f"2026年12月の締切{len(dec)}本は、{jp(TODAY)}の時点ですべて過ぎています。来年の予定を立てる手がかりとして、日付を残しています。"), table=table(dec, f"12月の年内最後の締切({len(dec)}本)")),
        S("締切のあと、どうするか", "", html=groups_html(dec)),
        S("締切の読み方", "同じ「締切」でも、種類で意味が違います。早割は値段が戻る日、キャンセル・変更期限は無料で取り消せる最後の日、受付終了は注文そのものができなくなる日です。",
          "公式が「25時59分」のように24時を超えて書く場合は、翌日の1時59分までのことです。店舗や商品によって締切が違うものは、一番早い日を載せず、公式ページで確かめられた代表の日だけを載せています。申し込む前に、商品のページで確かめておきましょう。"),
    ]
    for s in dec_secs:
        if s.get("paras") == [""]:
            s.pop("paras")
    december = page(
        "/deadline/december/", "article", "/deadline/", "12月の締切", f"{dec_title}|年賀状・おせち・ふるさと納税など年内最後の期限",
        ("12月の締切" + (f"{len(dec)}本" if dec else "") + "(年内最後の期限)") if not over_all else "12月の締切の記録(2026年分は終了)",
        f"年賀状、おせち、クリスマスケーキ、ふるさと納税など、12月に締切が来る年内最後のものを日付順にまとめました。各社の公式ページで確かめた日付と、締切のあとの動き方を載せています。",
        ((f"12月の締切は{len(dec)}本です。最初は{dec[0]['title']}({DL.when_short(dec[0])})、最後は{dec[-1]['title']}({DL.when_short(dec[-1])})です。" if not over_all
          else f"2026年12月の締切{len(dec)}本は、すべて過ぎています。以下は当時の日付の記録です。") if dec else lead),
        dec_secs, [R("/deadline/", "年内の締切カレンダー"), R("/calendar/", "セール日程の一覧"), R("/rakuten/", "楽天のセール")],
        intent=1, secondary=["年賀状 締切", "ふるさと納税 年内 いつまで", "おせち 予約 締切"], basis=f"各社の公式ページ({jp(TODAY)}時点)",
    )
    return [hub, december]
