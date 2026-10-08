"""Sends the day's e-mail notices to the members who switched them on (run by .github/workflows/atomou-mail.yml twice a day).

    python -m sites.atomou.mail_send --dir <copy of the members folder, with its key file> --slot m|e [--today YYYY-MM-DD] [--dry-run]

A member's record (api/m.php, sealed at rest) holds "notices": {"on": true, "dates": [{"d": "2026-10-20", "s": "m", "t": "歯医者 15:00"}]}.
One mail per member and slot, listing that day's lines.  Not an advertisement: the mail is the notice the member asked for, carries the
sender's name and how to stop it (the switch on the my page), and never contains links to products.
SMTP from the environment: ATOMOU_SMTP_HOST, ATOMOU_SMTP_PORT (587, STARTTLS), ATOMOU_SMTP_USER, ATOMOU_SMTP_PASS; the sender address
is config.json "member_mail_from".  Output: counts only.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

from sites.atomou import members

HERE = Path(__file__).resolve().parent
NAME = "あと何日、もう何日"


def today_jst() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")


def lines_for(m: dict, today: str, slot: str) -> list[str]:
    n = m.get("notices") or {}
    if not n.get("on"):
        return []
    return [str(x.get("t") or "予定があります") for x in (n.get("dates") or []) if isinstance(x, dict) and x.get("d") == today and x.get("s", "m") == slot][:30]


def compose(to: str, sender: str, site_url: str, operator: str, today: str, slot: str, lines: list[str]) -> EmailMessage:
    y, mo, d = today.split("-")
    when = f"{int(mo)}月{int(d)}日" if slot == "m" else "明日"
    msg = EmailMessage()
    msg["Subject"] = f"【{NAME}】{when}の予定" + (f": {lines[0]}" if len(lines) == 1 else f"({len(lines)}件)")
    msg["From"] = f"{NAME} <{sender}>"
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@", 1)[-1])
    msg["Auto-Submitted"] = "auto-generated"
    body = (f"{when}の予定です。\n\n" + "".join(f"・{t}\n" for t in lines) +
            f"\n開く: {site_url}/my/\n\n"
            f"このメールは、{NAME} のマイページで「メールでもお知らせする」をオンにした方に送っています。"
            f"止めるときは、マイページでオフにしてください。\n{operator}\n{site_url}\n")
    msg.set_content(body)
    return msg


class Smtp:
    """A thin wrapper so the tests can replace it."""

    def __init__(self, host: str, port: int, user: str, password: str):
        self.host, self.port, self.user, self.password = host, port, user, password

    def __enter__(self):
        self.s = smtplib.SMTP(self.host, self.port, timeout=30)
        self.s.starttls()
        self.s.login(self.user, self.password)
        return self

    def __exit__(self, *a):
        try:
            self.s.quit()
        except Exception:  # noqa: BLE001
            pass

    def send(self, msg: EmailMessage) -> None:
        self.s.send_message(msg)


def run(folder: Path, today: str, slot: str, cfg: dict, *, dry_run: bool = False, smtp=None) -> dict:
    key = members.load_key(folder)
    all_members = members.load_members(folder, key)
    due = [(mid, m, lines_for(m, today, slot)) for mid, m in all_members]
    due = [(mid, m, ls) for mid, m, ls in due if ls]
    counts = {"members": len(all_members), "due": len(due), "sent": 0, "failed": 0}
    if dry_run or not due:
        return counts
    sender = cfg["member_mail_from"]
    smtp = smtp or Smtp(os.environ["ATOMOU_SMTP_HOST"], int(os.environ.get("ATOMOU_SMTP_PORT", "587")), os.environ["ATOMOU_SMTP_USER"], os.environ["ATOMOU_SMTP_PASS"])
    with smtp as s:
        for _mid, m, ls in due:
            try:
                s.send(compose(m["email"], sender, cfg["site_url"].rstrip("/"), cfg.get("operator_name") or NAME, today, slot, ls))
                counts["sent"] += 1
            except Exception:  # noqa: BLE001 — one bad address must not stop the others
                counts["failed"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--slot", choices=("m", "e"), required=True)
    ap.add_argument("--today", default=today_jst())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    if not cfg.get("member_mail_from"):
        print(json.dumps({"skipped": "member_mail_from is not set"}))
        return 0
    counts = run(Path(a.dir), a.today, a.slot, cfg, dry_run=a.dry_run)
    print(json.dumps({"today": a.today, "slot": a.slot, **counts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
