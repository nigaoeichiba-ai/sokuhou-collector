"""Rakuten Ichiba Item Search API (2026 version) client and the helpers every Rakuten-backed site needs.

The API needs an application ID and an access key (GitHub secrets RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY, never written
into the repository) and a Referer header naming a domain registered for the application.  It allows about one
request per second per application, so the client spaces its calls and retries a few times on 429 / 5xx.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
RANKING_URL = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
USER_AGENT = "sokuhou-collector/0.1 (+https://github.com/nigaoeichiba-ai/sokuhou-collector)"


class RakutenError(Exception):
    pass


Transport = Callable[[str, dict], bytes]


def _urllib_transport(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


@dataclass
class Client:
    app_id: str
    access_key: str
    referer: str
    affiliate_id: str | None = None
    min_interval: float = 1.1
    retries: int = 3
    transport: Transport = _urllib_transport
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    calls: int = field(default=0, init=False)
    _last: float | None = field(default=None, init=False, repr=False)

    def _wait(self) -> None:
        if self._last is not None:
            gap = self.min_interval - (self.clock() - self._last)
            if gap > 0:
                self.sleep(gap)
        self._last = self.clock()

    def search(self, **params) -> list[dict]:
        """One search.  Returns the raw item dicts (formatVersion 2: flat objects), [] when nothing matches."""
        return self._call(API_URL, params)

    def ranking(self, **params) -> list[dict]:
        """One page (30 places) of the Ichiba ranking: age=10..50 with sex=0/1 (together), or genreId alone, plus page=1..34.  Items carry `rank`."""
        return self._call(RANKING_URL, params)

    def _call(self, api_url: str, params: dict) -> list[dict]:
        query = {"applicationId": self.app_id, "accessKey": self.access_key, "format": "json", "formatVersion": 2,
                 **{k: v for k, v in params.items() if v is not None}}
        if self.affiliate_id:
            query.setdefault("affiliateId", self.affiliate_id)
        url = api_url + "?" + urllib.parse.urlencode(query)
        headers = {"Referer": self.referer, "Origin": self.referer.rstrip("/"), "User-Agent": USER_AGENT}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._wait()
            self.calls += 1
            try:
                body = self.transport(url, headers)
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else ""
                if e.code == 404 or (e.code == 400 and "not_found" in detail):
                    return []  # no item matches
                if e.code in (429, 500, 502, 503, 504):
                    last_error = e
                    self.sleep(2.0 * (attempt + 1))
                    continue
                raise RakutenError(f"HTTP {e.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = e
                self.sleep(2.0 * (attempt + 1))
        else:
            raise RakutenError(f"gave up after {self.retries} tries: {last_error}")
        data = json.loads(body.decode("utf-8"))
        return data.get("Items") or data.get("items") or []


def _first_image(item: dict) -> str:
    """The picture URL exactly as the API gave it (the first of `mediumImageUrls`; of `smallImageUrls` when there is no medium one).  It is never rewritten: the size on the page is the CSS's."""
    for key in ("mediumImageUrls", "smallImageUrls"):
        for entry in item.get(key) or []:
            url = entry.get("imageUrl") if isinstance(entry, dict) else entry
            if url:
                return url
    return ""


def page_url(item_url: str) -> str:
    """The Ichiba page of a product, for the places that need the page itself (the ♡ keeps it, the spec's link formula takes it as `pc`).  The API's `itemUrl` is sometimes already a redirect
    (hb.afl.rakuten.co.jp/hgc/<ID>/?pc=<the page>&...): then the page is its `pc` value, cut out and not changed.  Any other URL is returned as it is."""
    parts = urllib.parse.urlsplit(item_url)
    if parts.netloc == "hb.afl.rakuten.co.jp":
        pc = urllib.parse.parse_qs(parts.query).get("pc", [""])[0]
        if pc.startswith("https://"):
            return pc
    return item_url


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


_PROMO = [
    r"【[^】]*】", r"≪[^≫]*≫", r"《[^》]*》", r"★[^★]*★", r"◆[^◆]*◆", r"■[^■]*■", r"［[^］]*］", r"\[[^\]]*\]",
    r"\S*クーポン\S*", r"\S*\d+/\d+\S*", r"\S*ポイント\d*倍\S*", r"\S*\d+%OFF\S*", r"\S*OFF\S*", r"送料無料", r"あす楽\S*",
]


def clean_title(name: str) -> str:
    """Rakuten shop titles carry promotions (coupons, dates, point multiples) that go stale; drop them, keep the product words."""
    import re
    out = name
    for pat in _PROMO:
        out = re.sub(pat, " ", out)
    out = " ".join(out.split())
    return out if len(out) >= 8 else " ".join(name.split())


def _points(item: dict) -> dict:
    """The point multiplier a shop has put on an item, with the time it ends (the API leaves both out when there is none): {"point_rate": 5, "point_end": "2026-10-17 09:59"};
    nothing when the rate is 1 or the end is missing (a multiplier without an end is not shown as a campaign)."""
    rate = _num(item.get("pointRate"), 1)
    end = str(item.get("pointRateEndTime") or "").strip()
    if rate < 2 or not end:
        return {}
    return {"point_rate": int(rate) if float(rate).is_integer() else rate, "point_end": end}


def normalize(item: dict) -> dict | None:
    """The few fields the site needs; None when the item cannot be shown (no price, link or image)."""
    item = item.get("Item", item)  # formatVersion 1 wraps each item
    name = clean_title((item.get("itemName") or "").strip())
    url = item.get("itemUrl") or ""                                 # as the API gave it
    price = int(_num(item.get("itemPrice")))
    image = _first_image(item)
    if not (name and url.startswith("https://") and price > 0 and image):
        return None
    return {
        "code": item.get("itemCode") or url,
        "name": name,
        "price": price,
        "url": url,
        "image": image,
        "shop": (item.get("shopName") or "").strip(),
        "shop_code": item.get("shopCode") or "",
        "reviews": int(_num(item.get("reviewCount"))),
        "rating": round(_num(item.get("reviewAverage")), 2),
        "available": int(_num(item.get("availability"), 1)) == 1,
        "free_shipping": int(_num(item.get("postageFlag"), 1)) == 0,
        "gift": int(_num(item.get("giftFlag"))) == 1,
        "appoint": int(_num(item.get("appointDeliveryDateFlag"))) == 1,
        **_points(item),
    }


def search_url(keyword: str) -> str:
    """Rakuten Ichiba keyword search results page."""
    return "https://search.rakuten.co.jp/search/mall/" + urllib.parse.quote(keyword, safe="") + "/"


def affiliate_link(affiliate_id: str, tracking_id: str | None, target: str) -> str:
    """Affiliate redirect to a Rakuten Ichiba URL, with the site's tracking ID when it has one."""
    path = f"{affiliate_id}/{tracking_id}" if tracking_id else f"{affiliate_id}/"
    enc = urllib.parse.quote(target, safe="")
    return f"https://hb.afl.rakuten.co.jp/hgc/{path}?pc={enc}&m={enc}"
