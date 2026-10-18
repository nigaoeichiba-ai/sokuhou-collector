"""Upload a built site to its folder on the server and switch to it (the 'Upload and switch' step of .github/workflows/deploy.yml).

    python -m sokuhou.deployupload --dir <folder in the SSH user's home> [--release release] [--mode auto|rsync|tar]

Since 2026-10-18 the default is an incremental upload: the new site is first made as a hard-linked copy of the live one (`cp -al`: the files are not copied, the
inodes stay), then rsync sends only the files whose CONTENT differs (--checksum: the build writes every file with a new time, so size and time say nothing), then a
second rsync (a dry run with --checksum --delete) must find nothing left to do - that is the check, by content, that the server has exactly what was built - and only
then are the folders switched (public_html -> .deploy_prev, .deploy_next -> public_html: the rollback of deploy.yml is unchanged).  minna's full upload of 747 MB took
165 to 400 seconds; unchanged images are not sent again.  Where rsync is missing, or --mode tar, the whole site is sent as one tar stream as before.

A file rsync replaces is written next to the old one and renamed over it, so the old copy (.deploy_prev, the rollback) keeps its content.  Nothing here changes the live
folder before the last command; a connection lost earlier (ssh exit 255) leaves the live site as it was, and is reported to the workflow ("unreachable=true").
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys

CARRY = ("live", "demo/live", "demo.atomou.com/live")   # atomou's live file (written every 10 minutes by the server's own cron) is not part of the build: it is kept, never deleted
PORT = os.environ.get("SSH_PORT", "10022")


def ssh_base() -> list[str]:
    return ["ssh", "-i", os.path.expanduser("~/.ssh/id_xserver"), "-p", PORT, "-o", "BatchMode=yes", f"{os.environ['USER_ID']}@{os.environ['HOST']}"]


def run(cmd: list[str], stdin=None, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdin=stdin, capture_output=capture, text=capture)


def remote(script: str, capture: bool = False) -> subprocess.CompletedProcess:
    return run(ssh_base() + [script], capture=capture)


def has_rsync(site_dir: str) -> bool:
    return remote(f'cd "$HOME/{site_dir}" && command -v rsync > /dev/null && test -d public_html', capture=True).returncode == 0 and subprocess.run(["rsync", "--version"], capture_output=True).returncode == 0


def rsync_cmd(site_dir: str, release: str, *extra: str) -> list[str]:
    ssh = f"ssh -i {os.path.expanduser('~/.ssh/id_xserver')} -p {PORT} -o BatchMode=yes"
    protect = [x for d in CARRY for x in ("--filter", f"P /{d}/")]
    return ["rsync", "-rlpt", "--checksum", "--delete", *protect, *extra, "-e", ssh, release.rstrip("/") + "/", f"{os.environ['USER_ID']}@{os.environ['HOST']}:{site_dir}/.deploy_next/"]


def upload_rsync(site_dir: str, release: str) -> int:
    q = shlex.quote(site_dir)
    rc = remote(f'set -e; cd "$HOME/"{q}; rm -rf .deploy_next; cp -al public_html .deploy_next').returncode
    if rc:
        return rc
    rc = run(rsync_cmd(site_dir, release, "--stats")).returncode
    if rc:
        return 255 if rc in (12, 255) else rc     # rsync 12 or 255 = the ssh connection died
    check = run(rsync_cmd(site_dir, release, "-n", "--itemize-changes"), capture=True)
    if check.returncode:
        print(check.stdout, check.stderr)
        return check.returncode
    left = [line for line in check.stdout.splitlines() if line.strip() and not line.startswith(("sending", "sent ", "total size", "building"))]
    if left:
        print("the server does not hold what was built after the upload; nothing was switched. Differences:")
        print("\n".join(left[:40]))
        return 1
    print("verified by content: the new folder on the server is identical to the build")
    return switch(site_dir)


def switch(site_dir: str) -> int:
    q = shlex.quote(site_dir)
    return remote(f'set -e; cd "$HOME/"{q}; test -f .deploy_next/index.html; test -f .deploy_next/.htaccess; rm -rf .deploy_prev; mv public_html .deploy_prev; mv .deploy_next public_html').returncode


def upload_tar(site_dir: str, release: str) -> int:
    q = shlex.quote(site_dir)
    carry = " ".join(CARRY)
    script = (f'set -e; cd "$HOME/"{q}; rm -rf .deploy_next; mkdir .deploy_next; tar -xzf - -C .deploy_next; test -f .deploy_next/index.html; test -f .deploy_next/.htaccess; '
              f'for d in {carry}; do if [ -d "public_html/$d" ]; then mkdir -p ".deploy_next/$(dirname $d)"; cp -a "public_html/$d" ".deploy_next/$d"; fi; done; '
              'rm -rf .deploy_prev; mv public_html .deploy_prev; mv .deploy_next public_html')
    tar = subprocess.Popen(["tar", "-C", release, "-czf", "-", "."], stdout=subprocess.PIPE)
    rc = run(ssh_base() + [script], stdin=tar.stdout).returncode
    tar.stdout.close()
    tar.wait()
    return rc or tar.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--release", default="release")
    ap.add_argument("--mode", choices=("auto", "rsync", "tar"), default="auto")
    a = ap.parse_args(argv)
    mode = a.mode
    if mode == "auto":
        mode = "rsync" if has_rsync(a.dir) else "tar"
        print(f"upload mode: {mode}")
    rc = upload_rsync(a.dir, a.release) if mode == "rsync" else upload_tar(a.dir, a.release)
    if rc == 255 and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("unreachable=true\n")
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
