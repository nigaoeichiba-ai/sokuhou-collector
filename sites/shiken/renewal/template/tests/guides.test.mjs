import test from 'node:test';
import assert from 'node:assert/strict';
import {matchExams,scheduleConflicts,normalizeSchoolPlans} from '../dist/guide-model.js';
import {exams,events} from '../dist/data.js';
test('search combines alias, purpose and exam month without treating deadlines as exams',()=>{
 assert.deepEqual(matchExams(exams,events,{query:'英検',purpose:'language',period:'2027-01'}).map(e=>e.id),['eiken']);
 assert.equal(matchExams(exams,events,{query:'英検',purpose:'language',period:'2026-12'}).length,0);
 assert.ok(matchExams(exams,events,{purpose:'work'}).every(e=>e.field!=='語学'&&e.field!=='大学入試'));
});
test('conflicts require different exams on the same exam date',()=>{
 assert.deepEqual(scheduleConflicts(events,['eiken','fp']).map(c=>c.date),['2027-01-24']);
 assert.deepEqual(scheduleConflicts([...events,...events],['toeic']),[]);
});
test('stored personal plans reject malformed records and impossible dates',()=>{
 assert.deepEqual(normalizeSchoolPlans({}),[]);
 const plans=normalizeSchoolPlans([null,{id:'x',name:'学校',dates:{apply:'2027-02-30',exam:'2027-02-28',enroll:'invalid'}}]);
 assert.equal(plans.length,1);assert.equal(plans[0].dates.apply,'');assert.equal(plans[0].dates.exam,'2027-02-28');assert.equal(plans[0].dates.enroll,'');
});
