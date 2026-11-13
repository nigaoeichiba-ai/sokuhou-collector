import {renderDetailDates} from './detail-dates.js';
import {CHECKED_AT,scheduleMeta,scheduleSources,eventLabel as officialEventLabel,fieldStatusLabel} from './official-schedule.js';
import {sourceHtml,eventSourceHtml,futureHtml} from './schedule-ui.js';
import {examDetails,detailPhases} from './exam-details-data.js';
import {affiliateSection,groupFor} from './affiliate.js';
let detailAbort;
export function mountExam(id,params,c){
 detailAbort?.abort();detailAbort=new AbortController();const signal=detailAbort.signal;
 const {state,exams,events,formatDate,esc,checklist,updateProgress}=c;
 const exam=exams.find(e=>e.id===id),meta=examDetails[id];if(!exam||!meta){location.hash='#/guide/decided';return;}
 const root=document.querySelector('#exam-page'),ownEvents=events.filter(e=>e.exam===id).sort((a,b)=>a.date.localeCompare(b.date));
 const eventLabel=e=>officialEventLabel(e)+(e.planned?'（予定）':'');
 const dateText=e=>formatDate(e.date,true)+(e.time?' '+e.time+(e.type==='deadline'?'まで':''):'');
 const official=(label=meta.sources[0][0],index=0)=>`<a href="${meta.sources[index][1]}" target="_blank" rel="noopener noreferrer">${label} <span aria-hidden="true">↗</span></a>`;
 const siblings=exams.filter(e=>exam.field==='高校入試'?e.field==='高校入試':e.family===exam.family);
 const key=s=>`exam-${id}-${s}`;
 const nav=[['dates','日程'],['flow','受験までの流れ'],['packing','持ち物・当日の流れ'],['faq','よくある質問']];
 const verified=scheduleMeta[id];
 root.dataset.theme=meta.theme;
 root.innerHTML=`<nav class="ed-breadcrumb" aria-label="現在のページ"><a href="#/">トップ</a><span aria-hidden="true">›</span><a href="#/guide/decided">試験を探す</a><span aria-hidden="true">›</span><span>${exam.short}</span></nav>
 <header class="ed-hero"><div><span class="ed-eyebrow">${exam.field} の試験案内</span><h1 id="exam-title">${exam.name}</h1><p class="ed-scope">${meta.scope}</p><p class="ed-intro">${meta.intro}</p><div class="ed-hero-actions"><button class="save-button" data-save="${id}" aria-pressed="${state.saved.includes(id)}">${state.saved.includes(id)?'✓ 保存済み':'♧ 保存'}</button>${official('主催者の案内を見る')}<span>保存すると、あとから見返せます。</span></div></div><figure><img src="/assets/guide-${meta.art}.webp" width="1536" height="1024" alt="${meta.art==='family'?'親子で受験の予定を確認する様子':meta.art==='prepared'?'試験当日の持ち物をそろえる様子':'明るい部屋で試験の準備を相談する様子'}" decoding="async"></figure></header>
 ${siblings.length>1?`<div class="ed-round-selector"><label>${exam.field==='高校入試'?'地域を選ぶ':'実施回・方式を選ぶ'}<select id="exam-round-select">${siblings.map(e=>`<option value="${e.id}" ${e.id===id?'selected':''}>${e.name}｜${e.edition}</option>`).join('')}</select></label></div>`:''}
 <nav class="ed-page-nav" aria-label="このページの内容">${nav.map(([section,label])=>`<button data-detail-section="${section}">${label}<span aria-hidden="true">↓</span></button>`).join('')}</nav>
 ${renderDetailDates({id,meta,ownEvents,params,key,dateText,formatDate,eventLabel,esc})}
 <div class="ed-content-layout"><div class="ed-main"><section id="${key('flow')}" class="ed-flow-section" aria-labelledby="${key('flow-title')}"><div class="ed-section-title"><div><span class="ed-kicker">準備の順番が分かるように</span><h2 id="${key('flow-title')}">申し込みから当日までの流れ</h2></div></div><p class="ed-section-intro">いまのご自身に近いところから、ご覧ください。済んでいることは、下のチェックに残せます。</p><ol class="ed-timeline">${meta.steps.map(([when,title,body],i)=>`<li><span class="ed-step-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</span><div><span class="ed-when">${when}</span><h3>${title}</h3><p>${body}</p></div></li>`).join('')}</ol><p class="ed-source-inline">手続きの参照先：${official()}</p></section>
 <section class="ed-check-section" aria-labelledby="${key('check-title')}"><div class="ed-section-title"><div><span class="ed-kicker">確認したことを、ひとつずつ</span><h2 id="${key('check-title')}">いま、確かめておきたいこと</h2></div></div><div class="ed-phase-tabs" role="group" aria-label="準備を確認する時期">${detailPhases.map(p=>`<button data-detail-phase="${p.id}" aria-pressed="false">${p.label}</button>`).join('')}</div><div class="ed-check-caption"><h3 id="ed-phase-title"></h3><span id="ed-check-count" aria-live="polite"></span></div><div id="ed-check-items"></div><p class="ed-disclaimer">チェックはこのブラウザに保存されます。主催者への申し込み・支払いは別に行ってくださいね。</p></section>
 <section id="${key('packing')}" class="ed-packing" aria-labelledby="${key('packing-title')}"><div class="ed-section-title"><div><span class="ed-kicker">前日までに見ておくと安心です</span><h2 id="${key('packing-title')}">持ち物と、当日の過ごし方</h2></div></div><p class="ed-section-intro">持っていくものは試験ごとに違います。ここを手がかりに、ご自身の受験案内と照らし合わせてそろえてみましょう。</p><div class="ed-kit-grid">${meta.kit.map(([title,body],i)=>`<article><span class="ed-kit-symbol" aria-hidden="true">${['▤','✓','⌁'][i]}</span><h3>${title}</h3><p>${body}</p></article>`).join('')}</div><div class="ed-day-flow"><h3>当日は、この順番で</h3><ol>${meta.day.map((s,i)=>`<li><span>${i+1}</span><p>${s}</p></li>`).join('')}</ol><p>${official('主催者の案内で、当日の注意事項を確認する',id==='toeic'?1:0)}</p></div></section>
 <section class="ed-after"><span class="ed-kicker">受験、おつかれさまでした</span><h2>試験が終わったあとも</h2><p>${meta.after}</p><a class="text-link" href="#/guide/${id==='kyotsu'?'family':'prepared?exam='+id}">${id==='kyotsu'?'学校ごとの予定をメモする':'試験後の準備チェックを見る'} ›</a></section>
 <section id="${key('faq')}" class="ed-faq" aria-labelledby="${key('faq-title')}"><h2 id="${key('faq-title')}">気になることを、もう少し</h2>${meta.faq.map(([q,a])=>`<details><summary>${q}</summary><p>${a}</p></details>`).join('')}<p class="ed-source-inline">詳しくは ${official()} をご覧ください。</p></section>
 </div><aside class="ed-sidebar"><div class="ed-adviser"><span class="ed-adviser-mark">ひとこと</span><h2>${meta.advice}</h2><p>${meta.adviceBody}</p></div><div class="ed-official-card"><h2>申し込むときは、主催者の案内へ</h2><p>このページの試験・受け方が、ご自身の申し込みと合っているか確かめてからお進みくださいね。</p>${official('主催者の受験案内を開く')}<label class="applied-label"><input type="checkbox" data-applied="${id}" ${state.applied.includes(id)?'checked':''}>申し込みを済ませた</label><p class="small-note">ご自身の確認用のチェックです。</p></div><div class="ed-focus"><h2>申し込み前の確認に</h2><ul>${meta.focus.map(t=>`<li>${t}</li>`).join('')}</ul></div><a class="ed-compare-link" href="#/guide/compare">ほかの試験も受ける予定の方へ<span>日程を並べて確認できます ›</span></a></aside></div>
 ${affiliateSection(groupFor(exam),key('pr'))}
 <section class="ed-sources" aria-labelledby="${key('sources-title')}"><h2 id="${key('sources-title')}">主催者の案内・確認先</h2><p>手続きの説明は、下記の主催者案内を参照して整理しています。最新のお知らせや細かな条件も、こちらで確かめておいてくださいね。</p><ul>${[...meta.sources,...verified.sourceIds.map(s=>[scheduleSources[s].title,scheduleSources[s].url])].filter((s,i,a)=>a.findIndex(x=>x[1]===s[1])===i).map(([label,url])=>`<li><a href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a></li>`).join('')}</ul><p class="small-note">日程の確認日：${(verified.checkedAt||CHECKED_AT).replaceAll('-','/')}。日程ごとの出典は、上の日程欄にも掲載しています。</p></section>
 <section class="ed-other"><div class="ed-section-title"><h2>ほかの試験も見てみる</h2><a href="#/guide/decided">試験を探す ›</a></div><div>${exams.filter(e=>e.id!==id).map(e=>`<a href="#/exam/${e.id}"><span>${e.field}</span><strong>${e.short}</strong><b aria-hidden="true">›</b></a>`).join('')}</div></section>`;
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
 document.title=exam.name+'｜'+exam.edition+'の日程・受験準備｜資格・試験への道';
 document.querySelector('meta[name="description"]').content=exam.name+'（'+exam.edition+'）の日程と申し込みから当日までの準備をご案内します。出典・確認日と、公表状況を分けて掲載しています。';
}
