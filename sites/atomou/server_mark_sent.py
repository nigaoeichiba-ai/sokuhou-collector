"""Writes back what the sender announced (slot s): reads ~/atomou.com/push/.notified.json ({subscription file name: {card id: version}}) and sets "sent" of those watched cards
in the subscription files, so that the same change is never announced twice.  Run on the server (Python 3.6):  ssh host python3 - < server_mark_sent.py"""
import json
import os
import re

folder = os.path.expanduser("~/atomou.com/push")
src = os.path.join(folder, ".notified.json")
n = 0
try:
    with open(src, encoding="utf-8") as fh:
        notified = json.load(fh)
except (OSError, ValueError):
    notified = {}
for name, cards in (notified.items() if isinstance(notified, dict) else []):
    if not re.match(r"^[0-9a-f]{64}\.json$", name) or not isinstance(cards, dict):
        continue
    path = os.path.join(folder, name)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        continue
    for w in rec.get("watch") or []:
        if isinstance(w, dict) and isinstance(cards.get(w.get("id")), int):
            w["sent"] = max(int(w.get("sent", 0)), cards[w["id"]])
            n += 1
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    os.replace(tmp, path)
try:
    os.remove(src)
except OSError:
    pass
print("marked %d" % n)
