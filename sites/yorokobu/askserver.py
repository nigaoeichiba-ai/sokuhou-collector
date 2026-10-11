"""The server side of the 「それとなく聞く」アンケート and of the 診断ドック counters: api/ask.php, made from ask_receiver.php.tpl."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def allowlist(ask: dict) -> dict:
    """{question id: {"max": most options at once, "o": [option ids]}}: what the receiver accepts as an answer."""
    return {q["id"]: {"max": int(q.get("max") or 1) if q.get("multi") else 1, "o": [o["id"] for o in q["options"]]} for q in ask["questions"]}


def ask_php(cfg: dict, ask: dict) -> str:
    """The receiver, with this site's address and its questions in it (it answers only requests that come from the pages of this site, and takes only the options the questions have)."""
    url = cfg["site_url"].rstrip("/")
    spec = json.dumps(allowlist(ask), separators=(",", ":"))
    if "'" in spec or "\\" in spec:
        raise ValueError("a question or option id with a quote or a backslash")
    return (HERE / "ask_receiver.php.tpl").read_text(encoding="utf-8").replace("__SITE_URL__", url).replace("__ASK__", spec)
