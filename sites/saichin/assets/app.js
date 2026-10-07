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

  // Shortfall checker (/check/). The arithmetic is a pure function (exposed as window.saichinCheck) so the browser tests can call it
  // with a fixed date; the DOM part below only reads the form and prints the result. Nothing typed here is sent or stored anywhere.
  const floor1 = (x) => Math.floor(x * 10 + 1e-9) / 10;
  const num1 = (x) => floor1(x).toLocaleString('ja-JP', { minimumFractionDigits: Number.isInteger(floor1(x)) ? 0 : 1, maximumFractionDigits: 1 });
  const KIND_TEXT = { hourly: '時給', daily: '日給', monthly: '月給' };

  const ceil1 = (x) => Math.ceil(x * 10 - 1e-9) / 10;
  const fmtUp = (n) => Math.max(1, Math.ceil(n - 1e-9)).toLocaleString('ja-JP');
  const given = (v) => v !== '' && v != null;
  function evaluateCheck(inp, row, todayIso) {
    if (!row) return { error: '都道府県を選んでください。' };
    const kind = inp.kind;
    if (!KIND_TEXT[kind]) return { error: '賃金の形を選んでください。' };
    const pay = Number(inp.pay);
    if (!(pay > 0) || !Number.isFinite(pay)) return { error: KIND_TEXT[kind] + 'の金額を入れてください。' };
    const excluded = kind === 'hourly' ? 0 : Number(inp.excluded) || 0;
    if (!Number.isFinite(excluded) || excluded < 0) return { error: '手当の金額が正しくありません。0以上の数で入れてください。' };
    const hours = given(inp.hours) ? Number(inp.hours) : NaN, days = given(inp.days) ? Number(inp.days) : NaN;
    const hoursOk = hours > 0 && hours <= 24, daysOk = days > 0 && days <= 366;
    // A day's hours matter for daily and monthly pay, the year's days for monthly pay; for the others they only turn the gap into a month and a year.
    if ((kind !== 'hourly' || given(inp.hours)) && !hoursOk) return { error: '1日の所定労働時間は、0より大きく24以下の数で入れてください。' };
    if ((kind === 'monthly' || given(inp.days)) && !daysOk) return { error: '年間の所定労働日数は、1〜366の数で入れてください。' };
    if (kind !== 'hourly' && excluded >= pay) return { error: '除外する手当が、' + KIND_TEXT[kind] + 'の金額以上になっています。入力を確かめてください。' };
    const effective = pay - excluded;
    const monthlyHours = hoursOk && daysOk ? (hours * days) / 12 : null;
    const hourly = kind === 'hourly' ? pay : kind === 'daily' ? effective / hours : effective / monthlyHours;
    const done = daysBetween(todayIso, row.date) <= 0;
    const rates = done
      ? [{ key: 'now', min: row.amount, since: row.date }]
      : [{ key: 'now', min: row.prev, until: row.date }, { key: 'new', min: row.amount, since: row.date }];
    const periods = rates.map((r) => {
      // The verdict compares without dividing, so float noise at the boundary (180,000 / (2,000 / 12) = 1,080.0000000000002) cannot flip it.
      const ok = kind === 'hourly' ? pay >= r.min : kind === 'daily' ? effective >= r.min * hours : effective * 12 >= r.min * hours * days;
      const gap = r.min - hourly;
      const base = kind === 'hourly' ? r.min : kind === 'daily' ? Math.ceil(r.min * hours - 1e-9) : Math.ceil(r.min * monthlyHours - 1e-9);
      const known = !ok && monthlyHours !== null;
      return Object.assign({}, r, {
        gap, ok, perMonth: ok ? 0 : known ? Math.max(gap, 0) * monthlyHours : null, perYear: ok ? 0 : known ? Math.max(gap, 0) * monthlyHours * 12 : null,
        required: base + excluded,
      });
    });
    const steps = [];
    if (kind === 'hourly') {
      steps.push('時給 ' + yen(pay) + ' をそのまま、最低賃金(時間額)と比べます。');
    } else {
      steps.push(KIND_TEXT[kind] + ' ' + yen(pay) + ' − 最低賃金の対象にならない手当 ' + yen(excluded) + ' = 対象になる賃金 ' + yen(effective));
      if (kind === 'monthly') {
        steps.push('1か月平均所定労働時間 = ' + hours + '時間 × ' + days + '日 ÷ 12か月 = ' + num1(monthlyHours) + '時間');
        steps.push('時間額 = ' + yen(effective) + ' ÷ ' + num1(monthlyHours) + '時間 = 約' + num1(hourly) + '円');
      } else {
        steps.push('時間額 = ' + yen(effective) + ' ÷ 1日の所定労働時間 ' + hours + '時間 = 約' + num1(hourly) + '円');
      }
    }
    return { kind, pay, excluded, effective, hours, days, monthlyHours, hourly, done, periods, steps, row };
  }
  window.saichinCheck = { evaluate: evaluateCheck };

  const chk = $('chk-form');
  if (chk && prefs.length) {
    const sel = $('chk-pref'), out = $('chk-out'), pay = $('chk-pay'), hours = $('chk-hours'), days = $('chk-days');
    const kinds = [...chk.querySelectorAll('input[name="chk-kind"]')];
    const exclFields = [...chk.querySelectorAll('[data-excl]')];
    sel.replaceChildren(new Option('都道府県を選ぶ', ''), ...prefs.map((r) => new Option(r.name, r.name)));
    const fromUrl = new URLSearchParams(location.search).get('pref');
    if (fromUrl && prefs.some((r) => r.name === fromUrl)) sel.value = fromUrl;
    const kind = () => (kinds.find((k) => k.checked) || {}).value || 'monthly';
    const syncKind = () => {
      const k = kind();
      $('chk-pay-label').firstChild.textContent = KIND_TEXT[k] + '(円)';
      $('chk-excl').hidden = k === 'hourly';
      $('chk-excl-legend').textContent = '最低賃金の対象にならない手当(' + (k === 'daily' ? '1日あたり' : '1か月あたり') + 'の額。ないものは空欄)';
      $('chk-days-label').firstChild.textContent = k === 'hourly' ? '年間の所定労働日数(月・年の不足額を出すための入力)' : '年間の所定労働日数';
    };
    const render = () => {
      const r = prefs.find((p) => p.name === sel.value);
      const excluded = exclFields.reduce((s, f) => s + Math.max(0, Number(f.value) || 0), 0);
      const res = evaluateCheck({ kind: kind(), pay: pay.value, excluded, hours: hours.value, days: days.value }, r, today);
      out.classList.remove('ok', 'ng');
      if (res.error) { out.textContent = pay.value ? res.error : '都道府県と賃金を入れると、最低賃金との差額を計算します。'; return; }
      const [a, b] = res.periods;
      const last = res.periods[res.periods.length - 1];
      let head, cls;
      if (res.done || (a.ok && b.ok)) {
        cls = last.ok ? 'ok' : 'ng';
        head = last.ok
          ? (res.done ? '最低賃金以上です。' : '現在も、' + jp(r.date) + '以降の新しい額でも、最低賃金以上です。')
          : '最低賃金を下回っています。';
      } else if (a.ok) {
        cls = 'ng'; head = '現在は最低賃金以上ですが、' + jp(r.date) + '以降は下回ります。';
      } else {
        cls = 'ng'; head = '現在の最低賃金を下回っています。';
      }
      const title = (p) => (res.done ? jp(p.since) + 'から(現在の額)' : p.key === 'new' ? jp(p.since) + 'から(新しい額)' : '今(' + jp(p.until) + 'の前日まで)');
      const fmtGap = (p) => (p.ok ? '余裕 ' + num1(-p.gap) + '円' : '不足 ' + Math.max(0.1, ceil1(p.gap)).toLocaleString('ja-JP', { minimumFractionDigits: Number.isInteger(Math.max(0.1, ceil1(p.gap))) ? 0 : 1, maximumFractionDigits: 1 }) + '円');
      const need = { hourly: '時給', daily: '日給', monthly: '月給' }[res.kind];
      const line = (k, v) => '<dt>' + k + '</dt><dd>' + v + '</dd>';
      const table = '<div class="chk-periods">' + res.periods.map((p) => {
        const c = p.ok ? 'ok' : 'ng';
        return '<section class="chk-period ' + c + '"><h3>' + title(p) + '</h3><dl>' +
          line(r.name + 'の最低賃金', '<b>' + yen(p.min) + '</b>') +
          line('あなたの時間額(換算後)', '約' + num1(res.hourly) + '円') +
          line('判定', '<b class="' + c + '">' + (p.ok ? '最低賃金以上' : '下回っています') + '</b>') +
          line('1時間あたりの差', '<b class="' + c + '">' + fmtGap(p) + '</b>') +
          (p.ok || p.perMonth === null ? '' : line('1か月あたりの不足額', '約' + fmtUp(p.perMonth) + '円') + line('1年あたりの不足額', '約' + fmtUp(p.perYear) + '円')) +
          line('最低賃金を満たす' + need + 'の目安' + (res.kind === 'hourly' ? '' : '(手当を含む)'), yen(p.required)) +
          '</dl></section>';
      }).join('') + '</div>';
      const summary = r.name + ' / ' + KIND_TEXT[res.kind] + ' ' + yen(res.pay) + (res.excluded ? '(うち除外する手当 ' + yen(res.excluded) + ')' : '') +
        ' / 1日 ' + res.hours + '時間・年 ' + res.days + '日';
      out.classList.add(cls);
      out.innerHTML = '<p class="chk-head ' + cls + '">' + head + '</p><p class="chk-sum">' + summary + '</p>' + table +
        '<details class="chk-steps"><summary>計算の内訳</summary><ol>' + res.steps.map((s) => '<li>' + s + '</li>').join('') + '</ol></details>' +
        '<p class="chk-date">計算した日: ' + jp(today) + '(あなたの端末の中だけで計算しています。入力した内容は送信も保存もしません)</p>';
    };
    syncKind(); render();
    chk.addEventListener('input', (e) => { if (e.target.name === 'chk-kind') syncKind(); render(); });
    const printBtn = $('chk-print');
    if (printBtn) printBtn.addEventListener('click', () => window.print());
  }
})();

/* motion: count-up for the headline number and reveal-on-scroll for cards below the fold. Never hides anything without JS,
   skips everything under prefers-reduced-motion. */
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;
  var root = document.documentElement;
  root.classList.add("js");

  var big = document.querySelector(".big");
  if (big) {
    var node = null;
    for (var i = 0; i < big.childNodes.length; i++) {
      if (big.childNodes[i].nodeType === 3 && /\d/.test(big.childNodes[i].textContent)) { node = big.childNodes[i]; break; }
    }
    var m = node && node.textContent.match(/^(\D*)([\d,]+)(.*)$/);
    if (m) {
      var target = parseInt(m[2].replace(/,/g, ""), 10), start = null, dur = 900;
      var step = function (t) {
        if (start === null) start = t;
        var p = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - p, 3);
        node.textContent = m[1] + Math.round(target * e).toLocaleString("ja-JP") + m[3];
        if (p < 1) requestAnimationFrame(step); else node.textContent = m[0];
      };
      node.textContent = m[1] + "0" + m[3];
      requestAnimationFrame(step);
    }
  }

  if (!("IntersectionObserver" in window)) return;
  var targets = document.querySelectorAll(".stat, .box, .bar-list li, .guide-card, .rel-grid a, .tilemap-box, .mypref, .next-box, .chart-box, .pref-card");
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
    });
  }, { rootMargin: "0px 0px -8% 0px" });
  Array.prototype.forEach.call(targets, function (el) {
    var r = el.getBoundingClientRect();
    if (r.top > window.innerHeight) { el.classList.add("rv"); io.observe(el); }
  });
})();
