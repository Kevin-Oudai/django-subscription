from __future__ import annotations

import datetime
from functools import wraps
from typing import Any, Dict, Tuple

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import conf
from .models import Plan, Subscription, SubscriptionStatus, UsageCounter
from .selectors import _identity_kwargs, compute_subscription_status, resolve_entitlements


def assign_plan(
    *,
    plan: Plan | str,
    tenant=None,
    user=None,
    starts_at=None,
    trial_days=None,
) -> Subscription:
    """Assign a plan to the tenant/user, expiring any previous current subscription."""
    starts_at = starts_at or timezone.now()
    identity = _identity_kwargs(tenant=tenant, user=user)
    trial_days = conf.trial_days_default() if trial_days is None else trial_days
    if isinstance(plan, str):
        plan = Plan.objects.get(slug=plan)

    with transaction.atomic():
        current = (
            Subscription.objects.select_for_update()
            .filter(**identity, starts_at__lte=starts_at)
            .order_by("-starts_at", "-created_at")
            .first()
        )
        if current:
            current.ends_at = starts_at
            current.status = SubscriptionStatus.EXPIRED
            current.save(update_fields=["ends_at", "status", "updated_at"])

        trial_end = (
            starts_at + datetime.timedelta(days=trial_days) if trial_days and trial_days > 0 else None
        )
        status = SubscriptionStatus.TRIAL if trial_end and starts_at < trial_end else SubscriptionStatus.ACTIVE

        subscription = Subscription.objects.create(
            plan=plan,
            starts_at=starts_at,
            trial_ends_at=trial_end,
            status=status,
            cancel_at_period_end=True,
            **identity,
        )
    return subscription


def cancel_subscription(subscription: Subscription, *, at_period_end: bool = True) -> Subscription:
    """Cancel a subscription, optionally letting it run until period end with grace."""
    now = timezone.now()
    grace_days = conf.grace_days_default()
    with transaction.atomic():
        if at_period_end and not subscription.ends_at:
            subscription.ends_at = now
        if not at_period_end:
            subscription.ends_at = now

        if grace_days and grace_days > 0:
            grace_end = (subscription.ends_at or now) + datetime.timedelta(days=grace_days)
            subscription.grace_ends_at = grace_end
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancel_at_period_end = at_period_end
        subscription.save(
            update_fields=["ends_at", "grace_ends_at", "status", "cancel_at_period_end", "updated_at"]
        )
    return subscription


def _usage_identity(*, tenant=None, user=None) -> Dict[str, Any]:
    return _identity_kwargs(tenant=tenant, user=user)


def _usage_period(key: str, at_dt) -> Tuple[datetime.date, datetime.date]:
    dt = (at_dt or timezone.now()).date()
    if key.endswith("_per_month"):
        return UsageCounter.month_bounds(dt)
    # default to monthly until additional period strategies are added
    return UsageCounter.month_bounds(dt)


def increment_usage(*, key: str, amount: int = 1, tenant=None, user=None, at_dt=None) -> UsageCounter:
    if not conf.usage_enabled():
        raise ImproperlyConfigured("Usage tracking is disabled via SUBSCRIPTIONS_ENABLE_USAGE.")
    identity = _usage_identity(tenant=tenant, user=user)
    period_start, period_end = _usage_period(key, at_dt)
    with transaction.atomic():
        counter, created = UsageCounter.objects.select_for_update().get_or_create(
            key=key,
            period_start=period_start,
            period_end=period_end,
            defaults={"used": 0, **identity},
        )
        if not created:
            for field, value in identity.items():
                setattr(counter, field, value)
        counter.used = F("used") + amount
        counter.save(update_fields=list(identity.keys()) + ["used", "updated_at"])
        counter.refresh_from_db()
    return counter


def check_limit(*, key: str, tenant=None, user=None, at_dt=None) -> Tuple[bool, int | None]:
    entitlements = resolve_entitlements(tenant=tenant, user=user, at_dt=at_dt)
    limit_value = entitlements["limits"].get(key)
    if limit_value is None:
        return True, None
    if not conf.usage_enabled():
        return True, limit_value
    identity = _usage_identity(tenant=tenant, user=user)
    period_start, period_end = _usage_period(key, at_dt)
    used = (
        UsageCounter.objects.filter(
            key=key, period_start=period_start, period_end=period_end, **identity
        ).values_list("used", flat=True)
    )
    current_used = used[0] if used else 0
    remaining = limit_value - current_used
    return remaining > 0, max(0, remaining)


def enforce_limit(*, key: str, tenant=None, user=None, at_dt=None) -> Tuple[bool, int | None]:
    allowed, remaining = check_limit(key=key, tenant=tenant, user=user, at_dt=at_dt)
    if not allowed:
        raise ValidationError(f"Limit '{key}' has been reached.")
    return allowed, remaining


def require_feature(feature_key: str):
    """Decorator ensuring the feature is enabled for the tenant/user."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            entitlements = resolve_entitlements(
                tenant=kwargs.get("tenant"), user=kwargs.get("user"), at_dt=kwargs.get("at_dt")
            )
            if not entitlements["features"].get(feature_key, False):
                raise ValidationError(f"Feature '{feature_key}' is not enabled for this subscription.")
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_limit(limit_key: str, *, amount: int = 1):
    """Decorator ensuring a limit is not exceeded before proceeding."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tenant = kwargs.get("tenant")
            user = kwargs.get("user")
            at_dt = kwargs.get("at_dt")
            allowed, _ = check_limit(key=limit_key, tenant=tenant, user=user, at_dt=at_dt)
            if not allowed:
                raise ValidationError(f"Limit '{limit_key}' has been reached.")
            if conf.usage_enabled():
                increment_usage(key=limit_key, amount=amount, tenant=tenant, user=user, at_dt=at_dt)
            return func(*args, **kwargs)

        return wrapper

    return decorator
