import {CHECKED_AT,scheduleMeta,scheduleSources,fieldStatusLabel} from './official-schedule.js';
const checkedLabel=CHECKED_AT.replaceAll('-','/');
export function sourceHtml(id,sourceId){const m=scheduleMeta[id];sourceId=sourceId||m.sourceIds[0];return `<p class="schedule-source">出典：<a href="${scheduleSources[sourceId].url}" target="_blank" rel="noopener noreferrer">${scheduleSources[sourceId].title} ↗</a><span>確認日：${(m.checkedAt||CHECKED_AT).replaceAll('-','/')}</span></p>`;}
export function eventSourceHtml(e){const s=scheduleSources[e.sourceId];return `<p class="schedule-source"><a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.title} ↗</a><span>確認日：${e.checkedAt.replaceAll('-','/')}</span></p>`;}
export function futureHtml(id){const f=scheduleMeta[id].future;if(!f)return '';return `<aside class="schedule-pending"><strong>${f.name||''}・${f.edition}の日程：${fieldStatusLabel(f.status)}</strong><p>${f.note}</p><a href="${scheduleSources[f.sourceId].url}" target="_blank" rel="noopener noreferrer">公式の掲載状況を確認 ↗</a><span>確認日：${(scheduleMeta[id].future.checkedAt||scheduleMeta[id].checkedAt||CHECKED_AT).replaceAll('-','/')}</span></aside>`;}
export function renderSourceOverview(){
 const overview=document.querySelector('#schedule-source-list');
 if(overview)overview.innerHTML=Object.entries(scheduleMeta).map(([id,m])=>`<article><h3><a href="#/exam/${id}">${m.scope} ›</a></h3>${sourceHtml(id)}${m.fieldNotes?.deadline?`<p class="small-note">${m.fieldNotes.deadline}</p>`:''}</article>`).join('');
 const pending=document.querySelector('#calendar-pending');if(pending)pending.innerHTML=Object.keys(scheduleMeta).filter(id=>scheduleMeta[id].future).slice(0,2).map(futureHtml).join('')+'<p class="small-note">ほかの実施回の公表状況も、下の試験一覧や各詳細ページでご覧いただけます。</p>';
}
