import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import * as calculations from '../site/calculators.mjs';

function page(name, script) {
  const window = new Window({ url: `http://localhost/${name}.html`, settings: { enableJavaScriptEvaluation: true, disableJavaScriptFileLoading: true, disableCSSFileLoading: true } });
  window.document.write(readFileSync(new URL(`../site/${name}.html`, import.meta.url),'utf8'));
  Object.assign(window, calculations);
  const source = readFileSync(new URL(`../site/${script}`, import.meta.url),'utf8').replace(/^import .*?;\r?\n/, '');
  window.eval(source);
  return window;
}
function fill(w, values) {
  for (const [id,value] of Object.entries(values)) {
    const input = w.document.getElementById(id); input.value = String(value);
    input.dispatchEvent(new w.Event('input', { bubbles: true }));
  }
}
function submit(w,id) { w.document.getElementById(id).dispatchEvent(new w.Event('submit', { bubbles:true, cancelable:true })); }

test('旅行と家電の見積もり欄は有効な総額を比べ、入力変更で結果を消す', async () => {
  for (const [slug, cheaper] of [
    ['case-family-trip', 'セット'],
    ['case-temporary-appliances', 'レンタル'],
  ]) {
    const w = page(slug, 'common.js');
    try {
      const form = w.document.querySelector('[data-quote-compare]');
      const [first, second] = form.querySelectorAll('input');
      const output = form.querySelector('output');
      const compare = () => form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
      assert.equal(form.hidden, false);
      first.value = '83000';
      second.value = '80000';
      compare();
      assert.match(output.textContent, new RegExp(`${cheaper}の総額が3,000円`));
      second.value = '-1';
      second.dispatchEvent(new w.Event('input', { bubbles: true }));
      compare();
      assert.equal(output.textContent, '');
      first.value = '0';
      second.value = '0';
      compare();
      assert.match(output.textContent, /支払総額は同じです/);
    } finally { await w.happyDOM.close(); }
  }
});

test('年次計画のフォーム、タブ、CSV内容、入力変更時の失効', async () => {
  const w = page('tools','tools.js');
  try {
    w.document.querySelector('[data-tool="annual"]').click();
    assert.equal(w.document.getElementById('annual-panel').hidden,false);
    assert.equal(w.document.getElementById('savings-panel').hidden,true);
    fill(w, {'annual-saved':1000000,monthly:10000,years:3,'expense-year':2,expense:1500000});
    submit(w,'annual-form');
    assert.match(w.document.getElementById('annual-result').textContent, /-140,000円/);
    assert.equal(w.document.querySelectorAll('#annual-table tbody tr').length,3);
    let captured;
    w.URL.createObjectURL = blob => { captured = blob; return 'blob:local-test'; };
    w.URL.revokeObjectURL = () => {};
    let download;
    w.HTMLAnchorElement.prototype.click = function () { download = this.download; };
    w.document.getElementById('download-plan').click();
    assert.match(download,/積立計画.csv$/);
    assert.match(await captured.text(), /2,1120000,120000,1500000,-260000/);
    fill(w,{monthly:20000});
    assert.equal(w.document.getElementById('annual-table-area').hidden,true);
    assert.match(w.document.getElementById('annual-result').textContent,/入力内容が変わりました/);
    captured = null; w.document.getElementById('download-plan').click(); assert.equal(captured,null);
  } finally { await w.happyDOM.close(); }
});

test('預金比較は入力条件を反映し、税率空欄を税引前と表示', async () => {
  const w = page('tools','tools.js');
  try {
    fill(w,{principal:1000000,term:12,'a-promo':1,'a-months':12,'a-standard':0,'a-fees':0,'b-promo':0.5,'b-months':12,'b-standard':0,'b-fees':0});
    submit(w,'deposit-form');
    const output = w.document.getElementById('deposit-result').textContent;
    assert.match(output,/10,000円/); assert.match(output,/5,000円/); assert.match(output,/税引前/);
  } finally { await w.happyDOM.close(); }
});

test('イベント絞り込みとメニューのEscape操作', async () => {
  const w = page('events','common.js');
  try {
    w.document.querySelector('[data-filter="care"]').click();
    const visible = [...w.document.querySelectorAll('[data-event]')].filter(e=>!e.hidden);
    assert.equal(visible.length,1); assert.equal(visible[0].dataset.event,'care');
    assert.equal(new URL(w.location.href).searchParams.get('event'),'care');
    const button = w.document.querySelector('.menu-toggle'); button.click();
    assert.equal(button.getAttribute('aria-expanded'),'true');
    w.document.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(button.getAttribute('aria-expanded'),'false');
  } finally { await w.happyDOM.close(); }
});
