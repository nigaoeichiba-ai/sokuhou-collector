"""Shared building blocks for the static sites (the layout, the standard pages and the files every site ships).

sites/saichin predates this and keeps its own copy of the same markup; new sites start here.  A `site` is a dict:
    nav        [(label, href, active_prefix)]            header links
    glyph      one character shown in the logo
    source_html  the credit line in the footer (HTML, may contain {source} which the caller replaces)
    assets     Path of the site's assets folder (style.css, app.js)
and `cfg` is the site's config.json (site_url, site_name, operator_name, contact_form_url, adsense_pub_id, ...).
"""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

# Xserver's default rules for a new domain: HTTP -> HTTPS redirect and the server cache switches.
# Replacing public_html drops the file, so every build ships it.
HTACCESS = (
    'SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=off\n'
    'SetEnvIf Request_URI ".*" Ngx_Cache_AllCacheMode\n'
    "AddType text/calendar .ics\n"
    "RewriteEngine on\n"
    "RewriteCond %{HTTPS} !on\n"
    "RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]\n"
)


class BuildError(Exception):
    pass


def esc(s) -> str:
    return html.escape(str(s), quote=True)


TEXT_ASSETS = {".css", ".js", ".svg", ".json", ".txt", ".html"}
ROOT_COPIES = {"favicon.ico", "apple-touch-icon.png"}


def asset_files(assets: Path) -> list[Path]:
    """Every file under the assets folder (sub-folders such as img/ included), in a stable order."""
    return sorted(p for p in assets.rglob("*") if p.is_file())


def asset_pages(assets: Path) -> dict:
    """Published path -> content: text for css/js/svg, bytes for images and everything else."""
    out = {}
    for p in asset_files(assets):
        rel = f"assets/{p.relative_to(assets).as_posix()}"
        out[rel] = p.read_text(encoding="utf-8") if p.suffix.lower() in TEXT_ASSETS else p.read_bytes()
        if p.parent == assets and p.name in ROOT_COPIES:  # browsers ask for these at the site root
            out[p.name] = out[rel]
    return out


def asset_version(assets: Path) -> str:
    """Short content hash of the assets; part of their URLs so browsers and server caches never serve stale ones."""
    h = hashlib.sha1()
    for a in asset_files(assets):
        h.update(a.relative_to(assets).as_posix().encode("utf-8"))
        h.update(a.read_bytes())
    return h.hexdigest()[:8]


def missing_config(cfg: dict) -> list[str]:
    """Release needs an operator name and at least one way to be contacted (a form URL and/or an email)."""
    missing = [] if cfg.get("operator_name") else ["operator_name"]
    if not (cfg.get("contact_form_url") or cfg.get("contact_email")):
        missing.append("contact_form_url or contact_email")
    return missing


def crumbs(items: list[tuple[str, str | None]]) -> str:
    out = [f'<a href="{href}">{esc(label)}</a>' if href else f"<span>{esc(label)}</span>" for label, href in items]
    return '<nav class="crumbs" aria-label="パンくず">' + " &gt; ".join(out) + "</nav>"


def nav_html(site: dict, path: str) -> str:
    out = []
    for label, href, prefix in site["nav"]:
        current = path == "/" if prefix == "/" else path.startswith(prefix)
        out.append(f'<a href="{href}"{" aria-current=\'page\'" if current else ""}>{label}</a>')
    return "".join(out)


def layout(site: dict, cfg: dict, preview: bool, *, path: str, title: str, description: str, body: str,
           scripts: bool = False, og_image: str | None = None, alternates: tuple[tuple[str, str], ...] = ()) -> str:
    base = cfg["site_url"].rstrip("/")
    name = esc(cfg["site_name"])
    robots = '<meta name="robots" content="noindex,nofollow">\n' if preview else ""
    banner = ('<div class="preview">プレビュー版です。運営者情報などが未設定のため、検索エンジンには公開されません。</div>\n'
              if preview else "")
    adsense = ""
    if cfg.get("adsense_pub_id"):
        pub = cfg["adsense_pub_id"].replace("ca-", "")
        adsense = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                   f'?client=ca-{esc(pub)}" crossorigin="anonymous"></script>\n')
    ver = asset_version(site["assets"])
    if og_image:
        og_tags = "".join(f"{line}\n" for line in (
            f'<meta property="og:image" content="{esc(base + og_image)}">',
            '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:image" content="{esc(base + og_image)}">'))
    else:
        og_tags = '<meta name="twitter:card" content="summary">\n'
    links = "".join(f'<link rel="alternate" type="application/atom+xml" title="{esc(t)}" href="{esc(h)}">\n'
                    for t, h in alternates)
    script = f'<script src="/assets/app.js?v={ver}" defer></script>\n' if scripts else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(base + path)}">
{robots}<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(base + path)}">
{og_tags}{links}<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/style.css?v={ver}">
{adsense}</head>
<body>
{banner}<header class="site"><div class="wrap">
<a class="brand" href="/"><span class="logo" aria-hidden="true">{site['glyph']}</span>{name}</a>
<nav aria-label="メイン">{nav_html(site, path)}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p class="src">{site['source_html']}</p>
<p class="legal"><a href="/about/">運営者情報</a><a href="/privacy/">プライバシーポリシー</a><a href="/contact/">お問い合わせ</a><span>&copy; {name}</span></p>
</div></footer>
{script}</body>
</html>
"""


def amazon_disclosure(cfg: dict) -> str:
    """Amazon Associates requires this sentence on a site that carries Amazon links."""
    if not cfg.get("amazon_tracking_id"):
        return ""
    name = cfg.get("amazon_disclosure_name") or cfg["site_name"]  # the site name, as on most sites (the account holder may be a person)
    return f"<p>Amazonのアソシエイトとして、{esc(name)}は適格販売により収入を得ています。</p>"


def contact_summary(cfg: dict) -> str:
    parts = []
    if cfg.get("contact_form_url"):
        parts.append('<a href="/contact/">お問い合わせフォーム</a>')
    if cfg.get("contact_email"):
        parts.append(esc(cfg["contact_email"]))
    return " / ".join(parts) or "(未設定)"


def legal_pages(site: dict, cfg: dict, preview: bool, *, purpose: str, sources_html: str, update_text: str,
                disclaimer_html: str, contact_notice: str, input_note: str = "", finish=lambda s: s) -> dict[str, str]:
    """about / privacy / contact / 404, with the site-specific sentences passed in."""
    name = cfg["site_name"]
    op = esc(cfg["operator_name"] or "(未設定)")

    def page(path, title, description, body):
        return finish(layout(site, cfg, preview, path=path, title=f"{title} | {name}", description=description, body=body))

    about = f"""<h1>運営者情報</h1>
<dl class="info">
<dt>サイト名</dt><dd>{esc(name)}</dd>
<dt>運営者</dt><dd>{op}</dd>
<dt>連絡先</dt><dd>{contact_summary(cfg)}</dd>
<dt>目的</dt><dd>{purpose}</dd>
<dt>情報の出典</dt><dd>{sources_html}</dd>
<dt>更新</dt><dd>{update_text}</dd>
</dl>
<h2>免責事項</h2>
{disclaimer_html}"""
    privacy = f"""<h1>プライバシーポリシー</h1>
<h2>取得する情報</h2>
<p>当サイトは、会員登録などの機能を持ちません。お問い合わせの際にいただいたお名前・メールアドレスなどは、返信のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。</p>
{input_note}<h2>アクセス解析</h2>
<p>現時点では、Google アナリティクスなどのアクセス解析ツールを使用していません。使用を始める場合は、このページでお知らせします。</p>
<h2>広告について</h2>
<p>当サイトは、第三者配信の広告サービス「Google AdSense」を利用する場合があります。広告配信事業者は、利用者の興味に応じた広告を表示するために、Cookie(クッキー)を使用することがあります。</p>
<p>Cookie を無効にする、または、パーソナライズ広告を無効にするには、<a href="https://adssettings.google.com/" rel="noopener" target="_blank">Google の広告設定</a>をご利用ください。第三者配信事業者による Cookie の使用を無効にするには、<a href="https://www.aboutads.info/choices/" rel="noopener" target="_blank">aboutads.info</a> もご利用いただけます。</p>
<p>広告の配信にあたり、お使いのブラウザから広告配信事業者へ、閲覧に関する情報が送信されることがあります。</p>
<h2>アフィリエイトについて</h2>
<p>当サイトには、商品やサービスの紹介リンク(アフィリエイトリンク)が含まれる場合があります。該当するページには、広告であることを明示します。リンク先で商品が購入されると、当サイトの運営者に報酬が支払われることがあります。</p>{amazon_disclosure(cfg)}
<h2>免責事項・著作権</h2>
<p>免責事項と情報の出典は、<a href="/about/">運営者情報</a>に記載しています。</p>
<h2>お問い合わせ</h2>
<p>このポリシーに関するお問い合わせは、{contact_summary(cfg)}からお願いします。</p>
<h2>改定</h2>
<p>このポリシーは、必要に応じて見直し、変更する場合があります。変更後の内容は、このページに掲載した時点から効力を持ちます。</p>"""
    form, mail = cfg.get("contact_form_url"), cfg.get("contact_email")
    links = []
    if form:
        links.append(f'<p><a class="btn" href="{esc(form)}" rel="noopener" target="_blank">お問い合わせフォームを開く</a></p>')
    if mail:
        links.append(f'<p>メール: <a href="mailto:{esc(mail)}">{esc(mail)}</a></p>')
    contact = f"""<h1>お問い合わせ</h1>
<p>データの誤りのご指摘、ご意見・ご要望は、次からお送りください。内容によっては、お返事に日数がかかることや、お返事できないことがあります。</p>
{chr(10).join(links) or "<p>(未設定)</p>"}
<p class="notice">{contact_notice}</p>"""
    nf = '<h1>ページが見つかりません</h1>\n<p><a href="/">トップページへ</a></p>'
    return {
        "about/index.html": page("/about/", "運営者情報", f"{name}の運営者情報、情報の出典、免責事項です。", about),
        "privacy/index.html": page("/privacy/", "プライバシーポリシー", f"{name}のプライバシーポリシーです。取得する情報、広告、Cookie の扱いについて説明します。", privacy),
        "contact/index.html": page("/contact/", "お問い合わせ", f"{name}へのお問い合わせ先です。", contact),
        "404.html": page("/404.html", "ページが見つかりません", "ページが見つかりません。", nf),
    }


def standard_files(pages: dict, cfg: dict, preview: bool, lastmod: str) -> dict:
    """sitemap.xml, robots.txt, ads.txt, .htaccess and the Search Console verification file."""
    base = cfg["site_url"].rstrip("/")
    urls = sorted({"/" + p[: -len("index.html")] for p in pages if p.endswith("index.html")}, key=lambda u: (u != "/", u))
    out: dict[str, str] = {
        "sitemap.xml": ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                        + "".join(f"<url><loc>{esc(base + u)}</loc><lastmod>{lastmod}</lastmod></url>\n" for u in urls)
                        + "</urlset>\n"),
        "robots.txt": "User-agent: *\nDisallow: /\n" if preview else f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n",
        ".htaccess": HTACCESS,
    }
    if cfg.get("adsense_pub_id"):
        pub = cfg["adsense_pub_id"].replace("ca-", "")
        out["ads.txt"] = f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n"
    verification = cfg.get("google_site_verification")
    if verification:
        if not re.fullmatch(r"google[0-9a-f]{16}\.html", verification):
            raise BuildError(f"google_site_verification must look like google<16 hex>.html, got {verification!r}")
        out[verification] = f"google-site-verification: {verification}\n"
    return out


def write_pages(pages: dict, out: Path) -> None:
    """Overwrite in place and delete only stale files: removing the whole folder fails on Windows when Dropbox or
    the indexer briefly holds a directory open."""
    for rel, content in pages.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8", newline="\n")
    if out.exists():
        for f in out.rglob("*"):
            if f.is_file() and f.relative_to(out).as_posix() not in pages:
                f.unlink()
