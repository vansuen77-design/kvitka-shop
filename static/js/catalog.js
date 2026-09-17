/* KVITKA — catalog.js
   Author: ISHOD · 2026 · all rights reserved. */
const FILTERS_KEY = 'kvitka:filters-collapsed';

// parameters that may carry several values: the keys from
// catalog/facets.py plus status and availability
const MULTI_PARAMS = ['type', 'flower', 'occasion', 'color', 'size',
  'status', 'stock'];

/**
 * Catalog: filters apply without a page reload.
 * The form stays functional without JavaScript — here we only intercept
 * changes and swap the product grid.
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
      // the select is tied to the form via form="catalog-filters", so
      // FormData already sees it — refetching the list is enough
      this.sortSelect.addEventListener('change', () => this.fetchResults());
    }

    this.root.querySelectorAll('[data-facet-search]').forEach((input) => {
      input.addEventListener('input', () => this.filterGroup(input));
      // search inside a group must not submit the form
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
   * The "Filters" button collapses the whole filter panel.
   * The choice is remembered in the browser: if the person works with a
   * collapsed panel, it must not expand again on every page.
   */
  setupCollapse() {
    const toggle = this.root.querySelector('[data-filters-toggle]');
    if (!toggle) return;

    const apply = (collapsed) => {
      this.root.classList.toggle('is-filters-collapsed', collapsed);
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.title = collapsed ? KVITKA.i18n.expand : KVITKA.i18n.collapse;
    };

    // localStorage may be unavailable: private window, cookies blocked
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
        /* could not remember — no harm, the panel just forgets the choice */
      }
    });
  }

  /**
   * The category is picked with a radio button, and a radio cannot be
   * unchecked by a plain click: that is how browsers work. So the state
   * before the click is remembered, and a click on the already selected
   * category unchecks it ourselves.
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
      // a click on the label produces a second identical event on the
      // input itself, so the target is forgotten at once — otherwise the
      // selection would be cleared twice
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
    // The category is not a form field, it is part of the URL. It cannot
    // be unchecked, so we simply go to the whole catalog keeping the other filters.
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
      // the path comes from the form, not from the address bar: if a
      // category was requested, the URL must show that category, otherwise
      // what is shown and what is written diverge
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
  // The new-arrivals banner needs no script: it is static markup.
});
