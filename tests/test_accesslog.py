import unittest

from sokuhou import accesslog


def line(ip="203.0.113.7", day="16/Oct/2026", method="GET", path="/tottori/", status=200,
         ref="-", ua="Mozilla/5.0 (Windows NT 10.0) Chrome/120"):
    return f'{ip} - - [{day}:10:00:00 +0900] "{method} {path} HTTP/1.1" {status} 512 "{ref}" "{ua}"'


class AccessLogTest(unittest.TestCase):
    def run_lines(self, lines):
        return accesslog.aggregate(lines, "kuma-sokuho.com")

    def test_counts_pages_refs_and_search(self):
        ls = [line(ref="https://www.google.com/")] * 3 + [line(path="/a/", ref="https://t.co/x?q=1")] * 3
        r = self.run_lines(ls)
        self.assertEqual(r["human_views"], 6)
        self.assertEqual(r["search"]["Google"], 3)
        self.assertEqual(r["refs"]["t.co"], 3)

    def test_assets_and_bots_are_not_human_pages(self):
        ls = [line(path="/style.css")] * 4 + [line(ua="Mozilla/5.0 (compatible; GPTBot/1.0)")] * 3
        r = self.run_lines(ls)
        self.assertEqual(r["human_views"], 0)
        self.assertEqual(r["agents"]["OpenAI(GPTBot等)"], 3)

    def test_404_drops_query_and_small_rows(self):
        ls = [line(path="/wp-login.php?x=secret", status=404)] * 3 + [line(path="/rare", status=404)]
        r = self.run_lines(ls)
        out = accesslog.render(r, "kuma-sokuho.com")
        self.assertIn("/wp-login.php 3", out)
        self.assertNotIn("secret", out)
        self.assertNotIn("/rare", out)

    def test_nothing_identifying_is_printed(self):
        ua = "Mozilla/5.0 UniqueAgentString/9.9"
        ls = [line(ip="198.51.100.23", ua=ua, ref="https://example.org/p?token=abc")] * 5
        out = accesslog.render(self.run_lines(ls), "kuma-sokuho.com")
        for secret in ("198.51.100.23", "UniqueAgentString", "token=abc"):
            self.assertNotIn(secret, out)

    def test_unparsable_lines_are_reported_not_hidden(self):
        r = self.run_lines(["garbage line", line()])
        self.assertEqual((r["lines"], r["parsed"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
