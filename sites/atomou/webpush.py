"""Web Push without a library: RFC 8291 (aes128gcm message encryption), RFC 8188 (encrypted content encoding), RFC 8292 (VAPID).

Only `cryptography` is needed.  Everything is pure functions, so the tests can play the browser's side (decrypt with the
subscription's private key, verify the VAPID token with the public key) without any network.

A subscription, as the browser hands it over (PushSubscription.toJSON()):
    {"endpoint": "https://...", "keys": {"p256dh": "<base64url 65-byte uncompressed P-256 point>", "auth": "<base64url 16 bytes>"}}
"""
from __future__ import annotations

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand

CURVE = ec.SECP256R1()
RS = 4096                       # record size: one record is enough for a notification (payload limit of the push services is 4 KB)
MAX_PAYLOAD = 3900


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------- keys ----------
def private_key_from_b64u(raw: str) -> ec.EllipticCurvePrivateKey:
    """The VAPID private key as the 32-byte scalar in base64url (what make_vapid.py prints; also what most tools print)."""
    return ec.derive_private_key(int.from_bytes(b64u_decode(raw), "big"), CURVE)


def load_private_key(text: str) -> ec.EllipticCurvePrivateKey:
    """Accepts the base64url scalar or a PEM block."""
    t = text.strip()
    if t.startswith("-----"):
        k = serialization.load_pem_private_key(t.encode("ascii"), password=None)
        if not isinstance(k, ec.EllipticCurvePrivateKey):
            raise ValueError("not an EC private key")
        return k
    return private_key_from_b64u(t)


def public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def public_key_from_bytes(raw: bytes) -> ec.EllipticCurvePublicKey:
    return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, raw)


def generate_vapid() -> tuple[str, str]:
    """(private scalar base64url, public point base64url).  The private value is a secret: it goes to a GitHub secret, never into the repository."""
    k = ec.generate_private_key(CURVE)
    priv = k.private_numbers().private_value.to_bytes(32, "big")
    return b64u(priv), b64u(public_bytes(k.public_key()))


# ---------- VAPID (RFC 8292) ----------
def vapid_token(private_key: ec.EllipticCurvePrivateKey, audience: str, subject: str, now: int | None = None, ttl: int = 12 * 3600) -> str:
    now = int(time.time()) if now is None else now
    head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64u(json.dumps({"aud": audience, "exp": now + ttl, "sub": subject}, separators=(",", ":")).encode())
    signing = f"{head}.{body}".encode("ascii")
    der = private_key.sign(signing, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return f"{head}.{body}." + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def vapid_verify(token: str, public_key: ec.EllipticCurvePublicKey) -> dict:
    """The push service's side (used by the tests): checks the signature and returns the claims."""
    head, body, sig = token.split(".")
    raw = b64u_decode(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    public_key.verify(der, f"{head}.{body}".encode("ascii"), ec.ECDSA(hashes.SHA256()))
    return json.loads(b64u_decode(body))


def audience_of(endpoint: str) -> str:
    u = urlsplit(endpoint)
    if u.scheme != "https" or not u.netloc:
        raise ValueError("the endpoint must be an https URL")
    return f"{u.scheme}://{u.netloc}"


# ---------- message encryption (RFC 8291 + RFC 8188, aes128gcm) ----------
def _hkdf_extract_expand(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _keys(ecdh_secret: bytes, auth: bytes, client_pub: bytes, server_pub: bytes, salt: bytes) -> tuple[bytes, bytes]:
    # RFC 8291 §3.3 / §3.4
    ikm = _hkdf_extract_expand(auth, ecdh_secret, b"WebPush: info\x00" + client_pub + server_pub, 32)
    cek = _hkdf_extract_expand(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_extract_expand(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    return cek, nonce


def encrypt(plaintext: bytes, p256dh: str, auth: str, *, salt: bytes | None = None, server_key: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """The body of the push request (header block + one encrypted record), RFC 8188 aes128gcm with the keys of RFC 8291."""
    if len(plaintext) > MAX_PAYLOAD:
        raise ValueError("payload too long")
    client_pub = b64u_decode(p256dh)
    auth_secret = b64u_decode(auth)
    if len(client_pub) != 65 or client_pub[0] != 4 or len(auth_secret) != 16:
        raise ValueError("bad subscription keys")
    server_key = server_key or ec.generate_private_key(CURVE)
    server_pub = public_bytes(server_key.public_key())
    secret = server_key.exchange(ec.ECDH(), public_key_from_bytes(client_pub))
    salt = salt or os.urandom(16)
    cek, nonce = _keys(secret, auth_secret, client_pub, server_pub, salt)
    record = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)      # 0x02: the last (only) record
    header = salt + struct.pack(">I", RS) + bytes([len(server_pub)]) + server_pub
    return header + record


def decrypt(body: bytes, client_key: ec.EllipticCurvePrivateKey, auth: str) -> bytes:
    """The browser's side (tests only): undo `encrypt` with the subscription's private key."""
    salt, rs, idlen = body[:16], struct.unpack(">I", body[16:20])[0], body[20]
    server_pub = body[21:21 + idlen]
    record = body[21 + idlen:]
    if rs != RS or len(record) > rs:
        raise ValueError("unexpected record layout")
    client_pub = public_bytes(client_key.public_key())
    secret = client_key.exchange(ec.ECDH(), public_key_from_bytes(server_pub))
    cek, nonce = _keys(secret, b64u_decode(auth), client_pub, server_pub, salt)
    plain = AESGCM(cek).decrypt(nonce, record, None)
    if not plain.endswith(b"\x02"):
        raise ValueError("bad padding delimiter")
    return plain[:-1]


# ---------- sending ----------
@dataclass
class Result:
    status: int          # HTTP status (0 = no answer)
    gone: bool           # 404 / 410: the subscription is dead and must be deleted
    retry: bool          # 429 / 5xx / no answer: try again next time
    detail: str = ""


def send(subscription: dict, payload: dict, private_key: ec.EllipticCurvePrivateKey, subject: str, *, ttl: int = 12 * 3600, urgency: str = "normal",
         opener=None, now: int | None = None) -> Result:
    """One push.  `opener` (tests) replaces urllib.request.urlopen.  Nothing about the subscription is logged here."""
    endpoint = subscription["endpoint"]
    keys = subscription.get("keys") or {}
    body = encrypt(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), keys["p256dh"], keys["auth"])
    token = vapid_token(private_key, audience_of(endpoint), subject, now=now)
    pub = b64u(public_bytes(private_key.public_key()))
    req = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/octet-stream", "Content-Encoding": "aes128gcm", "Content-Length": str(len(body)),
        "TTL": str(ttl), "Urgency": urgency, "Authorization": f"vapid t={token}, k={pub}",
    })
    try:
        with (opener or urllib.request.urlopen)(req, timeout=20) as r:
            return Result(r.status, False, False)
    except urllib.error.HTTPError as e:
        return Result(e.code, e.code in (404, 410), e.code == 429 or e.code >= 500, (e.read(200) or b"").decode("utf-8", "replace")[:200] if hasattr(e, "read") else "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Result(0, False, True, type(e).__name__)
