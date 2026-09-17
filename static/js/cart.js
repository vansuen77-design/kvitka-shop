/* KVITKA — cart.js
   Author: ISHOD · 2026 · all rights reserved. */
/**
 * Cart page: quantities, removing lines, clearing and the delivery
 * fields of the order form.
 *
 * The page never reloads: together with the totals the server returns
 * the ready table markup, and we swap it in place. A reload used to be a
 * source of confusion here — it cut off the next request, and a line was
 * added "every other time".
 *
 * Without JavaScript the plain forms in the table rows do the same
 * (orders:form-update) — here we only intercept them.
 */

class CartPage {
  constructor(root) {
    this.root = root;
    this.updateUrl = root.dataset.updateUrl;
    this.removeUrl = root.dataset.removeUrl;
    this.clearUrl = root.dataset.clearUrl;
    this.table = root.querySelector('[data-cart-table]');
    this.clearSlot = root.querySelector('[data-cart-clear-slot]');
    this.orderForm = root.querySelector('form.contact');
    this.busy = false;
    this.cart = null;
    this.sendQuantity = KVITKA.debounce((line) => this.updateLine(line), 400);
  }

  init() {
    this.root.addEventListener('click', (event) => {
      const stepButton = event.target.closest('[data-step-button]');
      if (stepButton && stepButton.closest('[data-line]')) {
        event.preventDefault();
        this.bump(stepButton.closest('[data-line]'), Number(stepButton.dataset.stepButton));
        return;
      }
      if (event.target.closest('[data-cart-clear]')) {
        this.clear();
      }
    });

    // the line form: "Remove" is the cross with name=remove, otherwise update
    this.root.addEventListener('submit', (event) => {
      const line = event.target.closest('[data-line]');
      if (!line) return;
      event.preventDefault();
      const remove = event.submitter && event.submitter.name === 'remove';
      if (remove) this.removeLine(line);
      else this.updateLine(line);
    });

    this.root.addEventListener('change', (event) => {
      const line = event.target.closest('[data-line]');
      if (line && event.target.matches('[data-quantity]')) {
        this.sendQuantity(line);
      }
    });

    this.setupDelivery();
  }

  /**
   * Delivery fields. For pickup the address is not needed — hidden, and
   * the totals say "pickup". The free-delivery threshold and rate are
   * computed by the server (CartTotals), here only the labels are redrawn.
   */
  setupDelivery() {
    if (!this.orderForm) return;
    const radios = this.orderForm.elements['delivery'];
    if (!radios) return;
    const apply = () => this.renderDelivery();
    Array.from(radios.length ? radios : [radios]).forEach((radio) =>
      radio.addEventListener('change', apply));
    apply();
  }

  deliveryMethod() {
    const field = this.orderForm && this.orderForm.elements['delivery'];
    if (!field) return 'courier';
    return field.value || 'courier';
  }

  renderDelivery() {
    const pickup = this.deliveryMethod() === 'pickup';
    const courierFields = this.root.querySelector('[data-courier-fields]');
    if (courierFields) courierFields.hidden = pickup;
    const delivery = this.root.querySelector('[data-totals-delivery]');
    if (delivery) {
      if (pickup) {
        delivery.textContent = delivery.dataset.pickup;
      } else if (this.cart) {
        delivery.textContent = this.cart.free_delivery_reached
          ? delivery.dataset.free : this.cart.courier_cost_label;
      }
      // the cart has not changed yet — keep what the server rendered
    }
    const progress = this.root.querySelector('[data-progress]');
    if (progress) progress.hidden = pickup;
  }

  bump(line, direction) {
    const input = line.elements['quantity'];
    if (!input) return;
    const next = (parseInt(input.value, 10) || 0) + direction;
    input.value = Math.max(0, Math.min(next, parseInt(line.dataset.max, 10) || 0));
    this.sendQuantity(line);
  }

  async updateLine(line) {
    if (!line || this.busy) return;
    const quantity = parseInt(line.elements['quantity'].value, 10) || 0;
    this.busy = true;
    try {
      const data = await KVITKA.api.post(this.updateUrl, {
        product: line.dataset.product, quantity,
      });
      this.applyResult(data);
    } catch (error) {
      console.error(error);
    } finally {
      this.busy = false;
    }
  }

  async removeLine(line) {
    if (!line || this.busy) return;
    this.busy = true;
    try {
      const data = await KVITKA.api.post(this.removeUrl, { product: line.dataset.product });
      this.applyResult(data);
    } catch (error) {
      console.error(error);
    } finally {
      this.busy = false;
    }
  }

  async clear() {
    if (this.busy) return;
    this.busy = true;
    try {
      const data = await KVITKA.api.post(this.clearUrl, {});
      this.applyResult(data);
    } catch (error) {
      console.error(error);
    } finally {
      this.busy = false;
    }
  }

  /** Replaces the lines table and totals with what the server returned. */
  applyResult(data) {
    if (!data) return;
    if (this.table && typeof data.html === 'string') {
      this.table.innerHTML = data.html;
    }
    if (this.clearSlot) {
      const positions = data.cart ? data.cart.positions : 0;
      const has = this.clearSlot.querySelector('[data-cart-clear]');
      if (positions && !has) {
        this.clearSlot.innerHTML =
          `<button type="button" class="button button--ghost" data-cart-clear>${KVITKA.i18n.clear}</button>`;
      } else if (!positions && has) {
        this.clearSlot.innerHTML = '';
      }
    }
    this.applyTotals(data.cart);
  }

  applyTotals(cart) {
    if (!cart) return;
    this.cart = cart;
    KVITKA.badge.update(cart);
    const amount = this.root.querySelector('[data-totals-amount]');
    if (amount) amount.textContent = cart.amount_label;
    const count = this.root.querySelector('[data-totals-count]');
    if (count) {
      count.textContent =
        `${cart.positions} ${KVITKA.Plural.forms(cart.positions, KVITKA.i18n.positions)}, ${cart.quantity} ${KVITKA.i18n.pieces}`;
    }
    const bar = this.root.querySelector('[data-progress-bar]');
    if (bar) bar.style.width = `${cart.free_delivery_progress}%`;
    const note = this.root.querySelector('[data-progress-note]');
    if (note) {
      note.textContent = cart.free_delivery_reached
        ? note.dataset.reached
        : `${note.dataset.gap} ${cart.free_delivery_gap_label}.`;
    }
    this.renderDelivery();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-cart-page]');
  if (root) new CartPage(root).init();
});
