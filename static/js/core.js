/* KVITKA — core.js
   Author: ISHOD · 2026 · all rights reserved. */
/**
 * Общий слой для всех страниц: запросы к бэкенду, форматирование денег
 * и счётчик корзины в шапке.
 */

/**
 * Подписи на языке страницы. Django переводит только шаблоны, поэтому
 * строки для скриптов кладутся в <script type="application/json"> в base.html,
 * а здесь просто читаются. Если блока нет — работаем на русском.
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
 * Липкая шапка.
 *
 * Каталог длинный, а корзина и поиск нужны на любой высоте страницы —
 * иначе за ними приходится мотать наверх. Поэтому шапка прилипает
 * к верху окна, а когда страница прокручена, сама ужимается: уходят
 * подпись под логотипом, контакты менеджера и строка разделов.
 * Остаётся узкая полоса — логотип, поиск, кабинет, заявка.
 *
 * Вся работа скрипта — один класс на <body>: что именно прячется,
 * решает CSS. Слушатель пассивный и срабатывает только на смене
 * состояния, а не на каждом пикселе прокрутки.
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
 * Всплывающие уведомления о добавлении в корзину.
 *
 * Корзина собирается прямо в каталоге, не открывая её: человек жмёт
 * корзинку на карточке и остаётся на месте. Без ответа непонятно,
 * попал товар в корзину или нет — счётчик в шапке меняется слишком
 * тихо, особенно на прокрученной странице.
 *
 * Больше трёх сообщений на экране не держим: четвёртое вытесняет
 * самое старое, иначе при наборе десяти позиций они закрывают товары.
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
      // aria-live: читалка произносит появившийся текст, не уводя фокус
      this.box.setAttribute('aria-live', 'polite');
      document.body.appendChild(this.box);
    }
    return this.box;
  }

  /** show('текст', {href, text}) — ссылка необязательна. */
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
    // навели мышь — не убираем: человек читает или целится в ссылку
    toast.addEventListener('mouseenter', () => clearTimeout(timer));
    toast.addEventListener('mouseleave', () => setTimeout(hide, 1200));
  }

  /** Общая формулировка: «Название» — что с ним стало. */
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

  /** Сердечко сняли. Ссылка тут не нужна: человек ничего не набирал. */
  unfavorited(name) {
    this.about(name, I18N.fromFavorites, null);
  }
}

class ProductCards {
  /** Счётчик и кнопка «в корзину» прямо в плитке каталога.
   *
   * В плитке лежит обычная форма (orders:form-add): без скрипта она
   * отправляется с перезагрузкой, здесь мы её перехватываем и шлём
   * fetch, чтобы человек остался на месте.
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
    // поля — через form.elements, а не по атрибутам: так поле нельзя
    // спутать с одноимённым свойством формы (грабля 17)
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
 * Приведение количества к тому, что можно заказать.
 *
 * Повторяет Product.normalize_quantity с сервера: целое, не меньше
 * нуля, не больше остатка. Дублирование намеренное: сервер всё равно
 * проверит, а счётчик должен показывать правду сразу, не дожидаясь
 * ответа.
 */
function normalizeQuantity(value, options = {}) {
  const max = parseInt(options.max, 10) || 0;
  if (max <= 0) return 0;
  const quantity = parseInt(value, 10) || 0;
  if (quantity <= 0) return 0;
  return Math.min(quantity, max);
}

/** То же самое, но пустое значение подтягивается к минимуму:
 *  в счётчике товара ноль показывать незачем. */
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
 * Избранное. Сердечко на карточке товара и на его странице.
 *
 * Гостю кабинета нет — сервер ответит отказом, и мы просто уводим
 * человека на вход, запомнив, куда он хотел вернуться. Внешний вид
 * кнопки меняем сразу, до ответа: так нажатие ощущается мгновенным,
 * а если сервер откажет — возвращаем как было.
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
      // название лежит на карточке товара или на его странице —
      // у обеих есть data-name, поэтому ищем ближайшего носителя
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
    // на странице товара и в каталоге может быть одна и та же карточка
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
