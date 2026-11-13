import {scheduleSnapshot} from './schedule-records.js';
export const CHECKED_AT=scheduleSnapshot.checkedAt;
export const scheduleSources=scheduleSnapshot.sources;
export const scheduleMeta=scheduleSnapshot.meta;
export const scheduleRows=scheduleSnapshot.rows;
export const eventLabel=e=>e.label||({deadline:'申込締切',exam:'試験日',result:'結果発表等'}[e.type]);
export const fieldStatusLabel=status=>({published:'公表済み','published-window':'具体日は未発表（期間のみ公表）',regional:'実施機関・地域ごとに異なります',rolling:'日時・会場を選んで予約',individual:'受験者・学校ごとに異なります',unannounced:'未発表',unverified:'未確認'}[status]||'要確認');
export function scheduleSummary(events,id,type,formatDate,{all=true}={}){
 const rows=events.filter(e=>e.exam===id&&e.type===type&&(all||e.primary!==false)).sort((a,b)=>(a.date+(a.time||'')).localeCompare(b.date+(b.time||'')));
 if(!rows.length)return scheduleMeta[id]?.fieldSummaries?.[type]||fieldStatusLabel(scheduleMeta[id]?.fields[type]||'unverified');
 return rows.map(e=>`${rows.length>1||type==='result'?eventLabel(e)+'：':''}${formatDate(e.date)}${e.time?' '+e.time:''}${e.planned?'（予定）':''}${e.note&&type==='deadline'?'（'+e.note+'）':''}`).join(' ／ ');
}
export function eventToIcs(event,now=new Date()){
 const clean=s=>String(s).replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
 const compact=event.date.replaceAll('-','');
 const timed=time=>`${compact}T${time.replace(':','')}00`;
 const next=new Date(event.date+'T00:00:00Z');next.setUTCDate(next.getUTCDate()+1);
 const timing=event.time?`DTSTART;TZID=Asia/Tokyo:${timed(event.time)}${event.endTime?'\r\nDTEND;TZID=Asia/Tokyo:'+timed(event.endTime):''}`:`DTSTART;VALUE=DATE:${compact}\r\nDTEND;VALUE=DATE:${next.toISOString().slice(0,10).replaceAll('-','')}`;
 const source=scheduleSources[event.sourceId];
 const desc=[event.edition,event.note,event.planned?'主催者公表の予定日':'',`公式情報の確認日：${event.checkedAt||CHECKED_AT}`,source.title,source.url,'最新の変更は主催者の案内をご確認ください。'].filter(Boolean).join('\n');
 return `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Shikaku Shiken Michi//JP\r\nBEGIN:VEVENT\r\nUID:${event.id}@michi-calendar\r\nDTSTAMP:${now.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'')}\r\n${timing}\r\nSUMMARY:${clean('【'+eventLabel(event)+(event.planned?'・予定':'')+'】'+event.name)}\r\nDESCRIPTION:${clean(desc)}\r\nURL:${source.url}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n`;
}
