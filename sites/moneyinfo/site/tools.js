import { savings, annualPlan, monthDifference, depositEstimate } from './calculators.js';

const yen = value => `${new Intl.NumberFormat('ja-JP').format(value)}円`;
const $ = selector => document.querySelector(selector);
const tabs = [...document.querySelectorAll('[data-tool]')];
const IDs = tabs.map(tab => tab.dataset.tool);
const text = (tag, content, className = '') => {
  const element = document.createElement(tag);
  element.textContent = content;
  if (className) element.className = className;
  return element;
};
function selectTool(key, changeHash = false, focus = false) {
  const chosen = IDs.includes(key) ? key : 'savings';
  tabs.forEach(tab => {
    const active = tab.dataset.tool === chosen;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    $(`#${tab.dataset.tool}-panel`).hidden = !active;
    if (active && focus) tab.focus();
  });
  if (changeHash) history.replaceState(null, '', `#${chosen}`);
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTool(tab.dataset.tool, true));
  tab.addEventListener('keydown', e => {
    let next;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (index + 1) % tabs.length;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (index + tabs.length - 1) % tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = tabs.length - 1;
    if (next !== undefined) { e.preventDefault(); selectTool(tabs[next].dataset.tool, true, true); }
  });
});
selectTool(location.hash.slice(1));
window.addEventListener('hashchange', () => selectTool(location.hash.slice(1)));

function currentJSTMonth() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit' }).formatToParts(new Date()).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}`;
}
function nextMonth(month) {
  const [y, m] = month.split('-').map(Number), date = new Date(Date.UTC(y, m, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}
$('#deadline').min = nextMonth(currentJSTMonth());
function error(id, message) {
  const box = $(`#${id}`); box.textContent = message; box.hidden = false; box.scrollIntoView({ block: 'nearest' });
}
function clearError(id) { $(`#${id}`).hidden = true; $(`#${id}`).textContent = ''; }
function result(id, title, nodes) {
  const box = $(`#${id}`);
  box.replaceChildren(text('h2', title), ...nodes);
}
function formInput(id) { return Object.fromEntries(new FormData($(`#${id}`))); }
const initialMessages = {
  savings: '目標額・準備済み資金・目標月を入力してください。',
  annual: '毎月の積立と予定支出を入力すると、年ごとの残高を確認できます。',
  deposit: 'ご自身で確認した条件を入力してください。特定の金融機関を推奨するものではありません。'
};
let planRows = null;
for (const id of IDs) {
  $(`#${id}-form`).addEventListener('input', () => {
    clearError(`${id}-error`);
    result(`${id}-result`, id === 'annual' ? '計画の確認' : id === 'deposit' ? '比較結果' : '計算結果', [text('p', '入力内容が変わりました。計算ボタンで結果を更新してください。')]);
    if (id === 'annual') { $('#annual-table-area').hidden = true; planRows = null; }
  });
  $(`#${id}-form`).addEventListener('reset', () => {
    clearError(`${id}-error`);
    result(`${id}-result`, '計算結果', [text('p', initialMessages[id])]);
    if (id === 'annual') { $('#annual-table-area').hidden = true; planRows = null; }
  });
}

$('#savings-form').addEventListener('submit', event => {
  event.preventDefault(); clearError('savings-error');
  try {
    const fields = formInput('savings-form');
    const months = monthDifference(currentJSTMonth(), fields.deadline);
    const value = savings({ target: fields.target, saved: fields.saved, months });
    const amount = text('strong', yen(value.monthly), 'result-number');
    const detail = text('p', `残りの準備額 ${yen(value.remaining)} ／ 積立回数 ${months}回`, 'result-detail');
    let notes = '準備済み資金で目標額に達しています。支払う時期と、用途を重複させていないかも確認しましょう。';
    if (value.remaining > 0) {
      const adjustment = value.finalDeposit === value.monthly
        ? ''
        : `最終回は${yen(value.finalDeposit)}に調整します。`;
      notes = `翌月から計${value.payments}回積み立てます。${adjustment}`;
    }
    result('savings-result', '毎月の準備額', [amount, detail, text('p', notes)]);
  } catch (e) { error('savings-error', e.message); }
});

$('#annual-form').addEventListener('submit', event => {
  event.preventDefault(); clearError('annual-error');
  try {
    const fields = formInput('annual-form');
    planRows = annualPlan({ saved: fields['annual-saved'], monthly: fields.monthly, years: fields.years, expenseYear: fields['expense-year'], expense: fields.expense });
    const final = planRows.at(-1), firstShortage = planRows.find(row => row.balance < 0);
    result('annual-result', `${final.year}年目の年末残高`, [text('strong', yen(final.balance), `result-number${final.balance < 0 ? ' negative' : ''}`), text('p', firstShortage ? `${firstShortage.year}年目に年末残高がマイナスになります。支出額・時期・積立額を見直す条件を考えましょう。` : '入力した予定では、各年の年末残高はマイナスになりません。年の途中の支払時期も別に確認しましょう。')]);
    const tbody = $('#annual-table tbody'); tbody.replaceChildren();
    for (const row of planRows) {
      const tr = document.createElement('tr');
      const year = text('th', `${row.year}年目`); year.scope = 'row'; tr.append(year);
      for (const value of [row.start, row.deposits, row.expense, row.balance]) tr.append(text('td', yen(value), value < 0 ? 'negative' : ''));
      tbody.append(tr);
    }
    $('#annual-table-area').hidden = false;
  } catch (e) { planRows = null; $('#annual-table-area').hidden = true; error('annual-error', e.message); }
});
$('#download-plan').addEventListener('click', () => {
  if (!planRows) return;
  const rows = [['年','年初残高（円）','年間積立額（円）','予定支出（円）','年末残高（円）'], ...planRows.map(r => [r.year,r.start,r.deposits,r.expense,r.balance])];
  const csv = '\ufeff' + rows.map(row => row.join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = '暮らしのマネー情報_積立計画.csv';
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});

$('#deposit-form').addEventListener('submit', event => {
  event.preventDefault(); clearError('deposit-error');
  try {
    const fields = formInput('deposit-form');
    const estimates = ['a','b'].map(key => depositEstimate({ principal: fields.principal, months: fields.term, promoRate: fields[`${key}-promo`], promoMonths: fields[`${key}-months`], standardRate: fields[`${key}-standard`], fees: fields[`${key}-fees`], tax: fields.tax }));
    const comparison = document.createElement('div'); comparison.className = 'tool-comparison';
    estimates.forEach((value, index) => {
      const section = document.createElement('section');
      section.append(text('h3', `比較条件 ${index === 0 ? 'A' : 'B'}`), text('strong', yen(value.net), 'result-number'), text('p', `利息 ${yen(value.interest)} ／ 税 ${value.taxIncluded ? yen(value.tax) : '未計算'} ／ 手数料 ${yen(value.fees)}`, 'result-detail'));
      comparison.append(section);
    });
    const difference = Math.abs(estimates[0].net - estimates[1].net);
    const caption = difference === 0 ? '入力した条件での差はありません。' : `利息から入力した税・手数料を引いた金額の差は${yen(difference)}です。`;
    result('deposit-result', '利息から税・手数料を引いた概算額', [comparison, text('p', caption), text('p', fields.tax.trim() === '' ? '税率が空欄のため、税引前の比較です。実際の税・適用条件は別に確認してください。' : '入力した税率による概算です。金融機関の実際の端数処理・日割り計算等とは異なる場合があります。', 'fine')]);
  } catch (e) { error('deposit-error', e.message); }
});
