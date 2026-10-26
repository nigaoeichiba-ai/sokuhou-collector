"""The words a product card shows in place of the shop's product name: what the product is, in one or two words of the site's own.

The shop's title is the shop's: the programme (Rakuten Web Service, terms Article 10 (1) (7) and the help page 「各APIで取得した情報はどのような目的で利用できますか?」) lets the site introduce
the product with a link to its page, and bars copying or altering the information for any other purpose.  So the card shows the picture (as the API gives it, with the affiliate link) and, in
plain letters, a short note of the site's own, not the name, shortened or not:

    {brand}の{kind}({a capacity or a count})      ロクシタンのハンドクリーム(10ml)    タンブラー(350ml)    焼き菓子(8種)    ハンドクリーム

  kind   the site's own word for the sort of product: the page's kind (a comparison's label) or an idea's must-word, or a word of the site's vocabulary (the comparison kinds, the ideas'
         must-words, EXTRA) that the title contains;
  brand  only a brand of the site's dictionary (content/brands.json: the brand and its spellings), written as the dictionary writes it;
  the number with its unit, if the title gives one (350ml, 8種, 20個入).
A product of which the site knows neither a kind nor a brand gets no note (the card is its picture and its buttons).  content/product_blurbs.json ({item code: note}) overrides one product.
No label ("商品名" and the like) goes with the note anywhere: it is a plain line of text, not a name.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"

# attributes the line may carry (a fixed vocabulary of the site's: the card says THAT the title mentions it, in the site's word)
FORMS = (("ペア", ("ペアグ", "ペアマ", "ペアタ", "ペアセット", "ペアギフト", "ペア ", "ペア　", "ペア・")), ("詰め合わせ", ("詰め合わせ", "詰合せ", "詰合わせ", "アソート")), ("個包装", ("個包装", "個別包装")), ("名入れ", ("名入れ", "名前入り", "名入り")))
CAPACITY = re.compile(r"(\d[\d,.]*)\s*(ml|mL|ML|L|ℓ|g|kg|ｇ|ｍｌ|cc)")
COUNT = re.compile(r"(\d[\d,]*)\s*(種類|種|個入り|個入|個|枚入り|枚入|枚|本入り|本入|本|袋入り|袋入|袋|点セット|点|足組|足|組|包|粒|玉|杯|色)")
SIZE = re.compile(r"(\d[\d,.]*)\s*(cm|mm)")

EXTRA = ("タオル ハンカチ マフラー ストール ブランケット ひざ掛け ルームシューズ スリッパ ソックス 靴下 エコバッグ トートバッグ 財布 キーケース ボールペン 万年筆 手帳 ノート 文房具 文具 ペンケース "
         "タンブラー マグカップ マグ グラス ペアグラス コップ 湯呑み 箸 皿 茶碗 ボトル 水筒 コーヒー 紅茶 日本茶 緑茶 ティーバッグ ドリップバッグ チョコレート チョコ クッキー 焼き菓子 バウムクーヘン ケーキ "
         "ゼリー プリン どら焼き 羊羹 せんべい 和菓子 洋菓子 お菓子 スイーツ ワイン 日本酒 ビール ウイスキー 焼酎 ジュース ハンドクリーム ボディクリーム 入浴剤 バスソルト アロマ アロマキャンドル キャンドル "
         "ディフューザー リードディフューザー ルームフレグランス ホットアイマスク アイマスク カタログギフト 写真立て フォトフレーム プリザーブドフラワー 花束 ぬいぐるみ おもちゃ 積み木 絵本 パズル "
         "ボードゲーム カードゲーム 貯金箱 イヤホン ワイヤレスイヤホン ヘッドホン 傘 日傘 折りたたみ傘 ポーチ バッグ リュック 時計 腕時計 マスク ガーゼ ミニタオル フェイスタオル バスタオル ハンドタオル タオルハンカチ "
         "ポチ袋 のし袋 色鉛筆 クレヨン 筆箱 おりがみ 折り紙 ドライヤー ヘアブラシ 化粧水 美容液 リップ 香水 石けん 洗剤 おむつケーキ スタイ ベビー服 ラトル 歯固め").split()
STOP_KIND = frozenset("ギフト プレゼント セット ペア ミニ ベビー キッズ ケース 小物 雑貨 グッズ アイテム".split())

_KINDS: list[str] | None = None
_KINDS2: list[str] | None = None
_BRANDS: list[tuple[str, str]] | None = None
_OVERRIDE: dict | None = None


def _load_vocab() -> None:
    """Tier 1: the comparison kinds' labels and words and EXTRA (curated).  Tier 2: the ideas' must-words (many, some loose): used only where tier 1 finds nothing in a title."""
    global _KINDS, _KINDS2
    one = {w for w in EXTRA if len(w) == 1}
    t1 = set(EXTRA)
    try:
        for g in json.loads((CONTENT / "compare.json").read_text(encoding="utf-8"))["groups"]:
            t1.update(g.get("words", []))
    except (OSError, ValueError, KeyError):
        pass
    t2 = set()
    try:
        for v in json.loads((CONTENT / "ideas.json").read_text(encoding="utf-8")).values():
            for idea in v.get("ideas", []):
                for w in idea.get("must") or []:
                    if isinstance(w, str) and len(w) >= 3:
                        t2.add(w)
    except (OSError, ValueError, AttributeError):
        pass

    def ok(w: str) -> bool:
        return (2 <= len(w) <= 12 or w in one) and w not in STOP_KIND and not re.search(r"\d", w)
    _KINDS = sorted((w for w in t1 if ok(w)), key=lambda w: (-len(w), w))
    _KINDS2 = sorted((w for w in t2 - t1 if ok(w)), key=lambda w: (-len(w), w))


def vocab() -> list[str]:
    if _KINDS is None:
        _load_vocab()
    return _KINDS or []


def vocab2() -> list[str]:
    if _KINDS2 is None:
        _load_vocab()
    return _KINDS2 or []


def brands() -> list[tuple[str, str]]:
    """[(spelling, the dictionary's brand name)], longest spelling first."""
    global _BRANDS
    if _BRANDS is None:
        out: list[tuple[str, str]] = []
        try:
            d = json.loads((CONTENT / "brands.json").read_text(encoding="utf-8")).get("brands", {})
            for name, spellings in d.items():
                for sp in {name, *spellings}:
                    out.append((sp, name))
        except (OSError, ValueError):
            pass
        _BRANDS = sorted(out, key=lambda x: -len(x[0]))
    return _BRANDS


def overrides() -> dict:
    global _OVERRIDE
    if _OVERRIDE is None:
        try:
            d = json.loads((CONTENT / "product_blurbs.json").read_text(encoding="utf-8"))
            _OVERRIDE = d.get("lines", d) if isinstance(d, dict) else {}
        except (OSError, ValueError):
            _OVERRIDE = {}
    return _OVERRIDE


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


KATAKANA = re.compile(r"[ァ-ヶー]")
KATAKANA_WORD = re.compile(r"[ァ-ヶー]+")
TAILS = ("セット", "ギフト", "ペア")                                   # what may follow a kind word that is written in katakana without making it another word
INSIDE = {"リップ": ("クリップ",), "コップ": ("スコップ",), "グラス": ("サングラス",)}      # a word that stands inside a longer, different one ("マネークリップ" is not "リップ")


def occurrences(t: str, w: str) -> list[int]:
    """Where the kind word `w` stands in the (normalised) title `t` AS A WORD: a katakana word that goes on into more katakana is another word ("マグネット" is not "マグ",
    "スタイル" is not "スタイ"), except for the few endings that only say a set or a pair, and the list INSIDE of known look-alikes ("クリップ" is not "リップ")."""
    wn = _norm(w)
    if not wn:
        return []
    out, i = [], t.find(wn)
    while i >= 0:
        end, ok = i + len(wn), True
        if KATAKANA_WORD.fullmatch(wn):
            if end < len(t) and KATAKANA.match(t[end]) and not any(t.startswith(a, end) for a in TAILS):
                ok = False
            for bad in INSIDE.get(wn, ()):
                if t.startswith(bad, i - bad.find(wn)):
                    ok = False
        if ok:
            out.append(i)
        i = t.find(wn, i + 1)
    return out


def _best(t: str, words: list[str]) -> str:
    hits = []
    for w in words:
        at = occurrences(t, w)
        if at:
            hits.append((w, at[0], len(at)))
    if not hits:
        return ""
    long = [h for h in hits if not any(h[0] != o[0] and h[0] in o[0] for o in hits)]                      # a word inside a longer hit goes
    long.sort(key=lambda h: (-h[2], h[1], -len(h[0])))                   # the word the title says most often, then the earliest
    return long[0][0]


def find_kind(title: str, kind: str | None = None, must: list[str] | None = None) -> str:
    """The site's word for the sort of product.  `kind`: the page's own word (a comparison's label): the product is on the page because it is of that kind, so the word is used as it is.
    `must`: an idea's words; a title that holds one of them is of that kind.  Otherwise: a word of the site's vocabulary that the title contains."""
    t = _norm(title)
    from sites.yorokobu import relevance                      # the same reading of the idea's word as the gate that let the product in: spaces and case ignored, a short katakana word only as a word
    if kind and (not must or any(w and relevance.word_positions(title, w) for w in must)):
        return kind
    if must and not kind:
        hit = [w for w in must if w and relevance.word_positions(title, w)]
        if hit:
            return max(hit, key=lambda w: (len(relevance.word_positions(title, w)), len(w)))
    return _best(t, vocab()) or _best(t, vocab2())


def find_brand(title: str) -> str:
    t = _norm(title).lower()
    for sp, name in brands():
        if _norm(sp).lower() in t:
            return name
    return ""


def specs(title: str) -> list[str]:
    t = _norm(title).replace(",", "")
    out = []
    m = CAPACITY.search(t)
    if m:
        out.append(f"{m.group(1)}{'ml' if m.group(2).lower() in ('ml', 'cc') else m.group(2)}")
    m = COUNT.search(t)
    if m:
        unit = {"個入り": "個入", "枚入り": "枚入", "本入り": "本入", "袋入り": "袋入", "種類": "種"}.get(m.group(2), m.group(2))
        out.append(f"{m.group(1)}{unit}")
    if not out:
        m = SIZE.search(t)
        if m:
            out.append(f"{m.group(1)}{m.group(2)}")
    return out[:2]


def form_of(title: str, kind: str) -> str:
    t = _norm(title)
    if "詰め合わせ" in kind:
        return ""
    for label, keys in FORMS:
        if label in kind:
            continue
        if any(k in t for k in keys):
            return label
    return ""


def blurb(title: str, code: str | None = None, kind: str | None = None, must: list[str] | None = None) -> str:
    """The line for one product ('' when the site knows neither a kind nor a brand)."""
    if code and code in overrides():
        return overrides()[code]
    k = find_kind(title, kind, must)
    b = find_brand(title)
    if k and b and b in k:
        k = ""
    if not k and not b:
        return ""
    base = f"{b}の{k}" if (b and k) else (k or f"{b}の品")
    attrs = specs(title)[:1]
    return base + (f"({'・'.join(attrs)})" if attrs else "")
