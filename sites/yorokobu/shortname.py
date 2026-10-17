"""The short name of a product card: what the product is, in a few words.

A shop's title is a string of search words ("お菓子 おしゃれ 高級 プレゼント 凛菓 ティラミス 詰め合わせ 抹茶スイーツ 個包装 …").  Nobody reads it; the card shows the name of the product:
the words that say WHICH product (the brand, the product, a size or a count), without the promotion, occasion, recipient and praise words a shop puts in for searches, and never cut in
the middle with "…".  Nothing is added: every word shown is a word of the shop's own title, in the shop's own spelling and order.

The shop's full title stays with the product (the title attribute of the card's links): the programmes' terms (Rakuten Web Service, Article 10 (1) (7)) allow product information to be
altered only in the ways the company determines, so the original is kept next to what the site shows.

Rules, in order:
  1. the dictionary content/product_names.json ({item code: name}) wins, for the few titles the rules cannot read;
  2. a bracketed promotion (【…】 ≪…≫ [...]) and decoration (＼ ／ ★ ◆ …) goes; HTML entities are read;
  3. a word that is a promotion, an occasion, a recipient, a praise or a season goes (STOP; "…祝い" and "…お返し" in any form; "20代"; a year; "1位"; a lone symbol or number);
  4. a word that is inside another kept word is dropped (the plainer one is replaced by the more specific one);
  5. the first words are kept while they fit BUDGET characters (at least two, if the title has them; never longer than HARD), in the title's order, then one size or count the title gives.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

BUDGET = 18                                    # the words of the name are kept while they fit (at least two words, if the title has them)
HARD = 38                                      # and never past this
DICTIONARY = Path(__file__).resolve().parent / "content" / "product_names.json"

# words that are about the search, not about the product
STOP = frozenset("""
ギフト プレゼント プレゼント用 誕生日 おしゃれ お洒落 オシャレ かわいい 可愛い カワイイ お祝い 御祝 祝い お返し 贈り物 贈答 贈答品 プチギフト ギフトセット お礼 挨拶 記念日 記念品 景品
高級 人気 送料無料 爆買 ブランド 実用的 女性 男性 彼氏 彼女 女友達 友達 友人 両親 父 母 妻 夫 大人 同僚 上司 先輩 後輩 義母 義父 祖父 祖母 おじいちゃん おばあちゃん
ラッピング 無料ラッピング ギフトラッピング 熨斗 のし 熨斗対応 即日発送 即納 メール便 ポイント消化 お得 セール 限定 新作 新生活 おすすめ オススメ 定番 話題 大人気 人気商品
今年 来年 冬 秋 春 夏 秋冬 春夏 季節 クリスマス ハロウィン お正月 お中元 お歳暮 バレンタイン ホワイトデー 母の日 父の日 敬老の日 卒業 入学 入園 卒園 就職 退職 結婚 出産 還暦 古希 喜寿 米寿
結婚記念日 結婚式 引き出物 引出物 香典返し 内祝い 内祝 出産内祝い 結婚内祝い 七五三 七五三内祝い 快気祝い 新築祝い 退職祝い 還暦祝い 結婚祝い 出産祝い 入学祝い 卒業祝い
子供会 まとめ買い 大量 業務用 イベント 粗品 ノベルティ 販促 配布 サプライズ 喜ばれる 贈る 贈りもの 贈りたい 母の日ギフト 父の日ギフト 誕生日プレゼント 誕生日ギフト
gws GWS | / ／ ・ ♪ ★ ☆ ◆ ■ ● ※ ！ ! ？ ? 〜 ~ 円 の と
楽天ランキング 楽天 ランキング 受賞 獲得 半額 早割 予約 翌日配送 最強翌日配送 送料込 税込 以下 以上 無料 最短 名入れ無料 名前入り 名入り 当日出荷 即日出荷 ご挨拶
新入学 新学期 入学準備 シンプル 軽量 コンパクト 大容量 大判 大風量 高品質 無地 日本製 本革 いい香り 厚手 暖かい 防寒 保温 面白 かっこいい 安い 格安 激安 ポイント 福袋 ばらまき
""".split())
SUFFIX_STOP = re.compile(r".*(祝い|祝|内祝い|内祝|お返し|返礼)$")
AGE = re.compile(r"^\d{1,2}代(?:男性|女性)?$|^20[2-3]\d(?:年)?$|^\d{1,2}歳(?:以上|から)?$|^\d+位(?:獲得|受賞)?$|^\d+[%％]?(?:OFF|オフ|off)$|^[0-9０-９]+月[0-9０-９]*日?まで$")
UNIT = re.compile(r"\d[\d,.]*\s*(?:個|枚|本|袋|箱|g|kg|ml|mL|L|cm|mm|m|cc|粒|包|杯|枚入|個入|本入|袋入|種|色|点|セット|入り|入|P|pcs|ｇ|ｍｌ|足|組|ヶ月|か月)")
SPEC_ONLY = re.compile(r"^[0-9０-９%％.\-+×xX/]+$")
GENERIC = frozenset("お菓子 スイーツ 洋菓子 和菓子 雑貨 グッズ 食品 飲料 ドリンク 小物 日用品 プチ 贈答用".split())
QUOTES = "\"“”「」『』"
LINKS = frozenset("& ＆ × ＋ +".split())
SPLIT = re.compile(r"[\s　|｜]+")
EDGE = "!！?？、。,，:：;；＼／\\|｜"
BRACKETS = re.compile(r"【[^】]*】|≪[^≫]*≫|《[^》]*》|\[[^\]]*\]|［[^］]*］|★[^★]*★|☆[^☆]*☆|◆[^◆]*◆|■[^■]*■")
DECOR = re.compile(r"[＼／♪★☆◆■●▼▲♡♥※{}｛｝]+")
PROMO_WORD = re.compile(r"特価|お買い得|[Pp]\d*倍|\d+倍|人気|おすすめ|オススメ|ランキング|限定|SALE|sale|セール|楽天スーパー|メッセージカード|包装|無料|のし|ラッピング|小分け|エントリー|買いまわり|買い回り|ポイント|スタート|クーポン|期間中|マラソン|割引|送料|ネコポス|ポスト投函|あす楽|即日|翌日|発送|レビュー|お買い物")
DATE_HEAD = re.compile(r"^\d+月\d+日(?:\d+時)?(?:スタート|まで|から)?[!！]*")
PAREN = re.compile(r"[（(]([^）)]*)[）)]")


def _paren(m: re.Match) -> str:
    """A bracketed note made only of search words ("(ギフト)") goes; a reading or a spec ("(ウェッジウッド)" "(S-BEO)") stays."""
    inner = [w for w in SPLIT.split(m.group(1)) if w]
    return " " if inner and all(w in STOP or _is_promo(w) for w in inner) else m.group(0)


def _tokens(name: str) -> list[str]:
    name = html.unescape(name)
    name = DECOR.sub(" ", BRACKETS.sub(" ", PAREN.sub(_paren, name)))
    out = []
    for t in SPLIT.split(name):
        t = DATE_HEAD.sub("", t.strip(EDGE)).strip(EDGE)
        if t:
            out.append(t)
    return out


def _is_promo(t: str) -> bool:
    if PROMO_WORD.search(t):
        return True
    return len(t) >= 5 and t[0] in QUOTES and t[-1] in QUOTES            # a tagline in quotation marks ("”かわいい手土産”")


def _drop(t: str) -> bool:
    if t in STOP or AGE.match(t) or SUFFIX_STOP.match(t) or _is_promo(t):
        return True
    if SPEC_ONLY.match(t) and not UNIT.search(t):
        return True
    return False


TAIL_WORDS = ("おしゃれ", "オシャレ", "かわいい", "可愛い", "プレゼント")


def _clean(t: str) -> str:
    """A word glued to the front by a search word ("誕生日プレゼント用…") loses that part; a title word never gets shorter otherwise."""
    for w in ("誕生日プレゼント", "プレゼント"):
        if t != w and t.startswith(w) and len(t) > len(w) + 1:
            t = t[len(w):]
    for w in TAIL_WORDS:                                                 # "350mLおしゃれ": the praise glued to the end
        if t.endswith(w) and len(t) > len(w) + 2:
            t = t[: -len(w)]
    return t


def load_dictionary(path: Path | None = None) -> dict:
    p = path or DICTIONARY
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d.get("names", d) if isinstance(d, dict) else {}


_DICT: dict | None = None


def short_name(name: str, code: str | None = None, budget: int = BUDGET, keep: list[str] | tuple[str, ...] | None = None) -> str:
    """The product's name in a few words (see the module text); the words come from the title only, in its order."""
    global _DICT
    if code:
        if _DICT is None:
            _DICT = load_dictionary()
        if code in _DICT:
            return _DICT[code]
    toks = [_clean(t) for t in _tokens(name)]
    kept: list[str] = []
    for t in toks:
        if not t or _drop(t):
            continue
        if t not in LINKS and any(t in k for k in kept):                 # a repeat, or a plainer word of one already kept
            continue
        kept = [k for k in kept if k in LINKS or k not in t] + [t]                     # a later, more specific word replaces the plainer one before it
    plain = [k for k in kept if k not in GENERIC]
    if len(plain) >= 2:                                                  # "お菓子 スイーツ" in front of a named product says nothing; kept only when nothing else is left
        kept = plain
    if not kept:
        kept = [t for t in toks if t][:3] or [name.strip()]
    merged: list[str] = []                                               # "DEAN" "&" "DELUCA" is one name
    for t in kept:
        if merged and merged[-1] in LINKS:
            merged[-2:] = [f"{merged[-2]} {merged[-1]} {t}"] if len(merged) >= 2 else [t]
        else:
            merged.append(t)
    kept = merged
    out, used = "", 0
    for t in kept:
        nxt = f"{out} {t}".strip()
        if used >= 2 and len(nxt) > budget:
            break
        if used >= 1 and len(nxt) > HARD:
            break
        out, used = nxt, used + 1
    for t in kept[used:]:                                                # a size or a count that the title gives, after the product
        if UNIT.search(t) and len(t) <= 12 and len(f"{out} {t}") <= HARD:
            out = f"{out} {t}"
            break
    if keep:                                                             # the words of the kind the card stands for (an idea's must-words) stay visible: the page's text proves the match
        want = [k for k in keep if k]
        if want and not any(k in out for k in want):
            for t in kept:
                if any(k in t for k in want):
                    out = f"{out} {t}"
                    break
    words = out.split()
    while words and words[-1] in LINKS:                                  # a joining symbol ("DEAN & DELUCA") stays inside a name, never at its end
        words.pop()
    return " ".join(words)
