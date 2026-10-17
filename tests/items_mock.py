"""A static test server that also answers GET /api/items.php like the real one (sites/yorokobu/items_receiver.php.tpl; the logic is itemsserver.answer, the Python twin).
The data is what the build just left in build.PRIVATE (the three private files)."""
import functools
import http.server
import json
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sites.yorokobu import build, itemsserver


def private_from_build() -> dict:
    return {k: json.loads(build.PRIVATE[name]) for k, name in itemsserver.PRIVATE_FILES.items() if name in build.PRIVATE}


def serve(root: Path, private: dict | None = None, port: int = 0) -> http.server.ThreadingHTTPServer:
    db = private if private is not None else private_from_build()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            u = urlsplit(self.path)
            if u.path != "/api/items.php":
                return super().do_GET()
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            code, out = itemsserver.answer(q, {k: db.get(k, {}) for k in itemsserver.PRIVATE_FILES})
            data = json.dumps(out, ensure_ascii=False).encode("utf-8") if out is not None else b""
            self.send_response(code)
            if data:
                self.send_header("Content-Type", "application/json; charset=UTF-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
