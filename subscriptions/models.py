from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class BillingPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"


class SubscriptionPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price_ttd = models.DecimalField(max_digits=10, decimal_places=2)
    billing_period = models.CharField(max_length=20, choices=BillingPeriod.choices)
    is_active = models.BooleanField(default=True)
    max_active_listings = models.IntegerField(null=True, blank=True)
    featured_credits_per_period = models.PositiveIntegerField(default=0)
    badge_label = models.CharField(max_length=150, blank=True)
    priority_support = models.BooleanField(default=False)
    can_add_multiple_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.max_active_listings is not None and self.max_active_listings < 0:
            raise ValidationError("max_active_listings cannot be negative.")


class SubscriptionProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=150, unique=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="products")
    period_days = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sku"]

    def __str__(self) -> str:
        return f"{self.sku} -> {self.plan.key}"


class UserSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="user_subscriptions")
    status = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE
    )
    started_at = models.DateTimeField()
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField(db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    last_paid_order_reference = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-current_period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=SubscriptionStatus.ACTIVE),
                name="unique_active_subscription_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.plan}"

    def is_active(self, at=None) -> bool:
        at = at or timezone.now()
        return self.status == SubscriptionStatus.ACTIVE and self.current_period_end > at

    def mark_expired(self, at=None):
        self.status = SubscriptionStatus.EXPIRED
        self.current_period_end = at or self.current_period_end
        self.save(update_fields=["status", "current_period_end", "updated_at"])

    def extend(self, days: int):
        self.current_period_start = self.current_period_end
        self.current_period_end = self.current_period_end + timedelta(days=days)
        self.save(update_fields=["current_period_start", "current_period_end", "updated_at"])


class SubscriptionCreditLedger(models.Model):
    class CreditType(models.TextChoices):
        FEATURED = "featured", "Featured"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_credit_entries")
    subscription = models.ForeignKey(
        UserSubscription, on_delete=models.PROTECT, related_name="credit_entries"
    )
    credit_type = models.CharField(max_length=50, choices=CreditType.choices)
    change = models.IntegerField()
    reason = models.CharField(max_length=255)
    related_order_reference = models.CharField(max_length=255, null=True, blank=True)
    related_listing_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.credit_type}: {self.change}"


class ProcessedSubscriptionOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_reference = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="processed_subscription_orders"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="processed_orders"
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at"]

    def __str__(self) -> str:
        return f"{self.order_reference} -> {self.plan.key}"
