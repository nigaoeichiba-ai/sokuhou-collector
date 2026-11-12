"""2026-11-13: add a short, natural 'shopping search' section at the end of articles whose topic has something to buy.
Only search-page links (Rakuten hb.afl search / Amazon s?k&tag), never mall product names/prices/images.  Re-runnable."""
import json
from pathlib import Path
from urllib.parse import quote

CONTENT = Path(__file__).resolve().parents[1] / "content"
RID = "583f273a.77c989b6.583f273b.0a6a5fff"
REL = 'rel="nofollow sponsored noopener" target="_blank"'
MARK = "探すなら"


def rakuten(kw):
    inner = quote("https://search.rakuten.co.jp/search/mall/" + quote(kw) + "/", safe="")
    return f'<a href="https://hb.afl.rakuten.co.jp/hgc/{RID}/?pc={inner}" {REL}>楽天市場で「{kw}」を探す</a>（PR）'


def amazon(kw):
    return f'<a href="https://www.amazon.co.jp/s?k={quote(kw)}&amp;tag=amazonmacs-22" {REL}>Amazonで「{kw}」を探す</a>（PR）'


def block(kws):
    lis = lambda f: "<ul>" + "".join(f"<li>{f(k)}</li>" for k in kws) + "</ul>"
    return "<p>楽天市場の検索ページ</p>" + lis(rakuten) + "<p>Amazonの検索ページ</p>" + lis(amazon)


ITEMS = {
    "bousai": ("防災グッズを探すなら", "チェックリストの品は、検索ページから探せます。", ["防災セット", "防災用 懐中電灯", "防災用 モバイルバッテリー", "携帯トイレ 防災", "保存水 備蓄", "非常食 5年保存"]),
    "bousai-light": ("防災用のライトを探すなら", "ライトは、検索ページで明るさや点灯時間を見比べられます。", ["防災用 懐中電灯", "LED ヘッドライト 防災", "乾電池 単3"]),
    "bousai-denchi-juden": ("電池と充電の備えを探すなら", "モバイルバッテリーと電池は、検索ページで容量や本数を見比べられます。", ["防災用 モバイルバッテリー", "手回し充電 ラジオ ライト", "乾電池 単3"]),
    "bousai-keitai-toilet": ("携帯トイレを探すなら", "携帯トイレは、検索ページで回数分のセットを探せます。", ["携帯トイレ 防災", "携帯トイレ 凝固剤 50回"]),
    "bousai-mizu-shokuryo": ("保存水と非常食を探すなら", "保存水と非常食は、検索ページで保存期間や量を見比べられます。", ["保存水 備蓄", "非常食 5年保存", "アルファ米 非常食"]),
    "trend-fire-alarm": ("火災警報器を探すなら", "交換や買い足しの前に、検索ページで型と対応年数を見比べられます。", ["住宅用火災警報器", "住宅用火災警報器 10年"]),
    "trend-fire-prevention-week": ("火の元の備えを探すなら", "火の元まわりの備えは、検索ページから探せます。", ["住宅用火災警報器", "住宅用消火器"]),
    "trend-typhoon32": ("停電や断水の備えを探すなら", "停電や断水への備えは、検索ページから探せます。", ["防災用 懐中電灯", "保存水 備蓄"]),
    "trend-humidifier-care": ("加湿器まわりの用品を探すなら", "加湿器本体やフィルターは、検索ページで型番から探せます。", ["加湿器", "加湿器 フィルター"]),
    "trend-rice-price": ("お米を探すなら", "お米は、検索ページで容量や産地ごとに探せます。", ["米 5kg"]),
    "trend-vegetable-price": ("野菜を探すなら", "野菜は、検索ページで宅配のセットも探せます。", ["野菜 詰め合わせ セット"]),
    "trend-engel-coefficient": ("家計の記録を始めるなら", "食費の割合を自分で確かめるなら、家計簿から始められます。", ["家計簿"]),
    "trend-crab-phone-call": ("迷惑電話の対策を探すなら", "電話機の機能での対策は、検索ページから探せます。", ["迷惑電話防止 電話機"]),
    "trend-blackfriday-price": ("セールの検索ページを見るなら", "気になる品の通常価格を記録したら、検索ページから探せます。", ["ブラックフライデー"]),
}
# nengajo-print: the A8 link already used in nengajo-hayawari is added by hand below (provided tag, unchanged)
ITEMS["trend-nengajo-print"] = ("年賀状の印刷と用品を探すなら", "年賀状の印刷や用品は、検索ページから探せます。", ["年賀状 印刷", "年賀状 プリンター インク"])


def main():
    for slug, (h2, intro, kws) in ITEMS.items():
        f = CONTENT / f"{slug}.json"
        raw = f.read_bytes().decode("utf-8")
        nl = chr(13) + chr(10) if chr(13) in raw else chr(10)
        d = json.loads(raw)
        line2 = raw.split(chr(10))[1]
        ind = len(line2) - len(line2.lstrip(chr(32)))
        if any(s.get("h2", "").endswith(MARK) for s in d["sections"]):
            continue
        d["sections"].append({"h2": h2, "paras": [intro]})
        d["sections"].append({"html": block(kws)})
        out = json.dumps(d, ensure_ascii=False, indent=ind).replace(chr(10), nl) + (nl if raw.endswith(chr(10)) else "")
        f.write_bytes(out.encode("utf-8"))
        print("added", slug)


if __name__ == "__main__":
    main()
