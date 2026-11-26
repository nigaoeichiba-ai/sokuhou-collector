// Which round a series' parent page (TOEIC) shows, in one place so that the detail page and every list agree (2026-11-27):
// its own round while that still takes applications, then the next round of the series that does.  `rows` are the schedule rows.
const SERIES={toeic:/^toeic-\d{8}$/};
const format=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'});
export const jstDay=()=>format.format(new Date());
export function shownRound(id,rows,day){
 const re=SERIES[id];if(!re)return id;day=day||jstDay();     // only a series' parent reads the clock and the rows (lists ask for every exam)
 if(rows.some(r=>r.exam===id&&r.type==='deadline'&&r.date>=day))return id;
 const next=rows.filter(r=>re.test(r.exam)&&r.type==='deadline'&&r.date>=day).sort((a,b)=>a.date.localeCompare(b.date))[0];
 return next?next.exam:id;
}
// the round written in a list: the exam's own, or the next one marked as such
export function listedEdition(exam,exams,rows){
 const id=shownRound(exam.id,rows);return id===exam.id?exam.edition:'次は'+exams.find(e=>e.id===id).edition;
}
