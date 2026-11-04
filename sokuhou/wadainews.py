"""wadai: the morning news collector and the 'primary bundle' (READ ONLY; nothing is published; nothing is posted).

What it does (design: docs/new_sites/WADAI_DESIGN_2026-11-04.md, WADAI_NEWS_DRAFTS_2026-11-04.md section 7, steps 1-4):
 1. collect   read public RSS / Atom feeds, politely, and keep only the HEADLINE and its DATE (and the source id) in the private folder (~/wadai-private/news/YYYYMMDD.jsonl).
              No body, no link, no summary are kept.  A source that refuses (robots.txt disallow, HTTP 401/403/429) is written to news/refused.json and never used again.
 2. report    classify every headline (rules, no AI) and write the day's counts: how many headlines, how many can lead to a product, why the others do not.
              Candidate headlines are listed only in the private report file, never on stdout (stdout may land in a public CI log).
 3. bundle    fetch the PRIMARY facts that a candidate needs: the typhoon data of the Japan Meteorological Agency and the notice list of the Disaster Management Agency, and keep
              the facts as fill-in lines for the fact layer of an article (title, date and numbers only).
 4. skeleton  pour the facts into an article skeleton (fact layer filled; view and preparation layers left for the editor) and run the checks of wadaipost.py on it.
 Every stage writes its start and end time to news/timing.jsonl, so that the 'one hour' target is measured, not felt.

Rules kept here (owner conditions 2026-11-04): RSS and public pages only; robots.txt checked first; a gap between requests; only headline + date kept; the private folder only;
a refused source is dropped.  No login, no CAPTCHA, no scraping of article bodies.  The repository holds this code and its tests, never the news, the feeds' content or any token.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

UA = "sokuhou-collector/0.1 (read-only news headline reader; headline and date only)"
HOST_GAP = 3.0           # seconds between two requests to the same host
ANY_GAP = 1.0            # seconds between any two requests
HOST_GAPS = {"b.hatena.ne.jp": 5.0}      # hosts whose robots.txt asks for a longer Crawl-delay
MAX_BYTES = 5_000_000
REFUSE_STATUS = {401, 403, 429}
REPO_ROOT = Path(__file__).resolve().parents[1]

# id -> (url, kind).  kind: general / business / tech / science / security / official.  Sports and entertainment-only feeds are not read.
SOURCES = {
    "yahoo-top": ("https://news.yahoo.co.jp/rss/topics/top-picks.xml", "general"),
    "yahoo-domestic": ("https://news.yahoo.co.jp/rss/topics/domestic.xml", "general"),
    "yahoo-business": ("https://news.yahoo.co.jp/rss/topics/business.xml", "business"),
    "yahoo-it": ("https://news.yahoo.co.jp/rss/topics/it.xml", "tech"),
    "yahoo-local": ("https://news.yahoo.co.jp/rss/topics/local.xml", "general"),
    "yahoo-science": ("https://news.yahoo.co.jp/rss/topics/science.xml", "science"),
    "itmedia": ("https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml", "tech"),
    "gnews": ("https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja", "general"),
    "jiji": ("https://www.jiji.com/rss/ranking.rdf", "general"),
    "kyodo-yahoo": ("https://news.yahoo.co.jp/rss/media/kyodonews/all.xml", "general"),
    "trends": ("https://trends.google.com/trending/rss?geo=JP", "general"),
    # aggregators: used only to DISCOVER headlines (owner 2026-11-04).  A fact is written only after it is checked at the primary (the party's own announcement, an office, the report itself).
    "livedoor": ("https://news.livedoor.com/topics/rss/top.xml", "aggregator"),
    "hatena": ("https://b.hatena.ne.jp/hotentry/all.rss", "aggregator"),
    "nhk-main": ("https://www3.nhk.or.jp/rss/news/cat0.xml", "general"),
    "asahi": ("https://www.asahi.com/rss/asahi/newsheadlines.rdf", "general"),
    "jpcert": ("https://www.jpcert.or.jp/rss/jpcert.rdf", "security"),
    "ipa": ("https://www.ipa.go.jp/security/alert-rss.rdf", "security"),
}
JMA_TARGETS = "https://www.jma.go.jp/bosai/typhoon/data/targetTc.json"
JMA_SPEC = "https://www.jma.go.jp/bosai/typhoon/data/{tc}/specifications.json"
BOUSAI_TOP = "https://www.bousai.go.jp/"


# ---- private folder ----------------------------------------------------------------------------------------------------------------------------
def private_dir(path: str | Path) -> Path:
    """The private folder must exist and must not be inside this repository (the repository is public)."""
    p = Path(path).expanduser().resolve()
    try:
        p.relative_to(REPO_ROOT)
    except ValueError:
        pass
    else:
        raise ValueError(f"{p} is inside the repository; the news must stay in ~/wadai-private/")
    (p / "news").mkdir(parents=True, exist_ok=True)
    return p


class Stopwatch:
    """Writes the start and end of every stage to news/timing.jsonl (ISO times) so that the speed is measured."""
    def __init__(self, private: Path, clock=datetime.now):
        self.path = private / "news" / "timing.jsonl"
        self.clock = clock

    def stage(self, name: str):
        sw = self

        class _Ctx:
            def __enter__(self_inner):
                self_inner.t0 = sw.clock()
                return self_inner

            def __exit__(self_inner, *exc):
                t1 = sw.clock()
                self_inner.seconds = round((t1 - self_inner.t0).total_seconds(), 1)
                with sw.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"stage": name, "start": self_inner.t0.isoformat(timespec="seconds"), "end": t1.isoformat(timespec="seconds"),
                                        "seconds": round((t1 - self_inner.t0).total_seconds(), 1), "ok": exc[0] is None}, ensure_ascii=False) + "\n")
                return False
        return _Ctx()


# ---- polite fetcher ----------------------------------------------------------------------------------------------------------------------------
def urllib_transport(url: str, headers: dict, timeout: float = 20.0):
    """(status, bytes).  The only place that touches the network."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return e.code, b""


class Refused(Exception):
    pass


class Fetcher:
    def __init__(self, transport=urllib_transport, sleep=time.sleep, clock=time.monotonic):
        self.transport, self.sleep, self.clock = transport, sleep, clock
        self.last_host: dict[str, float] = {}
        self.last_any = -1e9
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _wait(self, host: str):
        now = self.clock()
        wait = max(self.last_host.get(host, -1e9) + HOST_GAPS.get(host, HOST_GAP) - now, self.last_any + ANY_GAP - now, 0)
        if wait > 0:
            self.sleep(wait)
        t = self.clock()
        self.last_host[host] = t
        self.last_any = t

    def allowed(self, url: str) -> bool:
        u = urllib.parse.urlsplit(url)
        base = f"{u.scheme}://{u.netloc}"
        if base not in self.robots:
            self._wait(u.netloc)
            status, body = self.transport(base + "/robots.txt", {"User-Agent": UA})
            rp = urllib.robotparser.RobotFileParser()
            if status == 200:
                rp.parse(body.decode("utf-8", "replace").splitlines())
                self.robots[base] = rp
            elif status in REFUSE_STATUS:
                rp.disallow_all = True                 # a refused robots.txt: treat the host as closed
                self.robots[base] = rp
            else:
                self.robots[base] = None               # no robots.txt (404 etc.): nothing forbids reading
        rp = self.robots[base]
        return True if rp is None else rp.can_fetch(UA, url) or rp.can_fetch("*", url)

    def get(self, url: str) -> bytes:
        if not self.allowed(url):
            raise Refused("robots.txt")
        self._wait(urllib.parse.urlsplit(url).netloc)
        status, body = self.transport(url, {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/html;q=0.8"})
        if status in REFUSE_STATUS:
            raise Refused(f"HTTP {status}")
        if status != 200:
            raise OSError(f"HTTP {status}")
        if len(body) > MAX_BYTES:
            raise OSError("response too large")
        return body


# ---- feed parsing --------------------------------------------------------------------------------------------------------------------------------
def parse_feed(data: bytes) -> list[dict]:
    """RSS 2.0 / RDF (RSS 1.0) / Atom -> [{"title", "date"}].  Only the title and the date are taken; DTDs and entities are refused (no XXE, no entity bombs)."""
    head = data[:2000].lower()
    if b"<!doctype" in head or b"<!entity" in data[:20000].lower():
        raise ValueError("feed with a DTD or entities is refused")
    root = ET.fromstring(data)
    out = []
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        d = {c.tag.split("}")[-1]: (c.text or "") for c in it}
        title = re.sub(r"\s+", " ", d.get("title", "")).strip()
        if title:
            out.append({"title": title, "date": (d.get("pubDate") or d.get("date") or d.get("updated") or d.get("published") or "").strip()})
    return out


# ---- classification (rules; today's counts) -----------------------------------------------------------------------------------------------------
# order matters: the first category whose word matches wins.  'candidate' categories can lead to a product kind.
CATEGORIES = [
    ("gadget_sale", False, "価格・割引率が主題(価格を書かない決まりと合わない)", [r"セールで\d+％オフ", r"％オフ", r"クーポン", r"還元", r"ポイント"]),
    ("disaster_weather", True, "", [r"台風", r"大雨", r"警報", r"備蓄", r"防災", r"地震", r"津波", r"停電", r"豪雨", r"大雪", r"寒波", r"噴火", r"避難", r"気温", r"傘", r"天気", r"雷雨", r"土砂", r"通信障害", r"システム障害", r"ライフライン"]),
    ("leak_security", True, "", [r"流出", r"漏えい", r"漏洩", r"漏れて", r"不正アクセス", r"脆弱性", r"ハッキング", r"サイバー", r"フィッシング", r"ダークウェブ", r"盗難", r"セキュリティ", r"乗っ取り", r"ランサム", r"設計上の不備", r"窃取", r"GMO.*会見", r"会見.*GMO", r"不正なユーザー"]),
    # consumer trouble (contracts, cancellation, labels, fees, procedures) is in scope since 2026-11-04; the party's own products are never placed
    ("consumer_trouble", True, "", [r"契約", r"解約", r"勧誘", r"トラブル", r"高額請求", r"返金", r"注意喚起", r"国民生活センター", r"消費者", r"表示", r"料金", r"手続き", r"制度", r"クーリング"]),
    ("health", False, "効能の断定・診断や治療の助言になりやすい", [r"病", r"医療", r"感染", r"症", r"がん", r"体臭", r"ダイエット", r"エボラ", r"健康", r"精子"]),
    ("incident", False, "被害を扱う話に商品を結びつけない", [r"死亡", r"重体", r"重傷", r"遺体", r"逮捕", r"摘発", r"事件", r"事故", r"容疑", r"爆弾", r"空爆", r"攻撃", r"監禁", r"運転見合わせ"]),
    ("politics_world_finance", False, "政治・国際・金融は扱わない", [r"選挙", r"大統領", r"首相", r"政権", r"与党", r"野党", r"民主", r"共和", r"トランプ", r"イスラエル", r"イラン", r"ウクライナ", r"ロシア", r"北朝鮮", r"中国",
                                                         r"東証", r"NY円", r"NY株", r"NYダウ", r"日経平均", r"為替", r"利上げ", r"株価", r"原油", r"首脳", r"外相", r"国会", r"献金", r"農相", r"自治体システム",
                                                         r"安保", r"ICC", r"表現の自由", r"協定", r"党大会", r"証券", r"ファイナンス", r"物品税", r"外交", r"デモ"]),
    ("sports_entertainment", False, "人名・作品名で売る商品は扱わない", [r"監督", r"選手", r"優勝", r"ドラマ", r"主演", r"映画", r"アニメ", r"MV", r"歌", r"結婚", r"将棋", r"竜王", r"野球", r"サッカー", r"ゴルフ", r"駅伝", r"欧州CL", r"ACL", r"阪神", r"巨人",
                                                                  r"Ｇリーグ", r"Gリーグ", r"F1", r"連覇", r"開幕戦", r"ブラッサム", r"アナ[、。]", r"アナウンサー", r"パワハラ発言", r"MLB", r"NBA", r"リベンジ"]),
    ("career_learning", True, "", [r"教員免許", r"資格", r"転職", r"中途採用", r"公務員志望", r"学び直し", r"リスキリング", r"採用", r"試験"]),
    ("product_news", True, "", [r"生産中止", r"再販", r"発売", r"特典", r"ワークマン", r"バッグ", r"バックパック", r"新モデル"]),
    ("life_food", True, "", [r"値上げ", r"もやし", r"カメムシ", r"家族じまい", r"セルフレジ", r"節約", r"食品", r"洗剤", r"収納", r"掃除", r"暖房", r"寒さ", r"電気代", r"光熱費", r"物価", r"建築費", r"家計", r"アレンジ", r"レシピ", r"ウナギ"]),
    ("it_company", False, "商品の種類が決まらない(企業・AI・決算の話)", [r"AI", r"決算", r"増収", r"買収", r"IPO", r"Windows", r"Apple", r"Google", r"Microsoft", r"アプリ", r"SaaS", r"業績", r"社長", r"人事", r"Engine", r"PHP", r"Xiaomi", r"ChatGPT",
                                                            r"ドコモ", r"オープンソース", r"人件費", r"iPhone", r"Anthropic"]),
]
CAT_LABEL = {"career_learning": "学び直し・仕事・資格", "product_news": "商品そのものの話題(生産中止・再販など)", "security_advisory": "技術的な注意喚起(JPCERT・IPA)", "consumer_trouble": "消費者トラブル・制度・手続き", "disaster_weather": "防災・気象", "leak_security": "情報漏えい・セキュリティ", "life_food": "暮らし・食", "gadget_sale": "ガジェットのセール(価格が主題)",
             "health": "健康・医療", "incident": "事件・事故", "politics_world_finance": "政治・国際・金融・市況", "sports_entertainment": "スポーツ・芸能・文化",
             "it_company": "IT・企業・AI", "other": "その他(商品に結びつかない)"}


def classify(title: str, source: str | None = None) -> str:
    if source in ("jpcert", "ipa"):
        return "security_advisory"      # the agencies' technical advisories: a weak link at best (update habits, second factor); counted apart from the leaks in the news
    for cat, _cand, _why, pats in CATEGORIES:
        if any(re.search(p, title) for p in pats):
            return cat
    return "other"


def is_candidate(cat: str) -> bool:
    return cat == "security_advisory" or any(c == cat and cand for c, cand, _w, _p in CATEGORIES)


def _grams(s: str, n: int = 3) -> set:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def cluster(titles: list[str], threshold: float = 0.4) -> list[list[str]]:
    """Headlines about the same event grouped together (3-gram overlap), so that one event counts once among the candidates."""
    groups: list[tuple[set, list[str]]] = []
    for t in titles:
        g = _grams(t)
        for gg, members in groups:
            if g and gg and len(g & gg) / len(g | gg) >= threshold:
                members.append(t)
                gg |= g
                break
        else:
            groups.append((set(g), [t]))
    return [m for _g, m in groups]


# ---- stages ------------------------------------------------------------------------------------------------------------------------------------
def load_refused(private: Path) -> dict:
    p = private / "news" / "refused.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def collect(private: Path, fetcher: Fetcher, day: str, sources: dict | None = None) -> dict:
    """Read the feeds and keep headline + date + source id only.  Returns counts (no headline text)."""
    sources = sources or SOURCES
    refused = load_refused(private)
    rows, status = [], {}
    for sid, (url, _kind) in sources.items():
        if sid in refused:
            status[sid] = "skipped (refused before)"
            continue
        try:
            items = parse_feed(fetcher.get(url))
            rows += [{"source": sid, "title": i["title"], "date": i["date"]} for i in items]
            status[sid] = f"ok {len(items)}"
        except Refused as e:
            refused[sid] = {"reason": str(e), "day": day}
            status[sid] = f"refused ({e}) - dropped"
        except (OSError, ET.ParseError, ValueError) as e:
            status[sid] = f"error {type(e).__name__}"
    seen, uniq = set(), []
    for r in rows:
        k = (r["title"],)
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    (private / "news" / "refused.json").write_text(json.dumps(refused, ensure_ascii=False, indent=1), encoding="utf-8")
    out = private / "news" / f"{day}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in uniq), encoding="utf-8")
    return {"headlines": len(uniq), "raw": len(rows), "status": status}


def make_report(private: Path, day: str) -> dict:
    """Counts per category, the candidate clusters (written to the private report only), and the reasons the others do not lead to a product."""
    rows = [json.loads(l) for l in (private / "news" / f"{day}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by: dict[str, list[str]] = {}
    for r in rows:
        by.setdefault(classify(r["title"], r.get("source")), []).append(r["title"])
    counts = {c: len(v) for c, v in by.items()}
    cand_titles = [t for c, v in by.items() if is_candidate(c) for t in v]
    clusters = cluster(cand_titles)
    why = {cat: w for cat, cand, w, _p in CATEGORIES if not cand}
    lines = [f"# {day} headlines: {len(rows)}", ""]
    for c, n in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {CAT_LABEL.get(c, c)}: {n}" + ("" if is_candidate(c) else f" (not used: {why.get(c, 'no product kind')})"))
    lines += ["", f"candidate headlines: {len(cand_titles)} in {len(clusters)} events", ""]
    for i, cl in enumerate(sorted(clusters, key=len, reverse=True), 1):
        lines.append(f"{i}. ({len(cl)}) " + " / ".join(cl[:3]))
    (private / "news" / f"{day}_report.md").write_text("\n".join(lines), encoding="utf-8")
    return {"headlines": len(rows), "counts": counts, "candidates": len(cand_titles), "events": len(clusters)}


# ---- primary facts ---------------------------------------------------------------------------------------------------------------------------------
def typhoon_facts(targets: list, specs: dict) -> list[dict]:
    """JMA typhoon data -> fill-in lines for the fact layer.  targets: targetTc.json; specs: {tropicalCyclone id: specifications.json}.  Only numbers and the JMA's own words."""
    out = []
    for t in targets:
        spec = specs.get(t["tropicalCyclone"])
        if not spec:
            continue
        title = next((e for e in spec if e.get("part") == "title"), None)
        parts = [e for e in spec if isinstance(e.get("part"), dict)]
        ana = next((e for e in parts if e["part"].get("en") == "Analysis"), None)
        if not title or not ana:
            continue
        j = datetime.fromisoformat(ana["validtime"]["JST"])
        no = int(title["typhoonNumber"][2:])
        lines = [f"気象庁は{j.month}月{j.day}日{j.hour}時の解析で、台風第{no}号({title['name']['jp']})を「{ana['intensity']}」勢力としている。"
                 f"中心気圧は{ana['pressure']}ヘクトパスカル、最大風速は{ana['maximumWind']['sustained']['m/s']}メートル。"]
        issue = datetime.fromisoformat(title["issue"]["JST"])
        for e in parts:
            if e["part"].get("en", "").startswith("Forecast") or e.get("advancedHours", 0) in (24, 48, 72):
                if e.get("advancedHours", 0) == 24 and e.get("validtime"):
                    v = datetime.fromisoformat(e["validtime"]["JST"])
                    where = e.get("location") or "北緯{:.1f}度、東経{:.1f}度".format(*e["position"]["deg"])
                    lines.append(f"気象庁の予報では、{v.month}月{v.day}日{v.hour}時に台風は{where}にある。")
        horizon = max([e.get("advancedHours", 0) for e in parts] or [0])
        lines.append(f"気象庁の予報は、{issue.month}月{issue.day}日の時点で{horizon}時間先まで出ている。")
        out.append({"number": no, "name": title["name"]["jp"], "issued": issue.isoformat(), "fact_lines": lines, "evidence_id": f"jma-typhoon-{title['typhoonNumber']}-{issue:%Y%m%d-%H%M}",
                    "ledger": ["気象庁", title["name"]["jp"], ana["intensity"], f"第{no}号"]})
    return out


def bousai_notices(html: str) -> list[dict]:
    """Titles (and the relative paths) of the notices on the Disaster Management Agency's top page: '令和8年11月2日 事前防災徹底のための緊急要請' etc.  Titles and dates only."""
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        d = re.search(r"令和(\d+)年(\d+)月(\d+)日|(\d+)月(\d+)日", text)
        if text and d and len(text) < 120:
            out.append({"title": text, "path": m.group(1)})
    return out


def article_skeleton(topic_id: str, title: str, fact_lines: list[str], ledger: list[str] | None = None) -> dict:
    """The fact layer filled with the primary facts; the view and preparation layers are left as marked gaps for the editor (the checks then refuse an article that still has a gap)."""
    return {"id": topic_id, "title": title, "updated": datetime.now().date().isoformat(), "ledger": list(ledger or ["気象庁"]), "sections": [
        {"layer": "fact", "heading": "確認できた事実", "bullets": fact_lines},
        {"layer": "opinion", "heading": "考察(編集部の見方)", "paras": ["〔書く: 場合分け・論点・時系列で整理する。事実と混ぜない。〕"]},
        {"layer": "prep", "heading": "備え・選び方", "paras": ["〔書く: 選ぶ基準と、商品カードの位置。〕"]},
        {"layer": "history", "heading": "更新履歴", "bullets": [f"{datetime.now().month}月{datetime.now().day}日 追記: 一次の情報を反映した。"]}]}


def has_gap(article: dict) -> bool:
    return any("〔書く" in t for s in article["sections"] for t in list(s.get("paras", [])) + list(s.get("bullets", [])))


def timing_summary(private: Path) -> str:
    """Stage names, start / end times and seconds only (safe for a public CI log): the 'one hour' target is measured from these."""
    p = private / "news" / "timing.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    lines = [f"{r['stage']}: {r['start']} -> {r['end']} = {r['seconds']}s" + ("" if r.get("ok", True) else " (failed)") for r in rows[-20:]]
    total = round(sum(r["seconds"] for r in rows[-20:]), 1)
    return "\n".join(lines + [f"total (last {len(rows[-20:])} stages): {total}s"])


# ---- command line ------------------------------------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="wadai news collector (read only)")
    ap.add_argument("cmd", choices=["collect", "report", "bundle", "timing"])
    ap.add_argument("--private", required=True, help="the private folder, e.g. ~/wadai-private (must be outside the repository)")
    ap.add_argument("--day", default=datetime.now().strftime("%Y%m%d"))
    a = ap.parse_args(argv)
    private = private_dir(a.private)
    sw = Stopwatch(private)
    if a.cmd == "timing":
        print(timing_summary(private))
        return 0
    if a.cmd == "collect":
        with sw.stage("collect") as st:
            r = collect(private, Fetcher(), a.day)
        print(f"headlines={r['headlines']} raw={r['raw']} seconds={st.seconds}")
        for sid, st in r["status"].items():
            print(f"  {sid}: {st}")
    elif a.cmd == "report":
        with sw.stage("report") as st:
            r = make_report(private, a.day)
        print(f"headlines={r['headlines']} candidates={r['candidates']} events={r['events']} seconds={st.seconds}")
        for c, n in sorted(r["counts"].items(), key=lambda x: -x[1]):
            print(f"  {CAT_LABEL.get(c, c)}: {n}")
    else:
        f = Fetcher()
        with sw.stage("bundle") as st:
            targets = json.loads(f.get(JMA_TARGETS))
            specs = {t["tropicalCyclone"]: json.loads(f.get(JMA_SPEC.format(tc=t["tropicalCyclone"]))) for t in targets}
            bundle = {"typhoons": typhoon_facts(targets, specs), "bousai": bousai_notices(f.get(BOUSAI_TOP).decode("utf-8", "replace"))}
            (private / "news" / f"{a.day}_bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"typhoons={len(bundle['typhoons'])} bousai_notices={len(bundle['bousai'])} seconds={st.seconds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
