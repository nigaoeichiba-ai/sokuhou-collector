"""The live check (`sitecheck --live`, run right after every deploy; a failure rolls the site back) against a local web server.

2026-10-18: it was made fast (kept-alive connections, 16 workers, HEAD for images and other files) because minna's check took 859 to 1293 seconds.  A faster
check that sees less would be a lie, so every defect the slow version found is built here and must still be named: a missing page, a broken link to a page
or to an image, a page on another host, a page that breaks the page rules, a server that answers only some requests, and the ways a real server misbehaves
(refuses HEAD, closes the connection, redirects, fails once).
"""
import http.server
import threading
import time
import unittest
from unittest import mock

from sokuhou import sitecheck


class Server:
    """A tiny site.  `routes` maps a path to (status, body); `head_status` overrides what HEAD answers for a path; `close_after` closes a connection after that many requests."""

    def __init__(self, routes, head_status=None, close_after=0, flaky=None, redirects=None):
        self.routes, self.head_status, self.close_after = routes, head_status or {}, close_after
        self.flaky = dict(flaky or {})          # path -> number of 500 answers before the real one
        self.redirects = redirects or {}        # path -> location
        self.connections = 0
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                outer.connections += 1
                self.served = 0

            def log_message(self, *a):
                pass

            def handle_one(self, head):
                path = self.path
                outer.requests.append((self.command, path))
                self.served += 1
                if path in outer.redirects:
                    self.send_response(301)
                    self.send_header("Location", outer.redirects[path])
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if outer.flaky.get(path, 0) > 0:
                    outer.flaky[path] -= 1
                    status, body = 500, b"oops"
                elif head and path in outer.head_status:
                    status, body = outer.head_status[path], b""
                else:
                    status, body = outer.routes.get(path, (404, b"not found"))
                if isinstance(body, str):
                    body = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                if outer.close_after and self.served >= outer.close_after:
                    self.send_header("Connection", "close")
                    self.close_connection = True
                self.end_headers()
                if not head:
                    self.wfile.write(body)

            def do_GET(self):
                self.handle_one(False)

            def do_HEAD(self):
                self.handle_one(True)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def page(base, path, body="<p>text</p>"):
    return (f'<!doctype html><html><head><title>t</title><meta name="description" content="d"><link rel="canonical" href="{base}{path}"></head>'
            f'<body><main><h1>H</h1>{body}</main></body></html>')


def site(extra_links="", pages=3, **server_kw):
    """A clean site of `pages` pages (/ and /p1/ ...) with a sitemap, an image and a stylesheet; returns the running server."""
    holder = {}
    routes = {}
    srv = Server(routes, **server_kw)
    base = srv.base
    paths = ["/"] + [f"/p{i}/" for i in range(1, pages)]
    for i, p in enumerate(paths):
        nxt = paths[(i + 1) % len(paths)]
        routes[p] = (200, page(base, p, f'<a href="{nxt}">next</a><img src="/img/a.png" alt=""><link rel="stylesheet" href="/s.css">' + extra_links))
    routes["/sitemap.xml"] = (200, '<?xml version="1.0"?><urlset>' + "".join(f"<url><loc>{base}{p}</loc></url>" for p in paths) + "</urlset>")
    routes["/img/a.png"] = (200, b"\x89PNG")
    routes["/s.css"] = (200, b"body{}")
    holder["srv"] = srv
    return srv


class LiveCheckTest(unittest.TestCase):
    def run_check(self, srv, **kw):
        self.addCleanup(srv.stop)
        with mock.patch("time.sleep"):
            return sitecheck.check_live(srv.base, **kw)

    def test_a_clean_site_passes_and_the_connections_are_reused(self):
        srv = site(pages=40)
        problems, n = self.run_check(srv, workers=4)
        self.assertEqual(problems, [])
        self.assertEqual(n, 40)
        self.assertGreater(len(srv.requests), 40)
        self.assertLess(srv.connections, 20, f"{srv.connections} connections for {len(srv.requests)} requests: each worker should keep its connection")

    def test_the_images_and_stylesheets_are_checked_with_head_and_the_pages_with_get(self):
        srv = site()
        self.run_check(srv)
        self.assertIn(("HEAD", "/img/a.png"), srv.requests)
        self.assertIn(("HEAD", "/s.css"), srv.requests)
        self.assertNotIn(("GET", "/img/a.png"), srv.requests)
        self.assertIn(("GET", "/p1/"), srv.requests)

    def test_a_sitemap_page_that_answers_404_is_reported(self):
        srv = site()
        del srv.routes["/p1/"]
        problems, _ = self.run_check(srv)
        self.assertTrue(any("[sitemap]" in p and "/p1/" in p and "404" in p for p in problems), problems)

    def test_a_broken_link_to_a_page_is_reported(self):
        srv = site('<a href="/month/10/">October</a>')
        problems, _ = self.run_check(srv)
        self.assertTrue(any("[links]" in p and "/month/10/" in p for p in problems), problems)

    def test_a_broken_image_is_reported_even_though_it_is_asked_with_head(self):
        srv = site('<img src="/img/gone.png" alt="">')
        problems, _ = self.run_check(srv)
        self.assertTrue(any("[links]" in p and "/img/gone.png" in p and "404" in p for p in problems), problems)

    def test_a_server_that_refuses_head_is_asked_again_with_get(self):
        srv = site(head_status={"/img/a.png": 405, "/s.css": 405})
        problems, _ = self.run_check(srv)
        self.assertEqual(problems, [])
        self.assertIn(("GET", "/img/a.png"), srv.requests)

    def test_a_file_that_is_missing_stays_missing_when_head_is_refused_too(self):
        srv = site('<img src="/img/gone.png" alt="">', head_status={"/img/gone.png": 405})
        problems, _ = self.run_check(srv)
        self.assertTrue(any("/img/gone.png" in p for p in problems), problems)

    def test_a_server_that_closes_every_connection_is_still_checked(self):
        srv = site(pages=12, close_after=1)
        problems, n = self.run_check(srv, workers=3)
        self.assertEqual((problems, n), ([], 12))

    def test_a_connection_dropped_between_requests_is_opened_again(self):
        srv = site(pages=30)
        orig = srv.httpd.RequestHandlerClass

        class Dropper(orig):
            def handle_one(self, head):
                super().handle_one(head)
                if self.served >= 3:           # closes without announcing it (no Connection: close header)
                    self.close_connection = True

        srv.httpd.RequestHandlerClass = Dropper
        problems, n = self.run_check(srv, workers=2)
        self.assertEqual((problems, n), ([], 30))

    def test_a_redirect_to_the_page_with_a_slash_is_followed_like_before(self):
        srv = site('<a href="/about">about</a>', redirects={"/about": "/about/"})
        srv.routes["/about/"] = (200, page(srv.base, "/about/"))
        problems, _ = self.run_check(srv)
        self.assertEqual(problems, [])

    def test_one_failed_answer_is_retried_but_a_page_that_keeps_failing_is_reported(self):
        srv = site(flaky={"/p1/": 1})
        problems, _ = self.run_check(srv)
        self.assertEqual(problems, [])
        srv2 = site(flaky={"/p1/": 99})
        problems, _ = self.run_check(srv2)
        self.assertTrue(any("/p1/" in p and "500" in p for p in problems), problems)

    def test_a_page_that_breaks_the_page_rules_is_reported_from_the_live_copy(self):
        srv = site()
        srv.routes["/p1/"] = (200, "<!doctype html><html><head><title>t</title></head><body><main><h1>H</h1><h1>again</h1></main></body></html>")
        problems, _ = self.run_check(srv)
        self.assertTrue(any("p1" in p for p in problems), problems)

    def test_a_sitemap_url_on_another_host_is_reported(self):
        srv = site()
        srv.routes["/sitemap.xml"] = (200, srv.routes["/sitemap.xml"][1].replace("</urlset>", "<url><loc>http://other.test/x/</loc></url></urlset>"))
        real = sitecheck._fetch
        with mock.patch.object(sitecheck, "_fetch", lambda url, timeout=30, method="GET": (200, b"") if "other.test" in url else real(url, timeout, method)):
            problems, _ = self.run_check(srv)
        self.assertTrue(any("another host" in p for p in problems), problems)

    def test_a_missing_sitemap_and_a_missing_probe_are_reported(self):
        srv = site()
        problems, _ = self.run_check(srv, probes=("/feed.xml",))
        self.assertTrue(any("[probe]" in p and "/feed.xml" in p for p in problems), problems)
        srv2 = site()
        del srv2.routes["/sitemap.xml"]
        problems, n = self.run_check(srv2)
        self.assertEqual(n, 0)
        self.assertTrue(any("sitemap.xml answered 404" in p for p in problems), problems)

    def test_the_light_check_still_fetches_only_what_it_selects(self):
        srv = site(pages=30)
        problems, n = self.run_check(srv, sample=5)
        self.assertEqual(problems, [])
        self.assertEqual(n, 6)    # the home page and 5 others

    def test_an_unreachable_server_is_reported_not_raised(self):
        with mock.patch("time.sleep"), mock.patch.object(sitecheck, "_once", side_effect=ConnectionRefusedError("refused")):
            problems, n = sitecheck.check_live("http://127.0.0.1:9")
        self.assertEqual(n, 0)
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
