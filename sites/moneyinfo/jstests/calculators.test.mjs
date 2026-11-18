import { test } from 'node:test';
import assert from 'node:assert/strict';
import { savings, annualPlan, monthDifference, depositEstimate, money } from '../site/calculators.js';

test('端数を切り上げ、最終回を調整して目標に届く', () => {
  const r = savings({ target: 100, saved: 0, months: 3 });
  assert.equal(r.monthly, 34); assert.equal(r.finalDeposit, 32);
  assert.equal(r.monthly * 2 + r.finalDeposit, 100);
});
test('準備済み額が目標を超えても負の積立額にしない', () => {
  assert.equal(savings({ target: 10, saved: 20, months: 2 }).monthly, 0);
});
test('残額が積立回数より小さい場合も目標を超えて払い続けない', () => {
  const r = savings({ target: 1, saved: 0, months: 12 });
  assert.equal(r.monthly, 1); assert.equal(r.payments, 1); assert.equal(r.finalDeposit, 1);
  assert.equal(r.monthly * (r.payments - 1) + r.finalDeposit, 1);
});
test('空欄・負数・小数の金額と不正な期間を拒否する', () => {
  for (const value of ['', '-1', '1.5', 'Infinity', 'x']) assert.throws(() => money(value));
  for (const months of [0, -1, 1.5, '', 601]) assert.throws(() => savings({ target: 10, saved: 0, months }));
});
test('月数は年の境界をまたいで正しく数える', () => {
  assert.equal(monthDifference('2026-11', '2027-02'), 3);
  assert.throws(() => monthDifference('2026-11', '2026-11'));
  assert.throws(() => monthDifference('2026-11', '2026-10'));
  assert.throws(() => monthDifference('2026-11', '2027-13'));
});
test('指定年の支出だけを引き、翌年へ残高を引き継ぐ', () => {
  const rows = annualPlan({ saved: 100, monthly: 10, years: 3, expenseYear: 2, expense: 300 });
  assert.deepEqual(rows.map(r => r.balance), [220, 40, 160]);
  assert.equal(rows[2].start, 40);
});
test('積立計画では不足を隠すために残高を0へ丸めない', () => {
  assert.equal(annualPlan({ saved: 0, monthly: 0, years: 1, expenseYear: 1, expense: 100 })[0].balance, -100);
});
test('支出年と支出額は組で検証する', () => {
  assert.throws(() => annualPlan({ saved: 0, monthly: 10, years: 2, expenseYear: 3, expense: 10 }));
  assert.throws(() => annualPlan({ saved: 0, monthly: 10, years: 2, expenseYear: 1, expense: '' }));
});
test('優遇期間の終了後は通常金利で計算し、費用と税を区別する', () => {
  const r = depositEstimate({ principal: 120000, months: 12, promoRate: 2, promoMonths: 3, standardRate: 1, fees: 100, tax: 20 });
  assert.deepEqual(r, { interest: 1500, tax: 300, fees: 100, net: 1100, taxIncluded: true });
});
test('優遇期間が預入期間より長くても利息を過大計上しない', () => {
  const r = depositEstimate({ principal: 120000, months: 3, promoRate: 2, promoMonths: 12, standardRate: 1, fees: 0 });
  assert.equal(r.interest, 600); assert.equal(r.taxIncluded, false);
});
test('金利比較は費用によるマイナスを表示できる', () => {
  assert.equal(depositEstimate({ principal: 100, months: 12, promoRate: 0, promoMonths: 0, standardRate: 0, fees: 10 }).net, -10);
});
