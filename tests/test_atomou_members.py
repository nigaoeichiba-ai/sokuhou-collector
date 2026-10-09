"""atomou: the member foundation (one-time code by e-mail, first-come tiers, referral codes, e-mail notices) — the generated receiver,
the pages it switches on, and the browser side's referral memory.  PHP is not run here (it is not installed); the template is checked for
the properties that matter (what is stored, how, and what never is)."""
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sites.atomou import build  # noqa: E402
from sokuhou.sitekit import BuildError  # noqa: E402

TODAY = date(2026, 10, 8)
CFG = json.loads((ROOT / "sites" / "atomou" / "config.json").read_text(encoding="utf-8"))
ON = {**CFG, "member_mail_from": "noreply@atomou.com", "member_tiers": [{"id": "tester", "label": "先着テスター", "size": 30, "months": 18, "tester": True}, {"id": "first", "label": "先着", "size": 270, "months": 12}], "member_ref_months": 6, "member_ref_give_months": 1, "member_ref_cap": 6}


class Receiver(unittest.TestCase):
    def setUp(self):
        self.php = build.member_php(ON)

    def test_config_values_are_filled_in(self):
        self.assertIn('$TIERS = [{"id": "tester", "size": 30, "months": 18, "tester": true}, {"id": "first", "size": 270, "months": 12, "tester": false}];', self.php)
        self.assertIn("$REF_MONTHS = 6;", self.php)
        self.assertIn("$REF_CAP = 6;", self.php)
        self.assertIn("$MAIL_FROM = 'noreply@atomou.com';", self.php)
        self.assertIn("$SITE_URL = 'https://atomou.com';", self.php)
        for ph in ("__TIERS__", "__REF_MONTHS__", "__REF_CAP__", "__MAIL_FROM__", "__SITE_NAME__", "__SITE_URL__"):
            self.assertNotIn(ph, self.php)

    def test_stored_outside_the_web_root_and_encrypted(self):
        self.assertIn("dirname(__DIR__, 2)", self.php)
        self.assertIn("'/members'", self.php)
        self.assertIn("openssl_encrypt(", self.php)
        self.assertIn("'aes-256-gcm'", self.php)
        self.assertIn("random_bytes(32)", self.php)        # the key file
        self.assertIn("@chmod($f, 0600)", self.php)
        self.assertIn("seal($root, $m)", self.php)          # members are written sealed
        self.assertNotIn("file_put_contents($f, json_encode($m)", self.php)   # never in the clear

    def test_codes_are_hashed_short_lived_and_limited(self):
        self.assertIn("password_hash($code, PASSWORD_DEFAULT)", self.php)
        self.assertIn("'exp' => time() + 600", self.php)
        self.assertIn("count($sent) >= 3", self.php)        # three codes an hour per address
        self.assertIn("($p['tries'] ?? 0) >= 5", self.php)   # five guesses
        self.assertIn("random_int(0, 999999)", self.php)
        self.assertIn("out(204, array())", self.php)        # the 'code' action never reveals whether an address is known

    def test_sessions_are_hashes_in_an_httponly_cookie_limited_to_the_api_path(self):
        self.assertIn("hash('sha256', $secret)", self.php)
        self.assertIn("'httponly' => true", self.php)
        self.assertIn("'samesite' => 'Lax'", self.php)
        self.assertIn("'path' => '/api/'", self.php)
        self.assertIn("$origin !== $SITE_URL", self.php)     # CSRF: the site's own pages only

    def test_first_come_tiers_and_single_level_referral(self):
        self.assertIn("flock($fh, LOCK_EX)", self.php)       # the counter is updated under a lock
        # the two pools are offered at the same time and count on their own; a full tester pool falls back to the ordinary one, never the other way
        self.assertIn("if ($t['id'] === $want) { array_unshift($order, $t); } elseif (empty($t['tester'])) { $order[] = $t; }", self.php)
        self.assertIn("$c['by'][$t['id']] = $used + 1;", self.php)
        self.assertIn("in_array((string)($d['want'] ?? ''), $IDS, true)", self.php)
        self.assertIn("$tier = 'referred'; $months = $REF_MONTHS;", self.php)
        self.assertIn("(int)($rm['referrals'] ?? 0) < $REF_CAP", self.php)
        self.assertIn("$found[0] !== $id", self.php)         # no self-referral
        self.assertNotIn("ref_by'] !== '' && load_member($root, $m['ref_by'])", self.php)   # no second level

    def test_public_view_never_contains_sessions_and_notices_carry_short_titles_only_when_on(self):
        m = re.search(r"function public_view\(\$m\) \{.*?\n\}", self.php, re.S).group(0)
        self.assertNotIn("$m['sessions']", m)
        self.assertIn("'dates' => $on ? $dates : array()", self.php)
        self.assertIn("mb_substr((string)($x['t'] ?? ''), 0, 60)", self.php)

    def test_referrer_reward_is_separate_and_small(self):
        # 2026-10-09: the referrer used to get the referred person's 6 months per referral (up to 3 years); now its own, smaller number
        self.assertIn("$REF_GIVE = 1;", self.php)
        self.assertIn("$rm = extend($rm, $REF_GIVE, $today);", self.php)
        self.assertNotIn("months_later($base, $REF_MONTHS)", self.php)

    def test_seats_answer_is_public_and_carries_no_personal_data(self):
        seats = self.php[self.php.index("if ($a === 'seats')"):self.php.index("$s = session_member($root);")]
        self.assertLess(self.php.index("if ($a === 'seats')"), self.php.index("$s = session_member($root);"))   # before the login check
        self.assertIn("'left' => max(0, (int)$t['size'] - (int)($by[$t['id']] ?? 0))", seats)
        for word in ("email", "load_member", "sessions"):
            self.assertNotIn(word, seats)

    def test_only_testers_answer_the_questionnaire_with_fixed_choices(self):
        q = self.php[self.php.index("if ($a === 'survey')"):self.php.index("if ($a === 'logout')")]
        self.assertIn("($m['tier'] ?? '') !== 'tester'", q)
        self.assertIn("array('daily', 'weekly', 'rarely')", q)
        self.assertIn("mb_substr(trim((string)($ans['text'] ?? '')), 0, 300)", q)
        self.assertIn("seal($root, $m)", self.php)          # stored with the sealed member record, never in the clear

    def test_delete_removes_the_record(self):
        self.assertIn("@unlink($root . '/m/' . $id . '.json');", self.php)

    def test_bad_tier_config_is_refused(self):
        with self.assertRaises(BuildError):
            build.member_php({**ON, "member_tiers": [{"id": "bad id!", "size": 1, "months": 1}]})


class Pages(unittest.TestCase):
    def test_switched_on_by_the_sender_address(self):
        on = build.build_pages(ON, release=True, today=TODAY)
        self.assertIn("api/m.php", on)
        self.assertIn("terms/index.html", on)
        self.assertIn('id="member-box"', on["my/index.html"])
        self.assertIn('id="members"', on["privacy/index.html"])
        self.assertIn('"members":{"tiers":{"tester":"先着テスター","first":"先着"},"ref":6,"give":1,"cap":6}', on["index.html"])
        self.assertIn("member.js", build.BUNDLE[-1] + ".js")
        off = build.build_pages({**CFG, "member_mail_from": None}, release=True, today=TODAY)
        self.assertNotIn("api/m.php", off)
        self.assertNotIn("terms/index.html", off)
        self.assertNotIn('id="member-box"', off["my/index.html"])
        self.assertNotIn('"members"', off["index.html"])

    def test_terms_cover_the_decisions_the_owner_made(self):
        terms = build.build_pages(ON, release=True, today=TODAY)["terms/index.html"]
        for want in ("パスワードはありません", "同時に募集します", "先着テスター", "1か月後に", "回答しなかったときも、無料期間は取り消しません", "自動で料金がかかることはありません", "期間の延長だけで、お金や商品はありません", "自分で自分を紹介", "退会する", "責任を負いません"):
            self.assertIn(want, terms)
        self.assertNotIn("おめでとう", terms)

    def test_the_client_remembers_a_referral_link_and_sends_only_known_fields(self):
        js = (ROOT / "sites" / "atomou" / "assets" / "member.js").read_text(encoding="utf-8")
        self.assertIn("/[?&]ref=([A-Z2-9]{8})\\b/", js)
        self.assertIn("credentials: 'same-origin'", js)
        self.assertIn("autocomplete=\"one-time-code\"", js)
        self.assertIn("a: 'update', notices: { on: on, dates: dates }", js)
        self.assertNotIn('type="password"', js)


if __name__ == "__main__":
    unittest.main()
