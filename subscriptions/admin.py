from django.contrib import admin
from django.db import models
from django.utils import timezone

from . import conf
from .models import EntitlementOverride, Plan, Subscription, SubscriptionStatus, UsageCounter


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_public", "sort_order")
    search_fields = ("name", "slug")
    list_filter = ("is_active", "is_public")
    ordering = ("sort_order", "name")
    formfield_overrides = {
        models.JSONField: {"widget": admin.widgets.AdminTextareaWidget},
    }


@admin.action(description="Set selected subscriptions to ACTIVE")
def set_active(modeladmin, request, queryset):
    queryset.update(status=SubscriptionStatus.ACTIVE)


@admin.action(description="Set selected subscriptions to CANCELLED (ends now)")
def set_cancelled(modeladmin, request, queryset):
    now = timezone.now()
    queryset.update(status=SubscriptionStatus.CANCELLED, ends_at=now)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "plan",
        "status",
        "starts_at",
        "ends_at",
        "trial_ends_at",
        "grace_ends_at",
    )
    list_filter = ("status", "plan")
    search_fields = ("external_reference",)
    actions = (set_active, set_cancelled)
    ordering = ("-starts_at",)


if conf.overrides_enabled():
    @admin.register(EntitlementOverride)
    class EntitlementOverrideAdmin(admin.ModelAdmin):
        list_display = ("id", "feature_key", "limit_key", "note", "created_at")
        search_fields = ("feature_key", "limit_key", "note")
        list_filter = ("feature_key",)


if conf.usage_enabled():
    @admin.register(UsageCounter)
    class UsageCounterAdmin(admin.ModelAdmin):
        list_display = ("key", "period_start", "period_end", "used")
        list_filter = ("key", "period_start")
        readonly_fields = ("key", "period_start", "period_end", "used", "created_at", "updated_at")
        ordering = ("-period_start",)
