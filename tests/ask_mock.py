"""A stand-in for api/ask.php (the real one is PHP, which is not installed here): the same operations and the same checks, in Python, in memory, and a static file server
around it, so that the scripts of the pages can be driven end to end in a browser.  It is an executable copy of what sites/yorokobu/ask_receiver.php.tpl is meant to do;
the tests on the PHP source check that the PHP has the same checks.

    python -m tests.ask_mock <folder> <port>      # serves the built site and the fake receiver
"""
from __future__ import annotations

import hashlib
import http.server
import json
import re
import sys
import threading
from functools import partial
from pathlib import Path

ID = re.compile(r"^[A-Za-z0-9_-]{22}$")
OPT = re.compile(r"^[a-z0-9]{1,12}$")
STAT = re.compile(r"^(dock\.[a-z0-9]{1,8}\.[a-z0-9_-]{1,32}|pop\.[ra]\.[A-Za-z0-9._:-]{3,64})$")
ENDPOINT = re.compile(r"^https://([A-Za-z0-9-]+\.)*(googleapis\.com|push\.services\.mozilla\.com|mozaws\.net|push\.apple\.com|notify\.windows\.com)(:\d+)?/")


class Store:
    def __init__(self, allow: dict | None = None):
        self.allow = allow                                                         # {question id: {"max": n, "o": [option ids]}}, as askserver.allowlist makes it
        self.surveys: dict[str, dict] = {}
        self.answers: dict[str, list] = {}
        self.subs: dict[str, dict] = {}
        self.stats: dict[str, int] = {}
        self.calls: list[tuple[str, dict]] = []

    def bump(self, keys):
        for k in keys:
            self.stats[k] = self.stats.get(k, 0) + 1

    def handle(self, d: dict) -> tuple[int, object]:
        if not isinstance(d, dict) or d.get("v") != 1 or not isinstance(d.get("op"), str):
            return 400, None
        op = d["op"]
        self.calls.append((op, d))
        if op == "new":
            i, k = d.get("id", ""), d.get("key", "")
            if not (isinstance(i, str) and ID.match(i) and isinstance(k, str) and ID.match(k)):
                return 400, None
            if i in self.surveys:
                return 409, None
            mode = "s" if d.get("mode") == "s" else "o"
            self.surveys[i] = {"kh": hashlib.sha256(k.encode()).hexdigest(), "m": mode, "n": 0}
            self.answers[i] = []
            self.bump(["ask.new." + mode])
            return 204, None
        if op == "answer":
            i = d.get("id", "")
            meta = self.surveys.get(i) if isinstance(i, str) and ID.match(i) else None
            if meta is None:
                return 404, None
            if meta["n"] >= 40:
                return 429, None
            a = d.get("a")
            if not isinstance(a, dict) or len(a) > 12 or not isinstance(self.allow, dict):
                return 400, None
            clean = {}
            for q, v in a.items():
                if q not in self.allow:
                    return 400, None                                              # an unknown question: the whole answer is refused
                vals = v if isinstance(v, list) else [v]
                c = []
                for x in vals:
                    if not isinstance(x, str) or x not in self.allow[q]["o"]:
                        return 400, None                                          # an unknown option: the same
                    if x not in c:
                        c.append(x)
                if not 1 <= len(c) <= self.allow[q]["max"]:
                    return 400, None
                clean[q] = c
            if not clean:
                return 400, None
            self.answers[i].append({"t": "now", "a": clean})
            meta["n"] += 1
            self.bump(["ask.n.all", "ask.mode." + meta["m"]] + [f"ask.{q}.{o}" for q, os in clean.items() for o in os])
            return 204, None
        if op in ("read", "del", "sub"):
            pass
        if op == "read":
            i, k = d.get("id", ""), d.get("key", "")
            meta = self.surveys.get(i) if isinstance(i, str) and ID.match(i) else None
            if meta is None or not (isinstance(k, str) and ID.match(k) and meta["kh"] == hashlib.sha256(k.encode()).hexdigest()):
                return 403, None
            return 200, {"m": meta["m"], "n": meta["n"], "c": "2026-10-12", "r": self.answers[i][:40]}
        if op == "del":
            i, k = d.get("id", ""), d.get("key", "")
            meta = self.surveys.get(i) if isinstance(i, str) and ID.match(i) else None
            if meta is None or not (isinstance(k, str) and ID.match(k) and meta["kh"] == hashlib.sha256(k.encode()).hexdigest()):
                return 403, None
            self.surveys.pop(i), self.answers.pop(i)
            for sub in self.subs.values():                                        # the survey leaves every subscription
                sub["watch"] = [w for w in sub.get("watch", []) if w["id"] != i]
            self.subs = {ep: sub for ep, sub in self.subs.items() if sub["watch"]}
            return 204, None
        if op == "sub":
            sub = d.get("sub") if isinstance(d.get("sub"), dict) else {}
            ep = sub.get("endpoint", "")
            if not isinstance(ep, str) or not ENDPOINT.match(ep):
                return 400, None
            if d.get("off"):
                self.subs.pop(ep, None)
                return 204, None
            old = {w["id"]: w["sent"] for w in (self.subs.get(ep) or {}).get("watch", [])}
            watch = []
            for x in d.get("watch") or []:
                meta = self.surveys.get(x.get("id"))
                if meta and meta["kh"] == hashlib.sha256(str(x.get("key")).encode()).hexdigest():
                    watch.append({"id": x["id"], "sent": old.get(x["id"], meta["n"])})
            if not watch:                                                         # nothing of the sender's to watch: nothing is kept
                self.subs.pop(ep, None)
                return 204, None
            self.subs[ep] = {"keys": sub.get("keys"), "watch": watch}
            return 204, None
        if op == "stat":
            keys = [k for k in (d.get("k") or []) if isinstance(k, str) and STAT.match(k)][:40]
            if not keys:
                return 400, None
            self.bump(keys)
            return 204, None
        return 400, None


def serve(root: Path, port: int = 0, allow: dict | None = None) -> tuple[http.server.ThreadingHTTPServer, Store]:
    store = Store(allow)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_POST(self):
            if self.path != "/api/ask.php":
                self.send_response(404)
                self.end_headers()
                return
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                d = json.loads(body.decode("utf-8"))
            except ValueError:
                d = None
            code, out = store.handle(d)
            data = json.dumps(out, ensure_ascii=False).encode("utf-8") if out is not None else b""
            self.send_response(code)
            if data:
                self.send_header("Content-Type", "application/json; charset=UTF-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, store


if __name__ == "__main__":
    allow = None
    if len(sys.argv) > 3:
        allow = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    srv, _ = serve(Path(sys.argv[1]), int(sys.argv[2]), allow)
    print("serving", srv.server_address)
    threading.Event().wait()
