// The pages of the old site (33 URLs) that stay at their address, the pages every site needs (about, contact, privacy) and the 301s.
// Bodies of the old articles are in legacy/<slug>.json (converted once from the old generator's content; evergreen text only).  Everything that depends on the day
// (the lists of coming dates) is made here from schedule/registry.json at build time, so it is right on the day the site is built (the site is built again every day).
import {readFile} from 'node:fs/promises';
import {affiliateSection} from '../dist/affiliate.js';

// Equivalent single-exam pages go to the detail page of the same exam (HTTP 301).
export const redirects={
 '/takken/':'/exams/takken/','/gyosei/':'/exams/gyosei/','/sharoshi/':'/exams/sharoshi/',
 '/kangoshi/':'/exams/nurse/','/kaigo-fukushi/':'/exams/kaigo/',
 '/kyotsu/':'/exams/kyotsu/','/kyotsu-tsuishi/':'/exams/kyotsu-tsuishi-2027/',
 '/tokushu-nyushi/':'/nyushi/'
};
export const SITE_NAME='資格・試験への道';
export const OPERATOR='資格・試験への道運営部';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const W=['日','月','火','水','木','金','土'];
export const jpDate=iso=>{const d=new Date(iso+'T00:00:00Z');return `${d.getUTCFullYear()}年${d.getUTCMonth()+1}月${d.getUTCDate()}日（${W[d.getUTCDay()]}）`;};
const TYPE={deadline:'申込締切',exam:'試験日',result:'結果発表等'};

// scope strings: 'all' | 'cat:school' | 'fam:boki' | 'pre:koko-' | 'ids:a,b'   (an array = any of them)
export function inScope(exam,scope){
 return [].concat(scope).some(s=>s==='all'||(s.startsWith('cat:')&&exam.category===s.slice(4))||(s.startsWith('fam:')&&(exam.family===s.slice(4)||exam.family.startsWith(s.slice(4)+'-')))||(s.startsWith('pre:')&&exam.id.startsWith(s.slice(4)))||(s.startsWith('ids:')&&s.slice(4).split(',').includes(exam.id)));
}
const FEATURED='ids:takken,gyosei,sharoshi,nurse,kaigo,kanri,shindanshi,eiken,toeic,boki,fp,kyotsu,komuin-sogo,itpassport-cbt';
// per page: parent (breadcrumb), art picture, related exams (cards), live list (coming dates made from the registry), pr group (affiliate section)
export const config={
 'boki-net':{parent:'/yomimono/',art:'decided',related:['ids:boki-net-2026,boki,boki-175'],live:{scope:'ids:boki,boki-173,boki-175',types:['exam']},pr:'bokinet'},
 'boki':{parent:'/schedule/',art:'decided',related:['ids:boki,boki-173,boki-175,boki-net-2026'],live:{scope:'fam:boki',types:['exam']},pr:'boki'},
 'cbt':{parent:'/yomimono/',art:'decided',related:['ids:itpassport-cbt,fe-cbt,boki-net-2026,fp23-jafp-2026,fp23-kinzai-2026,touroku-tokyo-2026']},
 'corrections':{parent:'/',art:'decided',related:[FEATURED]},
 'deadlines':{parent:'/schedule/',art:'decided',live:{scope:'all',types:['deadline'],limit:40,heading:'これから締切が来る申込'}},
 'eiken':{parent:'/schedule/',art:'decided',related:['fam:eiken'],live:{scope:'fam:eiken',types:['deadline','exam','result'],limit:14},pr:'eiken'},
 'fees':{parent:'/yomimono/',art:'decided',related:[FEATURED]},
 'flow':{parent:'/yomimono/',art:'prepared',related:[FEATURED]},
 'fp':{parent:'/schedule/',art:'decided',related:['fam:fp'],live:{scope:'fam:fp',types:['deadline','exam','result'],limit:12},pr:'fp'},
 'goukaku-ritsu':{parent:'/yomimono/',art:'decided',related:['ids:takken,gyosei,sharoshi,kaigo,nurse'],pr:'takken'},
 'kokkoritsu':{parent:'/nyushi/',art:'family',related:['cat:university'],live:{scope:'cat:university',types:['deadline','exam','result'],limit:14,heading:'これから先の日程'},pr:'daigaku'},
 'koko':{parent:'/nyushi/',art:'family',related:[],list:'pre:koko-',pr:'koko'},
 'komuin':{parent:'/schedule/',art:'decided',related:['fam:komuin'],live:{scope:'fam:komuin',types:['deadline','exam','result'],limit:10},pr:'komuin'},
 'method':{parent:'/yomimono/',art:'decided',related:[FEATURED]},
 'minkan':{parent:'/schedule/',art:'decided',related:['fam:toeic','fam:kanken','ids:itpassport-cbt,fe-cbt'],live:{scope:['ids:toeic,toeic-20261206,toeic-20261219,toeic-20270124,toeic-20270214,toeic-20270306,toeic-20270314','fam:kanken'],types:['deadline','exam'],limit:16},pr:'toeic'},
 'nendo':{parent:'/yomimono/',art:'decided',related:[FEATURED]},
 'nyushi':{parent:'/',art:'family',children:'/nyushi/',childrenHeading:'入試のくわしい解説',related:['ids:kyotsu,kyotsu-tsuishi-2027,todai-2027,kyodai-2027,hokudai-zenki-2027'],live:{scope:['cat:university','cat:school'],types:['deadline','exam','result'],limit:24,heading:'これから先の入試の日程'},pr:'kyotsu'},
 'postmark':{parent:'/yomimono/',art:'decided',related:['ids:takken,gyosei,sharoshi,kangoshi,nurse,kaigo']},
 'results':{parent:'/schedule/',art:'prepared',related:[],live:{scope:'all',types:['result'],limit:30,heading:'これから先の合格発表・結果の日'}},
 'schedule':{parent:'/',art:'discover',related:[],list:'all',children:'/schedule/',childrenHeading:'試験ごとのまとめと、日付の一覧'},
 'takken-junbi':{parent:'/yomimono/',art:'decided',related:['ids:takken'],pr:'takken'},
 'yama':{parent:'/schedule/',art:'compare',related:[FEATURED],live:{scope:'all',types:['exam'],limit:30,heading:'これから先の試験日'}},
 'yomimono':{parent:'/',art:'discover',related:[],children:'/yomimono/',childrenHeading:'特集の一覧'},
 'zenki-koki':{parent:'/nyushi/',art:'family',related:['ids:todai-2027,kyodai-2027,hokudai-zenki-2027,hokudai-koki-2027,national-zenki-2027,national-koki-2027'],pr:'daigaku'}
};
const PARENT_TITLE={'/schedule/':'資格試験日程一覧','/yomimono/':'特集','/nyushi/':'入試カレンダー','/':null};
const KINDS=['日程・内容の誤りのご指摘','ご意見・ご要望','その他'];
export async function loadLegacy(root){
 const out={};
 for(const slug of Object.keys(config)){try{out[slug]=JSON.parse(await readFile(new URL('legacy/'+slug+'.json',root),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}}
 return out;
}
const examCard=e=>`<a href="/exams/${e.id}/"><span>${esc(e.field)} · ${esc(e.edition)}</span><strong>${esc(e.name)}</strong><b>›</b></a>`;
const fmtTime=r=>r.time?`${r.time}${r.type==='deadline'?'まで':''}`:'';
export function liveSection(registry,live,today){
 const ids=new Map(registry.exams.filter(e=>inScope(e,live.scope)).map(e=>[e.id,e]));
 const rows=registry.rows.filter(r=>ids.has(r.exam)&&live.types.includes(r.type)&&r.date>=today&&r.primary!==false).sort((a,b)=>a.date.localeCompare(b.date)||(a.time||'').localeCompare(b.time||'')).slice(0,live.limit||20);
 const heading=live.heading||'これから先の日程';
 if(!rows.length)return `<section class="ed-section"><h2>${esc(heading)}</h2><p>いま掲載している、${esc(jpDate(today))}より先の日程はありません。日程が発表されたら追加します。</p></section>`;
 const trs=rows.map(r=>{const e=ids.get(r.exam);return `<tr><td>${esc(jpDate(r.date))}${r.time?`<br><small>${esc(fmtTime(r))}</small>`:''}</td><td><a href="/exams/${e.id}/">${esc(e.name)}</a><br><small>${esc(e.edition)}</small></td><td>${esc(TYPE[r.type])}${r.planned?'（予定）':''}${r.label&&r.label!=='試験日'?`<br><small>${esc(r.label)}</small>`:''}</td></tr>`;}).join('');
 return `<section class="ed-section"><h2>${esc(heading)}</h2><p>${esc(jpDate(today))}以降の日程です。日付の早い順に表示しています。${live.types.length===1&&live.types[0]==='result'?'結果の確かめ方は':'申込の方法や時刻は'}、試験ごとのページで確かめられます。</p><div class="tablewrap"><table class="ed-table"><thead><tr><th>日付</th><th>試験・実施回</th><th>区分</th></tr></thead><tbody>${trs}</tbody></table></div></section>`;
}
function relatedSection(registry,related,heading='日程と申し込みの案内'){
 const exams=registry.exams.filter(e=>inScope(e,related));
 if(!exams.length)return '';
 return `<section class="ed-other"><h2>${esc(heading)}</h2><div>${exams.slice(0,24).map(examCard).join('')}</div></section>`;
}
function listSection(registry,mode){
 const groups=mode==='all'?[['資格・検定','cat:qualification'],['大学入試','cat:university'],['公立高校入試','cat:school']]:[['都道府県別の公立高校入試',mode]];
 return groups.map(([name,scope])=>{const exams=registry.exams.filter(e=>inScope(e,scope));return `<section class="ed-section"><h2>${esc(name)}（${exams.length}件）</h2><ul class="ed-link-list">${exams.map(e=>`<li><a href="/exams/${e.id}/">${esc(e.name)}</a><span>${esc(e.edition)}</span></li>`).join('')}</ul></section>`;}).join('');
}
function childrenSection(legacy,parent,heading,self){
 const items=Object.values(legacy).filter(d=>config[d.slug]&&config[d.slug].parent===parent&&d.slug!==self);
 if(!items.length)return '';
 return `<section class="ed-section"><h2>${esc(heading)}</h2><div class="ed-card-grid">${items.map(d=>`<div class="ed-card"><h3><a href="/${d.slug}/">${esc(d.h1)}</a></h3><p>${esc(d.answer)}</p></div>`).join('')}</div></section>`;
}
export function legacyMain({slug,data,registry,today,prefix,legacy}){
 const c=config[slug];
 const parentTitle=PARENT_TITLE[c.parent];
 const crumbs=[['トップ','/']];if(parentTitle)crumbs.push([parentTitle,c.parent]);
 const bc=crumbs.map(([t,h])=>`<a href="${h}">${esc(t)}</a>`).join('<span aria-hidden="true">›</span>')+`<span aria-hidden="true">›</span><span aria-current="page">${esc(data.h1)}</span>`;
 const sections=data.sections.map(s=>`<section class="ed-section legacy-section">${s.h2?`<h2>${esc(s.h2)}</h2>`:''}${s.html}</section>`).join('');
 const live=c.live?liveSection(registry,c.live,today):'';
 const list=c.list?listSection(registry,c.list):'';
 const articles=c.children?childrenSection(legacy,c.children,c.childrenHeading||'あわせて読みたい',slug):'';
 const pr=c.pr?affiliateSection(c.pr,'pr-'+slug):'';
 const related=(c.related||[]).length?relatedSection(registry,c.related):'';
 const nav=`<section class="ed-section"><h2>あわせて読みたい</h2><p><a href="/guides/decided/">受ける試験の日程を探す</a>　<a href="/guides/compare/">試験の予定を比べる</a>　<a href="/yomimono/">特集の一覧</a>　<a href="/schedule/">掲載している試験の一覧</a>　<a href="/deadlines/">申込の締切が近い試験</a>　<a href="/results/">合格発表の日</a>　<a href="/nyushi/">入試カレンダー</a></p></section>`;
 const crumbData=crumbs.map(([t,h])=>({name:t,url:h}));crumbData.push({name:data.h1,url:`/${slug}/`});
 return {html:`<article class="exam-detail legacy-page" data-theme="cream"><nav class="ed-breadcrumb" aria-label="現在のページ">${bc}</nav><header class="ed-hero"><div><span class="ed-eyebrow">${c.parent==='/yomimono/'?'受験の前の読みもの':'試験の日程と準備'}</span><h1 id="legacy-title">${esc(data.h1)}</h1><p class="ed-intro">${esc(data.answer||data.description)}</p></div><figure><img src="${prefix}/assets/guide-${c.art}.webp" width="1536" height="1024" alt="" decoding="async"></figure></header>${live}${sections}${list}${articles}${pr}${related}${nav}</article>`,crumbs:crumbData};
}

// ---- site-wide pages -------------------------------------------------------------------------------------------------
export const siteWide={
 about:{title:'運営者情報',description:`${SITE_NAME}の運営者、サイトの目的、日程の確かめ方、免責事項をご案内します。`,h1:'運営者情報',intro:'このサイトを運営している者と、日程の扱い方をご案内します。',body:()=>`<section class="ed-section"><h2>サイトの概要</h2><dl class="ed-info"><dt>サイト名</dt><dd>${SITE_NAME}</dd><dt>運営者</dt><dd>${OPERATOR}</dd><dt>連絡先</dt><dd><a href="/contact/">お問い合わせフォーム</a></dd><dt>目的</dt><dd>資格試験と入学試験の、申込・出願の期間、試験日、合格発表の日を、確かめた日付で表示し、受験する方が締切を見落とさないようにすることです。</dd><dt>日程の出どころ</dt><dd>試験団体・省庁・教育委員会・大学などの発表をもとにしています。各日程には、出典と確認日を添えています。確かめられなかった日付は「未確認」と表示し、日付を推測で補うことはしません。</dd><dt>更新</dt><dd>日程の発表や変更を見つけたら、出典を確かめて入れ替えます。年度が替わるたびに、日付を取り直します。直した内容は<a href="/corrections/">訂正と更新の記録</a>に残します。</dd></dl></section><section class="ed-section"><h2>免責事項</h2><p>日程は、試験団体や教育委員会が変更することがあります。申し込む前に、必ず主催者の最新の案内を確かめておきましょう。</p><p>このサイトは、日付と制度の事実を伝えるものです。個々の受験について、出願先や受験資格の判断はしません。掲載した情報を使って行った行動の結果については、責任を負えません。</p></section><section class="ed-section"><h2>関連するページ</h2><p><a href="/method/">日程の調べ方と出典</a>　<a href="/privacy/">プライバシーポリシー</a>　<a href="/contact/">お問い合わせ</a></p></section>`},
 contact:{title:'お問い合わせ',description:`${SITE_NAME}へのお問い合わせ先です。日程の誤りのご指摘、ご意見・ご要望をお送りいただけます。`,h1:'お問い合わせ',intro:'日程の誤りのご指摘、ご意見・ご要望は、次のフォームからお送りください。内容によっては、お返事に日数がかかったり、お返事できなかったりします。',body:()=>`<section class="ed-section"><form class="cf" action="/contact/send.php" method="post" accept-charset="UTF-8"><label>お問い合わせの種類<select name="kind" required>${KINDS.map((k,i)=>`<option value="${esc(k)}"${i===0?' selected':''}>${esc(k)}</option>`).join('')}</select></label><label>ご用件<small>日本語で、5文字以上、2000文字以内。</small><textarea name="message" required minlength="5" maxlength="2000" placeholder=""></textarea></label><label>該当するページのアドレス（わかれば）<input type="text" name="page" maxlength="200" placeholder="例：https://shiken-nittei.com/exams/takken/" autocomplete="off"></label><label>お返事がほしいときのメールアドレス<small>省略できます。いただいても、お返事できない場合があります。</small><input type="email" name="email" maxlength="200" autocomplete="email"></label><div class="cf-hp" aria-hidden="true"><label>この欄は空のままにしてください<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div><button type="submit">送信する</button><p class="cf-note">送信すると、<a href="/privacy/">プライバシーポリシー</a>の内容に同意したものとみなします。いただいた内容は、サイトの改善と、お返事のためだけに使います。</p></form></section>`},
 privacy:{title:'プライバシーポリシー',description:`${SITE_NAME}のプライバシーポリシーです。取得する情報、ブラウザへの保存、アクセス解析、広告の扱いをご案内します。`,h1:'プライバシーポリシー',intro:'取得する情報と、ブラウザに保存する内容、広告のリンクの扱いをご案内します。',body:()=>`<section class="ed-section"><h2>取得する情報</h2><p>当サイトには、会員登録などの機能がありません。お問い合わせの際にいただいた内容やメールアドレスは、サイトの改善とお返事のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。</p></section><section class="ed-section"><h2>お問い合わせフォームで取得する情報</h2><p>お問い合わせフォームでは、ご用件の内容と、任意で該当ページのアドレス、メールアドレスをお預かりします。あわせて、迷惑なメッセージを防ぐため、送信元のIPアドレスを、毎日変わる値で変換した記号（元のIPアドレスには戻せません）と、ブラウザの種類を記録します。これらは、サイトの改善とお返事のためだけに使い、法令に基づく場合を除いて、第三者へ提供しません。</p></section><section class="ed-section" id="storage"><h2>保存した試験について</h2><p>試験の保存や、申し込みを済ませたことのチェックは、いまお使いのブラウザに保存します。このサイトのプログラムから、保存した内容をサーバーへ送ることはありません。</p><p>別の端末には引き継がれません。ブラウザのデータを消したり、プライベートモードを閉じたりすると、保存した内容が消えることがあります。共有の端末では、使い終えたあとに保存した内容をご確認ください。</p></section><section class="ed-section"><h2>アクセス解析</h2><p>当サイトは、Google アナリティクスなどの外部のアクセス解析ツールを使っていません。代わりに、ページの利用の様子を数えるための小さなスクリプトを、当サイトの中だけで動かしています。</p><p>数えるのは、訪問の始まり、紹介リンクや外部サイトへのリンクを押した回数（種類だけで、リンク先もページも記録しません）、ページを開いていた時間とその訪問で見たページ数（おおまかな区間）、7日以内にこのブラウザで来たことがあるかどうかです。クッキーは使いません。お名前・IPアドレス・端末を見分けるための番号は、取得も保存もしません。</p><p>「7日以内に来たことがあるか」を知るため、お使いのブラウザの中にだけ、前に開いた時刻と、この訪問で見たページ数を残します。この値は当サイトのサーバーへは送られません。ブラウザの設定でサイトデータを消せば、なくなります。ブラウザの「トラッキング拒否（Do Not Track）」を有効にしている場合は、数えません。</p></section><section class="ed-section"><h2>アフィリエイトについて</h2><p>当サイトの一部のページには、書籍や講座などの紹介リンク（アフィリエイトリンク）があります。該当する場所には「PR」と表示しています。リンク先で商品やサービスが購入・申し込みされると、当サイトの運営者に報酬が支払われることがあります。リンクの有無や報酬の大小で、日程や解説の内容を変えることはしません。</p><p>当サイトが参加しているのは、楽天アフィリエイト、Amazonアソシエイト、A8.netです。</p><p>Amazonのアソシエイトとして、${SITE_NAME}は適格販売により収入を得ています。</p></section><section class="ed-section"><h2>免責事項・著作権</h2><p>免責事項と情報の出どころは、<a href="/about/">運営者情報</a>に記載しています。</p></section><section class="ed-section"><h2>お問い合わせ</h2><p>このポリシーに関するお問い合わせは、<a href="/contact/">お問い合わせフォーム</a>からお願いします。</p><h2>改定</h2><p>このポリシーは、必要に応じて見直し、変更します。変更後の内容は、このページに載せた時点から効力を持ちます。</p></section>`},
 thanks:{title:'送信しました',description:'お問い合わせを受け付けました。',h1:'送信しました',intro:'お問い合わせを受け付けました。ありがとうございます。内容は確認して、サイトの改善に役立てます。',noindex:true,body:()=>`<section class="ed-section"><p>お返事は、できない場合があります。</p><p><a class="text-link" href="/">トップページへ戻る ›</a></p></section>`}
};
export function siteWideMain(key,prefix){
 const p=siteWide[key];
 const bc=`<a href="/">トップ</a><span aria-hidden="true">›</span><span aria-current="page">${esc(p.h1)}</span>`;
 return {html:`<article class="exam-detail legacy-page" data-theme="cream"><nav class="ed-breadcrumb" aria-label="現在のページ">${bc}</nav><header class="ed-hero"><div><h1 id="legacy-title">${esc(p.h1)}</h1><p class="ed-intro">${esc(p.intro)}</p></div><figure><img src="${prefix}/assets/guide-decided.webp" width="1536" height="1024" alt="" decoding="async"></figure></header>${p.body()}</article>`,crumbs:[{name:'トップ',url:'/'},{name:p.h1,url:key==='thanks'?'/contact/thanks.html':`/${key}/`}]};
}
