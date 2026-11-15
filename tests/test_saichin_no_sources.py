"""saichin: 情報元(出典)の具体的な記載と、情報元への外部リンクは画面に出さない(オーナー指示 2026-11-15、D26 選択肢2)。

残すもの(法令・ライセンスが求める表記。根拠は政府標準利用規約 第2版(公共データ利用規約 第1.0版 PDL1.0)の「出典の記載」と「編集・加工の明示」):
  * 全ページのフッターの「出典: 厚生労働省「地域別最低賃金の全国一覧」を加工して作成。厚生労働省が作成したものではありません。」(リンクなし)
  * /cite/ と /data/(データの再利用の決まりを説明するページ)の、ライセンス(PDL1.0)の表記とそのリンク
  * /ranking/ratio/ の「賃金構造基本統計調査を加工して作成」の表記(リンクなし)
  * プライバシーポリシーの広告設定リンク(出典ではない)
広告(rel に sponsored、または px.a8.net)と、応募・申込の入口以外の外部リンクは、これ以外に出さない。
"""
import re
import unittest

from tests.test_saichin_pages import SiteFixture

WORDS = re.compile(r"出典|情報元|情報源|参考資料|参考文献|出どころ|確認元")
FOOTER_LINE = "出典: 厚生労働省「地域別最低賃金の全国一覧」を加工して作成。厚生労働省が作成したものではありません。"
FOOTER_GENERIC = "公式の発表をはじめとする複数の情報をもとにしています。"
LICENSE_PAGES = ("cite/index.html", "data/index.html")
# 公共データ利用規約 第1.0版 1.1 は、出典の記載例が「提供元(当該ページのURL)、PDL1.0(規約原文ページのURL)」の形(URLリンクを張る形にできる)。
# そのため、フッターの加工表記の出典リンク(厚労省の全国一覧)と、賃金統計の加工表記の出典リンク(e-Stat)は、記載例の URL として残す(窓口判断 2026-11-15)。
REQUIRED_NOTICE_LINKS = ("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/minimumichiran/index.html",
                         "https://www.e-stat.go.jp/stat-search/files?tclass=000001229518&cycle=0")
EXTERNAL_OK = ("https://www.digital.go.jp/resources/open_data/public_data_license_v1.0",   # PDL1.0 の条文(ライセンス表記)
               "https://adssettings.google.com/", "https://www.aboutads.info/", "https://policies.google.com/technologies/partner-sites")   # 広告の設定(出典ではない)


def external_non_ad_links(html: str) -> list[str]:
    out = []
    for m in re.finditer(r"<a\b([^>]*)>", html):
        attrs = m.group(1)
        h = re.search(r'href="(https?://[^"]+)"', attrs)
        if not h or "sponsored" in attrs or "px.a8.net" in h.group(1) or "saichin-sokuho.com" in h.group(1) or "calendar.google.com" in h.group(1):
            continue
        out.append(h.group(1))
    return out


def visible_text(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def source_words_outside_allowed(rel: str, html: str) -> list[str]:
    """出典の語が、必須の表記以外のところに出ていないか。フッターの必須の1行を除いて数える。"""
    text = visible_text(html)
    text = re.sub(r"出典: 厚生労働省「地域別最低賃金の全国一覧」を加工して作成。", "", text)
    if rel in LICENSE_PAGES:
        return []
    if rel == "ranking/ratio/index.html":
        text = re.sub(r"出典: 厚生労働省「賃金構造基本統計調査」[^。]*を加工して作成。", "", text)
    return [text[max(0, m.start() - 12):m.end() + 12] for m in WORDS.finditer(text)]


class NoSourcesOnScreenTest(SiteFixture):
    def pages(self):
        return [r for r in self.files if r.endswith(".html")]

    def test_no_external_link_except_ads_and_the_license(self):
        bad = {}
        for rel in self.pages():
            if rel.startswith("contact/"):
                continue   # お問い合わせフォームの入口(出典ではない)
            links = [u for u in external_non_ad_links(self.read(rel)) if u not in EXTERNAL_OK and u.replace("&amp;", "&") not in REQUIRED_NOTICE_LINKS]
            if links:
                bad[rel] = links
        self.assertEqual(bad, {})

    def test_the_license_link_is_only_on_the_license_pages(self):
        for rel in self.pages():
            has = EXTERNAL_OK[0] in self.read(rel)
            self.assertEqual(has, rel in LICENSE_PAGES, rel)

    def test_no_source_word_outside_the_required_notices(self):
        bad = {}
        for rel in self.pages():
            hits = source_words_outside_allowed(rel, self.read(rel))
            if hits:
                bad[rel] = hits[:3]
        self.assertEqual(bad, {})

    def test_every_page_keeps_the_required_processing_notice_and_the_generic_sentence(self):
        for rel in self.pages():
            text = visible_text(self.read(rel))
            self.assertIn(FOOTER_LINE, text, rel)
            self.assertIn(FOOTER_GENERIC, text, rel)

    def test_the_confirmation_dates_stay(self):
        self.assertIn("内容の確認日", self.read("guide/what-is/index.html") if (self.out / "guide/what-is/index.html").exists() else self.read("guide/faq/index.html"))
        self.assertIn("データの取得日", self.read("history/index.html"))

    def test_the_license_pages_keep_license_and_processing_notation(self):
        data = visible_text(self.read("data/index.html"))
        cite = visible_text(self.read("cite/index.html"))
        for text in (data, cite):
            self.assertIn("PDL1.0", text)
            self.assertIn("加工", text)


class DetectorHasTeethTest(unittest.TestCase):
    """負例: 出典の語・出典リンクが画面に出たら、この検査は落ちる。"""
    def test_detects_a_source_link(self):
        self.assertEqual(external_non_ad_links('<p><a href="https://www.mhlw.go.jp/x.html" rel="noopener" target="_blank">厚生労働省</a></p>'),
                         ["https://www.mhlw.go.jp/x.html"])

    def test_ignores_ads_and_own_links(self):
        html = ('<a href="https://px.a8.net/svt/ejp?a8mat=1" rel="nofollow">広告</a><a href="https://x.example/" rel="nofollow sponsored noopener">広告</a>'
                '<a href="https://saichin-sokuho.com/about/">運営者</a>')
        self.assertEqual(external_non_ad_links(html), [])

    def test_detects_a_source_note_in_a_body(self):
        self.assertTrue(source_words_outside_allowed("guide/x/index.html", "<main><h2>出典</h2><ul><li>厚生労働省</li></ul></main>"))
        self.assertTrue(source_words_outside_allowed("tokyo/index.html", "<p>この節の出典: 最低賃金法</p>"))

    def test_the_required_footer_line_alone_is_allowed(self):
        self.assertEqual(source_words_outside_allowed("tokyo/index.html", f"<footer><p>{FOOTER_LINE}</p></footer>"), [])


if __name__ == "__main__":
    unittest.main()
