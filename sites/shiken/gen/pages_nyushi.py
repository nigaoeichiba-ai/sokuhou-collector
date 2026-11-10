"""University entrance pages: the Common Test (dates, fee, the make-up days) and the national / public universities' general selection.
Only what the Centre and the University of Tokyo print on their own pages is a date here; the rest of the common schedule is linked, not guessed."""
from __future__ import annotations

from datetime import date

from . import common
from .common import jp, md, span, left, in_days, today_j
from .pages_exam import dates_table, drow, official


def art(path, kw, title, h1, desc, answer, secs, related, sources, basis, intent=1, secondary=(), kind="analysis"):
    return {"path": path, "kind": kind, "parent": "/nyushi/", "primary_kw": kw, "secondary_kw": list(secondary), "intent": intent,
            "title": title, "h1": h1, "description": desc, "answer": answer, "data_basis": basis, "sections": secs, "related": related, "sources": sources}


def kyotsu() -> dict:
    gap = (date(2027, 1, 16) - common.TODAY).days
    return art(
        "/kyotsu/", "共通テストの日程", "共通テストの日程 2027年1月16・17日と検定料(令和9年度)", "共通テストの日程・検定料・成績の見方(令和9年度)",
        "令和9年度の大学入学共通テストの日程です。本試験は2027年1月16日と17日、追・再試験は1月23日と24日。出願は10月2日に終わっています。検定料と成績の閲覧期間も、大学入試センターの公式ページで確かめて載せています。",
        f"令和9年度の共通テストは、{jp('2027-01-16')}と{md('2027-01-17')}です。出願は2026年10月2日に終了しています。",
        [
            {"h2": "令和9年度の日程", "paras": [
                f"本試験は{jp('2027-01-16')}と{jp('2027-01-17')}の2日間です。今日({jp(common.TODAY)})から数えて、{gap}日後に始まります。",
                "出願はすでに終わっています。登録とマイページの作成は2026年10月2日の17時まで、検定料などの支払は同日の23時59分まででした。これから新しく出願することはできません。出願内容の確認と訂正は、10月9日から10月16日の間でした。"],
             "table": dates_table("令和9年度 大学入学共通テストの日程", [
                 drow("出願の登録・支払の開始", "2026-09-15"), drow("出願の締切(登録は17時、支払は23時59分)", "2026-10-02"),
                 drow("出願内容の確認・訂正の最終日", "2026-10-16"), drow("本試験の1日目", "2027-01-16"), drow("本試験の2日目", "2027-01-17"),
                 drow("追・再試験の1日目", "2027-01-23"), drow("追・再試験の2日目", "2027-01-24"), drow("成績の閲覧の開始", "2027-04-01"), drow("成績の閲覧の終了", "2027-04-30")],
                 "マイページの作成は7月1日の10時から始まっていました。")},
            {"h2": "検定料", "paras": [
                "検定料は、受験する教科の数で決まります。3教科以上を受ける場合は18,000円、2教科以下の場合は12,000円です。このほかに、支払手数料の188円がかかります。",
                "成績の閲覧を出願のときに希望した場合は、閲覧手数料の300円もかかります。成績の郵送は行われません。マイページで、4月1日から4月30日の間に確認できます。"],
             "table": {"caption": "令和9年度 共通テストの検定料と手数料", "cols": ["区分", "金額"], "num_cols": [1],
                       "rows": [["3教科以上を受験", "18,000円"], ["2教科以下を受験", "12,000円"], ["支払手数料", "188円"], ["成績閲覧手数料(希望者のみ)", "300円"]],
                       "note": "金額は大学入試センターの実施要項と出願サイトの記載です。"}},
            {"h2": "これから受験生が確認すること", "paras": [
                "出願が終わった今は、試験会場と受験票を確かめる時期です。受験票は、センターの案内に従って届きます。試験会場は、出願のときに選んだ地域で決まります。",
                f"本試験を受けられなかった場合の追・再試験は、{jp('2027-01-23')}と{md('2027-01-24')}です。条件と手続きは、別のページで確認できます。"]},
            {"h2": "最終確認は公式で", "paras": ["日程と金額の確認日は2026年11月3日です。当日の持ち物は、受験票と筆記用具が中心です。試験場では、受験票に書かれた注意が適用されます。"],
             "html": official(("令和9年度 試験情報(大学入試センター)", "https://www.dnc.ac.jp/kyotsu/shiken_jouhou/r9/index.html"))},
        ],
        [{"path": "/kyotsu-tsuishi/", "text": "共通テストの追試験(追・再試験)"}, {"path": "/kokkoritsu/", "text": "国公立大学の出願期間"}, {"path": "/yama/", "text": "2026年11月から2027年3月の試験の山"},
         {"path": "/nyushi/", "text": "入試カレンダー(大学・高校)"}], ["dnc"], "令和9年度(2027年1月実施)", secondary=("共通テスト 日程 2027", "共通テスト 出願", "共通テスト 検定料")) | {"parent": "/nyushi/"}


def tsuishi() -> dict:
    return art(
        "/kyotsu-tsuishi/", "共通テストの追試験", "共通テストの追試験(追・再試験)の日程 2027年1月23・24日", "共通テストの追試験(追・再試験) 2027年の日程",
        "令和9年度の共通テストの追・再試験は、2027年1月23日と24日です。本試験の1週間後にあたります。誰が受けられるか、国公立大学の出願が始まる前に結果が出るのかを、日付で整理しました。",
        f"令和9年度の共通テストの追・再試験は、{jp('2027-01-23')}と{md('2027-01-24')}です。本試験の7日後です。",
        [
            {"h2": "日程", "paras": [
                f"本試験は{jp('2027-01-16')}と{md('2027-01-17')}です。追・再試験は、その翌週の{jp('2027-01-23')}と{md('2027-01-24')}に、同じ2日間の形で行われます。",
                f"東京大学の一般選抜の出願は{jp('2027-01-25')}から始まります。追・再試験の2日目の翌日です。追・再試験を受ける場合は、結果を待たずに、国公立大学の出願へ進むことになります。"],
             "table": {"caption": "本試験と追・再試験の日付の関係", "cols": ["日", "できごと", f"{today_j()}から"], "rows": [
                 [jp("2027-01-16"), "本試験の1日目", in_days("2027-01-16")], [jp("2027-01-17"), "本試験の2日目", in_days("2027-01-17")],
                 [jp("2027-01-23"), "追・再試験の1日目", in_days("2027-01-23")], [jp("2027-01-24"), "追・再試験の2日目", in_days("2027-01-24")],
                 [jp("2027-01-25"), "東京大学の出願の開始", in_days("2027-01-25")]]}},
            {"h2": "追試験と再試験の違い", "paras": [
                "追試験は、病気やけがなど、やむを得ない理由で本試験を受けられなかった方のための試験です。再試験は、本試験の最中に、試験場の事故などで正しく受けられなかった場合の試験です。",
                "どちらを受けられるかは、理由と手続きで決まります。受験案内に、必要な書類と連絡の期限が書かれています。迷ったときの連絡先は、受験票に書かれたセンターの窓口です。"]},
            {"h2": "本試験を受けられなかったときの順番", "paras": [
                "まず、受験票に書かれた連絡先とセンターの案内に連絡します。次に、必要な書類を出します。出願先の大学にも、追・再試験を受ける旨を伝えておくと、大学の手続きとずれません。",
                "追・再試験の成績は、本試験と同じ形で大学に送られます。大学ごとに、追・再試験の成績の使い方は募集要項に出ています。"]},
            {"h2": "最終確認は公式で", "paras": ["日付の確認日は2026年11月3日です。手続きの窓口は、大学入試センターです。"],
             "html": official(("令和9年度 試験情報(大学入試センター)", "https://www.dnc.ac.jp/kyotsu/shiken_jouhou/r9/index.html"))},
        ],
        [{"path": "/kyotsu/", "text": "共通テストの日程と検定料"}, {"path": "/kokkoritsu/", "text": "国公立大学の出願期間"}, {"path": "/zenki-koki/", "text": "国公立の前期日程と後期日程の違い"},
         {"path": "/nyushi/", "text": "入試カレンダー(大学・高校)"}], ["dnc", "utokyo"], "令和9年度(2027年1月実施)", intent=4)


def kokkoritsu() -> dict:
    return art(
        "/kokkoritsu/", "国公立大学の出願期間", "国公立大学の出願期間 2027(東京大学の例と、共通テストからの流れ)", "国公立大学の出願期間 2027年度入試の流れ",
        "国公立大学の一般選抜は、共通テストのあとの1月下旬に出願が始まります。東京大学の令和9年度の出願期間は1月25日から2月3日、試験は2月25日から。共通テストからの日付を並べました。",
        f"東京大学の令和9年度の出願期間は、{md('2027-01-25')}から{md('2027-02-03')}です。試験は{md('2027-02-25')}から、合格発表は{md('2027-03-10')}です。",
        [
            {"h2": "共通テストから合格発表までの日付(東京大学の例)", "paras": [
                f"共通テストの本試験は{md('2027-01-16')}と{md('2027-01-17')}です。東京大学の出願は{jp('2027-01-25')}に始まり、{jp('2027-02-03')}に終わります。共通テストの最初の日から、出願の開始まで9日です。",
                f"東京大学は、第1段階選抜の合格者を{md('2027-02-10')}に発表します。第2次学力試験は{md('2027-02-25')}と{md('2027-02-26')}で、理科三類だけは{md('2027-02-27')}にもあります。合格発表は{jp('2027-03-10')}の12時ごろです。"],
             "table": dates_table("東京大学 令和9年度 一般選抜の日付", [
                 drow("共通テスト 本試験の1日目", "2027-01-16"), drow("出願の開始", "2027-01-25"), drow("出願の締切", "2027-02-03"), drow("第1段階選抜の合格者発表", "2027-02-10"),
                 drow("第2次学力試験の1日目", "2027-02-25"), drow("第2次学力試験の2日目", "2027-02-26"), drow("合格者発表", "2027-03-10")],
                 "第2次学力試験の27日は理科三類のみ。検定料は11月中旬に公表される募集要項で確認してください。")},
            {"h2": "出願期間は大学ごとに決まる", "paras": [
                "国公立大学の出願期間は、すべての大学で同じではありません。上の表は東京大学の日付です。ほかの大学の日程は、その大学が出す募集要項(入学者選抜要項)に出ています。",
                "募集要項が公表される前の大学の出願期間は、まだ公表されていません。公表されたことを公式ページで確かめてから、日付を足します。"]},
            {"h2": "郵送か、インターネットか", "paras": [
                "出願の方法は、大学ごとに、郵送かインターネットかが決まっています。郵送の場合は、締切の扱い(消印か必着か)で、実質的な締切日が変わります。",
                "大学の募集要項に書かれた「必着」の文字を見落とすと、出願の最終日に投函しても間に合いません。消印と必着の違いは、別のページで確認できます。"]},
            {"h2": "最終確認は公式で", "paras": ["確認日は2026年11月3日です。志望する大学の日付は、公式ページと募集要項に出ています。"],
             "html": official(("令和9年度 一般選抜(東京大学)", "https://www.u-tokyo.ac.jp/ja/admissions/undergraduate/e01_02_01.html"), ("大学入学者選抜について(文部科学省)", "https://www.mext.go.jp/a_menu/koutou/senbatsu/1412102_00013.htm"))},
        ],
        [{"path": "/zenki-koki/", "text": "国公立の前期日程と後期日程の違い"}, {"path": "/postmark/", "text": "消印有効と必着の違い"}, {"path": "/kyotsu/", "text": "共通テストの日程と検定料"},
         {"path": "/nyushi/", "text": "入試カレンダー(大学・高校)"}], ["utokyo", "mext", "dnc"], "令和9年度(2027年)", intent=1, secondary=("国公立 出願期間 2027", "国公立 前期 日程"))


def _desk_text(slug: str) -> tuple[str, list[dict]]:
    """The desk's confirmed text (sites/shiken/articles/<slug>.md, put in word for word) -> (the answer, the sections).
    Only the form is changed: '---' lines (separators) and '**' (emphasis marks) are not shown; a '###' line is the caption of the table that follows; a '- ' list is a <ul>."""
    import html as _h
    import re
    from pathlib import Path
    md_ = (Path(__file__).resolve().parents[1] / "articles" / f"{slug}.md").read_text(encoding="utf-8")
    md_ = re.sub(r"\A\s*<!--.*?-->\s*", "", md_, flags=re.S).replace("**", "")
    lines = [l.rstrip() for l in md_.splitlines()]
    secs: list[dict] = []
    cur: dict = {}
    order = {"paras": 0, "table": 1, "html": 2}
    last = -1
    caption = ""
    def put(kind, value):
        nonlocal cur, last
        if cur and order[kind] <= last and not (kind == "paras" and last == 0):
            secs.append(cur); cur = {}; last = -1
        if kind == "paras":
            cur.setdefault("paras", []).append(value)
        else:
            cur[kind] = value
        last = order[kind]
    i, answer = 0, None
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.strip() == "---" or ln.startswith("# "):
            i += 1; continue
        if ln.startswith("## "):
            if cur: secs.append(cur)
            cur, last = {"h2": ln[3:].strip()}, -1
            i += 1; continue
        if ln.startswith("### "):
            caption = ln[4:].strip(); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            put("table", {"caption": caption, "cols": rows[0], "rows": rows[2:]})
            continue
        if ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip()); i += 1
            put("html", "<ul>" + "".join(f"<li>{_h.escape(x, quote=False)}</li>" for x in items) + "</ul>")
            continue
        if answer is None and not cur:
            answer = ln.strip(); i += 1; continue
        put("paras", ln.strip()); i += 1
    if cur: secs.append(cur)
    return answer, secs


def zenki_koki() -> dict:
    answer, secs = _desk_text("zenki-koki")
    return art(
        "/zenki-koki/", "前期日程と後期日程の違い", "国公立の前期日程と後期日程の違い(令和9年度の日付つき)", "国公立大学の前期日程と後期日程の違い",
        "国公立大学の一般選抜には、前期日程と後期日程があります。令和9年度の前期日程は2月25日から。何が違い、いつ決まり、出願はいくつできるのかを、東京大学の公式の日付とあわせて整理しました。",
        answer, secs,
        [{"path": "/kokkoritsu/", "text": "国公立大学の出願期間"}, {"path": "/kyotsu/", "text": "共通テストの日程と検定料"}, {"path": "/postmark/", "text": "消印有効と必着の違い"},
         {"path": "/nyushi/", "text": "入試カレンダー(大学・高校)"}], ["utokyo", "mext"], "令和9年度(2027年)", intent=4, secondary=("国公立 前期 後期 違い", "国公立 前期 日程"))


def pages() -> list[dict]:
    return [kyotsu(), tsuishi(), kokkoritsu(), zenki_koki()]
