import {GUIDES,CALENDAR_RANGE,LEGACY_DOCUMENT_CHECKS,LEGACY_PLANNER_ITEMS,recordsForMonth} from './data.js?v=__V__';
import {plannerItems,addMonths} from './calendar.js?v=__V__';

export const LIBRARY_KEY='kurashi-guide-library-v1';
export const CALENDAR_KEY='kurashi-calendar-v1';
const strings=value=>Array.isArray(value)?[...new Set(value.filter(s=>typeof s==='string'))].slice(0,2000):[];
export function readObject(storage,key){try{const v=JSON.parse(storage.getItem(key)||'{}');return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}catch{return {};}}
export function normalizeRecordId(id,guides=GUIDES,legacyPlans=LEGACY_PLANNER_ITEMS){
 for(const [guide,g] of Object.entries(guides)){
  for(const event of g.calendar||[])for(const old of event.legacyDates||[]){
   const m=id.match(/^(\d{4})-(\d{2})-(.+)-(\d{1,2})$/);
   if(m&&m[3]===guide&&Number(m[2])===old.month&&Number(m[4])===old.day)return m[1]+'-'+guide+'-'+event.id;
  }
  const prefix='plan-'+guide+'-';
  if(id.startsWith(prefix)){
   const old=id.slice(prefix.length).match(/^(\d{4}-\d{2}-\d{2})-(\d+)$/);
   if(old&&legacyPlans[guide]?.[Number(old[2])])return prefix+old[1]+'-'+legacyPlans[guide][Number(old[2])];
  }
 }
 return id;
}
export function migrateChecked(keys,legacy=LEGACY_DOCUMENT_CHECKS){
 return strings(keys).map(key=>{
  if(key.includes(':'))return key;
  for(const [guide,ids] of Object.entries(legacy)){const prefix=guide+'-';if(key.startsWith(prefix)&&/^\d+$/.test(key.slice(prefix.length))){const id=ids[Number(key.slice(prefix.length))];return id?guide+':'+id:null;}}
  return null;
 }).filter(Boolean);
}
export function readLibrary(storage){const raw=readObject(storage,LIBRARY_KEY);return {...raw,version:2,saved:strings(raw.saved),checked:strings(migrateChecked(raw.checked))};}
export function readCalendar(storage){const raw=readObject(storage,CALENDAR_KEY);return {...raw,saved:strings(raw.saved).map(id=>normalizeRecordId(id)),completed:strings(raw.completed).map(id=>normalizeRecordId(id))};}
export function migrateStorage(storage){
 for(const [key,value] of [[LIBRARY_KEY,readLibrary(storage)],[CALENDAR_KEY,readCalendar(storage)]]){const before=storage.getItem(key);if(before!==null&&before!==JSON.stringify(value))storage.setItem(key,JSON.stringify(value));}
}
export function setGuideSaved(storage,id,wanted){if(!GUIDES[id])return;const lib=readLibrary(storage);const saved=new Set(lib.saved);wanted?saved.add(id):saved.delete(id);storage.setItem(LIBRARY_KEY,JSON.stringify({...lib,saved:[...saved]}));}
export function setDocumentChecked(storage,id,wanted){const lib=readLibrary(storage);const checked=new Set(lib.checked);wanted?checked.add(id):checked.delete(id);storage.setItem(LIBRARY_KEY,JSON.stringify({...lib,checked:[...checked]}));}
export function setRecordSaved(storage,id,wanted){const data=readCalendar(storage);const saved=new Set(data.saved);id=normalizeRecordId(id);wanted?saved.add(id):saved.delete(id);storage.setItem(CALENDAR_KEY,JSON.stringify({...data,saved:[...saved]}));}
export function allCalendarRecords(){const records=[];for(let m=CALENDAR_RANGE.minMonth;m<=CALENDAR_RANGE.maxMonth;m=addMonths(m,1))records.push(...recordsForMonth(m));return records;}
export function findRecord(id,records=allCalendarRecords()){
 id=normalizeRecordId(id);
 const regular=records.find(r=>r.id===id);if(regular)return regular;
 for(const [guide,g] of Object.entries(GUIDES)){
  if(!g.planner)continue;const prefix='plan-'+guide+'-';
  if(!id.startsWith(prefix))continue;const suffix=id.slice(prefix.length).match(/^(\d{4}-\d{2}-\d{2})-([a-z][a-z0-9-]*)$/);if(!suffix)continue;
  try{const found=plannerItems(guide,suffix[1]).find(r=>r.id===id);if(found)return found;}catch{}
 }
}
export function getSavedItems(storage){
 const lib=readLibrary(storage),calendar=readCalendar(storage),records=allCalendarRecords();
 return [...lib.saved.filter(id=>GUIDES[id]).map(id=>({type:'guide',id,guide:id,title:GUIDES[id].title,summary:GUIDES[id].summary})),
 ...strings(calendar.saved).map(id=>findRecord(id,records)).filter(Boolean).map(r=>({type:'record',id:r.id,guide:r.guide,title:r.title,summary:r.description,date:r.date,record:r}))];
}

