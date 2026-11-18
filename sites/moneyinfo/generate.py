from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'site'

EVENTS = [
 ('work','就職・転職','初任給までの生活費','新生活の初期費用と、収入が変わる前後の家計を考えます。',['住まいの契約と引越しにかかる費用','給与の支払日までに必要な生活費','勤務先の制度と社会保険の確認']),
 ('marriage','結婚・新生活','式と新居の支払い','式や新居にかかるお金を、支払う時期と家計の分け方から整理します。',['挙式・新居・家具などの費用を分ける','前払いと精算の時期を確認する','共同で支払う費用と個人の支出を分ける']),
 ('birth','出産・子育て','育休中の家計','出産・育児の費用と、休業・復職で変わる家計を整理します。',['出産や育児の準備に必要な費用','休業中の支出と給付の対象・入金時期','入園と復職で変わる支出']),
 ('education','進学・教育','入学前の納付','学費と生活費、入学前の支払いを分けて準備します。',['進路ごとの学費と生活費','受験・入学手続きで先に払う費用','支援制度の対象条件と入金時期']),
 ('housing','住まい・車','頭金と維持費','購入時だけでなく、住み始めてからの家計にも目を向けます。',['頭金・諸費用と残しておく生活費','毎月の返済と税・修繕などの支払い','車の維持費と買い替えの準備']),
 ('care','親の介護','介護費と休業','親の生活と、自分の世帯の家計を分けて考えます。',['介護を始めるときの費用と毎月の支出','親自身の収入・資産と子世帯の支出','休業や遠距離の移動で変わる家計']),
 ('retirement','退職・老後','年金までの生活費','退職前後の収入と、受給後の暮らしに必要なお金を整理します。',['退職から年金を受け取るまでの収支','退職金の使う時期と用途の区分','年払い・修繕・住み替えの備え']),
]

SYMBOLS = '''<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" aria-hidden="true" style="position:absolute;overflow:hidden"><defs>
<symbol id="i-arrow" viewBox="0 0 24 24"><path d="m9 5 7 7-7 7"/></symbol>
<symbol id="i-menu" viewBox="0 0 24 24"><path d="M3 5h18M3 12h18M3 19h18"/></symbol>
<symbol id="i-work" viewBox="0 0 24 24"><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12c5 3 13 3 18 0M10 12h4v4h-4z"/></symbol>
<symbol id="i-home" viewBox="0 0 24 24"><path d="m2 11 10-8 10 8M5 10v11h14V10M10 21v-7h4v7"/></symbol>
<symbol id="i-rings" viewBox="0 0 24 24"><circle cx="8" cy="14" r="6"/><circle cx="16" cy="14" r="6"/><path d="m9 3 3-2 3 2-3 4z"/></symbol>
<symbol id="i-calc" viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M7 5h10v4H7zM7 13h1m3 0h1m4 0h1M7 17h1m3 0h1m4 0h1"/></symbol>
<symbol id="i-book" viewBox="0 0 24 24"><path d="M12 5c-4-3-7-3-10-2v17c3-1 6-1 10 2 4-3 7-3 10-2V3c-3-1-6-1-10 2zM12 5v17"/></symbol>
<symbol id="i-calendar" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="17" rx="2"/><path d="M3 10h18M8 2v6m8-6v6M7 14h2m4 0h2m-8 4h2m4 0h2"/></symbol>
<symbol id="i-coins" viewBox="0 0 24 24"><ellipse cx="9" cy="6" rx="7" ry="3"/><path d="M2 6v4c0 4 14 4 14 0V6M2 10v4c0 4 14 4 14 0v-4M2 14v4c0 4 14 4 14 0v-4M17 9c6 0 7 5 2 6m-1 0c5 1 5 5 1 6"/></symbol>
<symbol id="i-shield" viewBox="0 0 24 24"><path d="M12 2 3 5v7c0 5 9 10 9 10s9-5 9-10V5zM12 7v10M8 11l4 4 4-4"/></symbol>
<symbol id="i-wallet" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="16" rx="2"/><path d="m3 5 14-3v3M16 11h6v6h-6zM18 14h1"/></symbol>
<symbol id="i-leaf" viewBox="0 0 24 24"><path d="M3 21c4-9 9-12 17-17M7 16C1 6 11 2 21 2c-1 12-5 17-14 14z"/></symbol>
</defs></svg>'''

def icon(name): return f'<svg aria-hidden="true"><use href="#i-{name}"></use></svg>'
ARROW = icon('arrow')

def brand():
 return '<a class="brand" href="index.html" aria-label="暮らしのマネー情報 トップ"><img class="brand-mark" src="assets/brand-mark.webp" alt="" width="70" height="70"><span class="brand-name">暮らしの<em>マネー</em>情報</span></a>'

def header(current=''):
 links=[('events','events.html','人生のイベント'),('cases','index.html#cases','モデルケース'),('basics','index.html#basics','お金の基本'),('tools','tools.html','便利ツール')]
 nav=''.join(f'<a href="{url}"'+(' aria-current="page"' if key==current else '')+f'>{label}</a>' for key,url,label in links)
 return f'''<p class="preview-note">公開前のプレビュー</p><a class="skip" href="#main">本文へ移動</a>{SYMBOLS}<header class="site-header"><div class="wrap header-inner">{brand()}<button class="menu-toggle" type="button" aria-controls="main-nav" aria-expanded="false" aria-label="メニューを開く">{icon('menu')}</button><nav class="site-nav" id="main-nav" aria-label="主な案内">{nav}</nav></div></header>'''

def footer():
 links=[('about','このサイトについて'),('operator','運営者情報'),('ads','広告・比較方針'),('privacy','プライバシーポリシー'),('contact','お問い合わせ')]
 return f'''<footer class="site-footer"><div class="wrap"><div class="footer-top">{brand()}<nav class="footer-links" aria-label="サイトの方針">{''.join(f'<a href="information.html#{k}">{v}</a>' for k,v in links)}</nav></div><p class="footer-bottom">モデルケースは架空の例です。制度や商品については、ご自身の条件に合わせてご確認ください。広告を含む記事にはPRを表示します。</p></div></footer>'''

def page(filename,title,description,body,current='',script=''):
 html=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="description" content="{escape(description,quote=True)}"><meta name="theme-color" content="#fffaf0"><title>{title}｜暮らしのマネー情報</title><link rel="icon" href="assets/site-icon.webp"><link rel="stylesheet" href="styles.css"><script src="common.js" defer></script>{script}</head><body>{header(current)}{body}{footer()}</body></html>'''
 (SITE/filename).write_text(html,encoding='utf-8')

def heading(title,lead=''):
 return f'<div class="section-heading"><h2>{title}</h2>'+ (f'<p>{lead}</p>' if lead else '')+'</div>'

def scene(key,cls=''):
 return f'<span class="scene {cls}" data-scene="{key}" aria-hidden="true"></span>'

def button(url,label,blue=False):
 return f'<a class="button'+(' button-blue' if blue else '')+f'" href="{url}">{label}{ARROW}</a>'

def event_items():
 return ''.join(f'<a class="event-link" href="events.html?event={key}">{scene(key)}<strong>{name}</strong><small>{desc}</small></a>' for key,name,desc,_,__ in EVENTS)

def case_item(url,img,tag,title,desc,more):
 return f'<a class="case-item" href="{url}">{img}<div class="case-copy"><span class="tag">{tag}</span><h3>{title}</h3><p>{desc}</p><span class="more">{more} →</span></div></a>'

HOME=f'''<main id="main"><section class="hero"><div class="wrap"><div class="hero-main"><div class="hero-copy"><h1><span class="hero-line">人生に必要な<span class="money-word">お金</span>の知識、</span><span class="hero-line">もっと深く<wbr><span class="hero-phrase">知っておきませんか。</span></span></h1><p>必要なお金を把握できれば、暮らしに余裕が生まれます。</p><div class="hero-actions">{button('#events','人生のイベントから探す')}{button('#cases','モデルケースから探す',True)}</div></div><img class="hero-art" src="assets/hero.webp" width="1774" height="887" alt="仕事、新生活、子育て、老後。それぞれの日常を黄色いリボンでつなぐイラスト" fetchpriority="high"></div><p class="illustration-note">イメージです。</p><nav class="quick-links" aria-label="よく調べる人生のイベント"><a href="events.html?event=work">{icon('work')}就職・転職</a><a href="events.html?event=marriage">{icon('rings')}結婚・子育て</a><a href="events.html?event=housing">{icon('home')}住まい</a><a href="events.html?event=care"><img src="assets/care-hands.png" width="47" height="47" alt="">介護・老後</a></nav></div></section>
<section class="section" id="events"><div class="wrap">{heading('人生のイベントから、お金を調べる','費用だけでなく、支払う時期と準備することまで。')}<div class="event-grid">{event_items()}</div></div></section>
<section class="section section-tint" id="cases"><div class="wrap">{heading('自分に近いモデルケースから','世帯や働き方、これからの予定に合わせて。')}<div class="case-grid">
{case_item('article.html','<img class="case-image" src="assets/article-home.webp" width="800" height="450" loading="lazy" alt="家のテーブルで住宅資金の予定を話す二人">','共働き・住宅購入','住宅資金と家計の計画','購入までの準備と、購入後に残すお金を分けて考える。','モデルケースを読む')}
{case_item('events.html?event=work',scene('work','case-image'),'単身・新生活','一人暮らしの準備','初任給までの生活費と最初に必要な支払い。','関連するテーマへ')}
{case_item('events.html?event=birth',scene('birth','case-image'),'子育て・復職','育休から復職までのお金','給付や給与の時期と毎月の家計を考える。','関連するテーマへ')}
</div><p class="fine cases-note">モデルケースは架空の例です。金額や制度の対象条件は、記事ごとに確認します。</p></div></section>
<section class="section" id="tools"><div class="wrap">{heading('便利ツールで、準備する金額を具体的に','入力した条件から計算し、家計の計画に役立てましょう。')}<div class="tool-grid">
<a class="tool-item" href="tools.html#savings">{icon('calc')}<h3>毎月の準備額を計算</h3><p>目標額・期限・準備済み資金から、毎月の積立額を逆算。</p><span class="text-link">準備額を計算する →</span></a>
<a class="tool-item" href="tools.html#annual">{icon('calendar')}<h3>年ごとの積立計画表</h3><p>積立と支出の予定を年ごとの残高で確認。</p><span class="text-link">計画表を作る →</span></a>
<a class="tool-item" href="tools.html#deposit">{icon('coins')}<h3>預金の利息を比較</h3><p>優遇期間・通常金利・手数料を同じ条件で計算。</p><span class="text-link">条件を入れて比較する →</span></a>
</div></div></section>
<section class="section section-tint" id="basics"><div class="wrap">{heading('お金の基本を知る','仕組みを理解して選択肢を考える。')}<div class="basic-grid"><a class="basic-link" href="guide.html#work">{icon('book')}勤務先の制度・税・社会保険</a><a class="basic-link" href="guide.html#savings">{icon('coins')}貯蓄・口座・資産形成</a><a class="basic-link" href="guide.html#protection">{icon('shield')}公的保障と民間保険</a><a class="basic-link" href="guide.html#household">{icon('wallet')}日常の家計・支払い</a></div></div></section>
<section class="section"><div class="wrap">{heading('まず読んでおきたい記事')}<ul class="news-list"><li><a href="article.html"><img class="news-thumb" src="assets/article-home.webp" loading="lazy" width="125" height="72" alt="">共働き世帯の住宅資金と家計の計画{ARROW}</a></li><li><a href="guide.html#savings">{icon('book')}使う時期から考える、貯蓄と口座の基本{ARROW}</a></li></ul></div></section></main>'''
page('index.html','人生のイベントとお金の準備','人生のイベントに必要な費用と時期を、モデルケースや便利ツールから考える情報サイト。',HOME)

ARTICLE=f'''<main class="wrap" id="main"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><a href="events.html?event=housing">住まい・車</a><span aria-hidden="true">›</span><span>モデルケース</span></nav><div class="article-layout"><article class="article-main"><span class="tag">モデルケース</span><h1 class="article-title">共働き世帯の住宅資金と家計の計画</h1><p class="article-deck">購入までの準備と、購入後に残すお金を分けて考える。</p><img class="article-hero" src="assets/article-home.webp" width="1600" height="800" alt="賃貸の部屋で、住宅購入までの予定をノートに書きながら相談する共働きの二人" fetchpriority="high"><p class="article-note">生活場面のイメージです。この記事は、公開前のモデルケースの構成見本です。金額と制度の確認はこれから行います。</p>
<section class="key-points" aria-labelledby="key-heading"><h2 id="key-heading">この記事の要点</h2><ul><li>購入時の費用とその後の生活費を分ける</li><li>支払いと入金の時期から必要な手元資金を考える</li><li>期限までの準備額と使える制度を確認する</li></ul></section>
<nav class="toc" aria-labelledby="toc-heading"><h2 id="toc-heading">{icon('book')}目次</h2><ol><li><a href="#conditions">モデルケースの条件</a></li><li><a href="#costs">購入にかかる費用と内訳</a></li><li><a href="#timing">支払いと入金の予定</a></li><li><a href="#monthly">毎月の準備額を考える</a></li><li><a href="#next">利用できる制度と次の行動</a></li></ol></nav>
<section class="article-section" id="conditions"><h2>モデルケースの条件</h2><ul class="attributes"><li>共働き</li><li>賃貸</li><li>住宅購入を検討</li></ul><p>二人で働きながら、住宅購入に向けて準備する世帯を想定しています。物件の購入費だけでなく、購入後の暮らしに残す資金も分けて考えます。</p><p>家族構成や勤務先の制度が異なる場合は、その条件に合わせて読み替えましょう。具体的な金額は、確認を終えてから反映します。</p></section>
<section class="article-section" id="costs"><h2>購入にかかる費用と内訳</h2><p>頭金と諸費用、購入後の生活費を分けて整理します。費用の見積りでは、対象となる支出と支払う時期を対応させましょう。</p><div class="table-scroll tablewrap" role="region" aria-label="購入にかかる費用の内訳" tabindex="0"><table><caption class="sr-only">金額確認前の費用整理表</caption><thead><tr><th scope="col">費目</th><th scope="col">準備する時期</th><th scope="col">金額</th></tr></thead><tbody><tr><th scope="row">頭金</th><td>契約・決済の条件を確認</td><td>確認後に表示</td></tr><tr><th scope="row">諸費用</th><td>支払先ごとに確認</td><td>確認後に表示</td></tr><tr><th scope="row">購入後の生活費</th><td>入居後も確保</td><td>確認後に表示</td></tr></tbody></table></div><p class="fine">具体的な費目・支払時期は、物件と契約の条件に合わせて確認します。</p></section>
<section class="article-section" id="timing"><h2>支払いと入金の予定</h2><p>購入の流れに沿って、いつ支払いがあるかを確認します。利用を予定する制度や資金の入金が後になる場合は、それまでに使える資金を分けておきましょう。</p><ol class="timeline"><li>契約<span></span><small>手付金などの条件を確認</small></li><li>引越し<span></span><small>決済・転居の支出を整理</small></li><li>入居後<span></span><small>維持費と生活費を確保</small></li></ol></section>
<section class="article-section" id="monthly"><h2>毎月の準備額を考える</h2><p>目標額から、その用途に使える準備済み資金を差し引きます。残りを積立回数で割ると、毎月の準備額を計算できます。</p><p>必要な支払日より前に資金がそろうかも別に確認しましょう。同じ貯蓄を、住宅と教育など複数の用途に重ねて計上しないようにしましょう。</p><div class="article-callout"><p>目標額と期限が決まったら、ご自身の条件で試算できます。</p>{button('tools.html#savings','毎月の準備額を計算する')}<span class="draft-label">計算はブラウザー内で行い、入力内容は送信しません。</span></div></section>
<section class="article-section" id="next"><h2>利用できる制度と次の行動</h2><ul class="check-list"><li>勤務先の財形制度など、利用できる仕組みを確認する</li><li>資金を使う時期に合う預金の条件を確認する</li><li>住宅購入後の返済・維持費・生活費を整理する</li></ul><p>まずは対象条件や払出し条件を確かめ、その後に選択肢を比較しましょう。必要な時期が近い資金と、長く使わない資金は区別して考えます。</p><a class="text-link" href="guide.html#savings">貯蓄・口座・資産形成の基本へ →</a></section>
<section class="article-section" aria-labelledby="related-heading"><h2 id="related-heading">あわせて確認したいこと</h2><div class="related-grid"><a href="guide.html#savings">口座の使い分け →</a><a href="events.html?event=housing">住宅購入後の維持費 →</a></div></section><a class="to-top" href="#main">記事の先頭へ ↑</a></article>
<aside class="related-sidebar" aria-label="関連する案内"><h2>こちらも確認</h2><a class="sidebar-link" href="tools.html#savings">{icon('calc')}<h3>毎月の準備額を計算</h3><p>目標と期限から積立額を逆算。</p></a><a class="sidebar-link" href="guide.html#savings">{icon('coins')}<h3>貯蓄と口座の基本</h3><p>使う時期と引き出せる条件から。</p></a></aside></div></main>'''
page('article.html','共働き世帯の住宅資金と家計の計画','住宅購入までの費用、支払いと入金の予定、毎月の準備額を整理するモデルケースの構成見本。',ARTICLE,'cases')

filters='<button class="filter-button" type="button" data-filter="all" aria-pressed="true">すべて</button>'+''.join(f'<button class="filter-button" type="button" data-filter="{key}" aria-pressed="false">{name}</button>' for key,name,*_ in EVENTS)
details=[]
for key,name,short,desc,checks in EVENTS:
 more=button('tools.html#savings','準備する金額を計算する',True)
 details.append(f'<section class="event-detail" data-event="{key}" id="event-{key}">{scene(key)}<div><h2>{name}のお金</h2><p>{desc}</p><ul>{"".join(f"<li>{s}</li>" for s in checks)}</ul>{more}</div></section>')
events=f'''<main id="main" class="wrap"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><span>人生のイベント</span></nav><header class="page-intro"><h1>人生のイベントと、お金の準備</h1><p>これからの予定から、費用・支払う時期・確認することを整理できます。</p></header><div class="filter-row" role="group" aria-label="人生のイベントを選ぶ">{filters}</div><p class="fine" id="event-status" aria-live="polite">すべてのイベントを表示しています。</p><div class="event-layout" style="display:grid;gap:24px">{''.join(details)}</div></main>'''
page('events.html','人生のイベントからお金を調べる','就職、結婚、出産、進学、住宅、介護、退職に必要なお金と準備の案内。',events,'events')

def field(name,label,unit='',kind='number',hint='',optional=False,attrs=''):
 value=f'<input id="{name}" name="{name}" type="{kind}" '+('' if optional else 'required ')+f'{attrs}>'
 return f'<div class="form-row"><label for="{name}">{label}'+('<span class="optional">任意</span>' if optional else '')+f'</label><div class="input-unit">{value}'+(f'<span>{unit}</span>' if unit else '')+'</div>'+ (f'<small>{hint}</small>' if hint else '')+'</div>'

def error(id): return f'<p class="form-error" id="{id}" role="alert" hidden></p>'
moneyattrs='min="0" max="1000000000000" step="1" inputmode="numeric"'
saveform=field('target','目標額','円',attrs=moneyattrs)+field('saved','この目的に使える準備済み資金','円',attrs=moneyattrs)+field('deadline','資金を準備したい月',kind='month',hint='翌月から目標月まで、毎月積み立てる条件です。')
savepanel=f'''<section class="tool-panel" id="savings-panel" role="tabpanel" aria-labelledby="savings-tab"><div class="tool-layout"><form class="tool-form" id="savings-form"><h2>毎月の準備額を計算</h2>{saveform}{error('savings-error')}<button class="button" type="submit">毎月の準備額を計算する{ARROW}</button><p class="form-note">利息・運用益を含めず、毎月同じ額を積み立てる単純計算です。1円未満は切り上げ、最終回で調整します。</p></form><div class="result-box" id="savings-result" aria-live="polite" aria-atomic="true"><h2>計算結果</h2><p>目標額・準備済み資金・目標月を入力してください。</p></div></div></section>'''
annualfields=field('annual-saved','開始時点の資金','円',attrs=moneyattrs)+field('monthly','毎月の積立額','円',attrs=moneyattrs)+field('years','計画する年数','年',attrs='min="1" max="50" step="1" inputmode="numeric"')+field('expense-year','まとまった支出がある年','年目',hint='予定支出額と一緒に入力してください。',optional=True,attrs='min="1" max="50" step="1" inputmode="numeric"')+field('expense','その年の予定支出額','円',optional=True,attrs=moneyattrs)
annualpanel=f'''<section class="tool-panel" id="annual-panel" role="tabpanel" aria-labelledby="annual-tab" hidden><div class="tool-layout"><form class="tool-form" id="annual-form"><h2>年ごとの積立計画表</h2>{annualfields}{error('annual-error')}<button class="button" type="submit">積立計画表を作る{ARROW}</button><p class="form-note">利息・運用益は含めません。予定支出は指定年の年末残高から差し引きます。年の途中の資金不足は別に確認が必要です。</p></form><div class="result-box" id="annual-result" aria-live="polite" aria-atomic="true"><h2>計画の確認</h2><p>毎月の積立と予定支出を入力すると、年ごとの残高を確認できます。</p></div></div><div class="result-table-area" id="annual-table-area" hidden><h2>年ごとの残高</h2><div class="table-scroll tablewrap" role="region" aria-label="年ごとの積立計画" tabindex="0"><table id="annual-table"><caption class="sr-only">年ごとの積立と支出の計画</caption><thead><tr><th scope="col">年</th><th scope="col">年初残高</th><th scope="col">年間積立額</th><th scope="col">予定支出</th><th scope="col">年末残高</th></tr></thead><tbody></tbody></table></div><button type="button" class="button button-outline" id="download-plan">計画表をCSVで保存</button></div></section>'''

depositcommon=field('principal','預入額','円',attrs=moneyattrs)+field('term','預入期間','か月',attrs='min="1" max="600" step="1" inputmode="numeric"')+field('tax','試算に使う税率','％',optional=True,hint='空欄なら税引前。入力した税率で概算します。',attrs='min="0" max="100" step="any" inputmode="decimal"')
offers=[]
for key in ['a','b']:
 offers.append(f'<fieldset class="offer-form"><legend>比較条件 {key.upper()}</legend>'+field(f'{key}-promo','優遇金利（年率）','％',attrs='min="0" max="100" step="any" inputmode="decimal"')+field(f'{key}-months','優遇が適用される期間','か月',attrs='min="0" max="600" step="1" inputmode="numeric"')+field(f'{key}-standard','優遇終了後の金利（年率）','％',attrs='min="0" max="100" step="any" inputmode="decimal"')+field(f'{key}-fees','期間中の手数料合計','円',attrs=moneyattrs)+'</fieldset>')
depositpanel=f'''<section class="tool-panel" id="deposit-panel" role="tabpanel" aria-labelledby="deposit-tab" hidden><form class="tool-form" id="deposit-form"><h2>預金の利息を比較</h2><p>同じ預入額・期間で、金利の適用条件と手数料を比較します。</p><div class="form-grid">{depositcommon}</div><div class="tool-comparison">{''.join(offers)}</div>{error('deposit-error')}<button class="button" type="submit" style="margin-top:24px">条件を比較する{ARROW}</button><p class="form-note">単利・月数割りの概算です。優遇期間は預入期間を上限とします。利息・税はそれぞれ1円未満を切り捨てます。実際の利息は日割り・複利・金融機関の端数処理や適用条件などで異なります。</p></form><div class="result-box" id="deposit-result" aria-live="polite" aria-atomic="true" style="position:static;margin-top:24px"><h2>比較結果</h2><p>ご自身で確認した条件を入力してください。特定の金融機関を推奨するものではありません。</p></div></section>'''
tools=f'''<main id="main" class="wrap tool-content"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><span>便利ツール</span></nav><header class="page-intro"><h1>お金の準備に役立つ、便利ツール</h1><p>目標や支払う時期が決まったら、ご自身の条件で試算しましょう。入力内容はブラウザー内で計算し、送信・保存しません。</p></header><noscript><p class="no-script">便利ツールの計算にはJavaScriptが必要です。解説記事はそのままお読みいただけます。</p></noscript><div class="tool-tabs" role="tablist" aria-label="便利ツールの種類"><button class="tool-tab" id="savings-tab" role="tab" aria-controls="savings-panel" aria-selected="true" tabindex="0" data-tool="savings">毎月の準備額</button><button class="tool-tab" id="annual-tab" role="tab" aria-controls="annual-panel" aria-selected="false" tabindex="-1" data-tool="annual">年ごとの積立計画</button><button class="tool-tab" id="deposit-tab" role="tab" aria-controls="deposit-panel" aria-selected="false" tabindex="-1" data-tool="deposit">預金の利息比較</button></div>{savepanel}{annualpanel}{depositpanel}<section class="article-section"><h2>計算の後に確認したいこと</h2><p>試算は、入力した条件の範囲での計算です。支払う時期と、資金を引き出せる条件も確認しましょう。</p><div class="related-grid"><a href="case-family-trip.html">帰省の交通費と宿代のケースを見る →</a><a href="article.html">住宅購入の頭金と諸費用を調べる →</a><a href="cases.html#readable-cases">ほかの暮らしのケースを探す →</a><a href="guide.html#savings">貯蓄・口座の基本 →</a></div></section></main>'''
for anchor, title in [('savings','毎月の準備額を計算'),('annual','年ごとの積立計画表'),('deposit','預金の利息を比較')]:
 tools = tools.replace(f'<h2>{title}</h2>',f'<span id="{anchor}" class="sr-only" aria-hidden="true"></span><h2>{title}</h2>')
page('tools.html','毎月の準備額・積立計画・預金利息の便利ツール','目標額からの積立額計算、年ごとの資金計画、預金利息と費用の比較をブラウザー内で行えます。',tools,'tools','<script src="tools.js" type="module"></script>')

guide=f'''<main id="main" class="wrap"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><span>お金の基本</span></nav><header class="page-intro"><h1>仕組みを知って、お金の準備を考える</h1><p>ご自身の制度や契約の条件を確認するための、基本的な調べ方を整理しています。</p></header><div class="policy-content"><section id="work"><h2>勤務先の制度・税・社会保険</h2><p>給与明細、就業規則、福利厚生の案内から、勤務先で利用できる制度を確認しましょう。財形や企業年金の有無は、勤務先ごとに異なります。</p><p>税と社会保険、勤務先独自の手当は、対象条件を分けて確認しましょう。</p><a class="text-link" href="events.html?event=work">就職・転職のお金へ →</a></section><section id="savings"><h2>貯蓄・口座・資産形成</h2><p>生活費、支払う時期が決まっている費用、長く使わない資金を、用途ごとに分けて考えます。口座を増やす前に、引落し・振込み・払出しの条件と費用を確認しましょう。</p><p>投資を考えるときは、必要な時期に資金を確保できるか、値下がりや費用を受け入れられるかも確認が必要です。</p><a class="text-link" href="tools.html#savings">毎月の準備額を試算する →</a></section><section id="protection"><h2>公的保障と民間保険</h2><p>加入している健康保険、年金、勤務先の制度などから、対象になる保障を確認します。その後に、貯蓄や民間の保障で備える範囲を考えましょう。</p><p>給付では、金額・申請時期・入金時期・対象外の費用を確認しましょう。</p><a class="text-link" href="events.html?event=care">介護の家計を考える →</a></section><section id="household"><h2>日常の家計・支払い</h2><p>毎月の支払いに加え、税・保険・更新料など年払いの費用も整理します。支払う月を先に把握すると、毎月準備する金額を考えやすくなります。</p><p>決済方法は、還元と年会費、支払日、分割などにかかる手数料も含めて比較しましょう。</p><a class="text-link" href="tools.html#annual">年ごとの積立計画を作る →</a></section></div></main>'''
page('guide.html','勤務先制度・貯蓄・保障・家計の基本','人生のイベントに合わせて、勤務先制度、口座の条件、保障、日常の支出を確認するための基本。',guide,'basics')

info=f'''<main id="main" class="wrap"><header class="page-intro"><h1>このサイトの方針と案内</h1><p>現在は公開前のプレビューです。暮らしのマネー情報運営部が、記事と便利ツールを制作しています。</p></header><div class="policy-content"><section id="about"><h2>このサイトについて</h2><p>暮らしのマネー情報は、人生のイベントに必要なお金と準備を、モデルケースや便利ツールから考える情報サイトです。実在する相談事例や有資格者による個別の助言を装うものではありません。</p></section><section id="operator"><h2>運営者情報</h2><p>運営者は暮らしのマネー情報運営部です。料金や制度の条件と確認日を記録し、記事を見直します。</p></section><section id="ads"><h2>広告・比較方針</h2><p>広告を含む記事にはPRを表示します。比較の条件と対象範囲を明確にし、広告の報酬だけで選択肢を決めない方針です。</p><p>このプレビューにはアフィリエイトリンクや広告主への申込みリンクはありません。広告主・リンク先・掲載条件を確認するまで、架空の広告や申込みボタンは設けません。</p></section><section id="privacy"><h2>プライバシーポリシー</h2><p>このプレビューの便利ツールは、入力内容をブラウザー内で計算します。入力した金額は外部へ送信せず、ブラウザーへの保存も行いません。アクセス解析や広告配信の外部スクリプトは使用していません。</p><p>本公開時には、実際に導入するサービスと受付方法に合わせて、この方針を確認します。</p></section><section id="contact"><h2>お問い合わせ</h2><p><a href="contact.html">お問い合わせフォーム</a></p></section><section id="calculations"><h2>試算とモデルケースについて</h2><p>モデルケースは架空の条件で組み立てた例です。未確認の金額は確定値として表示しません。便利ツールの結果は入力した条件に応じた計算であり、将来の収益や必要資金の確保を保証するものではありません。</p></section><section><h2>ページ一覧</h2><div class="policy-list"><a href="index.html">トップページ</a><a href="events.html">人生のイベント</a><a href="cases.html">モデルケース</a><a href="tools.html">便利ツール</a><a href="guide.html">お金の基本</a></div></section></div></main>'''
page('information.html','サイトの方針・運営者・広告・プライバシー','公開前プレビューの運営・広告方針、入力情報の扱い、モデルケースと試算の注意点。',info)
page('contact.html','お問い合わせフォーム','暮らしのマネー情報運営部へのお問い合わせフォームの案内。','<main class="wrap page-intro" id="main"><h1>お問い合わせフォーム</h1><p data-contact-preview>公開前の確認画面です。フォームのリンク先は公開用の設定で指定します。</p></main>')
(SITE/'robots.txt').write_text('User-agent: *\nDisallow: /\n',encoding='utf-8')
print('Built 6 pages: index, article, events, tools, guide, information')

from faithful_pages import install
install()
