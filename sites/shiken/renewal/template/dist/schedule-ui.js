import {CHECKED_AT,scheduleMeta,scheduleSources,scheduleRows,fieldStatusLabel} from './official-schedule.js';
import {shownRound} from './current-round.js';
const checkedLabel=CHECKED_AT.replaceAll('-','/');
// 2026-11-15 のオーナー指示: 日程の根拠の名前とリンクは、画面に出さない(データは registry.json に残す)。
export function sourceHtml(){return '';}
export function eventSourceHtml(){return '';}
export function futureHtml(id){const f=scheduleMeta[id].future;if(!f)return '';return `<aside class="schedule-pending"><strong>${f.name||''}・${f.edition}の日程：${fieldStatusLabel(f.status)}</strong><p>${f.note}</p><p class="small-note">次の年度の日程の見つけ方は、<a href="/nendo/">次の年度の日程が出る時期</a>にあります。</p></aside>`;}
export function renderSourceOverview(){
 const overview=document.querySelector('#schedule-source-list');
 if(overview)overview.innerHTML='<ul class="schedule-coverage-list">'+Object.entries(scheduleMeta).map(([id,own])=>{const sid=shownRound(id,scheduleRows),m=scheduleMeta[sid];return `<li><a href="#/exam/${id}">${m.scope} ›</a>${m.fieldNotes?.deadline?`<span class="small-note"> ${m.fieldNotes.deadline}</span>`:''}</li>`;}).join('')+'</ul>';
 const pending=document.querySelector('#calendar-pending');if(pending)pending.innerHTML=Object.keys(scheduleMeta).filter(id=>scheduleMeta[id].future).slice(0,2).map(futureHtml).join('')+'<p class="small-note">ほかの実施回の公表状況も、下の試験一覧や各詳細ページでご覧いただけます。</p>';
}
