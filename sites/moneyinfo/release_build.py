"""Release/review output of the site (run through build.py). The local preview always stays noindex."""
import argparse
from html import escape, unescape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from PIL import Image, ImageOps
from case_articles import AVERAGE, CASES

ROOT = Path(__file__).resolve().parent
BASE = "https://kurashi-no-money.com/"
OPERATOR = "暮らしのマネー情報運営部"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


HTACCESS = (
    'SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=off\n'
    'SetEnvIf Request_URI ".*" Ngx_Cache_AllCacheMode\n'
    "RewriteEngine on\n"
    "RewriteCond %{HTTPS} !on\n"
    "RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]\n"
)
CONTACT_KINDS = ["記事の数字・内容の誤りのご指摘", "ご意見・ご要望", "広告・掲載に関するご連絡", "その他"]
SITE_NAME = "暮らしのマネー情報"
CONTACT_FORM_URL = BASE + "contact/"
RELEASE_TEXT = [
    ("現在は公開前のプレビューです。暮らしのマネー情報運営部が、記事と便利ツールを制作しています。",
     "暮らしのマネー情報運営部が、記事と便利ツールを制作しています。"),
    ("このプレビューにはアフィリエイトリンクや広告主への申込みリンクはありません。広告主・リンク先・掲載条件を確認するまで、架空の広告や申込みボタンは設けません。",
     "現在、このサイトには広告主への申込みリンクはありません。広告を掲載するときは、記事にPRと表示します。"),
    ("このプレビューの便利ツールは、入力内容をブラウザー内で計算します。入力した金額は外部へ送信せず、ブラウザーへの保存も行いません。アクセス解析や広告配信の外部スクリプトは使用していません。",
     "便利ツールは、入力内容をブラウザー内で計算します。入力した金額は外部へ送信せず、ブラウザーへの保存も行いません。アクセス解析や広告配信の外部スクリプトは使用していません。"),
    ("本公開時には、実際に導入するサービスと受付方法に合わせて、この方針を確認します。",
     "お問い合わせフォームに入力した内容(種類・本文・任意のメールアドレス・送信日時)は、お返事とサイトの改善のためだけに使い、第三者へ提供しません。"
     "迷惑な送信を防ぐため、送信元は日ごとに変わる識別値にして保存し、元の情報は残しません。サービスを新しく導入するときは、この方針を先に直します。"),
]


DESC_OVERRIDE = {
    "information": "暮らしのマネー情報の運営者、広告・PRの扱い、プライバシーポリシー、モデルケースと試算を読むときの注意点をまとめたページです。",
    "contact": "暮らしのマネー情報運営部へのお問い合わせは、フォームから受け付けています。記事の誤りのご指摘やご意見をお寄せください。",
    "events": "就職・結婚・出産・進学・住宅購入・介護・退職。人生のイベントごとに、必要なお金と準備の時期を整理して調べられます。",
    "guide": "勤務先の制度、口座の使い分け、公的保障、毎月の家計。暮らしのお金の基本を、テーマ別のガイドから調べられます。",
}


def breadcrumb(slug, title, canonical):
    trail = [("トップ", BASE)]
    if slug.startswith("basics-"):
        trail.append(("お金の基本", BASE + "guide.html"))
    elif slug == "tools":
        trail.append(("便利ツール", BASE + "tools-category.html"))
    trail.append((title, canonical))
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": url} for i, (name, url) in enumerate(trail, 1)]}


def own_contact_pages(output, template_html, head_extra):
    """The site's own form (the form of the other sites: contact/send.php, inbox outside the web root). Needs the sokuhou checkout for the receiver."""
    import importlib.util, os
    repo = Path(os.environ.get("SOKUHOU_REPO") or (ROOT.parents[1] if (ROOT.parents[1] / "sokuhou" / "contactform.py").exists() else "C:/work/sokuhou/newsite-scaffold/sokuhou-collector"))
    if not (repo / "sokuhou" / "contactform.py").exists():
        raise SystemExit("SOKUHOU_REPO に、sokuhou/contactform.py のあるチェックアウトを指定してください。")
    sys.path.insert(0, str(repo))
    spec = importlib.util.spec_from_file_location("_contactform", repo / "sokuhou" / "contactform.py")
    cf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cf)
    cfg = {"contact_kinds": CONTACT_KINDS, "site_name": SITE_NAME}
    form = cf.form_html(cfg, message_hint="記事の数字の誤り、ご意見など")
    form = form.replace("/privacy/", "/information.html#privacy").replace("https://…/gift/…/", "https://kurashi-no-money.com/…")
    form = form.replace("該当するページのアドレス(わかれば)", "該当するページのアドレス(わかれば)")
    def frame(title, main, desc):
        html = template_html
        html = re.sub(r"<main.*?</main>", lambda _: main, html, flags=re.S)
        html = re.sub(r"<title>.*?</title>", f"<title>{escape(title)}｜{SITE_NAME}</title>", html)
        html = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{escape(desc, quote=True)}">', html)
        html = re.sub(r'(href|src)="(?!https?:|/|#|data:|mailto:)', r'\1="/', html)
        return html.replace("</head>", head_extra + "</head>")
    folder = output / "contact"
    folder.mkdir()
    main = ('<main class="wrap page-intro" id="main"><h1>お問い合わせフォーム</h1>'
            '<p>記事の数字や内容の誤りのご指摘、ご意見、広告・掲載に関するご連絡を受け付けています。個別の家計や投資の相談にはお答えできません。</p>'
            + form + "</main>")
    (folder / "index.html").write_text(frame("お問い合わせフォーム", main, "暮らしのマネー情報運営部へのお問い合わせフォーム。記事の誤りのご指摘やご意見を受け付けています。"), encoding="utf-8")
    thanks = '<main class="wrap page-intro" id="main">' + cf.thanks_body(cfg) + "</main>"
    (folder / "thanks.html").write_text(frame("送信しました", thanks, "お問い合わせを受け付けました。"), encoding="utf-8")
    (folder / "send.php").write_text(cf.send_php(cfg), encoding="utf-8")


def build(output, contact_url, review, own_contact=False):
    if output.exists() and any(output.iterdir()):
        raise SystemExit("既存の中身を上書きしません。新しい出力先(または空のフォルダ)を指定してください。")
    if ROOT in output.parents or output == ROOT:
        raise SystemExit("出力先はこのプロジェクトのフォルダの外にしてください(生成元を壊さないため)。")
    if not review and not contact_url and not own_contact:
        raise SystemExit("お問い合わせの設定が必要です(--own-contact か --contact-url)。確認用には --review を指定できます。")
    if contact_url:
        parsed = urlparse(contact_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise SystemExit("確認済みのお問い合わせフォームのHTTPS URLを指定してください。")
    subprocess.run([sys.executable, str(ROOT / "generate.py")], check=True)
    source = ROOT / "site"
    output.mkdir(exist_ok=True)
    shutil.copytree(source / "assets", output / "assets")
    originals = {c["slug"]: c for c in (*CASES, AVERAGE)}
    og_dir = output / "assets" / "shares"
    og_dir.mkdir()
    artwork = {"home": "approved-home-pc", **{key: c.get("image", key) for key, c in originals.items()}}
    for key, asset in artwork.items():
        if key == "home":
            with Image.open(source / "assets" / "hero.webp") as hero:
                hero = hero.convert("RGBA")
                hero.thumbnail((1120, 590), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (1200, 630), (255, 250, 240))
                canvas.paste(hero, ((1200 - hero.width) // 2, (630 - hero.height) // 2), hero)
                canvas.save(og_dir / "home.jpg", quality=90)
            continue
        with Image.open(source / "assets" / f"{asset}.webp") as picture:
            ImageOps.fit(picture.convert("RGB"), (1200, 630),
                         method=Image.Resampling.LANCZOS).save(og_dir / f"{key}.jpg", quality=90)
    ET.register_namespace("", SITEMAP_NS)
    sitemap = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for page in sorted(source.iterdir()):
        if page.suffix in {".css", ".js", ".mjs"}:
            shutil.copy2(page, output / page.name)
        if page.suffix != ".html":
            continue
        slug = page.stem
        html = page.read_text(encoding="utf-8")
        title = unescape(re.search(r"<title>(.*?)</title>", html)[1])
        if slug in DESC_OVERRIDE:
            html = re.sub(r'<meta name="description" content="[^"]*">',
                          lambda _: f'<meta name="description" content="{escape(DESC_OVERRIDE[slug], quote=True)}">', html, count=1)
        desc = unescape(re.search(r'<meta name="description" content="([^"]*)">', html)[1])
        canonical = BASE if slug == "index" else BASE + page.name
        image = BASE + f"assets/shares/{slug if slug in originals else 'home'}.jpg"
        meta = {"og:title": title, "og:description": desc, "og:url": canonical,
                "og:image": image, "og:image:width": "1200", "og:image:height": "630",
                "og:type": "article" if slug in originals else "website", "og:locale": "ja_JP"}
        head = f'<link rel="canonical" href="{canonical}">'
        head += "".join(f'<meta property="{key}" content="{escape(value, quote=True)}">'
                        for key, value in meta.items())
        head += '<meta name="twitter:card" content="summary_large_image">'
        if slug in originals:
            c = originals[slug]
            article = {"@type": "Article", "headline": c["title"], "description": desc,
                       "mainEntityOfPage": canonical, "image": [image],
                       "author": {"@type": "Organization", "name": OPERATOR},
                       "publisher": {"@type": "Organization", "name": OPERATOR}}
            crumbs = {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": i, "name": name, "item": url}
                for i, (name, url) in enumerate(
                    (("トップ", BASE), ("モデルケース", BASE + "cases.html"), (c["title"], canonical)), 1
                )
            ]}
            data = json.dumps({"@context": "https://schema.org", "@graph": [article, crumbs]},
                              ensure_ascii=False).replace("<", "\\u003c")
            head += f'<script type="application/ld+json">{data}</script>'
        if slug not in originals:
            graph = []
            if slug == "index":
                graph = [{"@type": "WebSite", "name": SITE_NAME, "url": BASE, "inLanguage": "ja"},
                         {"@type": "Organization", "name": OPERATOR, "url": BASE}]
            else:
                page_title = title.split("｜")[0]
                graph = [breadcrumb(slug, page_title, canonical)]
            data = json.dumps({"@context": "https://schema.org", "@graph": graph},
                              ensure_ascii=False).replace("<", "\u003c")
            head += f'<script type="application/ld+json">{data}</script>'
        if not review:
            html = html.replace('<meta name="robots" content="noindex,nofollow">', "")
            html = html.replace("公開前のプレビュー", "暮らしのマネー情報")
            for old, new in RELEASE_TEXT:
                html = html.replace(old, new)
        if slug == "contact" and own_contact:
            html = re.sub(r"<p data-contact-preview>.*?</p>",
                          f'<p>お問い合わせは、フォームから受け付けています。</p><p><a href="{CONTACT_FORM_URL}">お問い合わせフォームを開く</a></p>', html)
        if slug == "contact" and contact_url:
            html = re.sub(r"<p data-contact-preview>.*?</p>",
                          lambda _: f'<p><a href="{escape(contact_url, quote=True)}">お問い合わせフォームを開く</a></p>', html)
        if slug == "contact" and own_contact:
            contact_template = html
        (output / page.name).write_text(html.replace("</head>", head + "</head>"), encoding="utf-8")
        node = ET.SubElement(sitemap, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(node, f"{{{SITEMAP_NS}}}loc").text = canonical
    if own_contact:
        own_contact_pages(output, contact_template, '<meta name="robots" content="noindex,follow">')
    ET.indent(sitemap)   # one <loc> per line: the deploy's live check counts them with grep -c
    ET.ElementTree(sitemap).write(output / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    robots = "User-agent: *\nDisallow: /\n" if review else f"User-agent: *\nAllow: /\nDisallow: /contact/\nSitemap: {BASE}sitemap.xml\n"
    (output / "robots.txt").write_text(robots, encoding="utf-8")
    # the deploy refuses a release without .htaccess (the same file as the other sites: server cache on, http -> https)
    (output / ".htaccess").write_text(HTACCESS, encoding="utf-8")
    print(f"{len(sitemap)} pages: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--contact-url")
    parser.add_argument("--own-contact", action="store_true", help="the site's own form (contact/send.php), as on the other sites")
    args = parser.parse_args()
    build(Path(args.output).resolve(), args.contact_url, args.review, args.own_contact)
