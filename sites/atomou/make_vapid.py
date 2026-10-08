"""Makes the VAPID key pair for the push notifications (the owner runs this once; the output is not written to any file).

    python sites/atomou/make_vapid.py

Register the PRIVATE line as the GitHub secret ATOMOU_VAPID_PRIVATE (Settings > Secrets and variables > Actions), and put the PUBLIC
line into sites/atomou/config.json as "vapid_public" (it is a public value and may be committed).  The two belong together: if a new
pair is made later, every visitor must subscribe again.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sites.atomou import webpush  # noqa: E402

if __name__ == "__main__":
    priv, pub = webpush.generate_vapid()
    print("PRIVATE (GitHub secret ATOMOU_VAPID_PRIVATE):", priv)
    print("PUBLIC  (config.json vapid_public):          ", pub)
