"""The ledger of what was checked, and on which day: the check day of a page and the log of the fetches are data here, not typed into the pages.

CHECKED_ON   the pages whose facts (dates, numbers) were checked again against the primary or two secondary sources on a day. The page shows the newest day
             it is listed under ("2026年11月15日確認"). The day of the content change (data_basis is not the update day) is not touched by this.
FETCH_LOG    every source that was asked on a day and what came back. A failed fetch is never a "no change": tests/test_kurashi_site.py lists the failed ones
             that no later "ok" covers, and the daily routine starts with them.
Only things that were really read go in. A page that was not looked at keeps its older day.
"""
from __future__ import annotations

from datetime import date

FIRST = "2026-11-03"

# the last day the National Tax Agency's special page for the 令和8年分 return was seen as not yet published (the page says so with this day)
TOKUSHU_NOT_YET = "2026-11-25"

# day -> the pages whose dates were compared with the sources that day
CHECKED_ON = {
    "2026-11-25": [
        "/nenmatsu-chosei/",                                  # 国税庁「年末調整がよくわかるページ(令和8年分)」の本文で変更点4項目を照合した
        "/nengajo/",                                          # 日本郵便 よくある質問(question/140)の本文で引受12/20・元日の差出目安12/27を照合した
        "/furusato/deadline/", "/furusato/one-stop/",         # 総務省「税金の控除について」の本文で3月15日・5団体を照合した
        "/moving/", "/moving/tenshutsu/",                     # マイナポータル moving_oss.html の本文(転入は来庁・14日以内・対象外の条件)で照合した
        "/life/birth/",                                       # 法務省 出生届のページの本文(14日以内・国外3か月)で照合した
    ],
    "2026-11-24": [
        "/nengajo/",                                          # 日本郵便の発表(検索の要約)とNHK等の二次情報で引受12/20・差出目安12/27・販売1/15を照合した
        "/nenmatsu-chosei/",                                  # 国税庁の令和8年度税制改正ページ(施行12/1)の要約と二次情報で変更点を照合した
    ],
    "2026-11-23": [
        "/nenmatsu-chosei/",                                  # 国税庁「年末調整がよくわかるページ(令和8年分)」の本文(変更点4項目)をChromeで再び読んで照合した
        "/furusato/deadline/", "/furusato/one-stop/",         # 総務省「税金の控除について」の本文(3月15日・5団体・控除の式)で照合した
        "/nengajo/",                                          # 日本郵便の2026-08-31発表(検索の公式PDF要約)で引受12/20・差出目安12/27・販売1/15・1/3配達を照合した
    ],
    "2026-11-22": [
        "/nenmatsu-chosei/",                                  # 国税庁「年末調整がよくわかるページ(令和8年分)」の本文で変更点4項目を照合した
        "/moving/", "/moving/tenshutsu/",                     # マイナポータル moving_oss.html の本文(転入は来庁・14日以内・対象外の条件)で照合した
        "/life/birth/",                                       # 法務省 出生届のページの本文(14日以内・国外3か月)で照合した
    ],
    "2026-11-21": [
        "/furusato/deadline/",                                # 総務省「税金の控除について」(新URL)の本文をChromeで読み、3月15日の申告・ワンストップ・控除の式を照合した
    ],
    "2026-11-20": [
        "/nengajo/",                                          # 日本郵便の公式発表(8/31)のPDFをChrome(Google文書ビューア)で全文読んで照合した
        "/furusato/deadline/",                                # 総務省「税金の控除について」を全文読み、寄附年と3月15日の申告を照合した(変更届の1月10日は一次未取得のまま)
    ],
    "2026-11-16": [
        "/nengajo/",                                          # 日本郵便の公式発表(8/31)の全文を読んで照合した
        "/nenmatsu-chosei/",                                  # 国税庁の年調ソフトのページと11/15のPDFで照合した
        "/moving/", "/moving/tenshutsu/",                     # マイナポータルの引越しの個別ページの本文で照合した
    ],
    "2026-11-15": [
        "/", "/month/", "/month/11/", "/month/12/", "/month/1/", "/month/2/", "/month/3/",
        "/nengajo/", "/nenmatsu-nenshi/", "/nenmatsu-chosei/",
        "/furusato/deadline/", "/furusato/one-stop/",
        "/kakutei-shinkoku/", "/kakutei-shinkoku/junbi/", "/kakutei-shinkoku/kanpu/", "/kakutei-shinkoku/furusato/",
    ],
}

# (day, what, how, result, note); result is "ok" (the body was read), "top" (only the top page or a list was read: never counts as "no change") or "failed".
# A later "ok" for the same what closes a "failed"; a "top" does not.
FETCH_LOG = [
    ("2026-11-25", "国税庁 年末調整がよくわかるページ(令和8年分)", "Chrome(本文)", "ok", "変更点4項目。サイトと一致"),
    ("2026-11-25", "日本郵便 年賀状の引受開始(よくある質問)", "Chrome(本文 question/140)", "ok", "引受12/20・元日の差出目安(できるだけ)12/27。サイトと一致"),
    ("2026-11-25", "総務省 ふるさと納税 税金の控除について", "Chrome(本文)", "ok", "3月15日までの確定申告・ワンストップは5団体以内。サイトと一致"),
    ("2026-11-25", "マイナポータル 引越し手続(hikkoshi_top)", "Chrome(myna.go.jp/html/moving_oss.html の本文)", "ok", "転入は来庁・14日以内・対象外の条件。サイトと一致"),
    ("2026-11-25", "法務省 戸籍・婚姻届の案内", "Chrome(ONLINE/FAMILYREGISTER/5-1.html の本文。婚姻届は今回は読んでいない)", "ok", "出生届は14日以内(国外3か月)・手数料なし。サイトと一致"),
    ("2026-11-25", "国税庁 確定申告特集", "Chrome(本文)", "ok", "まだ令和7年分(令和8年3月16日まで)の表示。令和8年分は未公開"),
    ("2026-11-25", "日本年金機構 お知らせ", "Chrome(トップページのお知らせ)", "top", "控除証明書の送付などで、手続きの変更は見当たらない(一覧のみ)"),
    ("2026-11-25", "厚生労働省 介護・高齢者福祉", "Chrome(トピックス一覧)", "top", "最新は11/18の基金の内示。一覧のみ"),
    ("2026-11-25", "国税庁 報道発表一覧", "Chrome(一覧)", "top", "最新は10月分(法人税の実績など)。一覧のみ"),
    ("2026-11-25", "e-Tax お知らせ", "Chrome(一覧と10/20の記事の本文)", "top", "令和9年1月の新機能は個人事業の開業手続で、このサイトの記述に影響なし"),
    ("2026-11-23", "国税庁 年末調整がよくわかるページ(令和8年分)", "Chrome(本文。/gensen/nenmatsu/ は存在せず /gensen/nencho/index.htm)", "ok", "変更点4項目(基礎控除・給与所得控除の最低保障額・扶養親族等の所得要件・23歳未満の扶養親族の生命保険料控除の特例)。サイトと一致"),
    ("2026-11-23", "日本年金機構 お知らせ", "Chrome(トップページの本文)", "ok", "最新は10/30(障害年金の認定状況・年金請求書の審査)と10/9(令和8年分の国民年金保険料控除証明書の送付)。サイトの控除証明書の記述と矛盾なし"),
    ("2026-11-23", "厚生労働省 介護・高齢者福祉", "Chrome(本文。/stf/newpage_00001.html は404)", "ok", "トピックスは統計の更新のみ(11/10)。介護の手続きに関わる制度変更は見当たらない"),
    ("2026-11-23", "国税庁 報道発表一覧", "WebFetch(一覧)", "top", "令和8年分の制度変更は7月の路線価のみ。一覧だけなので変更なしとはしない"),
    ("2026-11-23", "e-Tax お知らせ", "WebFetch(一覧)", "top", "法人向けの案内が中心。個人の確定申告の新しい案内は見当たらない(一覧のみ)"),
    ("2026-11-23", "日本年金機構 お知らせ", "WebFetch(日付つきの項目が取れない)", "failed", "メニューのみ。次回、別経路(検索・二次情報)で再実施"),
    ("2026-11-24", "日本郵便 2027年用年賀はがき(引受・差出目安・販売期間)", "WebSearch(公式PDFの要約+NHK+二次情報)", "ok", "引受12/20・差出目安12/27・販売11/2〜1/15。サイトと一致。12/15表記は古い記事のみ"),
    ("2026-11-24", "国税庁 令和8年度税制改正による基礎控除の引上げ等", "WebSearch(国税庁ページの要約+二次情報3件)", "ok", "施行は令和8年12月1日・12月の年末調整から。サイトの変更点4項目と一致。ページ本文の直接取得は次回"),
    ("2026-11-23", "総務省 ふるさと納税 税金の控除について", "Chrome(本文)", "ok", "3月15日までの確定申告・ワンストップは5団体以内・控除の式。サイトと一致"),
    ("2026-11-23", "国税庁 確定申告特集", "Chrome(本文)", "ok", "まだ令和7年分(令和8年3月16日まで)の表示。令和8年分の特集は未公開で、サイトの記述に変更なし"),
    ("2026-11-23", "日本郵便 2027年用年賀はがきの発行概要", "Chrome(PDFはテキスト取得不可)・検索で公式PDFの内容を確認", "ok", "引受12/20・元日の差出目安12/27・販売1/15・1/3も配達。サイトと一致"),
    ("2026-11-23", "日本郵便 ニュースリリース一覧", "Chrome(先頭は8/5の1件のみ表示)", "top", "一覧の読み込みが不完全。年賀は上の発行概要で代替"),
    ("2026-11-22", "国税庁 年末調整がよくわかるページ(令和8年分)", "Chrome(本文)", "ok", "変更点4項目(基礎控除・給与所得控除の最低保障額・扶養親族等の所得要件・23歳未満の扶養親族の生命保険料控除の特例)。サイトと一致"),
    ("2026-11-22", "マイナポータル 引越し手続(hikkoshi_top)", "Chrome(moving_oss.html の本文)", "ok", "転出届と来庁予定の申請まで・転入は来庁・14日以内・対象外の条件。サイトと一致。hikkoshi_top 自体は別URLで代替"),
    ("2026-11-22", "法務省 戸籍・婚姻届の案内", "検索で現行URLを特定→Chrome(ONLINE/FAMILYREGISTER/5-1.html・5-2.html の本文)", "ok", "出生届は14日以内(国外3か月)・手数料なし。婚姻届は随時・成年の証人2名(押印は任意)。現行URLは /ONLINE/FAMILYREGISTER/"),
    ("2026-11-21", "総務省 ふるさと納税 税金の控除について", "Chrome(新URL mechanism/deduction.html の本文)", "ok", "3月15日までの確定申告・ワンストップ・控除の式。サイトと一致(旧URL furusato/ は404)"),
    ("2026-11-21", "マイナポータル 引越し手続(hikkoshi_top)", "Chrome(403のまま)・トップは開けた(引越しの案内に変更なし)・デジタル庁の手順ページ(2024-01-29の移転案内のみ)", "failed", "403。個別ページの本文は未取得。11/16 の別URLの本文は ok"),
    ("2026-11-21", "法務省 戸籍・婚姻届の案内", "WebFetch(403)・Chrome(minji04.html は404)", "failed", "現行URLを未特定。次回は検索で現行URLを探す"),
    ("2026-11-21", "日本郵便 ニュースリリース一覧", "WebFetch・Chrome(一覧の先頭は8/5の1件のみ表示)", "top", "年賀の新しい発表は見えず。一覧の読み込みが不完全"),
    ("2026-11-20", "日本郵便 2027年用年賀はがきの発行概要(2026-08-31発表のPDF)", "Chrome+Google文書ビューア", "ok", "販売11/2〜1/15・引受開始12/20・元日の目安12/27・1/3も配達。サイトと一致"),
    ("2026-11-20", "総務省 ふるさと納税 税金の控除について", "Chrome", "ok", "3月15日までの確定申告・ワンストップ・控除の式。サイトと一致"),
    ("2026-11-20", "マイナポータル 引越し手続(hikkoshi_top)", "WebFetch・Chrome", "failed", "403。入口からの再確認が必要"),
    ("2026-11-15", "日本郵便 年賀はがき 引受開始・差出日・販売終了", "日本郵便の2026-08-31発表(検索の引用)+NHK", "ok", "12/20・12/27・1/15。サイトと一致"),
    ("2026-11-15", "日本郵便 /newyear/", "WebFetch・Chrome", "failed", "404(ページが移動)。上の発表で代替"),
    ("2026-11-15", "国税庁 令和8年分 年末調整のしかた(101.pdf)", "Google文書ビューア経由", "ok", "変更点4項目・納期限 令和9年1月12日。サイトの記述と一致"),
    ("2026-11-15", "国税庁 令和8年分 確定申告の期間・還付申告", "国税庁資料+二次情報", "ok", "2027年2月16日〜3月15日、還付は1月1日から。サイトと一致"),
    ("2026-11-15", "ワンストップ特例の期限(1月10日)", "自治体2件+ふるさと納税サイト", "ok", "法の期限は1月10日(日)。紙は自治体により1月12日扱い。サイトの文は変更届と申請書を分けて書いてある"),
    ("2026-11-15", "行政機関の休日(12月29日〜1月3日)", "法令の解説(hourei.net ほか)", "ok", "行政機関の休日に関する法律。サイトと一致"),
    ("2026-11-15", "総務省 ふるさと納税 公式ページ", "WebFetch(403/404)・Chrome・検索", "failed", "公式の本文は未取得。二次情報(freee ほか)で、2025年10月にポイント付与禁止が済み、2026年10月は地場産品基準・募集費用の見直しと確認"),
    ("2026-11-15", "マイナポータル 引越し手続", "WebFetch", "failed", "待機室へ転送。変更のお知らせは未確認"),
    ("2026-11-15", "gyosei.go.jp", "WebFetch", "failed", "名前解決不可。法令の解説で代替済み"),
    ("2026-11-16", "日本郵便 /newyear/", "Chrome(404のまま)→日本郵便の2026-08-31発表PDFをGoogle文書ビューアで全文", "ok", "発売11/2・販売終了1/15・引受開始12/20(日)・元日の目安12/27(日)・1/3(日)も配達。サイトと一致"),
    ("2026-11-16", "総務省 ふるさと納税 公式ページ", "Chrome(旧URLは移転)→総務省報道資料(令和7年6月24日)", "ok", "指定基準の改正(募集費用の透明化・地場産品基準の明確化)は令和8年10月開始の指定対象期間から適用。寄附する人の手続は変わらず、サイトの記述の変更は不要"),
    ("2026-11-16", "マイナポータル 引越し手続", "Chrome(トップは開けた)", "top", "トップのお知らせに引越し手続の変更なし(お知らせは離職票の受け取りのみ)。トップだけ読んだので「変更なし」には数えない"),
    ("2026-11-16", "マイナポータル 引越し手続", "Chrome(個別ページ myna.go.jp/html/moving_oss.html の本文)+デジタル庁の引越し手続ページの更新日(検索)", "ok", "転出届の提出と来庁予定の連絡まで・転入届は来庁・14日以内・対象外の条件。サイトの記述(/moving/tenshutsu/・引越しのガイド)と一致。変更なし"),
    ("2026-11-16", "国税庁 年末調整手続の電子化(nencho.htm)", "Chrome(本文)", "ok", "令和8年分の年調ソフトは12月1日以後の年末調整に対応。11/12に年調ソフトを再公開。サイトの『令和8年分で変わったところ』の4項目は11/15のPDFと一致し、直す記述なし"),
    ("2026-11-16", "gyosei.go.jp", "法令の解説で代替済み(11/15)。公式の名前解決は再試行せず", "ok", "行政機関の休日(12/29〜1/3)は法律で決まっており変更の話はない"),
]


def checked_day(path: str) -> str:
    """ISO day this page was last checked (FIRST when it was never checked again)."""
    days = [day for day, paths in CHECKED_ON.items() if path in paths]
    return max(days) if days else FIRST


def label(iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y}年{m}月{d}日"


def open_failures() -> list[tuple]:
    """failed fetches that no later 'ok' for the same source covers"""
    out = []
    for i, (day, what, how, res, note) in enumerate(FETCH_LOG):
        if res == "failed" and not any(r == "ok" and w == what and dd >= day for dd, w, _h, r, _n in FETCH_LOG[i + 1:]):
            out.append((day, what, how, note))
    return out


def stale_failures(min_days: int = 3) -> list[tuple]:
    """sources that failed on min_days or more different days and were never read ('ok') since: they are not 'no change', the routine has to find another way"""
    out = []
    for what in dict.fromkeys(w for _d, w, _h, _r, _n in FETCH_LOG):
        rows = sorted((d, r) for d, w, _h, r, _n in FETCH_LOG if w == what)
        last_ok = max((d for d, r in rows if r == "ok"), default="")
        days = sorted({d for d, r in rows if r == "failed" and d > last_ok})
        if len(days) >= min_days:
            out.append((what, days))
    return out


def latest_day() -> date:
    return date.fromisoformat(max(CHECKED_ON))
