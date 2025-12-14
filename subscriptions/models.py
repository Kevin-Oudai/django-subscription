from __future__ import annotations

import calendar
from datetime import date

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from . import conf

TENANT_MODEL_LABEL = conf.tenant_model_label()
USER_MODEL_LABEL = conf.user_model_label()


def _tenant_fk_kwargs(related_name: str):
    if not TENANT_MODEL_LABEL:
        return None
    return {
        "to": TENANT_MODEL_LABEL,
        "on_delete": models.CASCADE,
        "null": True,
        "blank": True,
        "related_name": related_name,
    }


HAS_TENANT = TENANT_MODEL_LABEL is not None


class SubscriptionStatus(models.TextChoices):
    TRIAL = "TRIAL", "Trial"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    GRACE = "GRACE", "Grace"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"


class Plan(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    features = models.JSONField(default=dict, blank=True)
    limits = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "slug"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.name}"

    def clean(self):
        errors = {}
        features = self.features or {}
        limits = self.limits or {}

        if not isinstance(features, dict):
            errors["features"] = "Features must be a mapping of flags."
        else:
            for key, value in features.items():
                if not isinstance(key, str):
                    errors["features"] = "Feature keys must be strings."
                    break
                if not isinstance(value, bool):
                    errors["features"] = f"Feature '{key}' must be a boolean."
                    break

        if not isinstance(limits, dict):
            errors["limits"] = "Limits must be a mapping of numeric limits."
        else:
            for key, value in limits.items():
                if not isinstance(key, str):
                    errors["limits"] = "Limit keys must be strings."
                    break
                if value is not None:
                    if not isinstance(value, int):
                        errors["limits"] = f"Limit '{key}' must be an integer or null for unlimited."
                        break
                    if value < 0:
                        errors["limits"] = f"Limit '{key}' must be zero or greater."
                        break

        if errors:
            raise ValidationError(errors)


class Subscription(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    if HAS_TENANT:
        tenant = models.ForeignKey(**_tenant_fk_kwargs("subscription_subscriptions"))
    user = models.ForeignKey(
        USER_MODEL_LABEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscription_user_subscriptions",
    )
    status = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=True)
    external_reference = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "starts_at"]),
        ]

    def __str__(self) -> str:
        label = getattr(self, "tenant", None) or self.user
        return f"{label} -> {self.plan}"


class EntitlementOverride(models.Model):
    if HAS_TENANT:
        tenant = models.ForeignKey(**_tenant_fk_kwargs("subscription_entitlement_overrides"))
    user = models.ForeignKey(
        USER_MODEL_LABEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscription_user_entitlement_overrides",
    )
    feature_key = models.CharField(max_length=150)
    feature_enabled = models.BooleanField(null=True)
    limit_key = models.CharField(max_length=150, blank=True)
    limit_value = models.IntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            *(
                [
                    models.UniqueConstraint(
                        fields=["tenant", "feature_key"], name="subscriptions_feature_override_tenant"
                    ),
                    models.UniqueConstraint(
                        fields=["tenant", "limit_key"], name="subscriptions_limit_override_tenant"
                    ),
                ]
                if HAS_TENANT
                else []
            ),
            models.UniqueConstraint(
                fields=["user", "feature_key"], name="subscriptions_feature_override_user"
            ),
            models.UniqueConstraint(
                fields=["user", "limit_key"], name="subscriptions_limit_override_user"
            ),
        ]

    def __str__(self) -> str:
        subject = getattr(self, "tenant", None) or self.user
        return f"Override for {subject}"


class UsageCounter(models.Model):
    if HAS_TENANT:
        tenant = models.ForeignKey(**_tenant_fk_kwargs("subscription_usage_counters"))
    user = models.ForeignKey(
        USER_MODEL_LABEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscription_user_usage_counters",
    )
    key = models.CharField(max_length=150)
    period_start = models.DateField()
    period_end = models.DateField()
    used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "-created_at"]
        constraints = [
            *(
                [
                    models.UniqueConstraint(
                        fields=["tenant", "key", "period_start", "period_end"],
                        name="subscriptions_usage_tenant_period_key",
                    )
                ]
                if HAS_TENANT
                else []
            ),
            models.UniqueConstraint(
                fields=["user", "key", "period_start", "period_end"],
                name="subscriptions_usage_user_period_key",
            ),
        ]

    def __str__(self) -> str:
        subject = getattr(self, "tenant", None) or self.user
        return f"Usage {self.key} for {subject}"

    @staticmethod
    def month_bounds(dt: date):
        start = date(dt.year, dt.month, 1)
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        end = date(dt.year, dt.month, last_day)
        return start, end


def get_tenant_model():
    if not TENANT_MODEL_LABEL:
        return None
    return apps.get_model(TENANT_MODEL_LABEL, require_ready=False)


def get_user_model():
    return apps.get_model(USER_MODEL_LABEL, require_ready=False)
