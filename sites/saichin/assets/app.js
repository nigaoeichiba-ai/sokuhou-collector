/* Progressive enhancement only: every page is complete HTML without this script. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const yen = (n) => n.toLocaleString('ja-JP') + '円';
  const jp = (iso) => { const [y, m, d] = iso.split('-').map(Number); return y + '年' + m + '月' + d + '日'; };
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const daysBetween = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000);
  const stateOf = (iso) => {
    const diff = daysBetween(today, iso);
    return diff <= 0 ? { code: 'done', text: '発効済み' } : { code: 'soon', text: 'あと' + diff + '日' };
  };

  document.querySelectorAll('.js-only').forEach((el) => { el.hidden = false; });

  // Status labels on tables, cards and calendar days.
  document.querySelectorAll('td.state[data-date]').forEach((td) => {
    const s = stateOf(td.dataset.date);
    td.textContent = s.text; td.className = 'state ' + s.code;
  });
  document.querySelectorAll('.chip.state[data-date]').forEach((chip) => {
    const s = stateOf(chip.dataset.date);
    chip.textContent = s.text; chip.className = 'chip state ' + s.code;
  });
  document.querySelectorAll('.cal-day[data-date]').forEach((day) => {
    if (stateOf(day.dataset.date).code === 'done') day.classList.add('past');
  });

  // Hero progress.
  const cards = document.querySelectorAll('.pref-card[data-date]');
  if (cards.length && $('done-count')) {
    const done = [...cards].filter((c) => stateOf(c.dataset.date).code === 'done').length;
    $('done-count').textContent = String(done);
    $('done-bar').style.width = Math.round((done / cards.length) * 100) + '%';
  }

  // Prefecture page status line.
  const status = document.querySelector('[data-status]');
  if (status) {
    const s = stateOf(status.dataset.date);
    const amount = Number(status.dataset.amount);
    status.textContent = s.code === 'done'
      ? jp(status.dataset.date) + ' に発効済みです。現在の最低賃金は ' + yen(amount) + ' です。'
      : jp(status.dataset.date) + ' に ' + yen(amount) + ' になります(' + s.text + ')。それまでは ' + yen(Number(status.dataset.prev)) + ' です。';
  }

  // Sortable, filterable table.
  const table = $('wage-table');
  if (table) {
    const body = table.tBodies[0];
    const rows = [...body.rows];
    const q = $('q'), st = $('status');
    let sortKey = 'date', dir = 1;
    const val = (tr, k) => (k === 'name' ? tr.dataset.name : k === 'state' ? tr.dataset.date : Number(tr.dataset[k]) || tr.dataset[k]);
    function render() {
      const term = q.value.trim(), want = st.value;
      const shown = rows.filter((tr) => {
        const code = stateOf(tr.dataset.date).code;
        return (!term || tr.dataset.name.includes(term)) && (!want || code === want);
      });
      shown.sort((a, b) => {
        const x = val(a, sortKey), y = val(b, sortKey);
        return (x < y ? -1 : x > y ? 1 : a.dataset.name.localeCompare(b.dataset.name, 'ja')) * dir;
      });
      body.replaceChildren(...shown);
      table.querySelectorAll('th[data-key]').forEach((th) => {
        if (th.dataset.key === sortKey) th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
        else th.removeAttribute('aria-sort');
      });
    }
    table.querySelectorAll('th[data-key]').forEach((th) => th.addEventListener('click', () => {
      dir = sortKey === th.dataset.key ? -dir : 1; sortKey = th.dataset.key; render();
    }));
    q.addEventListener('input', render); st.addEventListener('change', render);
    render();
  }

  const dataEl = $('data');
  const prefs = dataEl ? JSON.parse(dataEl.textContent) : [];
  const currentAmount = (row) => (stateOf(row.date).code === 'done' ? row.amount : row.prev);

  // "Is my hourly wage enough?" checker on the front page.
  if (prefs.length && $('check-out')) {
    const sel = $('pref'), wage = $('wage'), out = $('check-out');
    const check = () => {
      const row = prefs.find((r) => r.name === sel.value), w = Number(wage.value);
      if (!row || !wage.value || !Number.isFinite(w) || w < 0) { out.textContent = '都道府県と時給を入れると、現在の最低賃金と比べます。'; return; }
      const s = stateOf(row.date), cur = currentAmount(row);
      let msg = row.name + 'の現在の最低賃金は ' + yen(cur) + ' です。';
      msg += w >= cur ? 'あなたの時給 ' + yen(w) + ' は、現在の額以上です。' : 'あなたの時給 ' + yen(w) + ' は、現在の額を下回っています。';
      if (s.code === 'soon') msg += ' ' + jp(row.date) + ' から ' + yen(row.amount) + ' になります。' + (w >= row.amount ? '' : 'その日以降は、' + yen(row.amount - w) + ' 足りなくなります。');
      out.textContent = msg;
    };
    sel.addEventListener('input', check); wage.addEventListener('input', check);
  }

  // Monthly-wage converter on the guide page.
  const calc = $('calc');
  if (calc && prefs.length) {
    const sel = $('calc-pref'), pay = $('calc-pay'), hours = $('calc-hours'), days = $('calc-days'), out = $('calc-out');
    sel.replaceChildren(new Option('都道府県を選ぶ', ''), ...prefs.map((r) => new Option(r.name, r.name)));
    const run = () => {
      const row = prefs.find((r) => r.name === sel.value);
      const p = Number(pay.value), h = Number(hours.value), d = Number(days.value);
      if (!row || !(p > 0) || !(h > 0) || !(d > 0)) { out.textContent = '必要な項目を入れると、時間額に換算して、最低賃金と比べます。'; return; }
      const monthly = (h * d) / 12, hourly = p / monthly, cur = currentAmount(row), s = stateOf(row.date);
      let msg = '1か月平均所定労働時間は約' + monthly.toFixed(1) + '時間、時間額は約' + Math.round(hourly).toLocaleString('ja-JP') + '円です。' + row.name + 'の現在の最低賃金 ' + yen(cur) + ' と比べると、';
      msg += hourly >= cur ? '現在の額以上です。' : '現在の額を下回っています。';
      if (s.code === 'soon') msg += ' ' + jp(row.date) + ' から ' + yen(row.amount) + ' になります。' + (hourly >= row.amount ? '' : 'その日以降は下回ります。');
      out.textContent = msg;
    };
    [sel, pay, hours, days].forEach((el) => el.addEventListener('input', run));
  }
})();
