const MAX_MONEY = 1_000_000_000_000;
export function money(value, label = '金額') {
  if (String(value).trim() === '' || !Number.isFinite(Number(value)) || Number(value) < 0 || Number(value) > MAX_MONEY) throw new RangeError(`${label}は0円以上、1兆円以下の数値で入力してください。`);
  if (!Number.isInteger(Number(value))) throw new RangeError(`${label}は1円単位で入力してください。`);
  return Number(value);
}
function integer(value, min, max, label) {
  const n = Number(value);
  if (String(value).trim() === '' || !Number.isInteger(n) || n < min || n > max) throw new RangeError(`${label}は${min}から${max}までの整数で入力してください。`);
  return n;
}
function rate(value, label) {
  const n = Number(value);
  if (String(value).trim() === '' || !Number.isFinite(n) || n < 0 || n > 100) throw new RangeError(`${label}は0から100までの数値で入力してください。`);
  return n;
}
export function monthDifference(start, end) {
  const pattern = /^(\d{4})-(0[1-9]|1[0-2])$/;
  const a = pattern.exec(start), b = pattern.exec(end);
  if (!a || !b) throw new RangeError('目標月を選択してください。');
  const count = (Number(b[1]) - Number(a[1])) * 12 + Number(b[2]) - Number(a[2]);
  return integer(count, 1, 600, '積立回数');
}
export function savings({ target, saved, months }) {
  const goal = money(target, '目標額'), balance = money(saved, '準備済み資金');
  const count = integer(months, 1, 600, '積立回数');
  const remaining = Math.max(0, goal - balance), monthly = Math.ceil(remaining / count);
  const payments = remaining === 0 ? 0 : Math.ceil(remaining / monthly);
  return { target: goal, saved: balance, months: count, remaining, monthly, payments, finalDeposit: payments === 0 ? 0 : remaining - monthly * (payments - 1) };
}
export function annualPlan({ saved, monthly, years, expenseYear = '', expense = '' }) {
  let balance = money(saved, '準備済み資金');
  const deposit = money(monthly, '毎月の積立額'), count = integer(years, 1, 50, '年数');
  const hasExpense = String(expenseYear).trim() !== '' || String(expense).trim() !== '';
  const year = hasExpense ? integer(expenseYear, 1, count, '支出する年') : 0;
  const cost = hasExpense ? money(expense, '予定支出額') : 0;
  const rows = [];
  for (let i = 1; i <= count; i++) {
    const start = balance, outflow = i === year ? cost : 0;
    balance += deposit * 12 - outflow;
    if (!Number.isSafeInteger(balance)) throw new RangeError('計算できる金額の範囲を超えています。');
    rows.push({ year: i, start, deposits: deposit * 12, expense: outflow, balance });
  }
  return rows;
}
export function depositEstimate({ principal, months, promoRate, promoMonths, standardRate, fees, tax = '' }) {
  const amount = money(principal, '預入額'), duration = integer(months, 1, 600, '預入月数');
  const promotional = rate(promoRate, '優遇金利'), standard = rate(standardRate, '通常金利');
  const promotionalMonths = Math.min(integer(promoMonths, 0, 600, '優遇月数'), duration);
  const fee = money(fees, '手数料'), taxRate = String(tax).trim() === '' ? 0 : rate(tax, '税率');
  const raw = amount * (promotional / 100 * promotionalMonths / 12 + standard / 100 * (duration - promotionalMonths) / 12);
  const interest = Math.floor(raw + 1e-8), withheld = Math.floor(interest * taxRate / 100 + 1e-8);
  return { interest, tax: withheld, fees: fee, net: interest - withheld - fee, taxIncluded: String(tax).trim() !== '' };
}
