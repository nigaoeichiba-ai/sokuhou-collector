import {normalizeLinks,routeHash,fromHash} from './routes.js';
import {mountCatalog,catalogGroup} from './catalog.js';
import {mountGuide} from './guides.js';
import {mountExam} from './exam-details.js';
import {CHECKED_AT,scheduleMeta,eventLabel,scheduleSummary,eventToIcs} from './official-schedule.js';
import {sourceHtml,eventSourceHtml,renderSourceOverview} from './schedule-ui.js';
import {monthDays,shiftMonth,parseDate,dateKey,jstToday,dayDiff,eventsFor,readSaved} from './calendar.js';
import {events,exams,types,guides} from './data.js';
// Restore inactive screens for navigation. Static HTML exposes only this page's heading.
const shellData=document.getElementById('page-shells');
if(shellData){for(const [id,html] of Object.entries(JSON.parse(shellData.textContent)))document.getElementById(id).innerHTML=html;shellData.remove();}
const $=(s,root=document)=>root.querySelector(s), $$=(s,root=document)=>Array.from(root.querySelectorAll(s));
let browserStorage;
try{browserStorage=window.localStorage;}catch{browserStorage={getItem:()=>null,setItem:()=>{throw Error('保存不可');}};}
const initialDay=jstToday(),initialDate=parseDate(initialDay);
const state={year:initialDate.getUTCFullYear(),month:initialDate.getUTCMonth(),selected:initialDay,type:'all',calendarQuery:'',calendarGroup:'all',view:'calendar',...readSaved(browserStorage)};
const examById=id=>exams.find(x=>x.id===id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const monthKey=()=>`${state.year}-${String(state.month+1).padStart(2,'0')}`;
const formatDate=(key,year=false)=>new Intl.DateTimeFormat('ja-JP',{timeZone:'UTC',...(year?{year:'numeric'}:{}),month:'long',day:'numeric',weekday:'short'}).format(parseDate(key));
const badge=e=>`<span class="event-type ${types[e.type].class}">${eventLabel(e)}${e.planned?'（予定）':''}</span>`;
let toastTimer;
function toast(message){$('#toast').textContent=message;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').textContent='',3200);}
function persist(){try{browserStorage.setItem('michi-v1',JSON.stringify({saved:state.saved,applied:state.applied,checks:state.checks}));}catch{toast('このブラウザでは保存できません。開いている間はそのまま使えます。');}}
function storageChanged(){persist();renderSaved();$$('[data-save]').forEach(b=>{const selected=state.saved.includes(b.dataset.save);b.setAttribute('aria-pressed',String(selected));b.textContent=selected?'✓ 保存済み':'♧ 保存';});}
function toggleSave(id){const had=state.saved.includes(id);state.saved=had?state.saved.filter(x=>x!==id):[...state.saved,id];storageChanged();toast(had?'保存を解除しました。':'保存しました。「保存した試験」で確認できます。');}
function moveMonth(amount){const shifted=shiftMonth(state.year,state.month,amount);Object.assign(state,shifted);const selectedDay=parseDate(state.selected).getUTCDate();const last=new Date(Date.UTC(state.year,state.month+1,0)).getUTCDate();state.selected=dateKey(new Date(Date.UTC(state.year,state.month,Math.min(selectedDay,last))));renderCalendar();}
function setDate(key,focus=false){const d=parseDate(key);state.year=d.getUTCFullYear();state.month=d.getUTCMonth();state.selected=key;renderCalendar();if(focus)requestAnimationFrame(()=>$(`[data-date="${key}"]`)?.focus());}
function calendarItems(){const q=state.calendarQuery.toLocaleLowerCase('ja');return events.filter(e=>{const x=examById(e.exam);return (state.calendarGroup==='all'||catalogGroup(x)===state.calendarGroup)&&(!q||`${x.name} ${x.short} ${x.aliases} ${x.edition}`.toLocaleLowerCase('ja').includes(q));});}
function renderCalendar(){
 const selected=eventsFor(calendarItems(),{month:monthKey(),type:state.type});
 $('#month-label').textContent=`${state.year}年${state.month+1}月`;
 $('#calendar-grid').setAttribute('aria-label',`${state.year}年${state.month+1}月の日付`);
 $('#calendar-grid').innerHTML=monthDays(state.year,state.month).map(key=>{
   if(!key)return '<span class="date-cell date-empty" aria-hidden="true"></span>';
   const onDay=selected.filter(e=>e.date===key);const number=parseDate(key).getUTCDate();
   const label=`${formatDate(key,true)}、${onDay.length?onDay.map(e=>e.short+' '+types[e.type].label+(e.time?' '+e.time:'')).join('、'):'表示中の予定なし'}`;
   return `<button class="date-cell ${key===jstToday()?'today':''}" data-date="${key}" aria-label="${esc(label)}" aria-pressed="${key===state.selected}" ${key===jstToday()?'aria-current="date"':''}><span class="date-number">${number}</span>${onDay.slice(0,2).map(e=>`<span class="calendar-event ${types[e.type].class}" aria-hidden="true">${e.short==='日商簿記'?'簿記':e.short}・${e.type==='exam'?'試験':e.type==='deadline'?'締切':'結果'}</span>`).join('')}${onDay.length>2?`<span class="calendar-more" data-more="${onDay.length-2}">ほか${onDay.length-2}件</span>`:''}</button>`;
 }).join('');
 $('#calendar-wrap').hidden=state.view!=='calendar';$('#month-list').hidden=state.view!=='list';
 $('#month-list').innerHTML=selected.length?selected.map(e=>`<div class="month-event-row"><span class="month-event-date">${formatDate(e.date)}</span><div class="month-event-name">${badge(e)}<strong>${e.name}</strong><small>${e.time?e.time+(e.type==='deadline'?'まで':''):''}${e.note?' '+e.note:''}</small>${eventSourceHtml(e)}</div><button class="quiet-button" data-event="${e.id}">詳細 ›</button></div>`).join(''):'<div class="empty-note">この月に掲載している予定はありません。前後の月や、ほかの種類もご覧ください。</div>';
 $('#month-empty').hidden=selected.length!==0;$('#month-empty').textContent='この条件で掲載している予定はありません。掲載がない日も、試験がないことを意味しません。';
 $$('[data-type]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.type===state.type)));
 $$('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
 renderDay();
}
function renderDay(){
 const d=parseDate(state.selected);$('#selected-date-label').textContent=`${d.getUTCMonth()+1}月${d.getUTCDate()}日の予定`;
 const items=eventsFor(calendarItems(),{date:state.selected,type:state.type});
 const card=e=>{
   const related=events.find(x=>x.id===e.relatedExamEventId);const exam=events.find(x=>x.exam===e.exam&&x.type==='exam');const examDates=related?eventLabel(related)+'：'+formatDate(related.date,true):scheduleSummary(events,e.exam,'exam',key=>formatDate(key,true));
   return `<article class="day-event">${badge(e)}<h4>${e.name}</h4><p class="event-time">${e.time?'◷ '+e.time+(e.type==='deadline'?'まで':''):formatDate(e.date)}</p>${e.note?`<p class="event-note">${e.note}</p>`:''}${exam&&e.type!=='exam'?`<p class="event-secondary">試験日：${examDates}</p>`:''}${dayDiff(e.date)<0?'<p class="event-note">この日程は終了しました。</p>':''}<button class="primary" data-event="${e.id}"><span class="desktop-detail">日程・申込方法を見る</span><span class="mobile-detail">詳細</span> ›</button><button class="save-button" data-save="${e.exam}" aria-pressed="${state.saved.includes(e.exam)}">${state.saved.includes(e.exam)?'✓ 保存済み':'♧ 保存'}</button>${eventSourceHtml(e)}</article>`;
 };
 $('#day-events').innerHTML=items.length?items.slice(0,3).map(card).join('')+(items.length>3?`<details class="day-more"><summary>ほか${items.length-3}件の予定を見る</summary>${items.slice(3).map(card).join('')}</details>`:''):'<div class="day-empty"><h4>この日に掲載している予定はありません。</h4><p>ほかの日付や、予定の種類も選んでみてくださいね。</p></div>';
}
function renderSituations(){
 $('#situation-links').innerHTML=guides.map(g=>`<a class="situation-card" href="#/guide/${g.id}"><strong>${g.title}</strong><small>${g.sub}</small><span class="situation-art sprite art-${g.art}" aria-hidden="true"></span></a>`).join('');
}
function eventSummary(examId,type){return scheduleSummary(events,examId,type,key=>formatDate(key,true));}
function examCard(exam,{prepared=false}={}){
 return `<article class="exam-card"><h3>${exam.name}</h3><p>${exam.edition}</p><p><strong>試験日</strong>　${eventSummary(exam.id,'exam')}</p><p><strong>申込締切</strong>　${eventSummary(exam.id,'deadline')}</p><div class="exam-actions"><button class="text-button" data-exam="${exam.id}">日程・申込方法を見る ›</button><button class="save-button" data-save="${exam.id}" aria-pressed="${state.saved.includes(exam.id)}">${state.saved.includes(exam.id)?'✓ 保存済み':'♧ 保存'}</button></div>${sourceHtml(exam.id)}<label class="applied-label"><input type="checkbox" data-applied="${exam.id}" ${state.applied.includes(exam.id)?'checked':''}>申込を済ませた</label>${prepared?`<a class="text-link" href="#/guide/prepared?exam=${exam.id}">受験前の準備を確認 ›</a>`:''}</article>`;
}
function renderSaved(){
 const saved=exams.filter(e=>state.saved.includes(e.id));
 $('#saved-count').textContent=saved.length?` (${saved.length})`:'';
 $('#saved-list').innerHTML=saved.length?`<div class="saved-grid">${saved.map(e=>examCard(e,{prepared:true})).join('')}</div>`:'<div class="empty-saved"><p>まだ保存した試験はありません。</p><p>気になる試験が見つかったら、「保存」を押しておいてくださいね。あとからここで、日程や準備を確認できます。</p><a href="#calendar-section" class="text-link">カレンダーから試験を探す ›</a></div>';
}
function renderSearch(query){
 const q=query.trim().toLocaleLowerCase('ja');const items=exams.filter(e=>!q||`${e.name} ${e.short} ${e.aliases}`.toLocaleLowerCase('ja').includes(q));
 $('#search-results').hidden=false;$('#search-heading').textContent=q?`「${query.trim()}」の検索結果`:'掲載している試験';
 $('#search-result-list').innerHTML=items.length?items.map(e=>`<div class="search-result-row"><div><strong>${e.name}</strong><p class="small-note">${e.edition}</p></div><button class="primary" data-exam="${e.id}">日程を見る ›</button></div>`).join(''):'<p>名前に合う試験が見つかりませんでした。英検・TOEIC・簿記など、短い名前でもう一度探してみてくださいね。掲載していない試験・実施回もあります。</p>';
 $('#search-results').scrollIntoView({block:'start',behavior:'smooth'});
}
function dialog(content){$('#dialog-body').innerHTML=content;$('#detail-dialog').showModal();}
function showExam(id,eventId=null){
 if(!examById(id))return;
 if($('#detail-dialog').open)$('#detail-dialog').close();
 location.hash='#/exam/'+id+(eventId?'?event='+encodeURIComponent(eventId):'');
}
const articles={
 postal:{title:'「必着」と「消印有効」、どちらになっていますか？',body:'<p>郵送で申し込むときは、同じ締切日でも意味が違います。募集要項の言葉を、一度確かめておきましょう。</p><h3>「必着」と書かれている場合</h3><p>締切日までに、書類が相手に届く必要があります。投函する日ではないので、配達にかかる時間も見込んでくださいね。</p><h3>「消印有効」と書かれている場合</h3><p>指定日までの郵便局の消印があることが条件です。ポストに入れる時刻によっては当日の消印にならないこともあるため、余裕をもって窓口で確認しましょう。</p><p>提出先、郵送方法、受付時刻などの条件は、試験ごとの公式案内をご確認ください。</p>'},
 method:{title:'受け方が違うと、申込方法も変わります。',body:'<h3>決まった日に受ける試験</h3><p>申込期間と試験日が決まっています。会場や級によって受付期間が異なる場合もあるので、ご自身が受ける試験の案内を確認しましょう。</p><h3>日時や会場を選んで受ける試験</h3><p>CBTなどでは、会場の空き状況を見て日時を選ぶことがあります。希望する日がある方は、予約の開始時期や休止期間も確かめておいてくださいね。</p><h3>申込後にも、ひとつ確認を</h3><p>支払期限、受付完了のお知らせ、受験票の受け取り方まで確認しておくと、当日の準備がしやすくなります。</p>'},
 about:{title:'資格・試験への道について',body:'<p>受けたい試験が決まったときも、これから何を学ぶか迷っているときも。日程や準備を確かめる場所として、気軽に使っていただけるサイトを目指しています。</p><p>掲載している日程には、主催者の公式案内の出典と確認日を添えています。申込方法や変更のお知らせなど、詳しい条件は主催者の案内で確かめておいてくださいね。</p>'},
 sources:{title:'日程を確認するときに',body:'<p>実際に申し込む際は、試験の主催者が出している最新の案内をご確認ください。級、受験方式、会場、提出方法などによって、日程や条件が変わることがあります。</p><p>掲載している資格・試験を、実施回や地域に分けてご案内しています。対象はトップの一覧からお選びいただけます。確認日は各日程の出典欄に掲載しています。公表された予定日は「予定」、日程の公表がないものは「未発表」、日付を確定できないものは「未確認」と分けています。予約制や地域ごとに違う日程も、その旨を表示しています。掲載のない日も、試験がないことを意味しません。</p><p>予定の保存や「申込済み」のチェックは、ご自身の確認用です。主催者への申込や支払いは行われません。</p>'},
 privacy:{title:'保存した予定について',body:'<p>ログインしなくても、試験を保存できます。保存先は、いまお使いのブラウザです。このサイトから、保存した内容をサーバーへ送信することはありません。</p><p>別の端末には引き継がれません。また、ブラウザのデータを消したり、プライベートモードを閉じたりすると、保存した予定が消えることがあります。</p><p>共有の端末をお使いのときは、この点にも気をつけてくださいね。</p>'}
};
function showArticle(id){const a=articles[id];if(a)dialog(`<h2 id="dialog-heading">${a.title}</h2>${a.body}`);}
function renderGuide(id,params=new URLSearchParams()){
 const guide=guides.find(g=>g.id===id);if(!guide){location.hash='#/';return;}
 mountGuide(id,params,{state,exams,events,types,guides,esc,formatDate,examCard,eventSummary,checklist,updateProgress,toast});
}
function checklist(key,items){return `<div class="checklist">${items.map(([title,sub],i)=>`<label><input type="checkbox" data-check="${key}-${i}" ${state.checks[`${key}-${i}`]?'checked':''}><span><strong>${title}</strong><small>${sub}</small></span></label>`).join('')}</div><p class="check-progress" aria-live="polite"></p>`;}
function updateProgress(){const n=$$('[data-check]:checked').length;const total=$$('[data-check]').length;const p=$('.check-progress');if(p)p.textContent=n===total?'ひと通り確認できましたね。直前に主催者からのお知らせも、もう一度ご覧ください。':`${total}つのうち、${n}つ確認できました。ご自身のペースで進めてくださいね。`;}
export function route(){renderRoute();normalizeLinks();
 const canonical='https://shiken-nittei.com'+location.pathname;
 document.querySelector('link[rel="canonical"]')?.setAttribute('href',canonical);
 const description=document.querySelector('meta[name="description"]');if(description)description.setAttribute('content',description.content);
 for(const [name,value] of [['og:url',canonical],['og:title',document.title],['og:description',description?.content||'']])document.querySelector(`meta[property="${name}"]`)?.setAttribute('content',value);
 const schema=document.querySelector('script[type="application/ld+json"]');if(schema)schema.textContent=JSON.stringify({'@context':'https://schema.org','@type':'WebPage',url:canonical,name:document.title,description:description?.content||'',inLanguage:'ja'});
}
function renderRoute(){
 if(location.hash.startsWith('#/')){const next=fromHash(location.hash);history.replaceState(null,'',next);}
 const hash=routeHash(location.pathname,location.search,location.hash);const match=hash.match(/^#\/guide\/([^?]+)(?:\?(.*))?$/);const examMatch=hash.match(/^#\/exam\/([^?]+)(?:\?(.*))?$/);const guide=Boolean(match),detail=Boolean(examMatch);$('#home-page').hidden=guide||detail;$('#guide-page').hidden=!guide;$('#exam-page').hidden=!detail;
 if(!guide)$('#guide-content').innerHTML='';if(!detail)$('#exam-page').innerHTML='';
 $('#main-nav').classList.remove('menu-open');$('.menu-toggle').setAttribute('aria-expanded','false');
 $('.menu-toggle').setAttribute('aria-label','メニューを開く');
 $('.skip-link').href=detail?'#exam-title':guide?'#guide-title':'#calendar-section';$('.skip-link').textContent=detail||guide?'本文へ進む':'カレンダーへ進む';
 // Keep skip links within the current route instead of treating a section ID as the home route.
 if(detail){mountExam(examMatch[1],new URLSearchParams(examMatch[2]||''),{state,exams,events,formatDate,esc,checklist,updateProgress});window.scrollTo({top:0,behavior:'instant'});return;}
 document.querySelector('meta[name="description"]').content=guide?(guides.find(g=>g.id===match[1])?.intro||'試験の準備を確認できる確認日は、各日程の出典と一緒に掲載しています。'):'資格・試験への道。試験日や申込の締切をカレンダーで確認し、ご自身の状況から必要な準備を探せます。確認日は、各日程の出典と一緒に掲載しています。';
 if(guide){renderGuide(match[1],new URLSearchParams(match[2]||''));document.title=($('#guide-title').textContent||'受験の案内')+'｜資格・試験への道';window.scrollTo({top:0,behavior:'instant'});}
 else {document.title='資格・試験への道｜試験日程・申込期限・受験準備';renderSaved();if(hash&&hash!=='#/')requestAnimationFrame(()=>document.getElementById(hash.slice(1))?.scrollIntoView());else window.scrollTo({top:0,behavior:'instant'});}
}
function downloadEvent(event){
 const blob=new Blob([eventToIcs(event)],{type:'text/calendar;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=event.id+'.ics';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('出典と確認日を添えた予定ファイルを保存しました。');
}
document.addEventListener('click',e=>{
 if(e.target.closest('.skip-link')&&/^#\/(exam|guide)\//.test(location.hash)){e.preventDefault();const id=location.hash.startsWith('#/exam/')?'exam-title':'guide-title';const heading=document.getElementById(id);heading?.setAttribute('tabindex','-1');heading?.focus();return;}
 const target=e.target.closest('button');if(!target)return;
 if(target.dataset.date)setDate(target.dataset.date);
 if(target.dataset.type){state.type=target.dataset.type;renderCalendar();}
 if(target.dataset.view){state.view=target.dataset.view;renderCalendar();}
 if(target.dataset.save)toggleSave(target.dataset.save);
 if(target.dataset.event){const event=events.find(x=>x.id===target.dataset.event);if(event)showExam(event.exam,event.id);}
 if(target.dataset.exam)showExam(target.dataset.exam);
 if(target.dataset.article)showArticle(target.dataset.article);
 if(target.dataset.calendarEvent){const ev=events.find(x=>x.id===target.dataset.calendarEvent);if(ev){$('#detail-dialog').close();state.type='all';state.calendarQuery='';state.calendarGroup='all';$('#calendar-query').value='';$('#calendar-group').value='all';location.hash='#calendar-section';setDate(ev.date);}}
 if(target.dataset.ics){const ev=events.find(x=>x.id===target.dataset.ics);if(ev)downloadEvent(ev);}
});
document.addEventListener('change',e=>{
 if(e.target.dataset.applied){const id=e.target.dataset.applied;state.applied=e.target.checked?[...new Set([...state.applied,id])]:state.applied.filter(x=>x!==id);persist();renderSaved();$$(`[data-applied="${id}"]`).forEach(c=>c.checked=state.applied.includes(id));toast(e.target.checked?'申込済みにしました。':'申込済みのチェックを外しました。');}
 if(e.target.dataset.check){state.checks[e.target.dataset.check]=e.target.checked;persist();updateProgress();}
});
$('#prev-month').addEventListener('click',()=>moveMonth(-1));$('#next-month').addEventListener('click',()=>moveMonth(1));$('#today-button').addEventListener('click',()=>setDate(jstToday()));
$('#calendar-grid').addEventListener('keydown',e=>{const cell=e.target.closest('[data-date]');if(!cell)return;const offset={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[e.key];if(offset){e.preventDefault();setDate(dateKey(new Date(parseDate(cell.dataset.date).getTime()+offset*86400000)),true);}});
$('#home-search').addEventListener('submit',e=>{e.preventDefault();renderSearch($('#search-q').value);});$('#close-search').addEventListener('click',()=>{$('#search-results').hidden=true;$('#search-q').focus();});
$('#close-dialog').addEventListener('click',()=>$('#detail-dialog').close());$('#detail-dialog').addEventListener('click',e=>{if(e.target===$('#detail-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$('.menu-toggle').addEventListener('click',()=>{const next=$('.menu-toggle').getAttribute('aria-expanded')!=='true';$('.menu-toggle').setAttribute('aria-expanded',String(next));$('.menu-toggle').setAttribute('aria-label',next?'メニューを閉じる':'メニューを開く');$('#main-nav').classList.toggle('menu-open',next);});
window.addEventListener('hashchange',()=>{route();normalizeLinks();});window.addEventListener('popstate',()=>{route();normalizeLinks();});
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a||e.defaultPrevented||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button!==0||a.target||a.download)return;const u=new URL(a.href,location.href);if(u.origin===location.origin&&(/^\/(exams|guides)\//.test(u.pathname)||u.pathname==='/')){e.preventDefault();history.pushState(null,'',u.pathname+u.search+u.hash);route();normalizeLinks();}});
if(!globalThis.__SSG__)new MutationObserver(()=>normalizeLinks()).observe(document.body,{childList:true,subtree:true});window.addEventListener('storage',e=>{if(e.key==='michi-v1'){Object.assign(state,readSaved(browserStorage));renderSaved();renderDay();if(/^#\/(guide|exam)\//.test(location.hash))route();}});
$('#calendar-query').addEventListener('input',e=>{state.calendarQuery=e.target.value;renderCalendar();});$('#calendar-group').addEventListener('change',e=>{state.calendarGroup=e.target.value;renderCalendar();});
mountCatalog({exams,events,esc,eventSummary});renderSituations();renderSourceOverview();renderCalendar();renderSaved();route();normalizeLinks();



