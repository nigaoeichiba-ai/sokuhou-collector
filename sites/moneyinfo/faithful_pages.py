"""採用した画像のイラスト領域を再利用し、文字と操作をHTMLで再現する。"""
from pathlib import Path
import re
from html import escape

ROOT = Path(__file__).resolve().parent / 'site'

def art(box, cls='', source='home-pc', alt=''):
    x,y,w,h = box
    full = (724,2172) if 'mobile' in source else (1024,1536)
    aria = f'role="img" aria-label="{escape(alt,quote=True)}"' if alt else 'aria-hidden="true"'
    return f'<svg class="art {cls}" viewBox="{x} {y} {w} {h}" preserveAspectRatio="xMidYMid slice" {aria} focusable="false"><image href="assets/approved-{source}.webp" width="{full[0]}" height="{full[1]}"/></svg>'

def hero_art(mobile=False):
    if mobile:
        return '<svg class="hero-original hero-original-mobile" viewBox="0 64 724 426" aria-hidden="true" focusable="false"><defs><clipPath id="hero-mobile-cut"><path d="M470 125H724V490H0V300H300V270H450V220H470Z"/></clipPath></defs><image href="assets/approved-home-mobile.webp" width="724" height="2172" clip-path="url(#hero-mobile-cut)"/></svg>'
    return '<svg class="hero-original hero-original-pc" viewBox="0 74 1024 346" aria-hidden="true" focusable="false"><defs><clipPath id="hero-pc-cut"><path d="M610 74H1024V420H0V314H530V250H610Z"/></clipPath></defs><image href="assets/approved-home-pc.webp" width="1024" height="1536" clip-path="url(#hero-pc-cut)"/></svg>'

def care_icon():
    return '<img class="painted-icon care-symbol" src="assets/icons/care.webp" width="128" height="128" alt="">'

def arrow(): return '<svg class="chevron" aria-hidden="true"><use href="#i-arrow"/></svg>'
def icon(name):
    assets={'work':'work','rings':'marriage','home':'housing','coins':'basics-savings','shield':'basics-protection','wallet':'basics-household','payslip':'basics-work'}
    if name in assets:
        return f'<img class="painted-icon" src="assets/icons/{assets[name]}.webp" width="128" height="128" alt="">'
    return f'<svg aria-hidden="true"><use href="#i-{name}"/></svg>'
def heading(title, lead=''):
    return f'<div class="section-heading"><h2>{title}</h2>'+(f'<p>{lead}</p>' if lead else '')+'</div>'
def button(url,label,blue=False):
    return f'<a class="button {"button-blue" if blue else ""}" href="{url}">{label}{arrow()}</a>'

EVENTS = [
 ('work','就職・転職','初任給までの生活費',(18,566,145,108)),
 ('marriage','結婚・新生活','式と新居の支払い',(170,566,134,108)),
 ('birth','出産・子育て','育休中の家計',(313,566,135,108)),
 ('education','進学・教育','入学前の納付',(456,566,132,108)),
 ('housing','住まい・車','頭金と維持費',(594,566,128,108)),
 ('care','親の介護','介護費と休業',(727,566,134,108)),
 ('retirement','退職・老後','年金までの生活費',(866,566,146,108)),
]

def home():
    events=''.join(f'<a class="event-link" href="events.html?event={key}">{art(box,"event-art")}<span class="event-copy"><strong>{name}</strong><small>{lead}</small></span>{arrow()}</a>' for key,name,lead,box in EVENTS)
    from case_articles import CASES
    # every model case is on the top page (nine cards: three rows of three); a new case is added to CASES and shows here
    HOME_CASES = [c for c in CASES if c.get('consult')] + [c for c in CASES if not c.get('consult')]
    cases = "".join(
        f'<a class="case-item" href="{case["slug"]}.html">'
        f'<img class="case-picture case-picture-raster" src="assets/{case.get("image", case["slug"])}.webp" width="1200" height="600" loading="lazy" alt="">'
        f'<div class="case-copy"><span class="tag">{escape(case["tag"])}</span><h3>{escape(case["title"])}</h3></div>{arrow()}</a>'
        for case in HOME_CASES
    )
    tools=''
    for url,box,title,lead in [
      ('savings',(8,1058,117,104),'毎月の準備額を計算','目標額・期限・準備済み資金から逆算'),
      ('annual',(310,1058,100,104),'年ごとの積立計画表','積立と支出の予定を年ごとに確認'),
      ('deposit',(611,1076,67,84),'預金の利息を比較','優遇期間と手数料も含めて確認')]:
        tools+=f'<a class="tool-item" href="tools.html#{url}">{art(box,"tool-art")}<span><h3>{title}</h3><p>{lead}</p></span>{arrow()}</a>'
    return f'''<main id="main" class="home-page"><section class="hero"><div class="hero-canvas">
{hero_art()}{hero_art(True)}<div class="hero-copy"><h1><span class="hero-line">人生に必要な<span class="money-word">お金</span>の知識、</span><span class="hero-line">もっと深く<wbr><span class="hero-phrase">知っておきませんか。</span></span></h1><p>必要なお金を把握できれば、暮らしに余裕が生まれます。</p></div><div class="hero-actions">{button('#events','人生のイベントから探す')}{button('#cases','モデルケースから探す',True)}</div></div>
<nav class="quick-links wrap" aria-label="よく調べる人生のイベント"><a href="events.html?event=work">{icon('work')}就職・転職</a><a href="events.html?event=marriage">{icon('rings')}結婚・子育て</a><a href="events.html?event=housing">{icon('home')}住まい</a><a href="events.html?event=care">{care_icon()}介護・老後</a></nav></section>
<section class="section event-section" id="events"><div class="wrap">{heading('人生のイベントから、お金を調べる','費用だけでなく、支払う時期と準備することまで。')}<div class="event-grid">{events}</div></div></section>
<section class="section case-section" id="cases"><div class="wrap">{heading('自分に近いモデルケースから','モデルケースは架空の例です。')}<div class="case-grid">{cases}</div></div></section>
<section class="section tools-section" id="tools"><div class="wrap">{heading('便利ツールで、準備する金額を具体的に','必要な金額を、いつから分けて準備するか考えましょう。')}<div class="tools-overview"><div class="tool-grid">{tools}</div>{button('tools.html','便利ツールを見る',True)}</div></div></section>
<section class="section basics-section" id="basics"><div class="wrap">{heading('お金の基本を知る','仕組みを理解して選択肢を考える。')}<div class="basic-grid"><a class="basic-link" href="guide.html#work">{icon('book')}<span>勤務先の制度・税・<br>社会保険</span>{arrow()}</a><a class="basic-link" href="guide.html#savings">{icon('coins')}<span>貯蓄・口座・<br>資産形成</span>{arrow()}</a><a class="basic-link" href="guide.html#protection">{icon('shield')}<span>公的保障と<br>民間保険</span>{arrow()}</a><a class="basic-link" href="guide.html#household">{icon('wallet')}<span>日常の家計・<br>支払い</span>{arrow()}</a></div></div></section>
<section class="section reading-section"><div class="wrap">{heading('まず読んでおきたい記事')}<ul class="news-list"><li><a href="basics-savings.html">{icon('coins')}<span>使う時期から考える、貯蓄と口座の基本</span>{arrow()}</a></li></ul></div></section>{art((790,1325,234,122),"home-flowers")}</main>'''

def article():
    return f'''<main class="wrap article-page" id="main"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><a href="events.html?event=housing">住まい・車</a><span aria-hidden="true">›</span><span>モデルケース</span></nav><div class="article-layout"><article class="article-main"><span class="tag article-tag">モデルケース</span><h1 class="article-title"><span class="article-title-start">共働き世帯の</span><span class="article-title-end"><span class="money-word">住宅資金</span>と家計の計画</span></h1><p class="article-deck">購入までの準備と、購入後に残すお金を分けて考える。</p>
<div class="article-hero">{art((28,230,740,244),'article-hero-pc','article-pc','家のテーブルで住宅資金の予定を相談する二人')}{art((74,354,577,225),'article-hero-mobile','article-mobile','家のテーブルで住宅資金の予定を相談する二人')}</div>
<section class="key-points" aria-labelledby="key-heading"><h2 id="key-heading">{care_icon()}<span>この記事の要点</span></h2><ul><li>購入時の費用とその後の生活費を分ける</li><li>支払いと入金の時期から必要な手元資金を考える</li><li>期限までの準備額と使える制度を確認する</li></ul></section>
<nav class="toc" aria-labelledby="toc-heading"><h2 id="toc-heading">{icon('book')}目次</h2><ol><li><a href="#conditions">モデルケースの条件</a></li><li><a href="#costs">購入にかかる費用と内訳</a></li><li><a href="#timing">支払いと入金の予定</a></li><li><a href="#monthly">毎月の準備額を考える</a></li><li><a href="#next">利用できる制度と次の行動</a></li></ol></nav>
<section class="article-section illustrated-section" id="conditions"><div><h2>モデルケースの条件</h2><ul class="attributes"><li>共働き</li><li>賃貸</li><li>住宅購入を検討</li></ul><p>架空の条件で組み立てたモデルケースです。</p></div>{art((465,674,301,116),'section-art','article-pc')}</section>
<section class="article-section" id="costs"><h2>購入にかかる費用と内訳</h2><p>物件の代金だけでなく、諸費用と生活費も分けて準備します。</p><div class="cost-layout"><div class="table-scroll tablewrap" role="region" aria-label="購入にかかる費用の内訳" tabindex="0"><table><caption class="sr-only">金額確認前の費用整理表</caption><thead><tr><th scope="col">費目</th><th scope="col">準備する時期</th><th scope="col">金額</th></tr></thead><tbody><tr><th scope="row">頭金</th><td>契約条件を確認</td><td>確認後に表示</td></tr><tr><th scope="row">諸費用</th><td>支払先ごとに確認</td><td>確認後に表示</td></tr><tr><th scope="row">購入後の生活費</th><td>入居後も確保</td><td>確認後に表示</td></tr></tbody></table></div>{art((599,823,168,131),'section-art','article-pc')}</div></section>
<section class="article-section" id="timing"><h2>支払いと入金の予定</h2><p>支払いが先になる期間には、手元の資金が必要です。</p><div class="timing-layout"><ol class="timeline"><li>契約<span></span></li><li>引越し<span></span></li><li>入居後<span></span></li></ol>{art((601,993,166,112),'section-art','article-pc')}</div></section>
<section class="article-section" id="monthly"><h2>毎月の準備額を考える</h2><p>目標額と期限を決め、今の資金と合わせて毎月の準備額を考えます。</p><div class="monthly-layout"><div>{button('tools.html#savings','毎月の準備額を計算する')}<span class="monthly-note">目標額・期限・準備済み資金を入力</span></div>{art((634,1121,134,108),'section-art','article-pc')}</div></section>
<section class="article-section" id="next"><h2>利用できる制度と次の行動</h2><div class="next-layout"><ul class="check-list"><li>勤務先の財形制度を確認する</li><li>使う時期に合う預金の条件を確認する</li><li>住宅購入後の支出を見直す</li></ul><p>利用できる制度を確認し、購入までの準備と購入後の家計を考えましょう。</p>{art((685,1250,83,83),'section-art','article-pc')}</div></section>
<p class="article-draft">公開前の構成見本です。費用・制度・提携条件の確認後に本文と広告を確定します。</p>
<section class="article-section related-section" aria-labelledby="related-heading"><h2 id="related-heading">関連する記事</h2><div class="related-grid"><a href="guide.html#savings">{art((800,176,193,117),'related-art','article-pc')}<span>口座の使い分け</span>{arrow()}</a><a href="events.html?event=housing">{art((800,352,193,117),'related-art','article-pc')}<span>住宅購入後の維持費</span>{arrow()}</a></div></section></article>
<aside class="related-sidebar" aria-label="関連する案内"><h2>関連記事</h2><a class="sidebar-link" href="guide.html#savings">{art((800,176,193,117),'sidebar-art','article-pc')}<h3>口座の使い分け</h3>{arrow()}</a><a class="sidebar-link" href="events.html?event=housing">{art((800,352,193,117),'sidebar-art','article-pc')}<h3>住宅購入後の維持費</h3>{arrow()}</a></aside></div></main>'''

def install():
    from category_pages import prepare
    prepare(ROOT)
    logo=f'<a class="brand" href="index.html" aria-label="暮らしのマネー情報 トップ"><img class="brand-art" src="assets/brand-wordmark.webp" width="355" height="70" alt=""></a>'
    for path in ROOT.glob('*.html'):
        html=path.read_text(encoding='utf-8')
        if path.name=='index.html': html=re.sub(r'<main\b.*?</main>',lambda _:home(),html,count=1,flags=re.S)
        if path.name=='index.html':
            from growth_content import growth_guides
            html=html.replace('<section class="section reading-section">',growth_guides(True)+'<section class="section reading-section">')
        html=re.sub(r'<a class="brand"[^>]*>.*?</a>',lambda _:logo,html,flags=re.S)
        boxes={key:box for key,_,_,box in EVENTS}
        html=re.sub(r'<span class="scene [^"]*" data-scene="([^"]+)" aria-hidden="true"></span>',lambda m:art(boxes[m[1]],'event-detail-art'),html)
        html=html.replace('<body>','<body class="faithful-design">').replace('<link rel="stylesheet" href="styles.css">','<link rel="stylesheet" href="styles.css"><link rel="stylesheet" href="faithful.css">')
        html=html.replace('モデルケースは架空の例です。','').replace('架空の条件で組み立てたモデルケースです。','世帯の条件に合わせて、使う時期と準備する資金を整理します。')
        html=html.replace('<p></p>','')
        destinations={'人生のイベント':'events.html','モデルケース':'cases.html','お金の基本':'guide.html','便利ツール':'tools-category.html'}
        def nav_replace(match):
            nav=match[0]
            for label,destination in destinations.items():
                active=' aria-current="page"' if path.name==destination else ''
                nav=re.sub(r'<a href="[^"]*"(?: aria-current="page")?>'+label+r'</a>',f'<a href="{destination}"{active}>{label}</a>',nav)
            return nav
        html=re.sub(r'<nav class="site-nav"[^>]*>.*?</nav>',nav_replace,html,flags=re.S)
        html=html.replace('href="#cases"','href="cases.html"').replace('href="#events"','href="events.html"')
        html=html.replace('href="guide.html#work">'+icon('book'),'href="guide.html#work">'+icon('payslip'))
        html=html.replace('<link rel="stylesheet" href="faithful.css">','<link rel="stylesheet" href="faithful.css"><link rel="stylesheet" href="categories.css">')
        html=html.replace('<p class="preview-note">','<p class="preview-note sr-only">')
        html=html.replace('モデルケースは架空の例です。制度や商品については、ご自身の条件に合わせてご確認ください。広告を含む記事にはPRを表示します。','広告を含む記事にはPRを表示します。<br>イメージです。')
        path.write_text(html,encoding='utf-8')

if __name__=='__main__': install()
