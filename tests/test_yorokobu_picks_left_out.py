"""2026-10-26: /picks/2026-10-24/ and 2026-10-25/ showed 19 products (r7 missing) and nothing said why.  The page source now says which pick was left out and for which reason
(not-found: the API did not return the item; unavailable: it reports it as not for sale), so it can be read without the build log."""
import tempfile
import unittest
from pathlib import Path

from tests.test_yorokobu_picks import day, live_items, render


class LeftOutTest(unittest.TestCase):
    d = day()

    def html(self, items):
        with tempfile.TemporaryDirectory() as tmp:
            out = render(Path(tmp), [self.d], items)
            return (out / "picks/2026-10-11/index.html").read_text(encoding="utf-8")

    def test_an_unavailable_pick_is_named_with_its_reason(self):
        code = self.d["rakuten"][6]["code"]
        h = self.html(live_items(self.d, sold_out=(code,)))
        self.assertIn("<!-- left out of this page: r7=unavailable", h)

    def test_a_pick_the_api_did_not_return_is_named_as_not_found(self):
        items = live_items(self.d)
        del items[self.d["rakuten"][6]["code"]]
        h = self.html(items)
        self.assertIn("<!-- left out of this page: r7=not-found", h)

    def test_a_complete_day_has_no_such_comment(self):
        self.assertNotIn("left out of this page", self.html(live_items(self.d)))

    def test_the_comment_holds_no_product_data(self):
        items = live_items(self.d)
        del items[self.d["rakuten"][6]["code"]]
        h = self.html(items)
        line = next(l for l in h.splitlines() if "left out of this page" in l)
        self.assertNotIn(self.d["rakuten"][6]["code"], line)


if __name__ == "__main__":
    unittest.main()
