"""Reads the member records that api/m.php writes (sealed with AES-256-GCM: iv 12 bytes | tag 16 bytes | ciphertext, base64).

Used by the e-mail sender (mail_send.py) in GitHub Actions after it copied the members folder and the key file over SSH.
Nothing here prints an address; the callers print counts only.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def unseal(b64: str, key: bytes) -> dict | None:
    try:
        raw = base64.b64decode(b64, validate=True)
        if len(raw) < 29:
            return None
        iv, tag, ct = raw[:12], raw[12:28], raw[28:]
        plain = AESGCM(key).decrypt(iv, ct + tag, None)      # PHP keeps the tag apart; cryptography wants it appended
        d = json.loads(plain.decode("utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001 — a damaged file is skipped, never fatal
        return None


def seal(d: dict, key: bytes, iv: bytes | None = None) -> str:
    """The PHP side's format (for the tests)."""
    iv = iv or os.urandom(12)
    out = AESGCM(key).encrypt(iv, json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), None)
    ct, tag = out[:-16], out[-16:]
    return base64.b64encode(iv + tag + ct).decode("ascii")


def load_key(folder: Path) -> bytes:
    k = (folder / "key").read_bytes()
    if len(k) != 32:
        raise ValueError("the member key file must hold 32 bytes")
    return k


def load_members(folder: Path, key: bytes) -> list[tuple[str, dict]]:
    out = []
    for p in sorted((folder / "m").glob("*.json")):
        d = unseal(p.read_text(encoding="utf-8"), key)
        if d and isinstance(d.get("email"), str):
            out.append((p.stem, d))
    return out
