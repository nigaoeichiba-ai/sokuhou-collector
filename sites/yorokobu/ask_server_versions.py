"""Prints {survey id: number of answers} of the surveys on the server (ids and counts only; the answers themselves are not read).
Run on the server (Python 3.6) by .github/workflows/yorokobu-ask-push.yml:  ssh host python3 - < ask_server_versions.py"""
import glob
import json
import os
import re

out = {}
for f in glob.glob(os.path.expanduser("~/yorokobu-present.com/ask/s/*.json")):
    m = re.match(r"^([A-Za-z0-9_-]{22})\.json$", os.path.basename(f))
    if not m:
        continue
    try:
        with open(f, encoding="utf-8") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        continue
    if isinstance(c, dict) and isinstance(c.get("n"), int):
        out[m.group(1)] = c["n"]
print(json.dumps(out))
