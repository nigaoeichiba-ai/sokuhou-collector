"""Measuring the lead indicators L4 (clicks on partner links) and L5 (time on page, return visits, pages per visit) without knowing who anybody is.

How it works (decided 2026-11-03 with the report desk; the privacy text of the sites says the same, see sitekit.legal_pages):
  * The page loads a ~1 KB script (MEASURE_JS).  It sends a few GET requests for one tiny file, /m/t.gif, whose query carries only a KIND and a bucketed number:
        k=s&r=0|1                       a visit began in this tab (r=1: this browser was here during the last 7 days)
        k=c&t=aff|out|dl                a click on a partner link / another site / a download (the kind only: never the address, never the page)
        k=e&d=<bucket>&n=<bucket>       the page was left: seconds it was visible (bucket) and how many pages this visit has seen (bucket)
  * No cookie, no identifier, no IP address and no page address is sent or kept.  The only thing stored is on the visitor's own device (a time stamp in localStorage,
    to know whether the browser was here during the last 7 days, and a page counter in sessionStorage); neither is ever sent.
  * The web server's ordinary access log records the requests; sokuhou/accesslog.py reads the log and prints COUNTS only.  Nothing else is kept in the repository.
Numbers this gives (6-2 of docs/new_sites/BATCH1_PROPOSAL.md):
    L4  partner-link clicks per visit            = clicks of kind aff / visits
    L5  the middle time on a page (a bucket), return rate = visits with r=1 / visits, pages per visit = page leaves / visits
They are approximations (a script that is blocked, a tab that is killed and a browser that never fires the leave event are missed), and bots that run scripts are
filtered only by their user agent; compare them with the Search Console clicks before trusting a trend.  With fewer than MIN_VISITS visits nothing is judged.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qs, urlsplit

BEACON_PATH = "/m/t.gif"
MIN_VISITS = 100                  # 6-3: no signal for L4 below 100 sessions
DWELL_BUCKETS = (5, 15, 30, 60, 120, 300, 600)         # seconds: "up to 5", ... ; 600 stands for "more than 300"
PAGE_BUCKETS = (1, 2, 3, 4, 5)                         # 5 = five or more
CLICK_KINDS = ("aff", "out", "dl")

MEASURE_JS = r"""(function(){
var D=document,W=window,N=navigator,S=null,L=null,T=Date.now(),vis=0,seen=T,gone=0;
if(N.webdriver||N.doNotTrack==="1"||W.doNotTrack==="1")return;
try{S=W.sessionStorage}catch(e){}try{L=W.localStorage}catch(e){}
function send(q){var u="/m/t.gif?"+q+"&_="+Math.random().toString(36).slice(2,6);
try{if(W.fetch){W.fetch(u,{method:"GET",keepalive:true,mode:"no-cors",credentials:"omit"});return}}catch(e){}
try{(new Image()).src=u}catch(e){}}
function up(a,b){for(var i=0;i<a.length;i++)if(b<=a[i])return a[i];return a[a.length-1]}
var n=1;
if(S){try{n=(parseInt(S.getItem("m_n"),10)||0)+1;S.setItem("m_n",String(n));
if(n===1){var r=0;if(L){var p=parseInt(L.getItem("m_v"),10);if(p&&T-p<=6048e5)r=1;L.setItem("m_v",String(T))}send("k=s&r="+r)}}catch(e){}}
D.addEventListener("click",function(e){var a=e.target&&e.target.closest?e.target.closest("a"):null;if(!a)return;
var t=a.getAttribute("data-m")||"";if(!t){var rel=" "+(a.getAttribute("rel")||"")+" ";if(rel.indexOf(" sponsored ")>-1)t="aff";else if(a.hasAttribute("download"))t="dl";else if(a.host&&a.host!==W.location.host)t="out"}
if(t==="aff"||t==="out"||t==="dl")send("k=c&t="+t)},true);
D.addEventListener("visibilitychange",function(){var now=Date.now();if(D.visibilityState==="hidden"){vis+=now-seen;leave()}else seen=now});
function leave(){if(gone)return;gone=1;var s=Math.round(vis/1000);if(D.visibilityState!=="hidden")s=Math.round((vis+Date.now()-seen)/1000);
send("k=e&d="+up([5,15,30,60,120,300,600],s)+"&n="+up([1,2,3,4,5],n))}
W.addEventListener("pagehide",function(){if(!gone){if(D.visibilityState!=="hidden")vis+=Date.now()-seen;leave()}});
})();
"""

# the 1x1 transparent GIF the script asks for (so that the server answers 200 and the line is a plain, countable request)
GIF = bytes.fromhex("47494638396101000100800000dbdfef00000021f90401000000002c00000000010001000002024401003b")


def parse_beacon(target: str) -> dict | None:
    """The beacon in a request target ('/m/t.gif?k=c&t=aff&_=ab12'), or None for anything else or anything that does not look exactly like one of ours."""
    u = urlsplit(target)
    if u.path != BEACON_PATH:
        return None
    q = {k: v[0] for k, v in parse_qs(u.query).items() if v}
    k = q.get("k")
    if k == "s" and q.get("r") in ("0", "1"):
        return {"k": "s", "r": int(q["r"])}
    if k == "c" and q.get("t") in CLICK_KINDS:
        return {"k": "c", "t": q["t"]}
    if k == "e" and q.get("d", "").isdigit() and q.get("n", "").isdigit() and int(q["d"]) in DWELL_BUCKETS and int(q["n"]) in PAGE_BUCKETS:
        return {"k": "e", "d": int(q["d"]), "n": int(q["n"])}
    return None


def new() -> dict:
    return {"visits": 0, "returning": 0, "clicks": Counter(), "leaves": 0, "dwell": Counter(), "pages": Counter(), "ignored": 0}


def add(m: dict, b: dict) -> None:
    if b["k"] == "s":
        m["visits"] += 1
        m["returning"] += b["r"]
    elif b["k"] == "c":
        m["clicks"][b["t"]] += 1
    else:
        m["leaves"] += 1
        m["dwell"][b["d"]] += 1
        m["pages"][b["n"]] += 1


def median_bucket(hist: Counter) -> int | None:
    total = sum(hist.values())
    if not total:
        return None
    run = 0
    for b in sorted(hist):
        run += hist[b]
        if run * 2 >= total:
            return b
    return None


def summary(m: dict) -> dict:
    """The numbers for the ledger.  A value is None when it cannot be judged (too few visits, nothing measured): the ledger says 測れなかった, never a number."""
    v = m["visits"]
    ok = v >= MIN_VISITS
    return {"visits": v, "aff_clicks": m["clicks"]["aff"], "out_clicks": m["clicks"]["out"], "dl_clicks": m["clicks"]["dl"], "page_leaves": m["leaves"],
            "L4_aff_per_visit": (m["clicks"]["aff"] / v) if ok else None,
            "L5_median_dwell_bucket_sec": median_bucket(m["dwell"]) if m["leaves"] >= MIN_VISITS else None,
            "L5_return_rate": (m["returning"] / v) if ok else None,
            "L5_pages_per_visit": (m["leaves"] / v) if ok else None}


def render(m: dict) -> str:
    s = summary(m)
    if not (m["visits"] or m["leaves"] or sum(m["clicks"].values())):
        return "- 計測ビーコン: 受信なし(計測のスクリプトが入っていないか、まだ誰も来ていません)"
    def pct(x):
        return "測れなかった(訪問が%d未満)" % MIN_VISITS if x is None else f"{x * 100:.1f}%"
    med = s["L5_median_dwell_bucket_sec"]
    return "\n".join([
        f"- 計測ビーコン(個人を特定しない件数のみ): 訪問 {s['visits']}、ページを離れた回数 {s['page_leaves']}、クリック 提携 {s['aff_clicks']} / 外部 {s['out_clicks']} / ダウンロード {s['dl_clicks']}",
        f"  - L4 提携リンクのクリック ÷ 訪問: {pct(s['L4_aff_per_visit'])}",
        f"  - L5 ページの滞在の中央値: " + ("測れなかった" if med is None else (f"{med}秒以下の区間" if med < DWELL_BUCKETS[-1] else f"{DWELL_BUCKETS[-2]}秒超の区間")) +
        f"、7日以内の再訪率: {pct(s['L5_return_rate'])}、1訪問のページ数: " + ("測れなかった" if s['L5_pages_per_visit'] is None else f"{s['L5_pages_per_visit']:.2f}"),
        "  - 近似です(スクリプトを止めた閲覧・離脱イベントが出ない閲覧は数えられません)。Search Console のクリックと突き合わせてから傾向を読む。"])
