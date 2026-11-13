// Affiliate links of the study-material / course sections (PR).  The same file builds the section in the browser and in the static pages.
// Rakuten ID and Amazon tracking ID are the sites' public affiliate IDs (they sit in every affiliate URL on the web).
// The shapes follow the links this site has used since 2026-11-13: Rakuten Affiliate "hgc" link around a search page, Amazon search page with the tag, A8 text link with its 1x1 pixel.
// Rules (sokuhou-sites/docs/AFFILIATE_RULES.md, the CLAUDE.md of the 副業 folder): "PR" is shown, rel="nofollow sponsored noopener" target="_blank", the link text is words (never a URL),
// the Rakuten part and the Amazon part are separate paragraphs.
export const RAKUTEN_ID='583f273a.77c989b6.583f273b.0a6a5fff';
export const AMAZON_TAG='amazonmacs-22';
const A8_MAT='4BGJFS+FXCMIA+373C+7CX1E';
const A8_COURSE={label:'資格講座 | 資格スクエア',href:`https://px.a8.net/svt/ejp?a8mat=${A8_MAT}`,pixel:`https://www16.a8.net/0.gif?a8mat=${A8_MAT}`};
// the FP material of the same partner (A8 media console, media 試験日程カレンダー, material 228, checked 2026-11-13)
const A8_FP={label:'ファイナンシャルプランナー資格 | 資格スクエア',href:'https://px.a8.net/svt/ejp?a8mat=4BGJFS+FXCMIA+373C+7B7B6',pixel:'https://www14.a8.net/0.gif?a8mat=4BGJFS+FXCMIA+373C+7B7B6'};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const rakutenUrl=word=>`https://hb.afl.rakuten.co.jp/hgc/${RAKUTEN_ID}/?pc=${encodeURIComponent('https://search.rakuten.co.jp/search/mall/'+encodeURIComponent(word)+'/')}`;
export const amazonUrl=word=>`https://www.amazon.co.jp/s?k=${encodeURIComponent(word)}&tag=${AMAZON_TAG}`;
const REL='rel="nofollow sponsored noopener" target="_blank"';
// group -> {name (in the heading), word (the search words), course (A8 course link: only for the exams a course page of the partner covers)}
export const GROUPS={
 takken:{name:'宅建',word:'宅建 参考書',course:true},
 gyosei:{name:'行政書士',word:'行政書士 参考書',course:true},
 sharoshi:{name:'社会保険労務士',word:'社会保険労務士 テキスト',course:true},
 shindanshi:{name:'中小企業診断士',word:'中小企業診断士 テキスト',course:true},
 kaigo:{name:'介護福祉士',word:'介護福祉士 参考書'},
 nurse:{name:'看護師国家試験',word:'看護師国家試験 参考書'},
 kanri:{name:'管理業務主任者',word:'管理業務主任者 テキスト'},
 boki:{name:'日商簿記',word:'日商簿記 テキスト'},
 bokinet:{name:'簿記のネット試験',word:'簿記 ネット試験 問題集'},
 fp:{name:'FP技能検定',word:'FP技能検定 テキスト',course:true,link:'fp'},
 eiken:{name:'英検',word:'英検 過去問'},
 toeic:{name:'TOEIC',word:'TOEIC 公式問題集'},
 kanken:{name:'漢検',word:'漢検 問題集'},
 komuin:{name:'公務員試験',word:'公務員試験 参考書'},
 kyotsu:{name:'共通テスト',word:'共通テスト 過去問'},
 itpassport:{name:'ITパスポート',word:'ITパスポート 参考書'},
 fe:{name:'基本情報技術者',word:'基本情報技術者 参考書'},
 touroku:{name:'登録販売者',word:'登録販売者 テキスト'},
 koko:{name:'公立高校入試',word:'高校入試 過去問'},
 todai:{name:'東京大学の入試',word:'東京大学 過去問'},
 kyodai:{name:'京都大学の入試',word:'京都大学 過去問'},
 hokudai:{name:'北海道大学の入試',word:'北海道大学 過去問'},
 daigaku:{name:'国公立大学の入試',word:'国公立大学 過去問'}
};
// exam id / family -> group
export function groupFor(exam){
 if(!exam)return null;
 const id=exam.id,fam=exam.family||'';
 if(id==='boki-net-2026')return 'bokinet';
 if(id.startsWith('koko-'))return 'koko';
 if(id.startsWith('fp'))return 'fp';
 if(fam.startsWith('komuin'))return 'komuin';
 if(fam.startsWith('national')||fam.startsWith('public'))return 'daigaku';
 return {takken:'takken',gyosei:'gyosei',sharoshi:'sharoshi',shindanshi:'shindanshi',kaigo:'kaigo',nurse:'nurse',kanri:'kanri',boki:'boki',eiken:'eiken',toeic:'toeic',kanken:'kanken',kyotsu:'kyotsu',itpassport:'itpassport',fe:'fe',touroku:'touroku',todai:'todai',kyodai:'kyodai',hokudai:'hokudai'}[fam]||null;
}
// the section (an HTML string).  `idPrefix` makes the heading id unique in a page.
export function affiliateSection(group,idPrefix='pr'){
 const g=GROUPS[group];if(!g)return '';
 const A=g.link==='fp'?A8_FP:A8_COURSE;
 const course=g.course?`<p>${g.name}の講座をオンラインで探している方は、資格スクエアの講座ページを見てみてください。講座の内容や料金は、申し込む前に運営会社のページで確かめておきましょう。</p><p><a href="${A.href}" ${REL}>${A.label}</a><img border="0" width="1" height="1" src="${A.pixel}" alt=""></p>`:'';
 return `<section class="ed-pr" aria-labelledby="${idPrefix}-title"><div class="ed-section-title"><div><span class="ed-kicker">PR・広告</span><h2 id="${idPrefix}-title">【PR】${esc(g.name)}の${g.course?'勉強を始めるなら':'参考書・問題集を探すなら'}</h2></div></div><p class="small-note">この項目には、広告（PR）が含まれます。リンク先の販売ページで購入されると、当サイトに紹介料が入ることがあります。</p>${course}${g.course?'<h3>参考書・問題集を探すなら</h3>':''}<p>楽天市場では、<a href="${rakutenUrl(g.word)}" ${REL}>「${esc(g.word)}」を探す</a>ことができます。</p><p>Amazonでも、<a href="${amazonUrl(g.word)}" ${REL}>「${esc(g.word)}」を探す</a>ことができます。</p></section>`;
}
