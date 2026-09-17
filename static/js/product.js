/* KVITKA — product.js
   Author: ISHOD · 2026 · all rights reserved. */
/**
 * Product page: quantity, total calculation and adding to the cart.
 * The size switcher is plain links, no script needed.
 */

class QuantityBox {
  constructor(root) {
    this.root = root;
    this.input = root.querySelector('[data-quantity]');
    this.step = 1;
    this.min = 1;
    this.max = parseInt(root.dataset.max, 10) || 0;
  }

  get value() {
    return parseInt(this.input.value, 10) || 0;
  }

  set value(next) {
    this.input.value = this.clamp(next);
  }

  clamp(value) {
    if (this.max && value > this.max) value = this.max;
    if (value < this.min) value = Math.min(this.min, this.max || this.min);
    return Math.max(value, 0);
  }

  bump(direction) {
    this.value = this.value + direction * this.step;
  }

  reset() {
    this.value = this.min;
  }
}

class Gallery {
  /** Gallery: thumbnails, arrows and the left/right keys. */

  constructor(root) {
    this.main = root.querySelector('[data-gallery-main]');
    this.thumbs = Array.from(root.querySelectorAll('[data-thumb]'));
    this.prev = root.querySelector('[data-gallery-prev]');
    this.next = root.querySelector('[data-gallery-next]');
    this.counter = root.querySelector('[data-gallery-counter]');
    this.index = 0;
  }

  init() {
    if (!this.main || this.thumbs.length === 0) return;

    this.thumbs.forEach((thumb, index) => {
      thumb.addEventListener('click', () => this.show(index));
    });
    if (this.prev) this.prev.addEventListener('click', () => this.move(-1));
    if (this.next) this.next.addEventListener('click', () => this.move(1));

    // one photo — no arrows needed
    if (this.thumbs.length < 2) {
      [this.prev, this.next].forEach((node) => node && node.remove());
    }

    document.addEventListener('keydown', (event) => {
      // while the full-screen viewer is open, the arrow keys belong to it
      if (document.documentElement.classList.contains('is-lightbox')) return;
      if (event.key === 'ArrowLeft') this.move(-1);
      if (event.key === 'ArrowRight') this.move(1);
    });

    this.show(0);
  }

  move(direction) {
    if (this.thumbs.length < 2) return;
    // wraps around: forward from the last lands on the first
    const count = this.thumbs.length;
    this.show((this.index + direction + count) % count);
  }

  show(index) {
    const thumb = this.thumbs[index];
    if (!thumb) return;
    this.index = index;
    this.main.src = thumb.dataset.thumb;
    this.thumbs.forEach((node, i) => node.classList.toggle('is-active', i === index));
    if (this.counter) {
      this.counter.textContent = `${index + 1} / ${this.thumbs.length}`;
    }
  }
}

class Lightbox {
  /**
   * Full-screen photo viewer with zoom.
   *
   * Zoom is done via transform: scale and a transform-origin that follows
   * the cursor. The reference point comes from the UNscaled image size:
   * once scale is applied, getBoundingClientRect returns the stretched
   * box, and computing percentages from it means chasing your own tail.
   */

  static MAX_SCALE = 4;
  static CLICK_SCALE = 2.5;

  constructor(root, gallery) {
    this.gallery = gallery;
    this.node = root.querySelector('[data-lightbox]');
    if (!this.node) return;

    this.stage = this.node.querySelector('[data-lightbox-stage]');
    this.image = this.node.querySelector('[data-lightbox-image]');
    this.hint = this.node.querySelector('[data-lightbox-hint]');
    this.counter = this.node.querySelector('[data-lightbox-counter]');
    this.thumbs = Array.from(this.node.querySelectorAll('[data-lightbox-thumb]'));
    this.sources = this.thumbs.map((node) => node.dataset.lightboxThumb);

    this.index = 0;
    this.scale = 1;
    this.baseRect = null;
    this.opener = null;
  }

  init() {
    if (!this.node || this.sources.length === 0) return;

    this.node.querySelectorAll('[data-lightbox-close]').forEach((node) =>
      node.addEventListener('click', () => this.close()));

    const prev = this.node.querySelector('[data-lightbox-prev]');
    const next = this.node.querySelector('[data-lightbox-next]');
    if (prev) prev.addEventListener('click', (e) => { e.stopPropagation(); this.move(-1); });
    if (next) next.addEventListener('click', (e) => { e.stopPropagation(); this.move(1); });

    this.thumbs.forEach((thumb, index) =>
      thumb.addEventListener('click', (e) => { e.stopPropagation(); this.show(index); }));

    // a click outside the photo closes, on the photo — zooms
    this.stage.addEventListener('click', (event) => {
      if (event.target === this.image) this.toggleZoom(event);
      else this.close();
    });
    this.stage.addEventListener('mousemove', (event) => this.track(event));
    this.stage.addEventListener('mouseleave', () => this.zoomOut());
    this.stage.addEventListener('touchmove', (event) => {
      if (!this.zoomed) return;
      event.preventDefault();
      this.track(event.touches[0]);
    }, { passive: false });
    this.stage.addEventListener('wheel', (event) => {
      event.preventDefault();
      this.setScale(this.scale - event.deltaY * 0.0025, event);
    }, { passive: false });

    document.addEventListener('keydown', (event) => {
      if (!this.isOpen) return;
      if (event.key === 'Escape') this.close();
      if (event.key === 'ArrowLeft') this.move(-1);
      if (event.key === 'ArrowRight') this.move(1);
    });
    window.addEventListener('resize', () => this.zoomOut());

    document.querySelectorAll('[data-lightbox-open]').forEach((node) =>
      node.addEventListener('click', () => this.open(this.gallery ? this.gallery.index : 0)));

    const main = document.querySelector('[data-gallery-main]');
    if (main) main.addEventListener('click', () => this.open(this.gallery ? this.gallery.index : 0));
  }

  get isOpen() {
    return this.node && !this.node.hidden;
  }

  open(index) {
    this.opener = document.activeElement;
    this.node.hidden = false;
    document.documentElement.classList.add('is-lightbox');
    this.show(index || 0);
    const close = this.node.querySelector('[data-lightbox-close]');
    if (close) close.focus();
  }

  close() {
    this.zoomOut();
    this.node.hidden = true;
    document.documentElement.classList.remove('is-lightbox');
    if (this.opener && this.opener.focus) this.opener.focus();
  }

  move(direction) {
    const count = this.sources.length;
    if (count < 2) return;
    this.show((this.index + direction + count) % count);
  }

  show(index) {
    const source = this.sources[index];
    if (!source) return;
    this.index = index;
    this.zoomOut();
    this.image.src = source;
    this.thumbs.forEach((node, i) => node.classList.toggle('is-active', i === index));
    if (this.counter) {
      this.counter.textContent = this.sources.length > 1
        ? `${index + 1} / ${this.sources.length}` : '';
    }
    // keep the small gallery on the page on the same frame
    if (this.gallery) this.gallery.show(index);
  }

  toggleZoom(event) {
    if (this.zoomed) this.zoomOut();
    else this.setScale(Lightbox.CLICK_SCALE, event);
  }

  setScale(value, event) {
    const scale = Math.min(Lightbox.MAX_SCALE, Math.max(1, value));
    if (scale <= 1.001) { this.zoomOut(); return; }
    if (!this.zoomed) {
      // remember the box before the first scale, while it is still honest
      this.baseRect = this.image.getBoundingClientRect();
      this.zoomed = true;
      this.stage.classList.add('is-zoomed');
    }
    this.scale = scale;
    if (event) this.track(event);
    this.image.style.transform = `scale(${scale})`;
  }

  zoomOut() {
    if (!this.zoomed) return;
    this.zoomed = false;
    this.scale = 1;
    this.baseRect = null;
    this.stage.classList.remove('is-zoomed');
    this.image.style.transform = '';
    this.image.style.transformOrigin = '';
  }

  track(event) {
    if (!this.zoomed || !this.baseRect || !event) return;
    const rect = this.baseRect;
    const clamp = (v) => Math.max(0, Math.min(100, v));
    const x = clamp(((event.clientX - rect.left) / rect.width) * 100);
    const y = clamp(((event.clientY - rect.top) / rect.height) * 100);
    this.image.style.transformOrigin = `${x}% ${y}%`;
  }
}

class ProductPage {
  constructor(root) {
    this.root = root;
    this.productId = root.dataset.product;
    this.price = parseFloat(root.dataset.price) || 0;
    this.addUrl = root.dataset.addUrl;
    this.stock = parseInt(root.dataset.max, 10) || 0;

    this.totalNode = root.querySelector('[data-order-total]');
    this.form = root.querySelector('[data-add-form]');
    this.addButton = root.querySelector('[data-add-to-cart]');
    this.box = this.form ? new QuantityBox(root) : null;
  }

  init() {
    const gallery = new Gallery(this.root);
    gallery.init();
    new Lightbox(this.root, gallery).init();
    if (!this.box) return;

    this.root.addEventListener('click', (event) => {
      const stepButton = event.target.closest('[data-step-button]');
      if (stepButton && stepButton.closest('.order-box')) {
        this.box.bump(Number(stepButton.dataset.stepButton));
        this.render();
      }
    });
    // the plain form submits to the server with a reload; with JavaScript
    // we intercept it and stay on the page
    this.form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.addToCart();
    });

    this.root.addEventListener('input', (event) => {
      if (event.target.matches('[data-quantity]')) this.render();
    });
    this.root.addEventListener('change', (event) => {
      if (event.target.matches('[data-quantity]')) {
        this.box.value = this.box.value;
        this.render();
      }
    });

    this.render();
  }

  render() {
    const quantity = this.box.value;
    if (this.totalNode) {
      this.totalNode.textContent = KVITKA.Money.format(quantity * this.price);
    }
    if (this.addButton) this.addButton.disabled = quantity <= 0;
  }

  async addToCart() {
    const quantity = this.box.value;
    if (quantity <= 0) return;
    this.addButton.disabled = true;
    try {
      const data = await KVITKA.api.post(this.addUrl, {
        product: this.productId,
        quantity,
      });
      KVITKA.badge.update(data.cart);
      KVITKA.toasts.added(this.root.dataset.name || '');
      this.addButton.textContent = `${KVITKA.i18n.added} ✓`;
      setTimeout(() => {
        this.addButton.textContent = KVITKA.i18n.addToCart;
        this.addButton.disabled = false;
      }, 2000);
    } catch (error) {
      console.error(error);
      this.addButton.disabled = false;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-product-page]');
  if (root) new ProductPage(root).init();
});
