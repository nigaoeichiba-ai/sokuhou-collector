"""2026-10-23/24: yorokobu-items #6 died after 30 minutes on `JSONDecodeError: Expecting value: line 1 column 1` (the API answered with nothing, 1,610 calls in), the data went 47 hours old
and the deploy fetched everything at the same time as the retry: 429s for both.  The client asks again when an answer is empty, a failed lookup is a small error that the run survives,
and a deploy that finds the data old waits while the scheduled workflow runs."""
import json
import unittest
import urllib.error
from unittest import mock

from sites.yorokobu import items_fresh, refresh
from sokuhou import rakuten


def client(answers, **kw):
    """A client whose transport gives the answers in turn (bytes, or an exception to raise)."""
    calls = []
    sleeps = []

    def transport(url, headers):
        calls.append(url)
        a = answers[min(len(calls) - 1, len(answers) - 1)]
        if isinstance(a, Exception):
            raise a
        return a
    c = rakuten.Client("APP", "KEY", "https://yorokobu-present.com/", min_interval=0, sleep=sleeps.append, transport=transport, **kw)
    return c, calls, sleeps


GOOD = json.dumps({"Items": [{"itemCode": "s:1"}]}).encode()


class ClientTest(unittest.TestCase):
    def test_an_empty_answer_is_asked_again_and_the_next_good_one_is_used(self):
        c, calls, sleeps = client([b"", GOOD])
        self.assertEqual(c.search(keyword="x"), [{"itemCode": "s:1"}])
        self.assertEqual(len(calls), 2)
        self.assertTrue(sleeps and sleeps[0] >= 5)                       # it waited before asking again

    def test_a_half_written_answer_is_handled_like_an_empty_one(self):
        c, calls, _ = client([b'{"Items": [{"itemCo', GOOD])
        self.assertEqual(len(c.search(keyword="x")), 1)

    def test_answers_that_stay_empty_end_as_a_rakuten_error_not_a_json_error(self):
        c, calls, _ = client([b""])
        with self.assertRaises(rakuten.RakutenError) as cm:
            c.search(keyword="x")
        self.assertIn("empty", str(cm.exception))
        self.assertEqual(len(calls), c.retries)

    def test_the_other_failures_behave_as_before(self):
        c, calls, _ = client([urllib.error.URLError("down"), GOOD])
        self.assertEqual(len(c.search(keyword="x")), 1)
        c2, _, _ = client([urllib.error.HTTPError("u", 404, "nf", {}, None)])
        self.assertEqual(c2.search(keyword="x"), [])


class LookupTest(unittest.TestCase):
    def test_a_lookup_that_gets_nothing_back_is_one_small_error_and_the_run_goes_on(self):
        c, _, sleeps = client([b""])
        state = {"errors": 0}
        self.assertIsNone(refresh.lookup(c, "s:1", state, 1000))
        self.assertEqual(state["errors"], 1)
        self.assertIn(refresh.COOL_DOWN, sleeps)                          # it gave the API a moment

    def test_too_many_failures_still_stop_the_run(self):
        c, _, _ = client([b""])
        state = {"errors": 0}
        with self.assertRaises(rakuten.RakutenError):
            for _ in range(10):
                refresh.lookup(c, "s:1", state, 20)


class WaitTest(unittest.TestCase):
    def test_nothing_to_wait_for_without_a_repository_or_a_running_workflow(self):
        self.assertEqual(items_fresh.wait_for_items_run(None, running=lambda r, t: True), "")
        self.assertEqual(items_fresh.wait_for_items_run("o/r", running=lambda r, t: False), "")

    def test_it_waits_while_the_workflow_runs_and_says_how_long(self):
        state = {"n": 0, "t": 0.0}

        def running(repo, token):
            state["n"] += 1
            return state["n"] < 4                                          # running at the first look and for two polls

        def sleep(s):
            state["t"] += s
        out = items_fresh.wait_for_items_run("o/r", running=running, sleep=sleep, clock=lambda: state["t"], poll=60)
        self.assertIn("waited 3 minutes", out)

    def test_it_gives_up_after_the_limit(self):
        state = {"t": 0.0}
        out = items_fresh.wait_for_items_run("o/r", running=lambda r, t: True, sleep=lambda s: state.__setitem__("t", state["t"] + s), clock=lambda: state["t"], max_minutes=10, poll=60)
        self.assertIn("still running after 10 minutes", out)
        self.assertGreaterEqual(state["t"], 600)

    def test_no_answer_from_github_does_not_make_the_deploy_wait(self):
        def boom(repo, token):
            raise urllib.error.URLError("no network")
        out = items_fresh.wait_for_items_run("o/r", running=boom, sleep=lambda s: self.fail("must not sleep"))
        self.assertIn("could not ask", out)

    def test_the_running_check_reads_the_status_of_the_latest_runs(self):
        class R:
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, *a): return json.dumps(self.body).encode()
        with mock.patch.object(items_fresh.urllib.request, "urlopen", lambda req, timeout=0: R({"workflow_runs": [{"status": "completed"}, {"status": "in_progress"}]})):
            self.assertTrue(items_fresh.running_items_run("o/r"))
        with mock.patch.object(items_fresh.urllib.request, "urlopen", lambda req, timeout=0: R({"workflow_runs": [{"status": "completed"}]})):
            self.assertFalse(items_fresh.running_items_run("o/r"))
        with mock.patch.object(items_fresh.urllib.request, "urlopen", lambda req, timeout=0: R({"workflow_runs": []})):
            self.assertFalse(items_fresh.running_items_run("o/r"))


if __name__ == "__main__":
    unittest.main()
