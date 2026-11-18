(() => {
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#main-nav');
  function closeMenu(restoreFocus = false) {
    if (!toggle || !nav) return;
    nav.dataset.open = 'false';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'メニューを開く');
    if (restoreFocus) toggle.focus();
  }
  toggle?.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
    nav.dataset.open = String(open);
  });
  nav?.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') closeMenu(true);
  });
  document.addEventListener('click', e => {
    if (toggle?.getAttribute('aria-expanded') === 'true' && !e.target.closest('.site-header')) closeMenu();
  });
  const media = window.matchMedia('(min-width: 801px)');
  media.addEventListener('change', () => closeMenu());

  const caseFilters = document.querySelector('#case-filters');
  if (caseFilters) {
    const theme = document.querySelector('#case-theme');
    const household = document.querySelector('#case-household');
    const count = document.querySelector('#case-count');
    const cards = [...document.querySelectorAll('[data-case-theme]')];
    const applyCaseFilters = () => {
      let visible = 0;
      for (const card of cards) {
        card.hidden = Boolean(
          (theme.value && theme.value !== card.dataset.caseTheme) ||
          (household.value && household.value !== card.dataset.caseHousehold),
        );
        if (!card.hidden) visible++;
      }
      count.textContent = visible ? `${visible}件を表示` : '該当する記事はありません。条件を変えてお探しください。';
    };
    caseFilters.hidden = false;
    caseFilters.addEventListener('change', applyCaseFilters);
    applyCaseFilters();
  }

  const quoteCompare = document.querySelector('[data-quote-compare]');
  if (quoteCompare) {
    const first = quoteCompare.elements.namedItem('first');
    const second = quoteCompare.elements.namedItem('second');
    const result = quoteCompare.querySelector('output');
    quoteCompare.hidden = false;
    quoteCompare.addEventListener('input', () => { result.textContent = ''; });
    quoteCompare.addEventListener('submit', event => {
      event.preventDefault();
      if (!quoteCompare.checkValidity()) return;
      const delta = first.valueAsNumber - second.valueAsNumber;
      const cheaper = delta > 0 ? quoteCompare.dataset.second : quoteCompare.dataset.first;
      result.textContent = delta === 0
        ? '入力した条件では、支払総額は同じです。'
        : `入力した条件では、${cheaper}の総額が${Math.abs(delta).toLocaleString('ja-JP')}円少なくなります。`;
    });
  }

  const filters = [...document.querySelectorAll('[data-filter]')];
  const eventSections = [...document.querySelectorAll('[data-event]')];
  if (filters.length) {
    function selectEvent(key, updateURL) {
      const allowed = filters.some(button => button.dataset.filter === key);
      const selected = allowed ? key : 'all';
      filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === selected)));
      eventSections.forEach(section => { section.hidden = selected !== 'all' && section.dataset.event !== selected; });
      const label = filters.find(button => button.dataset.filter === selected)?.textContent;
      document.querySelector('#event-status').textContent = selected === 'all' ? 'すべてのイベントを表示しています。' : `${label}の案内を表示しています。`;
      if (updateURL) {
        const url = new URL(location.href);
        if (selected === 'all') url.searchParams.delete('event'); else url.searchParams.set('event', selected);
        history.replaceState(null, '', url);
      }
    }
    filters.forEach(button => button.addEventListener('click', () => selectEvent(button.dataset.filter, true)));
    selectEvent(new URLSearchParams(location.search).get('event') || 'all', false);
    window.addEventListener('popstate', () => selectEvent(new URLSearchParams(location.search).get('event') || 'all', false));
  }
})();
