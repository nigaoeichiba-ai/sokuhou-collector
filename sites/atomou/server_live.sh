#!/bin/bash
# atomou.com 速報 on the server itself (Xserver cron, every 10 minutes): reads the official feeds of data/atomou/live_sources.json (sites/atomou/live.py, Python 3.6 of the server)
# and puts the small live.v1.json where the app reads it.  No SSH, no GitHub: the server fetches the feeds itself (a ministry that refuses GitHub's addresses answers a Japanese host).
# Layout on the server (set up by the workflow atomou-server-live.yml):  ~/atomou.com/script/live/{server_live.sh, sites/atomou/live.py, data/atomou/live_sources.json, state.json, live.v1.json, last.log}
# The cron line:  */10 * * * *  /bin/bash $HOME/atomou.com/script/live/server_live.sh
set -u
HOME_DIR="${HOME:-$(cd ~ && pwd)}"
BASE="$HOME_DIR/atomou.com/script/live"
SITE="$HOME_DIR/atomou.com"
cd "$BASE" || exit 1
# one run at a time (a slow feed must not pile runs up)
if command -v flock > /dev/null 2>&1; then
  exec 9>"$BASE/.lock"
  flock -n 9 || exit 0
fi
LOG="$BASE/last.log"
if ! /usr/bin/python3 sites/atomou/live.py --state "$BASE/state.json" --out "$BASE/live.new.json" > "$LOG" 2>&1; then
  echo "live.py failed" >> "$LOG"
  exit 1
fi
/usr/bin/python3 -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));assert d['v']==1 and isinstance(d['items'],list)" "$BASE/live.new.json" || { echo "bad file" >> "$LOG"; exit 1; }
# put the file in each place that already has an app (the public site and the hidden demo folders), only when the headlines changed or after 6 hours
new=$(/usr/bin/python3 -c "import json,hashlib,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print(hashlib.sha256(json.dumps(d['items'],sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest())" "$BASE/live.new.json")
old=""; at=0
[ -f "$BASE/uploaded.txt" ] && read -r old at < "$BASE/uploaded.txt"
now=$(date +%s)
if [ "$new" = "$old" ] && [ $((now - ${at:-0})) -lt 21600 ]; then
  echo "no change since the last put" >> "$LOG"
  rm -f "$BASE/live.new.json"
  exit 0
fi
for d in public_html public_html/demo public_html/demo.atomou.com; do
  if [ -f "$SITE/$d/index.html" ] && [ -f "$SITE/$d/assets/catalog.json" ]; then
    mkdir -p "$SITE/$d/live"
    cp "$BASE/live.new.json" "$SITE/$d/live/live.v1.json.new" && mv "$SITE/$d/live/live.v1.json.new" "$SITE/$d/live/live.v1.json" && chmod 644 "$SITE/$d/live/live.v1.json"
    echo "put: $d/live/live.v1.json" >> "$LOG"
  fi
done
mv "$BASE/live.new.json" "$BASE/live.v1.json"
echo "$new $now" > "$BASE/uploaded.txt"
