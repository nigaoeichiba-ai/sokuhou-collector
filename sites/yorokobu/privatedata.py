"""The private store of the data the mall APIs give (Rakuten, Yahoo!): a folder on the site's server that is not in public_html, never the repository.

The terms of the Rakuten Web Service bar keeping what the API gives "in a place where information can be shared with an unspecified or a large number of people" (Article 10 (1) (9)),
and the help page lets prices and availability be kept for 24 hours and the rest for three months.  So the daily workflows (yorokobu-compare, -yahoo, -ranking, -candidates) do not commit
their result to the public repository: they write it here, and the deploy takes the files from here before it builds.

    python -m sites.yorokobu.privatedata pull [name ...]     server -> data/<name>     (a file the server does not have yet is skipped, with a note)
    python -m sites.yorokobu.privatedata push [name ...]     data/<name> -> server

Both directions are ONE ssh connection for the whole set (a tar stream), so a deploy opens few connections to the server.  `name` is one of FILES (default: all).  The connection is the deploy's: the repository secrets XSERVER_SSH_KEY, XSERVER_HOST, XSERVER_USER (port 10022, as in deploy.yml); without them
nothing happens (a fork, a local run).  The data/ files are git-ignored: they exist only in a run that pulled them, and the build runs without them (the pages that need them are left out).
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REMOTE_DIR = "yorokobu-private"                    # in the SSH user's home, beside public_html: nothing in it is served
FILES = ("yorokobu_compare.json", "yorokobu_yahoo.json", "yorokobu_ranking.json", "yorokobu_candidates.json")
BUILD_FILES = ("yorokobu_items_db.json", "yorokobu_gacha_db.json", "yorokobu_rec_db.json")            # made by the build and only pushed (api/items.php reads them); a pull of everything does not fetch them
WAIT = (0, 10, 30)                                 # seconds before the 1st, 2nd and 3rd try: a connection that fails at once (ssh 255, seen on 2026-10-18 for all four files in two deploys) is tried again after a pause
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
    bad = [n for n in names if n not in FILES + BUILD_FILES]
    if bad:
        print(f"privatedata: unknown file {bad}; one of {FILES + BUILD_FILES}")
        return 2
    DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        kf, kh = Path(td) / "key", Path(td) / "known_hosts"
        kf.write_text(key.strip() + chr(10), encoding="utf-8")
        kf.chmod(0o600)
        ssh = _ssh_base(str(kf), str(kh), host, user)
        if action == "push":
            return _push(ssh, names)
        return _pull(ssh, names)


def _try(ssh: list[str], remote: str, data: bytes | None = None) -> subprocess.CompletedProcess | None:
    """One connection per try (the whole set of files travels as one tar stream); the next try comes after a pause.  None when every try failed."""
    for attempt in range(3):
        time.sleep(WAIT[attempt])
        p = subprocess.run(ssh + [remote], input=data, capture_output=True)
        if p.returncode == 0:
            return p
        print(f"privatedata: the connection failed ({p.returncode}) attempt {attempt + 1}")
    return None


def _pull(ssh: list[str], names: list[str]) -> int:
    """All the files the server has, of `names`, in ONE connection: the server packs them into a tar stream (a file it does not have yet is left out)."""
    listing = " ".join(names)
    remote = f"cd ~/{REMOTE_DIR} 2>/dev/null || exit 0; f=''; for n in {listing}; do [ -f \"$n\" ] && f=\"$f $n\"; done; [ -z \"$f\" ] && exit 0; tar cf - $f"
    p = _try(ssh, remote)
    if p is None:
        return 1
    got: set[str] = set()
    if p.stdout:
        with tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:") as tf:
            for m in tf:
                if m.isfile() and m.name in names and "/" not in m.name:           # only the named plain files, nothing else
                    (DATA / m.name).write_bytes(tf.extractfile(m).read())
                    got.add(m.name)
                    print(f"privatedata: pulled {m.name} ({m.size // 1024} KB)")
    for n in names:
        if n not in got:
            print(f"privatedata: {n} is not on the server yet; skipped")
    return 0


def _push(ssh: list[str], names: list[str]) -> int:
    """The files that exist here, in ONE connection: a tar stream unpacked into a side folder, then moved into place (a reader never sees half a file), mode 600; the folder is 700."""
    here = [n for n in names if (DATA / n).exists()]
    for n in names:
        if n not in here:
            print(f"privatedata: {n} is not here; skipped")
    if not here:
        return 0
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tf:
        for n in here:
            tf.add(DATA / n, arcname=n)
    d = f"~/{REMOTE_DIR}"
    remote = f"mkdir -p {d} && chmod 700 {d} && cd {d} && rm -rf .in && mkdir .in && cd .in && tar xf - && chmod 600 * && mv -f * .. && cd .. && rmdir .in"
    if _try(ssh, remote, buf.getvalue()) is None:
        return 1
    for n in here:
        print(f"privatedata: pushed {n} ({(DATA / n).stat().st_size // 1024} KB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] not in ("pull", "push"):
        print(__doc__)
        return 2
    return run(a[0], a[1:])


if __name__ == "__main__":
    sys.exit(main())
