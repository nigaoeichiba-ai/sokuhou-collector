"""Prints {card id: version} of the shared cards on the server (the ids and numbers only; the cards themselves are locked text this script does not read).
Run on the server (Python 3.6) by .github/workflows/atomou-push.yml, slot s:  ssh host python3 - < server_versions.py"""
import glob
import json
import os
import re

out = {}
for f in glob.glob(os.path.expanduser("~/atomou.com/shared/c-*.json")):
    m = re.match(r"^c-([A-Za-z0-9_-]{22})\.json$", os.path.basename(f))
    if not m:
        continue
    try:
        with open(f, encoding="utf-8") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        continue
    if isinstance(c, dict) and not c.get("blocked") and isinstance(c.get("ver"), int):
        out[m.group(1)] = c["ver"]
print(json.dumps(out))
