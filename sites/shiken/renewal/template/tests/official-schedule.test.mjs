import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {events,exams} from '../dist/data.js';
import {CHECKED_AT,scheduleMeta,scheduleSources,scheduleSummary,eventToIcs,fieldStatusLabel} from '../dist/official-schedule.js';
const event=id=>events.find(e=>e.id===id);
test('実日程に置き換えた画面・スタイルに表示例の注記を残さない',async()=>{
 const directory=new URL('../dist/',import.meta.url);
 for(const name of await readdir(directory)){if(!/\.(js|css|html)$/.test(name))continue;const content=await readFile(new URL(name,directory),'utf8');assert.doesNotMatch(content,/表示例|表示サンプル/,name);}
});
test('全公表日程に公式出典と固定の照合日があり、不明な日付をイベントに混ぜない',()=>{
 assert.equal(CHECKED_AT,Object.values(scheduleMeta).map(m=>m.checkedAt).sort()[0]);assert.equal(Object.keys(scheduleMeta).length,exams.length);
 for(const e of events){assert.equal(e.checkedAt,scheduleMeta[e.exam].checkedAt);assert.ok(scheduleSources[e.sourceId]?.url.startsWith('https://'));assert.ok(e.label);assert.ok(scheduleMeta[e.exam]);if(e.relatedExamEventId){const related=event(e.relatedExamEventId);assert.equal(related.exam,e.exam);assert.equal(related.type,'exam');}}
 for(const [id,meta] of Object.entries(scheduleMeta)){for(const [type,status] of Object.entries(meta.fields)){if(status==='published')assert.ok(events.some(e=>e.exam===id&&e.type===type),id+' '+type);}}
 assert.equal(scheduleMeta.takken.future.status,'unannounced');assert.equal(fieldStatusLabel('unannounced'),'未発表');
 assert.equal(events.filter(e=>e.exam==='takken'&&e.date.startsWith('2027')).length,0);
 assert.equal(scheduleMeta.boki.fields.deadline,'regional');assert.equal(events.filter(e=>e.exam==='boki'&&e.type==='deadline').length,0);
});
test('公式の区分別期限・発表時刻を保持する',()=>{
 assert.equal(event('eiken-cash-deadline').date,'2026-12-11');assert.equal(event('eiken-deadline').date,'2026-12-14');
 assert.equal(event('eiken-second-a').date,'2027-02-28');assert.equal(event('eiken-second-b').date,'2027-03-07');
 assert.equal(event('nurse-deadline').time,'');assert.match(event('nurse-deadline').note,/消印有効/);assert.equal(event('nurse-counter-deadline').time,'17:00');
 assert.equal(event('fp-result').date,'2027-03-05');assert.equal(event('fp-result').time,'10:00');assert.equal(event('fp-result').planned,true);
 assert.equal(event('nurse-result').time,'14:00');assert.equal(event('takken-result').time,'09:30');
 assert.equal(event('kyotsu-registration-deadline').time,'17:00');assert.equal(event('kyotsu-payment-deadline').time,'23:59');
});
test('カード・比較・詳細用の集計が同じ日程を参照する',()=>{
 const summary=scheduleSummary(events,'eiken','exam',date=>date);
 assert.match(summary,/一次試験：2027-01-24/);assert.match(summary,/二次試験・A日程：2027-02-28/);assert.match(summary,/二次試験・B日程：2027-03-07/);
 assert.match(scheduleSummary(events,'boki','deadline',date=>date),/商工会議所.*受付終了/);
 assert.match(scheduleSummary(events,'toeic','result',date=>date),/デジタル公式認定証.*予定/);
});
test('予定ファイルも公式出典・確認日・日本時間を使用し、期限の終了時刻を捏造しない',()=>{
 const file=eventToIcs(event('fp-deadline'),new Date('2026-11-13T12:00:00Z'));
 assert.match(file,/DTSTART;TZID=Asia\/Tokyo:20261201T173000/);assert.doesNotMatch(file,/DTEND|表示例|sample/);
 assert.ok(file.includes(event('fp-deadline').checkedAt));assert.match(file,/https:\/\/products.kinzai.or.jp\/exam-fp\/schedule\//);
 const postal=eventToIcs(event('nurse-deadline'));assert.match(postal,/DTSTART;VALUE=DATE:20261127/);assert.match(postal,/消印有効/);
 const result=eventToIcs(event('toeic-result'));assert.match(result,/デジタル公式認定証/);assert.doesNotMatch(result,/合格発表/);
 assert.match(eventToIcs(event('takken-exam')),/DTEND;TZID=Asia\/Tokyo:20261018T150000/);
});
