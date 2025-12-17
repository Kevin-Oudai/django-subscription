from __future__ import annotations

from django.utils import timezone

from .models import SubscriptionStatus
from .selectors import (
    get_active_subscription_for_user,
    get_featured_credit_balance,
)
from .services import consume_featured_credit as _consume_credit
from .services import expire_due_subscriptions


def get_active_subscription(user):
    now = timezone.now()
    expire_due_subscriptions(now=now)
    return get_active_subscription_for_user(user, now=now)


def has_active_subscription(user) -> bool:
    return get_active_subscription(user) is not None


def get_entitlements(user) -> dict:
    subscription = get_active_subscription(user)
    if not subscription:
        return {
            "max_active_listings": None,
            "featured_credits_balance": 0,
            "badge_label": "",
            "priority_support": False,
        }

    plan = subscription.plan
    return {
        "max_active_listings": plan.max_active_listings,
        "featured_credits_balance": get_featured_credit_balance(subscription),
        "badge_label": plan.badge_label,
        "priority_support": plan.priority_support,
    }


def can_post_listing(user):
    subscription = get_active_subscription(user)
    if not subscription:
        return False, "no_active_subscription"

    entitlements = get_entitlements(user)
    max_active = entitlements["max_active_listings"]
    if max_active is None:
        return True, "unlimited"
    return True, "limit_not_enforced_in_mvp"


def consume_featured_credit(user, listing_id=None, reason: str = "consume"):
    subscription = get_active_subscription(user)
    if not subscription or subscription.status != SubscriptionStatus.ACTIVE:
        return False
    return _consume_credit(subscription, listing_id=listing_id, reason=reason)
