/* KVITKA — catalog.js
   Author: ISHOD · 2026 · all rights reserved. */
const FILTERS_KEY = 'kvitka:filters-collapsed';

// параметры, у которых может быть несколько значений: ключи из
// catalog/facets.py плюс статус и наличие
const MULTI_PARAMS = ['type', 'flower', 'occasion', 'color', 'size',
  'status', 'stock'];

/**
 * Каталог: фильтры применяются без перезагрузки страницы.
 * Форма остаётся рабочей и без JavaScript — здесь мы только перехватываем
 * изменения и подменяем сетку товаров.
 */

class CatalogPage {
  constructor(root) {
    this.root = root;
    this.form = root.querySelector('[data-filters-form]');
    this.results = root.querySelector('[data-catalog-results]');
    this.counter = root.querySelector('[data-catalog-count]');
    this.sortSelect = root.querySelector('[data-sort]');
    this.reload = KVITKA.debounce(() => this.fetchResults(), 250);
  }

  init() {
    if (!this.form || !this.results) return;

    this.form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.fetchResults();
    });

    this.setupCollapse();
    this.setupRadioReset();

    this.form.addEventListener('change', () => this.reload());
    this.form.addEventListener('input', (event) => {
      if (event.target.type === 'number') this.reload();
    });

    if (this.sortSelect) {
      // select связан с формой через form="catalog-filters",
      // поэтому FormData уже видит его — достаточно перезапросить список
      this.sortSelect.addEventListener('change', () => this.fetchResults());
    }

    this.root.querySelectorAll('[data-facet-search]').forEach((input) => {
      input.addEventListener('input', () => this.filterGroup(input));
      // поиск внутри группы не должен отправлять форму
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') event.preventDefault();
      });
    });

    this.root.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-drop-filter]');
      if (chip) {
        this.dropFilter(chip.dataset.dropFilter, chip.dataset.dropExtra);
        return;
      }
      const pageLink = event.target.closest('.pagination a');
      if (pageLink) {
        event.preventDefault();
        this.fetchResults(pageLink.getAttribute('href').replace('?', ''));
      }
    });

    window.addEventListener('popstate', () => {
      window.location.reload();
    });
  }

  /**
   * Кнопка «Подбор» сворачивает панель фильтров целиком.
   * Выбор запоминается в браузере: если человек работает со свёрнутой
   * панелью, она не должна разворачиваться на каждой странице заново.
   */
  setupCollapse() {
    const toggle = this.root.querySelector('[data-filters-toggle]');
    if (!toggle) return;

    const apply = (collapsed) => {
      this.root.classList.toggle('is-filters-collapsed', collapsed);
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.title = collapsed ? KVITKA.i18n.expand : KVITKA.i18n.collapse;
    };

    // localStorage бывает недоступен: приватное окно, запрет на куки
    let collapsed = false;
    try {
      collapsed = window.localStorage.getItem(FILTERS_KEY) === '1';
    } catch (error) {
      collapsed = false;
    }
    apply(collapsed);

    toggle.addEventListener('click', () => {
      const next = !this.root.classList.contains('is-filters-collapsed');
      apply(next);
      try {
        window.localStorage.setItem(FILTERS_KEY, next ? '1' : '0');
      } catch (error) {
        /* не смогли запомнить - не страшно, панель просто не запомнит выбор */
      }
    });
  }

  /**
   * Раздел выбирается радиокнопкой, а её нельзя снять обычным кликом:
   * браузер так устроен. Поэтому запоминаем состояние до нажатия и,
   * если кликнули по уже выбранному разделу, снимаем выбор сами.
   */
  setupRadioReset() {
    let pending = null;

    this.form.addEventListener('pointerdown', (event) => {
      const label = event.target.closest('.check');
      const radio = label && label.querySelector('input[type="radio"]');
      pending = radio && radio.checked ? radio : null;
    });

    this.form.addEventListener('click', (event) => {
      const label = event.target.closest('.check');
      const radio = label && label.querySelector('input[type="radio"]');
      if (!radio || radio !== pending) return;
      // клик по label порождает второе такое же событие на самом input,
      // поэтому сразу забываем цель - иначе снимем выбор дважды
      pending = null;
      radio.checked = false;
      this.fetchResults();
    });
  }

  filterGroup(input) {
    const term = input.value.trim().toLowerCase();
    const group = input.closest('.facet');
    if (!group) return;
    group.querySelectorAll('[data-facet-name]').forEach((item) => {
      const match = !term || item.dataset.facetName.includes(term);
      item.classList.toggle('is-hidden', !match);
    });
  }

  buildQuery() {
    const data = new FormData(this.form);
    const params = new URLSearchParams();
    const multi = {};

    data.forEach((value, key) => {
      if (!String(value).trim()) return;
      if (MULTI_PARAMS.includes(key)) {
        multi[key] = multi[key] || [];
        multi[key].push(value);
      } else {
        params.set(key, value);
      }
    });
    Object.entries(multi).forEach(([key, values]) => params.set(key, values.join(',')));
    return params.toString();
  }

  dropFilter(param, extra) {
    // Раздел — не поле формы, он часть адреса. Снять его галочкой нельзя,
    // поэтому просто уходим на весь каталог, сохранив остальные фильтры.
    if (param === 'category') {
      const root = this.root.dataset.catalogUrl || '/';
      const query = this.buildQuery();
      window.location.href = query ? `${root}?${query}` : root;
      return;
    }
    const inputs = this.form.querySelectorAll(`[name="${param}"]`);
    inputs.forEach((input) => {
      if (input.type === 'checkbox' || input.type === 'radio') input.checked = false;
      else input.value = '';
    });
    if (extra) {
      this.form.querySelectorAll(`[name="${extra}"]`).forEach((input) => {
        input.value = '';
      });
    }
    this.fetchResults();
  }

  async fetchResults(rawQuery = null) {
    const query = rawQuery !== null ? rawQuery : this.buildQuery();
    const url = `${this.form.action}?${query}`;
    this.results.classList.add('is-loading');
    try {
      const data = await KVITKA.api.getFragment(url);
      this.results.innerHTML = data.html;
      if (this.counter) {
        this.counter.textContent =
          `${data.count} ${KVITKA.Plural.forms(data.count, KVITKA.i18n.models)}`;
      }
      // берём путь из формы, а не из адресной строки: если запросили
      // раздел, в адресе должен оказаться он же, иначе показанное
      // и написанное разъезжаются
      const path = new URL(this.form.action, window.location.origin).pathname;
      window.history.replaceState({}, '', query ? `${path}?${query}` : path);
    } catch (error) {
      console.error(error);
      this.form.submit();
    } finally {
      this.results.classList.remove('is-loading');
    }
  }
}


document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-catalog]');
  if (root) new CatalogPage(root).init();
  // Баннер новинок скрипта не требует: он статичный, всё в разметке.
});
