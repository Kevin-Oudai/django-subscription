# Luk It Hyah Subscriptions

Business subscriptions for the Luk It Hyah Trinidad classifieds platform. This app listens to paid orders, activates/renews subscriptions, and exposes entitlements to the rest of the system. Payments remain the source of truth; this app never charges cards directly.

## Data Model

- `SubscriptionPlan`: defines packages (`key`, price info, billing period, entitlements such as `max_active_listings`, `featured_credits_per_period`, `badge_label`, `priority_support`, `can_add_multiple_staff`).
- `SubscriptionProduct`: maps payment SKUs to plans and a number of days (`period_days`) to add when paid.
- `UserSubscription`: current state for a user (`status` active/expired/cancelled, `current_period_start`, `current_period_end`, `last_paid_order_reference`). One active row per user enforced by constraint.
- `SubscriptionCreditLedger`: append-only ledger for featured credits (`change` +N or -N, `reason`, optional order reference or listing id). Balance is the sum of `change`.
- `ProcessedSubscriptionOrder`: idempotency guard so the same order reference is never processed twice.

## Activation & Renewal Flow

1) The payments app emits `payments.order_paid` with an order containing items.  
2) `subscriptions.signals.on_order_paid` inspects each item. If `item.sku` matches an active `SubscriptionProduct`, it calls `activate_or_renew_subscription_from_order_item(order, transaction, item, user)`.
3) `activate_or_renew_subscription_from_order_item`:
   - Resolves the product to a plan and period.
   - Aborts if the order reference was already recorded in `ProcessedSubscriptionOrder` (idempotent).
   - If the user has an active subscription on the same plan, extends `current_period_end` by `period_days` and shifts `current_period_start` to the previous end.
   - If the user has a different active plan, expires it immediately and creates a new subscription starting now.
   - If no active subscription exists, creates a fresh one starting now.
   - Records `last_paid_order_reference` and logs a credit grant if the plan includes featured credits.

## SKU Contract

- Every billable subscription SKU in the payments catalog must exist as an active `SubscriptionProduct` with the correct `plan` and `period_days` (e.g., `BUS_SUB_MONTH_BASIC` → 30 days on plan `business_basic`).  
- Order items must expose `.sku` (or `.product_sku`) and orders should provide a stable `reference` used for idempotency.

## Entitlements API (for other apps)

Import from `subscriptions.entitlements`:

- `get_active_subscription(user) -> UserSubscription | None`
- `has_active_subscription(user) -> bool`
- `get_entitlements(user) -> dict` returns `max_active_listings`, `featured_credits_balance`, `badge_label`, `priority_support`.
- `can_post_listing(user) -> (bool, reason)` (currently enforces active subscription and returns a reason string; hook classifieds limits here later).
- `consume_featured_credit(user, listing_id, reason) -> bool` subtracts one featured credit if balance > 0 and records the ledger entry.

No other app needs to touch subscription internals; check entitlements and ledger balances through this API.

## Credit Ledger

Credits are granted on activation/renewal (and optionally via the `grant_monthly_credits` command). Consumption always writes a `SubscriptionCreditLedger` row with `change = -1`. Balance for a subscription is `sum(change)` for entries with `credit_type="featured"`.

## Operations

- **Expiry:** run `expire_due_subscriptions` (or a periodic task calling it) to mark subscriptions with `current_period_end <= now` as expired. Entitlement helpers call it before lookups to keep status in sync.
- **Monthly grants:** `python manage.py grant_monthly_credits` grants featured credits at the start of a billing period (idempotent per day). Activation/renewal already grants credits; the command is a safety net.
- **Admin:** manage plans/products, expire subscriptions, and view the append-only ledger. Processed orders are read-only.

## Tests

Expected behaviours covered by tests:
- Activation creates an active subscription with the correct period end.
- Renewals extend periods; plan changes replace the active subscription.
- Idempotency prevents double-processing the same order.
- Ledger grants featured credits and consumption stops at zero.
- Expiry marks overdue subscriptions as expired.
