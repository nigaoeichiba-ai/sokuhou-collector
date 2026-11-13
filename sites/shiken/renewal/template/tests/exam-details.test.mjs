import test from 'node:test';
import assert from 'node:assert/strict';
import {access} from 'node:fs/promises';
import {scheduleSources} from '../dist/official-schedule.js';
import {exams} from '../dist/data.js';
import {examDetails} from '../dist/exam-details-data.js';
test('every listed exam has its own procedure content, existing illustration and official sources',async()=>{
 assert.deepEqual(Object.keys(examDetails).sort(),exams.map(e=>e.id).sort());
 const hosts=new Set(['www.iibc-global.org','www.kentei.ne.jp','www.mhlw.go.jp','products.kinzai.or.jp','www.retio.or.jp','www.eiken.or.jp','www.dnc.ac.jp']);
 for(const [id,detail] of Object.entries(examDetails)){
  assert.equal(detail.steps.length,5,id);assert.ok(detail.steps.every(step=>step.length===3&&step.every(Boolean)),id);
  assert.ok(detail.faq.length>=2,id);assert.equal(detail.kit.length,3,id);
  for(const [,url] of detail.sources){const u=new URL(url);assert.equal(u.protocol,'https:');assert.ok(hosts.has(u.hostname)||Object.values(scheduleSources).some(s=>new URL(s.url).hostname===u.hostname),id);}
  await access(new URL('../dist/assets/guide-'+detail.art+'.webp',import.meta.url));
 }
});
