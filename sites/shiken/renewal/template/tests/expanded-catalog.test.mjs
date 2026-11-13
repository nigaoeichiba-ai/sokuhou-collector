import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {exams,events} from '../dist/data.js';
import {catalogProfiles} from '../dist/expanded-catalog.js';
import {scheduleMeta,scheduleSources} from '../dist/official-schedule.js';
import {catalogGroup,catalogState} from '../dist/catalog.js';

test('元サイトの全対象名・40高校地域・大学例をカタログに引き継ぐ',async()=>{
 const audit=JSON.parse(await readFile(new URL('../research/coverage-audit.json',import.meta.url),'utf8'));
 assert.equal(audit.summary.familiesCovered,audit.summary.originalFamilies);
 assert.deepEqual(audit.summary.missingNamedFamilies,[]);assert.deepEqual(audit.summary.missingUniversityExamples,[]);
 const inventory=JSON.parse(await readFile(new URL('../research/original-inventory.json',import.meta.url),'utf8'));
 for(const pref of inventory.schools)assert.ok(exams.some(e=>e.field==='高校入試'&&e.name.includes(pref.pref)),pref.pref);
 assert.ok(exams.length>=95);assert.ok(events.length>=567);
 assert.equal(exams.filter(e=>catalogGroup(e)==='school').length,40);
});
test('高校の本人期限と学校受付期限を混同せず、追加確認済み項目に古い未確認注記を残さない',()=>{
 for(const id of ['koko-hokkaido','koko-iwate','koko-miyagi','koko-saitama','koko-kagawa','koko-miyazaki','koko-kagoshima']){
  assert.equal(scheduleMeta[id].fields.deadline,'published');assert.doesNotMatch(scheduleMeta[id].notes,/出願期限は未確認/);
  assert.ok(events.some(e=>e.exam===id&&e.type==='deadline'));assert.ok(scheduleSources[scheduleMeta[id].fieldSourceIds.deadline]);
 }
 assert.equal(scheduleMeta['koko-hyogo'].fields.deadline,'unverified');assert.equal(catalogState('koko-hyogo'),'partial');
 assert.ok(!events.some(e=>e.exam==='koko-hyogo'&&e.type==='deadline'));
 const miyagi=events.find(e=>e.id==='koko-miyagi-first-web-deadline')||events.find(e=>e.exam==='koko-miyagi'&&e.type==='deadline'&&e.date==='2027-02-16');assert.equal(miyagi.time,'11:00');
});
test('未発表・月幅・予約制の期間を、架空の単日イベントにしない',()=>{
 assert.equal(catalogState('touroku-tokyo-2027'),'unannounced');assert.ok(!events.some(e=>e.exam==='touroku-tokyo-2027'));
 for(const id of ['itpassport-cbt','fe-cbt']){assert.equal(catalogState(id),'rolling');assert.equal(scheduleMeta[id].availability.suspensions[0].end,null);assert.ok(!events.some(e=>e.exam===id&&e.type==='exam'));}
 for(const p of catalogProfiles){for(const row of p.rows){const e=events.find(e=>e.id===row.id);assert.ok(e);assert.equal(e.date,row.date);assert.equal(e.time,row.time||'');if(row.sourceUrl)assert.equal(scheduleSources[e.sourceId].url,row.sourceUrl);}}
});
