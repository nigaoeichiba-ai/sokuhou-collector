"""みんなのイラスト (minna-no-illust.com): a free illustration site (commercial use allowed, no credit needed) with a card maker.

    python sites/minna/build.py [--release] [--out DIR]

Illustrations are AI-generated, picked and tidied by people; the site says so on every page.  Every illustration has a detail page with
PNG (transparent) and WebP downloads, a licence summary, usage ideas and ImageObject markup; the card maker (/tool/card/) runs in the browser.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sites.minna.catalog import CATEGORIES, build_catalog  # noqa: E402
from sites.yorokobu import content as gift_content  # noqa: E402
from sokuhou import contactform  # noqa: E402
from sokuhou.sitekit import BuildError, asset_pages, crumbs, esc, layout, legal_pages, missing_config, standard_files, write_pages  # noqa: E402

SITE = {
    "nav": [("イラスト", "/illust/", "/illust/"), ("カードをつくる", "/tool/card/", "/tool/"), ("リクエスト", "/request/", "/request/"), ("利用について", "/license/", "/license/")],
    "glyph": '<img src="/assets/img/logo-mark.webp" alt="" width="36" height="36">',
    "assets": HERE / "assets",
    "source_html": "イラストは、AIで生成し、人が選んで、整えています。",
}
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Mochiy+Pop+One'
         '&family=Zen+Maru+Gothic:wght@500;700;900&display=swap">\n<meta name="theme-color" content="#2fd09b">\n')
USES = {
    "expressions": ["LINEやSNSの返信に", "スライドの、ひとこと解説に", "ブログの、吹き出しの横に", "動画のサムネイルに"],
    "jobs": ["案内ページの、案内役として", "サービス紹介の、イメージキャラとして", "お問い合わせ窓口の、イラストに", "チラシの、おすすめコーナーに"],
    "seasons": ["季節のお知らせに", "年賀状・クリスマスカードに", "店頭のポップに", "学校・園の、おたよりに"],
    "event-icons": ["招待状や、案内状に", "イベントの、告知画像に", "ギフトページの、見出しに", "メッセージカードに"],
    "people-icons": ["自己紹介スライドに", "チームの、役割の紹介に", "アンケートや、診断の、選択肢に", "家族の、お知らせに"],
}


def page(cfg, preview, **kw):
    kw.setdefault("og_image", "/assets/img/og.webp")
    return layout(SITE, cfg, preview, scripts=True, head_extra=FONTS, **kw)


def png_bytes(webp: Path) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.open(webp).convert("RGBA").save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def thumb_bytes(webp: Path, width: int = 360) -> bytes:
    from PIL import Image
    im = Image.open(webp).convert("RGBA")
    if im.width > width:
        im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=88, method=4)
    return buf.getvalue()


def load_catalog() -> list[dict]:
    c = gift_content.load()
    items = build_catalog({o["slug"]: o["name"] for o in c["occasions"]}, {r["slug"]: r["name"] for r in c["recipients"]})
    from PIL import Image
    for it in items:
        src = HERE / "src" / f"{it['src']}.webp"
        if not src.exists():
            raise BuildError(f"missing source image {src}")
        it["path"] = src
        with Image.open(src) as im:
            it["w"], it["h"] = im.size
    return items


def card(it: dict) -> str:
    return (f'<li><a class="illust-card" href="/illust/{it["id"]}/"><span class="checker"><img src="/thumbs/{it["id"]}.webp" alt="{esc(it["title"])}" '
            f'width="{min(it["w"], 360)}" height="{round(it["h"] * min(it["w"], 360) / it["w"])}" loading="lazy"></span><b>{esc(it["title"])}</b></a></li>')


def grid(items: list[dict]) -> str:
    return '<ul class="illust-grid">' + "".join(card(i) for i in items) + "</ul>"


def share(cfg: dict, path: str, text: str) -> str:
    url = cfg["site_url"].rstrip("/") + path
    return (f'<div class="share"><span class="share-label">このイラストを、教える</span>'
            f'<a class="share-btn line" href="{esc("https://line.me/R/share?text=" + quote(text + chr(10) + url, safe=""))}" target="_blank" rel="noopener">LINEで送る</a>'
            f'<a class="share-btn x" href="{esc("https://twitter.com/intent/tweet?text=" + quote(text, safe="") + "&url=" + quote(url, safe=""))}" target="_blank" rel="noopener">Xで共有</a></div>')


def licence_box() -> str:
    return ('<aside class="licence-box"><b>ずっと無料・商用OK・クレジット不要</b><span>個人でも、会社でも、点数の制限なく使えます。'
            '加工(色や大きさを変える)もできます。くわしくは<a href="/license/">利用について</a>。</span></aside>')


def index_page(cfg: dict, preview: bool, items: list[dict]) -> str:
    cats = "".join(
        f'<li><a class="cat-card" href="/category/{slug}/"><span class="checker small"><img src="/thumbs/{next(i for i in items if i["category"] == slug)["id"]}.webp" alt="" '
        f'width="200" height="150" loading="lazy"></span><span><b>{esc(name)}</b><small>{sum(1 for i in items if i["category"] == slug)}点</small></span></a></li>'
        for slug, name, _ in CATEGORIES)
    body = f"""<section class="band mint dots hero"><div class="in"><div class="hero-text"><span class="sticker">ずっと無料・商用OK</span>
<h1><span class="nb">そのまま使える、</span><br><span class="nb"><em>やさしい</em>イラスト</span></h1>
<p class="lead">シマエナガを中心に、表情・衣装・行事・イベント・人物アイコンまで。ダウンロードして、すぐに使えます。クレジット表示は、いりません。</p>
<p class="hero-cta"><a class="btn big" href="/illust/">イラストを見る</a><a class="btn big btn-sub" href="/tool/card/">カードをつくる</a></p></div>
<div class="hero-art"><img class="pair" src="/assets/img/mascot-pair.webp" alt="赤と青のマフラーをしたシマエナガのふたり" width="1400" height="579"></div></div></section>
{licence_box()}
<section style="margin-top:44px"><div class="sec-head"><h2>カテゴリから<span class="scribble">さがす</span></h2></div><ul class="cat-grid">{cats}</ul></section>
<section style="margin-top:50px"><div class="sec-head"><h2>すべての<span class="scribble">イラスト</span></h2><p>気になるものを、クリック。</p></div>{grid(items)}</section>
<section class="band yellow dots scallop" style="margin-top:56px"><div class="in"><div class="sec-head"><h2>名前や、ひとことを入れて、<span class="scribble">カードにする</span></h2><p>誕生日、ありがとう、お祝いのカードを、その場でつくって、画像で保存できます。</p></div>
<p style="text-align:center"><a class="btn big" href="/tool/card/">カードをつくる</a></p></div></section>"""
    return page(cfg, preview, path="/", title=f"{cfg['site_name']} 商用OK・クレジット不要の、やさしいイラスト素材",
                description="シマエナガのイラスト(表情・衣装・季節の行事)と、イベント・人物のアイコン。個人も商用も、無料で使えます。名前入りのカードも、つくれます。", body=body)


def illust_hub(cfg: dict, preview: bool, items: list[dict]) -> str:
    chips = "".join(f'<a href="/category/{slug}/">{esc(name)}</a>' for slug, name, _ in CATEGORIES)
    body = f"""{crumbs([("トップ", "/"), ("イラスト", None)])}
<h1>イラスト一覧</h1><p class="lead">すべて無料、商用OK、クレジット不要です。</p><nav class="chips">{chips}</nav>{grid(items)}"""
    return page(cfg, preview, path="/illust/", title=f"イラスト一覧 | {cfg['site_name']}", description="しまエナガ、イベント、人物アイコンなど、すべてのイラストの一覧です。", body=body)


def category_page(cfg: dict, preview: bool, slug: str, name: str, desc: str, items: list[dict]) -> str:
    body = f"""{crumbs([("トップ", "/"), (name, None)])}
<h1>{esc(name)}</h1><p class="lead">{esc(desc)}</p>{licence_box()}{grid([i for i in items if i["category"] == slug])}"""
    return page(cfg, preview, path=f"/category/{slug}/", title=f"{name}のイラスト | {cfg['site_name']}", description=desc[:110], body=body)


def illust_page(cfg: dict, preview: bool, it: dict, items: list[dict]) -> str:
    base = cfg["site_url"].rstrip("/")
    cat_name = next(n for s, n, _ in CATEGORIES if s == it["category"])
    related = [i for i in items if i["category"] == it["category"] and i["id"] != it["id"]][:8]
    uses = "".join(f"<li>{esc(u)}</li>" for u in USES[it["category"]])
    tags = "".join(f'<li>{esc(t)}</li>' for t in it["tags"])
    ld = json.dumps({"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": f"{base}/files/{it['id']}.png", "name": it["title"],
                     "description": it["desc"], "license": f"{base}/license/", "acquireLicensePage": f"{base}/license/",
                     "creditText": cfg["site_name"], "creator": {"@type": "Organization", "name": cfg["operator_name"]}, "width": it["w"], "height": it["h"],
                     "encodingFormat": "image/png"}, ensure_ascii=False)
    body = f"""{crumbs([("トップ", "/"), (cat_name, f"/category/{it['category']}/"), (it["title"], None)])}
<div class="detail"><div class="preview"><div class="checker big" id="bgbox"><img src="/files/{it['id']}.png" alt="{esc(it['title'])}" width="{it['w']}" height="{it['h']}"></div>
<div class="bgsw" aria-label="背景の色を変えて見る"><button type="button" data-bg="" class="on">すかし</button><button type="button" data-bg="#ffffff">白</button><button type="button" data-bg="#ffc93c">黄</button><button type="button" data-bg="#2b1b14">黒</button></div></div>
<div class="info"><h1>{esc(it['title'])}</h1><p class="lead">{esc(it['desc'])}</p>
<p class="dl"><a class="btn big" href="/files/{it['id']}.png" download="{it['id']}.png">PNG(透明)をダウンロード</a>
<a class="btn btn-sub" href="/files/{it['id']}.webp" download="{it['id']}.webp">WebP</a></p>
<p class="meta">サイズ: {it['w']}×{it['h']}px(透明な背景)</p>{licence_box()}
<p class="ai-note">このイラストは、AIで生成し、人が選んで、整えたものです。</p></div></div>
<section><h2><span class="scribble">こんなふうに、使えます</span></h2><ul class="check">{uses}</ul></section>
<section><h2><span class="scribble">キーワード</span></h2><ul class="tagcloud">{tags}</ul></section>
{share(cfg, f"/illust/{it['id']}/", f"{it['title']}(無料・商用OKのイラスト)")}
<section style="margin-top:44px"><h2><span class="scribble">おなじカテゴリの、イラスト</span></h2>{grid(related)}</section>
<script type="application/ld+json">{ld}</script>"""
    return page(cfg, preview, path=f"/illust/{it['id']}/", title=f"{it['title']} 無料・商用OKのイラスト | {cfg['site_name']}", description=f"{it['desc']}無料・商用OK・クレジット不要。",
                body=body, og_image=f"/thumbs/{it['id']}.webp")


def license_page(cfg: dict, preview: bool) -> str:
    body = f"""{crumbs([("トップ", "/"), ("利用について", None)])}
<h1>利用について(ライセンス)</h1>
<p class="lead">{esc(cfg['site_name'])}のイラストは、<b>個人でも、会社でも、無料で、ご利用いただけます</b>。使う前の連絡や、クレジット表示は、いりません。</p>
<h2><span class="scribble">できること</span></h2><ul class="check"><li>商用利用(チラシ、商品の説明、広告、動画、書籍、アプリなど)</li><li>点数の制限なしで、何点でも使うこと</li>
<li>大きさ、色、向きを変えたり、文字や、ほかの画像と、組み合わせたりすること</li><li>SNSやLINEで、画像として、共有すること</li></ul>
<h2><span class="scribble">お願い</span></h2><ul class="warn"><li>イラストそのものを、素材集として、配布・販売することは、できません(加工して、ほかの作品に使うのは、問題ありません)。</li>
<li>イラストを、商標として登録したり、「自分のキャラクター」として、権利を主張したりすることは、ご遠慮ください。</li>
<li>人を、傷つける内容、法律や公序良俗に反する内容に、使うことは、できません。</li></ul>
<h2><span class="scribble">AIで作ったイラストについて</span></h2>
<p>このサイトのイラストは、<b>AIで生成し、人が選んで、整えたもの</b>です。AIで生成したものは、法律上、著作物として扱われない場合があるため、ここでは、「著作権が、当サイトに帰属する」とは、書かず、<b>利用の許諾</b>として、上の内容をお約束します。</p>
<p>既存のキャラクターや、実在の人物、特定の作家の画風を、まねる指示では、作っていません。万一、似ているというご指摘があれば、<a href="/contact/">お問い合わせ</a>ください。速やかに、確認して、必要な場合は、取り下げます。</p>
<h2><span class="scribble">保証について</span></h2>
<p>イラストの利用によって生じた問題について、当サイトは、責任を負いません。第三者の権利を、侵害しないことの、保証もできません。ご自身の判断で、ご利用ください。</p>"""
    return page(cfg, preview, path="/license/", title=f"利用について(ライセンス) 商用OK・クレジット不要 | {cfg['site_name']}",
                description="個人も商用も無料、クレジット表示も、点数の制限も、ありません。できること、お願い、AIで作ったイラストの扱いを、説明します。", body=body)


def request_page(cfg: dict, preview: bool) -> str:
    form = contactform.form_html(cfg, default_kind="イラストのリクエスト", message_hint="例: しまエナガが、お花見でお弁当を食べているイラスト。スライドの表紙に使いたいです。", page_hint=False)
    body = f"""{crumbs([("トップ", "/"), ("リクエスト", None)])}
<h1>こんなイラストが、ほしい</h1>
<p class="lead">「このキャラクターの、こんなポーズが、ほしい」「こんな場面の、人物イラストが、ほしい」というご希望を、お聞かせください。</p>
<p>いただいたご希望は、ほかの方にも、役に立つものを、選んで、順番に、イラストにして、公開します(個別のお返事や、納期のお約束は、できません)。</p>
<ul class="check"><li>どのキャラクターか(しまエナガ・人物など)</li><li>どんなポーズ・場面か</li><li>何に使いたいか(スライド・LINE・チラシなど)</li></ul>
{form}
<p class="notice">既存のキャラクターや、実在の人物、特定の作家の画風を、まねるご希望は、お受けできません。</p>"""
    return page(cfg, preview, path="/request/", title=f"イラストのリクエスト | {cfg['site_name']}", description="こんなイラストがほしい、というご希望を送れます。", body=body)


def tool_page(cfg: dict, preview: bool, items: list[dict]) -> str:
    chars = [{"id": i["id"], "title": i["title"], "src": f"/files/{i['id']}.png"} for i in items if i["category"] in ("expressions", "jobs", "seasons")]
    data = esc(json.dumps({"chars": chars}, ensure_ascii=False, separators=(",", ":")))
    opts = "".join(f'<option value="{c["id"]}">{esc(c["title"])}</option>' for c in chars)
    body = f"""{crumbs([("トップ", "/"), ("カードをつくる", None)])}
<h1>名前入りの、カードをつくる</h1><p class="lead">名前とひとことを入れて、シマエナガのカードを、画像で保存できます。入力した内容は、この端末の中だけで、使われます(送信されません)。</p>
<section id="card-app" class="card-app" data-json="{data}">
<div class="card-form"><label>カードの種類<select name="tpl"><option value="birthday">誕生日</option><option value="thanks">ありがとう</option><option value="congrats">おめでとう</option><option value="cheer">おうえん</option></select></label>
<label>あて名(だれに)<input type="text" name="to" maxlength="14" placeholder="例: ハナコさん"></label>
<label>ひとこと<textarea name="msg" maxlength="60" rows="3" placeholder="例: いつも ありがとう。今日は ゆっくり してね。"></textarea></label>
<label>名前(だれから)<input type="text" name="from" maxlength="14" placeholder="例: タロウ"></label>
<label>キャラクター<select name="char">{opts}</select></label>
<label>いろ<select name="color"><option value="#ffc93c">たまご色</option><option value="#ffd6e0">さくら色</option><option value="#d9f1ff">空色</option><option value="#d7f7ea">ミント色</option></select></label>
<p class="dl"><button type="button" class="btn big" data-save>画像として保存</button></p><p class="memo-note">スマホで、保存できないときは、下の画像を、長押ししてください。</p></div>
<div class="card-preview"><canvas width="1080" height="1350" aria-label="カードのプレビュー"></canvas><img class="card-img" alt="できあがったカード" hidden></div></section>
{licence_box()}"""
    return page(cfg, preview, path="/tool/card/", title=f"名前入りカードをつくる 無料・保存OK | {cfg['site_name']}",
                description="名前とひとことを入れて、シマエナガのカードを画像で保存。誕生日・ありがとう・おめでとう・おうえん。無料で、すぐにつくれます。", body=body)


def sitemap_images(cfg: dict, items: list[dict]) -> str:
    base = cfg["site_url"].rstrip("/")
    rows = "".join(f"<url><loc>{esc(base)}/illust/{i['id']}/</loc><image:image><image:loc>{esc(base)}/files/{i['id']}.png</image:loc></image:image></url>\n" for i in items)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
            + rows + "</urlset>\n")


def render_site(cfg: dict, out: Path, release: bool = False, today: date | None = None) -> list[str]:
    missing = missing_config(cfg)
    if release and missing:
        raise BuildError(f"release build refused: set {', '.join(missing)} in config.json")
    preview = bool(missing)
    today = today or date.today()
    items = load_catalog()
    pages: dict[str, str | bytes] = {"index.html": index_page(cfg, preview, items), "illust/index.html": illust_hub(cfg, preview, items),
                                     "license/index.html": license_page(cfg, preview), "request/index.html": request_page(cfg, preview),
                                     "tool/card/index.html": tool_page(cfg, preview, items)}
    for slug, name, desc in CATEGORIES:
        pages[f"category/{slug}/index.html"] = category_page(cfg, preview, slug, name, desc, items)
    for it in items:
        pages[f"illust/{it['id']}/index.html"] = illust_page(cfg, preview, it, items)
        pages[f"files/{it['id']}.png"] = png_bytes(it["path"])
        pages[f"files/{it['id']}.webp"] = it["path"].read_bytes()
        pages[f"thumbs/{it['id']}.webp"] = thumb_bytes(it["path"])
    pages.update(legal_pages(
        SITE, cfg, preview,
        purpose="個人でも商用でも、無料で、使えるイラストを、公開し、名前入りのカードを、かんたんにつくれるようにすること。",
        sources_html="イラストは、AIで生成し、人が選んで、整えたものです。キャラクターは、当サイトのオリジナルです。",
        update_text="イラストは、順次、追加します。",
        disclaimer_html=("<p>イラストの利用によって生じた問題について、当サイトは責任を負いません。ご利用条件は、<a href=\"/license/\">利用について</a>をご覧ください。</p>"
                         "<p>既存のキャラクター・実在の人物・特定の作家の画風を、まねる指示では、作っていません。似ているというご指摘があれば、お問い合わせください。</p>"),
        contact_notice="リクエストは、お約束のお返事や、納期を、お約束するものではありません。",
        input_note="<p>カードをつくる機能に入力した内容は、この端末のブラウザの中だけで使われ、当サイトには、送信されません。</p>"))
    pages.update(standard_files(pages, cfg, preview, today.isoformat()))
    pages["sitemap-images.xml"] = sitemap_images(cfg, items)
    if not preview:
        pages["robots.txt"] = pages["robots.txt"] + f"Sitemap: {cfg['site_url'].rstrip('/')}/sitemap-images.xml\n"
    pages.update(asset_pages(HERE / "assets"))
    write_pages(pages, out)
    return sorted(pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default=str(HERE / "dist"))
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    try:
        files = render_site(cfg, Path(a.out), release=a.release)
    except BuildError as e:
        sys.exit(str(e))
    print(f"built {len(files)} files into {a.out}")


if __name__ == "__main__":
    main()
