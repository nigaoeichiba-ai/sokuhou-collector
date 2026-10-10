"""atomou: the monthly thanks (ranking, awards, the public list) and the encrypted export of the monitors' answers; the receiver's side
of qualified referrals, awards, pen names and the thanks answer; the monitor questionnaire reminder in the notice planner."""
import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build, members, monthly  # noqa: E402
from tests.test_atomou_core_js import ASSETS, find_chrome  # noqa: E402

TODAY = date(2026, 10, 9)
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
ON = {**CFG, "member_mail_from": "noreply@atomou.com"}


def mem(ref, **kw):
    return {"email": f"{ref.lower()}@example.com", "ref_code": ref, "tier": "first", "created": "2026-09-01", **kw}


class Ranking(unittest.TestCase):
    def test_top_three_referrers_by_qualified_referrals_with_ties_and_consented_names_only(self):
        ms = [("a" * 64, mem("AAAAAAAA", ref_log=["2026-10", "2026-10", "2026-10"], pen="さくら", pen_ok=True)),
              ("b" * 64, mem("BBBBBBBB", ref_log=["2026-10", "2026-10"], pen="ひみつ", pen_ok=False)),
              ("c" * 64, mem("CCCCCCCC", ref_log=["2026-10", "2026-10"])),
              ("d" * 64, mem("DDDDDDDD", ref_log=["2026-10"])),
              ("e" * 64, mem("EEEEEEEE", ref_log=["2026-09", "2026-09", "2026-09", "2026-09"]))]   # last month's do not count
        awards, thanks = monthly.rank(ms, "2026-10", [], {}, {})
        refs = thanks["months"][0]["referrers"]
        self.assertEqual([(r["rank"], r["name"], r["n"]) for r in refs], [(1, "さくら", 3), (2, "匿名の方", 2), (2, "匿名の方", 2)])
        self.assertEqual(awards["a" * 64], [{"key": "2026-10:ref", "months": 3, "badge": "referrer_star"}])
        self.assertEqual(awards["b" * 64][0]["months"], 1)
        self.assertNotIn("d" * 64, awards)     # rank 4
        self.assertNotIn("e" * 64, awards)
        self.assertNotIn("example.com", json.dumps(thanks, ensure_ascii=False))   # never an address

    def test_adopted_opinions_give_one_month_and_a_badge_once_a_month(self):
        ms = [("a" * 64, mem("AAAAAAAA", tier="tester", pen="もも", pen_ok=True))]
        adopted = [{"month": "2026-10", "ref": "AAAAAAAA", "note": "カレンダーの文字を大きくしました"},
                   {"month": "2026-10", "ref": "AAAAAAAA", "note": "ガイドを短くしました"},
                   {"month": "2026-09", "ref": "AAAAAAAA", "note": "先月のもの"},
                   {"month": "2026-10", "ref": "ZZZZZZZZ", "note": "いない人"}]
        awards, thanks = monthly.rank(ms, "2026-10", adopted, {}, {})
        self.assertEqual([x["note"] for x in thanks["months"][0]["adopted"]], ["カレンダーの文字を大きくしました", "ガイドを短くしました"])
        self.assertEqual(awards["a" * 64], [{"key": "2026-10:adopted", "months": 1, "badge": "monitor_star"}])

    def test_rerunning_a_month_does_not_double_and_old_months_are_kept_up_to_twelve(self):
        ms = [("a" * 64, mem("AAAAAAAA", ref_log=["2026-10"]))]
        old_thanks = {"months": [{"month": f"2025-{m:02d}", "referrers": [], "adopted": []} for m in range(1, 13)]}
        a1, t1 = monthly.rank(ms, "2026-10", [], {}, old_thanks)
        a2, t2 = monthly.rank(ms, "2026-10", [], a1, t1)
        self.assertEqual(a1, a2)
        self.assertEqual(len(t2["months"]), 12)
        self.assertEqual(t2["months"][0]["month"], "2026-10")
        self.assertEqual(sum(1 for x in t2["months"] if x["month"] == "2026-10"), 1)

    def test_last_month(self):
        self.assertEqual(monthly.last_month(date(2026, 1, 2)), "2025-12")
        self.assertEqual(monthly.last_month(date(2026, 11, 2)), "2026-10")


class Export(unittest.TestCase):
    def test_answers_are_exported_once_as_inbox_records(self):
        ms = [("a" * 64, mem("AAAAAAAA", tier="tester", survey={"1": {"at": "2026-10-08", "freq": "daily", "use": "calendar", "text": "文字が小さい"}})),
              ("b" * 64, mem("BBBBBBBB", tier="tester", survey={"1": {"at": "2026-10-08", "freq": "rarely", "use": "other", "text": ""}}))]
        out, state = monthly.export(ms, {"yorokobu": {"x.jsonl": 3}})
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["site"], "atomou")
        self.assertIn("ほぼ毎日", out[0]["kind"])
        self.assertEqual(out[0]["message"], "文字が小さい")
        self.assertEqual(out[1]["message"], "(自由記述なし)")
        self.assertEqual(state["yorokobu"], {"x.jsonl": 3})        # the contact inbox's state is left alone
        self.assertNotIn("AAAAAAAA", json.dumps(state))           # the state holds hashes only
        out2, _ = monthly.export(ms, state)
        self.assertEqual(out2, [])

    def test_command_line_reads_sealed_records(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td)
            (f / "m").mkdir()
            key = bytes(range(32))
            (f / "key").write_bytes(key)
            (f / "m" / ("a" * 64 + ".json")).write_text(members.seal(mem("AAAAAAAA", ref_log=["2026-10"], pen="さくら", pen_ok=True), key), encoding="utf-8")
            self.assertEqual(monthly.main(["rank", "--dir", td, "--month", "2026-10", "--adopted", str(f / "none.json")]), 0)
            t = json.loads((f / "thanks.json").read_text(encoding="utf-8"))
            self.assertEqual(t["months"][0]["referrers"][0]["name"], "さくら")


class Receiver(unittest.TestCase):
    def setUp(self):
        self.php = build.member_php(ON)

    def test_the_referrer_is_rewarded_only_after_two_days_of_use_a_week_apart(self):
        reg = self.php[self.php.index("if ($a === 'verify')"):self.php.index("if ($a === 'seats')")]
        self.assertNotIn("$REF_GIVE", reg)                                  # nothing at registration any more
        self.assertIn("count($m['seen']) >= 2 && strtotime(max($m['seen'])) - strtotime(min($m['seen'])) >= 7 * 86400", self.php)
        self.assertIn("empty($m['ref_ok'])", self.php)                     # once
        self.assertIn("$rm = extend($rm, $REF_GIVE, $today);", self.php)
        self.assertIn("date('Y-m')", self.php)                              # the month for the ranking

    def test_awards_are_applied_once_by_key_and_capped(self):
        self.assertIn("in_array($key, $done, true)", self.php)
        self.assertIn("min(12, (int)$x['months'])", self.php)
        self.assertIn("preg_match('/^[a-z_]{1,20}$/', $badge)", self.php)

    def test_pen_names_refuse_addresses_links_and_phone_numbers_and_consent_needs_a_name(self):
        self.assertIn("preg_match('/@|https?:|www\\.|\\d{7,}/i', $pen)", self.php)
        self.assertIn("mb_substr(trim(preg_replace(", self.php)
        self.assertIn("$m['pen_ok'] = !empty($d['pen_ok']) && ($m['pen'] ?? '') !== '';", self.php)

    def test_thanks_answer_is_public_and_comes_from_the_monthly_file(self):
        self.assertLess(self.php.index("if ($a === 'thanks')"), self.php.index("$s = session_member($root);"))
        t = self.php[self.php.index("if ($a === 'thanks')"):self.php.index("$s = session_member($root);")]
        self.assertIn("/thanks.json", t)
        for word in ("load_member", "email", "sessions"):
            self.assertNotIn(word, t)


class Pages(unittest.TestCase):
    def test_thanks_page_terms_and_privacy(self):
        pages = build.build_pages(ON, release=True, today=TODAY)
        self.assertIn("thanks/index.html", pages)
        th = pages["thanks/index.html"]
        self.assertIn('id="thanks-list"', th)
        self.assertIn("noindex", th)
        self.assertIn("お金や商品ではありません", th)
        terms = pages["terms/index.html"]
        for want in ("先着モニター", "それぞれ7日以内", "回答するまで、画面の上部に案内を表示します", "1週間以上あけて2回使ったとき", "協力者のページ"):
            self.assertIn(want, terms)
        self.assertNotIn("テスター", terms)
        self.assertIn("直近20日分", pages["privacy/index.html"])
        self.assertIn('"tester":"先着モニター"', pages["index.html"])


PLAN_PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['手続き・お金'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, vapid: 'B', members: { tiers: { tester: '先着モニター' }, ref: 6, give: 1, cap: 12 } };
localStorage.setItem('atomou.v1', '{"v":1,"entries":[]}');
localStorage.setItem('atomou.member', %(member)s);
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(plan)s"></script><script src="%(push)s"></script><script src="%(memberjs)s"></script>
<script>var p = window.AtomouPush.plan([], [2026, 10, 9]); var d = window.AtomouMember.due(JSON.parse(localStorage.getItem('atomou.member')), [2026, 10, 20]);
document.getElementById('out').textContent = JSON.stringify({ dates: p.dates, mirror: p.mirror, due: d && { n: d.n, late: d.late, deadline: d.deadline } });</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class ReminderInChrome(unittest.TestCase):
    def run_page(self, member: dict) -> dict:
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            doc = PLAN_PAGE % {"member": json.dumps(json.dumps(member)), "memberjs": (ASSETS / "member.js").as_uri(), **{n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "plan", "push")}}
            page.write_text(doc, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=4000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-09"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        return json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_monitor_reminder_two_days_before_the_deadline_and_lateness(self):
        r = self.run_page({"tier": "tester", "created": "2026-10-05", "surveys": [], "at": "2026-10-09"})
        self.assertIn({"d": "2026-10-17", "s": "m"}, r["dates"])                  # deadline 10-19, reminder 10-17
        self.assertEqual(r["mirror"]["2026-10-17|m"][0]["t"], "モニターのアンケート(1分)は10月19日までです。")
        self.assertEqual(r["due"], {"n": 1, "late": True, "deadline": [2026, 10, 19]})   # on 10-20 it is late

    def test_no_reminder_for_ordinary_members(self):
        r = self.run_page({"tier": "first", "created": "2026-10-05", "surveys": [], "at": "2026-10-09"})
        self.assertEqual(r["dates"], [])
        self.assertIsNone(r["due"])


if __name__ == "__main__":
    unittest.main()
