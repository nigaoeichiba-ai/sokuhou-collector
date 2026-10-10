"""atomou: shared cards that stay up to date (assets/shared.js, api/s.php).  The browser side is run in Chrome against a small stand-in for the server that keeps the same contract as
api/s.php (what is stored, the edit token as a hash, versions, a conflict answer, peek); the PHP itself is checked by reading it (its limits, what it never stores)."""
import html
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_atomou_core_js import find_chrome  # noqa: E402

ASSETS = ROOT / "sites/atomou/assets"

PAGE = """<!doctype html><meta charset="utf-8"><script>
window.ATOMOU = { v: 'x', groups: ['お金・税金・制度'], slugs: ['deadline'], skins: { basic: { card: 'plain' } }, plans: { on: true, free_cards: 5, free_shared: 2, plus_open: false } };
localStorage.setItem('atomou.v1', '{"v":1,"entries":[],"prefs":{}}');
</script><script src="%(core)s"></script><script src="%(ics)s"></script><pre id="out">pending</pre><script src="%(app)s"></script><script src="%(tier)s"></script><script src="%(shared)s"></script>
<script>
(function () {
  var store = {};            // the stand-in for the server: id -> {eh, ct, ver, upd}
  window.fetch = function (url, opt) {
    var d = JSON.parse(opt.body), res = function (status, data) { return Promise.resolve({ status: status, ok: status < 300, json: function () { return Promise.resolve(data); } }); };
    if (d.a === 'create') { if (store[d.id]) return res(409, { error: 'exists' }); store[d.id] = { eh: d.eh, ct: d.ct, ver: 1, upd: 1000 }; return res(200, { ok: true, ver: 1, upd: 1000 }); }
    if (d.a === 'peek') { var ch = []; d.items.forEach(function (it) { var c = store[it.id]; if (!c) ch.push({ id: it.id, gone: true }); else if (c.ver !== it.ver) ch.push({ id: it.id, ver: c.ver, upd: c.upd }); }); return res(200, { ok: true, changed: ch }); }
    var c = store[d.id];
    if (!c) return res(404, { error: 'none' });
    if (d.a === 'get') return res(200, { ok: true, ver: c.ver, ct: c.ct, upd: c.upd });
    if (d.a === 'report') return res(200, { ok: true });
    return AtomouApp.shared.sha256hex(d.e || '').then(function (h) {
      if (h !== c.eh) return res(403, { error: 'editor' });
      if (d.a === 'delete') { delete store[d.id]; return res(200, { ok: true }); }
      if (d.base !== c.ver) return res(409, { error: 'conflict', ver: c.ver, ct: c.ct, upd: c.upd });
      c.ct = d.ct; c.ver++; c.upd += 60; return res(200, { ok: true, ver: c.ver, upd: c.upd });
    });
  };
  var S = AtomouApp.shared, out = {}, card = { t: '秘密の打ち合わせ', d: '2026-12-01', tm: '10:00', m: '三番会議室', th: 1, tasks: [{ b: 3, x: '資料' }], e: '', k: 'event' };
  function msg(e) { return e && e.message; }
  S.create(card).then(function (x) {
    out.made = { id: x.id.length, k: x.k.length, e: x.e.length, ver: x.ver };
    out.plainNotOnServer = JSON.stringify(store).indexOf('秘密') < 0 && JSON.stringify(store).indexOf(btoa(unescape(encodeURIComponent('秘密'))).slice(0, 6)) < 0;
    out.storedEh = store[x.id].eh.length === 64 && store[x.id].eh !== x.e;                                  // the edit part is stored as a hash only
    return S.read({ id: x.id, k: x.k }).then(function (r) {
      out.readOk = r.card.t === card.t && r.card.m === card.m && r.ver === 1;
      return S.read({ id: x.id, k: S.parseRef('#s=' + x.id + '.' + 'A'.repeat(43)).k }).then(function () { out.wrongKey = 'read'; }, function (e) { out.wrongKey = msg(e); }).then(function () {
        // another device follows the card (view link only)
        S.drop(x.id);
        S.follow({ id: x.id, k: x.k, e: '' }, { card: r.card, ver: r.ver, upd: r.upd });
        out.followed = S.list().length === 1 && S.list()[0].follow === true && !S.list()[0].e;
        // the editor changes it
        var editor = { id: x.id, k: x.k, e: x.e, ver: 1 };
        return S.update(editor, Object.assign({}, card, { t: '場所が変わりました' })).then(function (u) { out.updatedTo = u.ver; return u; }).then(function () {
          return S.update(editor, Object.assign({}, card, { t: '二重更新' })).then(function () { out.stale = 'ok'; }, function (e) { out.stale = msg(e); out.newestVer = e.newest && e.newest.ver; });
        }).then(function () {
          return S.update({ id: x.id, k: x.k, e: 'x'.repeat(32), ver: 2 }, card).then(function () { out.badToken = 'ok'; }, function (e) { out.badToken = msg(e); });
        }).then(function () {
          S.put({ id: x.id, seen: 1, ver: 1 });   // the follower is another device: it has seen version 1 only
          return S.check().then(function (ch) { out.changed = ch.map(function (c) { return c.t; }); out.markedChanged = S.list()[0].changed === true; out.ver = S.list()[0].ver; S.seen(x.id, S.list()[0].ver); return S.check(); });
        }).then(function (again) {
          out.quietAfterSeen = again.length === 0;
          return S.remove({ id: x.id, k: x.k, e: x.e });
        }).then(function (gone) { out.removed = gone; return S.check(); });
      });
    });
  }).then(function (afterRemove) {
    out.goneReported = afterRemove.length === 0;   // the card is no longer followed after the delete (dropped on this device)
    out.refs = { view: !!S.parseRef('#s=' + 'a'.repeat(22) + '.' + 'b'.repeat(43)), edit: S.parseRef('#s=' + 'a'.repeat(22) + '.' + 'b'.repeat(43) + '.' + 'c'.repeat(32) + '&edit=1').e.length, bad: S.parseRef('#s=short.key') };
    // the free plan: two shared cards of one's own, then a stop
    S.put({ id: 'q'.repeat(22), k: 'k'.repeat(43), e: 'e'.repeat(24), mine: true }); S.put({ id: 'r'.repeat(22), k: 'k'.repeat(43), e: 'e'.repeat(24), mine: true });
    out.freeLimit = AtomouApp.tier.sharedBlocked();
    document.getElementById('out').textContent = JSON.stringify(out);
  }).catch(function (e) { document.getElementById('out').textContent = JSON.stringify({ error: String(e && e.stack || e) }); });
})();
</script>"""


@unittest.skipUnless(find_chrome(), "browser checks run locally")
class SharedInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "p.html"
            page.write_text(PAGE % {n: (ASSETS / f"{n}.js").as_uri() for n in ("core", "ics", "app", "tier", "shared")}, encoding="utf-8")
            r = subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox", f"--user-data-dir={Path(td) / 'prof'}", "--virtual-time-budget=8000",
                                "--dump-dom", page.as_uri() + "?today=2026-10-10"], capture_output=True, timeout=120)
        dom = r.stdout.decode("utf-8", "replace")
        a = dom.index('<pre id="out">') + len('<pre id="out">')
        cls.res = json.loads(html.unescape(dom[a:dom.index("</pre>", a)]))

    def test_no_script_error(self):
        self.assertNotIn("error", self.res, self.res)

    def test_a_card_is_locked_in_the_browser_and_the_server_holds_only_the_ciphertext_and_a_hash(self):
        r = self.res
        self.assertEqual(r["made"], {"id": 22, "k": 43, "e": 32, "ver": 1})
        self.assertTrue(r["plainNotOnServer"])
        self.assertTrue(r["storedEh"])

    def test_only_the_right_key_opens_a_card(self):
        self.assertTrue(self.res["readOk"])
        self.assertEqual(self.res["wrongKey"], "key")

    def test_following_updates_conflicts_and_the_edit_token(self):
        r = self.res
        self.assertTrue(r["followed"])
        self.assertEqual(r["updatedTo"], 2)
        self.assertEqual((r["stale"], r["newestVer"]), ("conflict", 2))      # a second change on an old version is refused with the newest
        self.assertEqual(r["badToken"], "editor")
        self.assertEqual(r["changed"], ["場所が変わりました"])                  # the follower finds the change
        self.assertTrue(r["markedChanged"])
        self.assertTrue(r["quietAfterSeen"])                                  # and is told once

    def test_a_deleted_card_and_the_link_forms(self):
        r = self.res
        self.assertTrue(r["removed"])
        self.assertEqual(r["refs"], {"view": True, "edit": 32, "bad": None})

    def test_the_free_plan_makes_two_shared_cards(self):
        self.assertTrue(self.res["freeLimit"])


class ReceiverText(unittest.TestCase):
    """api/s.php is read, not run, here (no PHP on the test machine): the limits and the promises of its comment."""
    php = (ROOT / "sites/atomou/share_receiver.php.tpl").read_text(encoding="utf-8")

    def test_it_generates_with_the_site_address_and_without_placeholders(self):
        from sites.atomou import build
        g = build.share_php()
        self.assertIn("$SITE_URL = 'https://atomou.com';", g)
        self.assertNotIn("__SITE_URL__", g)

    def test_it_stores_ciphertext_a_hash_and_counters_only(self):
        for needle in ("'eh' =>", "'ct' =>", "'ver' =>", "'rep' =>", "'blocked' =>"):
            self.assertIn(needle, self.php)
        self.assertIn("hash_equals((string)$c['eh'], hash('sha256', $e))", self.php)    # the edit token is compared as a hash
        self.assertNotIn("$_SERVER['HTTP_USER_AGENT']", self.php)
        self.assertNotIn("REMOTE_ADDR'] ?? '')) ", self.php)
        self.assertRegex(self.php, r"\$who = substr\(hash\('sha256', \$ip \. '\|' \. date\('Y-m-d'\)")   # a salted daily hash, never the address

    def test_it_has_limits(self):
        self.assertIn("$MAX_CT = 8192;", self.php)
        self.assertIn("$KEEP_DAYS = 180;", self.php)
        self.assertIn("$CREATE_PER_DAY = 20;", self.php)
        self.assertIn("$BLOCK_AT = 3;", self.php)
        self.assertIn("if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST')", self.php)
        self.assertIn("strlen($raw) > 20000", self.php)

    def test_every_action_is_there(self):
        for a in ("'peek'", "'get'", "'create'", "'update'", "'delete'", "'report'"):
            self.assertIn("$a === " + a, self.php)
        self.assertIn("out(409, array('error' => 'conflict'", self.php)
        self.assertIn("flock($fh, LOCK_EX)", self.php)

    def test_braces_balance(self):
        self.assertEqual(self.php.count("{"), self.php.count("}"))
        self.assertEqual(self.php.count("("), self.php.count(")"))

    def test_the_page_has_the_api_and_the_my_page_a_slot_for_the_list(self):
        from sites.atomou import build
        pages = build.build_pages(json.loads((ROOT / "sites/atomou/config.json").read_text(encoding="utf-8")), release=True)
        self.assertIn("api/s.php", pages)
        self.assertIn('id="shared-box"', pages["my/index.html"])


if __name__ == "__main__":
    unittest.main()
