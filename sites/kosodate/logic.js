/* Pure date/timeline logic. Dates are UTC-midnight "calendar dates" so DST and time zones cannot shift them. */
(function (root) {
  'use strict';
  const DAY = 86400000;
  const utc = (y, m, d) => new Date(Date.UTC(y, m - 1, d));
  const addDays = (d, n) => new Date(d.getTime() + n * DAY);

  function addMonths(d, n) {
    const y = d.getUTCFullYear();
    const m = d.getUTCMonth() + n;
    const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    return new Date(Date.UTC(y, m, Math.min(d.getUTCDate(), last)));
  }

  function parseDate(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    if (!m) return null;
    const d = utc(+m[1], +m[2], +m[3]);
    return d.getUTCMonth() + 1 === +m[2] && d.getUTCDate() === +m[3] ? d : null;
  }

  /* A child born 4/2 of year Y .. 4/1 of Y+1 enters elementary school in April of Y+7
     (age is reached on the day before the birthday, so 4/1-born children belong to the earlier cohort). */
  function schoolEntryYear(birth) {
    const y = birth.getUTCFullYear();
    const m = birth.getUTCMonth() + 1;
    const d = birth.getUTCDate();
    return m < 4 || (m === 4 && d === 1) ? y + 6 : y + 7;
  }

  function resolve(item, birth) {
    const r = item.rule;
    if (r.type === 'days') return { start: addDays(birth, r.start), end: addDays(birth, r.end) };
    if (r.type === 'weeks') return { start: addDays(birth, r.start * 7), end: addDays(birth, r.end * 7) };
    if (r.type === 'months') {
      return { start: addMonths(birth, r.start), end: r.end == null ? null : addMonths(birth, r.end) };
    }
    if (r.type === 'school') {
      const e = schoolEntryYear(birth);
      const at = (p) => (p ? utc(e + p.y, p.m, p.d) : null);
      return { start: at(r.start), end: at(r.end), showFrom: at(r.showFrom) };
    }
    throw new Error('unknown rule type: ' + r.type);
  }

  /* Only items with a source URL, a legal/official basis and a verification date may be shown. */
  function publishable(item) {
    return Boolean(item && item.source && item.source.url && item.basis && item.verifiedAt);
  }

  /* `showFrom` is display-only: it keeps an end-dated item out of the "now" list until it is relevant.
     Open-ended items (no end) count as "now" for 12 months from their start, then move to "past". */
  const shownFrom = (range) => range.start || range.showFrom || null;

  function classify(range, today) {
    const from = shownFrom(range);
    const end = range.end || (from ? addMonths(from, 12) : null);
    if (end && today.getTime() > end.getTime()) return 'past';
    if (from && today.getTime() < from.getTime()) return 'upcoming';
    return 'now';
  }

  function timeline(items, birth, today) {
    const out = { now: [], upcoming: [], past: [] };
    for (const item of items.filter(publishable)) {
      const range = resolve(item, birth);
      out[classify(range, today)].push({ item, range });
    }
    const key = (e) => (e.range.end || shownFrom(e.range)).getTime();
    out.now.sort((a, b) => key(a) - key(b));
    out.upcoming.sort((a, b) => shownFrom(a.range).getTime() - shownFrom(b.range).getTime());
    out.past.sort((a, b) => key(b) - key(a));
    return out;
  }

  function fmt(d) {
    return d.getUTCFullYear() + '年' + (d.getUTCMonth() + 1) + '月' + d.getUTCDate() + '日';
  }

  root.Kosodate = { utc, addDays, addMonths, parseDate, schoolEntryYear, resolve, publishable, classify, timeline, fmt };
})(typeof window !== 'undefined' ? window : globalThis);
