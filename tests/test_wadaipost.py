"""wadai post checks (sokuhou/wadaipost.py): the three owner-approved-style templates pass, and every rule has a negative case that must be caught
(the rule of this project: a check that is added must be shown to catch the past fault).  No network, no Threads, no private data."""
import copy
import json
import re
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sokuhou import wadaipost as w

ROOT = Path(__file__).resolve().parents[1]

REPLY = "【PR】選ぶときに見る点を、基準ごとにまとめました。\nhttps://example.com/fuyu/202611-ritto/"


def post(**kw):
    p = {"id": "A-01", "account": "A", "type": "T1S", "topic_id": "202611-ritto", "topic_kind": "E", "topic_category": "fuyu", "calendar_status": "◎",
         "calendar_date": "2026-11-07", "evidence_id": "nao-2026-rekiyou", "scheduled_at": "2026-11-07T12:30", "product_kind": "electric_blanket",
         "facts": ["11月7日は立冬"],
         "body": "11月7日は立冬。\n暦のうえでは冬の始まりだよ。\n寝るときの冷えは、先に手を打つと楽かも。\n電気毛布なら、消し忘れを防ぐ機能があるか見てね☺️",
         "reply": REPLY}
    p.update(kw)
    return p


T2 = post(id="A-02", type="T2", topic_id="202611-tsunami", topic_category="bousai", calendar_date="2026-11-05", scheduled_at="2026-11-05T12:30",
          product_kind="radio", facts=["11月5日は津波防災の日"],
          body="11月5日は津波防災の日。\n情報を受け取る手段を、ひとつ増やす日にしてみない？\n停電しても使える手段があると、慌てにくいかも。\nラジオなら、電池と手回し、どちらで動くかを見ておこうね📻")
T3 = post(id="A-03", type="T3", topic_id="202611-renkyu", topic_category="bousai", calendar_date="2026-11-21", scheduled_at="2026-11-21T12:30",
          product_kind="water", facts=["3連休"],
          body="3連休に、備蓄を数えてみよう。\n家族の人数×日数で、必要な量が出るよ。\nたとえば3人で3日なら、3×3＝9人日分（例だよ）。\n目安の量は、国の資料に載っているとおりにしてね。\n足りない物だけ、メモに書き出そう📝")

ACCOUNTS = {"accounts": [{"id": "A", "token_secret": "THREADS_TOKEN_A", "categories": ["bousai", "fuyu"], "daily_max": 2, "enabled": True},
                         {"id": "D", "token_secret": "THREADS_TOKEN_D", "categories": ["kaden"], "daily_max": 2, "enabled": True}]}


def codes(findings):
    return {f.code for f in findings}


class TestPostsPass(unittest.TestCase):
    def test_three_templates_pass(self):
        for p in (post(), T2, T3):
            self.assertEqual([f.line() for f in w.check_post(p)], [], p["id"])

    def test_batch_of_the_three_passes(self):
        self.assertEqual([f.line() for f in w.check_batch([post(), T2, T3], ACCOUNTS)], [])


class TestPostNegatives(unittest.TestCase):
    def assertCaught(self, code, **kw):
        found = codes(w.check_post(post(**kw)))
        self.assertIn(code, found, f"{code} was not caught for {kw}")

    def test_p01_evidence(self):
        self.assertCaught("P01", evidence_id=None)
        self.assertCaught("P01", calendar_status="△")
        self.assertCaught("P01", topic_kind="X")
        g = dict(topic_kind="W", evidence_date="2026-11-07T11:00", human_checked=True)
        self.assertEqual([f for f in w.check_post(post(**g)) if f.code == "P01"], [])
        self.assertCaught("P01", **{**g, "evidence_date": "2026-11-01T11:00"})        # older than 72 hours
        self.assertCaught("P01", **{**g, "human_checked": False})                      # nobody read the official text
        self.assertCaught("P01", **{**g, "evidence_date": None})

    def test_p02_alarm(self):
        for word in ("緊急", "今すぐ", "命を守る", "絶対", "必ず", "買い占め"):
            self.assertCaught("P02", body=post()["body"] + word)

    def test_p03_experience(self):
        for word in ("我が家では", "使ってみた", "愛用しています", "買いました"):
            self.assertCaught("P03", body=post()["body"] + word)

    def test_p04_price_authority(self):
        for word in ("最安", "1,980円", "人気No.1", "専門家によると", "ランキング上位", "話題の"):
            self.assertCaught("P04", body=post()["body"] + word)

    def test_p05_product_data(self):
        self.assertCaught("P05", body=post()["body"] + "\nhttps://item.rakuten.co.jp/shop/x/")
        found = codes(w.check_post(post(body=post()["body"] + "ブランドX"), {"product_terms": ["ブランドX"]}))
        self.assertIn("P05", found)

    def test_p06_length_counts_emoji_by_bytes(self):
        self.assertEqual(w.weighted_length("ab"), 2)
        self.assertEqual(w.weighted_length("あ"), 1)                 # Japanese counts one
        self.assertEqual(w.weighted_length("📻"), 4)                 # an emoji counts its UTF-8 bytes
        self.assertGreater(w.weighted_length("☺️"), 2)
        self.assertCaught("P06", body=post()["body"] + "あ" * 460)
        # 100 emoji = 400 weighted characters although only 100 characters
        self.assertCaught("P06", body=post()["body"] + "📻" * 100)
        self.assertCaught("P06", body="  ")

    def test_p07_links(self):
        self.assertCaught("P07", reply=REPLY + "\nhttps://example.com/b/")

    def test_p08_pr_line(self):
        self.assertCaught("P08", reply="こちら\nhttps://example.com/")
        self.assertCaught("P08", reply="【PR】\nhttps://example.com/")             # no line saying what the link offers
        self.assertCaught("P08", reply="【PR】https://example.com/\nhttps://example.com/x")
        self.assertCaught("P08", body="【PR】" + post()["body"])

    def test_p09_off_limits(self):
        for word in ("ボジョレー", "投資", "サプリ", "選挙", "パチンコ", "免疫", "違法です"):
            self.assertCaught("P09", body=post()["body"] + word)

    def test_p10_layers(self):
        # the fact line holds a hedge
        self.assertCaught("P10", body="11月7日は立冬かもしれない。\n冷えるかも。\n毛布を見てね。")
        # no view line
        self.assertCaught("P10", body="11月7日は立冬。\n冬の始まりだよ。\n毛布を見てね。")
        # the fact line has neither a date nor an issuer
        self.assertCaught("P10", body="冬の始まりだよ。\n冷えるかも。\n毛布を見てね。")
        # too few lines
        self.assertCaught("P10", body="11月7日は立冬。\n冷えるかも。")

    def test_p11_numbers(self):
        self.assertCaught("P11", body=post()["body"] + "\n気温は5度を下回る。")                 # an invented number
        self.assertCaught("P11", body=post()["body"] + "\n3割の家庭が使う。")
        self.assertEqual([f for f in w.check_post(T3) if f.code == "P11"], [])               # numbers in a formula line marked as an example are fine


class TestBatchNegatives(unittest.TestCase):
    def test_p12_similar_same_account(self):
        a = post()
        b = post(id="A-09", scheduled_at="2026-11-08T12:30", topic_id="x", product_kind="other")
        self.assertIn("P12", codes(w.check_batch([a, b])))

    def test_p12_same_topic_on_two_accounts(self):
        a = post()
        d = post(id="D-01", account="D", scheduled_at="2026-11-07T16:00", body="冬の始まりの日だね。\n暖房の電気代は、消費電力を見ると分かりそう。\n計算の仕方をまとめたよ。", product_kind="meter", facts=[])
        self.assertTrue(any("same topic" in f.msg for f in w.check_batch([a, d])))

    def test_p12_same_product_kind(self):
        a = post()
        b = post(id="A-08", scheduled_at="2026-11-10T12:30", topic_id="t2", body="まったく別の文章。\n中身も違うかも。\n別の話だよ。", facts=[])
        self.assertTrue(any("product kind" in f.msg for f in w.check_batch([a, b])))

    def test_p13_gap_between_accounts(self):
        a = post()
        d = post(id="D-02", account="D", scheduled_at="2026-11-07T13:00", topic_id="t3", topic_category="kaden", product_kind="m", body="別の話。\n別かも。\nこれも別だよ。", facts=[])
        self.assertTrue(any(f.code == "P13" and "minutes" in f.msg for f in w.check_batch([a, d], ACCOUNTS)))

    def test_p13_daily_limits(self):
        ps = [post(id=f"A-1{i}", scheduled_at=f"2026-11-07T{9 + 3 * i:02d}:00", topic_id=f"t{i}", product_kind=f"k{i}", type=["T1S", "T2", "T3", "T1S"][i % 4],
                   body=f"{'あいうえお' * (i + 3)}{i}の話。\n{'かきくけこ' * (i + 2)}かも。\n{'さしすせそ' * (i + 2)}。", facts=[f"{i}"]) for i in range(4)]
        found = w.check_batch(ps, ACCOUNTS)
        self.assertTrue(any("breaking posts" in f.msg for f in found))
        self.assertTrue(any("daily_max" in f.msg for f in found))

    def test_p13_same_type_three_times(self):
        ps = [post(id=f"A-2{i}", scheduled_at=f"2026-11-0{3 + i}T12:30", topic_id=f"u{i}", product_kind=f"u{i}",
                   body=f"{'あいうえお' * (i + 3)}話{i}。\n{'かきくけこ' * (i + 2)}かも。\n{'さしすせそ' * (i + 4)}。", facts=[]) for i in range(3)]
        self.assertTrue(any("three times in a row" in f.msg for f in w.check_batch(ps)))

    def test_p14_account_and_approval(self):
        off = {"accounts": [dict(ACCOUNTS["accounts"][0], enabled=False)]}
        self.assertTrue(any(f.code == "P14" and "not enabled" in f.msg for f in w.check_batch([post()], off)))
        self.assertTrue(any(f.code == "P14" and "category" in f.msg for f in w.check_batch([post(topic_category="kaden")], ACCOUNTS)))
        self.assertTrue(any(f.code == "P14" and "not in accounts" in f.msg for f in w.check_batch([post(account="Z")], ACCOUNTS)))
        appr = {"approved": [{"type": "T1S", "account": "A", "product_kinds": ["electric_blanket"]}]}
        self.assertEqual([f for f in w.check_batch([post()], ACCOUNTS, ctx={"approvals": appr}) if f.code == "P14"], [])
        self.assertTrue(any("not approved" in f.msg for f in w.check_batch([T2], ACCOUNTS, ctx={"approvals": appr})))
        self.assertTrue(any("outside the approved" in f.msg for f in w.check_batch([post(product_kind="radio")], ACCOUNTS, ctx={"approvals": appr})))


ART = {"id": "m-1", "updated": "2026-11-07", "ledger": ["国立天文台"], "sections": [
    {"layer": "fact", "heading": "確認できた事実(11月7日時点)", "bullets": ["国立天文台は、2026年の立冬を11月7日と暦要項に載せている。"]},
    {"layer": "opinion", "heading": "考察(編集部の見方)", "paras": ["朝晩の冷え込みが強まる頃で、寝具の見直しを始める人が増えるのではないか。あくまで編集部の見方で、地域によって違う。"]},
    {"layer": "prep", "heading": "備え・選び方", "paras": ["電気毛布は、消し忘れを防ぐ機能があるかを先に見る。"]},
    {"layer": "history", "heading": "更新履歴", "bullets": ["11月7日 追記: 立冬の日を反映した。"]}]}


def art(**changes):
    a = copy.deepcopy(ART)
    for k, v in changes.items():
        a[k] = v
    return a


def with_sections(**by_layer):
    a = copy.deepcopy(ART)
    for s in a["sections"]:
        if s["layer"] in by_layer:
            s.update(by_layer[s["layer"]])
    return a


class TestArticle(unittest.TestCase):
    def test_base_article_passes(self):
        self.assertEqual([f.line() for f in w.check_article(ART, {"today": "2026-11-08"})], [])

    def test_a01_layers(self):
        a = art(sections=ART["sections"][:2] + ART["sections"][3:])
        self.assertIn("A01", codes(w.check_article(a)))
        a = art(sections=[ART["sections"][1], ART["sections"][0]] + ART["sections"][2:])         # wrong order
        self.assertIn("A01", codes(w.check_article(a)))
        self.assertIn("A01", codes(w.check_article(with_sections(opinion={"heading": "まとめ"}))))

    def test_a02_layer_mix(self):
        self.assertIn("A02", codes(w.check_article(with_sections(fact={"bullets": ["国立天文台は11月7日に立冬と発表した可能性がある。"]}))))
        self.assertIn("A02", codes(w.check_article(with_sections(opinion={"paras": ["この冬は寒くなります。"]}))))

    def test_a03_fact_has_issuer_and_date(self):
        self.assertIn("A03", codes(w.check_article(with_sections(fact={"bullets": ["立冬は11月7日だ。"]}))))
        self.assertIn("A03", codes(w.check_article(with_sections(fact={"bullets": ["国立天文台は立冬を暦要項に載せている。"]}))))

    def test_a04_numbers(self):
        self.assertIn("A04", codes(w.check_article(with_sections(prep={"paras": ["電気毛布の消費電力は50Wほど。"]}))))
        self.assertNotIn("A04", codes(w.check_article(with_sections(prep={"paras": ["3人で3日なら3×3＝9人日分（例）。"]}))))

    def test_a05_unknown_proper_noun(self):
        self.assertIn("A05", codes(w.check_article(with_sections(opinion={"paras": ["テスト社の発表を受けて、備えが広がるのではないか。"]}))))
        self.assertIn("A05", codes(w.check_article(with_sections(opinion={"paras": ["台風第99号の影響が出るかもしれない。"]}))))
        ok = art(ledger=["国立天文台", "テスト社"])
        ok["sections"] = with_sections(opinion={"paras": ["テスト社の発表を受けて、備えが広がるのではないか。"]})["sections"]
        self.assertNotIn("A05", codes(w.check_article(ok)))

    def test_a06_criticism_of_a_named_party(self):
        a = art(ledger=["国立天文台", "テスト社"])
        a["sections"] = with_sections(opinion={"paras": ["テスト社の怠慢が原因ではないか。"]})["sections"]
        self.assertIn("A06", codes(w.check_article(a)))

    def test_a07_a08_words(self):
        self.assertIn("A07", codes(w.check_article(with_sections(prep={"paras": ["今すぐ買うべきだ。"]}))))
        self.assertIn("A07", codes(w.check_article(with_sections(prep={"paras": ["私の家で使ってみた。"]}))))
        self.assertIn("A07", codes(w.check_article(with_sections(prep={"paras": ["免疫が上がる。"]}))))
        self.assertIn("A08", codes(w.check_article(with_sections(prep={"paras": ["最安のものを選ぶ。"]}))))
        self.assertIn("A08", codes(w.check_article(with_sections(prep={"paras": ["1,980円で買える。"]}))))

    def test_a09_history_needs_a_real_change(self):
        prev = copy.deepcopy(ART)
        a = art(updated="2026-11-09", previous=prev)
        self.assertIn("A09", codes(w.check_article(a)))                                  # only the date changed
        b = art(updated="2026-11-09", previous=prev)
        b["sections"] = with_sections(prep={"paras": ["電気毛布は、消し忘れを防ぐ機能と、コードの長さを先に見る。"]})["sections"]
        self.assertNotIn("A09", codes(w.check_article(b)))

    def test_a10_freshness(self):
        self.assertTrue(any("stale" in f.msg for f in w.check_article(ART, {"today": "2026-12-20"})))
        self.assertTrue(any("warn" in f.msg for f in w.check_article(ART, {"today": "2026-11-20"})))


class TestAccountsAndDryRun(unittest.TestCase):
    def test_accounts_must_not_hold_a_token(self):
        bad = {"accounts": [{"id": "A", "token": "THAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "token_secret": "THREADS_TOKEN_A", "categories": ["x"], "daily_max": 2}]}
        self.assertTrue(w.validate_accounts(bad))
        bad2 = {"accounts": [{"id": "A", "token_secret": "THAAabcdefghijklmnopqrstuvwxyz", "categories": ["x"], "daily_max": 2}]}
        self.assertTrue(w.validate_accounts(bad2))                                       # a token value instead of a secret NAME
        bad3 = {"accounts": [{"id": "A", "token_secret": "THREADS_TOKEN_A", "categories": ["x"], "daily_max": 9}]}
        self.assertTrue(w.validate_accounts(bad3))
        self.assertEqual(w.validate_accounts(ACCOUNTS), [])

    def make(self, d: Path, rows, accounts=ACCOUNTS):
        w.write_jsonl(d / "queue.jsonl", rows)
        (d / "accounts.json").write_text(json.dumps(accounts, ensure_ascii=False), encoding="utf-8")
        (d / "approvals.json").write_text(json.dumps({"approved": [{"type": "T1S", "account": "A", "product_kinds": ["electric_blanket", "x1", "x2", "x3"]}]}), encoding="utf-8")

    def test_dry_run_posts_only_the_clean_due_approved(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            good = dict(post(), state="approved")
            bad = dict(post(id="A-05", scheduled_at="2026-11-07T08:00", topic_id="zz", product_kind="x1", body="木枯らしが吹く夜は早めの支度だね。\nひざ掛けもあると楽そう。\n今すぐ選んでね！", facts=[]), state="approved")
            later = dict(post(id="A-06", scheduled_at="2026-11-30T12:30", topic_id="yy", product_kind="x2", body="全然別の文章です。\nこれも別かも。\nさらに別の話。", facts=[]), state="approved")
            draft = dict(post(id="A-07", scheduled_at="2026-11-09T09:00", topic_id="ww", product_kind="x3", body="湯たんぽの話をしよう。\n朝まで温かいと楽かも。\n注ぎ口の向きを見てね。", facts=[]), state="draft")
            self.make(d, [good, bad, later, draft])
            r = w.dry_run(d, datetime(2026, 11, 7, 13, 0))
            self.assertEqual(r["posted"], ["A-01"])
            self.assertEqual(r["held"], ["A-05"])
            self.assertIn("P02", codes(r["findings"]))

    def test_pause_file_stops_everything(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.make(d, [dict(post(), state="approved")])
            (d / "PAUSE").write_text("", encoding="utf-8")
            r = w.dry_run(d, datetime(2026, 11, 8))
            self.assertTrue(r["paused"])
            self.assertEqual(r["posted"], [])

    def test_a_bad_accounts_file_holds_everything(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.make(d, [dict(post(), state="approved")], accounts={"accounts": [{"id": "A", "token": "x", "token_secret": "THREADS_TOKEN_A", "categories": ["fuyu"], "daily_max": 2, "enabled": True}]})
            r = w.dry_run(d, datetime(2026, 11, 8))
            self.assertEqual(r["posted"], [])
            self.assertTrue(r["account_errors"])

    def test_the_real_publisher_is_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            w.Publisher().publish({"id": "x"})

    def test_cli_does_not_print_draft_text(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "p.json"
            f.write_text(json.dumps([post(body=post()["body"] + "今すぐ")], ensure_ascii=False), encoding="utf-8")
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = w.main(["check-posts", str(f)])
            self.assertEqual(rc, 1)
            self.assertNotIn("今すぐ", buf.getvalue())
            self.assertNotIn("立冬", buf.getvalue())


class TestRepositoryHygiene(unittest.TestCase):
    """The repository is public: no queue, no accounts, no shelf, no token may be tracked, and this module never touches the network."""
    def test_no_private_files_tracked(self):
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True).stdout.decode("utf-8", "replace")
        names = {Path(p).name for p in out.split("\0") if p}
        for n in ("queue.jsonl", "tokens.json", "accounts.json", "shelf.json", "approvals.json", "calendar.json", "product_terms.json", "PAUSE"):
            self.assertNotIn(n, names, n + " must stay in ~/wadai-private/")

    def test_module_has_no_network_import(self):
        src = (ROOT / "sokuhou" / "wadaipost.py").read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import http", "import socket", "import smtplib", "graph.threads.com", "threads_publish"):
            self.assertNotIn(bad, src)
        self.assertFalse(re.search(r"\bTHAA[A-Za-z0-9]{20,}", src))


if __name__ == "__main__":
    unittest.main()
