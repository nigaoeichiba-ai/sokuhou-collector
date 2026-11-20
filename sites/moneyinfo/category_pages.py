"""4つのカテゴリ入口と、基本ガイドをデータから生成する。"""
from html import escape
import re

TOPICS = [
 ('work','勤務先の制度・税・社会保険','basics-work','給与明細や勤務先の案内から、利用できる制度を確認する。','勤務先の制度を調べるときに、先に確認すること','給与明細・勤務先の案内・申請先をつなげて調べましょう。',[
  ('まず、勤務先の資料を集める','給与明細、就業規則、福利厚生の案内を手元にそろえましょう。財形貯蓄や企業年金などは、制度の名前だけで利用できると判断せず、勤務先の説明とご自身の条件を照らし合わせます。'),
  ('申込みと受取りの条件を分ける','利用できる人、申込みの締切、給与からの控除、資金を受け取る条件を、別々に確認します。結婚・出産・住宅購入・退職などの予定があるときは、その時期に使える制度かも確認しましょう。'),
  ('分からないことを質問にする','担当窓口には「自分が対象か」「いつまでに何を出すか」「途中で変更するとどうなるか」を尋ねます。案内を受けた日と資料名を手元に残すと、次に確認する内容を整理できます。')],['給与から毎月引かれている項目','勤務先の制度の対象条件','申込みの締切と必要書類','転職・退職時に確認すること'],'work','財形と自分で積み立てる預金の違い'),
 ('savings','貯蓄・口座・資産形成','basics-savings','使う時期と、引き出せる条件からお金の置き方を考える。','口座を分ける前に、使う目的と手数料を確認する','口座の数より先に、何のためのお金かを書き出しましょう。',[
  ('支払いの時期で分けてみる','生活の支払いに使うお金、予定している支出のためのお金、すぐには使う予定のないお金を分けて書き出します。同じ貯蓄を住宅と教育の両方に重ねて数えないことも大切です。'),
  ('資金を移す費用と引出し条件を確認する','口座を増やす前に、振込みや引出しにかかる費用、無料になる条件、残高の管理方法を確認しましょう。口座どうしで資金を移す場合は、毎回の手間も含めて続けられる方法を考えます。'),
  ('商品を選ぶ前に必要な日を決める','使う予定のある資金は、必要な日に使えることを先に確認します。預金と投資は同じものとして扱わず、引き出せる時期や損失の可能性、費用を読んでから選択肢を考えましょう。')],['何に使う資金か','支払う予定の月','他の用途と重複していないか','振込・引出しなどの手数料'],'housing','NISAを考える前に整理する、使う予定のあるお金'),
 ('protection','公的保障と民間保険','basics-protection','受け取れる保障を調べてから、備える範囲を考える。','保険を選ぶ前に、公的保障と手元の資金を整理する','何に備えたいかと、すでに使える保障を分けて確認しましょう。',[
  ('心配している場面を書き出す','病気で働けないとき、家族の介護が必要なときなど、ご自身が気になる場面を具体的にします。生活費が増えるのか、収入が減るのかを分けると、調べる内容を絞れます。'),
  ('すでに使える保障を確認する','加入している公的な仕組みと勤務先の制度について、対象になる条件や申請先を確認します。民間保険を考える際も、こうした保障を先に調べると、重複や不足を確認する材料になります。'),
  ('相談前に条件をそろえる','手元の資金、現在の契約、毎月支払える費用、心配している場面をまとめましょう。相談先を利用する場合は、相談できる内容と費用、相談後の案内の扱いを確認します。申込みや契約の変更は、説明を読んでから判断しましょう。')],['備えたい場面と家計への影響','加入中の制度と契約','給付の対象条件と申請先','相談先の対応範囲と費用'],'care','保険・家計相談を利用する前に確認したい条件'),
 ('household','日常の家計・支払い','basics-household','毎月の支出に、年払いと特別な支払いを加えて考える。','毎月の家計に、年払いの支出を加えて考える','月々の収支と、支払いが集中する月を確認しましょう。',[
  ('毎月の支出とそれ以外の支出を分ける','家賃や食費など毎月の支出と、更新料・保険料・税金・進学の支度など時期の決まった支出を分けます。家計簿や利用明細から、ご自身が実際に支払っている項目を拾ってみましょう。'),
  ('支払う月をカレンダーに置く','金額が分かっている支出は、請求される月と支払う月を記録します。まだ分からないものは見積りや案内を確認し、確認済みの金額と分けておきます。複数の支出が重なる月を見つけることが目的です。'),
  ('毎月準備する額へ戻す','予定している支出と今使える資金を整理したら、支払いまでに準備する額を考えます。毎月の準備額と年ごとの残高は便利ツールでも試算できます。支払日の直前に資金が足りるかは、月ごとの予定でも確認しましょう。')],['毎月必ず支払う項目','年払いの費用と支払月','これから予定している大きな支出','準備済み資金と残りの準備期間'],'work','クレジットカードを選ぶ前に確認する年会費・支払日・手数料'),
]

def image_icon(name,cls=''):
    name={'basics-shopping':'basics-household','basics-points':'basics-savings','basics-sidework':'work'}.get(name,name)
    return f'<img class="painted-icon {cls}" src="assets/icons/{name}.webp" width="128" height="128" alt="">'

def crumb(name):
    return f'<nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span aria-hidden="true">›</span><span>{name}</span></nav>'

def hero(eyebrow,title,lead,box,source='home-pc'):
    from faithful_pages import art
    return f'<header class="hub-hero"><div><p class="eyebrow">{eyebrow}</p><h1>{title}</h1><p class="hub-lead">{lead}</p></div>{art(box,"hub-hero-art",source)}</header>'

def entry(url,title,desc,tag='基本ガイド'):
    return f'<a class="hub-entry" href="{url}"><span class="entry-tag">{tag}</span><h3>{title}</h3><p>{desc}</p><span class="entry-more">読む <span aria-hidden="true">›</span></span></a>'

def upcoming(title):
    return f'<div class="upcoming-entry"><span>制作予定</span><p>{title}</p></div>'

def basics():
    from faithful_pages import heading
    from growth_content import growth_guides
    choices=''.join(f'<a class="topic-choice" href="#{key}">{image_icon(asset)}<span><strong>{name}</strong><small>{lead}</small></span><b aria-hidden="true">›</b></a>' for key,name,asset,lead,*_ in TOPICS)
    blocks=''
    for key,name,asset,lead,title,deck,sections,checks,event,planned in TOPICS:
        prompts=''.join(f'<li>{s}</li>' for s in checks[:3])
        blocks+=f'<section class="knowledge-block" id="{key}"><div class="knowledge-intro">{image_icon(asset)}<h2>{name}</h2><p>{lead}</p><ul>{prompts}</ul></div><div class="knowledge-articles">{entry(asset+".html",title,deck)}{upcoming(planned)}<a class="quiet-link" href="events.html?event={event}">人生のイベントから考える ›</a></div></section>'
    return f'<main class="wrap hub-page" id="main">{crumb("お金の基本")}{hero("お金の基本","暮らしのお金を、<br>仕組みから知る。","いま使える制度、口座の使い方、保障、毎月の家計。気になるテーマから読んでみましょう。",(28,827,313,90))}<section class="hub-section">{heading("何から知りたいですか")}<div class="topic-choices">{choices}</div><a class="quiet-link" href="#household-growth">節約・セール、ポイ活、副業から考えたい方へ ›</a></section><section class="hub-section learning-path"><h2>知る、整理する、比べる。</h2><ol><li><span>知る</span>制度と仕組みを読む</li><li><span>整理する</span>自分の条件に当てはめる</li><li><span>考える</span>必要な準備額を試算する</li></ol><a href="tools-category.html">使える便利ツールを見る ›</a></section>{blocks}{growth_guides()}<aside class="hub-endnote"><p>条件が変わると、選べる方法も変わります。商品を決める前に、ご自身の予定と契約条件を確認しましょう。</p></aside></main>'

def guide_article(topic):
    from faithful_pages import heading,button,art
    key,name,asset,lead,title,deck,sections,checks,event,_=topic
    contents=''.join(f'<li><a href="#part-{i}">{h}</a></li>' for i,(h,p) in enumerate(sections,1))
    body=''.join(f'<section class="guide-section" id="part-{i}"><h2>{h}</h2><p>{p}</p></section>' for i,(h,p) in enumerate(sections,1))
    return f'<main class="wrap guide-article-page" id="main"><nav class="breadcrumbs" aria-label="パンくず"><a href="index.html">トップ</a><span>›</span><a href="guide.html">お金の基本</a><span>›</span><span>{name}</span></nav><div class="guide-article-layout"><article><header class="guide-article-header"><span class="entry-tag">お金の基本</span><h1>{title}</h1><p>{deck}</p></header><div class="guide-visual">{image_icon(asset)}<ul>{"".join(f"<li>{x}</li>" for x in checks[:3])}</ul></div><nav class="guide-toc" aria-label="目次"><h2>目次</h2><ol>{contents}</ol></nav>{body}<section class="guide-checklist"><h2>手元に書き出してみましょう</h2><ul>{"".join(f"<li>{x}</li>" for x in checks)}</ul></section><section class="guide-next"><h2>自分の予定に当てはめる</h2><p>予定している支出と期限が分かったら、毎月の準備額を試算できます。</p>{button("tools.html#savings","毎月の準備額を計算する")}<a class="quiet-link" href="events.html?event={event}">関連する人生のイベントを見る ›</a></section></article><aside class="guide-side"><h2>あわせて読む</h2>{"".join(entry(other[2]+".html",other[4],other[3]) for other in TOPICS if other[0]!=key)}<a class="quiet-link" href="guide.html">お金の基本の一覧へ ›</a></aside></div></main>'

def cases():
    from faithful_pages import art,heading
    from case_articles import cards as article_cards, case_filters
    plans=[('education','子どもの進学','学費と入学前の支払い'),('retirement','退職前後','年金を受け取るまでの資金')]
    boxes={key:box for key,_,_,box in __import__('faithful_pages').EVENTS}
    cards='<ul class="planned-list">'+''.join(f'<li>{name}（制作予定）</li>' for name in ("進学","退職前後"))+'</ul>'
    return f'<main class="wrap hub-page" id="main">{crumb("モデルケース")}{hero("モデルケース","必要なお金は環境によってそれぞれ。","お金を知れば暮らしが豊かになります。",(682,827,313,90))}<section class="hub-section" id="readable-cases">{heading("暮らしのシーンでお金を考える")}{case_filters()}<div class="case-index-grid">{article_cards()}</div><p><a href="travel-cost-average.html">帰省費用の平均と内訳を読む ›</a></p></section><section class="hub-section">{heading("これから加えるモデルケース")}{cards}</section><section class="hub-endnote"><h2>先に、費用の考え方を知りたい方へ</h2><p>世帯の条件にかかわらず、支払う時期と使える資金を分けることから始められます。</p><a href="guide.html">お金の基本を見る ›</a></section></main>'

def tools_category():
    from faithful_pages import art,heading,button
    specs=[('savings','毎月の準備額を計算','目標額と期限から、毎月の積立額を逆算します。',['目標額','準備済み資金','資金を準備したい月'],'毎月いくら準備するかを考えたいとき',(8,1058,117,104)),('annual','年ごとの積立計画表','積立と予定支出から、年ごとの残高を確認します。',['開始時点の資金','毎月の積立額・年数','予定している支出'],'支出が重なる年と資金不足を確認したいとき',(310,1058,100,104)),('deposit','預金の利息を比較','優遇期間や手数料を含めて、入力した条件を比較します。',['預入額・預入期間','優遇金利と通常金利','税率・手数料'],'ご自身で調べた預金の条件をそろえたいとき',(611,1076,67,84))]
    cards=''
    for key,title,desc,inputs,scene,box in specs:
        cards+=f'<section class="tool-directory-card" id="{key}">{art(box,"directory-tool-art")}<div><p class="eyebrow">{scene}</p><h2>{title}</h2><p>{desc}</p><h3>入力するもの</h3><ul>{"".join(f"<li>{x}</li>" for x in inputs)}</ul>{button("tools.html#"+key,"このツールを使う")}</div></section>'
    return f'<main class="wrap hub-page" id="main">{crumb("便利ツール")}{hero("便利ツール","これからの予定を、<br>準備する金額へ。","目標額や期限が決まったら、ご自身の条件を入力して試算しましょう。",(634,1121,134,108),"article-pc")}<section class="hub-section tool-directory">{cards}</section><aside class="hub-endnote"><h2>計算の前に</h2><p>入力内容はブラウザー内で計算し、保存・送信しません。利息や給付を自動で見込むものではありません。計算条件と実際の支払日も確認しましょう。</p><a href="guide.html">お金の基本を読む ›</a></aside></main>'

def prepare(root):
    template=(root/'index.html').read_text(encoding='utf-8')
    def write(name,title,description,main):
        html=re.sub(r'<main\b.*?</main>',lambda _:main,template,count=1,flags=re.S)
        html=re.sub(r'<title>.*?</title>',lambda _:f'<title>{title}｜暮らしのマネー情報</title>',html,count=1,flags=re.S)
        html=re.sub(r'<meta name="description" content="[^"]*">',lambda _:f'<meta name="description" content="{escape(description,quote=True)}">',html,count=1)
        (root/name).write_text(html,encoding='utf-8')
    write('guide.html','お金の基本｜勤務先制度・貯蓄・保障・家計から探す','勤務先制度、口座の条件、公的保障、毎月の家計を、テーマ別のガイドから調べる。',basics())
    write('cases.html','世帯と働き方から探すモデルケース','共働き、単身、子育て、介護、退職。暮らしの条件からお金の準備を考えるケースの一覧。',cases())
    write('tools-category.html','暮らしのお金を試算する便利ツール一覧','毎月の準備額、年ごとの積立計画、預金利息比較。目的に合った計算ツールを選べる一覧。',tools_category())
    from growth_content import MONEY_LIFE_TOPICS
    for topic in TOPICS + MONEY_LIFE_TOPICS:
        write(topic[2]+'.html',topic[4],topic[4]+'。'+topic[5]+topic[3],guide_article(topic))
    from case_articles import CASES, AVERAGE, article
    for case in (*CASES, AVERAGE):
        write(case["slug"] + ".html", case["title"], case["lead"], article(case))
