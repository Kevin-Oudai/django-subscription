from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone

from .models import (
    SubscriptionCreditLedger,
    SubscriptionProduct,
    SubscriptionStatus,
    UserSubscription,
)


def get_subscription_product_by_sku(sku: str) -> SubscriptionProduct | None:
    return (
        SubscriptionProduct.objects.filter(sku=sku, is_active=True)
        .select_related("plan")
        .first()
    )


def get_active_subscription_for_user(user, now=None, for_update: bool = False) -> UserSubscription | None:
    now = now or timezone.now()
    qs = UserSubscription.objects.filter(
        user=user, status=SubscriptionStatus.ACTIVE, current_period_end__gt=now
    )
    if for_update:
        qs = qs.select_for_update()
    return qs.order_by("-current_period_end", "-created_at").first()


def get_featured_credit_balance(subscription: UserSubscription) -> int:
    total = (
        SubscriptionCreditLedger.objects.filter(
            subscription=subscription, credit_type=SubscriptionCreditLedger.CreditType.FEATURED
        ).aggregate(total=Sum("change"))
    )["total"]
    return total or 0
