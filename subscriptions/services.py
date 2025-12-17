from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    ProcessedSubscriptionOrder,
    SubscriptionCreditLedger,
    SubscriptionProduct,
    SubscriptionStatus,
    UserSubscription,
)
from .selectors import (
    get_active_subscription_for_user,
    get_featured_credit_balance,
    get_subscription_product_by_sku,
)


def _extract_order_reference(order, item) -> str:
    for source in (order, item):
        for attr in (
            "reference",
            "order_reference",
            "external_reference",
            "id",
            "pk",
            "code",
        ):
            value = getattr(source, attr, None)
            if value:
                return str(value)
    return ""


def grant_featured_credits(subscription: UserSubscription, *, reason: str, order_reference: str | None = None):
    credits = subscription.plan.featured_credits_per_period
    if credits and credits > 0:
        SubscriptionCreditLedger.objects.create(
            user=subscription.user,
            subscription=subscription,
            credit_type=SubscriptionCreditLedger.CreditType.FEATURED,
            change=credits,
            reason=reason,
            related_order_reference=order_reference,
        )


def activate_or_renew_subscription_from_order_item(order, transaction, item, user) -> UserSubscription | None:
    sku = getattr(item, "sku", None) or getattr(item, "product_sku", None)
    product = get_subscription_product_by_sku(sku) if sku else None
    if not product or not user:
        return None

    order_reference = _extract_order_reference(order, item) or str(uuid.uuid4())
    now = timezone.now()

    with db_transaction.atomic():
        if ProcessedSubscriptionOrder.objects.filter(order_reference=order_reference).exists():
            return get_active_subscription_for_user(user, now=now, for_update=True)

        expire_due_subscriptions(now=now)

        active_subscription = get_active_subscription_for_user(user, now=now, for_update=True)
        target_subscription: UserSubscription

        if active_subscription and active_subscription.plan_id == product.plan_id:
            active_subscription.current_period_start = active_subscription.current_period_end
            active_subscription.current_period_end = active_subscription.current_period_end + timedelta(
                days=product.period_days
            )
            active_subscription.last_paid_order_reference = order_reference
            active_subscription.status = SubscriptionStatus.ACTIVE
            active_subscription.save(
                update_fields=[
                    "current_period_start",
                    "current_period_end",
                    "last_paid_order_reference",
                    "status",
                    "updated_at",
                ]
            )
            target_subscription = active_subscription
        else:
            if active_subscription:
                active_subscription.status = SubscriptionStatus.EXPIRED
                active_subscription.save(update_fields=["status", "updated_at"])

            target_subscription = UserSubscription.objects.create(
                user=user,
                plan=product.plan,
                status=SubscriptionStatus.ACTIVE,
                started_at=now,
                current_period_start=now,
                current_period_end=now + timedelta(days=product.period_days),
                cancelled_at=None,
                last_paid_order_reference=order_reference,
            )

        ProcessedSubscriptionOrder.objects.create(
            order_reference=order_reference, user=user, plan=product.plan
        )

        grant_featured_credits(
            target_subscription, reason="activation_grant", order_reference=order_reference
        )
        return target_subscription


def expire_due_subscriptions(now=None) -> int:
    now = now or timezone.now()
    return UserSubscription.objects.filter(
        status=SubscriptionStatus.ACTIVE, current_period_end__lte=now
    ).update(status=SubscriptionStatus.EXPIRED)


def consume_featured_credit(subscription: UserSubscription, *, listing_id=None, reason: str = "consume") -> bool:
    with db_transaction.atomic():
        subscription = (
            UserSubscription.objects.select_for_update()
            .filter(pk=subscription.pk, status=SubscriptionStatus.ACTIVE)
            .first()
        )
        if not subscription:
            return False

        balance = get_featured_credit_balance(subscription)
        if balance <= 0:
            return False

        SubscriptionCreditLedger.objects.create(
            user=subscription.user,
            subscription=subscription,
            credit_type=SubscriptionCreditLedger.CreditType.FEATURED,
            change=-1,
            reason=reason,
            related_listing_id=listing_id,
        )
        return True


def grant_periodic_credits(now=None) -> int:
    now = now or timezone.now()
    today = now.date()
    subscriptions = (
        UserSubscription.objects.select_related("plan", "user")
        .filter(
            status=SubscriptionStatus.ACTIVE,
            current_period_start__date=today,
            plan__featured_credits_per_period__gt=0,
        )
        .all()
    )

    created = 0
    for subscription in subscriptions:
        existing_today = subscription.credit_entries.filter(
            reason="monthly_grant", created_at__date=today
        ).exists()
        if existing_today:
            continue
        grant_featured_credits(subscription, reason="monthly_grant")
        created += 1
    return created
