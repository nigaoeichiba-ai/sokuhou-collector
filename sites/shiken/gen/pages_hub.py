"""The home page, the date-ordered lists, the entrance-exam hub, the high-school page, and the trust pages.  The tables are made from facts.py, so a changed date is changed once."""
from __future__ import annotations

import json
from pathlib import Path

from .common import TODAY, d, jp, md, left, in_days, CHECKED
from .facts import EVENTS, TOEIC
from .pages_exam import official

KOKO = json.loads((Path(__file__).resolve().parents[1] / "data" / "koko.json").read_text(encoding="utf-8"))
SRC = {"retio": "不動産適正取引推進機構"}


def upcoming(kinds: tuple[str, ...]) -> list[tuple[str, str, str, str]]:
    """(iso date, who, what, note) of the events from today on, in date order; TOEIC rounds are added."""
    names = {"apply_start": "申込の開始", "apply_end": "申込の締切", "exam": "試験日", "result": "合格発表"}
    out = []
    for who, group, kind, iso, src, note in EVENTS:
        if kind in kinds and left(iso) >= 0:
            out.append((iso, who, names[kind], note))
    for exam, s, e, res in TOEIC:
        if "apply_start" in kinds and left(s) >= 0:
            out.append((s, f"TOEIC L&R {md(exam)}の回", "申込の開始", ""))
        if "apply_end" in kinds and left(e) >= 0:
            out.append((e, f"TOEIC L&R {md(exam)}の回", "申込の締切", "15時まで" if exam == "2026-12-19" else ""))
        if "exam" in kinds and left(exam) >= 0:
            out.append((exam, f"TOEIC L&R {md(exam)}の回", "試験日", ""))
        if "result" in kinds and left(res) >= 0:
            out.append((res, f"TOEIC L&R {md(exam)}の回", "デジタル公式認定証", ""))
    return sorted(out)


def rows_of(items) -> list[list]:
    return [[jp(iso), who, what, in_days(iso)] for iso, who, what, note in items]


def table(caption, items, note="") -> dict:
    t = {"caption": caption, "cols": ["日付", "試験", "区分", "2026年11月3日から"], "rows": rows_of(items)}
    if note:
        t["note"] = note
    return t


def home() -> dict:
    near = upcoming(("apply_end",))[:8]
    return {
        "path": "/", "kind": "hub", "primary_kw": "試験日程カレンダー", "secondary_kw": ["資格 試験日程", "出願 期限"], "intent": 1,
        "title": "試験日程カレンダー 資格・入試の申込期限と試験日", "h1": "資格・入試の試験日程カレンダー",
        "description": "資格試験と入学試験の、申込・出願の期間、試験日、合格発表日を、公式ページで確かめた日付だけで並べています。締切が近い順の一覧と、試験ごとの日程、共通テストと公立高校入試の日程があります。",
        "answer": f"いちばん近い申込の締切は、{md(near[0][0])}の{near[0][1]}です。公式ページで確かめた日付だけを載せています。",
        "data_basis": "2026年11月3日現在", "sources": ["retio", "gyosei", "mhlw_kango", "eiken", "iibc", "dnc", "utokyo", "koko"],
        "sections": [
            {"h2": "いま近い申込の締切", "paras": [
                "締切が近い順に8件を並べました。ここにない試験は、「申込期限が近い試験の一覧」に続きがあります。日付の右は、2026年11月3日から数えた日数です。"],
             "table": table("申込の締切が近い順(2026年11月3日時点)", near, "日付は各試験団体の公式ページの記載です。時刻や郵送の扱いは、試験ごとのページで確かめてください。")},
            {"h2": "このサイトで分かること", "paras": [
                "資格試験は、申込の開始と締切、試験日、合格発表日、受験料を、試験ごとに並べています。宅建、行政書士、社労士、日商簿記、FP、英検、介護福祉士、看護師国家試験には、直近の合格率も載せています。",
                "入学試験は、共通テストと国公立大学の日程、公立高校入試の日程です。公立高校は、都道府県の教育委員会が出した令和9年度の日程を、" + f"{len(KOKO)}都道府県分並べました。",
                "私立大学、中学受験、専門学校の入試は、学校ごとに日程が分かれるため、載せていません。志望する学校の公式ページで確かめてください。"]},
            {"h2": "日付の確かめ方", "paras": [
                "すべての日付は、試験団体・省庁・教育委員会の公式ページで読み取った日です。予備校やまとめサイトの日付は使いません。曜日と「あと何日」は、日付から計算しています。",
                "公式ページに載っていない日程は、推測で補いません。その場合は、次の回が未発表であることだけを書いています。"]},
        ],
        "related": [{"path": "/schedule/", "text": "資格試験日程一覧(日付順)"}, {"path": "/deadlines/", "text": "申込期限が近い試験の一覧"}, {"path": "/nyushi/", "text": "入試カレンダー(共通テスト・国公立・公立高校)"},
                    {"path": "/method/", "text": "日程の調べ方と出典"}]}


def schedule() -> dict:
    items = upcoming(("exam", "result"))
    unpublished = [
        ["宅建士試験(令和9年度)", "未発表", "https://www.retio.or.jp/exam/schedule/"], ["行政書士試験(令和9年度)", "未発表", "https://www.gyosei-shiken.or.jp/"],
        ["社労士試験(第59回)", "未発表", "https://www.sharosi-siken.or.jp/"], ["中小企業診断士試験(令和9年度)", "未発表", "https://www.jf-cmca.jp/"],
        ["英検(2027年度第1回)", "未発表", "https://www.eiken.or.jp/eiken/schedule/examinee/03/"], ["漢検(2027年度)", "未発表", "https://www.kanken.or.jp/kanken/individual/pbt/schedule/"],
        ["国家公務員試験(申込期間)", "11月中旬に人事院が公表予定", "https://www.jinji.go.jp/kouho_houdo/kisya/2603/2027nittei.html"],
    ]
    return {
        "path": "/schedule/", "kind": "list", "parent": "/", "primary_kw": "資格試験日程一覧", "secondary_kw": ["資格 試験日程 一覧", "資格 試験日 一覧"], "intent": 1,
        "title": "資格試験日程一覧(試験日・合格発表を日付順に)", "h1": "資格試験日程一覧",
        "description": "これから来る資格試験の試験日と合格発表日を、日付の早い順に並べた一覧です。宅建・行政書士・看護師・英検・TOEIC・共通テストなど。次の回が未発表の試験も分かります。",
        "answer": f"次の試験日は{md(items[0][0])}の{items[0][1]}です。これから来る試験日と合格発表日を、日付順に並べています。",
        "data_basis": "2026年11月3日現在", "sources": ["retio", "gyosei", "sssc", "mhlw_kango", "jfcmca", "jinji", "kentei", "kinzai", "eiken", "iibc", "kanken", "dnc", "utokyo"],
        "sections": [
            {"h2": "これからの試験日と合格発表", "paras": [
                "2026年11月3日から後の、試験日と合格発表日です。日付の早い順に並べています。個別の試験の申込期間や受験料は、試験名のページで確かめてください。"],
             "table": table("これからの試験日と合格発表(日付順)", items, "TOEICは、デジタル公式認定証の日を合格発表の代わりに載せています。")},
            {"h2": "次の回が未発表の試験", "paras": [
                "次の回の日程が、公式ページにまだ載っていない試験です。当サイトは日付を推測で入れません。公式発表を確かめて、載ったら足します。"],
             "table": {"caption": "次の回が未発表の試験(2026年11月3日時点)", "cols": ["試験", "状況"], "rows": [[r[0], r[1]] for r in unpublished]}},
            {"h2": "使い方", "paras": [
                "試験名をたどって、各ページの日程表を見てください。申込を済ませたかどうかは、「申込期限が近い試験の一覧」で並べ替えて確かめられます。",
                "この一覧に載っていない試験は、まだ公式ページで確認できていません。載っていないことは、試験がないことを意味しません。"]},
        ],
        "related": [{"path": "/deadlines/", "text": "申込期限が近い試験の一覧"}, {"path": "/results/", "text": "資格試験の合格発表日の一覧"}, {"path": "/yama/", "text": "2026年11月から2027年3月の試験の山"},
                    {"path": "/nendo/", "text": "来年度の日程は、いつ発表されるか"}]}


def deadlines() -> dict:
    items = upcoming(("apply_end",))
    starts = upcoming(("apply_start",))[:6]
    return {
        "path": "/deadlines/", "kind": "list", "parent": "/", "primary_kw": "申込期限が近い試験", "secondary_kw": ["宅建 申し込み期限", "出願 期限"], "intent": 1,
        "title": "申込期限が近い試験の一覧(締切の近い順)", "h1": "申込期限が近い試験の一覧",
        "description": "今日から先の申込の締切を、近い順に並べた一覧です。看護師国家試験・FP1級・TOEIC・英検・漢検など。締切までの日数は日付から計算しています。時刻や郵送の扱いも添えています。",
        "answer": f"いちばん近い申込の締切は、{jp(items[0][0])}の{items[0][1]}です。あと{left(items[0][0])}日です。",
        "data_basis": "2026年11月3日現在", "sources": ["mhlw_kango", "kinzai", "eiken", "iibc", "kanken"],
        "sections": [
            {"h2": "締切の近い順", "paras": [
                f"2026年11月3日から先の、申込の締切です。今日からの日数が少ない順に並べています。いちばん上の{items[0][1]}は、あと{left(items[0][0])}日です。",
                "締切の時刻は、日付だけでは分かりません。インターネットは17時や23時59分、郵送は消印か必着かなど、試験ごとに違います。備考の欄と、試験ごとのページで確かめてください。"],
             "table": {"caption": "申込の締切が近い順(2026年11月3日時点)", "cols": ["締切の日", "試験", "あと何日", "備考"], "rows": [[jp(iso), who, in_days(iso), note or "—"] for iso, who, what, note in items]}},
            {"h2": "これから申込が始まる試験", "paras": ["申込がまだ始まっていない試験です。開始日を過ぎれば、同じ試験が上の表に並びます。"],
             "table": table("申込が始まる日(2026年11月3日時点)", starts)},
            {"h2": "締切の読み方", "paras": [
                "「締切」は、受付が終わる日です。その日の何時までに何をすれば間に合うのかは、試験によって違います。クレジットカードの決済が終わる時刻と、入力の終わる時刻が別の試験もあります。",
                "コンビニで払う場合は、締切より数日早い支払期限が付くことがあります。英検は、コンビニ払いが12月11日、個人申込の締切が12月14日と、3日差があります。"]},
        ],
        "related": [{"path": "/postmark/", "text": "消印有効と必着の違い"}, {"path": "/flow/", "text": "申込から合格発表までの流れ"}, {"path": "/schedule/", "text": "資格試験日程一覧(日付順)"},
                    {"path": "/yama/", "text": "2026年11月から2027年3月の試験の山"}]}


def nyushi() -> dict:
    gen = [r for r in KOKO if r["pref"] in ("東京都", "神奈川県", "大阪府", "愛知県", "埼玉県", "千葉県", "福岡県", "北海道")]
    rows = [[jp("2027-01-16"), "大学入学共通テスト(本試験の1日目)", in_days("2027-01-16")], [jp("2027-01-23"), "共通テストの追・再試験の1日目", in_days("2027-01-23")],
            [jp("2027-01-25"), "東京大学の出願の開始", in_days("2027-01-25")], [jp("2027-02-25"), "国公立大学 前期日程の試験(東京大学の例)", in_days("2027-02-25")],
            [jp("2027-03-10"), "東京大学の合格発表", in_days("2027-03-10")]]
    hs = sorted(([r["general"]["exam"][0], r["pref"]] for r in gen if r["general"]["exam"]))
    rows += [[jp(e), f"{p}の公立高校入試(学力検査)", in_days(e)] for e, p in hs]
    rows = sorted(rows, key=lambda r: _key(r[0]))
    return {
        "path": "/nyushi/", "kind": "hub", "parent": "/", "primary_kw": "入試カレンダー", "secondary_kw": ["受験 スケジュール", "共通テスト 日程"], "intent": 1,
        "title": "入試カレンダー 2027(共通テスト・国公立・公立高校の日程)", "h1": "入試カレンダー 2027年度入試の主な日程",
        "description": "令和9年度(2027年度)入試の主な日程を日付順に並べました。共通テスト、国公立大学、公立高校入試。公式ページで確かめた日付だけを載せ、私立の入試は載せていません。",
        "answer": f"共通テストは{jp('2027-01-16')}、国公立大学の前期日程は{md('2027-02-25')}から。公立高校入試は多くが2月から3月です。",
        "data_basis": "2026年11月3日現在", "sources": ["dnc", "utokyo", "koko"],
        "sections": [
            {"h2": "2027年1月から3月の主な日程", "paras": [
                "共通テストの出願は、2026年10月2日に終わりました。これから先の大きな日付は、1月の試験と、その後の出願、2月と3月の試験です。",
                "公立高校は、都道府県ごとに日程が違います。表には、人口の多い8都道府県の学力検査の日を入れました。全県の表は、公立高校入試のページにあります。"],
             "table": {"caption": "2027年度入試の主な日程(日付順)", "cols": ["日付", "できごと", "2026年11月3日から"], "rows": rows,
                       "note": "公立高校は、各都道府県の「学力検査に基づく選抜」の1日目です。推薦や特色選抜の日は含みません。"}},
            {"h2": "載せている範囲", "paras": [
                "このサイトの入試は、大学入学共通テスト、国公立大学、公立高校の3つです。国公立大学は、日程が公式ページで確かめられた大学だけを載せます。",
                "私立大学、私立高校、中学受験、専門学校の入試は、学校ごとに日程が分かれているため、載せていません。志望校の公式ページか募集要項で確かめてください。"]},
        ],
        "related": [{"path": "/kyotsu/", "text": "共通テストの日程と検定料"}, {"path": "/kokkoritsu/", "text": "国公立大学の出願期間"}, {"path": "/koko/", "text": "公立高校入試の日程(都道府県別)"},
                    {"path": "/zenki-koki/", "text": "国公立の前期日程と後期日程の違い"}]}


def _key(s: str):
    import re
    y, m, dd = map(int, re.findall(r"\d+", s)[:3])
    return (y, m, dd)


def _dates(ds: list[str]) -> str:
    if not ds:
        return "—"
    first = d(ds[0])
    if len(ds) == 1:
        return md(first)
    return md(first) + "から" + "・".join(f"{d(x).day}日({'月火水木金土日'[d(x).weekday()]})" for x in ds[1:])


def _apply(st: dict) -> str:
    a, b = st["apply"]
    if a and b:
        return md(a) + "から" + md(b)
    if st.get("apply_raw"):
        return "中学校長の承認 " + md(b) + "まで"
    return "公式で確認"


def koko() -> dict:
    gen_rows, early_rows = [], []
    for r in KOKO:
        g, e = r["general"], r["early"]
        link = r["pref"]
        gen_rows.append([link, _apply(g), _dates(g["exam"]), md(g["result"]) if g["result"] else "公式で確認"])
        if e:
            early_rows.append([link, _dates(e["exam"]), md(e["result"]) if e["result"] else "公式で確認"])
    gen_rows = [r for r in gen_rows]
    n = len(KOKO)
    return {
        "path": "/koko/", "kind": "list", "parent": "/nyushi/", "primary_kw": "公立高校入試の日程", "secondary_kw": ["公立高校入試 日程 2027", "高校入試 日程 2027"], "intent": 1,
        "title": "公立高校入試の日程 2027(令和9年度・都道府県別)", "h1": "公立高校入試の日程 令和9年度(2027年)都道府県別",
        "description": f"令和9年度の公立高校入試の日程を、{len(KOKO)}都道府県分並べました。出願、学力検査の日、合格発表日を教育委員会の公式ページで確かめています。推薦や前期など早い選抜の日も添えています。",
        "answer": f"東京都の学力検査は{jp('2027-02-21')}、大阪府は{md('2027-03-10')}。{n}都道府県の出願・試験・合格発表の日を並べました。",
        "data_basis": "2026年11月3日現在", "sources": ["koko"], "dataset": {"csv": "data/koko.csv", "table_section": 1},
        "sections": [
            {"h2": "掲載の範囲と読み方", "paras": [
                f"教育委員会が令和9年度の日程を公表していて、公式ページで日付を確かめられた{n}都道府県を載せています。確かめられなかった県は、載せていません。載っていないことは、日程がないことではありません。",
                "公立高校入試は、都道府県ごとに選抜の区分が違います。表の「学力検査中心の選抜」は、各県の一般的な選抜(一般・後期・共通選抜など)の日です。推薦・前期・特別選抜は、別の表にまとめました。各県の日程は、教育委員会が公表した資料のとおりです。"]},
            {"h2": "学力検査中心の選抜", "paras": ["出願、試験日、合格発表の順です。出願期間が「公式で確認」の県は、確かめた資料に載っていなかった県です。"],
             "table": {"caption": "令和9年度 公立高校入試 学力検査中心の選抜(都道府県別)", "cols": ["都道府県", "出願", "学力検査", "合格発表"], "rows": gen_rows,
                       "note": "再募集・二次募集・定時制の日は含みません。"}},
            {"h2": "推薦・前期など早い選抜", "paras": ["早い時期に試験をする選抜を設けている府県です。大阪府は特別入学者選抜、兵庫県は推薦・特色選抜など、名前は府県ごとに違います。"],
             "table": {"caption": "令和9年度 推薦・前期など早い選抜(試験日と結果の日)", "cols": ["都道府県", "試験日", "結果の通知・発表"], "rows": early_rows}},
            {"h2": "出願は中学校を通す", "paras": [
                "公立高校の出願は、県によっては、在籍する中学校が取りまとめます。兵庫県のように、インターネットの入力と中学校長の承認が締切になる県もあります。個人で直接、高校に出す方法ではありません。",
                "締切の扱いは県ごとに違います。受ける県の教育委員会の資料を、最後に自分で読んでください。"]},
        ],
        "related": [{"path": "/nyushi/", "text": "入試カレンダー(大学・高校)"}, {"path": "/kyotsu/", "text": "共通テストの日程と検定料"}, {"path": "/deadlines/", "text": "申込期限が近い試験の一覧"},
                    {"path": "/yama/", "text": "2026年11月から2027年3月の試験の山"}]}


def method() -> dict:
    return {
        "path": "/method/", "kind": "analysis", "parent": "/", "primary_kw": "日程の調べ方と出典", "secondary_kw": ["試験日程 出典"], "intent": 4,
        "title": "日程の調べ方と出典(規約・更新の手順)", "h1": "日程の調べ方と出典",
        "description": "このサイトの日付を、どこから、どう確かめて載せているかを書きました。出典の選び方、団体の転載の規約、年度が替わるときの更新の手順、確認できなかったことも説明します。",
        "answer": "日付は、試験団体・省庁・教育委員会の公式ページだけから取っています。確認できないものは載せません。",
        "data_basis": "2026年11月3日", "sources": ["retio", "gyosei", "mhlw_kango", "dnc", "koko"],
        "sections": [
            {"h2": "日付の取り方", "paras": [
                "日付は、試験の実施団体、省庁、都道府県の教育委員会、大学の公式ページから取ります。予備校、塾、まとめサイト、ニュースの日付は使いません。",
                "公式ページを開いて、申込の開始と締切、試験日、合格発表日、受験料を読み取り、表に入れています。曜日と「あと何日」は、日付から計算しています。手で書いた曜日はありません。",
                "各ページの更新日は、日付を確かめた日です。確かめた日より後に変更された日程は、反映されていません。"]},
            {"h2": "載せないもの", "paras": [
                "公式ページに載っていない日程は、載せません。「例年この時期」という推測も書きません。次の回が未発表の試験は、そのことだけを書きます。",
                "私立大学・中学受験・専門学校の入試は、学校ごとに日程が分かれているため、載せていません。受験の判断や、出願先の助言もしていません。"]},
            {"h2": "団体の規約について", "paras": [
                "試験団体の中には、サイトの内容の無断転載を禁じるところがあります。宅建士試験の不動産適正取引推進機構は、私的使用や引用など著作権法で認められた場合を除き、無断で転載できないとしています。行政書士試験研究センターは、無断の転用・引用を禁じています。",
                "当サイトは、これらの団体の表や文章を写していません。日付、期間、金額という事実だけを読み取り、自分の表に組み直しています。厚生労働省、人事院、こども家庭庁などの政府の資料は、公共データ利用規約に沿って利用しています。",
                "規約のページを確かめられなかった団体の資料は、日付のほかは載せていません。"]},
            {"h2": "更新の手順", "paras": [
                "試験団体が次の回を発表したら、公式ページで日付を確かめて表を入れ替え、そのページの最終更新日を変えます。年度が替わるときは、全ページの日付を公式ページから取り直します。",
                "訂正や更新は、「訂正と更新の記録」に日付つきで残します。数字の誤りを見つけたら、問い合わせのフォームから知らせてください。公式ページで確かめて、直します。",
                "試験団体や教育委員会から、削除や修正の依頼があったときは、すぐに従います。問い合わせのフォームから知らせてください。"]},
            {"h2": "確認できなかったこと", "paras": [
                "日商簿記の合格発表日、きんざいの受験料、危険物取扱者試験の全国の日程は、公式ページで直接読めなかったため、載せていません。大阪大学と九州大学の令和9年度入試は、募集要項が公表される前のため載せていません。",
                "公立高校入試は、滋賀・奈良・和歌山・鳥取・島根・山口・徳島・愛媛・佐賀・長崎・大分・宮崎・鹿児島・富山・福井・福島・茨城・高知・沖縄の日程を、公式資料で確かめられていません。確かめられたら足します。"]},
        ],
        "related": [{"path": "/corrections/", "text": "訂正と更新の記録"}, {"path": "/nendo/", "text": "来年度の日程は、いつ発表されるか"}, {"path": "/schedule/", "text": "資格試験日程一覧(日付順)"},
                    {"path": "/koko/", "text": "公立高校入試の日程(都道府県別)"}]}


def corrections() -> dict:
    return {
        "path": "/corrections/", "kind": "archive", "parent": "/", "primary_kw": "訂正と更新の記録", "secondary_kw": [], "intent": 4,
        "title": "訂正と更新の記録", "h1": "訂正と更新の記録",
        "description": "日程の追加、変更、訂正を日付つきで残す記録です。数字を直したら、ここに書きます。試験団体が日程を変更したときも、変更した日と内容を、このページに残し、該当ページにも注記します。",
        "answer": "日程を追加したり訂正したりした日と内容を、ここに残します。",
        "data_basis": CHECKED, "sources": ["retio"],
        "sections": [{"h2": "記録", "paras": ["2026年11月3日: サイトを作成しました。資格試験8種、共通テスト、国公立大学、公立高校入試の日程を、公式ページで確かめて載せました。"],
                      "table": {"caption": "更新の記録", "cols": ["日付", "内容"], "rows": [["2026年11月3日", "初回の掲載。全ページの日付を公式ページで確認"]]}}],
        "related": [{"path": "/method/", "text": "日程の調べ方と出典"}]}


def pages() -> list[dict]:
    return [home(), schedule(), deadlines(), nyushi(), koko(), method(), corrections()]
