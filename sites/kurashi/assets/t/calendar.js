import {GUIDES,CALENDAR_RANGE} from './data.js?v=__V__';
export const WEEKDAYS = ['日','月','火','水','木','金','土'];
export const MIN_MONTH = CALENDAR_RANGE.minMonth;
export const MAX_MONTH = CALENDAR_RANGE.maxMonth;
export function parseISO(iso) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) throw new RangeError('日付をYYYY-MM-DDで指定してください');
  const [y,m,d] = iso.split('-').map(Number);
  const date = new Date(Date.UTC(y,m-1,d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m-1 || date.getUTCDate() !== d) throw new RangeError('存在しない日付です');
  return date;
}
export function toISO(date) { return date.toISOString().slice(0,10); }
export function addDays(iso,days) { const d = parseISO(iso); d.setUTCDate(d.getUTCDate()+days); return toISO(d); }
export function addMonths(month,offset) {
  const d=parseISO(month+'-01'); d.setUTCMonth(d.getUTCMonth()+offset); return toISO(d).slice(0,7);
}
export function monthLabel(month,withYear=true) {const [y,m]=month.split('-').map(Number); return `${withYear ? y+'年' : ''}${m}月`;}
export function dateLabel(iso,withYear=false) {const d=parseISO(iso);return `${withYear ? d.getUTCFullYear()+'年' : ''}${d.getUTCMonth()+1}月${d.getUTCDate()}日（${WEEKDAYS[d.getUTCDay()]}）`;}
export function japanToday(now=new Date()) {const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now); const get=t=>parts.find(p=>p.type===t).value;return `${get('year')}-${get('month')}-${get('day')}`;}
export function clampMonth(month,span=1) {const max=addMonths(MAX_MONTH,1-span); return month < MIN_MONTH ? MIN_MONTH : month > max ? max : month;}
export function monthGrid(month) {
  const start=parseISO(month+'-01'); const first=addDays(month+'-01',-start.getUTCDay());
  return Array.from({length:42},(_,i)=>{const iso=addDays(first,i);const d=parseISO(iso);return {iso,day:d.getUTCDate(),weekday:d.getUTCDay(),current:iso.slice(0,7)===month};});
}
export function weekDates(iso) {const d=parseISO(iso); const start=addDays(iso,-d.getUTCDay());return Array.from({length:7},(_,i)=>addDays(start,i));}
export function plannerItems(event,base) {
  parseISO(base);

  if (!GUIDES[event]?.planner) throw new RangeError('未対応の出来事です');
  return GUIDES[event].planner.items.map(({offset,title,description},i)=>({id:`plan-${event}-${base}-${GUIDES[event].planner.items[i].id}`,date:addDays(base,offset),title,description,kind:'prep',topic:GUIDES[event].topic,guide:event}));
}
export function escapeHTML(value) {return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function escapeICS(v) {return String(v).replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');}
function foldLine(line) {let out='',count=0;for(const char of line){const size=new TextEncoder().encode(char).length;if(count+size>75){out+='\r\n ';count=1;}out+=char;count+=size;}return out;}
export function makeICS(items,stamp=new Date()) {
  const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Kurashi Calendar//Preparation Planner//JA','CALSCALE:GREGORIAN','METHOD:PUBLISH'];
  for(const item of items){parseISO(item.date);lines.push('BEGIN:VEVENT',`UID:${encodeURIComponent(item.id)}@kurashi-calendar-preview`,`DTSTAMP:${stamp.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'')}`,`DTSTART;VALUE=DATE:${item.date.replaceAll('-','')}`,`DTEND;VALUE=DATE:${addDays(item.date,1).replaceAll('-','')}`,`SUMMARY:${escapeICS((item.kind==='deadline'?'【期限】':item.kind==='boundary'?'【年内分の区切り】':'【準備の目安】')+item.title)}`,`DESCRIPTION:${escapeICS(item.description+'\n提出期限・受付方法は、提出先の公式案内で確認してください。')}`,'END:VEVENT');}
  lines.push('END:VCALENDAR');return lines.map(foldLine).join('\r\n')+'\r\n';
}

export function isSupportedMonth(month){return /^\d{4}-(0[1-9]|1[0-2])$/.test(month)&&month>=MIN_MONTH&&month<=MAX_MONTH;}
