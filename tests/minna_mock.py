"""A stand-in for api/q.php (the real one is PHP, which is not installed here): the same checks in Python, and a static file server around it, so that the request box and the
"nothing found" offer of the pages can be driven end to end in a browser.  The lines it would keep are collected in memory and printed; nothing is written to disk.

    python -m tests.minna_mock <folder> <port>      # serves the built site and the fake receiver
"""
from __future__ import annotations

import http.server
import json
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sites.minna import wishes  # noqa: E402
from sites.minna.build import TOUCHES  # noqa: E402

KEPT: list[dict] = []
COUNT: dict[str, int] = {}


def handle(d: object, who: str = "local") -> tuple[int, dict]:
    """The decisions of api/q.php, in the same order."""
    rules = wishes.load_rules()
    if not isinstance(d, dict) or d.get("v") != 1 or not isinstance(d.get("w"), str):
        return 400, {"error": "request"}
    w = wishes.clean(d["w"])
    use = d.get("u") if d.get("u") in wishes.USES else ""
    touch = d.get("t") if d.get("t") in [t[0] for t in TOUCHES] else ""
    src = d.get("s") if d.get("s") in ("form", "miss", "plus") else "form"
    why, _ = wishes.refusal(w, rules)
    if why == "length":
        return 422, {"error": "length"}
    if why and why != "test":
        return 422, {"error": why}
    if COUNT.get(who, 0) >= rules["per_day"]:
        return 429, {"error": "rate"}
    COUNT[who] = COUNT.get(who, 0) + 1
    KEPT.append({"message": w, "page": f"q:u={use};t={touch};s={'test' if why == 'test' else src}"})
    return 200, {"ok": True}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?")[0] != "/api/q.php":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            d = json.loads(self.rfile.read(min(n, 1001)).decode("utf-8"))
        except ValueError:
            d = None
        code, body = handle(d)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        print("kept so far:", json.dumps(KEPT, ensure_ascii=False), flush=True)

    def log_message(self, *a):
        pass


def main() -> None:
    folder, port = sys.argv[1], int(sys.argv[2])
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=folder))
    print(f"serving {folder} on http://127.0.0.1:{port}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
