"""site.json "sources": organisation, page, url, the day the page was read (basis = what the dates describe)."""
from .common import CHECKED


def S(org, table, url, basis="令和8〜9年度の日程"):
    return {"org": org, "table": table, "url": url, "basis": basis, "fetched": CHECKED}


SOURCES = {
    "retio": S("不動産適正取引推進機構", "宅地建物取引士資格試験 試験日程", "https://www.retio.or.jp/exam/schedule/", "令和8年度"),
    "gyosei": S("行政書士試験研究センター", "行政書士試験 受験案内", "https://www.gyosei-shiken.or.jp/doc/guide/guide.html", "令和8年度"),
    "sharosi": S("全国社会保険労務士会連合会 試験センター", "社会保険労務士試験 申込みの案内", "https://www.sharosi-siken.or.jp/application/", "令和8年度(第58回)"),
    "sssc": S("社会福祉振興・試験センター", "介護福祉士国家試験 受験の手続き", "https://www.sssc.or.jp/kaigo/tetsuzuki.html", "第39回(令和8年度)"),
    "mhlw_kango": S("厚生労働省", "看護師国家試験", "https://www.mhlw.go.jp/kouseiroudoushou/shikaku_shiken/kangoshi/", "第116回"),
    "jfcmca": S("中小企業診断協会", "令和8年度 中小企業診断士試験 日程", "https://www.jf-cmca.jp/contents/010_c_/010_c_r08_shiken/R08_nittei.html", "令和8年度"),
    "jinji": S("人事院", "令和9年度 国家公務員試験の日程", "https://www.jinji.go.jp/kouho_houdo/kisya/2603/2027nittei.html", "2027年度"),
    "kentei": S("日本商工会議所 検定試験", "簿記検定 試験日カレンダー", "https://www.kentei.ne.jp/calendar_2026", "第173〜175回"),
    "jafp": S("日本FP協会", "FP技能検定 試験日程", "https://www.jafp.or.jp/exam/schedule/", "2026〜2027年"),
    "kinzai": S("金融財政事情研究会(きんざい)", "FP技能検定 1級学科", "https://www.kinzai.or.jp/fp", "2027年1月"),
    "ipa": S("情報処理推進機構(IPA)", "情報処理技術者試験 スケジュール・手数料", "https://www.ipa.go.jp/shiken/mousikomi/schedule.html", "2026年度"),
    "kanrikyo": S("マンション管理業協会", "管理業務主任者試験 令和8年度の実施詳細", "https://www.kanrikyo.or.jp/kanri/shiken_r08/shiken_detail_20260605.html", "令和8年度"),
    "eiken": S("日本英語検定協会", "英検 2026年度 第3回 申込み", "https://www.eiken.or.jp/eiken/schedule/examinee/03/", "2026年度第3回"),
    "iibc": S("IIBC(国際ビジネスコミュニケーション協会)", "TOEIC Listening & Reading 公開テスト 日程", "https://www.iibc-global.org/toeic/test/lr/guide01/schedule.html", "2026年12月〜2027年3月"),
    "kanken": S("日本漢字能力検定協会", "漢検 個人受検 検定日程", "https://www.kanken.or.jp/kanken/individual/pbt/schedule/", "2026年度第3回"),
    "tokyo_hoken": S("東京都保健医療局", "登録販売者試験 令和8年度", "https://www.hokeniryo.metro.tokyo.lg.jp/anzen/iyaku/tourokushiken/r8shiken", "令和8年度"),
    "dnc": S("大学入試センター", "令和9年度 大学入学共通テスト 試験情報", "https://www.dnc.ac.jp/kyotsu/shiken_jouhou/r9/index.html", "令和9年度"),
    "utokyo": S("東京大学", "令和9年度 学部入学者選抜 一般選抜", "https://www.u-tokyo.ac.jp/ja/admissions/undergraduate/e01_02_01.html", "令和9年度"),
    "mext": S("文部科学省", "令和9年度大学入学者選抜について", "https://www.mext.go.jp/a_menu/koutou/senbatsu/1412102_00013.htm", "令和9年度"),
    "koko": S("各都道府県の教育委員会", "令和9年度 公立高等学校入学者選抜の日程(表の行ごとにリンク)", "https://www.mext.go.jp/", "令和9年度"),
    "retio_stat": S("不動産適正取引推進機構", "宅建士試験 実施状況(過去の年度)", "https://www.retio.or.jp/exam/exam_detail/", "平成26〜令和7年度"),
    "gyosei_stat": S("行政書士試験研究センター", "行政書士試験 結果の概要", "https://www.gyosei-shiken.or.jp/pdf/summary.pdf", "平成28〜令和7年度"),
    "sharosi_stat": S("厚生労働省", "社会保険労務士試験の合格者発表", "https://www.mhlw.go.jp/stf/newpage_76425.html", "第49〜58回"),
    "kentei_stat": S("日本商工会議所 検定試験", "簿記検定 受験者データ", "https://www.kentei.ne.jp/bookkeeping/candidate-data", "第163〜173回"),
    "kaigo_stat": S("厚生労働省", "介護福祉士国家試験の合格発表", "https://www.mhlw.go.jp/stf/newpage_71070.html", "第32〜38回"),
    "kango_stat": S("厚生労働省", "第115回看護師国家試験の合格発表", "https://www.mhlw.go.jp/general/sikaku/successlist/2026/siken03_04_05/about.html", "第115回"),
    "ipa_stat": S("情報処理推進機構(IPA)", "情報処理技術者試験 統計資料", "https://www.ipa.go.jp/shiken/reports/toukei_all.html", "平成28〜令和7年度"),
}

# One line at the foot of every page (the build wants a source for every page; the owner wants no links and no per-row citations)
SOURCES = {"official": {"org": "各試験団体・省庁・教育委員会", "table": "公式発表の日程", "url": "", "basis": "公表されている最新の回", "fetched": CHECKED}}
