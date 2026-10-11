"""Writes back what the sender announced: reads ~/yorokobu-present.com/ask/push/.notified.json ({subscription file name: {survey id: answers announced}}) and sets "sent"
of those surveys in the subscription files, so that the same answer is never announced twice.  Run on the server (Python 3.6):  ssh host python3 - < ask_server_mark.py"""
import json
import os
import re

folder = os.path.expanduser("~/yorokobu-present.com/ask/push")
src = os.path.join(folder, ".notified.json")
n = 0
try:
    with open(src, encoding="utf-8") as fh:
        notified = json.load(fh)
except (OSError, ValueError):
    notified = {}
for name, surveys in (notified.items() if isinstance(notified, dict) else []):
    if not re.match(r"^[0-9a-f]{64}\.json$", name) or not isinstance(surveys, dict):
        continue
    path = os.path.join(folder, name)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        continue
    for w in rec.get("watch") or []:
        if isinstance(w, dict) and isinstance(surveys.get(w.get("id")), int):
            w["sent"] = max(int(w.get("sent", 0)), surveys[w["id"]])
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
