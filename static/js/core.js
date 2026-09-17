/* KVITKA — core.js
   Author: ISHOD · 2026 · all rights reserved. */
/**
 * Shared layer for every page: backend requests, money formatting and
 * the cart counter in the header.
 */

/**
 * Labels in the page language. Django translates templates only, so
 * strings for scripts are placed into <script type="application/json">
 * in base.html and simply read here. If the block is missing — Russian.
 */
const I18N = (() => {
  const fallback = {
    positions: 'позиция,позиции,позиций',
    models: 'букет,букета,букетов',
    pieces: 'шт',
    expand: 'Развернуть подбор',
    collapse: 'Свернуть подбор',
    emptyAnswer: 'Пустой ответ',
    requestFailed: 'Не удалось выполнить запрос',
    listFailed: 'Не удалось загрузить список',
    added: 'Добавлено',
    addToCart: 'В корзину',
    clear: 'Очистить',
    loginToSave: 'Войдите в кабинет, чтобы сохранять товары',
    inCart: 'в корзине',
    goToCart: 'Перейти в корзину',
    inFavorites: 'в избранном',
    fromFavorites: 'убрано из избранного',
    goToFavorites: 'Перейти в избранное',
  };
  const node = document.getElementById('kvitka-i18n');
  if (!node) return fallback;
  try {
    return Object.assign({}, fallback, JSON.parse(node.textContent));
  } catch (error) {
    return fallback;
  }
})();

class Api {
  constructor(csrfToken) {
    this.csrfToken = csrfToken;
  }

  async post(url, payload = {}) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken,
        'X-Requested-With': 'fetch',
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({ ok: false, error: I18N.emptyAnswer }));
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || I18N.requestFailed);
    }
    return data;
  }

  async getFragment(url) {
    const response = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
    if (!response.ok) {
      throw new Error(I18N.listFailed);
    }
    return response.json();
  }
}

class Money {
  static format(value) {
    const rounded = Math.round(Number(value) || 0);
    return `${rounded.toLocaleString('ru-RU').replace(/ /g, ' ')} ₴`;
  }
}

class Plural {
  /** Plural.forms(3, 'модель,модели,моделей') -> 'модели' */
  static forms(number, packed) {
    const parts = String(packed).split(',').map((part) => part.trim());
    while (parts.length < 3) parts.push(parts[parts.length - 1]);
    return Plural.of(number, parts[0], parts[1], parts[2]);
  }

  static of(number, one, few, many) {
    const n = Math.abs(Number(number) || 0);
    if (n % 10 === 1 && n % 100 !== 11) return one;
    if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return few;
    return many;
  }
}

class CartBadge {
  constructor(root) {
    this.root = root;
    this.positions = root ? root.querySelector('[data-cart-positions]') : null;
    this.amount = root ? root.querySelector('[data-cart-amount]') : null;
  }

  update(cart) {
    if (!cart || !this.root) return;
    if (this.positions) {
      this.positions.textContent =
        `${cart.positions} ${Plural.forms(cart.positions, I18N.positions)}`;
    }
    if (this.amount) {
      this.amount.textContent = cart.amount_label || Money.format(cart.amount);
    }
  }
}

/**
 * Sticky header.
 *
 * The catalog is long, and the cart and search are needed at any scroll
 * position — otherwise you scroll back up for them. So the header sticks
 * to the top of the window and, once the page is scrolled, shrinks by
 * itself: the tagline under the logo, the manager contacts and the
 * category row go away. A narrow bar remains — logo, search, account, cart.
 *
 * All the script does is toggle one class on <body>: what exactly hides
 * is decided by CSS. The listener is passive and fires only on a state
 * change, not on every scrolled pixel.
 */
class StickyHeader {
  constructor(threshold = 120) {
    this.threshold = threshold;
    this.scrolled = null;
  }

  init() {
    const apply = () => {
      const now = window.scrollY > this.threshold;
      if (now === this.scrolled) return;
      this.scrolled = now;
      document.body.classList.toggle('is-scrolled', now);
    };
    apply();
    window.addEventListener('scroll', apply, { passive: true });
  }
}

/**
 * Toast notifications for adding to the cart.
 *
 * The cart is filled right in the catalog without opening it: the person
 * presses the cart icon on a tile and stays put. Without feedback it is
 * unclear whether the product got into the cart — the header counter
 * changes too quietly, especially on a scrolled page.
 *
 * No more than three messages on screen: the fourth pushes out the oldest,
 * otherwise picking ten items would cover the products.
 */
class Toasts {
  constructor(cartUrl, favoritesUrl) {
    this.cartUrl = cartUrl;
    this.favoritesUrl = favoritesUrl;
    this.box = null;
    this.life = 6000;
    this.limit = 3;
  }

  container() {
    if (!this.box) {
      this.box = document.createElement('div');
      this.box.className = 'toasts';
      // aria-live: a screen reader announces the new text without moving focus
      this.box.setAttribute('aria-live', 'polite');
      document.body.appendChild(this.box);
    }
    return this.box;
  }

  /** show('text', {href, text}) — the link is optional. */
  show(text, link = null) {
    const box = this.container();
    const toast = document.createElement('div');
    toast.className = 'toast';

    const line = document.createElement('span');
    line.className = 'toast__text';
    line.textContent = text;
    toast.appendChild(line);

    if (link && link.href) {
      const anchor = document.createElement('a');
      anchor.className = 'toast__link';
      anchor.href = link.href;
      anchor.textContent = link.text;
      toast.appendChild(anchor);
    }

    box.appendChild(toast);
    while (box.children.length > this.limit) box.removeChild(box.firstElementChild);

    const hide = () => {
      toast.classList.add('is-leaving');
      setTimeout(() => toast.remove(), 250);
    };
    const timer = setTimeout(hide, this.life);
    // mouse over — do not hide: the person is reading or aiming at the link
    toast.addEventListener('mouseenter', () => clearTimeout(timer));
    toast.addEventListener('mouseleave', () => setTimeout(hide, 1200));
  }

  /** Common wording: "Name" — what happened to it. */
  about(name, what, link) {
    this.show(name ? `«${name}» — ${what}` : what, link);
  }

  added(name) {
    this.about(name, I18N.inCart,
               { href: this.cartUrl, text: I18N.goToCart });
  }

  favorited(name) {
    this.about(name, I18N.inFavorites,
               { href: this.favoritesUrl, text: I18N.goToFavorites });
  }

  /** Heart removed. No link needed: the person did not collect anything. */
  unfavorited(name) {
    this.about(name, I18N.fromFavorites, null);
  }
}

class ProductCards {
  /** Stepper and "add to cart" button right in the catalog tile.
   *
   * The tile holds a plain form (orders:form-add): without the script it
   * submits with a reload, here we intercept it and send fetch so the
   * person stays put.
   */

  constructor(addUrl) {
    this.addUrl = addUrl;
  }

  init() {
    document.addEventListener('click', (event) => {
      const card = event.target.closest('[data-product-card]');
      if (!card) return;
      const stepButton = event.target.closest('[data-step-button]');
      if (stepButton) {
        event.preventDefault();
        this.bump(card, Number(stepButton.dataset.stepButton));
      }
    });
    document.addEventListener('submit', (event) => {
      const form = event.target.closest('[data-product-card] [data-add-form]');
      if (!form || !this.addUrl) return;
      event.preventDefault();
      this.add(form.closest('[data-product-card]'), form);
    });
  }

  bump(card, direction) {
    const input = card.querySelector('[data-quantity]');
    if (!input) return;
    const next = (parseInt(input.value, 10) || 0) + direction;
    input.value = quantityForStepper(next, card.dataset);
  }

  async add(card, form) {
    // fields via form.elements, not by attribute: this way a field cannot
    // be confused with a same-named form property
    const input = form.elements['quantity'];
    const button = form.querySelector('[data-add-to-cart]');
    const quantity = normalizeQuantity(input ? input.value : 0, card.dataset);
    if (!quantity) return;
    if (input) input.value = quantity;

    if (button) button.disabled = true;
    try {
      const data = await KVITKA.api.post(this.addUrl, {
        product: form.elements['product'].value,
        quantity,
      });
      KVITKA.badge.update(data.cart);
      card.classList.add('is-added');
      setTimeout(() => card.classList.remove('is-added'), 1600);
      KVITKA.toasts.added(card.dataset.name || '');
    } catch (error) {
      console.error(error);
    } finally {
      if (button) button.disabled = false;
    }
  }
}

/**
 * Normalising the quantity to what can be ordered.
 *
 * Mirrors Product.normalize_quantity on the server: an integer, not below
 * zero, not above stock. The duplication is deliberate: the server checks
 * anyway, but the stepper must show the truth immediately without waiting
 * for a response.
 */
function normalizeQuantity(value, options = {}) {
  const max = parseInt(options.max, 10) || 0;
  if (max <= 0) return 0;
  const quantity = parseInt(value, 10) || 0;
  if (quantity <= 0) return 0;
  return Math.min(quantity, max);
}

/** The same, but an empty value is pulled up to the minimum:
 *  there is no point showing zero in a product stepper. */
function quantityForStepper(value, options) {
  return normalizeQuantity(value, options) || normalizeQuantity(1, options);
}

function debounce(fn, delay = 300) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Favourites. The heart on the product tile and on the product page.
 *
 * A guest has no account — the server refuses, and we simply send the
 * person to the login page, remembering where they wanted to return. The
 * button look changes at once, before the response: the click feels
 * instant, and if the server refuses — it is reverted.
 */
class Favorites {
  constructor(url, loginUrl) {
    this.url = url;
    this.loginUrl = loginUrl;
  }

  init() {
    if (!this.url) return;
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-favorite]');
      if (!button) return;
      event.preventDefault();
      this.toggle(button);
    });
  }

  async toggle(button) {
    const was = button.classList.contains('is-active');
    this.paint(button, !was);
    button.disabled = true;
    try {
      const data = await KVITKA.api.post(this.url, { product: button.dataset.favorite });
      this.paint(button, data.active);
      this.count(data.total);
      // the name sits on the product tile or on its page — both have
      // data-name, so the closest carrier is looked up
      const name = (button.closest('[data-name]') || {}).dataset;
      KVITKA.toasts[data.active ? 'favorited' : 'unfavorited'](
        (name && name.name) || '',
      );
    } catch (error) {
      this.paint(button, was);
      if (this.loginUrl) {
        window.location.href = `${this.loginUrl}?next=${encodeURIComponent(window.location.pathname)}`;
      }
    } finally {
      button.disabled = false;
    }
  }

  paint(button, active) {
    button.classList.toggle('is-active', Boolean(active));
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    // the product page and the catalog may show the same product
    document.querySelectorAll(`[data-favorite="${button.dataset.favorite}"]`)
      .forEach((twin) => {
        twin.classList.toggle('is-active', Boolean(active));
        twin.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
  }

  count(total) {
    document.querySelectorAll('[data-favorites-count]').forEach((node) => {
      node.textContent = total;
      node.hidden = !total;
    });
  }
}

const KVITKA = {
  api: new Api(document.body.dataset.csrf || ''),
  badge: new CartBadge(document.querySelector('[data-cart-badge]')),
  toasts: new Toasts(document.body.dataset.cartUrl || '',
                     document.body.dataset.favoritesUrl || ''),
  Money,
  Plural,
  debounce,
  quantity: normalizeQuantity,
  stepperQuantity: quantityForStepper,
  i18n: I18N,
};

window.KVITKA = KVITKA;

document.addEventListener('DOMContentLoaded', () => {
  new StickyHeader().init();
  new ProductCards(document.body.dataset.addUrl || '').init();
  new Favorites(
    document.body.dataset.favoriteUrl || '',
    document.body.dataset.loginUrl || '',
  ).init();
});
