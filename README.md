# mroudai-django-subscriptions

Reusable Django app for plans, subscriptions, entitlements, and usage limits. It does **not** process payments.

## Features

- Plans with feature flags and numeric limits.
- Subscriptions scoped to a tenant or user.
- Deterministic entitlement resolution (`resolve_entitlements`).
- Optional per-tenant/user overrides and metered usage tracking.
- Grace periods and trials with sensible defaults.
- Django admin for plans, subscriptions, overrides, and usage counters.

## Installation

```bash
pip install mroudai-django-subscriptions
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "subscriptions",
]
```

Run migrations:

```bash
python manage.py migrate subscriptions
```

## Settings

```python
SUBSCRIPTIONS_TENANT_MODEL = None        # e.g. "tenants.Tenant" or None
SUBSCRIPTIONS_USER_MODEL = None          # defaults to AUTH_USER_MODEL
SUBSCRIPTIONS_DEFAULT_PLAN_SLUG = "free"
SUBSCRIPTIONS_TRIAL_DAYS_DEFAULT = 14
SUBSCRIPTIONS_GRACE_DAYS_DEFAULT = 7
SUBSCRIPTIONS_ENABLE_OVERRIDES = True
SUBSCRIPTIONS_ENABLE_USAGE = True
```

Tenancy rules:
- If `SUBSCRIPTIONS_TENANT_MODEL` is set, subscriptions are tenant-first; user is optional for attribution.
- If it is not set, subscriptions are user-scoped.

## Defining plans

Plans are static and hold flags + limits:

```python
from subscriptions.models import Plan

Plan.objects.create(
    name="Free",
    slug="free",
    features={"booking_ui": True, "multi_staff": False},
    limits={"providers_max": 1, "bookings_per_month": 50},
)
```

Features must be booleans. Limits must be integers `>= 0` or `None` for unlimited.

## Assigning subscriptions

```python
from subscriptions.services import assign_plan

# user-mode example
subscription = assign_plan(plan="pro", user=request.user)
```

This expires any current subscription for the same tenant/user and starts a new one. Trials default to `SUBSCRIPTIONS_TRIAL_DAYS_DEFAULT`.

Cancel with optional grace:

```python
from subscriptions.services import cancel_subscription

cancel_subscription(subscription, at_period_end=False)
```

## Resolving entitlements

```python
from subscriptions.selectors import resolve_entitlements

entitlements = resolve_entitlements(user=request.user)

entitlements == {
    "features": {"booking_ui": True, ...},
    "limits": {"bookings_per_month": 50, ...},
    "status": "ACTIVE",  # TRIAL/GRACE/EXPIRED etc determined by dates
}
```

## Overrides (optional)

If `SUBSCRIPTIONS_ENABLE_OVERRIDES` is `True`, use the admin or create `EntitlementOverride` rows to tweak features/limits per tenant or user. Overrides are applied on top of the plan.

## Usage tracking (optional)

If `SUBSCRIPTIONS_ENABLE_USAGE` is `True`, increment and enforce limits for keys ending with `_per_month`:

```python
from subscriptions.services import increment_usage, enforce_limit

enforce_limit(key="bookings_per_month", user=request.user)
increment_usage(key="bookings_per_month", user=request.user)
```

`check_limit` returns `(allowed, remaining)`; `enforce_limit` raises `ValidationError` if exceeded.

## Decorators

```python
from subscriptions.services import require_feature, require_limit

@require_feature("booking_ui")
def create_booking(*, user, **kwargs):
    ...

@require_limit("bookings_per_month")
def make_booking(*, user, **kwargs):
    ...
```

## Admin

The Django admin registers plans, subscriptions, overrides, and usage counters. JSON fields use a simple textarea for quick editing.

## What this app deliberately does not do

- No payment gateway integration (PayWise/Stripe/etc.).
- No invoicing or receipts.
- No domain-specific booking logic.

## Development

Tests (using SQLite by default):

```bash
python test django-subscriptions
```

SQLite works for development; PostgreSQL is recommended for production.

### Release to PyPI

Install build tooling:

```bash
python install_upload_dependencies.py
```

Build and upload (requires `TWINE_USERNAME`/`TWINE_PASSWORD` or `TWINE_TOKEN`):

```bash
python upload.py
```

## Licence

MIT
