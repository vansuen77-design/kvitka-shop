# KVITKA — project notes

Flower shop with delivery, built in September 2026 on the author's Django shop
template (the same code base powers a wholesale lingerie catalog and a pet-food
retail shop). This document records the product decisions, what was adapted
from the template and how the project is verified. The main entry point for
developers is `README.md`.

## Product decisions

| # | Question | Decision | Where in the code |
|---|---|---|---|
| 1 | How products are sold | by the piece (retail) | `Product.normalize_quantity` — integer, 0 = remove, never above stock; `test_normalize` |
| 2 | Product variants | yes — bouquet size (11 / 25 / 51 roses) | `Product.family`, `variants()`, `variant_label`; switcher in `product_detail.html`; `test_variants` |
| 3 | Order entity | order with delivery | `orders/models.Order`: courier / pickup, address, date, time slot, recipient, gift card, payment on delivery or by transfer |
| 4 | Filter facets | type · flowers (M2M) · occasion (M2M) · colour · size; on the tile — flowers, occasion, size | `catalog/facets.py` (`in_tile`), `managers.RELATED/PREFETCH`, `admin.py` |
| 5 | Price per unit | no | — |
| 6 | Free delivery | from 1 500 ₴, courier 150 ₴, pickup 0 | `SHOP["FREE_DELIVERY_FROM"]`, `SHOP["DELIVERY_COST"]`, `Order.delivery_cost_for`, progress bar in the cart |
| 7 | Per-order limit | no | — |
| 8 | Name, city, contacts | demo: "KVITKA", Odesa, placeholder phone, domain `kvitka.example` | `settings.SHOP`, `.env.example`, `seed_pages` |
| 9 | Repeat order | no | — |

## What is shared with the template

`core/` (models, middleware, admin gate, IP access, sitemaps, robots, template tags),
`accounts/` (login by e-mail, favourites, password reset), `pages/` (footer pages),
`catalog/filters.py` (filters and sorting), `catalog/deletion.py` + `signals.py`
(unpublishing on delete), `catalog/exports.py` (XLSX / YML without extra libraries),
`orders/notify.py` (Telegram in the background), the bot, `adopt_content`,
`compilelocales`, deployment files, owner scripts and the CSS / JS skeleton.

## What was adapted for flowers

- **Reference data**: 13 lingerie attributes replaced with 5 flower ones (`Kind`,
  `Flower`, `Occasion`, `Color`, `Size`). Composition, stem count and height are
  text and numbers, not facets.
- **Product**: packaging, minimum lot, weight and size range removed; `family`,
  `stems`, `height_cm`, `composition(_uk)`, `summary_uk` added.
- **Request → order**: `orders/draft.py` → `orders/cart.py` (`Cart`, `CartTotals`
  with the free-delivery threshold), `Request` → `Order` with delivery fields,
  `OrderLine` copies article / name / price at the moment of the order.
  "Add by list" (a wholesale feature) removed. URLs `/zakaz/` → `/korzina/`.
- **No JavaScript**: product tiles and the product page are plain forms posting to
  `orders:form-add`; cart lines are forms posting to `orders:form-update`
  ("Update" / "Remove" buttons); JS only intercepts them.
- **Filter panel**: the catalog is heterogeneous, so empty values are hidden
  (except selected ones) and empty groups are not shown.
- **Search**: case-insensitive for Cyrillic (case variants + `name_uk`, composition,
  flowers) — SQLite's `LIKE` is case-insensitive for ASCII only.
- **Sorting**: "popular first" (by `position`) added as the default.
- **Two languages**: the `makelocales` command (`core/i18n_tools.py`) collects
  strings from templates and code without the gettext binaries, `--check` verifies
  completeness; labels stored in the database (`FacetGroup.name_uk`) are taken
  from the `.po` file by `seed_facets`. Strings in form dictionaries and `choices`
  are marked with `gettext_noop`.
- **Demo catalog**: 15 bouquets with placeholder images drawn by Pillow
  (`catalog/placeholders.py`); every name and reference value in both languages.
- **Account**: profile holds phone and delivery address instead of company and city;
  they are pre-filled into the order form.
- **Admin**: orders with a delivery block, dashboard `kvitka_stats` / `recent_orders`;
  titles come from `SHOP["NAME"]`.
- **Bot**: order commands plus `/segodnya` — today's deliveries; stock without packaging.
- **Scripts**: `start.bat` only checks migrations (never creates them) and runs
  `seed_facets`; `tools\run-checks.bat` and `tools\seed-demo.bat` added.
- **Palette and mark**: crimson accent, a flower instead of the letter "A"
  (`static/img/*`, og-image).

## Fixes made against the template

1. `accounts/admin.py` overrode `SingleAdminUserAdmin` from `core/admin.py`: the
   `accounts` app registers later and replaced the "last administrator cannot be
   deleted" guard with a plain `UserAdmin`. Here `UserAdmin` inherits from
   `SingleAdminUserAdmin`.
2. The JSON catalog response lacked `Cache-Control: no-store` and
   `Vary: X-Requested-With` without `NoCacheMiddleware` (i.e. in production).
   `AjaxTemplateMixin` now sets them.
3. `TIME_ZONE = "Europe/Kiev"` → `"Europe/Kyiv"`.
4. The local-copy script used to create migrations itself — now it only checks.
5. Russian strings without `{% trans %}` in breadcrumbs ("Catalog") — wrapped.
6. The password-reset e-mail hard-coded the shop name — now passed via `extra_email_context`.
7. `seed_pages` lacked `politika-konfidentsialnosti`, which the order form links to — added.

## Alignment with the retail reference shop

The structure matched (same `orders/cart.py`, `core/i18n_tools.py`,
`placeholders.py`, `/korzina/` URLs). Ported what was missing:

- `Order.language` (migration `orders.0002`) and the **"order accepted" e-mail to the
  customer** in the language they used (`templates/orders/email_*.txt`,
  `notify._email_customer`); sent in the background together with Telegram. While
  `EMAIL_HOST` in `.env` is empty it is printed to the log.
- `orders/services.py::create_order` — checkout moved out of the view; lines are
  written with one `bulk_create` inside a transaction.
- `snapshot_db` command (VACUUM INTO) — called by `deploy-to-server.bat` instead of
  a one-liner.
- Tests: smoke (`test_smoke`), admin pages (`test_admin_pages`), `adopt_content`
  guards, `snapshot_db`, order language, customer e-mail.
- Found by the smoke test along the way: a non-existent category
  `/katalog/net-takogo/` returned the whole catalog with 200 — now 404.

Deliberately not ported: `catalog/context_processors.menu` (the menu here is built by
`core.navigation`), `accounts/signals.py` (the profile is created on first visit to
the account), the "discount on the whole catalog" script (the `set_discount` command
exists; the script is optional).

## Tests

181 tests (`manage.py test`): quantity normalisation, discount, sorting (including the
NULL trap), filters (every facet by URL, `a,b` = `a&b`), Cyrillic search, banner,
filter panel, variants, unpublishing, exports, bilingual UI and labels from `.po`,
cart and delivery threshold from `settings`, checkout (line copying, delivery cost,
address required, someone else's "thank you" page → 404, order language), no-JS
forms, API, notifications and the customer e-mail, admin gate (hash, expiry,
5 attempts, pause), IP access decision table, middleware order, `makelocales`,
account (someone else's order → 404, `next`), pages, seed commands on an empty
database, smoke, admin pages, `adopt_content` guards, `snapshot_db`.

## What the owner fills in

- Replace demo data: `SHOP` in `config/settings.py` (name, phone, address, hours,
  messengers), `.env` from `.env.example` (domain, e-mail, Telegram), page texts in
  the admin, placeholder images — with real photos.
- Check the amounts in the "Delivery and payment" page texts — they duplicate
  `SHOP` at build time.
- Server: `deploy/INSTALL.md` (user `kvitka`, units `kvitka*.service`), the
  Cloudflare tunnel id in `deploy/cloudflared.yml`.
- First run: `start.bat`, then `tools\seed-demo.bat` (if the database is empty)
  and `tools\run-checks.bat`.

## Pre-delivery checklist (16–17 Sep 2026)

| Check | Result |
|---|---|
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | No changes detected |
| `makelocales --check` | all 278 strings translated |
| `manage.py test` | 181 OK |
| `node --check` for every js file | ok |
| clean database: migrate → seed_facets → seed_pages → seed_catalog | ok, 15 products, 6 pages |
| leftovers of the template name | one intentional mention in a comment in `accounts/admin.py` |
| screenshots 1360 / 430, UK and RU: catalog, category with sorting, product with variants, cart | reviewed, no overflow |
