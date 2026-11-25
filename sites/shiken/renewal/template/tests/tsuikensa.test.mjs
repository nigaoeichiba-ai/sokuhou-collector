import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {SLUG,SPEC,tsuikensaRows,fillTsuikensa} from '../scripts/tsuikensa.mjs';
const read=async f=>JSON.parse(await readFile(new URL(f,import.meta.url),'utf8'));
const registry=await read('../schedule/registry.json');
const article=await read('../legacy/'+SLUG+'.json');
test('every prefecture with a general make-up row is in the table or is a listed exception',()=>{
 // exceptions: the make-up day belongs to an early selection, shares the day of the second round, or the main exam days do not line up
 const left=['koko-saitama','koko-tokyo','koko-aichi','koko-mie','koko-kyoto','koko-wakayama','koko-kagoshima'];
 const withRow=new Set(registry.rows.filter(r=>r.exam.startsWith('koko-')&&/追/.test(r.label)).map(r=>r.exam));
 const listed=new Set(SPEC.map(s=>'koko-'+s[1]));
 assert.deepEqual([...withRow].filter(id=>!listed.has(id)&&!left.includes(id)),[]);
});
test('the article has no number left to type and every placeholder is filled',()=>{
 const text=JSON.stringify(fillTsuikensa({[SLUG]:article},registry)[SLUG]);
 assert.doesNotMatch(text,/\{\{TK_/);
 assert.ok(text.includes(tsuikensaRows(registry).length+'道県'));
 assert.doesNotMatch(JSON.stringify(article),/[0-9]+道県/);
});
test('a missing row, an unknown placeholder or a new before-the-make-up prefecture stops the build',()=>{
 const without={...registry,rows:registry.rows.filter(r=>!(r.exam==='koko-shiga'&&/追/.test(r.label)))};
 assert.throws(()=>fillTsuikensa({[SLUG]:article},without),/koko-shiga/);
 assert.throws(()=>fillTsuikensa({[SLUG]:{...article,answer:'{{TK_NOPE}}'}},registry),/unknown placeholder/);
 const moved={...registry,rows:registry.rows.map(r=>r.exam==='koko-gunma'&&r.label==='合格発表'?{...r,date:'2027-02-20'}:r)};
 assert.throws(()=>fillTsuikensa({[SLUG]:article},moved),/before the make-up day/);
});
