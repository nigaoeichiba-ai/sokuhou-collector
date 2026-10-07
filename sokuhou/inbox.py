"""Messages from the sites' contact forms: copy them off the servers into the repository ENCRYPTED, and read them again on the owner's PC.

The repository is public, so a message (which may carry an e-mail address) is never stored in clear text there.

    # in GitHub Actions (.github/workflows/inbox.yml), per site, with the raw server dump in RAW:
    python -m sokuhou.inbox new --site yorokobu --raw RAW --state data/inbox/state.json --out NEW.jsonl
    openssl smime -encrypt -aes256 -binary -in NEW.jsonl -out data/inbox/yorokobu-<stamp>.p7m -outform DER sokuhou/inbox_cert.pem

    # on the owner's PC (routines): decrypt what has not been read yet; the private key never leaves ~/.sokuhou/
    python -m sokuhou.inbox read [--mark]

RAW is `== <file>` headers followed by that file's lines, as the workflow prints them.  The state file records how many lines of each server
file were already taken, so a message is copied exactly once.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "inbox"
KEY = Path.home() / ".sokuhou" / "inbox_private.pem"
SEEN = Path.home() / ".sokuhou" / "inbox_seen.json"
FIELDS = ("id", "at", "site", "kind", "message", "email", "page")


def parse_raw(raw: str) -> dict[str, list[str]]:
    files: dict[str, list[str]] = {}
    current = None
    for line in raw.splitlines():
        if line.startswith("== "):
            current = line[3:].strip()
            files[current] = []
        elif current is not None and line.strip():
            files[current].append(line)
    return files


def take_new(raw: str, state: dict) -> tuple[list[dict], dict]:
    """The messages of `raw` that the state has not seen (as dicts with only the known fields), and the new state."""
    out, new_state = [], dict(state)
    for name, lines in parse_raw(raw).items():
        done = int(new_state.get(name, 0))
        for line in lines[done:]:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("message"):
                out.append({k: rec.get(k, "") for k in FIELDS})
        new_state[name] = max(done, len(lines))
    return out, new_state


def cmd_new(a: argparse.Namespace) -> int:
    state_all = json.loads(Path(a.state).read_text(encoding="utf-8")) if Path(a.state).exists() else {}
    new, state_site = take_new(Path(a.raw).read_text(encoding="utf-8", errors="replace"), state_all.get(a.site, {}))
    state_all[a.site] = state_site
    Path(a.state).parent.mkdir(parents=True, exist_ok=True)
    Path(a.state).write_text(json.dumps(state_all, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new), encoding="utf-8", newline="\n")
    print(f"{a.site}: {len(new)} new message(s)")
    return 0


def summarize(site: str, records: list[dict]) -> str:
    """One line for the owner's notice: the site, how many messages, and how many of each KIND (a fixed menu).  Never the message, the e-mail address or the page."""
    kinds: dict[str, int] = {}
    for r in records:
        kinds[str(r.get("kind") or "(種類なし)")[:60]] = kinds.get(str(r.get("kind") or "(種類なし)")[:60], 0) + 1
    return f"{site}: {len(records)}件(" + "、".join(f"{k} {n}件" for k, n in sorted(kinds.items())) + ")"


def cmd_summary(a: argparse.Namespace) -> int:
    recs = [json.loads(x) for x in Path(a.file).read_text(encoding="utf-8").splitlines() if x.strip()]
    if recs:
        print(summarize(a.site, recs))
    return 0


def decrypt(path: Path, key: Path = KEY) -> list[dict]:
    r = subprocess.run(["openssl", "smime", "-decrypt", "-inform", "DER", "-in", str(path), "-inkey", str(key)], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"cannot decrypt {path.name}: {r.stderr.decode('utf-8', 'replace')[:200]}")
    return [json.loads(x) for x in r.stdout.decode("utf-8").splitlines() if x.strip()]


def cmd_read(a: argparse.Namespace) -> int:
    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() and not a.all else set()
    found = []
    for f in sorted(INBOX.glob("*.p7m")):
        if f.name in seen:
            continue
        site = f.name.split("-")[0]
        for rec in decrypt(f, Path(a.key)):
            found.append({**rec, "file": f.name, "site": rec.get("site") or site})
        seen.add(f.name)
    for rec in found:
        print(json.dumps(rec, ensure_ascii=False))
    if a.mark:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    print(f"{len(found)} message(s)", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--site", required=True)
    n.add_argument("--raw", required=True)
    n.add_argument("--state", required=True)
    n.add_argument("--out", required=True)
    m = sub.add_parser("summary", help="one line per site for the owner's notice (no message text)")
    m.add_argument("--site", required=True)
    m.add_argument("--file", required=True)
    r = sub.add_parser("read")
    r.add_argument("--key", default=str(KEY))
    r.add_argument("--mark", action="store_true", help="remember that these messages were read")
    r.add_argument("--all", action="store_true", help="ignore what was read before")
    a = ap.parse_args()
    return {"new": cmd_new, "summary": cmd_summary, "read": cmd_read}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
