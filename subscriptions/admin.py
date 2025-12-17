from django.contrib import admin

from .models import (
    ProcessedSubscriptionOrder,
    SubscriptionCreditLedger,
    SubscriptionPlan,
    SubscriptionProduct,
    SubscriptionStatus,
    UserSubscription,
)
from .services import grant_featured_credits


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "billing_period",
        "is_active",
        "price_ttd",
        "featured_credits_per_period",
        "max_active_listings",
    )
    list_filter = ("billing_period", "is_active")
    search_fields = ("name", "key")
    ordering = ("name",)


@admin.register(SubscriptionProduct)
class SubscriptionProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "plan", "period_days", "is_active")
    list_filter = ("is_active", "plan")
    search_fields = ("sku",)
    ordering = ("sku",)


@admin.action(description="Mark selected subscriptions as expired")
def expire_selected(modeladmin, request, queryset):
    queryset.update(status=SubscriptionStatus.EXPIRED)


@admin.action(description="Grant plan featured credits to selected subscriptions")
def grant_plan_credits(modeladmin, request, queryset):
    for subscription in queryset.select_related("plan"):
        grant_featured_credits(subscription, reason="admin_grant")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "current_period_end",
        "last_paid_order_reference",
    )
    list_filter = ("status", "plan")
    search_fields = ("user__username", "last_paid_order_reference")
    actions = (expire_selected, grant_plan_credits)
    ordering = ("-current_period_end",)


@admin.register(SubscriptionCreditLedger)
class SubscriptionCreditLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "subscription", "credit_type", "change", "reason", "created_at")
    list_filter = ("credit_type", "reason")
    readonly_fields = (
        "user",
        "subscription",
        "credit_type",
        "change",
        "reason",
        "related_order_reference",
        "related_listing_id",
        "created_at",
    )
    search_fields = ("user__username", "reason", "related_order_reference")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ProcessedSubscriptionOrder)
class ProcessedSubscriptionOrderAdmin(admin.ModelAdmin):
    list_display = ("order_reference", "user", "plan", "processed_at")
    search_fields = ("order_reference", "user__username")
    readonly_fields = ("order_reference", "user", "plan", "processed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
