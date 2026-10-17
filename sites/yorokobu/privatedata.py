"""The private store of the data the mall APIs give (Rakuten, Yahoo!): a folder on the site's server that is not in public_html, never the repository.

The terms of the Rakuten Web Service bar keeping what the API gives "in a place where information can be shared with an unspecified or a large number of people" (Article 10 (1) (9)),
and the help page lets prices and availability be kept for 24 hours and the rest for three months.  So the daily workflows (yorokobu-compare, -yahoo, -ranking, -candidates) do not commit
their result to the public repository: they write it here, and the deploy takes the files from here before it builds.

    python -m sites.yorokobu.privatedata pull [name ...]     server -> data/<name>     (a file the server does not have yet is skipped, with a note)
    python -m sites.yorokobu.privatedata push [name ...]     data/<name> -> server

`name` is one of FILES (default: all).  The connection is the deploy's: the repository secrets XSERVER_SSH_KEY, XSERVER_HOST, XSERVER_USER (port 10022, as in deploy.yml); without them
nothing happens (a fork, a local run).  The data/ files are git-ignored: they exist only in a run that pulled them, and the build runs without them (the pages that need them are left out).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REMOTE_DIR = "yorokobu-private"                    # in the SSH user's home, beside public_html: nothing in it is served
FILES = ("yorokobu_compare.json", "yorokobu_yahoo.json", "yorokobu_ranking.json", "yorokobu_candidates.json")
PORT = os.environ.get("SSH_PORT", "10022")


def _conn():
    key, host, user = (os.environ.get(k, "") for k in ("XSERVER_SSH_KEY", "XSERVER_HOST", "XSERVER_USER"))
    if not (key and host and user):
        return None
    return key, host, user


def _ssh_base(keyfile: str, known: str, host: str, user: str) -> list[str]:
    return ["ssh", "-i", keyfile, "-p", PORT, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={known}",
            "-o", "ConnectTimeout=20", f"{user}@{host}"]


def run(action: str, names: list[str]) -> int:
    c = _conn()
    if not c:
        print("privatedata: the server secrets are not set; nothing to do")
        return 0
    key, host, user = c
    names = names or list(FILES)
    bad = [n for n in names if n not in FILES]
    if bad:
        print(f"privatedata: unknown file {bad}; one of {FILES}")
        return 2
    DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        kf, kh = Path(td) / "key", Path(td) / "known_hosts"
        kf.write_text(key.strip() + "\n", encoding="utf-8")
        kf.chmod(0o600)
        ssh = _ssh_base(str(kf), str(kh), host, user)
        failed = 0
        if action == "push":
            subprocess.run(ssh + [f"mkdir -p ~/{REMOTE_DIR} && chmod 700 ~/{REMOTE_DIR}"], check=False)
        for n in names:
            local = DATA / n
            for attempt in range(3):
                if action == "push":
                    if not local.exists():
                        print(f"privatedata: {n} is not here; skipped")
                        break
                    with local.open("rb") as f:
                        p = subprocess.run(ssh + [f"cat > ~/{REMOTE_DIR}/{n}.part && mv ~/{REMOTE_DIR}/{n}.part ~/{REMOTE_DIR}/{n} && chmod 600 ~/{REMOTE_DIR}/{n}"],
                                           stdin=f, capture_output=True)
                    ok = p.returncode == 0
                    print(f"privatedata: pushed {n} ({local.stat().st_size // 1024} KB)" if ok else f"privatedata: push of {n} failed ({p.returncode}) attempt {attempt + 1}")
                else:
                    p = subprocess.run(ssh + [f"test -f ~/{REMOTE_DIR}/{n} && cat ~/{REMOTE_DIR}/{n}"], capture_output=True)
                    if p.returncode == 1 and not p.stdout:
                        print(f"privatedata: {n} is not on the server yet; skipped")
                        break
                    ok = p.returncode == 0 and bool(p.stdout)
                    if ok:
                        local.write_bytes(p.stdout)
                    print(f"privatedata: pulled {n} ({len(p.stdout) // 1024} KB)" if ok else f"privatedata: pull of {n} failed ({p.returncode}) attempt {attempt + 1}")
                if ok:
                    break
            else:
                failed += 1
        return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] not in ("pull", "push"):
        print(__doc__)
        return 2
    return run(a[0], a[1:])


if __name__ == "__main__":
    sys.exit(main())
