import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from sites.yorokobu import build, content, ranking
from sokuhou import rakuten, sitecheck
from tests.test_yorokobu_fetch import FakeTransport, client, raw_item

FIX = Path(__file__).parent / "fixtures" / "yorokobu"
FILTERS = {"min_price": 500, "ng_words": ["訳あり", "中古"]}
CFG = {"site_url": "https://yorokobu-present.com", "site_name": "よろこぶプレゼント", "operator_name": "テスト運営",
       "contact_form_url": "https://example.com/form", "rakuten_affiliate_id": "aaaa1111.bbbb2222.cccc3333.dddd4444",
       "rakuten_tracking_id": "yorokobu", "amazon_tracking_id": None, "adsense_pub_id": None}


def ranked(code, rank, price=3000, name=None):
    return {**rakuten.normalize(raw_item(code, price, name=name or f"ギフト用 商品{code} 詰め合わせ")), "rank": rank}


def day(codes, names=None):
    return [ranked(c, i + 1, name=(names or {}).get(c)) for i, c in enumerate(codes)]


def codes(n, prefix="p"):
    return [f"{prefix}{i}" for i in range(n)]


class ClientTest(unittest.TestCase):
    def test_the_ranking_call_uses_the_ranking_endpoint_with_age_and_sex_and_no_affiliate_redirect(self):
        t = FakeTransport(lambda u: [{**raw_item("a", 2000), "rank": 1}])
        c = rakuten.Client("APP", "KEY", "https://yorokobu-present.com/", transport=t, sleep=lambda s: None)
        items = c.ranking(age=20, sex=1, page=1)
        url, headers = t.urls[0]
        self.assertTrue(url.startswith("https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601?"))
        for part in ("age=20", "sex=1", "page=1", "applicationId=APP", "accessKey=KEY", "formatVersion=2"):
            self.assertIn(part, url)
        self.assertNotIn("affiliateId", url)
        self.assertEqual(headers["Referer"], "https://yorokobu-present.com/")
        self.assertEqual(items[0]["rank"], 1)

    def test_a_genre_is_asked_for_alone_without_age_or_sex(self):
        seg = ranking.SEGMENTS["g-sweets"]
        t = FakeTransport(lambda u: [{**raw_item("a", 2000), "rank": 1}])
        c = rakuten.Client("APP", "KEY", "https://x/", transport=t, sleep=lambda s: None)
        ranking.snapshot_segment(c, seg)
        url = t.urls[0][0]
        self.assertIn("genreId=551167", url)
        self.assertNotIn("&age=", url)
        self.assertNotIn("&sex=", url)
        self.assertEqual(seg["kind"], "genre")

    def test_every_genre_has_a_unique_slug_and_id_and_comes_before_the_people_lists(self):
        segs = ranking.all_segments()
        self.assertEqual(len({s["slug"] for s in segs}), len(segs))
        self.assertEqual(len({s["genre"] for s in segs if s["kind"] == "genre"}), len(ranking.GENRES))
        kinds = [s["kind"] for s in segs]
        self.assertEqual(kinds, sorted(kinds, key=lambda k: k != "genre"))          # all genres first

    def test_segments_are_age_by_sex_and_the_oldest_group_says_and_over(self):
        segs = ranking.segments()
        self.assertEqual(len(segs), 10)
        self.assertEqual({(s["age"], s["sex"]) for s in segs}, {(a, x) for a in (10, 20, 30, 40, 50) for x in (0, 1)})
        self.assertEqual(ranking.SEGMENTS["f50"]["label"], "50代以上女性")
        self.assertEqual(ranking.SEGMENTS["m20"]["label"], "20代男性")

    def test_a_snapshot_keeps_the_places_rakuten_reports_and_skips_items_that_cannot_be_shown(self):
        raw = [{**raw_item("a", 2000), "rank": 1}, {**raw_item("b", 0), "rank": 2}, {**raw_item("c", 1500), "rank": 3}]
        c = rakuten.Client("A", "K", "https://x/", transport=FakeTransport(lambda u: raw), sleep=lambda s: None)
        snap = ranking.snapshot_segment(c, ranking.SEGMENTS["f20"])
        self.assertEqual([(i["code"], i["rank"]) for i in snap], [("a", 1), ("c", 3)])


class HistoryTest(unittest.TestCase):
    def test_update_adds_today_trims_old_days_and_keeps_a_segment_that_failed_today(self):
        s1 = ranking.update(None, {"f20": day(["a", "b"]), "m20": day(["x"])}, date(2026, 10, 1))
        s2 = ranking.update(s1, {"f20": day(["b", "a"])}, date(2026, 10, 2))                # m20 failed today
        self.assertEqual(s2["segments"]["f20"]["history"], {"2026-10-01": [["a", 1], ["b", 2]], "2026-10-02": [["b", 1], ["a", 2]]})
        self.assertEqual(s2["segments"]["m20"]["date"], "2026-10-01")                       # untouched
        later = date(2026, 10, 1) + timedelta(days=ranking.HISTORY_DAYS + 5)
        s3 = ranking.update(s2, {"f20": day(["a"])}, later)
        self.assertEqual(list(s3["segments"]["f20"]["history"]), [later.isoformat()])         # the two October days are older than the kept window

    def test_only_kept_products_are_stored_and_the_history_keeps_their_real_places(self):
        items = [ranked("a", 7), ranked("b", 31), ranked("junk", 12, name="ソーラーライト 屋外")]
        s = ranking.update(None, {"g-sweets": items}, date(2026, 10, 1), keep=lambda i: i["code"] != "junk")
        seg = s["segments"]["g-sweets"]
        self.assertEqual([i["code"] for i in seg["items"]], ["a", "b"])
        self.assertEqual(seg["history"]["2026-10-01"], [["a", 7], ["b", 31]])
        self.assertEqual(seg["depth"], ranking.PAGES * ranking.PLACES)

    def test_risers_use_the_real_rakuten_places_not_the_position_in_our_short_list(self):
        s = ranking.update(None, {"g-sweets": [ranked("a", 50), ranked("b", 60), ranked("c", 70)]}, date(2026, 10, 1))
        s = ranking.update(s, {"g-sweets": [ranked("b", 40), ranked("a", 55), ranked("d", 90)]}, date(2026, 10, 2))
        mv = ranking.movers(s["segments"]["g-sweets"])
        self.assertEqual(mv["risers"], [("b", 20)])                 # 60 -> 40; a fell from 50 to 55
        self.assertEqual(mv["entered"], ["d"])
        self.assertEqual(mv["stay"], {"b": 2, "a": 2, "d": 1})

    def test_history_written_by_the_first_version_still_works(self):
        old = {"segments": {"f20": {"label": "20代女性", "kind": "people", "date": "2026-10-02", "items": [],
                                    "history": {"2026-10-01": ["a", "b", "c"], "2026-10-02": ["b", "a", "c"]}}}}
        mv = ranking.movers(old["segments"]["f20"])
        self.assertEqual(mv["risers"], [("b", 1)])
        self.assertEqual(mv["stay"], {"b": 2, "a": 2, "c": 2})

    def test_several_pages_are_fetched_with_continuing_places_and_stop_when_the_ranking_ends(self):
        pages = {1: 30, 2: 30, 3: 12}

        def reply(url):
            n = int(url.split("page=")[1].split("&")[0])
            return [raw_item(f"p{n}-{i}", 1000 + i, name=f"ギフト商品 p{n}-{i} 詰め合わせ") for i in range(pages.get(n, 0))]
        t = FakeTransport(reply)
        c = rakuten.Client("A", "K", "https://x/", transport=t, sleep=lambda s: None)
        snap = ranking.snapshot_segment(c, ranking.SEGMENTS["g-sweets"])
        self.assertEqual(len(t.urls), 3)                                # the third page was short: no fourth request
        self.assertEqual(len(snap), 72)
        self.assertEqual([i["rank"] for i in snap][:3] + [snap[-1]["rank"]], [1, 2, 3, 72])

    def test_a_segment_fetched_today_with_nothing_kept_does_not_keep_yesterdays_unfiltered_items(self):
        s = ranking.update(None, {"f20": day(codes(5))}, date(2026, 10, 1))                        # kept everything (no filter yet)
        s = ranking.update(s, {"f20": day(codes(5))}, date(2026, 10, 2), keep=lambda i: False)      # today the filter keeps nothing
        seg = s["segments"]["f20"]
        self.assertEqual(seg["items"], [])
        self.assertEqual(seg["date"], "2026-10-02")
        self.assertEqual(seg["history"]["2026-10-02"], [])

    def test_seasonal_decoration_costumes_and_everyday_clothes_are_not_gifts_even_when_the_title_says_present(self):
        for n in ("クリスマスツリー 150cm 高級 プレゼント", "ハロウィン コスプレ 子供 誕生日 ギフト", "ワイシャツ 長袖 メンズ ギフト プレゼント", "オーナメント セット ギフト"):
            self.assertFalse(ranking.shown(ranked("x", 1, name=n), FILTERS), n)
        self.assertTrue(ranking.shown(ranked("y", 1, name="誕生日 ギフト 高級 日本酒 飲み比べセット"), FILTERS))
        self.assertFalse(ranking.shown(ranked("z", 1, name="誕生日 クリスマス 部屋着 パジャマ"), FILTERS))      # a season word alone is not enough

    def test_only_genres_whose_products_are_given_as_presents_are_fetched(self):
        labels = {g[2] for g in ranking.GENRES}
        for gone in ("レディースファッション", "メンズファッション", "ホビー", "おもちゃ", "キッズ・ベビー・マタニティ"):
            self.assertNotIn(gone, labels)
        self.assertIn("ワイン", labels)
        self.assertNotIn("ビール・洋酒", labels)

    def test_segments_that_are_no_longer_fetched_are_dropped_from_the_store(self):
        old = {"segments": {"g-mens": {"label": "x", "kind": "genre", "items": [], "history": {}}, "g-wine": {"label": "ワイン", "kind": "genre", "date": "2026-10-01", "items": [], "history": {}}}}
        s = ranking.update(old, {"g-wine": day(codes(3))}, date(2026, 10, 2))
        self.assertEqual(sorted(s["segments"]), ["g-wine"])

    def test_an_empty_fetch_does_not_wipe_the_stored_segment(self):
        s1 = ranking.update(None, {"f20": day(["a", "b"])}, date(2026, 10, 1))
        s2 = ranking.update(s1, {"f20": []}, date(2026, 10, 2))
        self.assertEqual(s2["segments"]["f20"]["date"], "2026-10-01")

    def test_movers_risers_entries_and_streaks_are_computed_from_the_history(self):
        s = ranking.update(None, {"f20": day(["a", "b", "c", "d"])}, date(2026, 10, 1))
        s = ranking.update(s, {"f20": day(["a", "c", "e", "b"])}, date(2026, 10, 2))
        s = ranking.update(s, {"f20": day(["c", "a", "e", "f"])}, date(2026, 10, 3))
        mv = ranking.movers(s["segments"]["f20"])
        self.assertEqual(mv["days"], 3)
        self.assertEqual(mv["risers"], [("c", 1)])                         # only strictly higher places count: c 2 -> 1 (a fell, e stayed)
        self.assertEqual(mv["entered"], ["f"])
        self.assertEqual(mv["stay"]["a"], 3)
        self.assertEqual(mv["stay"]["c"], 3)
        self.assertEqual(mv["stay"]["e"], 2)
        self.assertEqual(mv["stay"]["f"], 1)

    def test_one_day_of_history_has_no_movers(self):
        s = ranking.update(None, {"f20": day(["a", "b"])}, date(2026, 10, 1))
        mv = ranking.movers(s["segments"]["f20"])
        self.assertEqual((mv["risers"], mv["entered"]), ([], []))

    def test_price_facts_are_plain_numbers(self):
        items = [{"price": p} for p in (500, 1000, 2000, 3000, 9000, 12000)]
        f = ranking.price_facts(items)
        self.assertEqual((f["n"], f["median"], f["le3000"], f["ge10000"], f["min"], f["max"]), (6, 2500, 4, 1, 500, 12000))
        self.assertIsNone(ranking.price_facts(items[:3]))


class ViewTest(unittest.TestCase):
    def store(self, extra=None):
        names = {"p0": "トイレットペーパー 12ロール 96個", "p1": "ミネラルウォーター 2L ケース販売", "p2": "訳あり 詰め合わせ", **(extra or {})}
        items = day(codes(14), names)
        s = ranking.update(None, {"f20": items}, date(2026, 10, 1))
        return ranking.update(s, {"f20": day(["p5", "p3", "p4"] + codes(14)[6:] + ["p0"], names)}, date(2026, 10, 2))

    def test_daily_necessities_and_ng_words_are_left_out_but_places_stay_the_real_ones(self):
        v = ranking.view(self.store(), FILTERS)
        sg = v["segments"]["f20"]
        shown = [i["code"] for i in sg["items"]]
        for gone in ("p0", "p1", "p2"):
            self.assertNotIn(gone, shown)
        self.assertEqual(sg["items"][0]["rank"], 1)                                # p5 is Rakuten's place 1 that day
        self.assertEqual(sg["items"][0]["code"], "p5")

    def test_risers_come_from_the_previous_day_and_only_from_shown_products(self):
        sg = ranking.view(self.store(), FILTERS)["segments"]["f20"]
        self.assertTrue(sg["risers"])
        self.assertTrue(all(g > 0 for _, g in sg["risers"]))
        self.assertEqual(sg["risers"][0][0]["code"], "p5")                          # 6th -> 1st
        self.assertEqual(sg["risers"][0][1], 5)

    def test_lenses_discs_diapers_and_bulk_staples_are_left_out(self):
        names = ["カラコン ワンデー 30枚", "コンタクトレンズ 2week", "Moonlit (初回盤1(Blu-ray)＋通常盤セット)", "メリーズ エアスルー パンツ", "白米 無洗米 10kg",
                 "福袋おせち 2027", "ブレンド米 5kg", "プロテイン 3kg"]
        for n in names:
            self.assertFalse(ranking.shown(ranked("x", 1, name=n), FILTERS), n)
        self.assertTrue(ranking.shown(ranked("y", 1, name="国産素材の焼き菓子 詰め合わせ 12個入り"), FILTERS))

    def test_only_products_whose_title_says_they_are_a_gift_are_shown(self):
        yes = ["誕生日 プレゼント 花束 おまかせSサイズ", "リンツ アソート ギフト 36個", "日本酒 飲み比べセット 父の日 ギフト 720ml 3本", "ペア マグカップ 名入れ"]
        no = ["ソーラーライト 屋外 防水 ガーデンライト", "ワイシャツ 長袖 メンズ ノーアイロン", "黒霧島 芋焼酎 25度 1800ml パック 6本 1ケース", "リビング ラグ 洗える 3畳",
              "焼酎 ギフト プレゼント 父の日 1.8L パック × 6本 1ケース"]
        for n in yes:
            self.assertTrue(ranking.shown(ranked("y", 1, name=n), FILTERS), n)
        for n in no:
            self.assertFalse(ranking.shown(ranked("y", 1, name=n), FILTERS), n)

    def test_a_very_expensive_product_is_not_shown_even_if_it_says_gift(self):
        self.assertFalse(ranking.shown(ranked("z", 1, price=120000, name="ギフト プレゼント 高級 腕時計"), FILTERS))

    def test_real_committed_data_if_present_always_produces_a_valid_view(self):
        store = ranking.load()
        if store is None:
            self.skipTest("no committed ranking data yet")
        v = ranking.view(store, content.load()["filters"])
        for slug in (v or {"order": []})["order"]:
            sg = v["segments"][slug]
            self.assertGreaterEqual(len(sg["items"]), 8)
            self.assertTrue(all(i["price"] > 0 and i["url"].startswith("https://") for i in sg["items"]))

    def test_a_segment_with_too_few_products_has_no_page_and_no_data_means_no_ranking(self):
        s = ranking.update(None, {"f20": day(codes(5))}, date(2026, 10, 1))
        self.assertIsNone(ranking.view(s, FILTERS))
        self.assertIsNone(ranking.view(None, FILTERS))
        self.assertIsNone(ranking.view({"segments": {}}, FILTERS))


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = content.load(FIX)
        cls.items = json.loads((FIX / "items.json").read_text(encoding="utf-8"))
        names = {"p3": "トイレットペーパー まとめ買い"}
        s = ranking.update(None, {"f20": day(codes(16), names), "m40": day(codes(16, "q"))}, date(2026, 10, 6))
        cls.store = ranking.update(s, {"f20": day(codes(16)[5:6] + codes(16)[:5] + codes(16)[6:] , names), "m40": day(codes(16, "q"))}, date(2026, 10, 7))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        build.render_site(cls.c, cls.items, CFG, cls.out, release=True, today=date(2026, 10, 7), ranking=cls.store)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        build.RANKING_ON = False

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_the_hub_and_the_segment_pages_exist_and_are_linked_from_the_nav_and_the_home_page(self):
        for rel in ("ranking/index.html", "ranking/f20/index.html", "ranking/m40/index.html"):
            self.assertTrue((self.out / rel).exists(), rel)
        self.assertFalse((self.out / "ranking/f30/index.html").exists())           # no data for that segment: no page
        for page in ("index.html", "theme/index.html"):
            self.assertIn('href="/ranking/"', self.read(page))
        self.assertIn("/ranking/f20/", self.read("sitemap.xml"))

    def test_products_link_through_the_affiliate_id_with_the_pr_label_and_the_dated_disclaimer(self):
        html = self.read("ranking/f20/index.html")
        self.assertIn("https://hb.afl.rakuten.co.jp/hgc/aaaa1111.bbbb2222.cccc3333.dddd4444/yorokobu?pc=", html)
        self.assertIn('rel="sponsored nofollow noopener"', html)
        self.assertIn('<span class="pr-chip">PR</span>', html)
        self.assertIn("価格・在庫は2026年10月7日時点の情報です", html)
        self.assertNotIn("Amazonのアソシエイト", html)

    def test_what_changed_since_yesterday_is_shown_with_true_numbers(self):
        html = self.read("ranking/f20/index.html")
        self.assertIn("きのうより、順位を上げた", html)
        self.assertIn("前日より5つ順位アップ(現在1位)", html)
        hub = self.read("ranking/index.html")
        self.assertIn("きのうより、順位を上げた商品", hub)
        self.assertIn("20代女性で、前日より5つ順位アップ", hub)

    def test_daily_necessities_are_not_shown(self):
        self.assertNotIn("トイレットペーパー", self.read("ranking/f20/index.html"))

    def test_the_built_ranking_pages_pass_the_site_checker_and_no_page_links_to_a_missing_one(self):
        problems = sitecheck.check_dir(self.out, CFG["site_url"], skip=("lists",))
        self.assertEqual([p for p in problems if "ranking" in p], [], problems[:10])

    def test_a_single_segment_builds_without_empty_sections(self):
        only = {"version": 1, "updated": "2026-10-07", "segments": {"f20": self.store["segments"]["f20"]}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(self.c, self.items, CFG, out, release=True, today=date(2026, 10, 7), ranking=only)
            self.assertTrue((out / "ranking/f20/index.html").exists())
            self.assertEqual([p for p in sitecheck.check_dir(out, CFG["site_url"], skip=("lists",)) if "ranking" in p], [])
            self.assertEqual([p for p in sitecheck.check_dir(out, CFG["site_url"]) if "ranking" in p and "empty" in p], [])
        build.RANKING_ON = False

    def test_genre_pages_use_the_genre_wording_and_the_hub_groups_genres_and_people(self):
        names = {}
        s = ranking.update(None, {"g-sweets": day(codes(16, "s")), "f20": day(codes(16))}, date(2026, 10, 6))
        s = ranking.update(s, {"g-sweets": day(codes(16, "s")), "f20": day(codes(16))}, date(2026, 10, 7))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(self.c, self.items, CFG, out, release=True, today=date(2026, 10, 7), ranking=s)
            g = (out / "ranking/g-sweets/index.html").read_text(encoding="utf-8")
            self.assertIn("スイーツ・お菓子の、<wbr>いま売れている商品", g)
            f = (out / "ranking/f20/index.html").read_text(encoding="utf-8")
            self.assertIn("20代女性に、<wbr>いま売れている商品", f)
            hub = (out / "ranking/index.html").read_text(encoding="utf-8")
            self.assertIn("ジャンルから選ぶ", hub)
            self.assertIn("世代と性別から選ぶ", hub)
            self.assertEqual([p for p in sitecheck.check_dir(out, CFG["site_url"], skip=("lists",)) if "ranking" in p], [])
        build.RANKING_ON = False

    def test_without_ranking_data_there_are_no_ranking_pages_and_no_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s"
            build.render_site(self.c, self.items, CFG, out, release=True, today=date(2026, 10, 7), ranking=None)
            self.assertFalse((out / "ranking").exists())
            self.assertNotIn("/ranking/", (out / "index.html").read_text(encoding="utf-8"))
        build.RANKING_ON = False


if __name__ == "__main__":
    unittest.main()
