import {CHECKED_AT,scheduleMeta,scheduleSources,fieldStatusLabel} from './official-schedule.js';
const checkedLabel=CHECKED_AT.replaceAll('-','/');
// 2026-11-15 のオーナー指示: 日程の根拠の名前とリンクは、画面に出さない(データは registry.json に残す)。
export function sourceHtml(){return '';}
export function eventSourceHtml(){return '';}
export function futureHtml(id){const f=scheduleMeta[id].future;if(!f)return '';return `<aside class="schedule-pending"><strong>${f.name||''}・${f.edition}の日程：${fieldStatusLabel(f.status)}</strong><p>${f.note}</p></aside>`;}
export function renderSourceOverview(){
 const overview=document.querySelector('#schedule-source-list');
 if(overview)overview.innerHTML='<ul class="schedule-coverage-list">'+Object.entries(scheduleMeta).map(([id,m])=>`<li><a href="#/exam/${id}">${m.scope} ›</a>${m.fieldNotes?.deadline?`<span class="small-note"> ${m.fieldNotes.deadline}</span>`:''}</li>`).join('')+'</ul>';
 const pending=document.querySelector('#calendar-pending');if(pending)pending.innerHTML=Object.keys(scheduleMeta).filter(id=>scheduleMeta[id].future).slice(0,2).map(futureHtml).join('')+'<p class="small-note">ほかの実施回の公表状況も、下の試験一覧や各詳細ページでご覧いただけます。</p>';
}
