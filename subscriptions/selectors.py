from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from . import conf
from .models import EntitlementOverride, Plan, Subscription, SubscriptionStatus


def _identity_kwargs(*, tenant=None, user=None) -> Dict[str, Any]:
    tenant_configured = conf.tenant_model_label() is not None
    if tenant_configured:
        if tenant is None:
            raise ValidationError("tenant is required when SUBSCRIPTIONS_TENANT_MODEL is configured.")
        identity = {"tenant": tenant}
        if user is not None:
            identity["user"] = user
        return identity
    if user is None:
        raise ValidationError("user is required when tenant model is not configured.")
    return {"user": user}


def _current_queryset(at_dt):
    return Subscription.objects.filter(
        starts_at__lte=at_dt,
    ).filter(Q(ends_at__gt=at_dt) | Q(ends_at__isnull=True) | Q(grace_ends_at__gt=at_dt))


def compute_subscription_status(subscription: Subscription, at_dt) -> str:
    at_dt = at_dt or timezone.now()
    if subscription.status == SubscriptionStatus.CANCELLED:
        if subscription.grace_ends_at and at_dt < subscription.grace_ends_at:
            return SubscriptionStatus.GRACE
        return SubscriptionStatus.CANCELLED
    if subscription.trial_ends_at and at_dt < subscription.trial_ends_at:
        return SubscriptionStatus.TRIAL
    if subscription.trial_ends_at and at_dt >= subscription.trial_ends_at and subscription.status == SubscriptionStatus.TRIAL:
        return SubscriptionStatus.ACTIVE
    if subscription.grace_ends_at and at_dt < subscription.grace_ends_at:
        return SubscriptionStatus.GRACE
    if subscription.ends_at and at_dt >= subscription.ends_at:
        return SubscriptionStatus.EXPIRED
    return subscription.status


def get_current_subscription(*, tenant=None, user=None, at_dt=None) -> Optional[Subscription]:
    at_dt = at_dt or timezone.now()
    identity = _identity_kwargs(tenant=tenant, user=user)
    qs = _current_queryset(at_dt).filter(**identity).order_by("-starts_at", "-created_at")
    subscription = qs.first()
    if subscription and compute_subscription_status(subscription, at_dt) == SubscriptionStatus.EXPIRED:
        return None
    return subscription


def get_plan(*, slug: str) -> Plan:
    return Plan.objects.get(slug=slug)


def resolve_entitlements(*, tenant=None, user=None, at_dt=None) -> Dict[str, Any]:
    at_dt = at_dt or timezone.now()
    status = SubscriptionStatus.EXPIRED
    features: Dict[str, Any] = {}
    limits: Dict[str, Any] = {}

    default_plan_slug = conf.get_setting("SUBSCRIPTIONS_DEFAULT_PLAN_SLUG")
    subscription = None
    plan = None
    try:
        subscription = get_current_subscription(tenant=tenant, user=user, at_dt=at_dt)
    except ValidationError:
        subscription = None

    if subscription:
        plan = subscription.plan
        status = compute_subscription_status(subscription, at_dt)
    elif default_plan_slug:
        try:
            plan = Plan.objects.get(slug=default_plan_slug)
            status = SubscriptionStatus.ACTIVE
        except Plan.DoesNotExist:
            plan = None

    if plan:
        features = copy.deepcopy(plan.features or {})
        limits = copy.deepcopy(plan.limits or {})

    if conf.overrides_enabled():
        try:
            identity = _identity_kwargs(tenant=tenant, user=user)
        except ValidationError:
            identity = {}

        if identity:
            override_qs = EntitlementOverride.objects.filter(**identity)
            for override in override_qs:
                if override.feature_enabled is not None:
                    features[override.feature_key] = override.feature_enabled
                if override.limit_key:
                    limits[override.limit_key] = override.limit_value

    return {"features": features, "limits": limits, "status": status}
