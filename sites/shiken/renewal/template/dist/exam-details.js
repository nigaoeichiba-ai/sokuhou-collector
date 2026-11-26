import {renderDetailDates} from './detail-dates.js';
import {CHECKED_AT,scheduleMeta,scheduleSources,eventLabel as officialEventLabel,fieldStatusLabel} from './official-schedule.js';
import {sourceHtml,eventSourceHtml,futureHtml} from './schedule-ui.js';
import {examDetails,detailPhases} from './exam-details-data.js';
import {affiliateSection,groupFor} from './affiliate.js';
let detailAbort;
export function mountExam(id,params,c){
 detailAbort?.abort();detailAbort=new AbortController();const signal=detailAbort.signal;
 const {state,exams,events,formatDate,esc,checklist,updateProgress}=c;
 const base=exams.find(e=>e.id===id),meta=examDetails[id];if(!base||!meta){location.hash='#/guide/decided';return;}
 // the TOEIC parent page (2026-11-27): once its own round stops taking applications, it shows the next round of the series that still does (sid = the round whose dates are shown); a link to one of the old round's events keeps the old round
 const SERIES={toeic:/^toeic-\d{8}$/};
 const sid=(()=>{const re=SERIES[id];if(!re)return id;const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),own=events.filter(e=>e.exam===id);
  if(own.some(e=>(e.type==='deadline'&&e.date>=day)||e.id===params.get('event')))return id;
  const next=events.filter(e=>re.test(e.exam)&&e.type==='deadline'&&e.date>=day).sort((a,b)=>a.date.localeCompare(b.date))[0];return next?next.exam:id;})();
 const exam=sid===id?base:{...base,edition:exams.find(e=>e.id===sid).edition};
 const root=document.querySelector('#exam-page'),ownEvents=events.filter(e=>e.exam===sid).sort((a,b)=>a.date.localeCompare(b.date));
 const eventLabel=e=>officialEventLabel(e)+(e.planned?'（予定）':'');
 // the page's own dates in the first view (2026-11-20): pages of the same kind (a prefecture, a round) no longer open with the same sentences; only for the pages whose copy is made from a shared pattern
 // a parent page (TOEIC, Eiken, Boki, FP) lists its rounds with their dates and links to each (the round pages are noindex,follow; the dates stay findable on the parent)
 const ROUND_RE=/^(toeic-\d{8}|eiken-\d{4}-\d|boki-\d{3}|fp1-gakka-\d{8}|fp1-jafp-\d{4}|fp23-(?:jafp|kinzai)-\d{4})$/;
 const roundsHtml=()=>{const rs=exams.filter(e=>e.family===exam.family&&e.id!==sid&&(ROUND_RE.test(e.id)||(sid!==id&&e.id===id))&&!ROUND_RE.test(id));if(!rs.length)return '';return `<section class="ed-rounds"><div class="ed-section-title"><h2>${esc(exam.short)}の各回の日程</h2></div><ul>${rs.map(r=>{const ev=events.filter(x=>x.exam===r.id).sort((x,y)=>x.date.localeCompare(y.date)).slice(0,4).map(x=>eventLabel(x)+' '+formatDate(x.date,true)+(x.time?' '+x.time:''));const label=esc(r.name+'（'+r.edition+'）');return `<li>${r.id===id?label:`<a href="#/exam/${r.id}">${label}</a>`}：${ev.map(esc).join('、')}</li>`;}).join('')}</ul></section>`;};
 const ownLead=()=>{if(!meta.autoLead||!ownEvents.length)return '';if(id.startsWith('koko-')){const first=ty=>ownEvents.find(e=>e.type===ty),last=ty=>[...ownEvents].reverse().find(e=>e.type===ty),f=(e,w)=>e?`${w}が${formatDate(e.date,true)}(${esc(e.label)})`:'';const parts=[f(first('deadline'),'最も早い出願の締切'),f(first('exam'),'最も早い検査'),f(last('result'),'最後の結果発表')].filter(Boolean);return `<p class="ed-own-dates">${esc(exam.name+'（'+exam.edition+'）')}の日程は、${parts.join('、')}です。選抜の日程は全部で${ownEvents.length}件載せています。</p>`;}
 const shown=ownEvents.slice(0,6).map(e=>eventLabel(e)+' '+formatDate(e.date,true)+(e.time?' '+e.time:''));return `<p class="ed-own-dates">${esc(exam.name+'（'+exam.edition+'）')}の主な日付は、${shown.map(esc).join('、')}${ownEvents.length>6?'、ほか':''}です。</p>`;};
 const dateText=e=>formatDate(e.date,true)+(e.time?' '+e.time+(e.type==='deadline'?'まで':''):'');
 const applyOpen=(()=>{const v=scheduleMeta[sid];if(!v?.applyPage?.url)return false;const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  if((v.availability?.suspensions||[]).some(x=>x.start<=today&&(!x.end||x.end>=today)))return false;
  if(v.fields.deadline==='rolling')return true;
  if(v.fields.deadline==='regional')return ownEvents.some(e=>e.type==='exam'&&e.date>today);
  const starts=(v.application||[]).map(a=>a.start).filter(Boolean).sort(),opens=!starts.length||starts[0]<=today;
  return opens&&ownEvents.some(e=>e.type==='deadline'&&e.date>=today);})();
 const applySection=applyOpen?`<section class="ed-apply" id="exam-${id}-apply" aria-labelledby="exam-${id}-apply-title"><div class="ed-section-title"><div><span class="ed-kicker">準備ができたら</span><h2 id="exam-${id}-apply-title">申し込みのページへ</h2></div></div><p>${esc(scheduleMeta[sid].applyPage.note||'受ける回と受け方を確かめたら、主催者の申し込みのページへ進めます。')}別のサイトが開きます。</p><a class="primary ed-apply-button" href="${scheduleMeta[sid].applyPage.url}" target="_blank" rel="noopener nofollow">申し込みのページへ <span aria-hidden="true">↗</span></a></section>`:'';
 const todayJ=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const siblings=exams.filter(e=>exam.field==='高校入試'?e.field==='高校入試':e.family===exam.family&&(sid===id||e.id!==id));
 const key=s=>`exam-${id}-${s}`;
 const nav=[['dates','日程'],['flow','受験までの流れ'],['packing','持ち物・当日の流れ'],['faq','よくある質問']];
 const verified=scheduleMeta[sid];
 root.dataset.theme=meta.theme;
 root.innerHTML=`<nav class="ed-breadcrumb" aria-label="現在のページ"><a href="#/">トップ</a><span aria-hidden="true">›</span><a href="#/guide/decided">試験を探す</a><span aria-hidden="true">›</span><span>${exam.short}</span></nav>
 <header class="ed-hero"><div><span class="ed-eyebrow">${exam.field} の試験案内</span><h1 id="exam-title">${sid!==id?exam.name+'の次の回（'+exam.edition+'）':exams.filter(e=>e.name===exam.name).length>1?exam.name+'（'+exam.edition+'）':exam.name}</h1><p class="ed-scope">${meta.scope}</p><p class="ed-intro">${meta.intro}</p>${ownLead()}<div class="ed-hero-actions"><button class="save-button" data-save="${id}" aria-pressed="${state.saved.includes(id)}">${state.saved.includes(id)?'✓ 保存済み':'♧ 保存'}</button><span>保存すると、あとから見返せます。</span></div></div><figure><img src="/assets/guide-${meta.art}.webp" width="1536" height="1024" alt="${meta.art==='family'?'親子で受験の予定を確認する様子':meta.art==='prepared'?'試験当日の持ち物をそろえる様子':'明るい部屋で試験の準備を相談する様子'}" decoding="async"></figure></header>
 ${siblings.length>1?`<div class="ed-round-selector"><label>${exam.field==='高校入試'?'地域を選ぶ':'実施回・方式を選ぶ'}<select id="exam-round-select">${siblings.map(e=>`<option value="${e.id}" ${e.id===sid?'selected':''}>${e.name}｜${e.edition}</option>`).join('')}</select></label></div>`:''}
 <nav class="ed-page-nav" aria-label="このページの内容">${nav.map(([section,label])=>`<button data-detail-section="${section}">${label}<span aria-hidden="true">↓</span></button>`).join('')}</nav>
 ${renderDetailDates({id:sid,meta,ownEvents,params,key,dateText,formatDate,eventLabel,esc})}
 <div class="ed-content-layout"><div class="ed-main"><section id="${key('flow')}" class="ed-flow-section" aria-labelledby="${key('flow-title')}"><div class="ed-section-title"><div><span class="ed-kicker">準備の順番が分かるように</span><h2 id="${key('flow-title')}">申し込みから当日までの流れ</h2></div></div><p class="ed-section-intro">いまのご自身に近いところから、ご覧ください。済んでいることは、下のチェックに残せます。</p><ol class="ed-timeline">${meta.steps.map(([when,title,body],i)=>`<li><span class="ed-step-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><div><span class="ed-when">${when}</span><h3>${title}</h3><p>${body}</p></div></li>`).join('')}</ol></section>
 <section class="ed-check-section" aria-labelledby="${key('check-title')}"><div class="ed-section-title"><div><span class="ed-kicker">確認したことを、ひとつずつ</span><h2 id="${key('check-title')}">いま、確かめておきたいこと</h2></div></div><div class="ed-phase-tabs" role="group" aria-label="準備を確認する時期">${detailPhases.map(p=>`<button data-detail-phase="${p.id}" aria-pressed="false">${p.label}</button>`).join('')}</div><div class="ed-check-caption"><h3 id="ed-phase-title"></h3><span id="ed-check-count" aria-live="polite"></span></div><div id="ed-check-items"></div><p class="ed-disclaimer">チェックはこのブラウザに保存されます。主催者への申し込み・支払いは別に行ってください。</p></section>
 <section id="${key('packing')}" class="ed-packing" aria-labelledby="${key('packing-title')}"><div class="ed-section-title"><div><span class="ed-kicker">前日までに見ておくと安心です</span><h2 id="${key('packing-title')}">持ち物と、当日の過ごし方</h2></div></div><p class="ed-section-intro">持っていくものは試験ごとに違います。ここを手がかりに、ご自身の受験案内と照らし合わせてそろえてみましょう。</p><div class="ed-kit-grid">${meta.kit.map(([title,body],i)=>`<article><span class="ed-kit-symbol" aria-hidden="true">${['▤','✓','⌁'][i]}</span><h3>${title}</h3><p>${body}</p></article>`).join('')}</div><div class="ed-day-flow"><h3>当日は、この順番で</h3><ol>${meta.day.map((s,i)=>`<li><span>${i+1}</span><p>${s}</p></li>`).join('')}</ol><p>当日の注意事項は、申し込みの前に主催者の最新の案内もご確認ください。</p></div></section>
 <section class="ed-after"><span class="ed-kicker">受験、おつかれさまでした</span><h2>試験が終わったあとも</h2><p>${meta.after}</p><a class="text-link" href="#/guide/${id==='kyotsu'?'family':'prepared?exam='+id}">${id==='kyotsu'?'学校ごとの予定をメモする':'試験後の準備チェックを見る'} ›</a></section>
 <section id="${key('faq')}" class="ed-faq" aria-labelledby="${key('faq-title')}"><h2 id="${key('faq-title')}">気になることを、もう少し</h2>${meta.faq.map(([q,a])=>`<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</section>
 </div><aside class="ed-sidebar"><div class="ed-adviser"><span class="ed-adviser-mark">ひとこと</span><h2>${meta.advice}</h2><p>${meta.adviceBody}</p></div><div class="ed-official-card"><h2>申し込むときは、主催者の最新の案内も</h2><p>このページの試験・受け方が、ご自身の申し込みと合っているか確かめてからお進みください。</p><label class="applied-label"><input type="checkbox" data-applied="${id}" ${state.applied.includes(id)?'checked':''}>申し込みを済ませた</label><p class="small-note">ご自身の確認用のチェックです。</p></div><div class="ed-focus"><h2>申し込み前の確認に</h2><ul>${meta.focus.map(t=>`<li>${t}</li>`).join('')}</ul></div><a class="ed-compare-link" href="#/guide/compare">ほかの試験も受ける予定の方へ<span>日程を並べて確認できます ›</span></a></aside></div>
 ${affiliateSection(groupFor(exam),key('pr'))}
 ${applySection}
 ${roundsHtml()}<section class="ed-other"><div class="ed-section-title"><h2>ほかの試験も見てみる</h2><a href="#/guide/decided">試験を探す ›</a></div><div>${exams.filter(e=>e.id!==id).map(e=>`<a href="#/exam/${e.id}"><span>${e.field}</span><strong>${e.short}</strong><b aria-hidden="true">›</b></a>`).join('')}</div></section>`;
 const $=s=>root.querySelector(s);
 $('#exam-round-select')?.addEventListener('change',e=>location.hash='#/exam/'+e.target.value,{signal});
 const phaseChecks={
  apply:[[meta.focus[0],'ご自身が受ける回・区分に合っているか、公式案内で確かめましょう。'],[meta.focus[1],'申込方法や必要な手続きを、案内と照らし合わせてみましょう。'],['申し込みと支払いの期限を確認する','登録・提出・支払いなど、期限が分かれていないかも見ておきましょう。']],
  ticket:[['受付の状況を確かめる','申込窓口やマイページの案内で、手続きが済んだことを確認しましょう。'],['受験票の受け取り方・準備方法を確認する',meta.steps[2][2]],['受験票の会場・時刻を確認する','会場が分かったら、交通手段や出発の時刻も考えておきたいですね。']],
  day:meta.kit.map(([title,sub])=>[title+'を確認する',sub]),
  after:[['結果の確認方法を見ておく',meta.after],['その後に必要な手続きを確認する','証明書や登録、大学への出願など、ご自身に必要な案内を見ておきましょう。']]
 };
 const progress=()=>{const all=[...root.querySelectorAll('[data-check]')];$('#ed-check-count').textContent=`${all.filter(x=>x.checked).length} / ${all.length} 確認済み`;updateProgress();};
 const setPhase=phase=>{root.querySelectorAll('[data-detail-phase]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.detailPhase===phase)));$('#ed-phase-title').textContent=detailPhases.find(p=>p.id===phase).label+'に';$('#ed-check-items').innerHTML=checklist(`detail-${id}-${phase}`,phaseChecks[phase]);progress();};
 const selectedEvent=ownEvents.find(e=>e.id===params.get('event'));const initial=params.get('stage')||(selectedEvent?.type==='result'?'after':selectedEvent?.type==='exam'?'day':'apply');setPhase(detailPhases.some(p=>p.id===initial)?initial:'apply');
 root.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.detailPhase)setPhase(b.dataset.detailPhase);if(b.dataset.detailSection)document.getElementById(key(b.dataset.detailSection))?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});},{signal});
 root.addEventListener('change',e=>{if(e.target.matches('[data-check]'))progress();},{signal});
 if(selectedEvent)$('.ed-date-tools').open=true;
 const word=e=>e.edition.replace('実施回','');
 document.title=(sid===id?meta.seoTitle:meta.seoTitle?.replace(word(base),word(exam)))||exam.name+'｜'+exam.edition+'の日程・受験準備｜資格・試験への道';
 const upcoming=t=>ownEvents.filter(e=>e.type===t&&e.date>=todayJ).sort((x,y)=>x.date.localeCompare(y.date))[0];
 const dlE=upcoming('deadline'),exE=upcoming('exam'),reE=upcoming('result'),rolling=scheduleMeta[sid]?.fields?.deadline==='rolling',bits=[dlE?'申込の締切は'+formatDate(dlE.date,true)+(dlE.time?' '+dlE.time+'まで':''):'',exE?'試験日は'+formatDate(exE.date,true):'',reE?'合格発表は'+formatDate(reE.date,true):''].filter(Boolean);
 document.querySelector('meta[name="description"]').content=meta.seoDesc||(bits.length?(sid===id?exam.name+'（'+exam.edition+'）の':exam.name+'で次に申し込めるのは'+exam.edition+'です。')+bits.join('、')+'。申し込みから当日までの流れと持ち物を、確認日つきでまとめています。':rolling?exam.name+'（'+exam.edition+'）は、受ける日と会場を選んで予約する試験です。申し込みから当日までの流れと、受けられない期間を、確認日つきでまとめています。':(exam.name+'（'+exam.edition+'）の日程と申し込みから当日までの準備をご案内します。確認日と、公表状況を分けて掲載しています。'));
}
