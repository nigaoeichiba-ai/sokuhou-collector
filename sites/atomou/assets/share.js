/* Sharing a day with other people.
   - A public day (an official date with its own page) is shared as a link: LINE, X, copy, the phone's own share sheet, or a picture of the count.
   - A day of the visitor's own is shared as words and a picture only, never as a link to it: it has no page, and the title is left out unless the visitor ticks it.
   Nothing here is sent to our server: the buttons open the other app with the words in the address, or make the words / the picture on this device.
   The only thing counted is how many times each button was pressed (act:share:...), the same fixed list as the other buttons. */
(function () {
  'use strict';
  var A = window.AtomouApp;
  if (!A) return;
  var C = A.C, TODAY = A.TODAY, H = A.H;

  function enc(s) { return encodeURIComponent(s); }
  function fmt(d, p) {
    if (!d) return '';
    return d[0] + '年' + (p === 'year' ? '' : d[1] + '月' + (p === 'month' ? '' : d[2] + '日'));
  }
  function pageUrl() { return location.origin + location.pathname; }

  /* the words: "「共通テスト」(2027年1月16日)まで、あと98日。" */
  function words(box) {
    if (box.hasAttribute('data-text')) return box.getAttribute('data-text');
    var title = box.getAttribute('data-title') || '', d = C.parse(box.getAttribute('data-date') || ''), p = box.getAttribute('data-p') || 'day';
    var priv = box.getAttribute('data-private') === '1', check = box.querySelector('[data-share-title]');
    if (priv && !(check && check.checked)) title = '';
    var name = title ? '「' + title + '」' : 'ある日';
    if (!d) return title || '';
    var when = fmt(d, p), n = C.totalDays(TODAY, d), line;
    if (p !== 'day') line = name + 'は' + when + 'です。';
    else if (n > 0) line = name + (title ? '(' + when + ')' : '') + 'まで、あと' + n + '日。';
    else if (n === 0) line = name + 'は今日です。';
    else line = name + (title ? '(' + when + ')' : '') + 'から、もう' + (-n) + '日。';
    return line;
  }
  function message(box) {
    var priv = box.getAttribute('data-private') === '1', url = priv ? location.origin + '/' : (box.getAttribute('data-url') || pageUrl());
    if (box.getAttribute('data-nolink') === '1') return { text: words(box), url: '' };   // sent as words only (the plus plan): no signature, no link
    if (box.hasAttribute('data-text')) return { text: words(box), url: url };
    return { text: words(box) + (priv ? '\n日数は「あと何日、もう何日」で数えています。' : '\n出典つきの公式の日付です。'), url: url };
  }

  function lineUrl(m) { return 'https://line.me/R/msg/text/?' + enc(m.text + (m.url ? '\n' + m.url : '')); }
  function xUrl(m) { return 'https://twitter.com/intent/tweet?text=' + enc(m.text) + (m.url ? '&url=' + enc(m.url) : ''); }
  function refresh(box) {
    var m = message(box), l = box.querySelector('[data-share-to="line"]'), x = box.querySelector('[data-share-to="x"]');
    if (l) l.href = lineUrl(m);
    if (x) x.href = xUrl(m);
  }

  /* a picture of the count, drawn on this device (1200 x 630: the size the other apps show in a chat) */
  function drawCard(box) {
    var cv = document.createElement('canvas'), W = 1200, Hh = 630, g = cv.getContext('2d'), cs = getComputedStyle(document.documentElement);
    function v(n, d) { var x = cs.getPropertyValue(n).trim(); return x || d; }
    var font = getComputedStyle(document.body).fontFamily || 'sans-serif', accent = v('--accent', '#1A56B8'), text = v('--text', '#1A1A1A'), muted = v('--muted', '#5A5A55'), bg = v('--surface', '#FFFFFF');
    cv.width = W; cv.height = Hh;
    g.fillStyle = bg; g.fillRect(0, 0, W, Hh);
    g.fillStyle = accent; g.fillRect(0, 0, W, 18);
    var title = box.getAttribute('data-title') || '', d = C.parse(box.getAttribute('data-date') || ''), p = box.getAttribute('data-p') || 'day';
    var priv = box.getAttribute('data-private') === '1', check = box.querySelector('[data-share-title]');
    if (priv && !(check && check.checked)) title = '';
    g.textBaseline = 'alphabetic';
    g.fillStyle = muted; g.font = '700 34px ' + font; g.fillText('あと何日、もう何日', 60, 90);
    // the title, wrapped to at most three lines
    g.fillStyle = text; g.font = '800 58px ' + font;
    var lines = [], cur = '', i, ch, maxW = W - 120;
    for (i = 0; i < title.length; i++) {
      ch = title.charAt(i);
      if (g.measureText(cur + ch).width > maxW) { lines.push(cur); cur = ch; } else cur += ch;
    }
    if (cur) lines.push(cur);
    if (lines.length > 3) { lines = lines.slice(0, 3); lines[2] = lines[2].slice(0, -1) + '…'; }
    var y = 180;
    lines.forEach(function (ln) { g.fillText(ln, 60, y); y += 72; });
    // the number
    var big;
    if (!d || p !== 'day') big = fmt(d, p);
    else { var n = C.totalDays(TODAY, d); big = n > 0 ? 'あと' + n + '日' : n === 0 ? '今日' : 'もう' + (-n) + '日'; }
    g.fillStyle = accent; g.font = '900 170px ' + font;
    var by = Math.max(y + 150, 450);
    g.fillText(big, 60, by);
    g.fillStyle = muted; g.font = '600 36px ' + font;
    if (d) g.fillText(fmt(d, p), 66, by + 62);
    g.textAlign = 'right'; g.fillText('atomou.com', W - 60, Hh - 40);
    return cv;
  }
  function saveImage(box) {
    var cv = drawCard(box);
    cv.toBlob(function (blob) {
      if (!blob) { A.toast('画像を作れませんでした。'); return; }
      var file;
      try { file = new File([blob], 'atomou.png', { type: 'image/png' }); } catch (e) { file = null; }
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file] }).catch(function () { /* the visitor closed the sheet */ });
        return;
      }
      var url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url; a.download = 'atomou.png'; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
      A.toast('画像を保存しました。');
    }, 'image/png');
  }
  var lastBump = 0;
  function bump() {   // one more send for the free plan's room; a quick run of clicks counts once
    var now = Date.now();
    if (!A.tier || now - lastBump < 20000) return;
    lastBump = now; A.tier.shared();
  }
  function copy(m) {
    var t = m.text + (m.url ? '\n' + m.url : '');
    function done() { A.toast('文面とリンクをコピーしました。'); bump(); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, fallback);
    else fallback();
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = t; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { A.toast('コピーできませんでした。'); }
      ta.remove();
    }
  }

  function init(root) {
    var boxes = (root || document).querySelectorAll('.share');
    Array.prototype.forEach.call(boxes, function (box) {
      refresh(box);
      var nat = box.querySelector('[data-share="native"]');
      if (nat && navigator.share) nat.hidden = false;
      var check = box.querySelector('[data-share-title]');
      if (check && !check.getAttribute('data-bound')) { check.setAttribute('data-bound', '1'); check.addEventListener('change', function () { refresh(box); }); }
    });
  }
  document.addEventListener('click', function (ev) {
    var t = ev.target.closest ? ev.target.closest('[data-share],[data-share-to]') : null;
    if (!t) return;
    var box = t.closest('.share');
    if (!box) return;
    var what = t.getAttribute('data-share') || t.getAttribute('data-share-to'), m = message(box);
    A.stat('act:share:' + what);
    if (t.hasAttribute('data-share-to')) bump();
    if (t.hasAttribute('data-share-to')) { refresh(box); return; }   // a link: the browser follows it
    ev.preventDefault();
    if (what === 'copy') copy(m);
    else if (what === 'image') { saveImage(box); bump(); }
    else if (what === 'native' && navigator.share) navigator.share({ text: m.text, url: m.url }).then(bump, function () { /* closed */ });
  });

  /* "Googleカレンダーに追加": the address that opens Google Calendar's own form with the day filled in (a whole day: the end is the next day) */
  function googleUrl(title, iso, detail) {
    var d = C.parse(iso);
    if (!d) return '';
    function s(a) { return String(a[0]).padStart(4, '0') + String(a[1]).padStart(2, '0') + String(a[2]).padStart(2, '0'); }
    return 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=' + enc(title) + '&dates=' + s(d) + '/' + s(C.addDays(d, 1)) + '&details=' + enc(detail || '') + '&ctz=Asia%2FTokyo';
  }

  function outlookUrl(title, iso, detail) {
    var d = C.parse(iso);
    if (!d) return '';
    function s(a) { return String(a[0]).padStart(4, '0') + '-' + String(a[1]).padStart(2, '0') + '-' + String(a[2]).padStart(2, '0'); }
    return 'https://outlook.live.com/calendar/0/deeplink/compose?path=%2Fcalendar%2Faction%2Fcompose&rru=addevent&subject=' + enc(title) + '&startdt=' + s(d) + '&enddt=' + s(C.addDays(d, 1)) + '&allday=true&body=' + enc(detail || '');
  }

  var ICON = {
    line: '<path d="M4 5h16v11h-8.5L7 20v-4H4z"/>', x: '<path d="M5 5l14 14M19 5L5 19"/>',
    copy: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    image: '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M4 17l5-5 4 4 3-3 4 4"/>',
    native: '<circle cx="6" cy="12" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="17" cy="18" r="2"/><path d="M8 11l7-4M8 13l7 4"/>'
  };
  var LABEL = { line: 'LINEで送る', x: 'Xで投稿', copy: 'リンクをコピー', image: '画像で保存', native: 'ほかのアプリで送る' };
  function icons(kinds) {   /* one thin row of small icon buttons (the words are for screen readers and the tooltip) */
    return kinds.map(function (k) {
      var svg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICON[k] + '</svg><span class="vh">' + LABEL[k] + '</span>';
      return (k === 'line' || k === 'x') ? '<a class="sbt" data-share-to="' + k + '" href="#" target="_blank" rel="noopener" title="' + LABEL[k] + '">' + svg + '</a>'
        : '<button type="button" class="sbt" data-share="' + k + '" title="' + LABEL[k] + '"' + (k === 'native' ? ' hidden' : '') + '>' + svg + '</button>';
    }).join('');
  }

  init();
  window.AtomouShare = { icons: icons, init: init, words: words, googleUrl: googleUrl, outlookUrl: outlookUrl, drawCard: drawCard };
})();
