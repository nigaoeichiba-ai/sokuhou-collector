import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../site');
const pages = readdirSync(root).filter(name => name.endsWith('.html'));

test('すべてのページが新しい名称と固有のタイトルを持ち、未公開として識別できる', () => {
  const titles = new Set();
  for (const name of pages) {
    const html = readFileSync(resolve(root,name),'utf8');
    assert(!html.includes('暮らしの予定'), `${name}: old event label`);
    assert(!html.includes('計算道具'), `${name}: old tools label`);
    assert(html.includes('人生のイベント')); assert(html.includes('便利ツール'));
    assert(html.includes('noindex,nofollow'));
    assert.equal((html.match(/<h1\b/g)||[]).length,1,`${name}: one h1`);
    const title = html.match(/<title>(.*?)<\/title>/s)[1];
    assert(!titles.has(title), `${name}: duplicate title`); titles.add(title);
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
    assert.equal(ids.length,new Set(ids).size,`${name}: duplicate id`);
  }
});
test('ページ・画像・スクリプトとフラグメントの参照がすべて存在する', () => {
  for (const name of pages) {
    const html = readFileSync(resolve(root,name),'utf8');
    for (const [,raw] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      assert(!/^https?:/.test(raw), `${name}: unexpected external request ${raw}`);
      const [path, fragment] = raw.split('#');
      const targetName = path ? path.split('?')[0] : name;
      const target = resolve(root, targetName);
      assert(existsSync(target), `${name}: missing ${raw}`);
      if (fragment && target.endsWith('.html')) assert(readFileSync(target,'utf8').includes(`id="${fragment}"`), `${name}: missing fragment ${raw}`);
    }
  }
});
test('記事の冒頭はヒーロー画像、要点、目次、本文の順である', () => {
  for (const name of ['article.html', 'case-family-trip.html', 'case-weeknight-dinner.html', 'case-temporary-appliances.html', 'travel-cost-average.html']) {
    const html = readFileSync(resolve(root,name),'utf8');
    const positions = ['class="model-hero"', 'class="model-points"', 'class="guide-toc"', 'id="part-1"'].map(s=>html.indexOf(s));
    assert(positions.every(p=>p>=0), name);
    assert(positions.every((p,i)=>i===0 || positions[i-1]<p), name);
    assert.equal(html.includes('id="household-profile"'), name !== 'travel-cost-average.html');
    assert(!html.includes('確認後に表示'), name);
  }
});

test('ヘッダーの4項目は全ページで独立カテゴリへ進み、削除した注記が残らない', () => {
  for (const name of pages) {
    const html = readFileSync(resolve(root,name),'utf8');
    assert(!html.includes('モデルケースは架空の例です。'),name);
    const nav=html.match(/<nav class="site-nav"[^>]*>(.*?)<\/nav>/s)[1];
    const links=[...nav.matchAll(/<a href="([^"]+)"[^>]*>([^<]+)<\/a>/g)];
    assert.equal(links.length,4,name);
    assert.equal(new Set(links.map(m=>m[1])).size,4,name);
    assert(links.every(m=>!m[1].includes('#')),`${name}: category links must not be homepage anchors`);
    assert.deepEqual(links.map(m=>m[1]),['events.html','cases.html','guide.html','tools-category.html']);
  }
});
