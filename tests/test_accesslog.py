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


class XserverSampleTest(unittest.TestCase):
    """Apache 'combined' lines as the server writes them: IPv6 client, '-' size, percent-encoded Japanese path."""

    SAMPLE = [
        '2001:db8::1 - - [17/Oct/2026:06:01:02 +0900] "GET /%E5%AE%AE%E5%9F%8E/ HTTP/2.0" 200 - "https://www.google.com/" "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1"',
        '198.51.100.9 - - [17/Oct/2026:06:01:03 +0900] "GET /ranking/ HTTP/1.1" 304 0 "https://search.yahoo.co.jp/" "Mozilla/5.0 Firefox/130.0"',
        '198.51.100.10 - - [17/Oct/2026:06:01:04 +0900] "GET /robots.txt HTTP/1.1" 200 120 "-" "Mozilla/5.0 (compatible; Googlebot/2.1)"',
        '198.51.100.11 - - [17/Oct/2026:06:01:05 +0900] "-" 408 - "-" "-"',
    ]

    def test_sample_is_read_and_reported(self):
        r = accesslog.aggregate(self.SAMPLE * 3, "kuma-sokuho.com")
        self.assertEqual(r["parsed"], 9)  # the 408 line without a request is reported as unparsed, not hidden
        self.assertEqual(r["lines"], 12)
        self.assertEqual(r["human_views"], 6)
        self.assertEqual((r["first"], r["last"]), ("2026-10-17", "2026-10-17"))
        out = accesslog.render(r, "kuma-sokuho.com")
        self.assertIn("Google 3", out)
        self.assertIn("Yahoo! 3", out)
        self.assertNotIn("2001:db8", out)


if __name__ == "__main__":
    unittest.main()


class AiReferralTest(unittest.TestCase):
    """L9: visits that came from an AI assistant, by referrer host (and utm_source), per ISO week; nothing that identifies anyone."""

    def run_lines(self, lines):
        return accesslog.aggregate(lines, "x.example")

    def test_known_assistants_are_counted_by_week_and_name(self):
        ls = ([line(ref="https://chatgpt.com/", day="05/Nov/2026")] * 3 + [line(ref="https://www.perplexity.ai/search", day="05/Nov/2026")] * 2
              + [line(ref="https://claude.ai/", day="12/Nov/2026")] * 4 + [line(ref="https://gemini.google.com/app", day="12/Nov/2026")])
        r = self.run_lines(ls)
        self.assertEqual(r["ai"][("2026-W45", "ChatGPT")], 3)
        self.assertEqual(r["ai"][("2026-W45", "Perplexity")], 2)
        self.assertEqual(r["ai"][("2026-W46", "Claude")], 4)
        self.assertEqual(r["ai"][("2026-W46", "Gemini")], 1)
        out = accesslog.render(r, "x.example")
        self.assertIn("2026-W45: 5", out)
        self.assertIn("測れなかった分があります", out)

    def test_utm_source_of_chatgpt_counts_without_a_referrer(self):
        r = self.run_lines([line(path="/a/?utm_source=chatgpt.com", ref="-")] * 3)
        self.assertEqual(sum(r["ai"].values()), 3)

    def test_duckduckgo_is_kept_apart_and_a_plain_search_is_not_ai(self):
        r = self.run_lines([line(ref="https://duckduckgo.com/")] * 3 + [line(ref="https://www.google.com/")] * 3 + [line(ref="https://notchatgpt.com.evil.example/")] * 3)
        self.assertEqual(sum(r["ai"].values()), 0)
        self.assertEqual(sum(r["ai_maybe"].values()), 3)
        out = accesslog.render(r, "x.example")
        self.assertIn("区別できない", out)

    def test_bots_are_not_ai_visits_and_nothing_identifying_is_printed(self):
        r = self.run_lines([line(ref="https://chatgpt.com/", ua="Mozilla/5.0 (compatible; GPTBot/1.0)")] * 3 + [line(ip="198.51.100.88", ref="https://chatgpt.com/c/secret-id")] * 3)
        self.assertEqual(sum(r["ai"].values()), 3)
        out = accesslog.render(r, "x.example")
        for secret in ("198.51.100.88", "secret-id"):
            self.assertNotIn(secret, out)

    def test_no_data_is_not_zero(self):
        self.assertIn("測れなかった", accesslog.render_ai(self.run_lines(["garbage"])))
