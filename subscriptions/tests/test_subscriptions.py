import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from subscriptions.models import EntitlementOverride, Plan, UsageCounter
from subscriptions.selectors import compute_subscription_status, resolve_entitlements
from subscriptions.services import (
    assign_plan,
    cancel_subscription,
    check_limit,
    enforce_limit,
    increment_usage,
)


class PlanValidationTests(TestCase):
    def test_features_require_booleans(self):
        plan = Plan(name="Bad", slug="bad", features={"booking_ui": "yes"})
        with self.assertRaises(ValidationError):
            plan.full_clean()

    def test_limits_require_non_negative_ints_or_none(self):
        plan = Plan(name="Bad2", slug="bad2", limits={"bookings": -1})
        with self.assertRaises(ValidationError):
            plan.full_clean()


class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice")
        self.plan_free = Plan.objects.create(
            name="Free",
            slug="free",
            features={"booking_ui": True},
            limits={"bookings_per_month": 2},
        )
        self.plan_pro = Plan.objects.create(
            name="Pro",
            slug="pro",
            features={"booking_ui": True, "multi_staff": True},
            limits={"bookings_per_month": 5},
        )

    def test_assign_plan_expires_previous(self):
        starts = timezone.now()
        sub1 = assign_plan(plan=self.plan_free, tenant=self.user, starts_at=starts)
        later = starts + datetime.timedelta(days=1)
        sub2 = assign_plan(plan=self.plan_pro, tenant=self.user, starts_at=later)
        sub1.refresh_from_db()
        self.assertEqual(sub1.ends_at, later)
        self.assertEqual(sub1.status, "EXPIRED")
        self.assertEqual(sub2.plan, self.plan_pro)

    def test_entitlements_merge_overrides(self):
        assign_plan(plan=self.plan_free, tenant=self.user)
        EntitlementOverride.objects.create(
            tenant=self.user,
            feature_key="booking_ui",
            feature_enabled=False,
            limit_key="bookings_per_month",
            limit_value=99,
        )
        entitlements = resolve_entitlements(tenant=self.user)
        self.assertFalse(entitlements["features"]["booking_ui"])
        self.assertEqual(entitlements["limits"]["bookings_per_month"], 99)

    def test_trial_and_grace_status_resolution(self):
        starts = timezone.now()
        sub = assign_plan(plan=self.plan_free, tenant=self.user, starts_at=starts, trial_days=3)
        ent_trial = resolve_entitlements(tenant=self.user, at_dt=starts + datetime.timedelta(days=1))
        self.assertEqual(ent_trial["status"], "TRIAL")

        ent_active = resolve_entitlements(tenant=self.user, at_dt=starts + datetime.timedelta(days=5))
        self.assertEqual(ent_active["status"], "ACTIVE")

        cancel_subscription(sub, at_period_end=False)
        ent_grace = resolve_entitlements(tenant=self.user, at_dt=timezone.now())
        self.assertEqual(ent_grace["status"], "GRACE")

    def test_usage_increment_and_enforcement(self):
        assign_plan(plan=self.plan_free, tenant=self.user)
        allowed, remaining = check_limit(key="bookings_per_month", tenant=self.user)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 2)

        increment_usage(key="bookings_per_month", tenant=self.user)
        increment_usage(key="bookings_per_month", tenant=self.user)
        allowed, remaining = check_limit(key="bookings_per_month", tenant=self.user)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        with self.assertRaises(ValidationError):
            enforce_limit(key="bookings_per_month", tenant=self.user)

    @override_settings(SUBSCRIPTIONS_TENANT_MODEL=None)
    def test_user_mode_allows_user_only(self):
        # When tenant model is not configured, user is required and tenant is optional.
        sub = assign_plan(plan=self.plan_free, user=self.user, trial_days=0)
        entitlements = resolve_entitlements(user=self.user)
        self.assertEqual(entitlements["status"], "ACTIVE")
        self.assertIsNone(getattr(sub, "tenant", None))

    @override_settings(SUBSCRIPTIONS_ENABLE_USAGE=False)
    def test_usage_disabled(self):
        assign_plan(plan=self.plan_free, tenant=self.user)
        allowed, remaining = check_limit(key="bookings_per_month", tenant=self.user)
        self.assertTrue(allowed)
        with self.assertRaises(ImproperlyConfigured):
            increment_usage(key="bookings_per_month", tenant=self.user)
