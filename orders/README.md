# orders — developer README

This file documents the `orders` Django app. It combines the app-level reference and developer notes into a single, readable guide for maintainers and contributors.

Contents
- Overview
- Features implemented
- Models & key fields
- API endpoints (contract)
- Payments, idempotency & webhooks
- Inventory integration (gallery)
- Middleware
- Admin & refunds
- Local development & testing
- Tests
- Unfinished components / next steps (actionable)
- Appendix: shell snippets and examples

---

## Overview

The `orders` app provides a compact order management system that supports:

- Creating orders (guest & authenticated)
- Line-item snapshotting so orders don't break if product records change
- Starting payments (Stripe example) and storing provider client secrets
- Provider webhook processing with deduplication and idempotent handling
- Basic admin tools for shipping/refunds and audit-friendly payment records

The implementation focuses on clarity, idempotency, and safe inventory handling for an MVP.

## Features implemented (MVP)

- Order creation with server-side total calculation and transactional saves.
- `start-payment` flow that creates a `PaymentRecord` and supports an `Idempotency-Key` to deduplicate client calls.
- Webhook endpoint that verifies provider events (helper), deduplicates by provider event id (`ProcessedEvent`) and updates `Order`/`PaymentRecord`.
- Inventory integration with `gallery.StockItem`:
  - Multi-qty SKUs use the `stock` integer and are decremented on successful payment.
  - One-of-a-kind items are marked with `is_unique=True` and use `status` transitions (`available -> reserved -> sold`).
- Snapshotting: `OrderItem.product_status` records the product's availability status at the time of ordering.
- Admin actions: `mark_shipped` and `mark_refunded`; `PaymentRecord.issue_refund()` helper with idempotency.
- Confirmation email sent on payment success (MVP: synchronous; consider moving to background worker).
- Tests covering the core behaviors (orders, payments, webhook dedupe, stock handling, admin actions).

## Models & key fields (summary)

See `orders/models.py` for full details. Key models/fields at a glance:

- Order: `order_number`, `user`, `guest_email`, `status`, `total`, `currency`, `stock_shortage`.
- OrderItem: `product_title`, `product_sku`, `unit_price`, `quantity`, `product_status` (snapshot).
- Address: shipping/billing address linked to `Order`.
- PaymentRecord: `provider`, `provider_payment_id`, `provider_client_secret`, `idempotency_key`, `amount`, `status`, `raw_response`, `provider_refund_id`, `refunded_at`.
- Reservation: optional user-bound reservation rows (used for authenticated checkout flows).
- ProcessedEvent: provider + event_id for webhook deduplication.

Inventory piece (in `gallery` app): `StockItem` with `sku`, `stock` (int), `status` (available/reserved/sold/archived) and `is_unique` boolean.

Where the code lives

- Serializers: `orders/serializers.py` (OrderCreateSerializer) — calculates totals, reserves unique items and snapshots `product_status`.
- Views / API: `orders/views.py` — Order creation, start-payment and refund endpoints.
- Webhook verification and handler: `orders/webhooks.py` (`stripe_webhook`) and `orders/payments.py` (helpers such as `verify_stripe_event`).
- Models: `orders/models.py` and inventory in `gallery/models.py`.

If you're stepping through the flow, start with `orders/serializers.py` -> `orders/views.py` -> `orders/webhooks.py`.

## API endpoints (contract)

1) POST /orders/create/
- Create an order (guest or authenticated). Request body must be JSON.
- Required: `items` array (each item: product_title, product_sku, unit_price, quantity).
- Responses: 201 created with serialized order; 400 validation errors; 415 non-JSON content (friendly JSON from middleware).

2) POST /orders/start-payment/<order_id>/
- Creates a `PaymentRecord` and (optionally) a provider-side payment intent.
- Supports `Idempotency-Key` header; returns `client_secret` when applicable.

Example request (client-side call):

```http
POST /orders/start-payment/42/ HTTP/1.1
Host: localhost:8000
Idempotency-Key: startpay-42
Content-Type: application/json

{}
```

Example response (successful, Stripe-style mocked response):

```json
{
	"payment_id": 7,
	"client_secret": "pi_abc_secret_123",
	"provider": "stripe"
}
```

3) POST /orders/webhook/
- Provider webhook endpoint (Stripe example). Verifies event, dedupes, updates PaymentRecord and Order.

Example minimal webhook payload (Stripe-like) for local testing or unit tests:

```json
{
	"id": "evt_1Example",
	"type": "payment_intent.succeeded",
	"data": {
		"object": {
			"id": "pi_1Example",
			"metadata": { "order_id": "42" }
		}
	}
}
```

4) POST /orders/refund/<payment_id>/
- Staff-only endpoint to trigger idempotent refunds via `PaymentRecord.issue_refund()`.

5) (Optional) GET /orders/schema/ — small DRF/OpenAPI schema endpoint used in dev.

## Payments, idempotency & webhooks

- Start-payment idempotency: when the client provides `Idempotency-Key`, the start-payment view returns the existing `PaymentRecord` for the same order + key to avoid duplicate provider intents.
- Webhook dedupe: `ProcessedEvent` records provider event ids to skip duplicate deliveries.
- Refund idempotency: `PaymentRecord.issue_refund()` records `provider_refund_id` and returns stored results if a refund already exists.

Operational notes:
- Keep `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in env vars or a secrets manager. Do not commit them.
- In production, ensure the webhook verification helper uses `STRIPE_WEBHOOK_SECRET` to validate signatures.

## Inventory integration (gallery)

Design summary:

- Multi-quantity SKUs: use integer `stock` on `gallery.StockItem`. On payment success the webhook decrements stock by ordered quantity.
- One-of-a-kind items: set `is_unique=True`. Reservation occurs at order-create (if quantity==1) by flipping `status` from `available` to `reserved`; the webhook finalizes by setting `status` to `sold`.
- `OrderItem.product_status` snapshots the product status at the time the order was created so staff can see what the customer purchased.
- MVP policy (Option A): if payment succeeds but stock is insufficient, the order is allowed to complete and `order.stock_shortage` is flagged for staff follow-up.

## Middleware

The repository includes `orders.middleware.RequireJSONForOrdersCreate` which returns a helpful 415 JSON error when non-JSON content is POSTed to the orders create endpoint. Consider changing the middleware to match by route name (`request.resolver_match.view_name`) for more robust deployments.

## Admin & refunds

- Admin actions:
  - `mark_shipped` — set selected orders to shipped.
  - `mark_refunded` — trigger `PaymentRecord.issue_refund()` across related payments and set order status to refunded.
- Staff-only refund endpoint: `POST /orders/refund/<payment_id>/`.

Manual refund guidance:

1. Prefer issuing the refund in the provider dashboard (Stripe) and recording the refund via the admin or shell.
2. Alternatively use the staff API which calls `PaymentRecord.issue_refund()`; this helper is idempotent and records provider response.

## Local development & testing

1) Prepare environment (PowerShell):

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Apply migrations and run server:

```powershell
python manage.py migrate
python manage.py createsuperuser  # optional
python manage.py runserver
```

3) Webhook dev: use Stripe CLI to forward webhook events:

```powershell
stripe listen --forward-to localhost:8000/orders/webhook/
```

4) Run only the orders tests during development:

```powershell
python manage.py test orders -v 2
```

## Tests

The `orders` app contains tests in `orders/tests.py` covering:

- Model behaviors (order_number, totals, reservation expiry)
- Payments helper fallback and refund idempotency
- API behavior (create/start-payment/refund endpoints)
- Webhook idempotency and stock handling
- Concurrency/oversell protection tests

Note: tests mock Stripe where appropriate; real Stripe keys are not required to run the orders tests locally.

## Unfinished components / actionable next steps

These tasks are not blockers for an MVP demo but are recommended to improve robustness, maintainability and production-readiness.

High priority

- Run the full project test suite and fix any regressions outside the `orders` app.
- Enable webhook signature verification using `STRIPE_WEBHOOK_SECRET` in production and ensure `orders.payments.verify_stripe_event` uses it.
- Move confirmation email sending out of the webhook into a background job (Celery/RQ) to avoid blocking webhook responses.

Medium priority

- Add CI (GitHub Actions or similar) to run tests on push/PR.
- Add a small data migration or management command to convert legacy `StockItem` rows to `is_unique=True` where appropriate (if you have legacy items with stock==1 that are actually unique).
- Harden refund/reconciliation flows: a management command to reconcile provider refunds vs `PaymentRecord` rows.

Low priority / Nice-to-have

- Reservation expiry worker to release `reserved` items after timeout.
- Add interactive OpenAPI docs (drf-spectacular) and wire a small `/orders/docs/` page for developers.
- Provider adapters (PayPal, Klarna) and more comprehensive payment integration tests.

## Appendix: useful shell snippets

- Mark an item as unique and set its status:

```powershell
python manage.py shell
from gallery.models import StockItem
p = StockItem.objects.get(sku='ONE-1')
p.is_unique = True
p.status = 'available'
p.save()
```

- Bulk-mark stock==1 items as unique (one-liner):

```powershell
python manage.py shell -c "from gallery.models import StockItem; StockItem.objects.filter(stock=1).update(is_unique=True)"
```

- Manual refund via shell:

```py
from django.utils import timezone
from orders.models import PaymentRecord
p = PaymentRecord.objects.get(pk=1)
p.provider_refund_id = 're_...'
p.raw_response = {'note': 'Refunded manually in Stripe dashboard'}
p.status = PaymentRecord.STATUS_REFUNDED
p.refunded_at = timezone.now()
p.save()
```

---

If you'd like, I can now:

- Run the full project test suite and fix regressions.
- Add middleware tests and convert middleware to route-name matching.
- Create a small management command/data migration to bulk-convert `StockItem` rows to `is_unique` per a rule you specify.

Tell me which follow-up you'd like and I'll implement it (with tests and README updates).

````
- Webhook idempotency: a new `ProcessedEvent` model records provider webhook event ids so duplicate deliveries are skipped. The webhook handler will record an event id on first delivery and return a quick success with `{"skipped": true}` on duplicates.


# MIND//EMBODY//SPIRIT

## Orders API

The `orders` app exposes a minimal REST API for creating orders and starting payments.

- Endpoint: `POST /orders/create/`
	- Content-Type: `application/json` only. Requests must send valid JSON. The API enforces strict JSON parsing.
	- Body (example):

```json
{
	"guest_email": "guest@example.com",
	"currency": "EUR",
	"items": [
		{"product_title": "Blue T-shirt", "product_sku": "TSHIRT-BLUE", "unit_price": 19.99, "quantity": 2}
	],
	"shipping_address": {"line1": "123 Street", "city": "Town", "postal_code": "12345", "country": "IE"}
}
```

- Endpoint: `POST /orders/start-payment/<order_id>/` — starts a payment and returns a `client_secret` (Stripe) and `payment_id`.
- Schema: `GET /orders/schema/` — minimal DRF schema for the orders endpoints.

Notes:
- Authenticated users may omit `guest_email` if the frontend provides an authenticated session/cookie; otherwise `guest_email` is required for anonymous checkout.
- The API intentionally rejects non-JSON bodies; if you need to support form-encoded clients, add a client-side JSON wrapper or update the server to accept additional parser types.
 
Middleware and helpful errors
----------------------------

The project includes a small middleware `orders.middleware.RequireJSONForOrdersCreate` which returns a friendly JSON 415 response when a non-JSON request is sent to `POST /orders/create/`. This avoids HTML error pages and provides a helpful hint for client developers.

Manual testing examples (PowerShell)
----------------------------------

# Successful JSON request (replace host and payload as needed)
```powershell
curl -Method POST -Uri http://localhost:8000/orders/create/ -Headers @{ 'Content-Type' = 'application/json' } -Body ('{ "guest_email": "x@x.com", "currency": "EUR", "items": [] }')
```

# Non-JSON request (will be rejected with a 415 JSON response)
```powershell
curl -Method POST -Uri http://localhost:8000/orders/create/ -Body @{ guest_email = 'x@x.com' }
```

Testing notes
-------------

- The orders test suite covers the API and middleware behavior; run it with:

```powershell
python manage.py test orders -v 2
```

If you want the middleware to apply to additional endpoints or to match by route name instead of path, I can update it to use `request.resolver_match`.